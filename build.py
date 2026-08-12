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
VERSION_FILE = BUILD / "version_info.txt"
NAME = "SnipTag"

# 寫進 exe 的檔案內容資訊。沒有這一段的話，Windows 的檔案內容頁全是空白，
# 防毒與 SmartScreen 會顯示成「不明的發行者」「沒有名稱」。
PUBLISHER = "and910805"
DESCRIPTION = "SnipTag 截圖工具"
REPOSITORY = "https://github.com/and910805/SnipTag"

VERSION_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers}, prodvers={numbers},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040404b0',
        [StringStruct('CompanyName', {publisher!r}),
         StringStruct('FileDescription', {description!r}),
         StringStruct('FileVersion', {version!r}),
         StringStruct('InternalName', 'SnipTag'),
         StringStruct('LegalCopyright', {copyright!r}),
         StringStruct('OriginalFilename', 'SnipTag.exe'),
         StringStruct('ProductName', 'SnipTag'),
         StringStruct('ProductVersion', {version!r}),
         StringStruct('Comments', {repository!r})])
    ]),
    VarFileInfo([VarStruct('Translation', [1028, 1200])])
  ]
)
"""


def write_version_file() -> Path:
    """產生 PyInstaller 用的版本資源檔。"""
    sys.path.insert(0, str(ROOT))
    from sniptag import __version__

    parts = [int(p) for p in __version__.split(".")][:4]
    while len(parts) < 4:
        parts.append(0)

    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(VERSION_TEMPLATE.format(
        numbers=tuple(parts),
        publisher=PUBLISHER,
        description=DESCRIPTION,
        version=__version__,
        copyright=f"Copyright (c) 2026 {PUBLISHER} — MIT License",
        repository=REPOSITORY,
    ), encoding="utf-8")
    return VERSION_FILE


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
    version_file = write_version_file()

    for stale in (DIST / f"{NAME}.exe", ROOT / f"{NAME}.spec"):
        stale.unlink(missing_ok=True)
    shutil.rmtree(BUILD / NAME, ignore_errors=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--noconsole",
        "--name", NAME,
        "--version-file", str(version_file),
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
