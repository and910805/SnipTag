"""混合 DPI 座標換算測試（不需要真的接外接螢幕）：python test_dpi.py

模擬情境：筆電 1440x900 @200%（實體 2880x1800）+ 右側外接 1920x1080 @100%。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from sniptag.screens import DesktopShot, Monitor

LAPTOP = Monitor("\\\\.\\DISPLAY1", QRect(0, 0, 1440, 900), QRect(0, 0, 2880, 1800), 2.0)
EXTERNAL = Monitor("\\\\.\\DISPLAY2", QRect(1440, 0, 1920, 1080),
                   QRect(2880, 0, 1920, 1080), 1.0)

RED = QColor(220, 40, 40)
BLUE = QColor(40, 80, 220)
MARK = QColor(255, 255, 255)


def build_shot() -> DesktopShot:
    """實體虛擬桌面 4800x1800：左半（筆電）紅、右半（外接）藍。

    兩邊各放一個白色標記，用來驗證裁切出來的內容沒有被縮放或位移。
    """
    image = QImage(4800, 1800, QImage.Format_RGB32)
    image.fill(Qt.black)
    painter = QPainter(image)
    painter.fillRect(QRect(0, 0, 2880, 1800), RED)
    painter.fillRect(QRect(2880, 0, 1920, 1080), BLUE)
    painter.fillRect(QRect(400, 400, 20, 20), MARK)     # 筆電：邏輯 (200,200)
    painter.fillRect(QRect(3200, 200, 20, 20), MARK)    # 外接：邏輯 (1760,200)
    painter.end()
    return DesktopShot(image, QPoint(0, 0), [LAPTOP, EXTERNAL])


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    shot = build_shot()

    print("整體範圍")
    check(shot.logical_geometry == QRect(0, 0, 3360, 1080), "邏輯桌面 = 1440+1920 寬")

    print("邏輯座標 -> 實體像素")
    check(shot.to_image_point(QPoint(100, 100)) == QPoint(200, 200), "筆電上 ×2")
    check(shot.to_image_point(QPoint(1540, 100)) == QPoint(2980, 100), "外接上 ×1")
    check(shot.color_at(QPoint(100, 100)) == RED, "筆電區取到紅色")
    check(shot.color_at(QPoint(1540, 100)) == BLUE, "外接區取到藍色")

    print("縮放比判定")
    check(shot.dpr_for(QRect(10, 10, 100, 100)) == 2.0, "全在筆電 -> 2.0")
    check(shot.dpr_for(QRect(1500, 10, 100, 100)) == 1.0, "全在外接 -> 1.0")
    check(shot.dpr_for(QRect(1400, 10, 200, 100)) == 2.0, "跨螢幕 -> 取高的 2.0")

    print("裁切解析度")
    laptop_crop = shot.crop(QRect(100, 100, 400, 300))
    check((laptop_crop.width(), laptop_crop.height()) == (800, 600),
          "筆電上 400x300 -> 800x600 實體像素")
    check(laptop_crop.devicePixelRatio() == 2.0, "裁切帶著 dpr=2")
    check(laptop_crop.toImage().pixelColor(400, 300) == RED, "內容是紅的")
    # 標記在實體 (400,400)，裁切原點是實體 (200,200)，所以應落在 (200,200)
    check(laptop_crop.toImage().pixelColor(210, 210) == MARK, "標記位置正確（沒被縮放）")
    check(laptop_crop.toImage().pixelColor(150, 150) == RED, "標記外圍仍是背景色")

    external_crop = shot.crop(QRect(1600, 100, 400, 300))
    check((external_crop.width(), external_crop.height()) == (400, 300),
          "外接上 400x300 -> 400x300 實體像素")
    check(external_crop.toImage().pixelColor(200, 150) == BLUE, "內容是藍的")
    check(external_crop.toImage().pixelColor(170, 110) == MARK, "外接標記位置正確")

    print("跨螢幕裁切")
    spanning = shot.crop(QRect(1340, 100, 200, 200))
    check((spanning.width(), spanning.height()) == (400, 400), "以高 dpr 為準拼接")
    left_half = spanning.toImage().pixelColor(50, 200)
    right_half = spanning.toImage().pixelColor(350, 200)
    check(left_half == RED, "左半來自筆電（紅）")
    check(right_half == BLUE, "右半來自外接（藍）")

    print("視窗矩形換算（實體 -> 邏輯）")
    check(shot.physical_rect_to_logical(200, 200, 1000, 800)
          == QRect(100, 100, 400, 300), "筆電上的視窗 ÷2")
    check(shot.physical_rect_to_logical(3080, 100, 3480, 400)
          == QRect(1640, 100, 400, 300), "外接上的視窗 ÷1")

    print("繪製到邏輯座標系")
    canvas = QImage(3360, 1080, QImage.Format_RGB32)
    canvas.fill(Qt.black)
    painter = QPainter(canvas)
    shot.paint(painter, QPoint(0, 0))
    painter.end()
    check(canvas.pixelColor(700, 400) == RED, "左側畫成筆電畫面")
    check(canvas.pixelColor(2400, 400) == BLUE, "右側畫成外接畫面")
    check(canvas.pixelColor(1430, 400) == RED, "接縫左邊仍是筆電")
    check(canvas.pixelColor(1450, 400) == BLUE, "接縫右邊已是外接")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
