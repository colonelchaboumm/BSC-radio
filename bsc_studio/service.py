from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import uuid
import wave
from pathlib import Path

import httpx
import imageio_ffmpeg
import trafilatura

from bsc_radio.config import Settings
from bsc_radio.db import Database
from bsc_radio.editorial import EditorialPipeline
from bsc_radio.providers import MockEditorialProvider

from .openai_provider import OpenAIEditorialProvider, synthesize
from .storage import Preferences, initialize

ROLES = {"Camille": "presenter", "Marcel": "consultant", "Jeanne": "storyteller", "Noé": "audience"}
NAMES = {v: k for k, v in ROLES.items()}


class StudioService:
    def __init__(self, root: Path):
        self.root = root
        initialize(root)
        self.preferences = Preferences(root)
        self.settings = Settings.load(root)
        self.db = Database(root / "radio.sqlite3")
        self.db.migrate()
        with self.db.connect() as connection:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(episode)")}
            for name, definition in {"studio_revision": "INTEGER NOT NULL DEFAULT 1", "studio_audio_revision": "INTEGER NOT NULL DEFAULT 0"}.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE episode ADD COLUMN {name} {definition}")
            connection.execute("""CREATE TABLE IF NOT EXISTS studio_audio (
              episode_id INTEGER PRIMARY KEY REFERENCES episode(id), path TEXT NOT NULL,
              script_hash TEXT NOT NULL, duration REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def pipeline(self, demo=False) -> EditorialPipeline:
        provider = MockEditorialProvider() if demo else OpenAIEditorialProvider(
            self.preferences.secret("openai_key"), self.preferences.get("text_model", "gpt-6-luna"), self.root / "prompts")
        return EditorialPipeline(self.settings, self.db, provider)

    def episodes(self):
        return [dict(row) for row in self.db.all("""SELECT e.*,a.path audio_path,a.duration FROM episode e
            LEFT JOIN studio_audio a ON a.episode_id=e.id ORDER BY e.id DESC""")]

    def items(self):
        return [dict(row) for row in self.db.all("SELECT id,title,url,status,collected_at,raw_text FROM item ORDER BY id DESC LIMIT 500")]

    def import_text(self, title: str, text: str, url: str = "") -> bool:
        if len(text.strip()) < 30:
            raise ValueError("Ajoutez au moins 30 caractères d’information.")
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        url = url.strip() or "manual:" + content_hash
        if self.db.one("SELECT id FROM item WHERE url=?", (url,)):
            return False
        now = dt.datetime.now(dt.UTC).isoformat()
        with self.db.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO source(id,name,kind,url,station,enabled,config_json) VALUES('studio-manual','Import studio','manual','','brasserie',1,'{}')")
            connection.execute("""INSERT INTO item(source_id,url,title,published_at,collected_at,content_hash,raw_text)
                VALUES('studio-manual',?,?,?,?,?,?)""", (url, title.strip() or "Information importée", now, now, content_hash, text))
        return True

    def import_url(self, url: str) -> bool:
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("Indiquez une adresse HTTP ou HTTPS complète.")
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            with client.stream("GET", url, headers={"User-Agent": "BSC-Radio-Studio/0.1"}) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 5_000_000:
                        raise ValueError("La page dépasse la limite de 5 Mo.")
        doc = trafilatura.bare_extraction(bytes(content), url=url)
        if not doc or not doc.text:
            raise ValueError("Le texte de cette page n’a pas pu être extrait. Utilisez l’import de texte.")
        return self.import_text(doc.title or url, doc.text, url)

    def create_episode(self, title="Nouvel épisode", script=None, fmt="journal") -> int:
        lines = script or [{"character": "presenter", "text": "", "fact_ids": [], "delivery": []}]
        pipeline = EditorialPipeline(self.settings, self.db, MockEditorialProvider())
        return pipeline._persist_episode(fmt, lines, {}, title)

    def generate_script(self, title: str, fmt: str, item_ids: list[int], progress, demo=False) -> int:
        if not item_ids:
            raise ValueError("Sélectionnez des informations dans l’onglet Imports.")
        pipeline = self.pipeline(demo)
        placeholders = ",".join("?" for _ in item_ids)
        # Extraction is restricted to the user's selection, including archived facts.
        for index, item_id in enumerate(item_ids):
            item = self.db.one("SELECT i.*,s.name source_name FROM item i JOIN source s ON s.id=i.source_id WHERE i.id=?", (item_id,))
            if not item:
                raise ValueError("Une information sélectionnée a disparu.")
            progress(f"Extraction des faits · {index + 1}/{len(item_ids)}")
            if not self.db.one("SELECT id FROM fact WHERE item_id=?", (item_id,)):
                facts = pipeline.provider.extract_facts(item["title"], item["raw_text"], {"name": item["source_name"], "url": item["url"], "date": item["published_at"]})
                with self.db.transaction() as connection:
                    for fact in facts:
                        connection.execute("""INSERT INTO fact(item_id,statement,fact_type,reliability,source_url,source_name,source_date)
                          VALUES(?,?,?,?,?,?,?)""", (item_id, fact["statement"], fact.get("type", "context"), fact.get("reliability", 0.5), item["url"], item["source_name"], item["published_at"]))
                    connection.execute("UPDATE item SET status='facts' WHERE id=?", (item_id,))
        facts = [dict(r) for r in self.db.all(f"SELECT * FROM fact WHERE item_id IN ({placeholders}) AND reliability>0 ORDER BY id", tuple(item_ids))]
        if not facts:
            raise ValueError("Aucun fait exploitable dans les informations choisies.")
        context = pipeline._context()
        config = dict(self.settings.schedule["formats"][fmt])
        context["format"] = {**config, "id": fmt, "allowed_characters": config.get("voices", ["presenter"]), "target_words": int(config.get("min_minutes", 3) * 150)}
        progress("Écriture du dialogue" + (" · démonstration" if demo else " · OpenAI"))
        script = pipeline.provider.write(fmt, facts, context)
        if not script or any(not str(line.get("text", "")).strip() for line in script):
            raise ValueError("Le modèle n’a pas renvoyé un dialogue utilisable.")
        return pipeline._persist_episode(fmt, script, context, title)

    def script(self, episode_id: int):
        row = self.db.one("SELECT script_json FROM episode WHERE id=?", (episode_id,))
        if not row:
            raise ValueError("Épisode introuvable.")
        return json.loads(row["script_json"])

    def save_script(self, episode_id: int, title: str, lines: list[dict]) -> None:
        if not title.strip():
            raise ValueError("Donnez un titre à l’épisode.")
        old = self.script(episode_id)
        changed = json.dumps(old, sort_keys=True) != json.dumps(lines, sort_keys=True)
        if not changed:
            self.db.execute("UPDATE episode SET title=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (title, episode_id))
            return
        backup = self.root / "backups" / f"episode-{episode_id}-{uuid.uuid4().hex[:10]}.json"
        backup.write_text(json.dumps({"title": title, "script": old}, ensure_ascii=False, indent=2), encoding="utf-8")
        with self.db.transaction() as connection:
            connection.execute("""UPDATE episode SET title=?,script_json=?,status='draft',studio_revision=studio_revision+1,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""", (title, json.dumps(lines, ensure_ascii=False), episode_id))
            connection.execute("DELETE FROM sentence WHERE episode_id=?", (episode_id,))
            for pos, line in enumerate(lines):
                connection.execute("""INSERT INTO sentence(episode_id,position,character,text,delivery_json,fact_ids_json,feedback_ids_json)
                  VALUES(?,?,?,?,?,?,?)""", (episode_id, pos, line["character"], line["text"], json.dumps(line.get("delivery", [])), json.dumps(line.get("fact_ids", [])), json.dumps(line.get("feedback_ids", []))))

    def render(self, episode_id: int, progress) -> Path:
        lines = self.script(episode_id)
        prefs = Preferences(self.root)
        key = prefs.secret("openai_key")
        if not key:
            raise ValueError("Ajoutez votre clé API OpenAI dans les paramètres.")
        voices = prefs.get("voices", {})
        model = prefs.get("voice_model", "gpt-realtime-2.1-mini")
        if not lines or not any(line["text"].strip() for line in lines):
            raise ValueError("Le script est vide.")
        missing = {NAMES.get(line["character"], line["character"]) for line in lines if line["text"].strip() and not voices.get(line["character"])}
        if missing:
            raise ValueError("Choisissez une voix API dans Paramètres pour : " + ", ".join(sorted(missing)))
        fingerprint = hashlib.sha256(json.dumps({"lines": lines, "voices": voices, "model": model}, sort_keys=True).encode()).hexdigest()
        destination = self.root / "audio" / f"episode-{episode_id}-{fingerprint[:12]}.wav"
        parts = []
        for index, line in enumerate(lines):
            if not line["text"].strip():
                continue
            if len(line["text"]) > 2500:
                raise ValueError("Une réplique dépasse 2 500 caractères. Découpez-la avant génération.")
            voice = voices[line["character"]]
            direction = "Ton radiophonique naturel. " + ", ".join(line.get("delivery", []))
            take_hash = hashlib.sha256(json.dumps([line["text"], voice, model, direction]).encode()).hexdigest()
            path = self.root / "takes" / (take_hash + ".wav")
            progress(f"Voix · réplique {index + 1}/{len(lines)}" + (" · cache" if path.exists() else " · génération"))
            if not path.exists():
                synthesize(key, model, line["text"], voice, path, direction)
            parts.append(path)
        temporary = destination.with_suffix(".partial.wav")
        with wave.open(str(temporary), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(24000)
            for part in parts:
                with wave.open(str(part), "rb") as source:
                    if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24000):
                        raise ValueError("Une prise audio est invalide.")
                    target.writeframes(source.readframes(source.getnframes()))
                    target.writeframes(b"\x00\x00" * 3600)
        temporary.replace(destination)
        with wave.open(str(destination), "rb") as wav:
            seconds = wav.getnframes() / wav.getframerate()
        self.db.execute("INSERT INTO studio_audio(episode_id,path,script_hash,duration) VALUES(?,?,?,?) ON CONFLICT(episode_id) DO UPDATE SET path=excluded.path,script_hash=excluded.script_hash,duration=excluded.duration,created_at=CURRENT_TIMESTAMP", (episode_id, str(destination), fingerprint, seconds))
        self.db.execute("UPDATE episode SET status='audio',studio_audio_revision=studio_revision WHERE id=?", (episode_id,))
        return destination

    def current_audio(self, episode_id: int) -> Path:
        episode = self.db.one("SELECT * FROM episode WHERE id=?", (episode_id,))
        if episode["studio_revision"] != episode["studio_audio_revision"]:
            raise ValueError("Le script a changé. Générez de nouveau l’audio ; les prises inchangées seront réutilisées.")
        row = self.db.one("SELECT path FROM studio_audio WHERE episode_id=?", (episode_id,))
        if not row or not Path(row["path"]).is_file():
            raise ValueError("Générez l’audio de cet épisode avant de l’écouter ou de l’exporter.")
        prefs = Preferences(self.root)
        expected = hashlib.sha256(json.dumps({"lines": self.script(episode_id), "voices": prefs.get("voices", {}),
            "model": prefs.get("voice_model", "gpt-realtime-2.1-mini")}, sort_keys=True).encode()).hexdigest()
        if self.db.one("SELECT script_hash FROM studio_audio WHERE episode_id=?", (episode_id,))["script_hash"] != expected:
            raise ValueError("Les voix ou le modèle ont changé. Générez de nouveau l’audio de cet épisode.")
        return Path(row["path"])

    def export_audio(self, episode_id: int, target: Path) -> None:
        source = self.current_audio(episode_id)
        if source.resolve() == target.resolve():
            raise ValueError("Choisissez un emplacement d’export différent du fichier de travail.")
        if target.suffix.lower() == ".wav":
            shutil.copy2(source, target)
        else:
            temporary = target.with_name(target.stem + ".partial.mp3")
            try:
                result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-y", "-loglevel", "error", "-i", str(source), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-b:a", "192k", str(temporary)], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode:
                    raise RuntimeError("L’encodage MP3 a échoué ; l’audio original est conservé.")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)

    def backup(self, target: Path) -> None:
        with self.db.connect() as source, sqlite3.connect(target) as destination:
            source.backup(destination)
