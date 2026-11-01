from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from packaging.version import InvalidVersion, Version

from . import REPOSITORY, __version__

ASSET_NAME = "BSC-Radio-Studio-Setup-x64.exe"
API_BASE = f"https://api.github.com/repos/{REPOSITORY}"
MAX_DOWNLOAD = 1024 * 1024 * 1024


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    url: str
    asset_id: int
    size: int
    digest: str
    checksum_id: int | None


def newer(candidate: str, installed: str = __version__) -> bool:
    try:
        version = Version(candidate.removeprefix("v"))
        return not version.is_prerelease and not version.is_devrelease and version > Version(installed)
    except InvalidVersion:
        return False


def release_from_json(payload: dict) -> Release | None:
    tag = payload.get("tag_name", "")
    if payload.get("draft") or payload.get("prerelease") or not newer(tag):
        return None
    assets = payload.get("assets", [])
    installer = next((a for a in assets if a.get("name") == ASSET_NAME and a.get("state", "uploaded") == "uploaded"), None)
    if not installer:
        raise RuntimeError("La version publiée ne contient pas encore l’installeur Windows x64.")
    checksum = next((a for a in assets if a.get("name") == "SHA256SUMS.txt"), None)
    digest = installer.get("digest") or ""
    if digest and not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise RuntimeError("L’empreinte GitHub est invalide.")
    if not digest and not checksum:
        raise RuntimeError("Cette version ne fournit pas d’empreinte SHA-256 vérifiable.")
    size = int(installer.get("size", 0))
    if size <= 0 or size > MAX_DOWNLOAD:
        raise RuntimeError("La taille de l’installeur publié est invalide.")
    return Release(tag.removeprefix("v"), str(payload.get("body") or ""),
                   f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
                   int(installer["id"]), size, digest.split(":")[-1].lower() if digest else "",
                   int(checksum["id"]) if checksum else None)


class GitHubUpdater:
    def __init__(self, token: str = "", client: httpx.Client | None = None):
        self.token = token.strip()
        self.client = client or httpx.Client(timeout=45, follow_redirects=False)

    def _headers(self, binary: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/octet-stream" if binary else "application/vnd.github+json",
                   "User-Agent": f"BSC-Radio-Studio/{__version__}", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check(self) -> Release | None:
        response = self.client.get(f"{API_BASE}/releases/latest", headers=self._headers())
        if response.status_code == 404:
            # A private repository without access and an absent release both return 404.
            repository = self.client.get(API_BASE, headers=self._headers())
            if repository.status_code in (401, 403, 404):
                raise RuntimeError("Accès au dépôt privé impossible. Ajoutez un jeton GitHub autorisé pour BSC-radio (Contents : lecture).")
            self._validate(repository)
            return None
        self._validate(response)
        return release_from_json(response.json())

    @staticmethod
    def _validate(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise RuntimeError("GitHub refuse l’accès : vérifiez le jeton et les limites de requêtes.")
        if response.is_error:
            raise RuntimeError(f"GitHub est indisponible (HTTP {response.status_code}).")

    def _download_chunks(self, asset_id: int):
        url = f"{API_BASE}/releases/assets/{int(asset_id)}"
        for hop in range(6):
            parsed = urlparse(url)
            if parsed.scheme != "https":
                raise RuntimeError("Téléchargement refusé : HTTPS est requis.")
            # Credentials are sent only to the GitHub API, never to a redirected CDN.
            headers = self._headers(True) if parsed.hostname == "api.github.com" else {"User-Agent": self._headers()["User-Agent"]}
            with self.client.stream("GET", url, headers=headers) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers["location"]))
                    host = urlparse(url).hostname or ""
                    if host not in {"api.github.com", "github.com"} and not host.endswith(".githubusercontent.com"):
                        raise RuntimeError("Redirection de téléchargement GitHub inattendue.")
                    continue
                self._validate(response)
                yield from response.iter_bytes(1024 * 256)
                return
        raise RuntimeError("Trop de redirections pendant le téléchargement.")

    def download(self, release: Release, destination: Path, progress=lambda value: None) -> Path:
        digest = release.digest
        if not digest:
            manifest = b"".join(self._limited_chunks(release.checksum_id, 64 * 1024)).decode("utf-8")
            matches = [m.group(1).lower() for line in manifest.splitlines()
                       if (m := re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?" + re.escape(ASSET_NAME), line.strip()))]
            if len(matches) != 1:
                raise RuntimeError("Le manifeste SHA-256 ne correspond pas à l’installeur.")
            digest = matches[0]
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / ASSET_NAME
        temporary = destination / (ASSET_NAME + ".part")
        hasher = hashlib.sha256()
        total = 0
        try:
            with temporary.open("wb") as stream:
                for chunk in self._limited_chunks(release.asset_id, release.size):
                    total += len(chunk)
                    stream.write(chunk)
                    hasher.update(chunk)
                    progress(int(total * 100 / release.size))
            if total != release.size or hasher.hexdigest() != digest:
                raise RuntimeError("L’intégrité du téléchargement n’est pas valide. Installation annulée.")
            with temporary.open("rb") as stream:
                if stream.read(2) != b"MZ":
                    raise RuntimeError("Le fichier téléchargé n’est pas un exécutable Windows.")
            os.replace(temporary, target)
            return target
        finally:
            temporary.unlink(missing_ok=True)

    def _limited_chunks(self, asset_id: int, maximum: int):
        total = 0
        for chunk in self._download_chunks(asset_id):
            total += len(chunk)
            if total > maximum:
                raise RuntimeError("Le téléchargement dépasse la taille annoncée.")
            yield chunk


def start_installer(path: Path) -> None:
    if not path.is_file() or path.name != ASSET_NAME:
        raise RuntimeError("Installeur introuvable.")
    # The normal installer UI asks the user to confirm installation and handles app shutdown.
    subprocess.Popen([str(path), "/SP-"], close_fds=True)
