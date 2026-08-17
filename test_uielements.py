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
    # 注意：不驗「面積由小到大」—— 真實的 UIA 樹裡，捲動容器的裁切矩形
    # 可能比子元素還小，順序交給 merge_into 排序。
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

    print("打穿自己的視窗（ProbeThrough）")
    # offscreen 平台（CI）的 winId 不是真實 HWND，樣式操作驗不出東西
    if sys.platform == "win32" and QApplication.platformName() == "windows":
        import ctypes

        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget

        cover = QWidget(None)
        cover.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                             | Qt.WindowStaysOnTopHint)
        cover.setGeometry(0, 0, 600, 400)
        cover.show()
        app.processEvents()

        user32 = ctypes.windll.user32
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        get_long.restype = ctypes.c_ssize_t
        get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        hwnd = int(cover.winId())
        before = get_long(hwnd, uielements.ProbeThrough.GWL_EXSTYLE)

        with uielements.ProbeThrough(cover):
            during = get_long(hwnd, uielements.ProbeThrough.GWL_EXSTYLE)
            uielements.hierarchy_at(300, 200)   # 不能爆炸
        after = get_long(hwnd, uielements.ProbeThrough.GWL_EXSTYLE)

        check(bool(during & uielements.ProbeThrough.WS_EX_TRANSPARENT),
              "查詢期間視窗對命中測試透明")
        check(bool(during & uielements.ProbeThrough.WS_EX_LAYERED),
              "而且是 layered（缺一個就打不穿）")
        check(after == before, "查完樣式完整還原")
        cover.close()
    else:
        print("  （offscreen／非 Windows，略過）")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
