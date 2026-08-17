"""游標下的 UI 元素階層（UI Automation）。

EnumChildWindows 看不進 Chrome / Edge / Electron —— 對 Win32 來說
整個網頁就是一塊畫布。UI Automation 走的是無障礙樹，瀏覽器會把網頁裡的
元素（文章區塊、圖片、表格…）暴露出來，所以拿它來補「視窗裡的子區塊」。

查詢一次要花數十毫秒，呼叫端必須節流（Overlay 用停頓去抖動），
這裡只負責「給一個座標，回傳由小到大的矩形階層」。
"""
from __future__ import annotations

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
