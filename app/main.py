from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QTimer

from app.ui.main_window import MainWindow


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
        # startup, membuat MainWindow, lalu keluar normal.
        QTimer.singleShot(800, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
