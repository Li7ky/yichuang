# -*- coding: utf-8 -*-
"""译窗 — Cursor 中文工具：安装 / 还原 / 校验。"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from typing import Callable, Optional

from .build_js import build_js, build_stats

LogFn = Callable[[str], None]


def _log(msg: str, log: Optional[LogFn] = None) -> None:
    if log:
        log(msg)
    else:
        print(msg)


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def _bundle_root() -> str:
    """只读资源根目录（开发态=项目根；打包态=PyInstaller 解压目录）。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable_root() -> str:
    """可写根目录（语言包缓存等；打包态=exe 同目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return _bundle_root()


ROOT = _bundle_root()

JS_FILE = "Cursor_CN_UI.js"
MARKER = "<!-- CURSOR_CN_UI_INJECTION -->"
BACKUP_SUFFIX = ".bak"

# 旧版注入标记（安装前先清干净）
LEGACY_JS_FILES = ("Cursor_Localization.js", "cursor_hanhua.js", "Cursor_I18n_Smooth.js")
LEGACY_MARKERS = (
    "<!-- CURSOR_LOCALIZATION_INJECTION -->",
    "<!-- CURSOR_HANHUA_INJECTION -->",
    "<!-- CURSOR_I18N_SMOOTH_INJECTION -->",
    MARKER,
)

LANGUAGE_PACK_VSIX = "VSCode-language-pack-zh-hans.vsix"
LANGUAGE_PACK_ID = "ms-ceintl.vscode-language-pack-zh-hans"
LANGUAGE_PACK_MARKETPLACE_QUERY = (
    "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
)
LANGUAGE_PACK_MARKETPLACE_DOWNLOAD = (
    "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/"
    "MS-CEINTL/vsextensions/vscode-language-pack-zh-hans/{version}/vspackage"
)


def workbench_dir(install_root: str) -> str:
    if is_macos():
        return os.path.join(
            install_root, "Contents", "Resources", "app",
            "out", "vs", "code", "electron-sandbox", "workbench",
        )
    return os.path.join(
        install_root, "resources", "app",
        "out", "vs", "code", "electron-sandbox", "workbench",
    )


def app_dir(install_root: str) -> str:
    if is_macos():
        return os.path.join(install_root, "Contents", "Resources", "app")
    return os.path.join(install_root, "resources", "app")


def html_path(install_root: str) -> str:
    return os.path.join(workbench_dir(install_root), "workbench.html")


def js_path(install_root: str) -> str:
    return os.path.join(workbench_dir(install_root), JS_FILE)


def product_path(install_root: str) -> str:
    return os.path.join(app_dir(install_root), "product.json")


def main_js_path(install_root: str) -> str:
    return os.path.join(app_dir(install_root), "out", "main.js")


def valid_install(install_root: str) -> bool:
    if not install_root or not os.path.isfile(html_path(install_root)):
        return False
    if is_windows():
        return os.path.isfile(os.path.join(install_root, "Cursor.exe"))
    if is_macos():
        return install_root.endswith(".app") and os.path.isdir(
            os.path.join(install_root, "Contents", "MacOS")
        )
    return True


def detect_install_dir() -> str:
    env = os.environ.get("CURSOR_INSTALL_DIR") or os.environ.get("CURSOR_ROOT")
    candidates = []
    if env:
        candidates.append(env)
    if is_macos():
        candidates.extend([
            "/Applications/Cursor.app",
            os.path.expanduser("~/Applications/Cursor.app"),
        ])
    else:
        candidates.extend([
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "cursor"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Cursor"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Cursor"),
        ])
    for c in candidates:
        if c and valid_install(c):
            return os.path.abspath(c)
    return candidates[0] if candidates else ""


def detect_user_data_dir() -> str:
    env = os.environ.get("CURSOR_USER_DATA_DIR")
    if env:
        return os.path.abspath(env)
    if is_macos():
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Cursor")
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "Cursor")
    return os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Cursor")


def cursor_exe(install_root: str) -> str:
    if is_macos():
        p = os.path.join(install_root, "Contents", "MacOS", "Cursor")
        return p if os.path.isfile(p) else install_root
    return os.path.join(install_root, "Cursor.exe")


def cursor_cli(install_root: str) -> Optional[str]:
    if is_macos():
        for name in ("cursor", "code"):
            p = os.path.join(install_root, "Contents", "Resources", "app", "bin", name)
            if os.path.isfile(p):
                return p
        return None
    for name in ("cursor.cmd", "cursor.exe", "bin\\cursor.cmd"):
        p = os.path.join(install_root, name)
        if os.path.isfile(p):
            return p
        p2 = os.path.join(install_root, "resources", "app", "bin", name.replace("\\", os.sep))
        if os.path.isfile(p2):
            return p2
    return None


def read_text(path: str) -> tuple[str, Optional[str]]:
    with open(path, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else ("\n" if b"\n" in raw else None)
    return raw.decode("utf-8"), nl


def write_text(path: str, content: str, nl: Optional[str] = None) -> None:
    if nl == "\r\n":
        content = content.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def file_checksum(path: str) -> str:
    """与 Cursor/VS Code 一致：SHA256 后 Base64，并去掉末尾 '='。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii").rstrip("=")


