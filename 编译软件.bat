@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [译窗] 安装打包依赖...
python -m pip install -q -r requirements.txt pyinstaller
echo [译窗] 开始编译...
python -m PyInstaller --noconfirm "译窗.spec"
if errorlevel 1 (
  echo 编译失败
  exit /b 1
)
echo.
echo 完成: dist\译窗.exe
explorer dist
