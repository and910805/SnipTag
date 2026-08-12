"""截圖歷史：保留最近的幾張，可以重新存檔、複製、釘選。

只放在記憶體裡，程式關掉就沒了 —— 歷史是為了「剛剛那張手滑關掉了」，
不是備份機制。
"""
from __future__ import annotations

import datetime as _dt
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

LIMIT = 30
THUMB = QSize(168, 112)


@dataclass
class Entry:
    pixmap: QPixmap
    taken_at: _dt.datetime
    name: str = ""          # 已存檔的話記下檔名

    def label(self) -> str:
        return self.name or self.taken_at.strftime("%H:%M:%S")

    def detail(self) -> str:
        stamp = self.taken_at.strftime("%H:%M:%S")
        return f"{self.name or '（未存檔）'}\n{stamp}\n" \
               f"{self.pixmap.width()} × {self.pixmap.height()}"


def thumbnail(pixmap: QPixmap) -> QPixmap:
    """統一成同樣大小的縮圖，長寬比不同的截圖排起來才整齊。"""
    source = QPixmap(pixmap)
    source.setDevicePixelRatio(1.0)
    scaled = source.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QPixmap(THUMB)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    left = (THUMB.width() - scaled.width()) // 2
    top = (THUMB.height() - scaled.height()) // 2
    painter.drawPixmap(left, top, scaled)
    painter.setPen(QPen(QColor(120, 126, 138), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(left, top, max(1, scaled.width() - 1), max(1, scaled.height() - 1))
    painter.end()
    return canvas


class History:
    def __init__(self, limit: int = LIMIT) -> None:
        self.entries: deque[Entry] = deque(maxlen=limit)

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, pixmap: QPixmap, name: str = "") -> Entry:
        entry = Entry(QPixmap(pixmap), _dt.datetime.now(), name)
        self.entries.append(entry)
        return entry

    def latest(self) -> Entry | None:
        return self.entries[-1] if self.entries else None

    def remove(self, entry: Entry) -> None:
        try:
            self.entries.remove(entry)
        except ValueError:
            pass

    def clear(self) -> None:
        self.entries.clear()


class HistoryDialog(QDialog):
    """瀏覽歷史截圖，並對選中的那張做事。"""

    def __init__(self, history: History, app, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history
        self.app = app
        self.setWindowTitle("截圖歷史")
        self.setMinimumSize(640, 420)

        layout = QVBoxLayout(self)
        self.hint = QLabel(self)
        self.hint.setStyleSheet("color:#888;")
        layout.addWidget(self.hint)

        self.list = QListWidget(self)
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 20, THUMB.height() + 40))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(6)
        self.list.itemDoubleClicked.connect(lambda _item: self.pin_selected())
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        for text, slot in (
            ("釘選", self.pin_selected),
            ("存檔（自動命名）", self.save_selected),
            ("複製", self.copy_selected),
            ("刪除", self.delete_selected),
            ("全部清除", self.clear_all),
        ):
            button = QPushButton(text, self)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        close_box = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self.reload()

    # --- 內容 -----------------------------------------------------
    def reload(self) -> None:
        self.list.clear()
        for entry in reversed(self.history.entries):
            item = QListWidgetItem(QIcon(thumbnail(entry.pixmap)), entry.label())
            item.setData(Qt.UserRole, entry)
            item.setToolTip(entry.detail())
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.hint.setText(
            f"最近 {len(self.history)} 張（上限 {self.history.entries.maxlen} 張，"
            "只存在記憶體，關掉程式就清空）"
        )

    def selected(self) -> Entry | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    # --- 動作 -----------------------------------------------------
    def pin_selected(self) -> None:
        entry = self.selected()
        if entry:
            self.app.pin_centered(entry.pixmap)

    def save_selected(self) -> None:
        entry = self.selected()
        if not entry:
            return
        path = self.app.save_pixmap(entry.pixmap, record=False)
        if path:
            entry.name = path.name
            self.reload()

    def copy_selected(self) -> None:
        entry = self.selected()
        if entry:
            self.app.copy_to_clipboard(entry.pixmap)

    def delete_selected(self) -> None:
        entry = self.selected()
        if entry:
            self.history.remove(entry)
            self.reload()

    def clear_all(self) -> None:
        self.history.clear()
        self.reload()
