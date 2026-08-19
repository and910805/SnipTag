"""建立可上傳至 Microsoft Partner Center 的 unsigned MSIX。

用法：
    python build_msix.py
    python build_msix.py --skip-exe   # 已經有 dist/SnipTag.exe 時

Store 會在認證通過後以 Microsoft 憑證重新簽署套件。這個 unsigned MSIX
只適合上傳 Partner Center，不應直接提供給一般使用者安裝。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
LAYOUT = BUILD / "msix" / "layout"
ASSETS = LAYOUT / "Assets"
MANIFEST_TEMPLATE = ROOT / "packaging" / "AppxManifest.xml.template"

# 固定版本讓本機與 GitHub Actions 使用完全相同的 Microsoft 官方工具。
WINDOWS_SDK_BUILD_TOOLS_VERSION = "10.0.26100.8249"
# Partner Center 保留第四段給 Store 使用，上傳套件必須以 0 結尾。
# Store 更新套件必須高於目前已發布的版本，並與應用程式 1.3.1 對齊。
MSIX_VERSION = "1.3.1.0"
WINDOWS_SDK_PACKAGE_URL = (
    "https://www.nuget.org/api/v2/package/"
    f"Microsoft.Windows.SDK.BuildTools/{WINDOWS_SDK_BUILD_TOOLS_VERSION}"
)


def store_version() -> str:
    parts = [int(part) for part in MSIX_VERSION.split(".")]
    if len(parts) != 4:
        raise ValueError("MSIX 版本號必須剛好有四段")
    if any(part < 0 or part > 65535 for part in parts):
        raise ValueError("MSIX 版本號的每一段必須介於 0 到 65535")
    if parts[3] != 0:
        raise ValueError("Partner Center 上傳套件的第四段版本必須是 0")
    return ".".join(str(part) for part in parts)


def _installed_makeappx() -> Path | None:
    configured = os.environ.get("MAKEAPPX_PATH")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        raise FileNotFoundError(f"MAKEAPPX_PATH 指向不存在的檔案：{path}")

    command = shutil.which("makeappx.exe")
    if command:
        return Path(command)

    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    sdk_bin = kits / "Windows Kits" / "10" / "bin"
    if sdk_bin.exists():
        matches = sorted(sdk_bin.glob("*/x64/makeappx.exe"), reverse=True)
        if matches:
            return matches[0]
    return None


def ensure_makeappx() -> Path:
    installed = _installed_makeappx()
    if installed:
        return installed

    tools_root = BUILD / "windows-sdk-tools" / WINDOWS_SDK_BUILD_TOOLS_VERSION
    matches = sorted(tools_root.rglob("makeappx.exe")) if tools_root.exists() else []
    x64_matches = [path for path in matches if path.parent.name.lower() == "x64"]
    if x64_matches:
        return x64_matches[0]

    tools_root.mkdir(parents=True, exist_ok=True)
    package_path = tools_root / "Microsoft.Windows.SDK.BuildTools.nupkg"
    print(f"下載 Microsoft Windows SDK Build Tools {WINDOWS_SDK_BUILD_TOOLS_VERSION}...")
    urllib.request.urlretrieve(WINDOWS_SDK_PACKAGE_URL, package_path)
    with zipfile.ZipFile(package_path) as package:
        package.extractall(tools_root)

    matches = sorted(tools_root.rglob("makeappx.exe"))
    x64_matches = [path for path in matches if path.parent.name.lower() == "x64"]
    if not x64_matches:
        raise FileNotFoundError("Microsoft Windows SDK 套件內找不到 x64 MakeAppx.exe")
    return x64_matches[0]


def generate_assets() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    from sniptag.icon import icon_pixmap

    app = QApplication.instance() or QApplication([])
    ASSETS.mkdir(parents=True, exist_ok=True)

    def square(filename: str, size: int) -> None:
        if not icon_pixmap(size).save(str(ASSETS / filename), "PNG"):
            raise RuntimeError(f"無法產生 {filename}")

    square("StoreLogo.png", 50)
    square("Square44x44Logo.png", 44)
    square("Square71x71Logo.png", 71)
    square("Square150x150Logo.png", 150)
    square("Square310x310Logo.png", 310)

    wide = QPixmap(310, 150)
    wide.fill(Qt.transparent)
    painter = QPainter(wide)
    icon = icon_pixmap(128)
    painter.drawPixmap((310 - 128) // 2, (150 - 128) // 2, icon)
    painter.end()
    if not wide.save(str(ASSETS / "Wide310x150Logo.png"), "PNG"):
        raise RuntimeError("無法產生 Wide310x150Logo.png")

    # Windows 的未加底工作列圖示命名慣例。
    unplated = QPixmap(44, 44)
    unplated.fill(QColor(0, 0, 0, 0))
    painter = QPainter(unplated)
    painter.drawPixmap(0, 0, icon_pixmap(44))
    painter.end()
    unplated.save(str(ASSETS / "Square44x44Logo.targetsize-44_altform-unplated.png"), "PNG")
    del app


def build_executable() -> None:
    import build

    if build.main() != 0:
        raise SystemExit("PyInstaller 建置失敗")


def create_layout(version: str) -> None:
    exe = DIST / "SnipTag.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"找不到 {exe}，請先執行 python build.py")

    shutil.rmtree(LAYOUT, ignore_errors=True)
    LAYOUT.mkdir(parents=True)
    shutil.copy2(exe, LAYOUT / exe.name)
    generate_assets()

    manifest = MANIFEST_TEMPLATE.read_text(encoding="utf-8").format(version=version)
    (LAYOUT / "AppxManifest.xml").write_text(manifest, encoding="utf-8", newline="\n")


def pack(makeappx: Path, version: str) -> Path:
    output = DIST / f"SnipTag_{version}_x64.msix"
    output.unlink(missing_ok=True)
    command = [
        str(makeappx), "pack",
        "/d", str(LAYOUT),
        "/p", str(output),
        "/o",
    ]
    print("執行：", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)
    if not output.is_file():
        raise FileNotFoundError(f"MakeAppx 沒有產生 {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-exe", action="store_true",
                        help="沿用 dist/SnipTag.exe，不重新執行 PyInstaller")
    args = parser.parse_args()

    version = store_version()
    if not args.skip_exe:
        build_executable()
    create_layout(version)
    output = pack(ensure_makeappx(), version)
    print(f"\nStore 套件完成：{output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")
    print("此檔案未簽章，只用於上傳 Microsoft Partner Center。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
