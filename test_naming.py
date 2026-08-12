"""命名邏輯的測試（不需要 GUI）：python test_naming.py"""
from __future__ import annotations

import datetime as dt
import shutil
import tempfile
from pathlib import Path

from sniptag.naming import Namer, sanitize


class FakeConfig(dict):
    """夠用的假設定物件：Namer 只需要 dict 存取加 save_root。"""

    @property
    def save_root(self) -> Path:
        return Path(self["save_dir"])


def make_config(tmp: Path, **overrides) -> FakeConfig:
    cfg = FakeConfig({
        "save_dir": str(tmp),
        "topic": "MDASH",
        "template": "{topic}_{n:02d}",
        "format": "png",
        "subfolder_per_topic": False,
    })
    cfg.update(overrides)
    return cfg


def check(condition: bool, label: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + label)
    assert condition, label


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sniptag_test_"))
    try:
        cfg = make_config(tmp)
        namer = Namer(cfg)

        print("流水號")
        check(namer.preview() == "MDASH_01.png", "空資料夾 → MDASH_01.png")
        for expected in ("MDASH_01.png", "MDASH_02.png", "MDASH_03.png"):
            path = namer.next_path()
            check(path.name == expected, f"連號 {expected}")
            path.write_bytes(b"x")

        print("換主題")
        cfg["topic"] = "AI導入"
        check(namer.preview() == "AI導入_01.png", "新主題從 01 開始")
        (tmp / "AI導入_01.png").write_bytes(b"x")
        check(namer.preview() == "AI導入_02.png", "新主題接著 02")
        cfg["topic"] = "MDASH"
        check(namer.preview() == "MDASH_04.png", "切回舊主題接續 04")

        print("刪中間不會覆蓋")
        (tmp / "MDASH_02.png").unlink()
        check(namer.preview() == "MDASH_04.png", "空缺不回填，仍是 04")

        print("樣板")
        cfg["template"] = "{date}_{topic}_{n:03d}"
        today = dt.datetime.now().strftime("%Y%m%d")
        check(namer.preview() == f"{today}_MDASH_001.png", "日期樣板 + 三位數")
        cfg["template"] = "{topic}-{n}"
        check(namer.preview() == "MDASH-1.png", "無補零")

        print("格式與子資料夾")
        cfg["template"] = "{topic}_{n:02d}"
        cfg["format"] = "jpg"
        check(namer.preview() == "MDASH_01.jpg", "換副檔名後編號獨立計算")
        cfg["format"] = "png"
        cfg["subfolder_per_topic"] = True
        check(namer.target_dir() == tmp / "MDASH", "子資料夾路徑")
        check(namer.preview() == "MDASH_01.png", "子資料夾內從 01 開始")

        print("非法字元")
        check(sanitize('a/b:c*d?') == "a_b_c_d_", "檔名字元清洗")
        cfg["subfolder_per_topic"] = False
        cfg["topic"] = "8/12 會議"
        check(namer.preview() == "8_12 會議_01.png", "主題含斜線也能存")

        print("\n全部通過。")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
