"""主題快速輸入框與完整設定視窗。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from . import autostart, hotkeys
from .naming import Namer

MODIFIER_KEYS = (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
                 Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock)
CLEAR_KEYS = (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Escape)


class HotkeyEdit(QLineEdit):
    """點一下就開始錄製：直接按下想要的組合鍵，不用自己打字。"""

    def __init__(self, value: str, parent: QWidget | None = None) -> None:
        super().__init__(value, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("點一下，然後按下想要的組合鍵（Esc 停用）")
        self.setToolTip("點一下之後直接按組合鍵；Esc / Backspace 可清空停用此熱鍵。")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in MODIFIER_KEYS:
            return                      # 等使用者按下真正的那個鍵
        if key in CLEAR_KEYS:
            self.clear()
            return
        try:
            combo = QKeySequence(event.keyCombination()).toString()
        except (AttributeError, TypeError):
            combo = QKeySequence(int(event.modifiers().value) | key).toString()
        if combo and hotkeys.parse(combo) is not None:
            self.setText(combo)
        # 不支援的組合就忽略，維持原本的值

TEMPLATE_HELP = (
    "可用欄位：{topic} 主題、{n} 流水號、{date} 20260812、"
    "{date2} 08-12、{time} 143005、{datetime}\n"
    "補零寫法：{n:02d} → 01、{n:03d} → 001"
)


class TopicDialog(QDialog):
    """Ctrl+F1 叫出來的小視窗：換主題，編號自動從 01 重新開始。"""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cfg = config
        self.setWindowTitle("設定主題")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("這場會議 / 這個題目的名稱："))

        self.combo = QComboBox(self)
        self.combo.setEditable(True)
        self.combo.addItems(self.cfg["recent_topics"])
        self.combo.setCurrentText(self.cfg["topic"])
        self.combo.lineEdit().selectAll()
        layout.addWidget(self.combo)

        self.preview = QLabel(self)
        self.preview.setStyleSheet("color:#2d7ff9;")
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.combo.currentTextChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        original = self.cfg["topic"]
        self.cfg["topic"] = self.combo.currentText().strip() or "Topic"
        try:
            name = Namer(self.cfg).preview()
        except Exception:
            name = "?"
        finally:
            self.cfg["topic"] = original
        self.preview.setText(f"下一張會存成：{name}")

    def topic(self) -> str:
        return self.combo.currentText().strip()


class SettingsDialog(QDialog):
    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cfg = config
        self.setWindowTitle("SnipTag 設定")
        self.setMinimumWidth(520)

        form = QFormLayout()

        self.topic_edit = QLineEdit(config["topic"], self)
        form.addRow("目前主題", self.topic_edit)

        folder_row = QHBoxLayout()
        self.dir_edit = QLineEdit(config["save_dir"], self)
        browse = QPushButton("瀏覽…", self)
        browse.clicked.connect(self._browse)
        folder_row.addWidget(self.dir_edit)
        folder_row.addWidget(browse)
        wrapper = QWidget(self)
        wrapper.setLayout(folder_row)
        form.addRow("存檔資料夾", wrapper)

        self.template_edit = QLineEdit(config["template"], self)
        form.addRow("檔名樣板", self.template_edit)
        help_label = QLabel(TEMPLATE_HELP, self)
        help_label.setStyleSheet("color:#888; font-size:11px;")
        help_label.setWordWrap(True)
        form.addRow("", help_label)

        self.format_combo = QComboBox(self)
        self.format_combo.addItems(["png", "jpg"])
        self.format_combo.setCurrentText(config["format"])
        form.addRow("影像格式", self.format_combo)

        self.quality_spin = QSpinBox(self)
        self.quality_spin.setRange(30, 100)
        self.quality_spin.setValue(int(config["jpeg_quality"]))
        form.addRow("JPG 品質", self.quality_spin)

        self.subfolder_check = QCheckBox("每個主題各開一個子資料夾", self)
        self.subfolder_check.setChecked(bool(config["subfolder_per_topic"]))
        form.addRow("", self.subfolder_check)

        self.copy_check = QCheckBox("存檔時同時複製到剪貼簿", self)
        self.copy_check.setChecked(bool(config["copy_on_save"]))
        form.addRow("", self.copy_check)

        self.notify_check = QCheckBox("存檔後顯示通知", self)
        self.notify_check.setChecked(bool(config["notify_on_save"]))
        form.addRow("", self.notify_check)

        self.cancelled_check = QCheckBox("連按 Esc 取消的截圖也收進歷史", self)
        self.cancelled_check.setChecked(bool(config["record_cancelled"]))
        self.cancelled_check.setToolTip("誤按 Esc 時還能從「截圖歷史」把它救回來。")
        form.addRow("", self.cancelled_check)

        effects_row = QHBoxLayout()
        self.corner_spin = QSpinBox(self)
        self.corner_spin.setRange(0, 40)
        self.corner_spin.setSuffix(" px")
        self.corner_spin.setValue(int(config["round_corners"]))
        self.corner_spin.setToolTip("0 = 直角")
        self.shadow_check = QCheckBox("陰影", self)
        self.shadow_check.setChecked(bool(config["drop_shadow"]))
        self.border_check = QCheckBox("外框", self)
        self.border_check.setChecked(bool(config["add_border"]))
        effects_row.addWidget(QLabel("圓角", self))
        effects_row.addWidget(self.corner_spin)
        effects_row.addWidget(self.shadow_check)
        effects_row.addWidget(self.border_check)
        effects_row.addStretch(1)
        effects_wrapper = QWidget(self)
        effects_wrapper.setLayout(effects_row)
        form.addRow("輸出效果", effects_wrapper)

        self.autostart_check = QCheckBox("開機時自動啟動（常駐系統匣）", self)
        self.autostart_check.setChecked(autostart.is_enabled())
        if autostart.is_packaged():
            self.autostart_check.setEnabled(False)
            self.autostart_check.setToolTip(
                "Microsoft Store 版由 Windows 管理。\n"
                "若要停用，請到工作管理員的「啟動應用程式」頁面。"
            )
        elif autostart.available():
            self.autostart_check.setToolTip(
                "寫入目前使用者的登錄檔啟動項，不需要系統管理員權限。\n"
                f"執行的命令：{autostart.launch_command()}")
        else:
            self.autostart_check.setEnabled(False)
            self.autostart_check.setToolTip("這個功能只支援 Windows。")
        form.addRow("", self.autostart_check)

        self.hk_capture = HotkeyEdit(config["hotkey_capture"], self)
        self.hk_quick = HotkeyEdit(config["hotkey_quickshot"], self)
        self.hk_pin = HotkeyEdit(config["hotkey_pin"], self)
        self.hk_topic = HotkeyEdit(config["hotkey_topic"], self)
        self.hk_repeat = HotkeyEdit(config["hotkey_repeat"], self)
        self.hk_hide = HotkeyEdit(config["hotkey_hide_pins"], self)
        form.addRow("熱鍵：框選截圖", self.hk_capture)
        form.addRow("熱鍵：快速截圖存檔", self.hk_quick)
        form.addRow("熱鍵：重複上次範圍", self.hk_repeat)
        form.addRow("熱鍵：貼上為釘圖", self.hk_pin)
        form.addRow("熱鍵：隱藏所有釘圖", self.hk_hide)
        form.addRow("熱鍵：切換主題", self.hk_topic)
        hotkey_note = QLabel(
            "點一下欄位後直接按下組合鍵即可；Esc 清空代表停用。按下 OK 立即生效。",
            self)
        hotkey_note.setStyleSheet("color:#888; font-size:11px;")
        hotkey_note.setWordWrap(True)
        form.addRow("", hotkey_note)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "選擇存檔資料夾", self.dir_edit.text()
        )
        if chosen:
            self.dir_edit.setText(chosen)

    def apply_autostart(self) -> bool | None:
        """回傳 None 表示沒有變動，否則回傳是否設定成功。"""
        wanted = self.autostart_check.isChecked()
        if not autostart.available() or wanted == autostart.is_enabled():
            return None
        return autostart.sync(wanted)

    def apply_to_config(self) -> None:
        self.cfg["save_dir"] = self.dir_edit.text().strip() or self.cfg["save_dir"]
        self.cfg["template"] = self.template_edit.text().strip() or "{topic}_{n:02d}"
        self.cfg["format"] = self.format_combo.currentText()
        self.cfg["jpeg_quality"] = self.quality_spin.value()
        self.cfg["subfolder_per_topic"] = self.subfolder_check.isChecked()
        self.cfg["copy_on_save"] = self.copy_check.isChecked()
        self.cfg["notify_on_save"] = self.notify_check.isChecked()
        self.cfg["record_cancelled"] = self.cancelled_check.isChecked()
        self.cfg["round_corners"] = self.corner_spin.value()
        self.cfg["drop_shadow"] = self.shadow_check.isChecked()
        self.cfg["add_border"] = self.border_check.isChecked()
        self.cfg["hotkey_capture"] = self.hk_capture.text().strip()
        self.cfg["hotkey_quickshot"] = self.hk_quick.text().strip()
        self.cfg["hotkey_pin"] = self.hk_pin.text().strip()
        self.cfg["hotkey_topic"] = self.hk_topic.text().strip()
        self.cfg["hotkey_repeat"] = self.hk_repeat.text().strip()
        self.cfg["hotkey_hide_pins"] = self.hk_hide.text().strip()
        self.cfg.set_topic(self.topic_edit.text())  # 內含 save()
