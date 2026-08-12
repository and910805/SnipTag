"""開機自動啟動測試：python test_autostart.py

用專屬的測試用值名稱，不會碰到真正的 SnipTag 啟動項。
"""
from __future__ import annotations

import sys

from sniptag import autostart

TEST_VALUE = "SnipTag-selftest"


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    print("命令列組成")
    command = autostart.launch_command()
    print(f"  {command}")
    check(command.startswith('"'), "路徑有加引號（避免空白路徑被拆開）")
    check(command.count('"') % 2 == 0, "引號成對")
    if getattr(sys, "frozen", False):
        check(".exe" in command.lower(), "打包後指向 exe 本身")
    else:
        check("python" in command.lower(), "從原始碼執行時指向 python")
        check("run.py" in command or "-m sniptag" in command, "帶著進入點")

    if not autostart.available():
        print("\n非 Windows，略過登錄檔部分。")
        return

    print("讀寫登錄檔（使用測試專用名稱）")
    real_before = autostart.is_enabled()
    try:
        check(not autostart.is_enabled(TEST_VALUE), "測試項一開始不存在")

        check(autostart.set_enabled(True, TEST_VALUE), "啟用成功")
        check(autostart.is_enabled(TEST_VALUE), "啟用後讀得到")
        check(autostart.current_command(TEST_VALUE) == command,
              "寫進去的命令與組出來的一致")

        check(autostart.set_enabled(True, TEST_VALUE, command="custom.exe"),
              "可以覆寫命令")
        check(autostart.current_command(TEST_VALUE) == "custom.exe", "覆寫生效")

        check(autostart.set_enabled(False, TEST_VALUE), "停用成功")
        check(not autostart.is_enabled(TEST_VALUE), "停用後讀不到")
        check(autostart.set_enabled(False, TEST_VALUE), "重複停用不會出錯")
        check(autostart.current_command(TEST_VALUE) == "", "命令也清掉了")
    finally:
        autostart.set_enabled(False, TEST_VALUE)

    print("沒有動到真正的 SnipTag 啟動項")
    check(autostart.is_enabled() == real_before,
          f"真實啟動項狀態不變（{real_before}）")

    print("\n全部通過。")


if __name__ == "__main__":
    main()