def status(install_root: str) -> dict:
    html = html_path(install_root)
    info = {
        "valid": valid_install(install_root),
        "install_root": install_root,
        "html": html,
        "smooth_injected": False,
        "legacy_injected": False,
        "has_backup": False,
    }
    if not info["valid"]:
        return info
    try:
        content, _ = read_text(html)
        info["smooth_injected"] = (
            MARKER in content
            or JS_FILE in content
            or "CURSOR_I18N_SMOOTH" in content
            or "Cursor_I18n_Smooth.js" in content
        )
        info["legacy_injected"] = any(
            m in content for m in (
                "<!-- CURSOR_LOCALIZATION_INJECTION -->",
                "<!-- CURSOR_HANHUA_INJECTION -->",
            )
        ) or any(
            name in content for name in ("Cursor_Localization.js", "cursor_hanhua.js")
        )
        info["has_backup"] = os.path.isfile(html + BACKUP_SUFFIX)
    except OSError:
        pass
    return info


def remove_injection_from_html(content: str) -> str:
    lines = content.splitlines(keepends=True)
    out = []
    skip_next_script = False
    for line in lines:
        if any(m in line for m in LEGACY_MARKERS):
            skip_next_script = True
            continue
        if skip_next_script and "<script" in line and (
            JS_FILE in line or any(x in line for x in LEGACY_JS_FILES)
        ):
            skip_next_script = False
            continue
        # 单行残留
        if JS_FILE in line and "<script" in line:
            continue
        if any(x in line for x in LEGACY_JS_FILES) and "<script" in line:
            continue
        out.append(line)
    return "".join(out)


def cleanup_workbench_js(install_root: str, log: Optional[LogFn] = None) -> None:
    wb = workbench_dir(install_root)
    for name in (JS_FILE,) + LEGACY_JS_FILES:
        p = os.path.join(wb, name)
        if os.path.isfile(p):
            os.remove(p)
            _log(f"[清理] 已删除 {name}", log)


