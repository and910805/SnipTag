"""自製通知泡泡：取代系統匣原生通知。

原生通知由 Windows Shell 繪製：會被「專注輔助」整顆吃掉、點到附近就收起來，
而且截圖工具（包含 SnipTag 自己）常常拍不到它。改成自己畫的一般視窗後，
BitBlt 一定抓得到，想截自己的「已存檔」泡泡也沒問題。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

ACCENTS = {
    "info": QColor("#2d7ff9"),
    "warning": QColor("#e8a33d"),
    "critical": QColor("#e05252"),
}
BACKGROUND = QColor(32, 33, 36, 242)
MARGIN = 16          # 與螢幕邊緣的距離
DURATION_MS = 4000   # 停留時間；夠長，想截它也來得及


class Toast(QWidget):
    """右下角的小通知卡片。同一時間只有一張，新訊息直接換內容。"""

    def __init__(self) -> None:
        super().__init__(None)
        # Tool = 不佔工作列；DoesNotAcceptFocus = 不搶正在打字的焦點
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.accent = ACCENTS["info"]

        # 字型用程式設定而不是 stylesheet：算寬度時 fontMetrics 才會準
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        body_font = QFont()
        body_font.setPointSize(9)

        self.title_label = QLabel()
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: white;")
        self.body_label = QLabel()
        self.body_label.setFont(body_font)
        self.body_label.setStyleSheet("color: #c9cbd1;")
        self.body_label.setWordWrap(True)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.title_label)
        text.addWidget(self.body_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 16, 12)   # 左邊多留一點給色條
        layout.addLayout(text)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, title: str, message: str, level: str = "info") -> None:
        self.accent = ACCENTS.get(level, ACCENTS["info"])
        self.title_label.setText(title)
        self.body_label.setText(message)
        self.body_label.setVisible(bool(message))
        # QLabel 開了自動換行後 sizeHint 不反映文字實際寬度，自己量
        lines = [(self.title_label, title)] + [
            (self.body_label, line) for line in message.splitlines()
        ]
        text_width = max(
            QFontMetrics(label.font()).horizontalAdvance(line)
            for label, line in lines
        )
        margins = self.layout().contentsMargins()
        wanted = text_width + margins.left() + margins.right() + 8
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setFixedWidth(min(max(wanted, 260), 420))
        self.adjustSize()

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - MARGIN,
                      area.bottom() - self.height() - MARGIN)
        self.show()
        self.raise_()
        self._timer.start(DURATION_MS)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(BACKGROUND)
        painter.drawRoundedRect(QRectF(self.rect()), 10, 10)
        painter.setBrush(self.accent)
        painter.drawRoundedRect(QRectF(8, 10, 4, self.height() - 20), 2, 2)
        painter.end()

    def mousePressEvent(self, _event) -> None:
        self._timer.stop()
        self.hide()
