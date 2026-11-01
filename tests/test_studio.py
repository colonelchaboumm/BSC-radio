import hashlib
import json
import sys
import wave

import httpx
import pytest

from bsc_studio.service import StudioService
from bsc_studio.storage import Preferences
from bsc_studio.updater import ASSET_NAME, GitHubUpdater, newer, release_from_json


@pytest.mark.parametrize("candidate,expected", [("v0.1.1", True), ("v0.1.0", False), ("v0.0.9", False),
    ("v0.2.0rc1", False), ("v0.2.0.dev1", False), ("nightly", False), ("v0.10.0", True)])
def test_only_newer_stable_versions(candidate, expected):
    assert newer(candidate, "0.1.0") is expected


def release_payload(data=b"MZinstaller", digest=None):
    return {"tag_name": "v0.1.1", "assets": [{"id": 123, "name": ASSET_NAME, "state": "uploaded",
        "size": len(data), "digest": digest or "sha256:" + hashlib.sha256(data).hexdigest()}]}


def test_private_repository_not_confused_with_no_release():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer private-test"
        return httpx.Response(404, json={})
    updater = GitHubUpdater("private-test", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="dépôt privé"):
        updater.check()


def test_accessible_repo_without_releases_is_normal():
    def handler(request):
        return httpx.Response(404 if request.url.path.endswith("latest") else 200, json={})
    updater = GitHubUpdater("", httpx.Client(transport=httpx.MockTransport(handler)))
    assert updater.check() is None


def test_verified_download_does_not_forward_token_to_cdn(tmp_path):
    data = b"MZthis is a test executable"
    def handler(request):
        if request.url.host == "api.github.com":
            assert request.headers["Authorization"] == "Bearer private-test"
            return httpx.Response(302, headers={"Location": "https://release-assets.githubusercontent.com/file"})
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=data)
    updater = GitHubUpdater("private-test", httpx.Client(transport=httpx.MockTransport(handler)))
    release = release_from_json(release_payload(data))
    assert updater.download(release, tmp_path).read_bytes() == data
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("data,digest", [(b"MZcorrupt", "sha256:" + "0" * 64),
    (b"not-an-exe", "sha256:" + hashlib.sha256(b"not-an-exe").hexdigest())])
def test_invalid_installer_is_never_kept(tmp_path, data, digest):
    updater = GitHubUpdater(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=data))))
    with pytest.raises(RuntimeError):
        updater.download(release_from_json(release_payload(data, digest)), tmp_path)
    assert not (tmp_path / ASSET_NAME).exists()
    assert not list(tmp_path.glob("*.part"))


def test_checksum_manifest_fallback(tmp_path):
    data = b"MZtest"
    manifest = f"{hashlib.sha256(data).hexdigest()}  {ASSET_NAME}\n".encode()
    payload = release_payload(data)
    payload["assets"][0].pop("digest")
    payload["assets"].append({"id": 456, "name": "SHA256SUMS.txt"})
    def handler(request):
        return httpx.Response(200, content=manifest if request.url.path.endswith("456") else data)
    updater = GitHubUpdater(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert updater.download(release_from_json(payload), tmp_path).read_bytes() == data


def test_download_rejects_redirect_to_unrelated_host(tmp_path):
    updater = GitHubUpdater("private-test", httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"Location": "https://example.com/untrusted.exe"}))))
    with pytest.raises(RuntimeError, match="inattendue"):
        updater.download(release_from_json(release_payload()), tmp_path)


def test_import_deduplication_and_demo_script(tmp_path):
    service = StudioService(tmp_path)
    text = "La fermentation est réalisée par les levures. La température est surveillée par les brasseurs."
    assert service.import_text("Fermentation", text)
    assert not service.import_text("Fermentation", text)
    item_id = service.items()[0]["id"]
    episode = service.generate_script("Journal de démonstration", "journal", [item_id], lambda _: None, demo=True)
    assert len(service.script(episode)) >= 2
    assert len(service.db.all("SELECT * FROM fact")) >= 1
    assert service.episodes()[0]["status"] == "draft"


def test_creation_never_publishes_and_titles_do_not_collide(tmp_path):
    service = StudioService(tmp_path)
    first = service.create_episode("Mon podcast")
    second = service.create_episode("Mon podcast")
    assert first != second
    assert all(episode["status"] == "draft" for episode in service.episodes())


