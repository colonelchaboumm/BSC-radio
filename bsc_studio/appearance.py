import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from .storage import resource_dir


def configure_fonts(application):
    brand_font = resource_dir() / "fonts" / "Roboto.ttf"
    if brand_font.is_file() and QFontDatabase.addApplicationFont(str(brand_font)) >= 0:
        application.setFont(QFont("Roboto", 10))
        return
    # The offscreen Windows Qt plugin does not discover system fonts on all hosts.
    # Load the existing Windows font in place; no Microsoft font is redistributed.
    windows = os.environ.get("WINDIR", "C:/Windows")
    font = Path(windows) / "Fonts" / "segoeui.ttf"
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    application.setFont(QFont("Segoe UI", 10))
