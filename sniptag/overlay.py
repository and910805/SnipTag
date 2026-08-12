"""全螢幕框選介面：暗化背景、拖曳選取、輔助框、放大鏡、標註、動作工具列。

所有換算都交給 DesktopShot 逐螢幕處理，因此混合 DPI（筆電 + 外接螢幕）
不需要任何設定，接上就對。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen,
    QPixmap, QRegion,
)
from PySide6.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from . import annotate, winrects
from .screens import DesktopShot

ACCENT = QColor("#2d7ff9")
DIM = QColor(0, 0, 0, 120)
HANDLE_SIZE = 8
MIN_SELECTION = 3
MAG_BOX = 132          # 放大鏡邊長（邏輯像素）
MAG_SRC_PX = 22        # 放大鏡取樣的原始像素數
NUDGE = 1
NUDGE_FAST = 10

TOOLBAR_QSS = """
QWidget#toolbar { background: #23262b; border: 1px solid #3a3f47; border-radius: 6px; }
QPushButton {
    background: #2f343b; color: #e8eaed; border: none; border-radius: 4px;
    padding: 4px 7px; font-size: 12px;
}
QPushButton:hover { background: #3d434c; }
QPushButton:checked { background: #2d7ff9; color: white; }
QPushButton#primary { background: #2d7ff9; color: white; font-weight: bold; }
QPushButton#primary:hover { background: #4a92fb; }
QLabel#name { color: #9fd18a; font-size: 12px; padding: 0 6px; }
QFrame#sep { background: #3a3f47; }
QLineEdit#inline {
    background: rgba(20, 22, 26, 220); color: white; border: 1px solid #2d7ff9;
    border-radius: 3px; padding: 2px 6px;
}
"""


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("sep")
    line.setFixedWidth(1)
    line.setFrameShape(QFrame.VLine)
    return line


class Toolbar(QWidget):
    """選取完成後浮出來的工具列：上排標註工具，下排輸出動作。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar")
        self.setStyleSheet(TOOLBAR_QSS)
        self.setCursor(Qt.ArrowCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.tool_buttons: dict[str, QPushButton] = {}
        for key, label, shortcut in annotate.TOOL_LABELS:
            button = self._button(f"{label} {shortcut}", checkable=True)
            tools.addWidget(button)
            self.tool_buttons[key] = button
        tools.addWidget(_separator())

        self.fill_button = self._button("填滿", checkable=True)
        tools.addWidget(self.fill_button)
        tools.addWidget(_separator())

        self.color_buttons: dict[str, QPushButton] = {}
        for color in annotate.PALETTE:
            tools.addWidget(self._swatch(color))
        self.custom_button = self._button("＋")
        self.custom_button.setFixedSize(20, 18)
        self.custom_button.setToolTip("自訂顏色")
        tools.addWidget(self.custom_button)
        tools.addWidget(_separator())

        self.width_buttons: dict[int, QPushButton] = {}
        for label, value in annotate.WIDTHS:
            button = self._button(label, checkable=True)
            tools.addWidget(button)
            self.width_buttons[value] = button
        tools.addWidget(_separator())

        self.undo_button = self._button("復原")
        self.undo_button.setToolTip("復原 Ctrl+Z　／　重做 Ctrl+Shift+Z")
        self.clear_button = self._button("清除")
        self.clear_button.setToolTip("清除所有標註")
        tools.addWidget(self.undo_button)
        tools.addWidget(self.clear_button)
        tools.addStretch(1)
        outer.addLayout(tools)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.name_label = QLabel(self)
        self.name_label.setObjectName("name")
        actions.addWidget(self.name_label)
        actions.addStretch(1)

        self.buttons: dict[str, QPushButton] = {}
        for key, text, primary in (
            ("save", "存檔  ⏎", True),
            ("copy", "複製  Ctrl+C", False),
            ("pin", "釘選  F", False),
            ("saveas", "另存…  Ctrl+S", False),
            ("cancel", "取消  Esc", False),
        ):
            button = self._button(text)
            if primary:
                button.setObjectName("primary")
            actions.addWidget(button)
            self.buttons[key] = button
        outer.addLayout(actions)
        self.adjustSize()

    def _button(self, text: str, checkable: bool = False) -> QPushButton:
        button = QPushButton(text, self)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.PointingHandCursor)
        button.setCheckable(checkable)
        return button

    def _swatch(self, color: str) -> QPushButton:
        button = self._button("", checkable=True)
        button.setFixedSize(18, 18)
        button.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 2px solid #23262b;"
            f" border-radius: 9px; padding: 0; }}"
            f"QPushButton:checked {{ border: 2px solid #e8eaed; }}"
        )
        self.color_buttons[color] = button
        return button

    def set_name(self, name: str) -> None:
        self.name_label.setText(f"→ {name}")
        self.adjustSize()

    def sync(self, tool: str | None, style: annotate.Style) -> None:
        for key, button in self.tool_buttons.items():
            button.setChecked(key == tool)
        for color, button in self.color_buttons.items():
            button.setChecked(color.lower() == style.color.lower())
        for value, button in self.width_buttons.items():
            button.setChecked(value == style.width)
        self.fill_button.setChecked(style.filled)
        self.fill_button.setEnabled(tool in annotate.FILLABLE)


