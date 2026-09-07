# -*- coding: utf-8 -*-
"""译窗 — 原生桌面 GUI（CustomTkinter）。一屏显示、高对比字体。"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT = sys._MEIPASS  # type: ignore[attr-defined]
    APP_DIR = os.path.join(ROOT, "app")
else:
    ROOT = os.path.dirname(APP_DIR)
ASSETS = os.path.join(APP_DIR, "webui", "assets")
ICON_ICO = os.path.join(ASSETS, "logo.ico")
ICON_PNG = os.path.join(ASSETS, "logo.png")

if not getattr(sys, "frozen", False) and ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import core  # noqa: E402
import customtkinter as ctk

ctk.set_appearance_mode("light")

# —— 视觉令牌 ——
BG = "#F0F3F7"
SIDE = "#FFFFFF"
SIDE_LINE = "#E2E8F0"
SIDE_HOVER = "#F1F5F9"
SIDE_ACTIVE = "#CCFBF1"
CARD = "#FFFFFF"
TEAL = "#0F766E"
TEAL_H = "#0B5F58"
TEXT = "#0F172A"
TEXT2 = "#1E293B"
MUTED = "#475569"
LINE = "#CBD5E1"
DANGER = "#B91C1C"
WARN_BG = "#FFF7ED"
WARN_BD = "#FB923C"
WARN_FG = "#9A3412"
OK_BG = "#D1FAE5"
OK_FG = "#047857"

FONT = "Microsoft YaHei UI"


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("译窗")
        self.geometry("1000x720")
        self.minsize(1000, 720)
        self.maxsize(1000, 720)
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self._set_icon()

        self.log_q: queue.Queue[str] = queue.Queue()
        self.busy = False
        self._feedback_job = None
        self.install_var = ctk.StringVar(value=core.detect_install_dir())
        self.userdata_var = ctk.StringVar(value=core.detect_user_data_dir())
        self.langpack_var = ctk.BooleanVar(value=True)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_side()
        self._build_main()
        self._show("home")
        self._refresh_status()
        self.after(100, self._drain_log)
        self.after(400, lambda: self._show_feedback("就绪。可查看上方状态，操作后会有结果提醒。", "info", 4000))

    def _set_icon(self) -> None:
        try:
            if os.path.isfile(ICON_ICO):
                self.iconbitmap(ICON_ICO)
        except Exception:
            pass
        try:
            if os.path.isfile(ICON_PNG):
                self._icon_img = tk.PhotoImage(file=ICON_PNG)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def _f(self, size: int = 13, bold: bool = False):
        return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")

    def _build_side(self) -> None:
        # 浅色侧栏 + 右侧分隔线
        wrap = ctk.CTkFrame(self, width=216, corner_radius=0, fg_color=SIDE_LINE)
        wrap.grid(row=0, column=0, sticky="nsw")
        wrap.grid_propagate(False)

        side = ctk.CTkFrame(wrap, width=215, corner_radius=0, fg_color="#F8FAFC")
        side.pack(side="left", fill="both", expand=True)
        side.pack_propagate(False)

        # —— 品牌区 ——
        brand_wrap = ctk.CTkFrame(side, fg_color="transparent")
        brand_wrap.pack(fill="x", padx=14, pady=(16, 8))

        brand = ctk.CTkFrame(
            brand_wrap, fg_color=CARD, corner_radius=14,
            border_width=1, border_color=SIDE_LINE, height=64,
        )
        brand.pack(fill="x")
        brand.pack_propagate(False)

        brand_inner = ctk.CTkFrame(brand, fg_color="transparent")
        brand_inner.pack(fill="both", expand=True, padx=12, pady=10)

        if os.path.isfile(ICON_PNG):
            try:
                from PIL import Image
                img = Image.open(ICON_PNG)
                self._logo = ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))
                ctk.CTkLabel(brand_inner, image=self._logo, text="").pack(
                    side="left", padx=(0, 10)
                )
            except Exception:
                pass

        text_col = ctk.CTkFrame(brand_inner, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)
        mid = ctk.CTkFrame(text_col, fg_color="transparent")
        mid.pack(side="left", anchor="center")
        ctk.CTkLabel(
            mid, text="译窗", font=self._f(16, True), text_color=TEXT, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            mid, text="一键汉化 Cursor", font=self._f(11), text_color=MUTED, anchor="w",
        ).pack(anchor="w")

        # —— 导航 ——
        ctk.CTkLabel(
            side, text="功能菜单", font=self._f(11, True), text_color=MUTED, anchor="w",
        ).pack(fill="x", padx=20, pady=(14, 8))

        nav_box = ctk.CTkFrame(side, fg_color="transparent")
        nav_box.pack(fill="x", padx=12)

        self.nav = {}
        self._nav_meta = {
            "home": ("汉化设置", "安装与还原中文界面"),
            "log": ("运行记录", "查看操作输出日志"),
            "about": ("关于软件", "版本与基本信息"),
        }
        for key, (title, desc) in self._nav_meta.items():
            item = ctk.CTkFrame(
                nav_box, fg_color="transparent", corner_radius=12,
                border_width=0, height=58, cursor="hand2",
            )
            item.pack(fill="x", pady=3)
            item.pack_propagate(False)

            accent = ctk.CTkFrame(item, width=3, corner_radius=2, fg_color="transparent")
            accent.pack(side="left", fill="y", padx=(6, 0), pady=10)

            body = ctk.CTkFrame(item, fg_color="transparent")
            body.pack(side="left", fill="both", expand=True, padx=(10, 10), pady=8)
            title_l = ctk.CTkLabel(
                body, text=title, font=self._f(14, True), text_color=TEXT2, anchor="w",
            )
            title_l.pack(anchor="w")
            desc_l = ctk.CTkLabel(
                body, text=desc, font=self._f(11), text_color=MUTED, anchor="w",
            )
            desc_l.pack(anchor="w")

            # 绑定点击
            widgets = (item, accent, body, title_l, desc_l)
            for w in widgets:
                w.bind("<Button-1>", lambda e, k=key: self._show(k))
                w.bind("<Enter>", lambda e, it=item: self._nav_hover(it, True))
                w.bind("<Leave>", lambda e, it=item, k=key: self._nav_hover(it, False, k))

            self.nav[key] = {
                "frame": item,
                "accent": accent,
                "title": title_l,
                "desc": desc_l,
            }

        # —— 底部状态 + 版本：与菜单标题同列左缘，纯文字（去掉色块胶囊）——
        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=12, pady=(8, 18))
        ctk.CTkFrame(foot, height=1, fg_color=SIDE_LINE).pack(fill="x", pady=(0, 12))

        # 与导航标题左缘对齐：accent(6+3) + body(10) = 19
        meta = ctk.CTkFrame(foot, fg_color="transparent")
        meta.pack(anchor="w", fill="x", padx=(19, 10))

        self.side_status = ctk.CTkLabel(
            meta, text="状态检测中", font=self._f(13, True),
            text_color=MUTED, anchor="w",
        )
        self.side_status.pack(anchor="w")
        ctk.CTkLabel(
            meta, text="版本 1.0", font=self._f(11), text_color=MUTED, anchor="w",
        ).pack(anchor="w", pady=(4, 2))

    def _nav_hover(self, item: ctk.CTkFrame, entering: bool, key: str | None = None) -> None:
        # 当前选中项不响应 hover 变回
        active = getattr(self, "_active_nav", "home")
        if key is not None and key == active:
            return
        if entering:
            # 仅非选中
            for k, meta in self.nav.items():
                if meta["frame"] is item and k != active:
                    item.configure(fg_color=SIDE_HOVER)
                    break
        else:
            if key != active:
                item.configure(fg_color="transparent")

    def _paint_nav(self, name: str) -> None:
        self._active_nav = name
        for k, meta in self.nav.items():
            if k == name:
                meta["frame"].configure(fg_color=SIDE_ACTIVE)
                meta["accent"].configure(fg_color=TEAL)
                meta["title"].configure(text_color=TEAL)
                meta["desc"].configure(text_color="#0F766E")
            else:
                meta["frame"].configure(fg_color="transparent")
                meta["accent"].configure(fg_color="transparent")
                meta["title"].configure(text_color=TEXT2)
                meta["desc"].configure(text_color=MUTED)

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # 顶栏
        bar = ctk.CTkFrame(main, height=56, corner_radius=0, fg_color=CARD, border_width=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)

        self.title_lbl = ctk.CTkLabel(bar, text="汉化设置", font=self._f(20, True), text_color=TEXT, anchor="w")
        self.title_lbl.grid(row=0, column=0, sticky="w", padx=20, pady=12)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=16)
        self.status = ctk.CTkLabel(
            right, text="检测中", height=30, corner_radius=15,
            font=self._f(13, True), fg_color="#E2E8F0", text_color=MUTED, padx=12,
        )
        self.status.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            right, text="打开 Cursor", width=108, height=32, corner_radius=9,
            font=self._f(13, True), fg_color=CARD, hover_color="#F1F5F9",
            text_color=TEXT2, border_width=1, border_color=LINE,
            command=self._open_cursor,
        ).pack(side="left")

        # 内容区（占满顶栏以下全部空间，避免大块留白）
        self.host = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        self.host.grid(row=2, column=0, sticky="nsew")
        main.grid_rowconfigure(2, weight=1)
        self.host.grid_columnconfigure(0, weight=1)
        self.host.grid_rowconfigure(0, weight=1)

        self.pages = {
            "home": self._page_home(self.host),
            "log": self._page_log(self.host),
            "about": self._page_about(self.host),
        }

        # 反馈条：插入顶栏与内容之间，显示时下推内容，隐藏时不占位
        self.feedback = ctk.CTkFrame(
            main, fg_color="#EFF6FF", corner_radius=10,
            border_width=1, border_color="#BFDBFE",
        )
        self.feedback_inner = ctk.CTkFrame(self.feedback, fg_color="transparent")
        self.feedback_inner.pack(fill="x", padx=12, pady=8)
        self.feedback_icon = ctk.CTkLabel(
            self.feedback_inner, text="i", width=22, height=22, corner_radius=11,
            font=self._f(12, True), fg_color="#3B82F6", text_color="#FFFFFF",
        )
        self.feedback_icon.pack(side="left", padx=(0, 10))
        self.feedback_text = ctk.CTkLabel(
            self.feedback_inner, text="", font=self._f(13, True),
            text_color="#1E3A8A", anchor="w",
        )
        self.feedback_text.pack(side="left", fill="x", expand=True)
        self._feedback_job = None
        self.feedback.grid_remove()


    def _card(self, parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12, border_width=1, border_color=LINE)

    def _page_home(self, parent) -> ctk.CTkFrame:
        p = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        p.grid_columnconfigure(0, weight=1)

        # 状态面板
        stat = self._card(p)
        stat.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 8))
        sbox = ctk.CTkFrame(stat, fg_color="transparent")
        sbox.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(sbox, text="当前状态", font=self._f(13, True), text_color=TEXT, anchor="w").pack(anchor="w")

        grid = ctk.CTkFrame(sbox, fg_color="transparent")
        grid.pack(fill="x", pady=(8, 0))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

        def _stat_cell(parent, col, title):
            cell = ctk.CTkFrame(parent, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color=LINE)
            cell.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0 if col == 2 else 6))
            ctk.CTkLabel(cell, text=title, font=self._f(11, True), text_color=MUTED, anchor="w").pack(
                anchor="w", padx=10, pady=(8, 0)
            )
            val = ctk.CTkLabel(cell, text="—", font=self._f(14, True), text_color=TEXT, anchor="w")
            val.pack(anchor="w", padx=10, pady=(2, 8))
            return val

        self.st_hanhua = _stat_cell(grid, 0, "汉化状态")
        self.st_backup = _stat_cell(grid, 1, "备份")
        self.st_path = _stat_cell(grid, 2, "安装目录")
        self.st_last = ctk.CTkLabel(
            sbox, text="最近操作：暂无", font=self._f(12), text_color=MUTED, anchor="w",
        )
        self.st_last.pack(anchor="w", pady=(8, 0))

        # 提醒
        alert = ctk.CTkFrame(p, fg_color=WARN_BG, corner_radius=12, border_width=1, border_color=WARN_BD)
        alert.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        alert.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            alert, text="!", width=26, height=26, corner_radius=13,
            fg_color=WARN_BD, text_color="#FFF7ED", font=self._f(14, True),
        ).grid(row=0, column=0, padx=(12, 10), pady=10, sticky="n")
        txt = ctk.CTkFrame(alert, fg_color="transparent")
        txt.grid(row=0, column=1, sticky="ew", pady=8, padx=(0, 12))
        ctk.CTkLabel(txt, text="操作前请先完全退出 Cursor", font=self._f(14, True), text_color=WARN_FG, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            txt, text="含托盘图标。汉化或还原后重新打开才会生效。",
            font=self._f(12), text_color="#C2410C", anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # 操作按钮
        actions = self._card(p)
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        row = ctk.CTkFrame(actions, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        self.btn_install = ctk.CTkButton(
            row, text="一键汉化", width=112, height=36, corner_radius=9,
            font=self._f(14, True), fg_color=TEAL, hover_color=TEAL_H, command=self._on_install,
        )
        self.btn_install.pack(side="left", padx=(0, 8))
        self.btn_restore = ctk.CTkButton(
            row, text="一键还原", width=112, height=36, corner_radius=9,
            font=self._f(14, True), fg_color=CARD, hover_color="#FFF1F2",
            text_color=DANGER, border_width=1, border_color="#FECACA", command=self._on_restore,
        )
        self.btn_restore.pack(side="left", padx=(0, 8))
        self.btn_fix = ctk.CTkButton(
            row, text="修复校验", width=100, height=36, corner_radius=9,
            font=self._f(14, True), fg_color=CARD, hover_color="#F8FAFC",
            text_color=TEXT2, border_width=1, border_color=LINE, command=self._on_fix,
        )
        self.btn_fix.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="刷新状态", width=96, height=36, corner_radius=9,
            font=self._f(13, True), fg_color=CARD, hover_color="#F8FAFC",
            text_color=TEXT2, border_width=1, border_color=LINE, command=self._on_refresh_click,
        ).pack(side="right")

        # 安装路径：按内容高度排布，下方留弹性空白，避免贴底挤压
        form = self._card(p)
        form.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))
        box = ctk.CTkFrame(form, fg_color="transparent")
        box.pack(fill="x", padx=14, pady=(12, 16))

        ctk.CTkLabel(box, text="目标安装", font=self._f(14, True), text_color=TEXT, anchor="w").pack(anchor="w")

        ctk.CTkLabel(box, text="安装目录", font=self._f(12, True), text_color=TEXT2, anchor="w").pack(anchor="w", pady=(8, 4))
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x")
        ctk.CTkEntry(
            r1, textvariable=self.install_var, height=34, corner_radius=9,
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=TEXT, fg_color="#F8FAFC", border_color=LINE,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            r1, text="浏览", width=68, height=34, corner_radius=9, font=self._f(13, True),
            fg_color=CARD, hover_color="#F1F5F9", text_color=TEXT2,
            border_width=1, border_color=LINE, command=self._browse_install,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkCheckBox(
            box, text="安装 / 更新官方简体中文语言包",
            variable=self.langpack_var, font=self._f(13, True),
            text_color=TEXT2, fg_color=TEAL, hover_color=TEAL_H, border_color=LINE,
        ).pack(anchor="w", pady=(10, 0))

        ctk.CTkLabel(box, text="用户数据目录", font=self._f(12, True), text_color=TEXT2, anchor="w").pack(anchor="w", pady=(8, 4))
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x")
        ctk.CTkEntry(
            r2, textvariable=self.userdata_var, height=34, corner_radius=9,
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=TEXT, fg_color="#F8FAFC", border_color=LINE,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            r2, text="浏览", width=68, height=34, corner_radius=9, font=self._f(13, True),
            fg_color=CARD, hover_color="#F1F5F9", text_color=TEXT2,
            border_width=1, border_color=LINE, command=self._browse_userdata,
        ).pack(side="left", padx=(8, 0))

        # 底部弹性空白，保证卡片与窗口底边有呼吸感
        spacer = ctk.CTkFrame(p, fg_color="transparent", height=12)
        spacer.grid(row=4, column=0, sticky="nsew")
        p.grid_rowconfigure(4, weight=1)

        return p

    def _page_log(self, parent) -> ctk.CTkFrame:
        # 铺满内容区，去掉多余留白
        p = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(0, weight=1)

        card = self._card(p)
        card.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        ctk.CTkLabel(head, text="运行记录", font=self._f(14, True), text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            head, text="清空", width=64, height=30, corner_radius=8, font=self._f(12, True),
            fg_color=CARD, hover_color="#F1F5F9", text_color=TEXT2,
            border_width=1, border_color=LINE,
            command=lambda: (
                self.log_box.configure(state="normal"),
                self.log_box.delete("1.0", "end"),
                self.log_box.configure(state="disabled"),
            ),
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            card, font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0F172A", text_color="#E2E8F0", corner_radius=10,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.insert("end", "就绪\n")
        self.log_box.configure(state="disabled")
        return p

    def _page_about(self, parent) -> ctk.CTkFrame:
        # 卡片铺满，信息靠上排列（避免中间一条、下面大片空白）
        p = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        p.grid_columnconfigure(0, weight=1)
        p.grid_rowconfigure(0, weight=1)

        card = self._card(p)
        card.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)

        box = ctk.CTkFrame(card, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(box, text="软件信息", font=self._f(14, True), text_color=TEXT, anchor="w").pack(anchor="w", pady=(0, 12))

        for k, v in (
            ("名称", "译窗"),
            ("版本", "1.0"),
            ("说明", "一键汉化 Cursor，支持安装、还原与校验"),
        ):
            row = ctk.CTkFrame(box, fg_color="#F8FAFC", corner_radius=10, border_width=1, border_color=LINE)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=k, width=56, anchor="w", font=self._f(13, True), text_color=MUTED).pack(
                side="left", padx=(14, 10), pady=14
            )
            ctk.CTkLabel(row, text=v, anchor="w", font=self._f(14, True), text_color=TEXT).pack(
                side="left", fill="x", expand=True, pady=14, padx=(0, 14)
            )

        # 底部补充，占住下方空间，避免空洞感
        tip = ctk.CTkFrame(box, fg_color="#F0FDFA", corner_radius=10, border_width=1, border_color="#99F6E4")
        tip.pack(fill="x", side="bottom", pady=(16, 0))
        ctk.CTkLabel(
            tip,
            text="使用提醒：汉化或还原后，请完全退出 Cursor（含托盘）再重新打开。",
            font=self._f(12), text_color=TEAL, anchor="w", justify="left",
            wraplength=560,
        ).pack(anchor="w", padx=14, pady=12)

        return p

    def _show_feedback(self, message: str, kind: str = "info", auto_hide_ms: int = 5000) -> None:
        styles = {
            "info": ("#EFF6FF", "#1E3A8A", "#3B82F6", "#BFDBFE", "i"),
            "ok": ("#ECFDF5", "#065F46", "#10B981", "#A7F3D0", "✓"),
            "warn": ("#FFF7ED", "#9A3412", "#F59E0B", "#FDBA74", "!"),
            "err": ("#FEF2F2", "#991B1B", "#EF4444", "#FECACA", "×"),
            "busy": ("#F5F3FF", "#5B21B6", "#8B5CF6", "#DDD6FE", "…"),
        }
        bg, fg, ico_bg, bd, ico = styles.get(kind, styles["info"])
        self.feedback.configure(fg_color=bg, border_color=bd)
        self.feedback_icon.configure(text=ico, fg_color=ico_bg)
        self.feedback_text.configure(text=message, text_color=fg)
        # 顶栏下方占位显示，下推内容，避免遮挡
        self.feedback.grid(row=1, column=0, sticky="ew", padx=16, pady=(10, 0))
        if self._feedback_job is not None:
            try:
                self.after_cancel(self._feedback_job)
            except Exception:
                pass
            self._feedback_job = None
        if auto_hide_ms > 0 and kind != "busy":
            self._feedback_job = self.after(auto_hide_ms, self._hide_feedback)

    def _hide_feedback(self) -> None:
        self.feedback.grid_remove()
        self._feedback_job = None

    def _show(self, name: str) -> None:
        titles = {"home": "汉化设置", "log": "运行记录", "about": "关于软件"}
        self.title_lbl.configure(text=titles[name])
        self._paint_nav(name)
        for k, page in self.pages.items():
            if k == name:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_forget()

    def _browse_install(self) -> None:
        path = filedialog.askdirectory(title="选择 Cursor 安装目录")
        if path:
            self.install_var.set(path)
            self._refresh_status()

    def _browse_userdata(self) -> None:
        path = filedialog.askdirectory(title="选择用户数据目录")
        if path:
            self.userdata_var.set(path)

    def _append_log(self, msg: str) -> None:
        self.log_q.put(msg)

    def _drain_log(self) -> None:
        try:
            while True:
                msg = self.log_q.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", msg + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _on_refresh_click(self) -> None:
        self._refresh_status()
        self._show_feedback("状态已刷新", "info", 2500)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_install, self.btn_restore, self.btn_fix):
            b.configure(state=state)

    def _refresh_status(self) -> None:
        root = self.install_var.get().strip()
        st = core.status(root)
        short = root if len(root) < 36 else ("…" + root[-34:])

        if not st["valid"]:
            self.status.configure(text="目录无效", fg_color="#FEE2E2", text_color=DANGER)
            if hasattr(self, "side_status"):
                self.side_status.configure(text="目录无效", text_color=DANGER)
            if hasattr(self, "st_hanhua"):
                self.st_hanhua.configure(text="未就绪", text_color=DANGER)
                self.st_backup.configure(text="—", text_color=MUTED)
                self.st_path.configure(text="无效", text_color=DANGER)
            return

        if st["legacy_injected"]:
            chip, bg, fg = "旧版汉化", "#FFEDD5", "#B45309"
            htxt, hfg = "旧版残留", "#B45309"
        elif st["smooth_injected"]:
            chip, bg, fg = "已汉化", OK_BG, OK_FG
            htxt, hfg = "已汉化", OK_FG
        else:
            chip, bg, fg = "未汉化", "#E2E8F0", MUTED
            htxt, hfg = "未汉化", MUTED

        self.status.configure(text=chip, fg_color=bg, text_color=fg)
        if hasattr(self, "side_status"):
            self.side_status.configure(text=chip, text_color=fg)
        if hasattr(self, "st_hanhua"):
            self.st_hanhua.configure(text=htxt, text_color=hfg)
            self.st_backup.configure(
                text="已备份" if st["has_backup"] else "无备份",
                text_color=OK_FG if st["has_backup"] else MUTED,
            )
            self.st_path.configure(text=short, text_color=TEXT)

    def _run_bg(self, title: str, fn: Callable[[], bool]) -> None:
        if self.busy:
            self._show_feedback("正在处理中，请稍候…", "warn", 2500)
            return
        self._set_busy(True)
        self._append_log(f"—— {title} ——")
        self._show_feedback(f"{title}进行中，请勿关闭窗口…", "busy", 0)
        self._show("log")

        def worker() -> None:
            ok = False
            try:
                ok = bool(fn())
            except Exception as e:
                self._append_log(f"[异常] {e}")
            finally:
                self.after(0, lambda: self._done(title, ok))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, title: str, ok: bool) -> None:
        self._set_busy(False)
        self._refresh_status()
        if hasattr(self, "st_last"):
            from datetime import datetime
            now = datetime.now().strftime("%H:%M:%S")
            result = "成功" if ok else "失败"
            self.st_last.configure(text=f"最近操作：{title} · {result} · {now}")

        if ok:
            self._show_feedback(f"{title}成功。请完全退出 Cursor（含托盘）后重新打开。", "ok", 8000)
            messagebox.showinfo(title, f"{title}成功。\n\n请完全退出 Cursor（含托盘图标）后重新打开，设置才会生效。")
        else:
            self._show_feedback(f"{title}未完成，请查看「运行记录」。如权限不足请以管理员运行。", "err", 8000)
            messagebox.showwarning(title, f"{title}未完全成功，请查看运行记录。\n如权限不足，请以管理员身份运行。")

    def _on_install(self) -> None:
        self._show_feedback("即将开始汉化：请确认已退出 Cursor", "warn", 3000)
        root, data, lang = self.install_var.get().strip(), self.userdata_var.get().strip(), self.langpack_var.get()
        self._run_bg("一键汉化", lambda: core.install(root, data, with_language_pack=lang, log=self._append_log))

    def _on_restore(self) -> None:
        if not messagebox.askyesno("确认还原", "将移除汉化注入并恢复备份，是否继续？"):
            self._show_feedback("已取消还原", "info", 2000)
            return
        root = self.install_var.get().strip()
        self._run_bg("一键还原", lambda: core.restore(root, log=self._append_log))

    def _on_fix(self) -> None:
        root = self.install_var.get().strip()
        self._run_bg("修复校验", lambda: core.fix_checksum(root, log=self._append_log))

    def _open_cursor(self) -> None:
        root = self.install_var.get().strip()
        exe = core.cursor_exe(root)
        if not os.path.exists(exe):
            self._show_feedback(f"找不到 Cursor：{exe}", "err", 5000)
            messagebox.showerror("错误", f"找不到 Cursor：{exe}")
            return
        try:
            subprocess.Popen(["open", root] if core.is_macos() else [exe])
            self._show_feedback("已尝试启动 Cursor", "ok", 3000)
        except Exception as e:
            self._show_feedback(str(e), "err", 5000)
            messagebox.showerror("错误", str(e))


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
