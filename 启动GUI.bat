@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 3.8+ 并勾选 Add to PATH
  pause
  exit /b 1
)

python -c "import customtkinter" 1>nul 2>nul
if errorlevel 1 (
  echo [依赖] 正在安装桌面界面组件 customtkinter ...
  python -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
  )
)

python -m app gui
if errorlevel 1 pause
