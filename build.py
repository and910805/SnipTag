"""打包成單一 exe：python build.py

產物是 dist/SnipTag.exe —— 免安裝、不需要對方電腦有 Python。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
ICON = BUILD / "SnipTag.ico"
NAME = "SnipTag"


def make_icon() -> Path | None:
    """用程式裡那顆圖示產生 .ico，免得再多一個要維護的二進位檔。"""
    from PySide6.QtGui import QGuiApplication  # noqa: F401 - 需要 QApplication
    from PySide6.QtWidgets import QApplication

    from sniptag.icon import write_ico

    app = QApplication.instance() or QApplication([])
    ICON.parent.mkdir(parents=True, exist_ok=True)
    ok = write_ico(ICON)
    del app
    return ICON if ok else None


def main() -> int:
    sys.path.insert(0, str(ROOT))
    icon = make_icon()
    if icon is None:
        print("!! 圖示產生失敗，改用預設圖示")

    for stale in (DIST / f"{NAME}.exe", ROOT / f"{NAME}.spec"):
        stale.unlink(missing_ok=True)
    shutil.rmtree(BUILD / NAME, ignore_errors=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--noconsole",
        "--name", NAME,
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        "--distpath", str(DIST),
        # 用不到的 Qt 模組排掉，檔案小很多
        "--exclude-module", "PySide6.QtNetwork",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
    ]
    if icon is not None:
        command += ["--icon", str(icon)]
    command.append(str(ROOT / "run.py"))

    print("執行：", " ".join(command[1:]), "\n")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe = DIST / f"{NAME}.exe"
    if not exe.exists():
        print("!! 找不到產物", exe)
        return 1
    print(f"\n完成：{exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
