@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python
  pause
  exit /b 1
)

python -c "import webview" 1>nul 2>nul
if errorlevel 1 (
  echo [依赖] 正在安装 pywebview ...
  python -m pip install pywebview -q
)

python -m app.gui_webview
if errorlevel 1 pause
