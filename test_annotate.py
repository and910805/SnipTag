"""標註功能測試：python test_annotate.py

重點在「標註畫在框選介面的座標上，輸出時要正確落到原生解析度的對應位置」。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from sniptag import annotate
from sniptag.overlay import Overlay
from sniptag.screens import DesktopShot, Monitor

DPR = 2.0
LOGICAL = QRect(0, 0, 800, 600)
MONITOR = Monitor("\\\\.\\DISPLAY1", LOGICAL,
                  QRect(0, 0, int(800 * DPR), int(600 * DPR)), DPR)
BACKDROP = QColor(250, 250, 250)
SELECTION = QRect(150, 150, 400, 300)


def build_shot() -> DesktopShot:
    image = QImage(int(800 * DPR), int(600 * DPR), QImage.Format_RGB32)
    image.fill(BACKDROP)
    painter = QPainter(image)
    # 放一塊高對比的圖樣，用來確認馬賽克真的動到了像素
    for i in range(0, 400, 8):
        painter.fillRect(QRect(600 + i, 400, 4, 200), QColor(10, 10, 10))
    painter.end()
    return DesktopShot(image, QPoint(0, 0), [MONITOR])


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def close_to(actual: QColor, expected: QColor, tolerance: int = 40) -> bool:
    return (abs(actual.red() - expected.red()) <= tolerance
            and abs(actual.green() - expected.green()) <= tolerance
            and abs(actual.blue() - expected.blue()) <= tolerance)


def new_overlay(shot: DesktopShot) -> Overlay:
    overlay = Overlay(shot, lambda: "T_01.png")
    overlay.window_groups = []
    overlay.selection = QRect(SELECTION)
    overlay.settled = True
    return overlay


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    shot = build_shot()

    print("圖層操作")
    layer = annotate.Layer()
    style = annotate.Style()
    layer.add(annotate.RectShape(QPoint(0, 0), QPoint(10, 10), style))
    layer.add(annotate.RectShape(QPoint(5, 5), QPoint(20, 20), style))
    check(len(layer) == 2, "加入兩個圖形")
    check(layer.undo() and len(layer) == 1, "復原")
    check(layer.redo() and len(layer) == 2, "重做")
    check(layer.clear() and len(layer) == 0, "清除")
    check(not layer.undo(), "空圖層復原回傳 False")
    check(layer.redo() and len(layer) == 1, "清除後仍可重做")

    print("輸出尺寸不受標註影響")
    overlay = new_overlay(shot)
    plain = overlay.render_result()
    check((plain.width(), plain.height()) == (800, 600),
          "400x300 @dpr2 -> 800x600")
    overlay.style = annotate.Style(color="#f5423f", width=4)
    overlay.layer.add(annotate.RectShape(QPoint(200, 200), QPoint(300, 260),
                                         overlay.style.copy()))
    annotated = overlay.render_result()
    check((annotated.width(), annotated.height()) == (800, 600),
          "加了標註之後尺寸不變")

    print("標註落點")
    image = annotated.toImage()
    # 框選左上角是 (150,150)，所以矩形上緣中點 (250,200) 應落在 (200,100)
    check(close_to(image.pixelColor(200, 100), QColor("#f5423f")),
          "矩形上緣落在 (200,100)")
    check(close_to(image.pixelColor(100, 100), QColor("#f5423f")),
          "矩形左上角落在 (100,100)")
    check(close_to(image.pixelColor(300, 300), BACKDROP),
          "矩形內部沒有被填滿")
    check(close_to(image.pixelColor(20, 20), BACKDROP),
          "矩形外面維持原樣")
    overlay.close()

    print("各種工具都畫得出東西")
    for tool in ("rect", "ellipse", "arrow", "line", "pen", "marker", "mosaic"):
        probe = new_overlay(shot)
        probe.style = annotate.Style(color="#2d7ff9", width=5)
        shape = annotate.make_shape(tool, QPoint(200, 200), QPoint(400, 380),
                                    probe.style)
        check(shape is not None, f"{tool}：建立圖形")
        if hasattr(shape, "points"):
            shape.points = [QPoint(200, 200), QPoint(300, 300), QPoint(400, 380)]
        probe.layer.add(shape)
        before = probe.shot.crop(SELECTION).toImage()
        after = probe.render_result().toImage()
        check(before != after, f"{tool}：輸出確實被改變")
        probe.close()

    print("馬賽克真的糊掉了")
    probe = new_overlay(shot)
    # 選一塊落在條紋圖樣上的區域
    probe.selection = QRect(280, 190, 220, 120)
    probe.layer.add(annotate.MosaicShape(QPoint(300, 200), QPoint(480, 300),
                                         annotate.Style()))
    result = probe.render_result().toImage()
    original = probe.shot.crop(probe.selection).toImage()
    check(result != original, "馬賽克區域的像素有變")
    probe.close()

    print("文字")
    probe = new_overlay(shot)
    probe.layer.add(annotate.TextShape(QPoint(200, 200), "MDASH",
                                       annotate.Style(color="#f5423f", width=4)))
    check(probe.render_result().toImage() != probe.shot.crop(SELECTION).toImage(),
          "文字有被畫上去")
    empty = new_overlay(shot)
    empty.layer.add(annotate.TextShape(QPoint(200, 200), "", annotate.Style()))
    check(empty.render_result().toImage() == empty.shot.crop(SELECTION).toImage(),
          "空字串不留下任何痕跡")
    probe.close()
    empty.close()

    print("工具切換")
    probe = new_overlay(shot)
    probe.set_tool("rect")
    check(probe.tool == "rect", "選取工具")
    probe.set_tool("rect")
    check(probe.tool is None, "再按一次同一個工具即取消")
    probe.set_color("#2ecc71")
    probe.set_width(7)
    check(probe.style.color == "#2ecc71" and probe.style.width == 7, "顏色與粗細")
    probe.close()

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
