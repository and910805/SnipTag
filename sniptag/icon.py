"""程式內畫出來的圖示，免去額外資源檔。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

ACCENT = "#2d7ff9"


def icon_pixmap(size: int = 256) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(QRectF(size * 0.05, size * 0.05, size * 0.9, size * 0.9),
                            size * 0.2, size * 0.2)

    # 白色的裁切框
    pen = QPen(QColor(255, 255, 255), max(2.0, size * 0.07))
    pen.setCapStyle(Qt.SquareCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    inner = QRectF(size * 0.27, size * 0.27, size * 0.46, size * 0.46)
    painter.drawRect(inner)
    painter.drawLine(int(size * 0.27), int(size * 0.13), int(size * 0.27), int(size * 0.87))
    painter.drawLine(int(size * 0.73), int(size * 0.13), int(size * 0.73), int(size * 0.87))
    painter.drawLine(int(size * 0.13), int(size * 0.27), int(size * 0.87), int(size * 0.27))
    painter.drawLine(int(size * 0.13), int(size * 0.73), int(size * 0.87), int(size * 0.73))
    painter.end()
    return pixmap


def app_icon(size: int = 128) -> QIcon:
    return QIcon(icon_pixmap(size))


def write_ico(path) -> bool:
    """輸出多尺寸 .ico，給 PyInstaller 當 exe 圖示用。"""
    image = icon_pixmap(256).toImage()
    return image.save(str(path), "ICO")
