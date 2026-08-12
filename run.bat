@echo off
rem 啟動 SnipTag（不留 console 視窗）
cd /d "%~dp0"
start "" pythonw.exe -m sniptag
