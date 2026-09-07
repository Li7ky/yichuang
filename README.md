# 译窗

> 一键为 Cursor 安装中文界面

[下载 YiChuang.exe](https://github.com/Li7ky/yichuang/releases/latest) · [Releases](https://github.com/Li7ky/yichuang/releases)

---

## 功能

| | |
|---|---|
| **一键汉化** | 官方简体中文语言包 + Cursor 界面文案 |
| **一键还原** | 按备份恢复原版界面 |
| **修复校验** | 处理「安装似乎已损坏」 |
| **自动检测** | 识别安装目录与用户数据目录 |

## 使用

1. 下载并打开 **YiChuang.exe**
2. 点击 **一键汉化**
3. 完全退出 Cursor（含托盘）后重新打开

> Cursor 安装在 `Program Files` 时，请右键 exe → **以管理员身份运行**。

若提示安装已损坏，在软件内点击 **修复校验**。

## 源码运行

```bat
pip install -r requirements.txt
python -m app gui
```

---

仅支持 Windows · 语言包在汉化时自动下载
