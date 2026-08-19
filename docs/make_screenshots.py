"""產生 README 用的示範截圖：python docs/make_screenshots.py

畫面是合成出來的假桌面，不會用到執行者電腦上的真實內容，
所以任何人都能重跑這個腳本得到一模一樣的圖。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPen, QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from sniptag import annotate  # noqa: E402
from sniptag.config import DEFAULTS  # noqa: E402
from sniptag.dialogs import SettingsDialog, TopicDialog  # noqa: E402
from sniptag.history import History, HistoryDialog  # noqa: E402
from sniptag.welcome import WelcomeDialog  # noqa: E402
from sniptag.overlay import Overlay  # noqa: E402
from sniptag.pinwindow import PinWindow  # noqa: E402
from sniptag.screens import DesktopShot, Monitor  # noqa: E402

OUT = Path(__file__).resolve().parent
LOGICAL = QRect(0, 0, 1440, 900)
DPR = 2.0
MONITOR = Monitor("\\\\.\\DISPLAY1", LOGICAL,
                  QRect(0, 0, int(1440 * DPR), int(900 * DPR)), DPR)

# 假桌面上的視窗位置（邏輯座標）
SLIDE = QRect(48, 44, 880, 620)
NOTES = QRect(952, 44, 440, 400)
FILES = QRect(952, 468, 440, 196)

INK = QColor("#1b2330")
MUTED = QColor("#6b7686")
BRAND = QColor("#2d7ff9")


def font(size: int, bold: bool = False) -> QFont:
    f = QFont("Microsoft JhengHei UI")
    f.setPointSize(size)
    f.setBold(bold)
    return f


def shadow(painter: QPainter, rect: QRect, radius: int = 10) -> None:
    painter.setPen(Qt.NoPen)
    for i in range(1, 14):
        painter.setBrush(QColor(0, 0, 0, 7))
        painter.drawRoundedRect(rect.adjusted(-i, -i + 3, i, i + 5), radius + i, radius + i)


def window_frame(painter: QPainter, rect: QRect, title: str, dark: bool = False) -> QRect:
    """畫一個 Windows 11 樣式的視窗，回傳內容區。"""
    shadow(painter, rect)
    bar_height = 38
    body = QColor("#161a21") if dark else QColor("#ffffff")
    bar = QColor("#20252e") if dark else QColor("#f3f3f3")
    text = QColor("#c9d1dc") if dark else QColor("#39424f")

    painter.setPen(Qt.NoPen)
    painter.setBrush(body)
    painter.drawRoundedRect(rect, 10, 10)
    painter.save()
    painter.setClipRect(QRect(rect.x(), rect.y(), rect.width(), bar_height))
    painter.setBrush(bar)
    painter.drawRoundedRect(rect, 10, 10)
    painter.restore()

    # 左側應用程式圖示；右側則使用 Windows 11 標準視窗按鈕。
    painter.setBrush(BRAND)
    painter.drawRoundedRect(QRect(rect.x() + 12, rect.y() + 11, 16, 16), 3, 3)
    painter.setPen(QPen(QColor("#ffffff"), 1.5))
    painter.drawLine(rect.x() + 16, rect.y() + 16, rect.x() + 24, rect.y() + 16)
    painter.drawLine(rect.x() + 16, rect.y() + 21, rect.x() + 24, rect.y() + 21)

    controls_x = rect.right() - 3 * 46 + 1
    painter.setPen(QPen(text, 1.2))
    # 最小化
    painter.drawLine(controls_x + 18, rect.y() + 20,
                     controls_x + 28, rect.y() + 20)
    # 最大化
    painter.drawRect(QRect(controls_x + 46 + 18, rect.y() + 14, 10, 10))
    # 關閉
    close_x = controls_x + 92
    painter.drawLine(close_x + 18, rect.y() + 14,
                     close_x + 28, rect.y() + 24)
    painter.drawLine(close_x + 28, rect.y() + 14,
                     close_x + 18, rect.y() + 24)

    painter.setPen(text)
    painter.setFont(font(9))
    painter.drawText(rect.x() + 38, rect.y() + 9, rect.width() - 190, 20,
                     Qt.AlignVCenter | Qt.AlignLeft, title)
    return QRect(rect.x(), rect.y() + bar_height, rect.width(),
                 rect.height() - bar_height)


def draw_slide(painter: QPainter) -> None:
    body = window_frame(painter, SLIDE, "本週進度 — 簡報.pptx")
    painter.setPen(INK)
    painter.setFont(font(21, bold=True))
    painter.drawText(body.x() + 40, body.y() + 26, body.width() - 80, 46,
                     Qt.AlignLeft | Qt.AlignVCenter, "兩種資料匯入方式")

    painter.setPen(QColor("#dfe4ea"))
    painter.drawLine(body.x() + 40, body.y() + 82, body.right() - 40, body.y() + 82)

    columns = [
        ("方式 A：線上同步", [
            "由系統定時連線來源端取得資料",
            "需要來源方開通存取權限",
            "適合集中控管、統一排程",
            "不需在每台機器安裝工具",
        ]),
        ("方式 B：本機匯入", [
            "由承辦人手動上傳檔案匯入",
            "不限來源格式，CSV 或 Excel 皆可",
            "需先自行整理成指定欄位",
            "適合離線或受限網段環境",
        ]),
    ]
    width = (body.width() - 100) // 2
    for index, (heading, bullets) in enumerate(columns):
        x = body.x() + 40 + index * (width + 20)
        y = body.y() + 108
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f5f8fc"))
        painter.drawRoundedRect(QRect(x, y, width, 340), 8, 8)
        painter.setPen(BRAND)
        painter.setFont(font(13, bold=True))
        painter.drawText(x + 20, y + 18, width - 40, 30,
                         Qt.AlignLeft | Qt.AlignVCenter, heading)
        painter.setFont(font(9))
        painter.setPen(QColor("#3c4756"))
        for line, bullet in enumerate(bullets):
            top = y + 62 + line * 46
            painter.setBrush(BRAND)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x + 22, top + 8, 5, 5)
            painter.setPen(QColor("#3c4756"))
            painter.drawText(x + 38, top, width - 58, 40,
                             Qt.AlignLeft | Qt.TextWordWrap, bullet)

    painter.setPen(MUTED)
    painter.setFont(font(8))
    painter.drawText(body.x() + 40, body.bottom() - 40, body.width() - 80, 24,
                     Qt.AlignLeft | Qt.AlignVCenter,
                     "補充說明：兩種方式匯入後的資料格式相同，可直接產出同一份報表。")
    painter.drawText(body.right() - 90, body.bottom() - 40, 50, 24,
                     Qt.AlignRight | Qt.AlignVCenter, "06 / 21")


def draw_notes(painter: QPainter) -> None:
    body = window_frame(painter, NOTES, "會議筆記 — 2026-08-12", dark=True)
    painter.setPen(QColor("#9fb0c6"))
    painter.setFont(font(11, bold=True))
    painter.drawText(body.x() + 22, body.y() + 16, body.width() - 44, 26,
                     Qt.AlignLeft | Qt.AlignVCenter, "本週討論事項")
    painter.setFont(font(9))
    painter.setPen(QColor("#7d8ea6"))
    notes = [
        "· 先確認兩種方式的適用範圍",
        "· 同步頻率：每週一次排程",
        "· 結果統一匯入既有報表",
        "· 下次會議前補上成本估算",
        "",
        "待辦：整理今天的簡報截圖",
    ]
    for index, line in enumerate(notes):
        painter.drawText(body.x() + 22, body.y() + 54 + index * 30, body.width() - 44, 26,
                         Qt.AlignLeft | Qt.AlignVCenter, line)


def draw_files(painter: QPainter) -> None:
    body = window_frame(painter, FILES, "SnipTag — 檔案總管")
    painter.setFont(font(9))
    names = ["週會_01.png", "週會_02.png", "週會_03.png"]
    for index, name in enumerate(names):
        top = body.y() + 16 + index * 44
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#eaf1fe") if index == 2 else QColor("#f7f9fb"))
        painter.drawRoundedRect(QRect(body.x() + 16, top, body.width() - 32, 36), 6, 6)
        painter.setBrush(BRAND if index == 2 else QColor("#b9c4d2"))
        painter.drawRoundedRect(QRect(body.x() + 28, top + 10, 16, 16), 3, 3)
        painter.setPen(INK if index == 2 else QColor("#5b6674"))
        painter.drawText(body.x() + 56, top, body.width() - 80, 36,
                         Qt.AlignLeft | Qt.AlignVCenter, name)


def build_desktop() -> QImage:
    image = QImage(int(LOGICAL.width() * DPR), int(LOGICAL.height() * DPR),
                   QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.scale(DPR, DPR)

    gradient = QLinearGradient(0, 0, LOGICAL.width(), LOGICAL.height())
    gradient.setColorAt(0.0, QColor("#123d79"))
    gradient.setColorAt(0.55, QColor("#0b2853"))
    gradient.setColorAt(1.0, QColor("#07162e"))
    painter.fillRect(LOGICAL, gradient)

    # 簡化的 Windows 11 藍色桌布光帶，避免被誤認為其他平台。
    painter.setPen(Qt.NoPen)
    for index, color in enumerate((
        QColor(64, 153, 255, 30), QColor(43, 111, 230, 34),
        QColor(113, 191, 255, 20),
    )):
        painter.setBrush(color)
        painter.drawEllipse(QRect(-180 + index * 190, 70 + index * 120,
                                  1180, 700))

    draw_slide(painter)
    draw_notes(painter)
    draw_files(painter)

    # Windows 11 置中工作列
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(242, 246, 252, 245))
    painter.drawRect(QRect(0, 854, LOGICAL.width(), 46))

    # Windows 開始圖示（四片藍色方格）
    start_x, start_y = 590, 866
    painter.setBrush(QColor("#1675e0"))
    for dx, dy in ((0, 0), (10, 0), (0, 10), (10, 10)):
        painter.drawRect(QRect(start_x + dx, start_y + dy, 8, 8))

    # 搜尋框
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRect(620, 861, 112, 32), 16, 16)
    painter.setPen(QPen(QColor("#596575"), 1.4))
    painter.drawEllipse(QRect(635, 870, 10, 10))
    painter.drawLine(644, 879, 650, 885)
    painter.setFont(font(8))
    painter.drawText(QRect(655, 861, 64, 32), Qt.AlignVCenter, "搜尋")

    # 檔案總管與瀏覽器圖示
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#f5bd2e"))
    painter.drawRoundedRect(QRect(748, 869, 25, 18), 3, 3)
    painter.setBrush(QColor("#42a5f5"))
    painter.drawEllipse(QRect(790, 864, 27, 27))

    painter.setPen(QColor("#354052"))
    painter.setFont(font(8))
    painter.drawText(QRect(LOGICAL.width() - 150, 860, 130, 40),
                     Qt.AlignRight | Qt.AlignVCenter, "上午 11:28\n2026/8/12")
    painter.end()
    return image


class _NullApp:
    """截圖時 HistoryDialog 不需要真的做事。"""

    def pin_centered(self, _pixmap): pass

    def save_pixmap(self, _pixmap, record=True): return None

    def copy_to_clipboard(self, _pixmap): pass


class DemoOverlay(Overlay):
    """把游標位置固定下來，讓放大鏡出現在指定的地方。"""

    def __init__(self, shot, preview, cursor: QPoint) -> None:
        super().__init__(shot, lambda: preview)
        self.demo_cursor = cursor
        self.window_groups = [[SLIDE], [NOTES], [FILES]]

    def _cursor_pos(self) -> QPoint:
        return self.demo_cursor


def save(pixmap: QPixmap, name: str) -> None:
    path = OUT / name
    pixmap.scaled(LOGICAL.width(), LOGICAL.height(),
                  Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(path), "PNG")
    print(f"  {name}  ({path.stat().st_size // 1024} KB)")


def grab_dialog(dialog) -> QPixmap:
    """對話框要真的顯示過一次，Qt 才會把版面算完整。"""
    dialog.show()
    QApplication.processEvents()
    dialog.adjustSize()
    QApplication.processEvents()
    shot = dialog.grab()
    dialog.hide()
    return shot


def panel(widget_shot: QPixmap, pad: int = 44) -> QPixmap:
    """對話框單獨呈現：保留原生解析度，只加上留白與陰影。

    縮到邏輯尺寸會讓中文字糊掉，所以這裡不縮放。
    """
    raw = QPixmap(widget_shot)
    raw.setDevicePixelRatio(1.0)
    canvas = QPixmap(raw.width() + pad * 2, raw.height() + pad * 2)
    canvas.fill(QColor("#dfe4ea"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRect(pad, pad, raw.width(), raw.height())
    shadow(painter, rect, 6)
    painter.drawPixmap(pad, pad, raw)
    painter.setPen(QPen(QColor(0, 0, 0, 70), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(rect.adjusted(0, 0, -1, -1))
    painter.end()
    return canvas


def save_raw(pixmap: QPixmap, name: str) -> None:
    path = OUT / name
    pixmap.save(str(path), "PNG")
    print(f"  {name}  ({path.stat().st_size // 1024} KB)")


def main() -> None:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)

    desktop = build_desktop()
    shot = DesktopShot(desktop, QPoint(0, 0), [MONITOR])
    print("產生示範截圖：")

    # 1. 拖曳框選中：暗化 + 尺寸標籤 + 放大鏡停在文字上（看得出逐像素放大）
    handle = QPoint(620, 348)   # 停在文字上，放大鏡才看得出逐像素
    overlay = DemoOverlay(shot, "週會_03.png", handle)
    overlay.selection = QRect(QPoint(88, 186), handle)
    overlay.settled = False
    save(overlay.grab(), "capture.png")
    overlay.close()

    # 2. 框選完成：控制點 + 工具列（含下一個檔名）
    overlay = DemoOverlay(shot, "週會_03.png", QPoint(-1, -1))
    overlay.selection = QRect(72, 186, 812, 364)
    overlay.settled = True
    overlay._show_toolbar()
    save(overlay.grab(), "toolbar.png")
    overlay.close()

    # 3. 標註：矩形、箭頭、螢光筆、馬賽克、文字全部用上
    overlay = DemoOverlay(shot, "週會_03.png", QPoint(-1, -1))
    overlay.selection = QRect(72, 186, 812, 364)
    overlay.settled = True
    red = annotate.Style("#f5423f", 4)
    blue = annotate.Style("#2d7ff9", 4)
    overlay.layer.add(annotate.RectShape(QPoint(500, 196), QPoint(878, 320), red))
    overlay.layer.add(annotate.ArrowShape(QPoint(320, 470), QPoint(520, 270), red))
    overlay.layer.add(annotate.MarkerShape(
        [QPoint(126, 256), QPoint(300, 256)], annotate.Style("#ff9f1c", 5)))
    overlay.layer.add(annotate.MosaicShape(QPoint(126, 290), QPoint(300, 312),
                                           annotate.Style()))
    overlay.layer.add(annotate.TextShape(QPoint(232, 492), "這段是重點", red))
    overlay.layer.add(annotate.EllipseShape(QPoint(520, 330), QPoint(700, 372), blue))
    overlay.layer.add(annotate.NumberShape(QPoint(110, 256), 1, blue))
    overlay.layer.add(annotate.NumberShape(QPoint(110, 302), 2, blue))
    overlay.layer.add(annotate.NumberShape(QPoint(508, 348), 3, blue))
    overlay.style = red
    overlay.tool = "rect"
    overlay._show_toolbar()
    save(overlay.grab(), "annotate.png")
    overlay.close()

    # 4. 視窗自動偵測：還沒拖曳，游標停在筆記視窗上
    overlay = DemoOverlay(shot, "週會_03.png", NOTES.center())
    overlay._update_hover(NOTES.center())
    save(overlay.grab(), "window-detect.png")
    overlay.close()

    # 4b. 工具列的提示列：滑到某個圖示上會寫出那是什麼
    overlay = DemoOverlay(shot, "週會_03.png", QPoint(-1, -1))
    overlay.selection = QRect(72, 186, 812, 364)
    overlay.settled = True
    overlay._show_toolbar()
    overlay.toolbar.hint_label.setText("馬賽克　M")
    overlay.toolbar.tool_buttons["mosaic"].setChecked(True)
    save(overlay.grab(), "toolbar-hint.png")
    overlay.close()

    # 4. 釘圖：把兩塊裁切結果釘在桌面上
    canvas = QPixmap.fromImage(desktop.scaled(
        LOGICAL.width(), LOGICAL.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    for source, target in ((QRect(88, 128, 400, 250), QPoint(560, 470)),
                           (QRect(500, 150, 380, 210), QPoint(120, 620))):
        piece = shot.crop(source)
        piece.setDevicePixelRatio(1.0)
        piece = piece.scaled(source.width(), source.height(),
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        rect = QRect(target, piece.size())
        shadow(painter, rect, 4)
        painter.drawPixmap(target, piece)
        painter.setPen(QPen(BRAND, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
    painter.end()
    save(canvas, "pin.png")

    # 5. 主題對話框
    config = dict(DEFAULTS)
    config["topic"] = "週會"
    config["recent_topics"] = ["週會", "產品簡報", "08-12 教育訓練"]
    # 用通用路徑，避免把產圖者的使用者名稱寫進文件
    config["save_dir"] = r"C:\Users\you\Pictures\SnipTag"

    class DemoConfig(dict):
        save_root = OUT / "_preview"

        def set_topic(self, topic):
            self["topic"] = topic

    demo_config = DemoConfig(config)
    (OUT / "_preview").mkdir(exist_ok=True)
    for index in (1, 2):
        (OUT / "_preview" / f"週會_{index:02d}.png").write_bytes(b"")

    topic_dialog = TopicDialog(demo_config)
    save_raw(panel(grab_dialog(topic_dialog)), "topic.png")
    topic_dialog.close()

    settings = SettingsDialog(demo_config)
    save_raw(panel(grab_dialog(settings)), "settings.png")
    settings.close()

    # 6b. 使用教學（第 1 與第 3 頁）
    for page, name in ((0, "welcome.png"), (2, "welcome-annotate.png")):
        tutorial = WelcomeDialog(demo_config)
        tutorial.stack.setCurrentIndex(page)
        tutorial._refresh()
        save_raw(panel(grab_dialog(tutorial)), name)
        tutorial.close()

    # 7. 截圖歷史
    history = History()
    for index, region in enumerate((
        QRect(88, 186, 390, 340), QRect(500, 186, 390, 340),
        QRect(72, 96, 816, 90), QRect(952, 78, 440, 366),
    )):
        piece = shot.crop(region)
        history.add(piece, f"週會_{index + 1:02d}.png" if index < 3 else "")
    history_dialog = HistoryDialog(history, _NullApp())
    save_raw(panel(grab_dialog(history_dialog)), "history.png")
    history_dialog.close()

    for leftover in (OUT / "_preview").glob("*.png"):
        leftover.unlink()
    (OUT / "_preview").rmdir()
    app.closeAllWindows()


if __name__ == "__main__":
    main()
    # 顯示過對話框之後 Qt 不見得會自己收乾淨，直接結束比較保險
    sys.exit(0)
