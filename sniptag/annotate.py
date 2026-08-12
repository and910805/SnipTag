"""標註圖形：矩形、橢圓、箭頭、直線、畫筆、螢光筆、馬賽克、文字。

所有圖形都以「框選介面的座標」記錄，實際輸出時再由呼叫端縮放到原生解析度，
所以標註在高 DPI 螢幕上也是向量般銳利，不會跟著截圖一起被放大。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPolygonF,
)

PALETTE = ["#f5423f", "#ff9f1c", "#2ecc71", "#2d7ff9", "#ffffff", "#1b2330"]
WIDTHS = (("細", 2), ("中", 4), ("粗", 7))
MOSAIC_BLOCK = 12
TEXT_FONT = "Microsoft JhengHei UI"


@dataclass
class Style:
    color: str = PALETTE[0]
    width: int = 4

    def pen(self, cap=Qt.RoundCap) -> QPen:
        pen = QPen(QColor(self.color), self.width)
        pen.setCapStyle(cap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def copy(self) -> "Style":
        return Style(self.color, self.width)


class Context:
    """提供底圖像素給馬賽克使用。"""

    def pixels(self, rect: QRect) -> QImage:  # pragma: no cover - 介面宣告
        raise NotImplementedError


# --- 圖形 ---------------------------------------------------------
@dataclass
class RectShape:
    start: QPoint
    end: QPoint
    style: Style

    @property
    def rect(self) -> QRect:
        return QRect(self.start, self.end).normalized()

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        painter.setPen(self.style.pen(Qt.SquareCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect)


@dataclass
class EllipseShape:
    start: QPoint
    end: QPoint
    style: Style

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        painter.setPen(self.style.pen(Qt.SquareCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRect(self.start, self.end).normalized())


@dataclass
class LineShape:
    start: QPoint
    end: QPoint
    style: Style

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(self.start, self.end)


@dataclass
class ArrowShape:
    start: QPoint
    end: QPoint
    style: Style

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        head = max(11.0, self.style.width * 3.4)
        angle = math.atan2(dy, dx)
        # 線段先收短一點，才不會從箭頭尖端戳出來
        shaft_end = QPointF(self.end.x() - math.cos(angle) * head * 0.72,
                            self.end.y() - math.sin(angle) * head * 0.72)
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(self.start), shaft_end)

        spread = math.radians(24)
        tip = QPointF(self.end)
        left = QPointF(self.end.x() - math.cos(angle - spread) * head,
                       self.end.y() - math.sin(angle - spread) * head)
        right = QPointF(self.end.x() - math.cos(angle + spread) * head,
                        self.end.y() - math.sin(angle + spread) * head)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.style.color))
        painter.drawPolygon(QPolygonF([tip, left, right]))


@dataclass
class PenShape:
    points: list[QPoint]
    style: Style

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        if len(self.points) < 2:
            return
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPolyline(QPolygonF([QPointF(p) for p in self.points]))


@dataclass
class MarkerShape:
    """螢光筆：半透明、加寬，用相乘混色讓底下文字還看得見。"""

    points: list[QPoint]
    style: Style

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        if len(self.points) < 2:
            return
        color = QColor(self.style.color)
        color.setAlpha(110)
        pen = QPen(color, self.style.width * 3.5)
        pen.setCapStyle(Qt.FlatCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Multiply)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolyline(QPolygonF([QPointF(p) for p in self.points]))
        painter.restore()


@dataclass
class MosaicShape:
    start: QPoint
    end: QPoint
    style: Style

    @property
    def rect(self) -> QRect:
        return QRect(self.start, self.end).normalized()

    def draw(self, painter: QPainter, ctx: Context) -> None:
        rect = self.rect
        if rect.width() < 2 or rect.height() < 2:
            return
        source = ctx.pixels(rect)
        if source.isNull():
            return
        block = max(2, MOSAIC_BLOCK)
        small = source.scaled(max(1, rect.width() // block),
                              max(1, rect.height() // block),
                              Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.drawImage(rect, small)
        painter.restore()


@dataclass
class TextShape:
    pos: QPoint
    text: str
    style: Style

    def font(self) -> QFont:
        font = QFont(TEXT_FONT)
        font.setPointSize(8 + self.style.width * 2)
        return font

    def draw(self, painter: QPainter, _ctx: Context) -> None:
        if not self.text:
            return
        font = self.font()
        metrics = QFontMetrics(font)
        painter.setFont(font)
        painter.setPen(QColor(self.style.color))
        painter.drawText(
            QRect(self.pos, QSize(metrics.horizontalAdvance(self.text) + 8,
                                  metrics.height() + 4)),
            Qt.AlignLeft | Qt.AlignTop, self.text,
        )


DRAG_TOOLS = {
    "rect": RectShape,
    "ellipse": EllipseShape,
    "arrow": ArrowShape,
    "line": LineShape,
    "mosaic": MosaicShape,
}
STROKE_TOOLS = {"pen": PenShape, "marker": MarkerShape}

TOOL_LABELS = (
    ("rect", "矩形", "R"),
    ("ellipse", "橢圓", "O"),
    ("arrow", "箭頭", "A"),
    ("line", "直線", "L"),
    ("pen", "畫筆", "P"),
    ("marker", "螢光", "H"),
    ("mosaic", "馬賽克", "M"),
    ("text", "文字", "T"),
)


# --- 圖層 ---------------------------------------------------------
class Layer:
    def __init__(self) -> None:
        self.shapes: list = []
        self._undone: list = []

    def __len__(self) -> int:
        return len(self.shapes)

    def add(self, shape) -> None:
        self.shapes.append(shape)
        self._undone.clear()

    def undo(self) -> bool:
        if not self.shapes:
            return False
        self._undone.append(self.shapes.pop())
        return True

    def redo(self) -> bool:
        if not self._undone:
            return False
        self.shapes.append(self._undone.pop())
        return True

    def clear(self) -> bool:
        if not self.shapes:
            return False
        self._undone.extend(reversed(self.shapes))
        self.shapes.clear()
        return True

    def draw(self, painter: QPainter, ctx: Context, preview=None) -> None:
        for shape in self.shapes:
            shape.draw(painter, ctx)
        if preview is not None:
            preview.draw(painter, ctx)


def make_shape(tool: str, start: QPoint, end: QPoint, style: Style):
    """依工具種類建立圖形；不認識的工具回傳 None。"""
    if tool in DRAG_TOOLS:
        return DRAG_TOOLS[tool](start, end, style.copy())
    if tool in STROKE_TOOLS:
        return STROKE_TOOLS[tool]([start, end], style.copy())
    return None
