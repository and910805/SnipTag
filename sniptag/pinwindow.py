"""釘圖視窗：把截圖釘在桌面最上層，可拖曳、縮放、調透明度。"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

MIN_SCALE = 0.1
MAX_SCALE = 8.0
MIN_OPACITY = 0.2


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

        self.app = app
        self.source = pixmap
        self.scale = 1.0
        self._drag_offset: QPoint | None = None

        self._apply_size()
        self.move(position)

    # --- 外觀 -----------------------------------------------------
    def _logical_size(self):
        dpr = self.source.devicePixelRatio() or 1.0
        return (max(1, round(self.source.width() / dpr * self.scale)),
                max(1, round(self.source.height() / dpr * self.scale)))

    def _apply_size(self) -> None:
        width, height = self._logical_size()
        self.setFixedSize(width, height)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.scale < 1.0)
        painter.drawPixmap(self.rect(), self.source)
        painter.setPen(QPen(QColor(45, 127, 249, 200), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    # --- 互動 -----------------------------------------------------
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
        center = self.geometry().center()
        self.scale = max(MIN_SCALE, min(MAX_SCALE, self.scale * (1.1 ** steps)))
        self._apply_size()
        new_geo = QRect(self.pos(), self.size())
        new_geo.moveCenter(center)
        self.move(new_geo.topLeft())
        self.update()

    def keyPressEvent(self, event) -> None:
        key, mods = event.key(), event.modifiers()
        if key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_C and mods & Qt.ControlModifier:
            self.app.copy_to_clipboard(self.source)
        elif key == Qt.Key_S and mods & Qt.ControlModifier:
            self.app.save_pixmap(self.source)
        elif key == Qt.Key_0 and mods & Qt.ControlModifier:
            self.scale = 1.0
            self._apply_size()
            self.update()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        actions = [
            ("存檔（自動命名）", lambda: self.app.save_pixmap(self.source)),
            ("另存新檔…", lambda: self.app.save_pixmap_as(self.source)),
            ("複製到剪貼簿", lambda: self.app.copy_to_clipboard(self.source)),
            ("原始大小", self._reset_scale),
            ("關閉", self.close),
        ]
        for text, slot in actions:
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        menu.exec(event.globalPos())

    def _reset_scale(self) -> None:
        self.scale = 1.0
        self.setWindowOpacity(1.0)
        self._apply_size()
        self.update()

    def closeEvent(self, event) -> None:
        self.app.forget_pin(self)
        super().closeEvent(event)
