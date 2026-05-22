from __future__ import annotations

from pathlib import Path
import sys

import webview

from app.api import AppApi


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative


def main() -> None:
    web_dir = resource_path("app/web")
    api = AppApi()
    webview.create_window(
        "ChatGPT Session Manager",
        str(web_dir / "index.html"),
        js_api=api,
        width=1160,
        height=760,
        min_size=(920, 620),
        text_select=True,
    )
    webview.start(debug=False, private_mode=False)


if __name__ == "__main__":
    main()
