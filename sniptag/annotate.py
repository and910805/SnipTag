"""標註圖形：矩形、橢圓、箭頭、直線、畫筆、螢光筆、馬賽克、文字、序號。

所有圖形都以「框選介面的座標」記錄，實際輸出時再由呼叫端縮放到原生解析度，
所以標註在高 DPI 螢幕上也是向量般銳利，不會跟著截圖一起被放大。

每個圖形都提供 bounds / hit / translate，讓畫完之後還能點選、搬移、刪除。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPolygonF,
)

PALETTE = ["#f5423f", "#ff9f1c", "#2ecc71", "#2d7ff9", "#ffffff", "#1b2330"]
WIDTHS = ((1, 2), (2, 3), (3, 4), (4, 6), (5, 9))   # 顯示標籤, 實際線寬
MOSAIC_BLOCK = 12
TEXT_FONT = "Microsoft JhengHei UI"
HIT_SLACK = 6
CORNER_RADIUS = 10          # 圓角矩形的半徑
ERASER_RADIUS = 14          # 橡皮擦的作用半徑


def _distance_to_segment(point: QPoint, start: QPoint, end: QPoint) -> float:
    dx, dy = end.x() - start.x(), end.y() - start.y()
    if dx == 0 and dy == 0:
        return math.hypot(point.x() - start.x(), point.y() - start.y())
    t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(point.x() - (start.x() + t * dx),
                      point.y() - (start.y() + t * dy))


def _contrast_color(background: QColor) -> QColor:
    """在給定底色上選一個讀得清楚的字色。"""
    luminance = (0.299 * background.red() + 0.587 * background.green()
                 + 0.114 * background.blue())
    return QColor("#1b2330") if luminance > 140 else QColor("#ffffff")


def _near_outline(point: QPoint, rect: QRect, slack: int) -> bool:
    outer = rect.adjusted(-slack, -slack, slack, slack)
    inner = rect.adjusted(slack, slack, -slack, -slack)
    return outer.contains(point) and not inner.contains(point)


@dataclass
class Style:
    color: str = PALETTE[0]
    width: int = 4
    filled: bool = False
    dashed: bool = False
    rounded: bool = False       # 圓角矩形
    both_ends: bool = False     # 雙向箭頭

    def pen(self, cap=Qt.RoundCap) -> QPen:
        pen = QPen(QColor(self.color), self.width)
        pen.setCapStyle(cap)
        pen.setJoinStyle(Qt.RoundJoin)
        if self.dashed:
            pen.setStyle(Qt.CustomDashLine)
            # 以線寬為單位，粗細改變時虛線比例才不會跑掉
            pen.setDashPattern([3.0, 2.4])
        return pen

    def copy(self) -> "Style":
        return Style(self.color, self.width, self.filled, self.dashed,
                     self.rounded, self.both_ends)


# --- 兩點式圖形 ---------------------------------------------------
@dataclass
class _TwoPoint:
    start: QPoint
    end: QPoint
    style: Style

    @property
    def rect(self) -> QRect:
        return QRect(self.start, self.end).normalized()

    def bounds(self) -> QRect:
        slack = self.style.width + HIT_SLACK
        return self.rect.adjusted(-slack, -slack, slack, slack)

    def translate(self, delta: QPoint) -> None:
        self.start += delta
        self.end += delta


class RectShape(_TwoPoint):
    def draw(self, painter: QPainter) -> None:
        painter.setPen(self.style.pen(Qt.SquareCap))
        painter.setBrush(QColor(self.style.color) if self.style.filled else Qt.NoBrush)
        if self.style.rounded:
            radius = min(CORNER_RADIUS, self.rect.width() / 2, self.rect.height() / 2)
            painter.drawRoundedRect(self.rect, radius, radius)
        else:
            painter.drawRect(self.rect)

    def hit(self, point: QPoint) -> bool:
        if self.style.filled:
            return self.bounds().contains(point)
        return _near_outline(point, self.rect, self.style.width + HIT_SLACK)


class EllipseShape(_TwoPoint):
    def draw(self, painter: QPainter) -> None:
        painter.setPen(self.style.pen(Qt.SquareCap))
        painter.setBrush(QColor(self.style.color) if self.style.filled else Qt.NoBrush)
        painter.drawEllipse(self.rect)

    def hit(self, point: QPoint) -> bool:
        rect = self.rect
        if rect.width() < 2 or rect.height() < 2:
            return False
        # 以橢圓方程式判斷，落在環帶上就算命中
        nx = (point.x() - rect.center().x()) / (rect.width() / 2)
        ny = (point.y() - rect.center().y()) / (rect.height() / 2)
        value = nx * nx + ny * ny
        if self.style.filled:
            return value <= 1.25
        return 0.6 <= value <= 1.5


class LineShape(_TwoPoint):
    def draw(self, painter: QPainter) -> None:
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(self.start, self.end)

    def hit(self, point: QPoint) -> bool:
        return _distance_to_segment(point, self.start, self.end) <= (
            self.style.width + HIT_SLACK)


class ArrowShape(_TwoPoint):
    def draw(self, painter: QPainter) -> None:
        dx = self.end.x() - self.start.x()
        dy = self.end.y() - self.start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        head = max(11.0, self.style.width * 3.4)
        angle = math.atan2(dy, dx)
        # 線段兩端各收短一點，才不會從箭頭尖端戳出來
        inset = head * 0.72
        shaft_start = QPointF(self.start)
        if self.style.both_ends:
            shaft_start = QPointF(self.start.x() + math.cos(angle) * inset,
                                  self.start.y() + math.sin(angle) * inset)
        shaft_end = QPointF(self.end.x() - math.cos(angle) * inset,
                            self.end.y() - math.sin(angle) * inset)
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(shaft_start, shaft_end)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.style.color))
        self._draw_head(painter, QPointF(self.end), angle, head)
        if self.style.both_ends:
            self._draw_head(painter, QPointF(self.start), angle + math.pi, head)

    @staticmethod
    def _draw_head(painter: QPainter, tip: QPointF, angle: float,
                   head: float) -> None:
        spread = math.radians(24)
        left = QPointF(tip.x() - math.cos(angle - spread) * head,
                       tip.y() - math.sin(angle - spread) * head)
        right = QPointF(tip.x() - math.cos(angle + spread) * head,
                        tip.y() - math.sin(angle + spread) * head)
        painter.drawPolygon(QPolygonF([tip, left, right]))

    def hit(self, point: QPoint) -> bool:
        return _distance_to_segment(point, self.start, self.end) <= (
            self.style.width + HIT_SLACK)


class MosaicShape(_TwoPoint):
    """打上馬賽克。

    和其他圖形不同，馬賽克要讀取「畫到目前為止」的畫面才能正確疊在別的標註上面，
    所以它不是用畫筆畫上去，而是由 render() 直接對輸出影像做處理。
    """

    def draw(self, painter: QPainter) -> None:
        # 由 render() 呼叫 apply() 處理，這裡不做事
        return

    def apply(self, image: QImage, scale: float, offset: QPoint) -> None:
        rect = _to_device(self.rect, scale, offset).intersected(image.rect())
        if rect.width() < 2 or rect.height() < 2:
            return
        block = max(2, round(MOSAIC_BLOCK * scale))
        small = image.copy(rect).scaled(
            max(1, rect.width() // block), max(1, rect.height() // block),
            Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.drawImage(rect, small)
        painter.end()

    def hit(self, point: QPoint) -> bool:
        return self.rect.contains(point)


# --- 筆畫式圖形 ---------------------------------------------------
@dataclass
class _Stroke:
    points: list[QPoint]
    style: Style

    def bounds(self) -> QRect:
        if not self.points:
            return QRect()
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        slack = self.style.width + HIT_SLACK
        return QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys))).adjusted(
            -slack, -slack, slack, slack)

    def translate(self, delta: QPoint) -> None:
        self.points = [p + delta for p in self.points]

    def hit(self, point: QPoint) -> bool:
        tolerance = self.style.width + HIT_SLACK
        return any(
            _distance_to_segment(point, self.points[i], self.points[i + 1]) <= tolerance
            for i in range(len(self.points) - 1)
        )


class PenShape(_Stroke):
    def draw(self, painter: QPainter) -> None:
        if len(self.points) < 2:
            return
        painter.setPen(self.style.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPolyline(QPolygonF([QPointF(p) for p in self.points]))


class MarkerShape(_Stroke):
    """螢光筆：半透明、加寬，用相乘混色讓底下文字還看得見。"""

    def draw(self, painter: QPainter) -> None:
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

    def hit(self, point: QPoint) -> bool:
        tolerance = self.style.width * 2 + HIT_SLACK
        return any(
            _distance_to_segment(point, self.points[i], self.points[i + 1]) <= tolerance
            for i in range(len(self.points) - 1)
        )


# --- 單點式圖形 ---------------------------------------------------
@dataclass
class TextShape:
    pos: QPoint
    text: str
    style: Style

    def font(self) -> QFont:
        font = QFont(TEXT_FONT)
        font.setPointSize(8 + self.style.width * 2)
        return font

    def bounds(self) -> QRect:
        metrics = QFontMetrics(self.font())
        return QRect(self.pos, QSize(metrics.horizontalAdvance(self.text) + 8,
                                     metrics.height() + 4))

    def translate(self, delta: QPoint) -> None:
        self.pos += delta

    def hit(self, point: QPoint) -> bool:
        return self.bounds().adjusted(-4, -4, 4, 4).contains(point)

    def draw(self, painter: QPainter) -> None:
        if not self.text:
            return
        painter.setFont(self.font())
        if self.style.filled:
            # 底色用文字色，字換成對比色，放在雜亂背景上才讀得到
            box = self.bounds().adjusted(-4, -2, 4, 2)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.style.color))
            painter.drawRoundedRect(box, 3, 3)
            painter.setPen(_contrast_color(QColor(self.style.color)))
        else:
            painter.setPen(QColor(self.style.color))
        painter.drawText(self.bounds(), Qt.AlignLeft | Qt.AlignTop, self.text)


@dataclass
class NumberShape:
    """序號標記：一個實心圓加上白色數字，點一下就自動遞增。"""

    pos: QPoint
    number: int
    style: Style

    def radius(self) -> int:
        return 9 + self.style.width * 2

    def bounds(self) -> QRect:
        r = self.radius()
        return QRect(self.pos.x() - r, self.pos.y() - r, r * 2, r * 2)

    def translate(self, delta: QPoint) -> None:
        self.pos += delta

    def hit(self, point: QPoint) -> bool:
        return (math.hypot(point.x() - self.pos.x(), point.y() - self.pos.y())
                <= self.radius() + 4)

    def draw(self, painter: QPainter) -> None:
        bounds = self.bounds()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.style.color))
        painter.drawEllipse(bounds)
        font = QFont(TEXT_FONT)
        font.setPointSize(max(7, self.radius()))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(bounds, Qt.AlignCenter, str(self.number))


# --- 工具對照表 ---------------------------------------------------
DRAG_TOOLS = {
    "rect": RectShape,
    "ellipse": EllipseShape,
    "arrow": ArrowShape,
    "line": LineShape,
    "mosaic": MosaicShape,
}
STROKE_TOOLS = {"pen": PenShape, "marker": MarkerShape}
CLICK_TOOLS = ("text", "number")

TOOL_LABELS = (
    ("rect", "矩形", "R"),
    ("ellipse", "橢圓", "O"),
    ("arrow", "箭頭", "A"),
    ("line", "直線", "L"),
    ("pen", "畫筆", "P"),
    ("marker", "螢光", "H"),
    ("mosaic", "馬賽克", "M"),
    ("text", "文字", "T"),
    ("number", "序號", "N"),
    ("eraser", "橡皮擦", "E"),
)

FILLABLE = ("rect", "ellipse", "text")   # text 的「填滿」= 加底色
ROUNDABLE = ("rect",)
DASHABLE = ("rect", "ellipse", "line", "arrow", "pen")
DOUBLE_ENDED = ("arrow",)


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

    def remove(self, shape) -> bool:
        if shape in self.shapes:
            self.shapes.remove(shape)
            return True
        return False

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

    def shape_at(self, point: QPoint):
        """由上而下找出第一個被點到的圖形。"""
        for shape in reversed(self.shapes):
            if shape.hit(point):
                return shape
        return None

    def erase_at(self, point: QPoint, radius: int = ERASER_RADIUS) -> bool:
        """擦掉游標附近的標註；有擦到東西就回傳 True。"""
        targets = [s for s in self.shapes
                   if any(s.hit(point + QPoint(dx, dy))
                          for dx, dy in ((0, 0), (-radius, 0), (radius, 0),
                                         (0, -radius), (0, radius)))]
        for shape in targets:
            self.shapes.remove(shape)
            self._undone.append(shape)
        return bool(targets)

    def next_number(self) -> int:
        used = [s.number for s in self.shapes if isinstance(s, NumberShape)]
        return max(used) + 1 if used else 1

    def all_shapes(self, preview=None) -> list:
        return self.shapes + ([preview] if preview is not None else [])


def _to_device(rect: QRect, scale: float, offset: QPoint) -> QRect:
    """標註座標 -> 輸出影像的實體像素座標。"""
    return QRect(round((rect.x() - offset.x()) * scale),
                 round((rect.y() - offset.y()) * scale),
                 round(rect.width() * scale), round(rect.height() * scale))


def _begin(image: QImage, scale: float, offset: QPoint) -> QPainter:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(scale, scale)
    painter.translate(-offset)
    return painter


def render(layer: "Layer", image: QImage, scale: float, offset: QPoint,
           preview=None) -> None:
    """把整個圖層畫到 image 上（就地修改）。

    image 的座標 = (標註座標 - offset) * scale。

    馬賽克必須讀取已經畫上去的內容，否則畫在它底下的標註會被無視 ——
    例如先用實心矩形遮住機敏資訊、再蓋馬賽克，遮住的東西會又被翻出來。
    QPainter 作用中無法安全讀取同一張 QImage，所以遇到馬賽克就先收起畫筆、
    處理完再重新開始。
    """
    painter = _begin(image, scale, offset)
    try:
        for shape in layer.all_shapes(preview):
            if isinstance(shape, MosaicShape):
                painter.end()
                shape.apply(image, scale, offset)
                painter = _begin(image, scale, offset)
            else:
                shape.draw(painter)
    finally:
        if painter.isActive():
            painter.end()


def make_shape(tool: str, start: QPoint, end: QPoint, style: Style):
    """依工具種類建立圖形；不認識的工具回傳 None。"""
    if tool in DRAG_TOOLS:
        return DRAG_TOOLS[tool](start, end, style.copy())
    if tool in STROKE_TOOLS:
        return STROKE_TOOLS[tool]([start, end], style.copy())
    return None


# --- 色彩格式 -----------------------------------------------------
COLOR_FORMATS = ("HEX", "RGB", "HSL")


def format_color(color: QColor, fmt: str) -> str:
    if fmt == "RGB":
        return f"rgb({color.red()}, {color.green()}, {color.blue()})"
    if fmt == "HSL":
        return (f"hsl({max(0, color.hslHue())}, "
                f"{round(color.hslSaturationF() * 100)}%, "
                f"{round(color.lightnessF() * 100)}%)")
    return color.name().upper()
