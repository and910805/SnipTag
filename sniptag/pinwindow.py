"""釘圖視窗：把截圖釘在桌面最上層，可拖曳、縮放、旋轉、調透明度、滑鼠穿透。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (
    QAction, QColor, QGuiApplication, QPainter, QPen, QPixmap, QTransform,
)
from PySide6.QtWidgets import QMenu, QWidget

MIN_SCALE = 0.1
MAX_SCALE = 8.0
MIN_OPACITY = 0.2
ZOOM_STEP = 1.1


class PinWindow(QWidget):
    """一張浮在桌面上的圖。關閉時會從 app 的清單裡移除。"""

    def __init__(self, pixmap: QPixmap, position: QPoint, app) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("SnipTag Pin")
        self.setFocusPolicy(Qt.StrongFocus)

        self.app = app
        self.original = pixmap
        self.source = pixmap
        self.scale = 1.0
        self.rotation = 0
        self.click_through = False
        self._drag_offset: QPoint | None = None

        self._apply_size()
        self.move(position)

    # --- 外觀 -----------------------------------------------------
    def _rebuild_source(self) -> None:
        if self.rotation % 360 == 0:
            self.source = self.original
            return
        transform = QTransform().rotate(self.rotation)
        self.source = self.original.transformed(transform, Qt.SmoothTransformation)
        self.source.setDevicePixelRatio(self.original.devicePixelRatio())

    def _logical_size(self) -> tuple[int, int]:
        dpr = self.source.devicePixelRatio() or 1.0
        return (max(1, round(self.source.width() / dpr * self.scale)),
                max(1, round(self.source.height() / dpr * self.scale)))

    def _apply_size(self) -> None:
        width, height = self._logical_size()
        self.setFixedSize(width, height)

    def _resize_around_center(self) -> None:
        center = self.geometry().center()
        self._apply_size()
        geometry = QRect(self.pos(), self.size())
        geometry.moveCenter(center)
        self.move(geometry.topLeft())
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.scale < 1.0)
        painter.drawPixmap(self.rect(), self.source)
        color = QColor(45, 127, 249, 200)
        if self.click_through:
            color = QColor(255, 176, 32, 220)   # 穿透中：換個顏色提示
        painter.setPen(QPen(color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    # --- 操作 -----------------------------------------------------
    def zoom(self, factor: float) -> None:
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * factor))
        self._resize_around_center()

    def rotate(self, degrees: int) -> None:
        self.rotation = (self.rotation + degrees) % 360
        self._rebuild_source()
        self._resize_around_center()

    def set_click_through(self, enabled: bool) -> None:
        """滑鼠穿透：圖還在最上層，但點擊會穿到底下的視窗。"""
        self.click_through = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
        self.show()
        self.update()

    def toggle_click_through(self) -> None:
        self.set_click_through(not self.click_through)

    def reset(self) -> None:
        self.scale = 1.0
        self.rotation = 0
        self.setWindowOpacity(1.0)
        self._rebuild_source()
        self._resize_around_center()

    def copy_color_at(self, pos: QPoint) -> None:
        image = self.source.toImage()
        dpr = self.source.devicePixelRatio() or 1.0
        x = round(pos.x() / self.scale * dpr)
        y = round(pos.y() / self.scale * dpr)
        if not image.rect().contains(x, y):
            return
        QGuiApplication.clipboard().setText(image.pixelColor(x, y).name().upper())

    # --- 滑鼠 -----------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
        elif event.button() == Qt.MiddleButton:
            self.close()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_offset = None

    def mouseDoubleClickEvent(self, _event) -> None:
        self.close()

    def wheelEvent(self, event) -> None:
        steps = event.angleDelta().y() / 120.0
        if event.modifiers() & Qt.ControlModifier:
            self.setWindowOpacity(
                max(MIN_OPACITY, min(1.0, self.windowOpacity() + steps * 0.08))
            )
            return
        self.zoom(ZOOM_STEP ** steps)

    # --- 鍵盤 -----------------------------------------------------
    def keyPressEvent(self, event) -> None:
        key, mods = event.key(), event.modifiers()
        if key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_C and mods & Qt.ControlModifier:
            self.app.copy_to_clipboard(self.source)
        elif key == Qt.Key_C and mods & Qt.AltModifier:
            self.copy_color_at(self.mapFromGlobal(self.cursor().pos()))
        elif key == Qt.Key_S and mods & Qt.ControlModifier:
            self.app.save_pixmap(self.source)
        elif key == Qt.Key_0 and mods & Qt.ControlModifier:
            self.reset()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(ZOOM_STEP)
        elif key == Qt.Key_Minus:
            self.zoom(1 / ZOOM_STEP)
        elif key == Qt.Key_1:
            self.rotate(-90)
        elif key == Qt.Key_2:
            self.rotate(90)
        elif key == Qt.Key_X:
            self.toggle_click_through()
        else:
            super().keyPressEvent(event)

    # --- 選單 -----------------------------------------------------
    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        entries = [
            ("存檔（自動命名）", lambda: self.app.save_pixmap(self.source)),
            ("另存新檔…", lambda: self.app.save_pixmap_as(self.source)),
            ("複製到剪貼簿", lambda: self.app.copy_to_clipboard(self.source)),
            None,
            ("向左旋轉  1", lambda: self.rotate(-90)),
            ("向右旋轉  2", lambda: self.rotate(90)),
            ("放大  +", lambda: self.zoom(ZOOM_STEP)),
            ("縮小  -", lambda: self.zoom(1 / ZOOM_STEP)),
            ("還原  Ctrl+0", self.reset),
            None,
            ("滑鼠穿透  X", self.toggle_click_through),
            ("關閉", self.close),
        ]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
                continue
            text, slot = entry
            action = QAction(text, menu)
            if text.startswith("滑鼠穿透"):
                action.setCheckable(True)
                action.setChecked(self.click_through)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:
        self.app.forget_pin(self)
        super().closeEvent(event)
