"""輸出後處理：圓角、陰影、邊框。

這些是存檔前套用在成品上的效果，和標註無關 —— 標註是畫在畫面上的內容，
這裡處理的是整張圖的外觀。
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

SHADOW_MARGIN = 18      # 邏輯像素
SHADOW_LAYERS = 14
BORDER_COLOR = "#00000038"


def _rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    if radius > 0:
        path.addRoundedRect(rect, radius, radius)
    else:
        path.addRect(rect)
    return path


def apply(pixmap: QPixmap, radius: int = 0, shadow: bool = False,
          border: bool = False) -> QPixmap:
    """依序套用圓角、邊框、陰影。radius 與邊界都以邏輯像素計。"""
    if not radius and not shadow and not border:
        return pixmap

    dpr = pixmap.devicePixelRatio() or 1.0
    source = QPixmap(pixmap)
    source.setDevicePixelRatio(1.0)
    radius_px = radius * dpr

    # --- 圓角與邊框：先做成一張帶 alpha 的圖 ---
    shaped = QPixmap(source.size())
    shaped.fill(Qt.transparent)
    painter = QPainter(shaped)
    painter.setRenderHint(QPainter.Antialiasing, True)
    body = QRectF(0, 0, source.width(), source.height())
    path = _rounded_path(body, radius_px)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, source)
    painter.setClipping(False)
    if border:
        pen = QPen(QColor(BORDER_COLOR), max(1.0, dpr))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        inset = pen.widthF() / 2
        painter.drawPath(_rounded_path(body.adjusted(inset, inset, -inset, -inset),
                                       max(0.0, radius_px - inset)))
    painter.end()

    if not shadow:
        shaped.setDevicePixelRatio(dpr)
        return shaped

    # --- 陰影：外擴一圈，用多層低透明度堆出柔邊 ---
    margin = round(SHADOW_MARGIN * dpr)
    canvas = QPixmap(source.width() + margin * 2, source.height() + margin * 2)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    for layer in range(SHADOW_LAYERS, 0, -1):
        spread = margin * layer / SHADOW_LAYERS
        rect = QRectF(margin - spread, margin - spread + margin * 0.18,
                      source.width() + spread * 2, source.height() + spread * 2)
        painter.setBrush(QColor(0, 0, 0, 8))
        painter.drawPath(_rounded_path(rect, radius_px + spread))
    painter.drawPixmap(margin, margin, shaped)
    painter.end()
    canvas.setDevicePixelRatio(dpr)
    return canvas
