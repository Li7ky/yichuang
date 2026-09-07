# -*- coding: utf-8 -*-
"""译窗 — HTML 桌面版（pywebview，上一版精美界面）。"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP_DIR)
WEBUI = os.path.join(APP_DIR, "webui")
INDEX = os.path.join(WEBUI, "index.html")
ICON = os.path.join(WEBUI, "assets", "logo.ico")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import core  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_static_server() -> tuple[ThreadingHTTPServer, str]:
    port = _free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=WEBUI)

    def log_message(self, format, *args):  # noqa: A002
        return

    handler.log_message = log_message  # type: ignore
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/index.html"


class Bridge:
    def __init__(self) -> None:
        self._window = None

    def set_window(self, window) -> None:
        self._window = window

    def get_init(self) -> dict:
        return {
            "install": core.detect_install_dir(),
            "userdata": core.detect_user_data_dir(),
            "version": "1.0.0",
        }

    def status(self, install_path: str = "") -> dict:
        root = (install_path or "").strip() or core.detect_install_dir()
        return core.status(root)

    def browse_folder(self, title: str = "选择文件夹") -> str:
        import webview

        if not self._window:
            return ""
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return ""
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def alert(self, title: str, message: str) -> None:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x40)
        except Exception:
            print(f"[{title}] {message}")

    def confirm(self, title: str, message: str) -> bool:
        try:
            import ctypes

            return ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x24) == 6
        except Exception:
            return True

    def _push_log(self, msg: str) -> None:
        print(msg)
        if not self._window:
            return
        try:
            self._window.evaluate_js(f"appendLog({json.dumps(str(msg), ensure_ascii=False)})")
        except Exception:
            pass

    def install(self, install_path: str, userdata_path: str, langpack: bool = True) -> bool:
        def log(msg: str) -> None:
            self._push_log(msg)

        try:
            return bool(
                core.install(
                    (install_path or "").strip() or core.detect_install_dir(),
                    (userdata_path or "").strip() or core.detect_user_data_dir(),
                    with_language_pack=bool(langpack),
                    log=log,
                )
            )
        except Exception as e:
            log(f"[异常] {e}")
            return False

    def restore(self, install_path: str) -> bool:
        def log(msg: str) -> None:
            self._push_log(msg)

        try:
            return bool(
                core.restore((install_path or "").strip() or core.detect_install_dir(), log=log)
            )
        except Exception as e:
            log(f"[异常] {e}")
            return False

    def fix(self, install_path: str) -> bool:
        def log(msg: str) -> None:
            self._push_log(msg)

        try:
            return bool(
                core.fix_checksum((install_path or "").strip() or core.detect_install_dir(), log=log)
            )
        except Exception as e:
            log(f"[异常] {e}")
            return False

    def open_cursor(self, install_path: str) -> bool:
        root = (install_path or "").strip() or core.detect_install_dir()
        exe = core.cursor_exe(root)
        if not os.path.exists(exe):
            self.alert("错误", f"找不到 Cursor：{exe}")
            return False
        try:
            if core.is_macos():
                subprocess.Popen(["open", root])
            else:
                subprocess.Popen([exe], shell=False)
            return True
        except Exception as e:
            self.alert("错误", str(e))
            return False


def main() -> None:
    if not os.path.isfile(INDEX):
        raise SystemExit(f"缺少界面文件: {INDEX}")

    try:
        import webview
    except ImportError:
        print("正在安装 pywebview ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview", "-q"])
        import webview

    httpd, url = _start_static_server()
    bridge = Bridge()
    kwargs = dict(
        title="译窗",
        url=url,
        js_api=bridge,
        width=980,
        height=640,
        min_size=(900, 600),
        background_color="#12171E",
        text_select=True,
    )
    if os.path.isfile(ICON):
        kwargs["icon"] = ICON
    window = webview.create_window(**kwargs)
    bridge.set_window(window)
    try:
        webview.start(debug=False)
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
