# -*- coding: utf-8 -*-
"""将词典与 runtime/engine.js 组装为注入脚本。"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from typing import Any


def _bundle_root() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _bundle_root()
LOC_DIR = os.path.join(ROOT, "localization")
ENGINE_PATH = os.path.join(ROOT, "runtime", "engine.js")


def _js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _load_json(name: str) -> Any:
    path = os.path.join(LOC_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_core_entries() -> dict[str, str]:
    data = _load_json("Core_Dictionary.json")
    out: dict[str, str] = {}
    for section in data.get("sections", []):
        for item in section.get("entries", []):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                en, zh = str(item[0]), str(item[1])
                if en and zh and en != zh:
                    out[en] = zh
    # 广告弹窗合并进主词典
    try:
        ad = _load_json("Ad_Popup_Dictionary.json")
        for item in ad.get("entries", []):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                en, zh = str(item[0]), str(item[1])
                if en and zh and en != zh:
                    out[en] = zh
    except FileNotFoundError:
        pass
    return out


def load_patterns() -> list[tuple[str, str, str]]:
    data = _load_json("Pattern_Dictionary.json")
    out: list[tuple[str, str, str]] = []
    for p in data.get("patterns", []):
        expr = p.get("regex") or p.get("pattern")
        repl = p.get("replacement") or p.get("replace")
        flags = p.get("flags") or ""
        if expr and repl is not None:
            out.append((str(expr), str(flags), str(repl)))
    return out


def load_fragments() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name in (
        "Partial_Fragments.json",
        "Dropdown_Fragments.json",
        "Cursor_Settings_Fragments.json",
    ):
        try:
            data = _load_json(name)
        except FileNotFoundError:
            continue
        entries = data.get("entries") or []
        if not entries:
            # Cursor_Settings_Fragments 特殊结构
            for key in ("mcpEntries", "domainEntries"):
                for item in data.get(key, []) or []:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        out.append((str(item[0]), str(item[1])))
            continue
        for item in entries:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out.append((str(item[0]), str(item[1])))
    return out


def load_market_js() -> str:
    try:
        data = _load_json("Plugin_Marketplace_Dictionary.json")
    except FileNotFoundError:
        return ""

    names = data.get("pluginNames") or {}
    ui = data.get("uiLabels") or {}
    frags = data.get("descriptionFragments") or []

    lines = ["(function(){", "var M=new Map(["]
    pairs = []
    for k, v in {**names, **ui}.items():
        pairs.append(f"[{_js_str(k)},{_js_str(v)}]")
    lines.append(",".join(pairs))
    lines.append("]);")
    lines.append("var F=[")
    fparts = []
    for item in frags:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            fparts.append(f"[{_js_str(item[0])},{_js_str(item[1])}]")
    lines.append(",".join(fparts))
    lines.append("];")
    lines.append(
        """
function mt(t){if(!t)return null;var x=t.trim();if(M.has(x))return M.get(x);var r=x,c=false;for(var i=0;i<F.length;i++){if(r.indexOf(F[i][0])!==-1){r=r.split(F[i][0]).join(F[i][1]);c=true;}}return c?r:null;}
function walkMarket(root){if(!root)return;var w;try{w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null);}catch(e){return;}var n;while((n=w.nextNode())){var raw=n.nodeValue;if(!raw||!raw.trim())continue;var tr=mt(raw);if(tr&&tr!==raw.trim())n.nodeValue=raw.replace(raw.trim(),tr);}}
var box=document.querySelector('.extensions-viewlet,.extensions-list,[class*="marketplace"],.monaco-workbench');
if(box)walkMarket(box);
"""
    )
    lines.append("})();")
    return "\n".join(lines)


def _dict_block(entries: dict[str, str]) -> str:
    parts = [f"[{_js_str(k)},{_js_str(v)}]" for k, v in entries.items()]
    return "var DICT=new Map([\n" + ",\n".join(parts) + "\n]);\n"


def _pattern_block(patterns: list[tuple[str, str, str]]) -> str:
    items = []
    for expr, flags, repl in patterns:
        try:
            re.compile(expr)
        except re.error:
            continue
        # 去掉 g：RegExp.test 带 g 会推进 lastIndex，导致偶发漏翻
        flag_js = "".join(c for c in flags if c in "imsu")
        items.append(f"[new RegExp({_js_str(expr)},{_js_str(flag_js)}),{_js_str(repl)}]")
    return "var PATTERNS=[\n" + ",\n".join(items) + "\n];\n"


def _fragment_block(frags: list[tuple[str, str]]) -> str:
    # 片段过多会拖慢；优先保留较短高价值条目，上限约 200
    slim = sorted(frags, key=lambda x: len(x[0]))[:200]
    parts = [f"[{_js_str(a)},{_js_str(b)}]" for a, b in slim]
    return "var FRAGMENTS=[\n" + ",\n".join(parts) + "\n];\n"


def build_js() -> str:
    with open(ENGINE_PATH, "r", encoding="utf-8") as f:
        engine = f.read()

    entries = load_core_entries()
    patterns = load_patterns()
    fragments = load_fragments()
    market = load_market_js()

    engine = engine.replace("__BUILD_TIMESTAMP__", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    engine = engine.replace("// __DICTIONARY_BLOCK__", _dict_block(entries))
    engine = engine.replace("// __PATTERN_BLOCK__", _pattern_block(patterns))
    engine = engine.replace("// __FRAGMENT_BLOCK__", _fragment_block(fragments))
    engine = engine.replace("// __MARKET_BLOCK__", market if market else "/* no market dict */")
    return engine


def build_stats() -> dict[str, int]:
    return {
        "dict": len(load_core_entries()),
        "patterns": len(load_patterns()),
        "fragments": min(200, len(load_fragments())),
    }
