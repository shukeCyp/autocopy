#!/usr/bin/env python3
"""TK 爆款复刻 — Desktop Launcher

Starts the FastAPI backend in a background thread, then opens a native
desktop window via PyWebView pointing at the local server.
"""

from __future__ import annotations

import sys
import threading
import time
import logging

import uvicorn
import webview


def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("tk-hot-copy")

    host = "127.0.0.1"
    port = 8799
    url = f"http://{host}:{port}"

    # Start FastAPI in background thread
    logger.info("starting backend server...")

    def run_server():
        uvicorn.run(
            "app.server.main:app",
            host=host,
            port=port,
            log_level="warning",
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        logger.error("backend server failed to start")
        sys.exit(1)

    logger.info(f"backend ready at {url}")
    logger.info("opening desktop window...")

    # Open native window maximized by default.
    window = webview.create_window(
        title="TK 爆款复刻",
        url=url,
        width=1280,
        height=800,
        min_size=(900, 600),
        resizable=True,
        fullscreen=False,
        maximized=True,
    )

    def maximize_window():
        window.maximize()

    webview.start(maximize_window, gui="cocoa" if sys.platform == "darwin" else None)
    logger.info("window closed, exiting")


if __name__ == "__main__":
    main()
