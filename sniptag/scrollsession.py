"""滾動截圖的進行中介面。

流程：選好區域 → 這個小視窗出現 → 使用者在目標視窗上自己捲動，
計時器每 200ms 拍一張餵給拼接器 → 按「完成」輸出長圖。

為什麼是使用者捲而不是程式捲：合成滾輪事件每個應用程式反應都不同
（不理會、平滑動畫、慣性），使用者自己捲則永遠是原生行為。
"""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import screens, scroll

TICK_MS = 200
MAX_HEIGHT = 40000      # 實體像素；超過就自動完成，避免記憶體吃到飽
WDA_EXCLUDEFROMCAPTURE = 0x11

QSS = """
QWidget#panel { background: #23262b; border: 1px solid #3a3f47; border-radius: 8px; }
QLabel#stats { color: #e8eaed; font-size: 13px; font-weight: bold; }
QLabel#hint  { color: #96a0ae; font-size: 12px; }
QLabel#warn  { color: #ffb020; font-size: 12px; font-weight: bold; }
QPushButton {
    background: #2f343b; color: #e8eaed; border: none; border-radius: 4px;
    padding: 6px 14px; font-size: 13px;
}
QPushButton:hover { background: #3d434c; }
QPushButton#primary { background: #2d7ff9; color: white; font-weight: bold; }
QPushButton#primary:hover { background: #4a92fb; }
"""


def _exclude_from_capture(widget: QWidget) -> None:
    """把視窗從螢幕擷取中排除，才不會被拍進長圖裡。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.SetWindowDisplayAffinity(
            int(widget.winId()), WDA_EXCLUDEFROMCAPTURE)
    except (AttributeError, OSError):
        pass    # 舊版 Windows 沒有這個功能


class RegionFrame(QWidget):
    """捲動期間標示擷取範圍的外框。滑鼠事件完全穿透，滾輪照常捲底下的視窗。"""

    BORDER = 3
    NORMAL = "#2d7ff9"
    WARNING = "#ffb020"

    def __init__(self, region: QRect) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.color = QColor(self.NORMAL)
        # 框畫在區域外側，內容一個像素都不遮
        b = self.BORDER
        self.setGeometry(region.adjusted(-b, -b, b, b))
        _exclude_from_capture(self)

    def set_warning(self, warning: bool) -> None:
        self.color = QColor(self.WARNING if warning else self.NORMAL)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        pen = QPen(self.color, self.BORDER)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        inset = self.BORDER // 2
        painter.drawRect(self.rect().adjusted(inset, inset, -inset - 1, -inset - 1))


class ScrollSession(QWidget):
    """一次滾動截圖。結束時把長圖交回給 app。"""

    def __init__(self, app, region: QRect, frame_source=None) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.setObjectName("panel")
        self.setStyleSheet(QSS)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.app = app
        self.region = QRect(region)          # 全域邏輯座標
        self.stitcher = scroll.Stitcher()
        self.frame_source = frame_source or self._grab_region
        self.dpr = 1.0
        self._finished = False
        self._seen_rejected = 0
        self._seen_segments = 0

        self.frame_marker = RegionFrame(self.region)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        self.stats_label = QLabel("等待第一張畫面…", self)
        self.stats_label.setObjectName("stats")
        layout.addWidget(self.stats_label)

        hint = QLabel("在框選的視窗上用滾輪慢慢往下捲，內容會自動接起來。", self)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self.warn_label = QLabel("", self)
        self.warn_label.setObjectName("warn")
        self.warn_label.hide()
        layout.addWidget(self.warn_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        finish_button = QPushButton("完成", self)
        finish_button.setObjectName("primary")
        finish_button.clicked.connect(self.finish)
        cancel_button = QPushButton("取消", self)
        cancel_button.clicked.connect(self.cancel)
        buttons.addWidget(finish_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        _exclude_from_capture(self)

    # --- 視窗行為 -------------------------------------------------
    def _place(self) -> None:
        """優先放在框選區域外面，滾輪才不會捲到這個視窗上。"""
        self.adjustSize()
        screen = QGuiApplication.screenAt(self.region.center())
        bounds = (screen.availableGeometry() if screen
                  else QGuiApplication.primaryScreen().availableGeometry())
        x = max(bounds.left() + 8,
                min(self.region.left(), bounds.right() - self.width() - 8))
        below = self.region.bottom() + 10
        above = self.region.top() - self.height() - 10
        if below + self.height() <= bounds.bottom():
            y = below
        elif above >= bounds.top():
            y = above
        else:   # 區域占滿整個螢幕：疊在右下角（反正已從擷取中排除）
            x = self.region.right() - self.width() - 16
            y = self.region.bottom() - self.height() - 16
        self.move(x, y)

    def start(self) -> None:
        self._place()
        self.frame_marker.show()    # 捲動期間讓使用者看得到擷取範圍在哪
        self.show()
        self.timer.start(TICK_MS)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish()
        else:
            super().keyPressEvent(event)

    # --- 擷取 -----------------------------------------------------
    def _grab_region(self):
        shot = screens.grab_desktop()
        if shot is None:
            return None
        pixmap = shot.crop(self.region)
        self.dpr = pixmap.devicePixelRatio() or 1.0
        pixmap.setDevicePixelRatio(1.0)
        return pixmap.toImage()

    def _tick(self) -> None:
        frame = self.frame_source()
        if frame is None:
            return
        self.stitcher.add(frame)
        self._refresh_labels()
        if self.stitcher.height >= MAX_HEIGHT:
            self.finish()

    def _refresh_labels(self) -> None:
        height = self.stitcher.height
        pages = height / max(1.0, self.region.height() * self.dpr)
        self.stats_label.setText(
            f"已接 {len(self.stitcher)} 段　長度 {height} px（約 {pages:.1f} 個畫面高）")
        if self.stitcher.rejected > self._seen_rejected:
            # 剛剛有一張接不上：提醒，直到下一段成功接上才收掉
            self._seen_rejected = self.stitcher.rejected
            self._seen_segments = len(self.stitcher)
            self.warn_label.setText("這一段接不上 —— 往回捲一點，再慢慢往下捲。")
            self.warn_label.show()
            self.frame_marker.set_warning(True)
        elif len(self.stitcher) > self._seen_segments:
            self.warn_label.hide()
            self.frame_marker.set_warning(False)

    # --- 收尾 -----------------------------------------------------
    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.timer.stop()
        result = self.stitcher.result()
        if result is None or len(self.stitcher) == 0:
            self.app.notify("滾動截圖", "沒有擷取到任何內容。")
            self._close()
            return
        pixmap = QPixmap.fromImage(result)
        pixmap.setDevicePixelRatio(self.dpr)
        self._close()
        self.app.finish_scroll(pixmap)

    def cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.timer.stop()
        self._close()

    def _close(self) -> None:
        self.frame_marker.close()
        self.app.forget_scroll_session(self)
        self.close()
