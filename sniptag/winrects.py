"""列舉桌面上可見視窗的範圍，用來做「滑鼠移到哪就框住哪個視窗」。

回傳順序即 Z 序（最上層在前），所以取第一個包含游標的矩形就是目標視窗。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_VISIBLE = 0x10000000
WS_EX_TOOLWINDOW = 0x00000080
MIN_SIDE = 24


def list_window_rects() -> list[tuple[int, int, int, int]]:
    """實體像素座標的 (left, top, right, bottom) 清單。"""
    if sys.platform != "win32":
        return []
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
    except (AttributeError, OSError):
        return []

    get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    get_long.restype = ctypes.c_ssize_t
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]

    rects: list[tuple[int, int, int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True
        if get_long(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True

        cloaked = wintypes.DWORD()
        if dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        ) == 0 and cloaked.value:
            return True  # 例如切到別的虛擬桌面的視窗

        rect = wintypes.RECT()
        if dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
        ) != 0:
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True

        if rect.right - rect.left < MIN_SIDE or rect.bottom - rect.top < MIN_SIDE:
            return True
        rects.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    try:
        user32.EnumWindows(callback, 0)
    except Exception:
        return []
    return rects
