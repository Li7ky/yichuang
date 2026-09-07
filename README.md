# 译窗

一键汉化 Cursor 的桌面工具：安装 / 还原 / 修复校验。自动检测安装路径，修改前备份，可还原。

## 下载

到 [Releases](../../releases) 下载 `译窗.exe`，右键 **以管理员身份运行**（若 Cursor 装在 Program Files）。

## 源码运行

```bat
pip install -r requirements.txt
python -m app gui
```

或双击 `启动GUI.bat`。

## 自行编译

```bat
编译软件.bat
```

产物：`dist\译窗.exe`

## 使用说明

1. 打开软件 → **一键汉化**
2. **完全退出** Cursor（含托盘）后再打开
3. 若提示「安装已损坏」→ 点 **修复校验**
4. 还原：点 **一键还原**

## 功能

- 官方简体中文语言包
- 注入脚本覆盖 Cursor 专有界面文案
- 一键还原与校验修复

## 命令行

```bat
python -m app gui
python -m app install
python -m app restore
python -m app fix
```
