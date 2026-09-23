from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

from app.ui.main_window import MainWindow


def main():
    QCoreApplication.setOrganizationName("SubAja")
    QCoreApplication.setApplicationName("SubAja")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
