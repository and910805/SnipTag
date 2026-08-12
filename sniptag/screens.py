"""桌面擷取與座標換算。

重點：支援混合 DPI（例如筆電 200% + 外接螢幕 100%）。
每台螢幕都保留自己的「邏輯矩形 ↔ 實體矩形 ↔ 縮放比」，所有換算都逐螢幕做，
不使用單一全域縮放比例，插拔外接螢幕不需要任何設定。
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
MONITORINFOF_PRIMARY = 1


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


@dataclass(frozen=True)
class Monitor:
    """一台螢幕：Qt 的邏輯座標、Windows 的實體座標，以及兩者的比例。"""

    name: str
    logical: QRect
    physical: QRect
    dpr: float

    def to_physical(self, point: QPoint) -> QPoint:
        return QPoint(
            round(self.physical.x() + (point.x() - self.logical.x()) * self.dpr),
            round(self.physical.y() + (point.y() - self.logical.y()) * self.dpr),
        )

    def to_logical(self, point: QPoint) -> QPoint:
        return QPoint(
            round(self.logical.x() + (point.x() - self.physical.x()) / self.dpr),
            round(self.logical.y() + (point.y() - self.physical.y()) / self.dpr),
        )


def virtual_geometry() -> QRect:
    """所有螢幕聯集後的邏輯座標範圍（Qt 座標系）。"""
    geo = QRect()
    for screen in QGuiApplication.screens():
        geo = geo.united(screen.geometry())
    return geo


def _win32_monitors() -> dict[str, QRect]:
    """裝置名稱 -> 實體像素矩形。"""
    if sys.platform != "win32":
        return {}
    try:
        user32 = ctypes.windll.user32
    except AttributeError:
        return {}

    found: dict[str, QRect] = {}
    proc = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
    )

    @proc
    def callback(handle, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcMonitor
            found[info.szDevice] = QRect(
                r.left, r.top, r.right - r.left, r.bottom - r.top
            )
        return True

    try:
        user32.EnumDisplayMonitors(None, None, callback, 0)
    except Exception:
        return {}
    return found


def enumerate_monitors() -> list[Monitor]:
    """把 Qt 螢幕與 Win32 螢幕配對起來。

    Windows 上 QScreen.name() 就是 '\\\\.\\DISPLAY1' 這種裝置名稱，可直接對上。
    對不上時退而用「邏輯尺寸 × 縮放比 == 實體尺寸」來配，再不行就自行推算。
    """
    physical_by_name = _win32_monitors()
    unclaimed = dict(physical_by_name)
    monitors: list[Monitor] = []

    for screen in QGuiApplication.screens():
        logical = screen.geometry()
        dpr = screen.devicePixelRatio() or 1.0
        name = screen.name()
        physical = unclaimed.pop(name, None)

        if physical is None:
            expected = (round(logical.width() * dpr), round(logical.height() * dpr))
            for key, rect in list(unclaimed.items()):
                if (rect.width(), rect.height()) == expected:
                    physical = unclaimed.pop(key)
                    break

        if physical is None:
            physical = QRect(
                round(logical.x() * dpr), round(logical.y() * dpr),
                round(logical.width() * dpr), round(logical.height() * dpr),
            )
        monitors.append(Monitor(name, logical, physical, dpr))

    return monitors


class DesktopShot:
    """一次桌面擷取的結果，附帶座標換算能力。

    image 永遠是「整個虛擬桌面的實體像素」，原點為 physical_origin。
    """

    def __init__(self, image: QImage, physical_origin: QPoint,
                 monitors: list[Monitor]) -> None:
        self.image = image
        self.physical_origin = physical_origin
        self.monitors = monitors
        geometry = QRect()
        for monitor in monitors:
            geometry = geometry.united(monitor.logical)
        self.logical_geometry = geometry

    # --- 螢幕查詢 -------------------------------------------------
    def monitor_at(self, logical_point: QPoint) -> Monitor:
        for monitor in self.monitors:
            if monitor.logical.contains(logical_point):
                return monitor
        # 落在螢幕縫隙時，取中心最近的一台
        return min(
            self.monitors,
            key=lambda m: (m.logical.center() - logical_point).manhattanLength(),
            default=Monitor("", self.logical_geometry, self.logical_geometry, 1.0),
        )

    def dpr_for(self, logical_rect: QRect) -> float:
        """跨螢幕時取最高的縮放比，避免高解析那半邊被降級。"""
        overlapping = [m.dpr for m in self.monitors if m.logical.intersects(logical_rect)]
        return max(overlapping) if overlapping else 1.0

    # --- 座標換算 -------------------------------------------------
    def to_image_point(self, logical_point: QPoint) -> QPoint:
        monitor = self.monitor_at(logical_point)
        return monitor.to_physical(logical_point) - self.physical_origin

    def physical_rect_to_logical(self, left: int, top: int,
                                 right: int, bottom: int) -> QRect:
        """Win32 的實體矩形換成 Qt 邏輯矩形（用矩形中心決定歸屬螢幕）。"""
        center = QPoint((left + right) // 2, (top + bottom) // 2)
        monitor = next(
            (m for m in self.monitors if m.physical.contains(center)),
            None,
        )
        if monitor is None:
            monitor = min(
                self.monitors,
                key=lambda m: (m.physical.center() - center).manhattanLength(),
                default=None,
            )
        if monitor is None:
            return QRect(left, top, right - left, bottom - top)
        top_left = monitor.to_logical(QPoint(left, top))
        bottom_right = monitor.to_logical(QPoint(right, bottom))
        return QRect(top_left, bottom_right - QPoint(1, 1))

    def _image_rect_for(self, logical_rect: QRect, monitor: Monitor) -> QRectF:
        offset_x = (logical_rect.x() - monitor.logical.x()) * monitor.dpr
        offset_y = (logical_rect.y() - monitor.logical.y()) * monitor.dpr
        return QRectF(
            monitor.physical.x() + offset_x - self.physical_origin.x(),
            monitor.physical.y() + offset_y - self.physical_origin.y(),
            logical_rect.width() * monitor.dpr,
            logical_rect.height() * monitor.dpr,
        )

    # --- 使用 -----------------------------------------------------
    def paint(self, painter: QPainter, origin: QPoint) -> None:
        """把桌面畫進以 origin 為左上角的邏輯座標系（逐螢幕各自縮放）。"""
        for monitor in self.monitors:
            source = QRectF(monitor.physical.translated(-self.physical_origin))
            target = QRectF(monitor.logical.translated(-origin))
            painter.drawImage(target, self.image, source)

    def crop(self, logical_rect: QRect) -> QPixmap:
        """依螢幕原生解析度裁切；跨螢幕時以較高的一邊為準拼接。"""
        rect = logical_rect.normalized()
        dpr = self.dpr_for(rect)
        # 先以實體像素作畫，畫完才標記 dpr：QPainter 會照 dpr 縮放座標，
        # 太早設會讓所有目標矩形被放大一輪。
        result = QPixmap(max(1, round(rect.width() * dpr)),
                         max(1, round(rect.height() * dpr)))
        result.fill(Qt.black)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        for monitor in self.monitors:
            part = monitor.logical.intersected(rect)
            if part.isEmpty():
                continue
            source = self._image_rect_for(part, monitor)
            target = QRectF(
                (part.x() - rect.x()) * dpr, (part.y() - rect.y()) * dpr,
                part.width() * dpr, part.height() * dpr,
            )
            painter.drawImage(target, self.image, source)
        painter.end()
        result.setDevicePixelRatio(dpr)
        return result

    def color_at(self, logical_point: QPoint) -> QColor:
        point = self.to_image_point(logical_point)
        if not self.image.rect().contains(point):
            return QColor(0, 0, 0)
        return self.image.pixelColor(point)


# --- 擷取 ---------------------------------------------------------
def _bitblt_virtual_screen() -> tuple[QImage, QPoint] | None:
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
    except AttributeError:
        return None

    user32.GetDC.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.BitBlt.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32,
    ]
    gdi32.GetDIBits.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
    ]

    x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if width <= 0 or height <= 0:
        return None

    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        if not gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, x, y,
                            SRCCOPY | CAPTUREBLT):
            return None
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # 負值 = top-down
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB
        buffer = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer,
                               ctypes.byref(info), 0):
            return None
        image = QImage(buffer, width, height, width * 4, QImage.Format_RGB32).copy()
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    return image, QPoint(x, y)


def _grab_with_qt(monitors: list[Monitor]) -> tuple[QImage, QPoint]:
    """跨平台後備：逐螢幕用 Qt 抓，再拼回實體座標系。"""
    bounds = QRect()
    for monitor in monitors:
        bounds = bounds.united(monitor.physical)
    if bounds.isEmpty():
        bounds = QRect(0, 0, 1, 1)

    canvas = QImage(bounds.width(), bounds.height(), QImage.Format_RGB32)
    canvas.fill(Qt.black)
    painter = QPainter(canvas)
    for screen, monitor in zip(QGuiApplication.screens(), monitors):
        shot = screen.grabWindow(0)
        shot.setDevicePixelRatio(1.0)
        target = monitor.physical.translated(-bounds.topLeft())
        painter.drawPixmap(target, shot)
    painter.end()
    return canvas, bounds.topLeft()


def grab_desktop() -> DesktopShot | None:
    monitors = enumerate_monitors()
    if not monitors:
        return None

    grabbed = None
    if sys.platform == "win32":
        try:
            grabbed = _bitblt_virtual_screen()
        except Exception:
            grabbed = None
    if grabbed is None:
        try:
            grabbed = _grab_with_qt(monitors)
        except Exception:
            return None

    image, origin = grabbed
    if image.isNull():
        return None
    return DesktopShot(image, origin, monitors)
