"""截圖歷史測試：python test_history.py"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from sniptag.history import History, HistoryDialog


class FakeApp:
    """記下 HistoryDialog 呼叫了什麼，不真的動到檔案。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def pin_centered(self, _pixmap):
        self.calls.append("pin")

    def save_pixmap(self, _pixmap, record=True):
        self.calls.append(f"save(record={record})")
        return type("P", (), {"name": "MDASH_07.png"})()

    def copy_to_clipboard(self, _pixmap):
        self.calls.append("copy")


def swatch(size: int = 40) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.red)
    return pixmap


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("上限與順序")
    history = History(limit=3)
    check(len(history) == 0, "一開始是空的")
    for index in range(5):
        history.add(swatch(10 + index), f"shot_{index}.png")
    check(len(history) == 3, "超過上限只留最近 3 張")
    check(history.latest().name == "shot_4.png", "最新的在最後")
    check([e.name for e in history.entries]
          == ["shot_2.png", "shot_3.png", "shot_4.png"], "舊的被擠掉")

    print("複製而非參考")
    original = swatch(20)
    entry = history.add(original, "copy.png")
    original.fill(Qt.blue)
    check(entry.pixmap.toImage().pixelColor(1, 1) == Qt.red,
          "歷史留的是當下的副本，之後改動原圖不影響")

    print("刪除與清空")
    target = history.latest()
    history.remove(target)
    check(target not in history.entries, "刪除指定項目")
    history.remove(target)
    check(True, "重複刪除不會爆掉")
    history.clear()
    check(len(history) == 0 and history.latest() is None, "清空")

    print("對話框")
    history = History()
    history.add(swatch(30), "MDASH_01.png")
    history.add(swatch(30))
    fake = FakeApp()
    dialog = HistoryDialog(history, fake)
    check(dialog.list.count() == 2, "兩個項目都列出來")
    check(dialog.selected() is history.entries[-1], "預設選最新的那張")

    dialog.pin_selected()
    dialog.copy_selected()
    check(fake.calls == ["pin", "copy"], "釘選與複製會轉給主程式")

    dialog.save_selected()
    check(fake.calls[-1] == "save(record=False)",
          "從歷史存檔不會再寫回歷史（避免無限增生）")
    check(dialog.selected().name == "MDASH_07.png", "存檔後標籤更新成檔名")

    dialog.delete_selected()
    check(dialog.list.count() == 1 and len(history) == 1, "刪除後清單同步")
    dialog.clear_all()
    check(dialog.list.count() == 0 and dialog.selected() is None, "全部清除")
    dialog.close()

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
