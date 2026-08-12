"""熱鍵解析與錄製欄位測試：python test_hotkeys.py"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from sniptag import hotkeys
from sniptag.dialogs import HotkeyEdit

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def press(widget: HotkeyEdit, key, modifiers=Qt.NoModifier) -> None:
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, modifiers))


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("解析")
    check(hotkeys.parse("F1")[1] == 0x70, "F1 -> VK 0x70")
    check(hotkeys.parse("F12")[1] == 0x7B, "F12 -> VK 0x7B")
    mods, vk = hotkeys.parse("Ctrl+Shift+A")
    check(vk == ord("A"), "字母鍵")
    check(mods & MOD_CONTROL and mods & MOD_SHIFT, "Ctrl 與 Shift 都在")
    check(not mods & MOD_ALT, "沒按的修飾鍵不會混進來")
    check(hotkeys.parse("Meta+P")[0] & MOD_WIN, "Meta 對應到 Windows 鍵")
    check(hotkeys.parse("bogus+") is None, "亂打的組合 -> None")
    check(hotkeys.parse("") is None, "空字串 -> None")

    print("錄製欄位")
    widget = HotkeyEdit("F1")
    check(widget.text() == "F1", "帶入原本的值")
    check(widget.isReadOnly(), "唯讀，不能用打字的")

    press(widget, Qt.Key_F1, Qt.ShiftModifier)
    check(widget.text() == "Shift+F1", "按 Shift+F1 -> 記錄成 Shift+F1")
    check(hotkeys.parse(widget.text()) is not None, "記錄的字串本身可被解析")

    press(widget, Qt.Key_F4, Qt.ControlModifier | Qt.AltModifier)
    check(widget.text() == "Ctrl+Alt+F4", "多個修飾鍵")

    before = widget.text()
    press(widget, Qt.Key_Shift, Qt.ShiftModifier)
    press(widget, Qt.Key_Control, Qt.ControlModifier)
    check(widget.text() == before, "只按修飾鍵不會覆寫，會等真正的鍵")

    press(widget, Qt.Key_Escape)
    check(widget.text() == "", "Esc 清空代表停用")
    press(widget, Qt.Key_F2)
    press(widget, Qt.Key_Backspace)
    check(widget.text() == "", "Backspace 也能清空")

    print("停用的熱鍵不算註冊失敗")
    manager = hotkeys.HotkeyManager(app)
    try:
        check(manager.register("", lambda: None) is False, "空字串不註冊")
        check(manager.register("   ", lambda: None) is False, "空白字串不註冊")
        check(manager.failed == [], "但也不會被列為失敗")
        check(manager.register("!!bad!!", lambda: None) is False, "壞組合註冊失敗")
        check(manager.failed == ["!!bad!!"], "壞組合才會被列出來")
    finally:
        manager.unregister_all()

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
