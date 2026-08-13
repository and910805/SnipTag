# Privacy Policy

Last updated: August 13, 2026

This Privacy Policy applies to the official SnipTag application and its source
code distributions.

## Summary

SnipTag is a local-first screenshot utility. It does not collect, transmit,
sell, or share personal information. It has no account system, advertising,
analytics, telemetry, crash reporting, or cloud synchronization.

## Information handled locally

SnipTag may handle the following information on your device when you use its
features:

- Screen pixels captured after you invoke a screenshot command.
- Clipboard images read when you invoke the pin-from-clipboard feature.
- Images or text written to the clipboard when you request a copy operation or
  enable copy-on-save.
- Captured images and annotations saved to a folder you choose.
- Preferences stored in `%APPDATA%\SnipTag\config.json`, including the save
  folder, topic names, recent topics, filename template, hotkeys, and display
  options.
- An optional `SnipTag` startup entry under
  `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` when you
  enable launch at sign-in.

The screenshot history holds up to 30 images in memory. It is cleared when you
clear the history or exit SnipTag. The history is not uploaded or stored as a
separate history database.

## Network transfers

SnipTag does not contain runtime code that sends screenshots, clipboard
content, preferences, or usage information over the network.

**This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.**

Visiting the SnipTag GitHub repository, downloading a release, or following an
external link uses services outside the SnipTag application. Those services
operate under their own privacy policies.

## Storage, retention, and deletion

The SnipTag maintainer does not receive or retain data handled by the
application. Data stored locally remains under your control:

- Delete saved screenshots from the folder you selected.
- Exit SnipTag and delete `%APPDATA%\SnipTag\config.json` (or the entire
  `%APPDATA%\SnipTag` folder) to remove its saved preferences.
- Disable **Launch at sign-in** in SnipTag before uninstalling, or remove the
  `SnipTag` value from the Windows registry location listed above.
- Clear screenshot history inside SnipTag or exit the application to remove its
  in-memory history.

SnipTag does not provide cloud backups. Protect locally saved screenshots using
the security controls appropriate for your device and the sensitivity of their
contents.

## Changes to this policy

This policy may be updated if SnipTag's data-handling behavior changes. Material
changes will be published in this repository before the affected feature is
released.

## Contact

For privacy questions, open an issue in the
[SnipTag GitHub repository](https://github.com/and910805/SnipTag/issues).

---

# 隱私權政策

最後更新日期：2026 年 8 月 13 日

本隱私權政策適用於 SnipTag 官方應用程式及其原始碼發行版本。

## 摘要

SnipTag 是以本機處理為主的截圖工具，不會蒐集、傳送、販售或分享個人資料，
也不包含帳號系統、廣告、使用情形分析、遙測、當機回報或雲端同步功能。

## 在本機處理的資訊

當你主動使用相關功能時，SnipTag 可能會在你的裝置上處理以下資訊：

- 你啟動截圖指令後所擷取的螢幕畫面。
- 你啟動「從剪貼簿釘圖」功能時讀取的剪貼簿圖片。
- 你要求複製或啟用「存檔時複製」後寫入剪貼簿的圖片或文字。
- 儲存至你所選資料夾的截圖與標註內容。
- 儲存在 `%APPDATA%\SnipTag\config.json` 的偏好設定，包括存檔資料夾、
  主題名稱、最近使用的主題、檔名範本、熱鍵及顯示選項。
- 你啟用登入時啟動功能後，寫入
  `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` 的可選
  `SnipTag` 啟動項目。

截圖歷史最多在記憶體中保留 30 張圖片。清除歷史或結束 SnipTag 後，這些記憶體
內容就會清除；SnipTag 不會將歷史上傳，也不會另存為歷史資料庫。

## 網路傳輸

SnipTag 不包含在執行時透過網路傳送截圖、剪貼簿內容、偏好設定或使用情形的程式碼。

**除非使用者、安裝者或操作人員明確要求，否則本程式不會將任何資訊傳送至其他
連網系統。**

造訪 SnipTag 的 GitHub 儲存庫、下載 Release 或開啟外部連結時，會使用 SnipTag
應用程式以外的服務；這些服務適用各自的隱私權政策。

## 儲存、保留與刪除

SnipTag 維護者不會收到或保留應用程式處理的資料。本機資料由你自行控制：

- 從你所選的資料夾刪除已儲存的截圖。
- 結束 SnipTag 後，刪除 `%APPDATA%\SnipTag\config.json` 或整個
  `%APPDATA%\SnipTag` 資料夾，即可移除已儲存的偏好設定。
- 解除安裝前先在 SnipTag 關閉「登入時啟動」，或從上述 Windows 登錄位置刪除
  `SnipTag` 值。
- 在 SnipTag 內清除截圖歷史，或結束應用程式，即可移除記憶體中的歷史內容。

SnipTag 不提供雲端備份。請依裝置的安全需求及截圖內容的敏感程度，妥善保護本機
儲存的截圖。

## 政策變更

如果 SnipTag 的資料處理行為改變，本政策可能會更新。影響重大的變更會在相關功能
發布前公布於本儲存庫。

## 聯絡方式

如有隱私相關問題，請在
[SnipTag GitHub 儲存庫](https://github.com/and910805/SnipTag/issues)提出 Issue。
