"""List and package only source files, never credentials, user data or build outputs."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("bsc_studio", "engine", "assets", "scripts", "tests", "packaging", ".github")
ROOT_FILES = ("README.md", "RELEASE_NOTES.md", "LICENSE", "UPSTREAM.md", "THIRD_PARTY_NOTICES.md", ".gitignore", "pyproject.toml",
              "requirements.txt", "requirements-build.txt", "requirements-lock.txt", "run_studio.py")
EXTENSIONS = {".py", ".md", ".txt", ".yaml", ".yml", ".iss"}


def source_files():
    files = [ROOT / name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in EXTENSIONS and "__pycache__" not in path.parts)
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--zip", type=Path)
    args = parser.parse_args()
    files = source_files()
    if args.json:
        print(json.dumps([{"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                           "content": path.read_text(encoding="utf-8-sig")} for path in files], ensure_ascii=True))
    if args.zip:
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, "BSC-radio/" + path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
