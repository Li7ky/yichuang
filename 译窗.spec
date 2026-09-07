# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：译窗"""

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")

a = Analysis(
    ["run_gui.py"],
    pathex=[],
    binaries=ctk_binaries,
    datas=ctk_datas
    + [
        ("localization", "localization"),
        ("runtime", "runtime"),
        ("app/webui/assets", "app/webui/assets"),
        ("VSCode-language-pack-zh-hans.vsix", "."),
    ],
    hiddenimports=ctk_hidden + ["PIL", "PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["webview", "gui_webview"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="译窗",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