def test_audio_cache_and_script_invalidation(tmp_path, monkeypatch):
    if sys.platform != "win32":
        pytest.skip("DPAPI requires Windows")
    service = StudioService(tmp_path)
    service.preferences.save({"voices": {"presenter": "marin"}, "voice_model": "gpt-realtime-2.1-mini"}, {"openai_key": "offline-test-key"})
    episode = service.create_episode("Mon podcast", [
        {"character": "presenter", "text": "Première réplique.", "delivery": [], "fact_ids": []},
        {"character": "presenter", "text": "Deuxième réplique.", "delivery": [], "fact_ids": []}])
    calls = []
    def fake_synthesize(key, model, text, voice, path, direction):
        calls.append(text)
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(b"\0\0" * 24000)
    monkeypatch.setattr("bsc_studio.service.synthesize", fake_synthesize)
    original = service.render(episode, lambda _: None)
    assert service.current_audio(episode) == original
    assert len(calls) == 2
    service.render(episode, lambda _: None)
    assert len(calls) == 2
    lines = service.script(episode)
    lines[1]["text"] = "Deuxième réplique corrigée."
    service.save_script(episode, "Mon podcast", lines)
    with pytest.raises(ValueError, match="script a changé"):
        service.current_audio(episode)
    assert original.exists()
    assert list((tmp_path / "backups").glob("*.json"))
    service.render(episode, lambda _: None)
    assert len(calls) == 3
    service.preferences.save({"voices": {"presenter": "cedar"}})
    with pytest.raises(ValueError, match="voix"):
        service.current_audio(episode)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")
def test_credentials_are_encrypted_for_windows_account(tmp_path):
    prefs = Preferences(tmp_path)
    prefs.save({"text_model": "test"}, {"openai_key": "clé-fictive-123", "github_token": "jeton-fictif-456"})
    raw = prefs.path.read_text(encoding="utf-8")
    assert "clé-fictive" not in raw and "jeton-fictif" not in raw
    assert Preferences(tmp_path).secret("openai_key") == "clé-fictive-123"
    assert Preferences(tmp_path).secret("github_token") == "jeton-fictif-456"


def test_realtime_protocol_collects_pcm_without_real_api(tmp_path, monkeypatch):
    from bsc_studio.openai_provider import synthesize
    import base64
    class Socket:
        def __init__(self):
            self.events = iter([{"type": "session.created"}, {"type": "session.updated"},
                {"type": "response.output_audio.delta", "delta": base64.b64encode(b"\0\0" * 24000).decode()},
                {"type": "response.done", "response": {"status": "completed"}}])
            self.sent = []
        def send(self, value):
            self.sent.append(json.loads(value))
        def recv(self):
            return json.dumps(next(self.events))
        def close(self):
            pass
    socket = Socket()
    monkeypatch.setattr("bsc_studio.openai_provider.websocket.create_connection", lambda *args, **kwargs: socket)
    output = tmp_path / "voice.wav"
    synthesize("fake", "gpt-realtime-2.1-mini", "Bonjour.", "marin", output)
    with wave.open(str(output)) as wav:
        assert wav.getframerate() == 24000 and wav.getnframes() == 24000
    assert [event["type"] for event in socket.sent] == ["session.update", "conversation.item.create", "response.create"]
    assert socket.sent[0]["session"]["audio"]["output"]["voice"] == "marin"


def test_windows_pipeline_lock_excludes_second_writer(tmp_path):
    from bsc_radio.observability import pipeline_lock
    from bsc_radio.config import Settings
    StudioService(tmp_path)
    settings = Settings.load(tmp_path)
    with pipeline_lock(settings):
        with pytest.raises(RuntimeError, match="déjà en cours"):
            with pipeline_lock(settings):
                pass


def test_backup_restores_episode_database(tmp_path):
    import sqlite3
    service = StudioService(tmp_path)
    service.create_episode("Un épisode sauvegardé")
    target = tmp_path / "backup.sqlite3"
    service.backup(target)
    with sqlite3.connect(target) as backup:
        assert backup.execute("SELECT title FROM episode").fetchone()[0] == "Un épisode sauvegardé"
