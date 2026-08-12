"""自動命名：把「主題 + 流水號」變成檔名，例如 MDASH_01.png。

編號是掃描目的資料夾算出來的（不是記在設定檔），所以刪檔、換主題、
重開程式都不會亂掉 —— 永遠接在現有最大號後面。
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

# 樣板中的欄位，例如 {topic}、{n:02d}、{date}
FIELD_RE = re.compile(r"\{([a-zA-Z_]+)(:[^}]*)?\}")

# 檔名不能出現的字元
ILLEGAL_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    return ILLEGAL_RE.sub("_", name).strip().rstrip(".") or "Topic"


class Namer:
    """依設定產生下一個檔名。"""

    def __init__(self, config) -> None:
        self.cfg = config

    # --- 欄位值 ---------------------------------------------------
    def values(self) -> dict:
        now = _dt.datetime.now()
        return {
            "topic": sanitize(self.cfg["topic"]),
            "date": now.strftime("%Y%m%d"),
            "date2": now.strftime("%m-%d"),
            "time": now.strftime("%H%M%S"),
            "datetime": now.strftime("%Y%m%d_%H%M%S"),
        }

    def target_dir(self) -> Path:
        root = self.cfg.save_root
        if self.cfg["subfolder_per_topic"]:
            root = root / sanitize(self.cfg["topic"])
        return root

    @property
    def ext(self) -> str:
        return "jpg" if str(self.cfg["format"]).lower() in ("jpg", "jpeg") else "png"

    # --- 核心 -----------------------------------------------------
    def render(self, index: int) -> str:
        values = self.values()
        values["n"] = index
        try:
            stem = self.cfg["template"].format(**values)
        except (KeyError, ValueError, IndexError):
            # 樣板寫壞了就退回預設，至少不會存不了檔
            stem = "{topic}_{n:02d}".format(**values)
        return f"{sanitize(stem)}.{self.ext}"

    def _pattern(self) -> re.Pattern | None:
        """把樣板轉成 regex，用來認出資料夾裡已存在的同系列檔案。"""
        template = self.cfg["template"]
        if "{n" not in template:
            return None
        values = self.values()
        parts: list[str] = []
        pos = 0
        for m in FIELD_RE.finditer(template):
            parts.append(re.escape(template[pos:m.start()]))
            field, spec = m.group(1), (m.group(2) or "")[1:]
            if field == "n":
                parts.append(r"(?P<n>\d+)")
            else:
                try:
                    text = format(values.get(field, ""), spec)
                except (ValueError, TypeError):
                    text = str(values.get(field, ""))
                parts.append(re.escape(sanitize(text)))
            pos = m.end()
        parts.append(re.escape(template[pos:]))
        return re.compile("^" + "".join(parts) + r"\." + self.ext + "$", re.IGNORECASE)

    def next_index(self) -> int:
        pattern = self._pattern()
        if pattern is None:
            return 1
        directory = self.target_dir()
        largest = 0
        try:
            entries = list(directory.iterdir())
        except OSError:
            return 1
        for entry in entries:
            if not entry.is_file():
                continue
            m = pattern.match(entry.name)
            if m:
                largest = max(largest, int(m.group("n")))
        return largest + 1

    def preview(self) -> str:
        """下一張會被存成什麼名字（給工具列顯示用）。"""
        return self.render(self.next_index())

    def next_path(self) -> Path:
        """保留一個實際可寫入的路徑（必要時自動跳號避免覆蓋）。"""
        directory = self.target_dir()
        directory.mkdir(parents=True, exist_ok=True)
        index = self.next_index()
        for _ in range(10000):
            path = directory / self.render(index)
            if not path.exists():
                return path
            index += 1
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return directory / f"{sanitize(self.cfg['topic'])}_{stamp}.{self.ext}"
