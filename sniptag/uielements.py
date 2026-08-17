"""游標下的 UI 元素階層（UI Automation）。

EnumChildWindows 看不進 Chrome / Edge / Electron —— 對 Win32 來說
整個網頁就是一塊畫布。UI Automation 走的是無障礙樹，瀏覽器會把網頁裡的
元素（文章區塊、圖片、表格…）暴露出來，所以拿它來補「視窗裡的子區塊」。

查詢一次要花數十毫秒，呼叫端必須節流（Overlay 用停頓去抖動），
這裡只負責「給一個座標，回傳由小到大的矩形階層」。
"""
from __future__ import annotations

import ctypes
import sys

Rect = tuple[int, int, int, int]

MAX_DEPTH = 12          # 最多往上走幾層祖先
MIN_SIDE = 24           # 太小的元素（游標、圖示）沒有框選價值
_uia = None
_walker = None
_failed = False


def _client():
    """第一次用到才初始化 COM；失敗就記住，之後不再嘗試。"""
    global _uia, _walker, _failed
    if _failed or sys.platform != "win32":
        return None
    if _uia is not None:
        return _uia
    try:
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()
        module = comtypes.client.GetModule("UIAutomationCore.dll")
        _uia = comtypes.CoCreateInstance(
            module.CUIAutomation._reg_clsid_,
            interface=module.IUIAutomation,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        _walker = _uia.ControlViewWalker
    except Exception:
        _failed = True
        _uia = None
    return _uia


def available() -> bool:
    return _client() is not None


def hierarchy_at(x: int, y: int) -> list[Rect]:
    """回傳 (x, y) 底下的元素矩形，由小到大（實體像素座標）。

    任何失敗都回傳空清單 —— 這是輔助功能，不能拖垮截圖流程。
    """
    uia = _client()
    if uia is None:
        return []
    try:
        import ctypes.wintypes as wintypes

        element = uia.ElementFromPoint(wintypes.POINT(x, y))
    except Exception:
        return []

    rects: list[Rect] = []
    for _ in range(MAX_DEPTH):
        if element is None:
            break
        try:
            bounds = element.CurrentBoundingRectangle
            rect = (int(bounds.left), int(bounds.top),
                    int(bounds.right), int(bounds.bottom))
            if (rect[2] - rect[0] >= MIN_SIDE
                    and rect[3] - rect[1] >= MIN_SIDE
                    and (not rects or rect != rects[-1])):
                rects.append(rect)
        except Exception:
            pass
        try:
            # 走到最頂層時這裡會丟 COMError（不是回傳 None）——
            # 收工，把已經拿到的層級交出去
            element = _walker.GetParentElement(element)
        except Exception:
            break
    return rects


class ProbeThrough:
    """暫時讓一個視窗對命中測試透明。

    截圖時整個螢幕蓋著我們自己的全螢幕框選視窗，ElementFromPoint 會打到
    它而不是底下的瀏覽器。WS_EX_TRANSPARENT 要搭配 WS_EX_LAYERED 才會
    影響命中測試（實測單獨設定無效），查完立刻還原。
    """

    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x20
    WS_EX_LAYERED = 0x80000
    LWA_ALPHA = 0x2

    def __init__(self, widget) -> None:
        self._hwnd = None
        self._old = None
        if sys.platform == "win32":
            try:
                self._hwnd = int(widget.winId())
            except Exception:
                self._hwnd = None

    def __enter__(self) -> "ProbeThrough":
        if self._hwnd is None:
            return self
        try:
            user32 = ctypes.windll.user32
            get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            get_long.restype = ctypes.c_ssize_t
            get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
            set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            set_long.restype = ctypes.c_ssize_t
            set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]

            self._old = get_long(self._hwnd, self.GWL_EXSTYLE)
            set_long(self._hwnd, self.GWL_EXSTYLE,
                     self._old | self.WS_EX_TRANSPARENT | self.WS_EX_LAYERED)
            # 全不透明：視覺上完全沒有變化，只影響命中測試
            user32.SetLayeredWindowAttributes(
                ctypes.c_void_p(self._hwnd), 0, 255, self.LWA_ALPHA)
        except Exception:
            self._old = None
        return self

    def __exit__(self, *_exc) -> None:
        if self._hwnd is None or self._old is None:
            return
        try:
            user32 = ctypes.windll.user32
            set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            set_long.restype = ctypes.c_ssize_t
            set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_long(self._hwnd, self.GWL_EXSTYLE, self._old)
        except Exception:
            pass


def merge_into(hierarchy: list, extra: list, bounding) -> list:
    """把 UIA 的矩形併進既有的候選清單。

    hierarchy / 回傳值：QRect 清單，由大到小（配合 Overlay 的滾輪切換方向）。
    extra：hierarchy_at 的結果換算成 QRect 後的清單。
    bounding：最外層視窗的 QRect，超出它的（例如整個桌面）不收。
    """
    combined = {(r.x(), r.y(), r.width(), r.height()): r for r in hierarchy}
    for rect in extra:
        if bounding is not None:
            rect = rect.intersected(bounding)   # 不讓元素超出它所在的視窗
        if rect.width() < MIN_SIDE or rect.height() < MIN_SIDE:
            continue
        key = (rect.x(), rect.y(), rect.width(), rect.height())
        combined.setdefault(key, rect)
    return sorted(combined.values(),
                  key=lambda r: r.width() * r.height(), reverse=True)
