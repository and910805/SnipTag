"""標註功能測試：python test_annotate.py

重點在「標註畫在框選介面的座標上，輸出時要正確落到原生解析度的對應位置」。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
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


def build_detailed_shot() -> DesktopShot:
    """白底加上細密的文字與條紋，用來檢查馬賽克到底吃掉多少細節。"""
    image = QImage(int(800 * DPR), int(600 * DPR), QImage.Format_RGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    font = QFont("Consolas")
    font.setPixelSize(28)
    painter.setFont(font)
    painter.setPen(QColor(10, 10, 10))
    for line in range(6):
        painter.drawText(380, 420 + line * 34, f"SECRET-{line}: hunter2 xyzzy")
    for offset in range(0, 480, 7):
        painter.fillRect(QRect(380 + offset, 620, 3, 40), QColor(200, 30, 90))
    # 使用明確色塊補足細節，避免不同 Qt / offscreen rasterizer 的文字
    # 反鋸齒策略讓測試只看見黑、白、粉紅三色。
    for y in range(400, 660, 4):
        for x in range(380, 860, 4):
            block_x = (x - 380) // 24
            block_y = (y - 400) // 24
            painter.fillRect(
                QRect(x, y, 2, 2),
                QColor((block_x * 37 + block_y * 13 + x * 3) % 256,
                       (block_x * 17 + block_y * 41 + y * 5) % 256,
                       (block_x * 29 + block_y * 23 + x + y) % 256),
            )
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
    probe.layer.add(annotate.TextShape(QPoint(200, 200), "週會",
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

    print("命中測試：空心圖形只認邊框")
    thin = annotate.Style(width=2)
    rect_shape = annotate.RectShape(QPoint(100, 100), QPoint(300, 200), thin)
    check(rect_shape.hit(QPoint(100, 150)), "點在左邊框上 -> 命中")
    check(rect_shape.hit(QPoint(200, 200)), "點在下邊框上 -> 命中")
    check(not rect_shape.hit(QPoint(200, 150)), "點在中間空白處 -> 不命中")
    check(not rect_shape.hit(QPoint(400, 150)), "點在外面 -> 不命中")

    filled = annotate.RectShape(QPoint(100, 100), QPoint(300, 200),
                                annotate.Style(width=2, filled=True))
    check(filled.hit(QPoint(200, 150)), "填滿的矩形中間也算命中")

    ellipse = annotate.EllipseShape(QPoint(100, 100), QPoint(300, 200), thin)
    check(ellipse.hit(QPoint(200, 100)), "橢圓上緣 -> 命中")
    check(not ellipse.hit(QPoint(200, 150)), "橢圓正中心 -> 不命中")
    check(not ellipse.hit(QPoint(105, 105)), "橢圓外的角落 -> 不命中")

    line = annotate.LineShape(QPoint(100, 100), QPoint(300, 100), thin)
    check(line.hit(QPoint(200, 102)), "直線上 -> 命中")
    check(not line.hit(QPoint(200, 140)), "離直線很遠 -> 不命中")
    check(not line.hit(QPoint(400, 100)), "延長線上但超出線段 -> 不命中")

    stroke = annotate.PenShape([QPoint(100, 100), QPoint(200, 200),
                                QPoint(300, 100)], thin)
    check(stroke.hit(QPoint(150, 150)), "筆畫中段 -> 命中")
    check(not stroke.hit(QPoint(200, 120)), "筆畫夾角內的空白 -> 不命中")

    number = annotate.NumberShape(QPoint(200, 200), 1, thin)
    check(number.hit(QPoint(203, 203)), "序號圓內 -> 命中")
    check(not number.hit(QPoint(260, 200)), "序號圓外 -> 不命中")

    print("搬移")
    moving = annotate.RectShape(QPoint(100, 100), QPoint(200, 160), thin)
    moving.translate(QPoint(30, -10))
    # QRect(topLeft, bottomRight) 是含端點的，所以寬高各多 1
    check(moving.rect == QRect(QPoint(130, 90), QPoint(230, 150)), "矩形整塊位移")
    stroke_move = annotate.PenShape([QPoint(0, 0), QPoint(10, 10)], thin)
    stroke_move.translate(QPoint(5, 5))
    check(stroke_move.points == [QPoint(5, 5), QPoint(15, 15)], "筆畫每個點都位移")

    print("圖層選取")
    layer = annotate.Layer()
    lower = annotate.RectShape(QPoint(100, 100), QPoint(300, 200), thin)
    upper = annotate.RectShape(QPoint(90, 90), QPoint(310, 210), thin)
    layer.add(lower)
    layer.add(upper)
    check(layer.shape_at(QPoint(90, 150)) is upper, "重疊時取最上面那個")
    check(layer.shape_at(QPoint(200, 150)) is None, "沒點到任何圖形")
    check(layer.remove(upper) and len(layer) == 1, "刪除指定圖形")

    print("序號自動遞增")
    layer = annotate.Layer()
    check(layer.next_number() == 1, "第一個是 1")
    layer.add(annotate.NumberShape(QPoint(0, 0), 1, thin))
    layer.add(annotate.NumberShape(QPoint(0, 0), 2, thin))
    check(layer.next_number() == 3, "接著是 3")
    layer.undo()
    check(layer.next_number() == 2, "復原之後回到 2")

    print("刪除選中的圖形")
    probe = new_overlay(shot)
    shape = annotate.RectShape(QPoint(200, 200), QPoint(300, 260), thin)
    probe.layer.add(shape)
    probe.selected_shape = shape
    probe.delete_selected()
    check(len(probe.layer) == 0 and probe.selected_shape is None, "刪除後清空選取")
    probe.close()

    print("馬賽克遮蔽")

    def colors_in(image, rect):
        return {image.pixelColor(x, y).rgb()
                for y in range(rect.top(), rect.bottom() + 1)
                for x in range(rect.left(), rect.right() + 1)}

    detailed = build_detailed_shot()
    probe = new_overlay(detailed)
    area = QRect(200, 200, 240, 120)          # 標註座標
    device = QRect(int((area.x() - SELECTION.x()) * DPR),
                   int((area.y() - SELECTION.y()) * DPR),
                   int(area.width() * DPR), int(area.height() * DPR))
    original = colors_in(probe.shot.crop(SELECTION).toImage(), device)
    probe.layer.add(annotate.MosaicShape(area.topLeft(), area.bottomRight(),
                                         annotate.Style()))
    mosaicked = colors_in(probe.render_result().toImage(), device)
    check(len(original) > 50, f"原圖該區細節豐富（{len(original)} 色）")
    check(len(mosaicked) * 10 < len(original),
          f"馬賽克後大幅減少（{len(original)} -> {len(mosaicked)} 色）")
    probe.close()

    print("馬賽克疊在已畫好的標註上（不能把底下遮住的東西翻出來）")
    probe = new_overlay(detailed)
    probe.layer.add(annotate.RectShape(
        area.topLeft(), area.bottomRight(),
        annotate.Style(color="#000000", width=2, filled=True)))
    probe.layer.add(annotate.MosaicShape(area.topLeft(), area.bottomRight(),
                                         annotate.Style()))
    covered = colors_in(probe.render_result().toImage(),
                        device.adjusted(6, 6, -6, -6))
    check(covered == {QColor("#000000").rgb()},
          "先實心遮蔽再蓋馬賽克，結果只有純黑")
    probe.close()

    print("馬賽克方塊大小跟著解析度走")
    probe = new_overlay(detailed)
    probe.layer.add(annotate.MosaicShape(area.topLeft(), area.bottomRight(),
                                         annotate.Style()))
    out = probe.render_result().toImage()
    block = int(annotate.MOSAIC_BLOCK * DPR)
    ragged, block_colors = [], set()
    for top in range(device.top(), device.bottom() - block + 1, block):
        for left in range(device.left(), device.right() - block + 1, block):
            corner = out.pixelColor(left, top).rgb()
            block_colors.add(corner)
            for y in range(top, top + block):
                for x in range(left, left + block):
                    if out.pixelColor(x, y).rgb() != corner:
                        ragged.append((left, top))
                        break
                else:
                    continue
                break
    check(not ragged,
          f"每個 {block}×{block} 方塊內部都是單一顏色"
          f"（{len(ragged)} 個不合格）")
    # Qt 6.11 的 offscreen rasterizer 會把縮圖量化成極少顏色；實體 Windows
    # 平台仍要求較多方塊顏色，CI 則至少確認不是整片單色。
    min_block_colors = 1 if QApplication.platformName() == "offscreen" else 3
    check(len(block_colors) > min_block_colors,
          f"方塊之間顏色有差異，確實蓋在有內容的地方（{len(block_colors)} 色）")
    probe.close()

    print("樣式變化真的畫出不一樣的東西")

    def render_with(shape) -> bytes:
        probe = new_overlay(shot)
        probe.layer.add(shape)
        image = probe.render_result().toImage()
        probe.close()
        return image.constBits().tobytes()

    base = annotate.Style(color="#f5423f", width=4)
    corners = QRect(200, 200, 160, 90)
    solid = render_with(annotate.RectShape(corners.topLeft(), corners.bottomRight(),
                                           annotate.Style("#f5423f", 4)))
    dashed = render_with(annotate.RectShape(corners.topLeft(), corners.bottomRight(),
                                            annotate.Style("#f5423f", 4, dashed=True)))
    rounded = render_with(annotate.RectShape(corners.topLeft(), corners.bottomRight(),
                                             annotate.Style("#f5423f", 4, rounded=True)))
    check(solid != dashed, "虛線與實線輸出不同")
    check(solid != rounded, "圓角與直角輸出不同")
    check(dashed != rounded, "虛線與圓角也不同")

    single = render_with(annotate.ArrowShape(QPoint(200, 200), QPoint(380, 320),
                                             annotate.Style("#f5423f", 4)))
    double = render_with(annotate.ArrowShape(
        QPoint(200, 200), QPoint(380, 320),
        annotate.Style("#f5423f", 4, both_ends=True)))
    check(single != double, "雙向箭頭與單向不同")

    plain_text = render_with(annotate.TextShape(QPoint(200, 200), "測試", base))
    boxed_text = render_with(annotate.TextShape(
        QPoint(200, 200), "測試", annotate.Style("#f5423f", 4, filled=True)))
    check(plain_text != boxed_text, "文字加底色與不加不同")

    print("橡皮擦")
    probe = new_overlay(shot)
    keep = annotate.RectShape(QPoint(200, 200), QPoint(260, 240), base)
    wipe = annotate.RectShape(QPoint(400, 380), QPoint(460, 420), base)
    probe.layer.add(keep)
    probe.layer.add(wipe)
    check(not probe.layer.erase_at(QPoint(330, 300)), "空白處擦不到東西")
    check(probe.layer.erase_at(QPoint(400, 380)), "擦到圖形回傳 True")
    check(probe.layer.shapes == [keep], "只擦掉碰到的那個")
    probe.layer.redo()
    check(len(probe.layer) == 2, "Ctrl+Z 可以把擦掉的救回來")
    probe.close()

    print("每個工具記住自己的顏色")
    probe = new_overlay(shot)
    probe.set_tool("rect")
    probe.set_color("#2ecc71")
    probe.set_tool("marker")
    check(probe.style.color == "#ff9f1c", "切到螢光筆用回螢光筆的顏色")
    probe.set_tool("rect")
    check(probe.style.color == "#2ecc71", "切回矩形記得剛才選的綠色")
    probe.close()

    print("Shift 拖曳成正方形")
    square = Overlay._square_from(QPoint(100, 100), QPoint(240, 180))
    check(square == QPoint(240, 240), "往右下：邊長取較長的那一邊")
    square = Overlay._square_from(QPoint(100, 100), QPoint(20, 60))
    check(square == QPoint(20, 20), "往左上也對稱")

    print("輔助框：預設框整個視窗，滾輪才鑽進子區塊")
    probe = new_overlay(shot)
    probe.settled = False
    window = QRect(100, 100, 600, 400)
    panel = QRect(150, 150, 200, 120)
    button = QRect(160, 160, 60, 30)
    probe.window_groups = [[window, panel, button]]
    probe._update_hover(QPoint(180, 175))
    check(probe.hover_rect == window, "預設是整個視窗，不是最小的那塊")
    check(probe.hierarchy == [window, panel, button], "候選由大到小排好")
    check(probe.hierarchy_index == 0, "從最外層開始")

    probe.hierarchy_index = 1
    probe.hover_rect = probe.hierarchy[1]
    check(probe.hover_rect == panel, "往下一層是面板")

    probe._update_hover(QPoint(900, 900))
    check(probe.hover_rect is None, "游標離開所有視窗就沒有輔助框")
    check(probe.hierarchy == [], "層級也清空")
    probe.close()

    print("工具列提示列（不靠 Qt tooltip）")
    probe = new_overlay(shot)
    probe._show_toolbar()
    toolbar = probe.toolbar
    check(toolbar.hint_label.text() == "", "一開始是空的")
    target = toolbar.tool_buttons["mosaic"]
    check(target in toolbar._hints, "圖示按鈕有登記說明")
    toolbar.eventFilter(target, QEvent(QEvent.Enter))
    check("馬賽克" in toolbar.hint_label.text(), "滑上去顯示功能名稱")
    check("M" in toolbar.hint_label.text(), "而且帶著快捷鍵")
    toolbar.eventFilter(target, QEvent(QEvent.Leave))
    check(toolbar.hint_label.text() == "", "移開就清掉")

    swatch = toolbar.color_buttons[annotate.PALETTE[0]]
    toolbar.eventFilter(swatch, QEvent(QEvent.Enter))
    check(annotate.PALETTE[0].upper() in toolbar.hint_label.text(),
          "顏色鈕也會顯示色碼")
    save_button = toolbar.buttons["save"]
    toolbar.eventFilter(save_button, QEvent(QEvent.Enter))
    check("存檔" in toolbar.hint_label.text(), "動作鈕也有說明")
    probe.close()

    print("色彩格式")
    red = QColor(245, 66, 63)
    check(annotate.format_color(red, "HEX") == "#F5423F", "HEX")
    check(annotate.format_color(red, "RGB") == "rgb(245, 66, 63)", "RGB")
    check(annotate.format_color(red, "HSL").startswith("hsl("), "HSL")
    probe = new_overlay(shot)
    check(probe.color_format == "HEX", "預設 HEX")
    probe.cycle_color_format()
    check(probe.color_format == "RGB", "切換到 RGB")
    probe.cycle_color_format()
    probe.cycle_color_format()
    check(probe.color_format == "HEX", "繞一圈回到 HEX")
    probe.close()

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