def load_tray_replacements() -> list[tuple[str, str]]:
    path = os.path.join(ROOT, "localization", "Tray_Dictionary.json")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for item in data.get("replacements", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append((str(item[0]), str(item[1])))
    return out


def apply_tray(install_root: str, reverse: bool = False, log: Optional[LogFn] = None) -> bool:
    path = main_js_path(install_root)
    if not os.path.isfile(path):
        _log("[托盘] 未找到 main.js，跳过", log)
        return False
    bak = path + BACKUP_SUFFIX
    try:
        content, nl = read_text(path)
    except OSError as e:
        _log(f"[托盘] 读取失败（可能需要管理员权限）: {e}", log)
        return False

    reps = load_tray_replacements()
    if not reps:
        return False

    if reverse:
        if os.path.isfile(bak):
            shutil.copy2(bak, path)
            os.remove(bak)
            _log("[托盘] 已从备份恢复 main.js", log)
            return True
        new = content
        for a, b in reps:
            new = new.replace(b, a)
        if new != content:
            write_text(path, new, nl)
            _log("[托盘] 已反向还原托盘文案", log)
        return True

    if not os.path.isfile(bak):
        shutil.copy2(path, bak)
    new = content
    for a, b in reps:
        new = new.replace(a, b)
    if new != content:
        write_text(path, new, nl)
        _log("[托盘] 已汉化系统托盘菜单", log)
    else:
        _log("[托盘] 托盘文案已是最新或未匹配到词条", log)
    return True


def update_checksums(install_root: str, log: Optional[LogFn] = None) -> bool:
    prod = product_path(install_root)
    if not os.path.isfile(prod):
        _log(f"[校验] 未找到 product.json: {prod}", log)
        return False

    bak = prod + BACKUP_SUFFIX
    if not os.path.isfile(bak):
        try:
            shutil.copy2(prod, bak)
            _log("[校验] 已备份 product.json", log)
        except OSError as e:
            _log(f"[校验] 备份失败: {e}", log)
            return False

    try:
        raw, nl = read_text(prod)
        product = json.loads(raw)
    except Exception as e:
        _log(f"[校验] 解析 product.json 失败: {e}", log)
        return False

    checksums = product.get("checksums") or {}
    if not isinstance(checksums, dict) or not checksums:
        _log("[校验] product.json 无 checksums 字段", log)
        return False

    app_root = app_dir(install_root)
    updated = 0
    for key in list(checksums.keys()):
        rel = key.replace("\\", "/")
        # 常见相对路径
        candidates = [
            os.path.join(app_root, rel),
            os.path.join(app_root, "out", rel) if not rel.startswith("out/") else os.path.join(app_root, rel),
            os.path.join(app_root, rel[4:]) if rel.startswith("out/") else "",
        ]
        target = next((c for c in candidates if c and os.path.isfile(c)), None)
        if not target:
            continue
        digest = file_checksum(target)
        # 就地替换文本，尽量保持格式
        old = checksums[key]
        if old == digest:
            continue
        # product.json 里值通常无 padding 差异，直接字符串替换更稳
        pattern = re.compile(
            r'("%s"\s*:\s*")([^"]*)(")' % re.escape(key.replace("\\", "\\\\"))
        )
        raw2, n = pattern.subn(r"\g<1>%s\g<3>" % digest, raw, count=1)
        if n:
            raw = raw2
            checksums[key] = digest
            updated += 1
            _log(f"[校验] 已更新 {os.path.basename(key)}", log)

    if updated:
        try:
            write_text(prod, raw, nl)
        except OSError as e:
            _log(f"[校验] 写入失败（请以管理员运行）: {e}", log)
            return False
    else:
        # 兜底：整表重算 workbench.html
        html = html_path(install_root)
        if os.path.isfile(html):
            digest = file_checksum(html)
            for key in list(checksums.keys()):
                if "workbench.html" in key.replace("\\", "/").lower():
                    pattern = re.compile(
                        r'("%s"\s*:\s*")([^"]*)(")' % re.escape(key)
                    )
                    raw2, n = pattern.subn(r"\g<1>%s\g<3>" % digest, raw, count=1)
                    if n:
                        raw = raw2
                        updated += 1
            if updated:
                write_text(prod, raw, nl)
                _log("[校验] 已更新 workbench.html 校验值", log)

    _log(f"[校验] 完成，更新 {updated} 项", log)
    return True


def restore_checksums(install_root: str, log: Optional[LogFn] = None) -> None:
    prod = product_path(install_root)
    bak = prod + BACKUP_SUFFIX
    if os.path.isfile(bak):
        shutil.copy2(bak, prod)
        os.remove(bak)
        _log("[校验] 已恢复 product.json", log)


def get_vscode_version(install_root: str) -> str:
    prod = product_path(install_root)
    try:
        with open(prod, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("vscodeVersion") or data.get("version") or "")
    except Exception:
        return ""


def vsix_version(path: str) -> str:
    try:
        with zipfile.ZipFile(path, "r") as z:
            raw = z.read("extension/package.json")
        return str(json.loads(raw.decode("utf-8")).get("version") or "")
    except Exception:
        return ""


def major_minor(ver: str) -> str:
    parts = re.split(r"[^\d]+", ver)
    parts = [p for p in parts if p]
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return ver


def ensure_language_pack_vsix(install_root: str, log: Optional[LogFn] = None) -> Optional[str]:
    vsix = os.path.join(_writable_root(), LANGUAGE_PACK_VSIX)
    bundled = os.path.join(ROOT, LANGUAGE_PACK_VSIX)
    if not os.path.isfile(vsix) and os.path.isfile(bundled) and bundled != vsix:
        try:
            shutil.copy2(bundled, vsix)
        except OSError:
            vsix = bundled
    cursor_ver = get_vscode_version(install_root)
    local_ver = vsix_version(vsix) if os.path.isfile(vsix) else ""
    if cursor_ver and local_ver and major_minor(cursor_ver) == major_minor(local_ver):
        _log(f"[语言包] 本地 VSIX 已匹配 Cursor VS Code {cursor_ver}", log)
        return vsix

    _log(f"[语言包] 需要匹配版本（Cursor={cursor_ver or '?'}，本地={local_ver or '无'}）", log)
    try:
        body = {
            "filters": [{
                "criteria": [
                    {"filterType": 7, "value": LANGUAGE_PACK_ID},
                ],
                "pageNumber": 1,
                "pageSize": 50,
                "sortBy": 0,
                "sortOrder": 0,
            }],
            "flags": 914,
        }
        req = urllib.request.Request(
            LANGUAGE_PACK_MARKETPLACE_QUERY,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json;api-version=3.0-preview.1",
                "User-Agent": "YiChuang-Cursor-CN",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        versions = []
        for ext in data.get("results", [{}])[0].get("extensions", []):
            for v in ext.get("versions", []):
                versions.append(v.get("version"))
        versions = [v for v in versions if v]
        pick = None
        target_mm = major_minor(cursor_ver) if cursor_ver else ""
        for v in versions:
            if target_mm and major_minor(v) == target_mm:
                pick = v
                break
        if not pick and versions:
            pick = versions[0]
        if not pick:
            _log("[语言包] 市场未返回可用版本，使用本地文件（若有）", log)
            return vsix if os.path.isfile(vsix) else None

        url = LANGUAGE_PACK_MARKETPLACE_DOWNLOAD.format(version=pick)
        _log(f"[语言包] 下载 {pick} ...", log)
        req2 = urllib.request.Request(url, headers={"User-Agent": "YiChuang-Cursor-CN"})
        with urllib.request.urlopen(req2, timeout=120) as resp2:
            blob = resp2.read()
        # 市场有时返回 gzip
        if blob[:2] == b"\x1f\x8b":
            blob = gzip.decompress(blob)
        with open(vsix, "wb") as f:
            f.write(blob)
        _log(f"[语言包] 已保存 {vsix}", log)
        return vsix
    except Exception as e:
        _log(f"[语言包] 下载失败: {e}", log)
        return vsix if os.path.isfile(vsix) else None


def set_locale_zh(user_data: str, log: Optional[LogFn] = None) -> None:
    locale_path = os.path.join(user_data, "User", "locale.json")
    os.makedirs(os.path.dirname(locale_path), exist_ok=True)
    data = {"locale": "zh-cn"}
    with open(locale_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _log("[语言] 已设置 locale.json = zh-cn", log)

    # Cursor 也读取 ~/.cursor/argv.json（支持注释的 JSONC）
    argv = os.path.join(os.path.expanduser("~"), ".cursor", "argv.json")
    try:
        os.makedirs(os.path.dirname(argv), exist_ok=True)
        if os.path.isfile(argv):
            text = open(argv, encoding="utf-8").read()
            if re.search(r'"locale"\s*:', text):
                text2 = re.sub(r'"locale"\s*:\s*"[^"]*"', '"locale": "zh-cn"', text, count=1)
            else:
                text2 = re.sub(r"\}\s*$", ',\n\t"locale": "zh-cn"\n}\n', text.rstrip())
            if text2 != text:
                open(argv, "w", encoding="utf-8").write(text2)
                _log("[语言] 已设置 argv.json locale = zh-cn", log)
        else:
            open(argv, "w", encoding="utf-8").write(
                '{\n\t"locale": "zh-cn"\n}\n'
            )
            _log("[语言] 已创建 argv.json locale = zh-cn", log)
    except OSError as e:
        _log(f"[语言] 写入 argv.json 失败: {e}", log)


def install_language_pack(install_root: str, user_data: str, log: Optional[LogFn] = None) -> bool:
    vsix = ensure_language_pack_vsix(install_root, log)
    if not vsix or not os.path.isfile(vsix):
        _log("[语言包] 无可用 VSIX，跳过安装（可稍后手动装中文语言包）", log)
        set_locale_zh(user_data, log)
        return False

    cli = cursor_cli(install_root)
    if not cli:
        _log("[语言包] 未找到 Cursor CLI，已写入 locale，请手动安装 VSIX", log)
        set_locale_zh(user_data, log)
        return False

    cmd = [cli, "--install-extension", vsix, "--force"]
    _log(f"[语言包] 安装中: {' '.join(cmd)}", log)
    try:
        # Windows 上 cursor.cmd 需 shell
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            shell=is_windows(),
        )
        out = (r.stdout or "") + (r.stderr or "")
        if out.strip():
            _log(out.strip()[:800], log)
        set_locale_zh(user_data, log)
        return r.returncode == 0
    except Exception as e:
        _log(f"[语言包] 安装异常: {e}", log)
        set_locale_zh(user_data, log)
        return False


def restore(install_root: str, log: Optional[LogFn] = None) -> bool:
    if not valid_install(install_root):
        _log("[错误] Cursor 安装目录无效", log)
        return False

    html = html_path(install_root)
    bak = html + BACKUP_SUFFIX

    if os.path.isfile(bak):
        shutil.copy2(bak, html)
        os.remove(bak)
        _log("[还原] 已从备份恢复 workbench.html", log)
    else:
        content, nl = read_text(html)
        cleaned = remove_injection_from_html(content)
        write_text(html, cleaned, nl)
        _log("[还原] 已移除 HTML 注入引用", log)

    cleanup_workbench_js(install_root, log)
    apply_tray(install_root, reverse=True, log=log)
    restore_checksums(install_root, log)
    # 还原后若 HTML 仍被改过（手动清理），再修一次校验
    try:
        update_checksums(install_root, log)
    except Exception:
        pass
    _log("[完成] 已还原。请完全退出并重启 Cursor。", log)
    return True


def install(
    install_root: str,
    user_data: Optional[str] = None,
    with_language_pack: bool = True,
    log: Optional[LogFn] = None,
) -> bool:
    if not valid_install(install_root):
        _log(f"[错误] 无效的 Cursor 目录: {install_root}", log)
        return False

    user_data = user_data or detect_user_data_dir()
    html = html_path(install_root)
    bak = html + BACKUP_SUFFIX

    _log("======== 译窗 · Cursor 中文工具 ========", log)
    _log(f"安装目录: {install_root}", log)
    _log(f"用户数据: {user_data}", log)

    st = status(install_root)
    if st["legacy_injected"]:
        _log("[提示] 检测到旧版汉化，先清理...", log)
        # 尽量从备份恢复；若无备份则剥脚本
        if os.path.isfile(bak):
            shutil.copy2(bak, html)
            _log("[清理] 已用备份恢复 HTML，准备重新注入", log)
        else:
            content, nl = read_text(html)
            write_text(html, remove_injection_from_html(content), nl)
        cleanup_workbench_js(install_root, log)
        apply_tray(install_root, reverse=True, log=log)

    if with_language_pack:
        _log("[步骤] 安装/更新官方简体中文语言包...", log)
        install_language_pack(install_root, user_data, log)

    _log("[步骤] 生成翻译脚本...", log)
    stats = build_stats()
    js = build_js()
    _log(
        f"[词典] dict={stats['dict']} patterns={stats['patterns']} fragments={stats['fragments']}",
        log,
    )

    # 备份原始 HTML（仅当还没有、或当前 HTML 看起来是干净的）
    content, nl = read_text(html)
    clean_enough = MARKER not in content and not any(m in content for m in LEGACY_MARKERS[:2])
    if not os.path.isfile(bak):
        if clean_enough:
            shutil.copy2(html, bak)
            _log("[备份] 已备份 workbench.html", log)
        else:
            # HTML 已有注入：先剥再备
            cleaned = remove_injection_from_html(content)
            write_text(html, cleaned, nl)
            shutil.copy2(html, bak)
            content, nl = read_text(html)
            _log("[备份] 已清理注入后备份 workbench.html", log)

    # 写入 JS
    out_js = js_path(install_root)
    with open(out_js, "w", encoding="utf-8") as f:
        f.write(js)
    _log(f"[写入] {out_js} ({len(js) // 1024} KB)", log)

    # 注入 HTML
    content, nl = read_text(html)
    content = remove_injection_from_html(content)
    snippet = f"\n\t{MARKER}\n\t<script src=\"./{JS_FILE}\"></script>\n"
    if MARKER not in content:
        if "</body>" in content:
            content = content.replace("</body>", f"</body>\n{snippet}")
        else:
            content = content.replace("</html>", f"{snippet}\n</html>")
    write_text(html, content, nl)
    _log("[注入] workbench.html 已注入汉化脚本", log)

    apply_tray(install_root, reverse=False, log=log)
    ok = update_checksums(install_root, log)

    _log("======== 完成 ========", log)
    _log("请完全退出 Cursor（托盘图标也要关）后重新打开。", log)
    if not ok:
        _log("若提示「安装已损坏」，请点「修复校验」或以管理员身份重试。", log)
    return True


def fix_checksum(install_root: str, log: Optional[LogFn] = None) -> bool:
    if not valid_install(install_root):
        _log("[错误] Cursor 安装目录无效", log)
        return False
    return update_checksums(install_root, log)
