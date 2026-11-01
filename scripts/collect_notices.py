"""Preserve dependency license files and metadata beside dynamically loaded libraries."""
import importlib.metadata
import shutil
from pathlib import Path


def collect(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown").replace("/", "_")
        folder = destination / name
        for relative in distribution.files or []:
            parts = str(relative).lower()
            if ".dist-info/" not in parts.replace("\\", "/"):
                continue
            if not any(term in parts for term in ("license", "copying", "notice", "metadata")):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                target = folder / Path(str(relative)).name
                folder.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target = folder / str(relative).replace("/", "_").replace("\\", "_")
                shutil.copy2(source, target)
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "assets" / "licenses", destination / "Qt-open-source", dirs_exist_ok=True)


if __name__ == "__main__":
    collect(Path(__file__).resolve().parents[1] / "dist" / "BSC-Radio-Studio" / "licenses")
