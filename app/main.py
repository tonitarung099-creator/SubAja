from __future__ import annotations

from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QTimer

from app.ui.main_window import MainWindow


def _runtime_smoke_check():
    """Verify critical packaged runtime pieces without network access."""
    import soundfile  # noqa: F401
    import sherpa_onnx  # noqa: F401
    from google import genai  # noqa: F401
    from imageio_ffmpeg import get_ffmpeg_exe

    from app.core.resources import model_paths

    ffmpeg = Path(get_ffmpeg_exe())
    if not ffmpeg.is_file():
        raise RuntimeError(f"FFmpeg runtime tidak ditemukan: {ffmpeg}")

    segmentation, embedding = model_paths()
    missing = [str(p) for p in (segmentation, embedding) if not p.is_file()]
    if missing:
        raise RuntimeError("Model speaker runtime tidak ditemukan: " + ", ".join(missing))


def main():
    QCoreApplication.setOrganizationName("SubAja")
    QCoreApplication.setApplicationName("SubAja")

    smoke_test = "--smoke-test" in sys.argv
    qt_argv = [arg for arg in sys.argv if arg != "--smoke-test"]
    app = QApplication(qt_argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()

    if smoke_test:
        # Dipakai CI untuk membuktikan EXE hasil PyInstaller benar-benar bisa
        # startup DAN membawa dependency runtime speaker/Gemini yang diperlukan.
        _runtime_smoke_check()
        QTimer.singleShot(800, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
