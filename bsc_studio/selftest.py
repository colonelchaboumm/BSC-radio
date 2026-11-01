"""Offline verification of the packaged app; never calls a real AI provider."""
import json
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path


def run():
    from PySide6.QtWidgets import QApplication
    from .service import StudioService
    from .ui import MainWindow, STYLESHEET
    from .appearance import configure_fonts
    report_path = Path(sys.argv[sys.argv.index("--report") + 1]) if "--report" in sys.argv else None
    checks = []
    try:
        with tempfile.TemporaryDirectory(prefix="bsc-studio-selftest-") as directory:
            root = Path(directory)
            service = StudioService(root)
            service.import_text("Test local", "Les levures transforment les sucres pendant la fermentation. Ce contenu est une démonstration du logiciel.")
            episode = service.generate_script("Démonstration du studio", "journal", [service.items()[0]["id"]], lambda _: None, demo=True)
            checks.append("SQLite, import, extraction et script de démonstration")
            application = QApplication.instance() or QApplication([])
            configure_fonts(application)
            application.setStyleSheet(STYLESHEET)
            window = MainWindow(service)
            window.open_episode(episode)
            window.save_episode()
            checks.append("Construction des six écrans Qt et sauvegarde du dialogue")
            if "--screenshot" in sys.argv:
                window.show()
                application.processEvents()
                window.grab().save(sys.argv[sys.argv.index("--screenshot") + 1])
            if "--screenshot-dir" in sys.argv:
                screenshots = Path(sys.argv[sys.argv.index("--screenshot-dir") + 1])
                screenshots.mkdir(parents=True, exist_ok=True)
                window.show()
                for page_index in range(window.pages.count()):
                    window.navigation.setCurrentRow(page_index)
                    application.processEvents()
                    window.grab().save(str(screenshots / f"page-{page_index}.png"))
            tone = root / "audio" / "test-tone.wav"
            with wave.open(str(tone), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(24000)
                audio.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / 24000))) for i in range(24000)))
            import hashlib
            fingerprint = hashlib.sha256(json.dumps({"lines": service.script(episode), "voices": {}, "model": "gpt-realtime-2.1-mini"}, sort_keys=True).encode()).hexdigest()
            service.db.execute("INSERT INTO studio_audio(episode_id,path,script_hash,duration) VALUES(?,?,?,1)", (episode, str(tone), fingerprint))
            service.db.execute("UPDATE episode SET studio_audio_revision=studio_revision WHERE id=?", (episode,))
            service.export_audio(episode, root / "test-export.mp3")
            assert (root / "test-export.mp3").stat().st_size > 1000
            checks.append("Outil FFmpeg embarqué et export MP3 d’un signal de test")
            window.close()
        result = {"ok": True, "checks": checks, "real_ai_calls": 0}
        code = 0
    except Exception as error:
        result = {"ok": False, "checks": checks, "error": str(error), "real_ai_calls": 0}
        code = 1
    if report_path:
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=True))
    return code
