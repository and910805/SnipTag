"""第一次啟動的使用教學。

用幾張自己畫的示意圖把核心流程講完，而不是丟一長串文字。
之後可以從系統匣選單的「使用教學…」再打開。
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import autostart, toolicons

CARD = QRect(0, 0, 470, 190)
BRAND = "#2d7ff9"
INK = "#e8eaed"
MUTED = "#96a0ae"
PANEL = "#2b2f36"

QSS = """
QDialog { background: #23262b; }
QLabel#title { color: #ffffff; font-size: 17px; font-weight: bold; }
QLabel#body  { color: #c6ccd6; font-size: 13px; }
QLabel#step  { color: #7d8794; font-size: 12px; }
QCheckBox    { color: #c6ccd6; font-size: 12px; }
QPushButton {
    background: #2f343b; color: #e8eaed; border: none; border-radius: 4px;
    padding: 7px 16px; font-size: 13px;
}
QPushButton:hover { background: #3d434c; }
QPushButton:disabled { color: #6b7280; }
QPushButton#primary { background: #2d7ff9; color: white; font-weight: bold; }
QPushButton#primary:hover { background: #4a92fb; }
"""


def _font(size: int, bold: bool = False) -> QFont:
    font = QFont("Microsoft JhengHei UI")
    font.setPointSize(size)
    font.setBold(bold)
    return font


def _chip(painter: QPainter, rect: QRectF, text: str, fill: str,
          text_color: str = "#ffffff", size: int = 10) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(fill))
    painter.drawRoundedRect(rect, 5, 5)
    painter.setPen(QColor(text_color))
    painter.setFont(_font(size, bold=True))
    painter.drawText(rect, Qt.AlignCenter, text)


# --- 各頁的示意圖 -------------------------------------------------
def _draw_naming(painter: QPainter) -> None:
    _chip(painter, QRectF(20, 74, 96, 40), "週會", BRAND, size=12)
    painter.setPen(QPen(QColor(MUTED), 2))
    painter.drawLine(QPointF(124, 94), QPointF(168, 94))
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(9))
    painter.drawText(QRectF(120, 48, 60, 20), Qt.AlignCenter, "主題")

    for index in range(3):
        top = 26 + index * 48
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(PANEL))
        painter.drawRoundedRect(QRectF(180, top, 262, 38), 6, 6)
        painter.setBrush(QColor(BRAND))
        painter.drawRoundedRect(QRectF(194, top + 11, 16, 16), 3, 3)
        painter.setPen(QColor(INK))
        painter.setFont(_font(11))
        painter.drawText(QRectF(222, top, 200, 38), Qt.AlignVCenter | Qt.AlignLeft,
                         f"週會_{index + 1:02d}.png")


def _draw_capture(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1a1d22"))
    painter.drawRoundedRect(QRectF(16, 16, 438, 158), 8, 8)
    painter.setBrush(QColor(35, 39, 46))
    painter.drawRect(QRectF(60, 46, 210, 96))
    painter.setPen(QPen(QColor(BRAND), 2))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(60, 46, 210, 96))
    for x, y in ((60, 46), (165, 46), (270, 46), (60, 94), (270, 94),
                 (60, 142), (165, 142), (270, 142)):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BRAND))
        painter.drawRect(QRectF(x - 3, y - 3, 6, 6))
    _chip(painter, QRectF(60, 22, 84, 18), "1024 × 480", "#191b1f", INK, 8)

    _chip(painter, QRectF(292, 60, 62, 26), "F1", PANEL, INK)
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(9))
    painter.drawText(QRectF(360, 60, 90, 26), Qt.AlignVCenter | Qt.AlignLeft,
                     "框選後再決定")
    _chip(painter, QRectF(292, 100, 62, 26), "⇧F1", BRAND)
    painter.setPen(QColor(MUTED))
    painter.drawText(QRectF(360, 100, 90, 26), Qt.AlignVCenter | Qt.AlignLeft,
                     "放開即存檔")


def _draw_annotate(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1a1d22"))
    painter.drawRoundedRect(QRectF(16, 16, 438, 158), 8, 8)

    names = ["rect", "ellipse", "arrow", "pen", "marker", "mosaic", "text",
             "number", "eraser"]
    for index, name in enumerate(names):
        left = 36 + index * 45
        painter.setBrush(QColor(BRAND) if index == 0 else QColor(PANEL))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(left, 34, 34, 32), 5, 5)
        toolicons.icon(name).paint(painter, QRect(int(left + 7), 41, 20, 20))

    painter.setPen(QPen(QColor("#f5423f"), 2))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(46, 96, 150, 54))
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(10))
    painter.drawText(QRectF(214, 96, 220, 54),
                     Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
                     "滑鼠停在圖示上會顯示名稱與快捷鍵。\n畫完之後點一下還能搬移或刪除。")


def _draw_pin(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1a1d22"))
    painter.drawRoundedRect(QRectF(16, 16, 438, 158), 8, 8)
    for offset, shade in ((0, "#333941"), (28, "#3d444e")):
        rect = QRectF(48 + offset, 44 + offset, 168, 96)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(shade))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(QColor(BRAND), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(10))
    painter.drawText(QRectF(262, 44, 176, 96),
                     Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap,
                     "釘在桌面最上層，\n滾輪縮放、Ctrl+滾輪調透明度。\n"
                     "Shift+F3 一鍵全部收起來。")


def _draw_scroll(painter: QPainter) -> None:
    # 迷你瀏覽器：頂欄是固定的，框選時要避開
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1a1d22"))
    painter.drawRoundedRect(QRectF(16, 16, 280, 158), 8, 8)
    painter.setBrush(QColor("#343a44"))
    painter.drawRect(QRectF(16, 18, 280, 24))
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(8))
    painter.drawText(QRectF(26, 18, 240, 24), Qt.AlignVCenter | Qt.AlignLeft,
                     "網址列／固定標題（避開，不要框）")

    # 內文行
    painter.setPen(Qt.NoPen)
    for line in range(6):
        painter.setBrush(QColor(70, 78, 90))
        painter.drawRoundedRect(
            QRectF(36, 56 + line * 18, 210 - (line % 3) * 34, 8), 4, 4)

    # 擷取範圍的藍框
    painter.setPen(QPen(QColor(BRAND), 2))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(26, 48, 244, 118))

    # 滾輪往下的箭頭
    pen = QPen(QColor(INK), 3)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(324, 56), QPointF(324, 108))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(INK))
    painter.drawPolygon(QPolygonF([QPointF(324, 122), QPointF(315, 106),
                                   QPointF(333, 106)]))
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(9))
    painter.drawText(QRectF(342, 58, 112, 60),
                     Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap,
                     "自己用滾輪\n慢慢往下捲")

    # 進度面板
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(PANEL))
    painter.drawRoundedRect(QRectF(300, 134, 154, 40), 6, 6)
    painter.setPen(QColor(INK))
    painter.setFont(_font(8))
    painter.drawText(QRectF(312, 134, 90, 40), Qt.AlignVCenter | Qt.AlignLeft,
                     "已接 5 段")
    _chip(painter, QRectF(404, 143, 42, 22), "完成", BRAND, size=9)


def _draw_done(painter: QPainter) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(BRAND))
    painter.drawEllipse(QRectF(206, 34, 58, 58))
    pen = QPen(QColor("#ffffff"), 5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.drawPolyline([QPointF(222, 63), QPointF(232, 74), QPointF(249, 52)])
    painter.setPen(QColor(MUTED))
    painter.setFont(_font(10))
    painter.drawText(QRectF(40, 108, 390, 60),
                     Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                     "隨時可以從系統匣圖示右鍵叫出所有功能，\n"
                     "或從「使用教學…」再看一次這份說明。")


PAGES = (
    ("先取個主題，之後就不用再命名", _draw_naming,
     "按 Ctrl+F1 輸入這場會議或這個題目的名字，例如「週會」。\n"
     "之後每張截圖會自動接續編號，換主題就從 01 重新開始。"),
    ("兩種截圖方式", _draw_capture,
     "F1 框選後出現工具列，可以先標註再決定存檔或複製。\n"
     "Shift+F1 是連拍模式：放開滑鼠當下就存好，不跳任何對話框。"),
    ("標註", _draw_annotate,
     "框好之後工具列會出現。矩形、箭頭、螢光筆、馬賽克、序號都在裡面。\n"
     "機敏資訊請用「矩形＋填滿」蓋純色，馬賽克有機會被還原。"),
    ("釘圖與歷史", _draw_pin,
     "按 F 把截圖釘在桌面最上層，對照資料時很好用。\n"
     "最近 30 張都留在「截圖歷史」，手滑關掉也救得回來。"),
    ("滾動截圖：長文章接成一張", _draw_scroll,
     "系統匣選單 →「滾動截圖」，框住會捲動的內文（避開固定的標題列）。\n"
     "藍色外框會標示擷取範圍；用滾輪慢慢捲，捲完按「完成」。"),
    ("開始使用吧", _draw_done, ""),
)


class WelcomeDialog(QDialog):
    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cfg = config
        self.setWindowTitle("SnipTag 使用教學")
        self.setStyleSheet(QSS)
        self.setFixedWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)

        self.stack = QStackedWidget(self)
        for title, painter_fn, body in PAGES:
            self.stack.addWidget(self._page(title, painter_fn, body))
        layout.addWidget(self.stack)

        self.autostart_check = QCheckBox("開機時自動啟動，常駐在系統匣", self)
        self.autostart_check.setChecked(autostart.is_enabled())
        self.autostart_check.setEnabled(autostart.available())
        layout.addWidget(self.autostart_check)

        controls = QHBoxLayout()
        self.step_label = QLabel(self)
        self.step_label.setObjectName("step")
        controls.addWidget(self.step_label)
        controls.addStretch(1)
        self.back_button = QPushButton("上一步", self)
        self.next_button = QPushButton("下一步", self)
        self.next_button.setObjectName("primary")
        self.skip_button = QPushButton("略過", self)
        controls.addWidget(self.skip_button)
        controls.addWidget(self.back_button)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)

        self.back_button.clicked.connect(lambda: self.go(-1))
        self.next_button.clicked.connect(lambda: self.go(1))
        self.skip_button.clicked.connect(self.accept)
        self._refresh()

    def _page(self, title: str, painter_fn, body: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        art = QLabel(page)
        art.setPixmap(self._illustration(painter_fn))
        art.setAlignment(Qt.AlignCenter)
        layout.addWidget(art)

        heading = QLabel(title, page)
        heading.setObjectName("title")
        layout.addWidget(heading)

        text = QLabel(body, page)
        text.setObjectName("body")
        text.setWordWrap(True)
        text.setMinimumHeight(46)
        layout.addWidget(text)
        layout.addStretch(1)
        return page

    @staticmethod
    def _illustration(painter_fn) -> QPixmap:
        pixmap = QPixmap(CARD.width() * 2, CARD.height() * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(QColor("#20242a"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter_fn(painter)
        painter.end()
        return pixmap

    # --- 導覽 -----------------------------------------------------
    def go(self, step: int) -> None:
        index = self.stack.currentIndex() + step
        if index >= self.stack.count():
            self.accept()
            return
        self.stack.setCurrentIndex(max(0, index))
        self._refresh()

    def _refresh(self) -> None:
        index = self.stack.currentIndex()
        last = index == self.stack.count() - 1
        self.step_label.setText(f"{index + 1} / {self.stack.count()}")
        self.back_button.setEnabled(index > 0)
        self.skip_button.setVisible(not last)
        self.next_button.setText("完成" if last else "下一步")

    def wants_autostart(self) -> bool:
        return self.autostart_check.isChecked()