class _ShotContext(annotate.Context):
    """讓馬賽克拿得到底圖像素。"""

    def __init__(self, shot: DesktopShot, origin: QPoint) -> None:
        self.shot = shot
        self.origin = origin

    def pixels(self, rect: QRect) -> QImage:
        pixmap = self.shot.crop(rect.translated(self.origin))
        pixmap.setDevicePixelRatio(1.0)
        return pixmap.toImage()


class Overlay(QWidget):
    finished = Signal(QPixmap, str, QRect)   # 影像、動作、螢幕上的位置
    cancelled = Signal()

    def __init__(self, shot: DesktopShot, preview_cb, quick: bool = False) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.shot = shot
        self.origin = shot.logical_geometry.topLeft()
        self.context = _ShotContext(shot, self.origin)
        self.preview_cb = preview_cb
        self.quick = quick

        self.selection = QRect()
        self.anchor = QPoint()
        self.press_pos = QPoint()
        self.mode: str | None = None   # drag / move / resize / annotate / shape
        self.resize_handle: str | None = None
        self.settled = False
        self._emitted = False

        self.layer = annotate.Layer()
        self.style = annotate.Style()
        self.tool: str | None = None
        self.pending = None            # 正在拖曳中的圖形
        self.selected_shape = None     # 已完成、被點選中的圖形
        self.text_edit: QLineEdit | None = None
        self.color_format = annotate.COLOR_FORMATS[0]
        self.flash = ""                # 短暫提示訊息（例如已複製色碼）

        self.setGeometry(shot.logical_geometry)
        self.window_groups = self._logical_window_groups()
        self.hover_rect: QRect | None = None

        self.toolbar = Toolbar(self)
        self.toolbar.hide()
        self._wire_toolbar()

    def _wire_toolbar(self) -> None:
        for key in ("save", "copy", "pin", "saveas"):
            self.toolbar.buttons[key].clicked.connect(
                lambda _=False, action=key: self._emit(action)
            )
        self.toolbar.buttons["cancel"].clicked.connect(self.cancel)
        for key, button in self.toolbar.tool_buttons.items():
            button.clicked.connect(lambda _=False, tool=key: self.set_tool(tool))
        for color, button in self.toolbar.color_buttons.items():
            button.clicked.connect(lambda _=False, value=color: self.set_color(value))
        for width, button in self.toolbar.width_buttons.items():
            button.clicked.connect(lambda _=False, value=width: self.set_width(value))
        self.toolbar.fill_button.clicked.connect(self.toggle_fill)
        self.toolbar.custom_button.clicked.connect(self.pick_custom_color)
        self.toolbar.undo_button.clicked.connect(self.undo)
        self.toolbar.clear_button.clicked.connect(self.clear_annotations)

    # --- 起手式 ---------------------------------------------------
    def start(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._update_hover(self._cursor_pos())

    def _cursor_pos(self) -> QPoint:
        return self.mapFromGlobal(QCursor.pos())

    def _logical_window_groups(self) -> list[list[QRect]]:
        """每個可見視窗一組：第一個是視窗本身，後面是它的子區塊。"""
        groups: list[list[QRect]] = []
        for window in winrects.list_window_groups():
            converted = []
            for left, top, right, bottom in window:
                rect = self.shot.physical_rect_to_logical(left, top, right, bottom)
                rect = rect.translated(-self.origin).intersected(self.rect())
                if rect.width() > 8 and rect.height() > 8:
                    converted.append(rect)
            if converted:
                groups.append(converted)
        return groups

    def _to_global(self, rect: QRect) -> QRect:
        return rect.translated(self.origin)

    # --- 標註設定 -------------------------------------------------
    def set_tool(self, tool: str | None) -> None:
        self._commit_text()
        self.tool = None if tool == self.tool else tool
        self.selected_shape = None
        self.toolbar.sync(self.tool, self.style)
        self.setCursor(Qt.CrossCursor if self.tool else Qt.ArrowCursor)
        self.update()

    def set_color(self, color: str) -> None:
        self.style.color = color
        self._apply_to_selected(lambda s: setattr(s.style, "color", color))
        self.toolbar.sync(self.tool, self.style)
        self.update()

    def set_width(self, width: int) -> None:
        self.style.width = width
        self._apply_to_selected(lambda s: setattr(s.style, "width", width))
        self.toolbar.sync(self.tool, self.style)
        self.update()

    def toggle_fill(self) -> None:
        self.style.filled = not self.style.filled
        self._apply_to_selected(
            lambda s: setattr(s.style, "filled", self.style.filled))
        self.toolbar.sync(self.tool, self.style)
        self.update()

    def pick_custom_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.style.color), self, "選擇顏色")
        if chosen.isValid():
            self.set_color(chosen.name())

    def _apply_to_selected(self, action) -> None:
        if self.selected_shape is not None:
            action(self.selected_shape)

    def undo(self) -> None:
        if self.layer.undo():
            self.selected_shape = None
            self.update()

    def redo(self) -> None:
        if self.layer.redo():
            self.update()

    def clear_annotations(self) -> None:
        if self.layer.clear():
            self.selected_shape = None
            self.update()

    def delete_selected(self) -> None:
        if self.selected_shape is not None and self.layer.remove(self.selected_shape):
            self.selected_shape = None
            self.update()

    # --- 取色 -----------------------------------------------------
    def copy_color(self) -> None:
        color = self.shot.color_at(self._cursor_pos() + self.origin)
        text = annotate.format_color(color, self.color_format)
        QGuiApplication.clipboard().setText(text)
        self.flash = f"已複製 {text}"
        self.update()

    def cycle_color_format(self) -> None:
        formats = annotate.COLOR_FORMATS
        index = formats.index(self.color_format)
        self.color_format = formats[(index + 1) % len(formats)]
        self.update()

    # --- 繪製 -----------------------------------------------------
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        self.shot.paint(painter, self.origin)

        selection = self.selection.normalized()
        has_selection = selection.isValid() and not selection.isEmpty()
        region = QRegion(self.rect())
        if has_selection:
            region = region - QRegion(selection)
        painter.save()
        painter.setClipRegion(region)
        painter.fillRect(self.rect(), DIM)
        painter.restore()

        if has_selection:
            painter.save()
            painter.setClipRect(selection)
            painter.setRenderHint(QPainter.Antialiasing, True)
            self.layer.draw(painter, self.context, self.pending)
            painter.restore()
            self._paint_selected_marker(painter)
            self._paint_selection(painter, selection)
        elif self.hover_rect is not None:
            painter.setPen(QPen(ACCENT, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.hover_rect.adjusted(0, 0, -1, -1))
            self._paint_hint(painter)

        if not self.settled:
            self._paint_magnifier(painter)

    def _paint_selected_marker(self, painter: QPainter) -> None:
        if self.selected_shape is None:
            return
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(255, 255, 255, 200), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.selected_shape.bounds())

    def _paint_selection(self, painter: QPainter, selection: QRect) -> None:
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(ACCENT, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(selection.adjusted(0, 0, -1, -1))

        if self.settled:
            painter.setBrush(ACCENT)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            for rect in self._handles(selection).values():
                painter.drawRect(rect)

        dpr = self.shot.dpr_for(self._to_global(selection))
        width = round(selection.width() * dpr)
        height = round(selection.height() * dpr)
        text = f"{width} × {height}"
        if self.flash:
            text = f"{text}　{self.flash}"
        self._draw_label(painter, text, selection.topLeft() + QPoint(0, -26))

    def _paint_hint(self, painter: QPainter) -> None:
        text = "拖曳框選　點擊選取視窗　方向鍵微調　C 複製色碼　Ctrl+A 全螢幕　Esc 取消"
        metrics = QFontMetrics(self._label_font())
        position = QPoint(
            self.rect().center().x() - metrics.horizontalAdvance(text) // 2,
            self.rect().top() + 40,
        )
        self._draw_label(painter, text, position)

    def _label_font(self) -> QFont:
        font = QFont()
        font.setPointSize(9)
        return font

    def _draw_label(self, painter: QPainter, text: str, top_left: QPoint) -> None:
        font = self._label_font()
        metrics = QFontMetrics(font)
        box = QRect(top_left, QSize(metrics.horizontalAdvance(text) + 12,
                                    metrics.height() + 6))
        bounds = self.rect()
        if box.top() < bounds.top():
            box.moveTop(bounds.top() + 2)
        if box.right() > bounds.right():
            box.moveRight(bounds.right() - 2)
        if box.left() < bounds.left():
            box.moveLeft(bounds.left() + 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(25, 27, 31, 220))
        painter.drawRoundedRect(box, 3, 3)
        painter.setPen(QColor(235, 238, 242))
        painter.setFont(font)
        painter.drawText(box, Qt.AlignCenter, text)

    def _paint_magnifier(self, painter: QPainter) -> None:
        cursor = self._cursor_pos()
        if not self.rect().contains(cursor):
            return
        center = self.shot.to_image_point(cursor + self.origin)
        half = MAG_SRC_PX // 2
        source = QRect(center.x() - half, center.y() - half, MAG_SRC_PX, MAG_SRC_PX)

        box = QRect(cursor + QPoint(18, 18), QSize(MAG_BOX, MAG_BOX + 48))
        if box.right() > self.rect().right():
            box.moveLeft(cursor.x() - 18 - box.width())
        if box.bottom() > self.rect().bottom():
            box.moveTop(cursor.y() - 18 - box.height())

        view = QRect(box.x(), box.y(), MAG_BOX, MAG_BOX)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 22, 26, 235))
        painter.drawRoundedRect(box, 4, 4)
        painter.drawImage(view, self.shot.image, source)

        painter.setPen(QPen(ACCENT, 1))
        painter.drawLine(view.center().x(), view.top(), view.center().x(), view.bottom())
        painter.drawLine(view.left(), view.center().y(), view.right(), view.center().y())
        painter.setPen(QPen(QColor(90, 95, 105), 1))
        painter.drawRect(view.adjusted(0, 0, -1, -1))

        global_pos = cursor + self.origin
        color = self.shot.color_at(global_pos)
        swatch = QRect(box.x() + 6, view.bottom() + 6, 12, 12)
        painter.setPen(QPen(QColor(120, 126, 138), 1))
        painter.setBrush(color)
        painter.drawRect(swatch)
        info = (f"({global_pos.x()}, {global_pos.y()})\n"
                f"{annotate.format_color(color, self.color_format)}　"
                f"C 複製 · Shift 換格式")
        painter.setPen(QColor(226, 230, 236))
        painter.setFont(self._label_font())
        painter.drawText(QRect(box.x() + 22, view.bottom() + 2, MAG_BOX - 26, 44),
                         Qt.AlignLeft | Qt.AlignVCenter, info)

    # --- 選取控制 -------------------------------------------------
    def _handles(self, selection: QRect) -> dict[str, QRect]:
        size = HANDLE_SIZE
        x0, y0 = selection.left(), selection.top()
        x1, y1 = selection.right(), selection.bottom()
        xm, ym = selection.center().x(), selection.center().y()
        points = {
            "tl": (x0, y0), "t": (xm, y0), "tr": (x1, y0),
            "l": (x0, ym), "r": (x1, ym),
            "bl": (x0, y1), "b": (xm, y1), "br": (x1, y1),
        }
        return {
            name: QRect(x - size // 2, y - size // 2, size, size)
            for name, (x, y) in points.items()
        }

    def _handle_at(self, pos: QPoint) -> str | None:
        if not self.settled or self.selection.isEmpty():
            return None
        for name, rect in self._handles(self.selection.normalized()).items():
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                return name
        return None

    def _update_hover(self, pos: QPoint) -> None:
        """取最上層那個視窗，再從它的子區塊裡挑面積最小的。"""
        for group in self.window_groups:
            if not group[0].contains(pos):
                continue
            inside = [rect for rect in group if rect.contains(pos)]
            self.hover_rect = min(inside, key=lambda r: r.width() * r.height())
            return
        self.hover_rect = None

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        self.press_pos = pos
        self.flash = ""
        self._commit_text()

        handle = self._handle_at(pos)
        if handle:
            self.mode, self.resize_handle = "resize", handle
        elif self.settled and self.tool and self.selection.contains(pos):
            self._begin_annotation(pos)
        elif self.settled and self.selection.contains(pos):
            shape = self.layer.shape_at(pos)
            if shape is not None:
                self.selected_shape = shape
                self.mode = "shape"
                self.anchor = pos
                self.toolbar.sync(self.tool, shape.style)
            else:
                self.selected_shape = None
                self.mode = "move"
                self.anchor = pos - self.selection.normalized().topLeft()
        else:
            self.selected_shape = None
            self.mode = "drag"
            self.settled = False
            self.anchor = pos
            self.selection = QRect(pos, pos)
            self.toolbar.hide()
        self.update()

    def _begin_annotation(self, pos: QPoint) -> None:
        if self.tool == "text":
            self._open_text_editor(pos)
            return
        if self.tool == "number":
            self.layer.add(annotate.NumberShape(pos, self.layer.next_number(),
                                                self.style.copy()))
            self.update()
            return
        self.mode = "annotate"
        self.pending = annotate.make_shape(self.tool, pos, pos, self.style)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        if self.mode == "annotate":
            self._extend_annotation(pos)
        elif self.mode == "shape":
            if self.selected_shape is not None:
                self.selected_shape.translate(pos - self.anchor)
                self.anchor = pos
        elif self.mode == "drag":
            self.selection = QRect(self.anchor, pos).normalized()
        elif self.mode == "move":
            self._move_selection_to(pos - self.anchor)
        elif self.mode == "resize":
            self._resize_to(pos)
            self._place_toolbar()
        else:
            if not self.settled:
                self._update_hover(pos)
            self.setCursor(self._cursor_for(pos))
        self.update()

    def _move_selection_to(self, top_left: QPoint) -> None:
        selection = self.selection.normalized()
        selection.moveTopLeft(top_left)
        bounds = self.rect()
        selection.moveLeft(max(bounds.left(),
                               min(selection.left(),
                                   bounds.right() - selection.width())))
        selection.moveTop(max(bounds.top(),
                              min(selection.top(),
                                  bounds.bottom() - selection.height())))
        self.selection = selection
        self._place_toolbar()

    def _extend_annotation(self, pos: QPoint) -> None:
        if self.pending is None:
            return
        if hasattr(self.pending, "points"):
            self.pending.points.append(pos)
        else:
            self.pending.end = pos

    def _cursor_for(self, pos: QPoint) -> Qt.CursorShape:
        handle = self._handle_at(pos)
        if handle:
            return {
                "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
                "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
                "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
                "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
            }[handle]
        if self.settled and self.selection.normalized().contains(pos):
            if self.tool == "text":
                return Qt.IBeamCursor
            if self.tool:
                return Qt.CrossCursor
            if self.layer.shape_at(pos) is not None:
                return Qt.OpenHandCursor
            return Qt.SizeAllCursor
        return Qt.CrossCursor

    def _resize_to(self, pos: QPoint) -> None:
        selection = self.selection.normalized()
        handle = self.resize_handle or ""
        if "l" in handle:
            selection.setLeft(min(pos.x(), selection.right() - MIN_SELECTION))
        if "r" in handle:
            selection.setRight(max(pos.x(), selection.left() + MIN_SELECTION))
        if "t" in handle:
            selection.setTop(min(pos.y(), selection.bottom() - MIN_SELECTION))
        if "b" in handle:
            selection.setBottom(max(pos.y(), selection.top() + MIN_SELECTION))
        self.selection = selection.intersected(self.rect())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()

        if self.mode == "annotate":
            self._finish_annotation()
            self.update()
            return
        if self.mode == "shape":
            self.mode = None
            self.update()
            return

        if self.mode == "drag" and (pos - self.press_pos).manhattanLength() < 6:
            self._update_hover(pos)
            self.selection = QRect(self.hover_rect) if self.hover_rect else QRect()
        self.mode = None

        selection = self.selection.normalized()
        if selection.width() < MIN_SELECTION or selection.height() < MIN_SELECTION:
            self.selection = QRect()
            self.settled = False
            self.toolbar.hide()
            self.update()
            return

        self.selection = selection
        self.settled = True
        if self.quick:
            self._emit("save")
            return
        self._show_toolbar()
        self.update()

    def _finish_annotation(self) -> None:
        self.mode = None
        shape = self.pending
        self.pending = None
        if shape is None:
            return
        if hasattr(shape, "points"):
            if len(shape.points) > 1:
                self.layer.add(shape)
            return
        if (shape.end - shape.start).manhattanLength() >= 4:
            self.layer.add(shape)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.tool:
            return
        pos = event.position().toPoint()
        if self.settled and self.layer.shape_at(pos) is not None:
            return
        if self.settled and self.selection.normalized().contains(pos):
            self._emit("save")

    # --- 文字工具 -------------------------------------------------
    def _open_text_editor(self, pos: QPoint) -> None:
        self._commit_text()
        editor = QLineEdit(self)
        editor.setObjectName("inline")
        editor.setStyleSheet(TOOLBAR_QSS)
        shape = annotate.TextShape(pos, "", self.style.copy())
        editor.setFont(shape.font())
        editor.setMinimumWidth(160)
        editor.move(pos)
        editor.setProperty("anchor", pos)
        editor.returnPressed.connect(self._commit_text)
        editor.show()
        editor.setFocus()
        self.text_edit = editor

    def _commit_text(self) -> None:
        editor = self.text_edit
        if editor is None:
            return
        self.text_edit = None
        text = editor.text().strip()
        anchor = editor.property("anchor") or editor.pos()
        editor.deleteLater()
        if text:
            self.layer.add(annotate.TextShape(anchor, text, self.style.copy()))
        self.setFocus()
        self.update()

    # --- 工具列 ---------------------------------------------------
    def _show_toolbar(self) -> None:
        try:
            self.toolbar.set_name(self.preview_cb())
        except Exception:
            self.toolbar.set_name("?")
        self.toolbar.sync(self.tool, self.style)
        # 窄螢幕上不讓工具列超出畫面，寧可讓按鈕擠一點
        self.toolbar.setMaximumWidth(max(320, self.width() - 16))
        self.toolbar.show()
        self.toolbar.adjustSize()
        self.toolbar.raise_()
        self._place_toolbar()

    def _place_toolbar(self) -> None:
        if self.toolbar.isHidden():
            return
        selection = self.selection.normalized()
        size = self.toolbar.size()
        bounds = self.rect()
        x = min(max(bounds.left() + 4, selection.right() - size.width()),
                max(bounds.left() + 4, bounds.right() - size.width() - 4))
        y = selection.bottom() + 8
        if y + size.height() > bounds.bottom():
            y = selection.top() - size.height() - 8
        if y < bounds.top():
            y = min(selection.top() + 8, bounds.bottom() - size.height() - 4)
        self.toolbar.move(x, y)

    # --- 鍵盤 -----------------------------------------------------
    def keyPressEvent(self, event) -> None:
        key, mods = event.key(), event.modifiers()

        if key == Qt.Key_Escape:
            self._handle_escape()
            return
        if key == Qt.Key_Shift:
            self.cycle_color_format()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._emit("save")
            return
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected_shape is not None:
            self.delete_selected()
            return
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self._handle_arrow(key, mods)
            return

        if mods & Qt.ControlModifier:
            if key == Qt.Key_C:
                self._emit("copy")
            elif key == Qt.Key_S:
                self._emit("saveas")
            elif key == Qt.Key_Z:
                self.redo() if mods & Qt.ShiftModifier else self.undo()
            elif key == Qt.Key_Y:
                self.redo()
            elif key == Qt.Key_A:
                self.selection = QRect(self.rect())
                self.settled = True
                self._show_toolbar()
                self.update()
            return

        if mods:
            super().keyPressEvent(event)
            return

        if self.settled:
            for tool, _label, shortcut in annotate.TOOL_LABELS:
                if key == getattr(Qt, f"Key_{shortcut}"):
                    self.set_tool(tool)
                    return
        if key == Qt.Key_C:
            self.copy_color()
        elif key == Qt.Key_S:
            self._emit("save")
        elif key == Qt.Key_F:
            self._emit("pin")
        else:
            super().keyPressEvent(event)

    def _handle_escape(self) -> None:
        if self.text_edit is not None:
            editor, self.text_edit = self.text_edit, None
            editor.deleteLater()
            self.setFocus()
        elif self.selected_shape is not None:
            self.selected_shape = None
        elif self.tool:
            self.set_tool(None)
        else:
            self.cancel()
            return
        self.update()

    def _handle_arrow(self, key: int, mods) -> None:
        step = NUDGE_FAST if mods & Qt.AltModifier else NUDGE
        delta = {
            Qt.Key_Left: QPoint(-step, 0), Qt.Key_Right: QPoint(step, 0),
            Qt.Key_Up: QPoint(0, -step), Qt.Key_Down: QPoint(0, step),
        }[key]

        if self.selected_shape is not None:
            self.selected_shape.translate(delta)
        elif not self.settled:
            # 還沒框好：讓游標逐像素移動，配合放大鏡對齊
            QCursor.setPos(QCursor.pos() + delta)
            if self.mode == "drag":
                self.selection = QRect(self.anchor, self._cursor_pos()).normalized()
        elif mods & Qt.ControlModifier:
            self.selection = self.selection.normalized().adjusted(
                0, 0, delta.x(), delta.y()).intersected(self.rect())
            self._place_toolbar()
        elif mods & Qt.ShiftModifier:
            selection = self.selection.normalized().adjusted(
                0, 0, -abs(delta.x()), -abs(delta.y()))
            if selection.width() >= MIN_SELECTION and selection.height() >= MIN_SELECTION:
                self.selection = selection
                self._place_toolbar()
        else:
            self._move_selection_to(self.selection.normalized().topLeft() + delta)
        self.update()

    # --- 收尾 -----------------------------------------------------
    def render_result(self) -> QPixmap:
        """裁切 + 把標註畫上去，輸出為原生解析度。"""
        selection = self.selection.normalized().intersected(self.rect())
        pixmap = self.shot.crop(self._to_global(selection))
        if not len(self.layer):
            return pixmap

        dpr = pixmap.devicePixelRatio() or 1.0
        pixmap.setDevicePixelRatio(1.0)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.scale(dpr, dpr)
        painter.translate(-selection.topLeft())
        self.layer.draw(painter, self.context)
        painter.end()
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def _emit(self, action: str) -> None:
        self._commit_text()
        selection = self.selection.normalized()
        if selection.width() < MIN_SELECTION or selection.height() < MIN_SELECTION:
            return
        self._emitted = True
        pixmap = self.render_result()
        global_rect = self._to_global(selection)
        self.close()
        self.finished.emit(pixmap, action, global_rect)

    def cancel(self) -> None:
        self._emitted = True
        self.close()
        self.cancelled.emit()

    def closeEvent(self, event) -> None:
        if not self._emitted:
            self._emitted = True
            self.cancelled.emit()
        super().closeEvent(event)
