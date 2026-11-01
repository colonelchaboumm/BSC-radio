from __future__ import annotations

import sys
from pathlib import Path

root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(root / "engine"))


def main():
    if "--self-test" in sys.argv:
        from bsc_studio.selftest import run
        return run()
    from PySide6.QtWidgets import QApplication, QMessageBox
    from bsc_studio.service import StudioService
    from bsc_studio.storage import data_dir
    from bsc_studio.ui import MainWindow, STYLESHEET
    from bsc_studio.appearance import configure_fonts
    application = QApplication(sys.argv)
    application.setApplicationName("BSC Radio Studio")
    application.setOrganizationName("Brewers Social Club")
    configure_fonts(application)
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)
    try:
        service = StudioService(data_dir())
        window = MainWindow(service)
        window.show()
        return application.exec()
    except Exception as error:
        QMessageBox.critical(None, "BSC Radio Studio", "Le studio n’a pas pu démarrer.\n" + str(error)[:400])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
