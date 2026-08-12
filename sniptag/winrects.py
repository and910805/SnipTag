"""列舉桌面上可見視窗（含其中的子區塊），用來做截圖時的輔助框。

回傳的順序即 Z 序（最上層在前），每一組的第一個元素是視窗本身，
後面接著它的子控制項 —— 讓框選時可以精準到視窗裡的某一塊，
而不是只能框整個視窗。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
MIN_SIDE = 24
MIN_CHILD_SIDE = 32
MAX_CHILDREN = 300

Rect = tuple[int, int, int, int]


def _frame_rect(hwnd, user32, dwmapi) -> Rect | None:
    rect = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
    ) != 0:
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
    return rect.left, rect.top, rect.right, rect.bottom


def _children(hwnd, user32) -> list[Rect]:
    """視窗內的子控制項範圍（用 GetWindowRect，已是螢幕座標）。"""
    found: list[Rect] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(child, _lparam):
        if len(found) >= MAX_CHILDREN:
            return False
        if not user32.IsWindowVisible(child):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(child, ctypes.byref(rect)):
            return True
        if (rect.right - rect.left < MIN_CHILD_SIDE
                or rect.bottom - rect.top < MIN_CHILD_SIDE):
            return True
        found.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    try:
        user32.EnumChildWindows(hwnd, callback, 0)
    except Exception:
        return []
    return found


def list_window_groups() -> list[list[Rect]]:
    """Z 序由上而下；每組 = [視窗本身, 子區塊...]，座標為實體像素。"""
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

    groups: list[list[Rect]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if get_long(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True

        cloaked = wintypes.DWORD()
        if dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        ) == 0 and cloaked.value:
            return True  # 例如切到別的虛擬桌面的視窗

        frame = _frame_rect(hwnd, user32, dwmapi)
        if frame is None:
            return True
        if frame[2] - frame[0] < MIN_SIDE or frame[3] - frame[1] < MIN_SIDE:
            return True
        groups.append([frame] + _children(hwnd, user32))
        return True

    try:
        user32.EnumWindows(callback, 0)
    except Exception:
        return []
    return groups


def active_window_rect() -> Rect | None:
    """目前作用中視窗的範圍（實體像素）。"""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
    except (AttributeError, OSError):
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    frame = _frame_rect(hwnd, user32, dwmapi)
    if frame is None or frame[2] - frame[0] < MIN_SIDE:
        return None
    return frame


def list_window_rects() -> list[Rect]:
    """只要最上層視窗的範圍（保留給不需要子區塊的呼叫端）。"""
    return [group[0] for group in list_window_groups()]
