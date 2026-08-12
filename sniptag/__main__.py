"""進入點：python -m sniptag"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .app import SnipTagApp
from .icon import app_icon


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("SnipTag")
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(app_icon())

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "SnipTag", "這台電腦沒有系統匣，無法執行。")
        return 1

    SnipTagApp(qapp)
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
