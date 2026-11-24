"""Start der Anwendung."""

from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .core import APP_ID, APP_NAME, resource_path


def main():
    # Eigene AppUserModelID -> Windows zeigt unser Icon in der Taskleiste statt des Python-Icons.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    from .ui.main_window import MainWindow  # nach QApplication (Icons brauchen sie)
    from .ui.style import STYLESHEET

    app.setStyleSheet(STYLESHEET)
    icon_file = resource_path("icon.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    win = MainWindow()
    win.show()
    QTimer.singleShot(150, win.check_setup)
    sys.exit(app.exec())
