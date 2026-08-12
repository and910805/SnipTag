"""全螢幕框選介面：暗化背景、拖曳選取、視窗自動偵測、放大鏡、動作工具列。

所有換算都交給 DesktopShot 逐螢幕處理，因此混合 DPI（筆電 + 外接螢幕）
不需要任何設定，接上就對。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QCursor, QFont, QFontMetrics, QPainter, QPen, QPixmap, QRegion,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from . import winrects
from .screens import DesktopShot

ACCENT = QColor("#2d7ff9")
DIM = QColor(0, 0, 0, 120)
HANDLE_SIZE = 8
MIN_SELECTION = 3
MAG_BOX = 132          # 放大鏡邊長（邏輯像素）
MAG_SRC_PX = 22        # 放大鏡取樣的原始像素數

TOOLBAR_QSS = """
QWidget#toolbar { background: #23262b; border: 1px solid #3a3f47; border-radius: 6px; }
QPushButton {
    background: #2f343b; color: #e8eaed; border: none; border-radius: 4px;
    padding: 5px 11px; font-size: 12px;
}
QPushButton:hover { background: #3d434c; }
QPushButton#primary { background: #2d7ff9; color: white; font-weight: bold; }
QPushButton#primary:hover { background: #4a92fb; }
QLabel#name { color: #9fd18a; font-size: 12px; padding: 0 8px; }
"""


class Toolbar(QWidget):
    """選取完成後浮出來的動作列。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar")
        self.setStyleSheet(TOOLBAR_QSS)
        self.setCursor(Qt.ArrowCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("name")
        layout.addWidget(self.name_label)

        self.buttons: dict[str, QPushButton] = {}
        for key, text, primary in (
            ("save", "存檔  ⏎", True),
            ("copy", "複製  Ctrl+C", False),
            ("pin", "釘選  F", False),
            ("saveas", "另存…  Ctrl+S", False),
            ("cancel", "取消  Esc", False),
        ):
            button = QPushButton(text, self)
            button.setFocusPolicy(Qt.NoFocus)
            button.setCursor(Qt.PointingHandCursor)
            if primary:
                button.setObjectName("primary")
            layout.addWidget(button)
            self.buttons[key] = button
        self.adjustSize()

    def set_name(self, name: str) -> None:
        self.name_label.setText(f"→ {name}")
        self.adjustSize()


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
        self.preview_cb = preview_cb
        self.quick = quick

        self.selection = QRect()
        self.anchor = QPoint()
        self.press_pos = QPoint()
        self.mode: str | None = None      # drag / move / resize
        self.resize_handle: str | None = None
        self.settled = False
        self._emitted = False

        self.setGeometry(shot.logical_geometry)
        self.window_rects = self._logical_window_rects()
        self.hover_rect: QRect | None = None

        self.toolbar = Toolbar(self)
        self.toolbar.hide()
        self.toolbar.buttons["save"].clicked.connect(lambda: self._emit("save"))
        self.toolbar.buttons["copy"].clicked.connect(lambda: self._emit("copy"))
        self.toolbar.buttons["pin"].clicked.connect(lambda: self._emit("pin"))
        self.toolbar.buttons["saveas"].clicked.connect(lambda: self._emit("saveas"))
        self.toolbar.buttons["cancel"].clicked.connect(self.cancel)

    # --- 起手式 ---------------------------------------------------
    def start(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._update_hover(self._cursor_pos())

    def _cursor_pos(self) -> QPoint:
        """游標在本視窗座標系的位置（產生說明用截圖時會被覆寫成固定值）。"""
        return self.mapFromGlobal(QCursor.pos())

    def _logical_window_rects(self) -> list[QRect]:
        """視窗的實體座標 → 本視窗的座標系（每台螢幕各自換算）。"""
        rects = []
        for left, top, right, bottom in winrects.list_window_rects():
            rect = self.shot.physical_rect_to_logical(left, top, right, bottom)
            rect = rect.translated(-self.origin).intersected(self.rect())
            if rect.width() > 8 and rect.height() > 8:
                rects.append(rect)
        return rects

    def _to_global(self, rect: QRect) -> QRect:
        return rect.translated(self.origin)

    # --- 繪製 -----------------------------------------------------
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        self.shot.paint(painter, self.origin)

        selection = self.selection.normalized()
        if selection.isValid() and not selection.isEmpty():
            region = QRegion(self.rect()) - QRegion(selection)
        else:
            region = QRegion(self.rect())
        painter.save()
        painter.setClipRegion(region)
        painter.fillRect(self.rect(), DIM)
        painter.restore()

        if selection.isValid() and not selection.isEmpty():
            self._paint_selection(painter, selection)
        elif self.hover_rect is not None:
            painter.setPen(QPen(ACCENT, 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.hover_rect.adjusted(0, 0, -1, -1))
            self._paint_hint(painter)

        if not self.settled:
            self._paint_magnifier(painter)

    def _paint_selection(self, painter: QPainter, selection: QRect) -> None:
        painter.setPen(QPen(ACCENT, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(selection.adjusted(0, 0, -1, -1))

        if self.settled:
            painter.setBrush(ACCENT)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            for rect in self._handles(selection).values():
                painter.drawRect(rect)

        # 尺寸標籤顯示實際會存下來的像素數
        dpr = self.shot.dpr_for(self._to_global(selection))
        width = round(selection.width() * dpr)
        height = round(selection.height() * dpr)
        self._draw_label(painter, f"{width} × {height}",
                         selection.topLeft() + QPoint(0, -26))

    def _paint_hint(self, painter: QPainter) -> None:
        text = "拖曳框選　點擊選取視窗　Ctrl+A 全螢幕　Esc 取消"
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

        box = QRect(cursor + QPoint(18, 18), QSize(MAG_BOX, MAG_BOX + 34))
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
        info = f"({global_pos.x()}, {global_pos.y()})\n{color.name().upper()}"
        painter.setPen(QColor(226, 230, 236))
        painter.setFont(self._label_font())
        painter.drawText(QRect(box.x() + 6, view.bottom() + 2, MAG_BOX - 12, 32),
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
        self.hover_rect = next(
            (rect for rect in self.window_rects if rect.contains(pos)), None
        )

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        self.press_pos = pos
        handle = self._handle_at(pos)
        if handle:
            self.mode, self.resize_handle = "resize", handle
        elif self.settled and self.selection.normalized().contains(pos):
            self.mode = "move"
            self.anchor = pos - self.selection.normalized().topLeft()
        else:
            self.mode = "drag"
            self.settled = False
            self.anchor = pos
            self.selection = QRect(pos, pos)
            self.toolbar.hide()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        if self.mode == "drag":
            self.selection = QRect(self.anchor, pos).normalized()
        elif self.mode == "move":
            selection = self.selection.normalized()
            selection.moveTopLeft(pos - self.anchor)
            bounds = self.rect()
            selection.moveLeft(max(bounds.left(),
                                   min(selection.left(),
                                       bounds.right() - selection.width())))
            selection.moveTop(max(bounds.top(),
                                  min(selection.top(),
                                      bounds.bottom() - selection.height())))
            self.selection = selection
            self._place_toolbar()
        elif self.mode == "resize":
            self._resize_to(pos)
            self._place_toolbar()
        else:
            self._update_hover(pos)
            self.setCursor(self._cursor_for(pos))
        self.update()

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
        if self.mode == "drag" and (pos - self.press_pos).manhattanLength() < 6:
            # 沒拖曳 = 選取游標底下的視窗
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

    def mouseDoubleClickEvent(self, event) -> None:
        if self.settled and self.selection.normalized().contains(
            event.position().toPoint()
        ):
            self._emit("save")

    # --- 工具列 ---------------------------------------------------
    def _show_toolbar(self) -> None:
        try:
            self.toolbar.set_name(self.preview_cb())
        except Exception:
            self.toolbar.set_name("?")
        self.toolbar.show()
        self.toolbar.raise_()
        self._place_toolbar()

    def _place_toolbar(self) -> None:
        if self.toolbar.isHidden():
            return
        selection = self.selection.normalized()
        size = self.toolbar.size()
        bounds = self.rect()
        x = min(max(bounds.left() + 4, selection.right() - size.width()),
                bounds.right() - size.width() - 4)
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
            self.cancel()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._emit("save")
        elif key == Qt.Key_C and mods & Qt.ControlModifier:
            self._emit("copy")
        elif key == Qt.Key_S and mods & Qt.ControlModifier:
            self._emit("saveas")
        elif key == Qt.Key_A and mods & Qt.ControlModifier:
            self.selection = QRect(self.rect())
            self.settled = True
            self._show_toolbar()
            self.update()
        elif key in (Qt.Key_S, Qt.Key_F) and not mods:
            self._emit("save" if key == Qt.Key_S else "pin")
        else:
            super().keyPressEvent(event)

    # --- 收尾 -----------------------------------------------------
    def crop(self) -> QPixmap:
        selection = self.selection.normalized().intersected(self.rect())
        return self.shot.crop(self._to_global(selection))

    def _emit(self, action: str) -> None:
        selection = self.selection.normalized()
        if selection.width() < MIN_SELECTION or selection.height() < MIN_SELECTION:
            return
        self._emitted = True
        pixmap = self.crop()
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
