"""工具列圖示：全部用程式畫出來，不需要額外的資源檔。

圖形工具用圖形表示比文字快讀得多 —— 名稱與快捷鍵改放在 tooltip。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
)

SIZE = 20
INK = "#e8eaed"


def _canvas() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(SIZE * 2, SIZE * 2)
    pixmap.setDevicePixelRatio(2.0)      # 設了 dpr 之後 painter 就是邏輯座標
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    return pixmap, painter


def _stroke(painter: QPainter, width: float = 1.6, dashed: bool = False) -> QPen:
    pen = QPen(QColor(INK), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if dashed:
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([2.4, 1.8])
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    return pen


def _arrow_head(painter: QPainter, tip: QPointF, angle: float,
                length: float = 5.5) -> None:
    spread = math.radians(26)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(INK))
    painter.drawPolygon(QPolygonF([
        tip,
        QPointF(tip.x() - math.cos(angle - spread) * length,
                tip.y() - math.sin(angle - spread) * length),
        QPointF(tip.x() - math.cos(angle + spread) * length,
                tip.y() - math.sin(angle + spread) * length),
    ]))


# --- 各工具 -------------------------------------------------------
def _rect(painter: QPainter) -> None:
    _stroke(painter)
    painter.drawRect(QRectF(3.5, 5.5, 13, 9))


def _rounded(painter: QPainter) -> None:
    _stroke(painter)
    painter.drawRoundedRect(QRectF(3.5, 5.5, 13, 9), 3.5, 3.5)


def _ellipse(painter: QPainter) -> None:
    _stroke(painter)
    painter.drawEllipse(QRectF(3.5, 4.5, 13, 11))


def _line(painter: QPainter) -> None:
    _stroke(painter)
    painter.drawLine(QPointF(4, 15), QPointF(16, 5))


def _arrow(painter: QPainter) -> None:
    _stroke(painter, 1.7)
    painter.drawLine(QPointF(4, 16), QPointF(13.2, 6.8))
    _arrow_head(painter, QPointF(16, 4), math.radians(-45))


def _both_ends(painter: QPainter) -> None:
    # 線的兩端要剛好接到箭頭底部，不然看起來像一條浮在中間的線
    _stroke(painter, 1.7)
    painter.drawLine(QPointF(8.4, 11.6), QPointF(11.6, 8.4))
    _arrow_head(painter, QPointF(15.5, 4.5), math.radians(-45), 5.5)
    _arrow_head(painter, QPointF(4.5, 15.5), math.radians(135), 5.5)


def _pen_tool(painter: QPainter) -> None:
    _stroke(painter, 1.7)
    path = QPainterPath(QPointF(3.5, 13.5))
    path.cubicTo(QPointF(6, 4), QPointF(9, 17), QPointF(11, 10))
    path.cubicTo(QPointF(12.5, 5), QPointF(15, 6), QPointF(16.5, 11))
    painter.drawPath(path)


def _marker(painter: QPainter) -> None:
    """一條被螢光筆劃過的文字：上下細線是字，中間粗帶是螢光。"""
    _stroke(painter, 1.3)
    painter.drawLine(QPointF(4, 5.5), QPointF(16, 5.5))
    painter.drawLine(QPointF(4, 15), QPointF(12.5, 15))
    pen = QPen(QColor(INK), 6.5)
    pen.setCapStyle(Qt.FlatCap)
    painter.setPen(pen)
    painter.setOpacity(0.5)
    painter.drawLine(QPointF(3.5, 10.2), QPointF(16.5, 10.2))
    painter.setOpacity(1.0)


def _mosaic(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    filled = {(0, 0), (1, 1), (2, 0), (0, 2), (2, 2), (1, 3), (3, 1), (3, 3)}
    for column in range(4):
        for row in range(4):
            painter.setBrush(QColor(INK) if (column, row) in filled
                             else QColor(232, 234, 237, 70))
            painter.drawRect(QRectF(3 + column * 3.6, 3 + row * 3.6, 3.1, 3.1))


def _text(painter: QPainter) -> None:
    _stroke(painter, 1.7)
    painter.drawLine(QPointF(4.5, 5.5), QPointF(15.5, 5.5))
    painter.drawLine(QPointF(10, 5.5), QPointF(10, 15.5))


def _number(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(INK))
    painter.drawEllipse(QRectF(3.5, 3.5, 13, 13))
    pen = QPen(QColor(35, 38, 43), 1.7)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(10, 6.5), QPointF(10, 13.5))
    painter.drawLine(QPointF(8.2, 8.2), QPointF(10, 6.5))


def _eraser(painter: QPainter) -> None:
    _stroke(painter)
    painter.drawPolygon(QPolygonF([
        QPointF(3.5, 13), QPointF(9.5, 4.5), QPointF(16.5, 8.5),
        QPointF(11.5, 15.5), QPointF(6, 15.5),
    ]))
    painter.drawLine(QPointF(6, 15.5), QPointF(11.5, 15.5))


def _filled(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(INK))
    painter.drawRect(QRectF(3.5, 5.5, 13, 9))


def _dashed(painter: QPainter) -> None:
    _stroke(painter, 1.8, dashed=True)
    painter.drawLine(QPointF(3.5, 10), QPointF(16.5, 10))


def _width_dot(diameter: float):
    def paint(painter: QPainter) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(INK))
        painter.drawEllipse(QRectF((SIZE - diameter) / 2, (SIZE - diameter) / 2,
                                   diameter, diameter))
    return paint


def _undo(painter: QPainter) -> None:
    _stroke(painter, 1.7)
    painter.drawArc(QRectF(4, 5.5, 12, 11), 30 * 16, 260 * 16)
    _arrow_head(painter, QPointF(4.2, 7.2), math.radians(115), 5.0)


def _clear(painter: QPainter) -> None:
    _stroke(painter, 1.7)
    painter.drawLine(QPointF(5.5, 5.5), QPointF(14.5, 14.5))
    painter.drawLine(QPointF(14.5, 5.5), QPointF(5.5, 14.5))


PAINTERS = {
    "rect": _rect,
    "ellipse": _ellipse,
    "arrow": _arrow,
    "line": _line,
    "pen": _pen_tool,
    "marker": _marker,
    "mosaic": _mosaic,
    "text": _text,
    "number": _number,
    "eraser": _eraser,
    "filled": _filled,
    "dashed": _dashed,
    "rounded": _rounded,
    "both_ends": _both_ends,
    "undo": _undo,
    "clear": _clear,
}

_cache: dict[str, QIcon] = {}


def _dimmed(pixmap: QPixmap) -> QPixmap:
    """停用狀態的版本。Qt 自動產生的灰階在深色底上分不太出來。"""
    faded = QPixmap(pixmap.size())
    faded.setDevicePixelRatio(pixmap.devicePixelRatio())
    faded.fill(Qt.transparent)
    painter = QPainter(faded)
    painter.setOpacity(0.28)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return faded


def _build(paint) -> QIcon:
    pixmap, painter = _canvas()
    paint(painter)
    painter.end()
    result = QIcon(pixmap)
    result.addPixmap(_dimmed(pixmap), QIcon.Disabled)
    return result


def icon(name: str) -> QIcon:
    if name not in _cache:
        painter_fn = PAINTERS.get(name, lambda _painter: None)
        _cache[name] = _build(painter_fn)
    return _cache[name]


def width_icon(width: int) -> QIcon:
    key = f"width{width}"
    if key not in _cache:
        _cache[key] = _build(_width_dot(min(13.0, 2.5 + width * 1.9)))
    return _cache[key]
