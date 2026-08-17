"""UI 元素偵測測試：python test_uielements.py

UIA 的查詢結果取決於當下桌面上有什麼，所以活體查詢只驗「不會爆炸、
格式正確」；合併邏輯（merge_into）才是完整驗證。
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from sniptag import uielements


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("活體查詢（結果依桌面而定，只驗格式）")
    ok = uielements.available()
    print(f"  UIA 可用：{ok}")
    rects = uielements.hierarchy_at(200, 200)
    check(isinstance(rects, list), "回傳 list")
    for rect in rects:
        left, top, right, bottom = rect
        check(right > left and bottom > top, f"矩形合法 {rect}")
        break   # 驗一個就夠
    if len(rects) >= 2:
        areas = [(r[2] - r[0]) * (r[3] - r[1]) for r in rects]
        check(areas == sorted(areas), "由小到大排列")
    check(uielements.hierarchy_at(-99999, -99999) == [] or True,
          "亂給座標也不會爆炸")

    print("合併邏輯")
    window = QRect(0, 0, 1000, 800)
    panel = QRect(100, 100, 500, 400)
    hierarchy = [window, panel]     # 由大到小
    element = QRect(150, 150, 200, 100)
    merged = uielements.merge_into(hierarchy, [element], window)
    check(merged == [window, panel, element], "新元素插進正確的位置（面積排序）")

    merged = uielements.merge_into(hierarchy, [panel], window)
    check(merged == [window, panel], "重複的不會加第二次")

    huge = QRect(-500, -500, 5000, 5000)
    merged = uielements.merge_into(hierarchy, [huge], window)
    check(merged[0] == window and len(merged) == 2,
          "超出視窗的會被裁掉；裁完跟視窗一樣大就不重複收")

    tiny = QRect(200, 200, 8, 8)
    merged = uielements.merge_into(hierarchy, [tiny], window)
    check(merged == [window, panel], "太小的元素（游標等級）不收")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
