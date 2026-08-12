"""輸出效果測試（圓角 / 陰影 / 外框）：python test_effects.py"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from sniptag import effects

DPR = 2.0
SIZE = 120


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def source() -> QPixmap:
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(QColor(30, 120, 220))
    pixmap.setDevicePixelRatio(DPR)
    return pixmap


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("沒開任何效果就原樣回傳")
    plain = source()
    check(effects.apply(plain) is plain, "回傳的是同一個物件，沒有多做事")

    print("圓角")
    rounded = effects.apply(source(), radius=16)
    image = rounded.toImage()
    check((rounded.width(), rounded.height()) == (SIZE, SIZE), "尺寸不變")
    check(rounded.devicePixelRatio() == DPR, "dpr 保留")
    check(image.pixelColor(0, 0).alpha() == 0, "左上角被切掉（透明）")
    check(image.pixelColor(SIZE - 1, SIZE - 1).alpha() == 0, "右下角也是")
    check(image.pixelColor(SIZE // 2, SIZE // 2).alpha() == 255, "中間維持不透明")
    check(image.pixelColor(SIZE // 2, 2).alpha() == 255, "上緣中點保留")

    print("直角時四個角都在")
    square = effects.apply(source(), radius=0, border=True)
    check(square.toImage().pixelColor(0, 0).alpha() == 255, "角落沒有被切掉")

    print("陰影")
    shadowed = effects.apply(source(), shadow=True)
    margin = round(effects.SHADOW_MARGIN * DPR)
    check(shadowed.width() == SIZE + margin * 2, f"寬度外擴 {margin}×2")
    check(shadowed.height() == SIZE + margin * 2, "高度同理")
    check(shadowed.devicePixelRatio() == DPR, "dpr 保留")
    shadow_image = shadowed.toImage()
    check(shadow_image.pixelColor(margin + SIZE // 2, margin + SIZE // 2)
          == QColor(30, 120, 220), "原圖內容擺在正中間")
    check(shadow_image.pixelColor(2, 2).alpha() < 60, "最外圈幾乎全透明")
    below = shadow_image.pixelColor(margin + SIZE // 2, margin + SIZE + margin // 2)
    check(0 < below.alpha() < 255, f"下緣有淡淡的陰影（alpha={below.alpha()}）")

    print("圓角 + 陰影 一起用")
    both = effects.apply(source(), radius=12, shadow=True, border=True)
    check(both.width() == SIZE + margin * 2, "尺寸以陰影為準")
    corner = both.toImage().pixelColor(margin + 1, margin + 1)
    check(corner.alpha() < 255, "圓角仍然生效（角落不是實心）")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
