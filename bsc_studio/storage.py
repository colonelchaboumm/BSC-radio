from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import sys
from ctypes import wintypes
from pathlib import Path


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets"


def data_dir() -> Path:
    override = os.environ.get("BSC_STUDIO_DATA_DIR")
    root = Path(override) if override else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BSC Radio Studio" / "Data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def initialize(root: Path) -> None:
    for name in ("config", "prompts"):
        source = resource_dir() / name
        destination = root / name
        destination.mkdir(parents=True, exist_ok=True)
        for file in source.rglob("*"):
            if file.is_file():
                target = destination / file.relative_to(source)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, target)
    for name in ("audio", "takes", "backups", "updates"):
        (root / name).mkdir(exist_ok=True)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("Le stockage des identifiants nécessite Windows.")
    buffer = ctypes.create_string_buffer(value)
    source = DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = DataBlob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    function = library.CryptProtectData if protect else library.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel = ctypes.WinDLL("kernel32")
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(result.pbData)


class Preferences:
    def __init__(self, root: Path):
        self.path = root / "preferences.json"
        self.values = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def secret(self, key: str) -> str:
        value = self.values.get(key, "")
        if not value:
            return ""
        try:
            return _crypt(base64.b64decode(value), False).decode("utf-8")
        except (OSError, ValueError):
            raise RuntimeError("Un identifiant ne peut plus être déchiffré. Renseignez-le de nouveau dans les paramètres.") from None

    def save(self, values: dict, secrets: dict[str, str] | None = None) -> None:
        self.values.update(values)
        for key, value in (secrets or {}).items():
            self.values[key] = base64.b64encode(_crypt(value.encode(), True)).decode() if value else ""
        atomic_json(self.path, self.values)
