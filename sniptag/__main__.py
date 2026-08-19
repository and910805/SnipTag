"""進入點：python -m sniptag"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .app import SnipTagApp
from .config import config_dir
from .icon import app_icon


def _acquire_single_instance() -> QLockFile | None:
    """搶單一實例鎖。搶不到代表已經有一個 SnipTag 在跑了。

    QLockFile 會把 PID 寫進鎖檔：上一個程序如果是當掉結束的，
    tryLock 會發現該 PID 已不存在，自動清掉殘鎖，不會卡死。
    """
    directory = config_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        directory = Path(QDir.tempPath())  # 建不了設定資料夾就把鎖放暫存區
    lock = QLockFile(str(directory / "sniptag.lock"))
    lock.setStaleLockTime(0)  # 常駐程式：鎖不因時間過期，只看程序死活
    if lock.tryLock(100):
        return lock
    return None


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("SnipTag")
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(app_icon())

    lock = _acquire_single_instance()
    if lock is None:
        QMessageBox.information(
            None, "SnipTag",
            "SnipTag 已經在執行中了。\n請直接用右下角系統匣的圖示或原本的熱鍵。",
        )
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "SnipTag", "這台電腦沒有系統匣，無法執行。")
        return 1

    SnipTagApp(qapp)
    try:
        return qapp.exec()
    finally:
        lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
