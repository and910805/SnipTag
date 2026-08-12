"""使用教學測試：python test_welcome.py"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from sniptag import autostart
from sniptag.config import DEFAULTS
from sniptag.welcome import PAGES, WelcomeDialog


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    config = dict(DEFAULTS)
    dialog = WelcomeDialog(config)

    print("頁面")
    check(dialog.stack.count() == len(PAGES), f"共 {len(PAGES)} 頁")
    check(all(not WelcomeDialog._illustration(fn).isNull()
              for _title, fn, _body in PAGES), "每頁的示意圖都畫得出來")
    check(dialog.stack.currentIndex() == 0, "從第一頁開始")

    print("導覽")
    check(not dialog.back_button.isEnabled(), "第一頁不能上一步")
    check(dialog.next_button.text() == "下一步", "還沒到最後一頁")
    check(dialog.skip_button.isVisible() or not dialog.isVisible(),
          "非最後一頁有略過鈕")

    dialog.go(1)
    check(dialog.stack.currentIndex() == 1, "下一步")
    check(dialog.back_button.isEnabled(), "第二頁可以回上一步")
    dialog.go(-1)
    check(dialog.stack.currentIndex() == 0, "上一步")
    dialog.go(-1)
    check(dialog.stack.currentIndex() == 0, "第一頁再往前不會變成負的")

    for _ in range(len(PAGES) - 1):
        dialog.go(1)
    check(dialog.stack.currentIndex() == len(PAGES) - 1, "走到最後一頁")
    check(dialog.next_button.text() == "完成", "最後一頁按鈕變成完成")
    check(dialog.step_label.text() == f"{len(PAGES)} / {len(PAGES)}", "頁碼正確")

    print("開機自動啟動勾選框")
    check(dialog.autostart_check.isChecked() == autostart.is_enabled(),
          "初始狀態跟登錄檔一致")
    check(dialog.autostart_check.isEnabled() == autostart.available(),
          "非 Windows 會停用")
    dialog.autostart_check.setChecked(True)
    check(dialog.wants_autostart(), "勾選後 wants_autostart 為 True")
    dialog.autostart_check.setChecked(False)
    check(not dialog.wants_autostart(), "取消勾選後為 False")
    dialog.close()

    print("設定旗標")
    check(DEFAULTS["seen_welcome"] is False, "預設沒看過，第一次啟動才會跳")

    print("\n全部通過。")
    del app


if __name__ == "__main__":
    main()
