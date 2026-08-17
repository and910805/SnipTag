"""滾動截圖拼接測試：python test_scroll.py

做法是反過來驗證：先造一張長圖當「整篇文章」，照已知的捲動量切出一張張
畫面餵給拼接器，最後檢查接出來的結果跟原圖一不一樣。
"""
from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from sniptag import scroll

WIDTH = 420
VIEW = 300          # 「視窗」高度
ARTICLE = 1800      # 「文章」總高度


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def build_article(height: int = ARTICLE) -> QImage:
    """一張夠有變化的長圖：每一列都長得不一樣，才驗得出對齊有沒有跑掉。"""
    image = QImage(WIDTH, height, QImage.Format_RGB32)
    image.fill(QColor(252, 252, 250))
    painter = QPainter(image)
    font = QFont("Consolas")
    font.setPixelSize(15)
    painter.setFont(font)
    for line in range(height // 26):
        top = line * 26
        painter.setPen(QColor(20 + (line * 7) % 90, 20, 30))
        painter.drawText(14, top + 18, f"{line:04d} 這是第 {line} 行的內容 abcdefg")
        if line % 5 == 0:
            painter.fillRect(QRect(0, top, WIDTH, 3),
                             QColor((line * 29) % 256, 90, 160))
    painter.end()
    return image


def frame_at(article: QImage, offset: int) -> QImage:
    return article.copy(QRect(0, offset, WIDTH, VIEW))


def images_equal(left: QImage, right: QImage) -> bool:
    if left.size() != right.size():
        return False
    return left.convertToFormat(QImage.Format_RGB32) == \
        right.convertToFormat(QImage.Format_RGB32)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    article = build_article()

    print("特徵擷取")
    signature = scroll.to_signature(frame_at(article, 0))
    check(signature.shape[0] == VIEW, f"列數等於畫面高度（{signature.shape[0]}）")
    check(signature.shape[1] <= scroll.COLUMNS, "直行數有壓縮")
    check(signature.dtype == np.int16, "用有號整數，相減不會溢位")
    narrow = QImage(7, 20, QImage.Format_RGB32)     # 寬度不是 4 的倍數
    narrow.fill(QColor(10, 20, 30))
    check(scroll.to_signature(narrow).shape == (20, 7),
          "寬度非 4 倍數時仍正確（bytesPerLine 有補齊）")

    print("找重疊")
    for shift in (12, 45, 137, 200):
        previous = scroll.to_signature(frame_at(article, 0))
        current = scroll.to_signature(frame_at(article, shift))
        match = scroll.find_overlap(previous, current)
        check(match.advance == shift,
              f"捲 {shift} 像素 -> 算出 {match.advance}")
        check(match.confident, f"捲 {shift} 判定為可信（差異 {match.score:.2f}）")

    same = scroll.to_signature(frame_at(article, 500))
    match = scroll.find_overlap(same, same)
    check(match.advance == 0, "同一張畫面 -> 位移 0")

    print("整篇拼接")
    stitcher = scroll.Stitcher()
    offsets = list(range(0, ARTICLE - VIEW + 1, 60))
    for offset in offsets:
        stitcher.add(frame_at(article, offset))
    result = stitcher.result()
    expected_height = offsets[-1] + VIEW
    check(result is not None, "有產出結果")
    check(result.height() == expected_height,
          f"高度 {result.height()} 應為 {expected_height}")
    check(result.width() == WIDTH, "寬度不變")
    check(images_equal(result, article.copy(QRect(0, 0, WIDTH, expected_height))),
          "接出來的長圖與原文逐像素相同")
    check(stitcher.rejected == 0, "沒有任何一張被判定接不起來")

    print("捲動量不固定也要接得起來")
    stitcher = scroll.Stitcher()
    position, positions = 0, [0]
    for step in (33, 120, 17, 205, 64, 150, 90):
        position += step
        positions.append(position)
        stitcher.add(frame_at(article, positions[-2]))
    stitcher.add(frame_at(article, position))
    result = stitcher.result()
    check(images_equal(result, article.copy(QRect(0, 0, WIDTH, position + VIEW))),
          f"忽快忽慢地捲到 {position} 也完全吻合")

    print("原地不動與重複畫面")
    stitcher = scroll.Stitcher()
    stitcher.add(frame_at(article, 0))
    before = stitcher.height
    check(stitcher.add(frame_at(article, 0)) == 0, "同一張 -> 沒有新內容")
    check(stitcher.add(frame_at(article, 2)) == 0,
          f"只動 2 像素（小於 {scroll.MIN_ADVANCE}）-> 當作沒動")
    check(stitcher.height == before, "高度沒有增加")
    check(len(stitcher) == 1, "重複的畫面不會被收進來")

    print("跳太遠、完全沒有重疊")
    stitcher = scroll.Stitcher()
    stitcher.add(frame_at(article, 0))
    added = stitcher.add(frame_at(article, 1200))
    check(added == 0, "沒有重疊就不接")
    check(stitcher.rejected == 1, "會記錄下來，讓上層可以提示使用者")

    print("局部變動（游標閃爍之類）仍要接得起來")
    stitcher = scroll.Stitcher()
    stitcher.add(frame_at(article, 0))
    blinking = frame_at(article, 80)
    painter = QPainter(blinking)
    painter.fillRect(QRect(300, 40, 12, 16), QColor(0, 0, 0))
    painter.end()
    check(stitcher.add(blinking) > 0, "畫面上多一個小游標不影響對齊")

    print("尺寸改變（切到別的視窗）")
    stitcher = scroll.Stitcher()
    stitcher.add(frame_at(article, 0))
    check(stitcher.add(article.copy(QRect(0, 0, WIDTH - 40, VIEW))) == 0,
          "寬度不同就忽略")
    check(stitcher.rejected == 1, "同樣會被記錄")

    print("往回捲")
    stitcher = scroll.Stitcher()
    stitcher.add(frame_at(article, 300))
    check(stitcher.add(frame_at(article, 200)) == 0, "往回捲不會接在後面")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
