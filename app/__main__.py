# -*- coding: utf-8 -*-
"""入口：python -m app  或  python -m app gui|install|restore|fix"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = (argv[0] if argv else "gui").lower()

    if cmd in ("gui", "ui", ""):
        from app.gui import main as gui_main
        gui_main()
        return 0

    if cmd in ("gui-web", "webview", "web"):
        print("精美版 WebView 已从本仓库移除，请使用: python -m app gui")
        return 2

    from app import core

    install = core.detect_install_dir()
    data = core.detect_user_data_dir()

    if cmd in ("install", "hanhua", "setup"):
        ok = core.install(install, data, with_language_pack=True)
        return 0 if ok else 1
    if cmd in ("restore", "reset", "uninstall"):
        ok = core.restore(install)
        return 0 if ok else 1
    if cmd in ("fix", "fix-checksum", "checksum"):
        ok = core.fix_checksum(install)
        return 0 if ok else 1
    if cmd in ("status",):
        print(core.status(install))
        return 0

    print("用法: python -m app [gui|install|restore|fix|status]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
