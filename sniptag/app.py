"""SnipTag 主控制器：系統匣、熱鍵、截圖流程、存檔、歷史。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QAction, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from . import screens
from .config import Config
from .dialogs import SettingsDialog, TopicDialog
from .history import History, HistoryDialog
from .hotkeys import HotkeyManager
from .icon import app_icon
from .naming import Namer
from .overlay import Overlay
from .pinwindow import PinWindow


class SnipTagApp(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.cfg = Config()
        self.namer = Namer(self.cfg)
        self.icon = app_icon()
        self.overlay: Overlay | None = None
        self.pins: list[PinWindow] = []
        self.history = History()
        self.history_dialog: HistoryDialog | None = None

        self.tray = QSystemTrayIcon(self.icon, self)
        self.menu = self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._refresh_tooltip()
        self.tray.show()

        self.hotkeys = HotkeyManager(qapp)
        self._register_hotkeys()
        QTimer.singleShot(600, self._greet)

    # --- 系統匣 ---------------------------------------------------
    def _build_menu(self) -> QMenu:
        menu = QMenu()
        self.topic_action = QAction("", menu)
        self.topic_action.setEnabled(False)
        menu.addAction(self.topic_action)
        menu.addSeparator()

        entries = [
            (f"框選截圖\t{self.cfg['hotkey_capture']}", lambda: self.start_capture(False)),
            (f"快速截圖存檔\t{self.cfg['hotkey_quickshot']}", lambda: self.start_capture(True)),
            (f"貼上為釘圖\t{self.cfg['hotkey_pin']}", self.paste_pin),
            None,
            (f"設定主題…\t{self.cfg['hotkey_topic']}", self.change_topic),
            ("截圖歷史…", self.show_history),
            ("開啟存檔資料夾", self.open_folder),
            None,
            ("解除所有滑鼠穿透", self.clear_click_through),
            ("關閉所有釘圖", self.close_all_pins),
            None,
            ("設定…", self.open_settings),
            ("結束", self.quit),
        ]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            text, slot = entry
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.aboutToShow.connect(self._refresh_tooltip)
        return menu

    def _refresh_tooltip(self) -> None:
        try:
            preview = self.namer.preview()
        except Exception:
            preview = "?"
        self.topic_action.setText(f"主題：{self.cfg['topic']}　下一張：{preview}")
        self.tray.setToolTip(f"SnipTag — {self.cfg['topic']} / 下一張 {preview}")

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.start_capture(False)

    def _greet(self) -> None:
        if self.hotkeys.failed:
            self.notify(
                "部分熱鍵註冊失敗",
                "被其他程式佔用：" + "、".join(self.hotkeys.failed)
                + "\n可在「設定…」改成別的組合。",
                QSystemTrayIcon.Warning,
            )
        else:
            self.notify(
                "SnipTag 已啟動",
                f"{self.cfg['hotkey_capture']} 截圖　"
                f"{self.cfg['hotkey_topic']} 換主題\n目前主題：{self.cfg['topic']}",
            )

    def notify(self, title: str, message: str, icon=QSystemTrayIcon.Information) -> None:
        if self.tray.supportsMessages():
            self.tray.showMessage(title, message, icon, 2600)

    # --- 熱鍵 -----------------------------------------------------
    def _register_hotkeys(self) -> None:
        self.hotkeys.register(self.cfg["hotkey_capture"], lambda: self.start_capture(False))
        self.hotkeys.register(self.cfg["hotkey_quickshot"], lambda: self.start_capture(True))
        self.hotkeys.register(self.cfg["hotkey_pin"], self.paste_pin)
        self.hotkeys.register(self.cfg["hotkey_topic"], self.change_topic)

    def reload_hotkeys(self, announce: bool = False) -> None:
        """改完設定立即套用，不需要重新啟動。"""
        self.hotkeys.unregister_all()
        self._register_hotkeys()
        if self.hotkeys.failed:
            self.notify(
                "部分熱鍵註冊失敗",
                "被其他程式佔用：" + "、".join(self.hotkeys.failed),
                QSystemTrayIcon.Warning,
            )
        elif announce:
            self.notify("設定已套用", "熱鍵已立即生效。")

    # --- 截圖流程 -------------------------------------------------
    def start_capture(self, quick: bool = False) -> None:
        if self.overlay is not None:
            return
        shot = screens.grab_desktop()
        if shot is None:
            self.notify("截圖失敗", "無法取得螢幕畫面。", QSystemTrayIcon.Critical)
            return
        overlay = Overlay(shot, self.namer.preview, quick)
        overlay.finished.connect(self._on_capture_finished)
        overlay.cancelled.connect(self._on_capture_cancelled)
        self.overlay = overlay
        overlay.start()

    def _on_capture_cancelled(self) -> None:
        self.overlay = None

    def _on_capture_finished(self, pixmap: QPixmap, action: str, geometry: QRect) -> None:
        self.overlay = None
        if action == "save":
            self.save_pixmap(pixmap)
            return
        if action == "saveas":
            self.save_pixmap_as(pixmap)
            return
        self.history.add(pixmap)
        if action == "copy":
            self.copy_to_clipboard(pixmap)
            self.notify("已複製", "截圖已放進剪貼簿。")
        elif action == "pin":
            self.pin(pixmap, geometry.topLeft())
        self._refresh_history_dialog()

    # --- 存檔 -----------------------------------------------------
    def _write(self, pixmap: QPixmap, path: Path) -> bool:
        fmt = "JPG" if path.suffix.lower() in (".jpg", ".jpeg") else "PNG"
        quality = int(self.cfg["jpeg_quality"]) if fmt == "JPG" else -1
        image = pixmap
        if fmt == "JPG" and pixmap.hasAlphaChannel():
            image = QPixmap(pixmap.size())
            image.setDevicePixelRatio(pixmap.devicePixelRatio())
            image.fill(Qt.white)
            painter = QPainter(image)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
        return image.save(str(path), fmt, quality)

    def save_pixmap(self, pixmap: QPixmap, record: bool = True) -> Path | None:
        try:
            path = self.namer.next_path()
        except OSError as exc:
            self.notify("存檔失敗", f"無法建立資料夾：{exc}", QSystemTrayIcon.Critical)
            return None
        if not self._write(pixmap, path):
            self.notify("存檔失敗", f"寫入失敗：{path}", QSystemTrayIcon.Critical)
            return None
        if record:
            self.history.add(pixmap, path.name)
            self._refresh_history_dialog()
        if self.cfg["copy_on_save"]:
            self.copy_to_clipboard(pixmap)
        if self.cfg["notify_on_save"]:
            self.notify("已存檔", path.name)
        self._refresh_tooltip()
        return path

    def save_pixmap_as(self, pixmap: QPixmap) -> Path | None:
        suggested = self.namer.target_dir() / self.namer.preview()
        chosen, _ = QFileDialog.getSaveFileName(
            None, "另存截圖", str(suggested), "PNG (*.png);;JPEG (*.jpg)"
        )
        if not chosen:
            return None
        path = Path(chosen)
        if not self._write(pixmap, path):
            self.notify("存檔失敗", f"寫入失敗：{path}", QSystemTrayIcon.Critical)
            return None
        self.history.add(pixmap, path.name)
        self._refresh_history_dialog()
        self._refresh_tooltip()
        return path

    def copy_to_clipboard(self, pixmap: QPixmap) -> None:
        QGuiApplication.clipboard().setPixmap(pixmap)

    # --- 釘圖 -----------------------------------------------------
    def pin(self, pixmap: QPixmap, position: QPoint) -> None:
        window = PinWindow(pixmap, position, self)
        self.pins.append(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def pin_centered(self, pixmap: QPixmap) -> None:
        screen = QGuiApplication.primaryScreen()
        center = screen.availableGeometry().center() if screen else QPoint(200, 200)
        dpr = pixmap.devicePixelRatio() or 1.0
        offset = QPoint(round(pixmap.width() / dpr / 2), round(pixmap.height() / dpr / 2))
        self.pin(pixmap, center - offset)

    def paste_pin(self) -> None:
        pixmap = QGuiApplication.clipboard().pixmap()
        if pixmap.isNull():
            self.notify("沒有可釘的圖", "剪貼簿裡沒有影像。", QSystemTrayIcon.Warning)
            return
        self.pin_centered(pixmap)

    def forget_pin(self, window: PinWindow) -> None:
        if window in self.pins:
            self.pins.remove(window)

    def close_all_pins(self) -> None:
        for window in list(self.pins):
            window.close()

    def clear_click_through(self) -> None:
        """滑鼠穿透的釘圖收不到鍵盤，只能從這裡救回來。"""
        for window in self.pins:
            if window.click_through:
                window.set_click_through(False)

    # --- 歷史 -----------------------------------------------------
    def show_history(self) -> None:
        if self.history_dialog is None:
            self.history_dialog = HistoryDialog(self.history, self)
            self.history_dialog.setWindowIcon(self.icon)
            self.history_dialog.finished.connect(self._on_history_closed)
        self.history_dialog.reload()
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def _on_history_closed(self, _result) -> None:
        self.history_dialog = None

    def _refresh_history_dialog(self) -> None:
        if self.history_dialog is not None and self.history_dialog.isVisible():
            self.history_dialog.reload()

    # --- 設定 -----------------------------------------------------
    def change_topic(self) -> None:
        dialog = TopicDialog(self.cfg)
        dialog.setWindowIcon(self.icon)
        if dialog.exec() == TopicDialog.Accepted:
            self.cfg.set_topic(dialog.topic())
            self._refresh_tooltip()
            self.notify("主題已切換", f"{self.cfg['topic']}　下一張：{self.namer.preview()}")

    def open_settings(self) -> None:
        # 全域熱鍵會攔截 F1 這類按鍵，錄製欄位就收不到了 —— 開設定期間先卸下
        self.hotkeys.unregister_all()
        accepted = False
        try:
            dialog = SettingsDialog(self.cfg)
            dialog.setWindowIcon(self.icon)
            accepted = dialog.exec() == SettingsDialog.Accepted
            if accepted:
                dialog.apply_to_config()
                self.menu = self._build_menu()
                self.tray.setContextMenu(self.menu)
                self._refresh_tooltip()
        finally:
            self.reload_hotkeys(announce=accepted)

    def open_folder(self) -> None:
        directory = self.namer.target_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(None, "SnipTag", f"無法開啟資料夾：{exc}")
            return
        if sys.platform == "win32":
            os.startfile(directory)  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(directory)])

    def quit(self) -> None:
        self.hotkeys.unregister_all()
        self.close_all_pins()
        if self.overlay is not None:
            self.overlay.close()
        self.tray.hide()
        self.qapp.quit()
