"""SnipTag 設定檔：存放於 %APPDATA%\\SnipTag\\config.json"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

APP_NAME = "SnipTag"

DEFAULTS = {
    # 存檔
    "save_dir": str(Path.home() / "Pictures" / "SnipTag"),
    "topic": "Topic",
    "template": "{topic}_{n:02d}",
    "format": "png",              # png / jpg
    "jpeg_quality": 92,
    "subfolder_per_topic": False,  # 每個主題開一個子資料夾
    # 行為
    "copy_on_save": True,          # 存檔同時複製到剪貼簿
    "notify_on_save": True,        # 存檔後跳通知
    "record_cancelled": False,     # 連按 Esc 取消的截圖也收進歷史
    "recent_topics": [],
    # 輸出效果
    "round_corners": 0,            # 圓角半徑（邏輯像素，0 = 直角）
    "drop_shadow": False,
    "add_border": False,
    # 熱鍵
    "hotkey_capture": "F1",         # 框選截圖（出現工具列）
    "hotkey_quickshot": "Shift+F1",  # 快速截圖：放開滑鼠直接存檔
    "hotkey_pin": "F3",             # 剪貼簿內容釘到桌面
    "hotkey_topic": "Ctrl+F1",      # 快速切換主題
    "hotkey_repeat": "Ctrl+Shift+F1",   # 重複上次的框選範圍
    "hotkey_hide_pins": "Shift+F3",     # 全部釘圖隱藏 / 顯示
}

MAX_RECENT = 12


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME


CONFIG_PATH = config_dir() / "config.json"


class Config(dict):
    """設定就是一個 dict，任何寫入後呼叫 save() 即持久化。"""

    def __init__(self) -> None:
        super().__init__(copy.deepcopy(DEFAULTS))
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key, value in raw.items():
            if key in DEFAULTS:
                self[key] = value

    def save(self) -> None:
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(self, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    # --- 便利方法 -------------------------------------------------
    def set_topic(self, topic: str) -> None:
        topic = (topic or "").strip() or "Topic"
        self["topic"] = topic
        recent = [t for t in self["recent_topics"] if t != topic]
        recent.insert(0, topic)
        self["recent_topics"] = recent[:MAX_RECENT]
        self.save()

    @property
    def save_root(self) -> Path:
        return Path(self["save_dir"]).expanduser()
