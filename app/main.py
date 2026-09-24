from __future__ import annotations

from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QIcon

from app.core.resources import resource_path
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

    logo = resource_path("assets/subaja-logo.png")
    if not logo.is_file():
        raise RuntimeError(f"Logo runtime tidak ditemukan: {logo}")


def main():
    QCoreApplication.setOrganizationName("SubAja")
    QCoreApplication.setApplicationName("SubAja")

    smoke_test = "--smoke-test" in sys.argv
    qt_argv = [arg for arg in sys.argv if arg != "--smoke-test"]
    app = QApplication(qt_argv)
    app.setStyle("Fusion")

    logo = resource_path("assets/subaja-logo.png")
    if logo.is_file():
        app.setWindowIcon(QIcon(str(logo)))

    window = MainWindow()
    window.show()

    if smoke_test:
        # Dipakai CI untuk membuktikan build portable benar-benar bisa startup
        # dan membawa dependency runtime speaker/Gemini/FFmpeg/logo.
        _runtime_smoke_check()
        QTimer.singleShot(800, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
