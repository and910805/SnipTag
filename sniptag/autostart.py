"""開機自動啟動：寫入 HKCU 的 Run 機碼。

以登錄檔為唯一真相，不另外記在設定檔裡 —— 使用者若從工作管理員的
「開機」分頁停用，設定視窗下次打開就會顯示正確狀態。

只動 HKEY_CURRENT_USER，不需要系統管理員權限，也不影響其他使用者。
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SnipTag"


def is_packaged() -> bool:
    """目前是否由 MSIX / Microsoft Store 套件身分啟動。"""
    if sys.platform != "win32":
        return False
    try:
        length = ctypes.c_uint32(0)
        result = ctypes.windll.kernel32.GetCurrentPackageFullName(
            ctypes.byref(length), None
        )
        # ERROR_INSUFFICIENT_BUFFER 表示 Windows 找到了套件名稱。
        return result == 122
    except (AttributeError, OSError):
        return False


def available() -> bool:
    # Store 版改由 AppxManifest 的 windows.startupTask 管理，不能再把
    # 版本化的 WindowsApps 實體路徑寫入 HKCU Run。
    return sys.platform == "win32" and not is_packaged()


def launch_command() -> str:
    """開機時要執行的命令列。"""
    if getattr(sys, "frozen", False):        # PyInstaller 打包出來的 exe
        return f'"{Path(sys.executable)}"'

    # 從原始碼執行：優先用 pythonw 避免跳出黑色主控台視窗
    launcher = Path(sys.executable)
    windowless = launcher.with_name("pythonw.exe")
    if windowless.exists():
        launcher = windowless

    script = Path(__file__).resolve().parent.parent / "run.py"
    if script.exists():
        return f'"{launcher}" "{script}"'
    return f'"{launcher}" -m sniptag'


def _winreg():
    import winreg
    return winreg


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    if is_packaged():
        # MSIX manifest 首次啟動時會註冊已啟用的 StartupTask；使用者仍可
        # 在 Windows「啟動應用程式」或工作管理員中停用。
        return True
    if not available():
        return False
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
            return bool(value)
    except (OSError, ImportError):
        return False


def current_command(value_name: str = VALUE_NAME) -> str:
    if not available():
        return ""
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
            return str(value)
    except (OSError, ImportError):
        return ""


def set_enabled(enabled: bool, value_name: str = VALUE_NAME,
                command: str | None = None) -> bool:
    """回傳是否成功。失敗多半是登錄檔被群組原則鎖住。"""
    if not available():
        return False
    winreg = _winreg()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ,
                                  command or launch_command())
            else:
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass        # 本來就沒開，也算成功
        return True
    except (OSError, ImportError):
        return False


def sync(enabled: bool) -> bool:
    """設成指定狀態；已經是該狀態且命令沒變就不動它。"""
    if not available():
        return False
    if enabled and is_enabled() and current_command() == launch_command():
        return True
    if not enabled and not is_enabled():
        return True
    return set_enabled(enabled)
