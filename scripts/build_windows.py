"""Build reproducible versioned Windows artifacts; requires Inno Setup ISCC on PATH or --iscc."""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "engine"))
from bsc_studio import __version__  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", default=shutil.which("ISCC") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("Compilez les versions Windows sur Windows.")
    import PySide6
    from collect_notices import collect
    from PySide6.QtWidgets import QApplication
    from bsc_studio.ui import app_icon
    _application = QApplication.instance() or QApplication([])
    app_icon().pixmap(128, 128).save(str(ROOT / "assets" / "studio.ico"))
    version_file = ROOT / "build" / "version_info.txt"
    version_file.parent.mkdir(exist_ok=True)
    version_tuple = tuple(map(int, __version__.split("."))) + (0,)
    version_file.write_text(f"""VSVersionInfo(ffi=FixedFileInfo(filevers={version_tuple},prodvers={version_tuple},mask=0x3f,flags=0,OS=0x40004,fileType=0x1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040c04b0',[StringStruct('CompanyName','Brewers Social Club'),StringStruct('FileDescription','BSC Radio Studio'),StringStruct('FileVersion','{__version__}'),StringStruct('ProductName','BSC Radio Studio'),StringStruct('ProductVersion','{__version__}')])]),VarFileInfo([VarStruct('Translation',[1036,1200])])])""", encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
               "--name", "BSC-Radio-Studio", "--icon", "assets/studio.ico", "--version-file", str(version_file),
               "--paths", "engine", "--add-data", "assets;assets", "--add-data", "LICENSE;.",
               "--add-data", "UPSTREAM.md;.", "--add-data", "THIRD_PARTY_NOTICES.md;.",
               "--collect-data", "trafilatura", "--collect-data", "certifi", "--collect-data", "dateparser",
               "--collect-data", "tzdata", "--collect-all", "imageio_ffmpeg",
               "--hidden-import", "lxml.html.clean", "--exclude-module", "PySide6.QtWebEngineCore",
               "--exclude-module", "PySide6.QtWebEngineWidgets", "run_studio.py"]
    # Do not allow unrelated tools (Poppler/Conda/etc.) from the user's PATH to
    # supply DLLs that shadow the Windows ICU or the packaged Qt libraries.
    environment = os.environ.copy()
    windows = Path(os.environ.get("WINDIR", "C:/Windows"))
    environment["PATH"] = os.pathsep.join(str(path) for path in (
        Path(sys.executable).parent, Path(sys.base_prefix), Path(sys.base_prefix) / "DLLs",
        windows / "System32", windows,
    ))
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    # Fail the build rather than distribute DLLs accidentally collected from
    # another installed tool or environment on the build machine.
    allowed_roots = (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(), windows.resolve(), ROOT.resolve())
    analysis = ast.literal_eval((ROOT / "build" / "BSC-Radio-Studio" / "Analysis-00.toc").read_text(encoding="utf-8"))
    def audit(value):
        if isinstance(value, (list, tuple)):
            if len(value) == 3 and value[2] == "BINARY" and isinstance(value[1], str):
                source = Path(value[1]).resolve()
                if not any(source.is_relative_to(allowed) for allowed in allowed_roots):
                    raise RuntimeError("Bibliothèque provenant d’un outil extérieur : " + source.name)
            for item in value:
                audit(item)
    audit(analysis)
    # Ship dynamically loaded Qt binaries and their applicable license texts unmodified.
    licenses = Path(PySide6.__file__).parent / "licenses"
    if licenses.is_dir():
        shutil.copytree(licenses, ROOT / "dist" / "BSC-Radio-Studio" / "licenses" / "Qt", dirs_exist_ok=True)
    collect(ROOT / "dist" / "BSC-Radio-Studio" / "licenses")
    for name in ("LICENSE", "UPSTREAM.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, ROOT / "dist" / "BSC-Radio-Studio" / name)
    compiler = Path(args.iscc)
    if not compiler.is_file():
        raise SystemExit("Compilateur Inno Setup introuvable. Utilisez --iscc chemin\\ISCC.exe.")
    subprocess.run([str(compiler), "/DAppVersion=" + __version__, str(ROOT / "packaging" / "windows.iss")], check=True)
    artifact = ROOT / "release" / "BSC-Radio-Studio-Setup-x64.exe"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (ROOT / "release" / "SHA256SUMS.txt").write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    shutil.make_archive(str(ROOT / "release" / "BSC-Radio-Studio-Portable-x64"), "zip", ROOT / "dist" / "BSC-Radio-Studio")
    print(f"Installeur {__version__} : {artifact}")


if __name__ == "__main__":
    main()
