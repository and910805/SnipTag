"""Windows 全域熱鍵（RegisterHotKey + Qt native event filter）。"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

_NAMED_KEYS = {
    "ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": 0x20, "TAB": 0x09,
    "ENTER": 0x0D, "RETURN": 0x0D, "INSERT": 0x2D, "DELETE": 0x2E,
    "HOME": 0x24, "END": 0x23, "PGUP": 0x21, "PGDN": 0x22,
    "PRINTSCREEN": 0x2C, "PRTSC": 0x2C,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA,
    "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}
_MODS = {
    "CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL,
    "ALT": MOD_ALT, "SHIFT": MOD_SHIFT,
    "WIN": MOD_WIN, "META": MOD_WIN, "SUPER": MOD_WIN,
}


def parse(spec: str) -> tuple[int, int] | None:
    """'Ctrl+Shift+F1' -> (modifiers, virtual-key)"""
    parts = [p.strip() for p in str(spec).split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for part in parts[:-1]:
        bit = _MODS.get(part.upper())
        if bit is None:
            return None
        mods |= bit
    key = parts[-1].upper()
    if key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    elif len(key) == 2 and key[0] == "F" and key[1].isdigit():
        vk = 0x70 + int(key[1]) - 1
    elif len(key) == 3 and key[0] == "F" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and (key.isalpha() or key.isdigit()):
        vk = ord(key)
    else:
        return None
    return mods | MOD_NOREPEAT, vk


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, callbacks: dict) -> None:
        super().__init__()
        self.callbacks = callbacks

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
            except (TypeError, ValueError):
                return False, 0
            if msg.message == WM_HOTKEY:
                callback = self.callbacks.get(int(msg.wParam))
                if callback is not None:
                    callback()
                    return True, 0
        return False, 0


class HotkeyManager:
    """註冊全域熱鍵；註冊失敗的會列在 .failed 讓上層提示使用者。"""

    def __init__(self, app) -> None:
        self.app = app
        self.callbacks: dict[int, callable] = {}
        self.failed: list[str] = []
        self._next_id = 1
        self._filter = _Filter(self.callbacks)
        self._available = sys.platform == "win32"
        if self._available:
            app.installNativeEventFilter(self._filter)

    def register(self, spec: str, callback) -> bool:
        if not self._available:
            return False
        parsed = parse(spec)
        if parsed is None:
            self.failed.append(spec)
            return False
        mods, vk = parsed
        hotkey_id = self._next_id
        if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, mods, vk):
            self.failed.append(spec)
            return False
        self.callbacks[hotkey_id] = callback
        self._next_id += 1
        return True

    def unregister_all(self) -> None:
        if not self._available:
            return
        for hotkey_id in list(self.callbacks):
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self.callbacks.clear()
        self.failed.clear()
        self._next_id = 1
