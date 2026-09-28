"""StudyMind Windows executable entry point.

The executable serves the bundled Vue application and stores user data under
``%LOCALAPPDATA%/StudyMindAI``. It defaults to SQLite so a clean Windows machine
does not need a separately installed database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

APP_NAME = "StudyMindAI"
URL = "http://127.0.0.1:8765"


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def configure() -> Path:
    root = bundle_root()
    data = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME / "data"
    data.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STUDYMIND_BUNDLE_ROOT", str(root))
    os.environ.setdefault("STUDYMIND_DATA_DIR", str(data))
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data / "studymind.sqlite3").as_posix())
    os.environ.setdefault("EMBEDDING_MODE", "keyword")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    return data


def ready() -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(URL + "/api/health", timeout=2) as response:
            return json.load(response).get("status") == "ok"
    except Exception:
        return False


def listening(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def open_when_ready(server) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if ready():
            if "--no-browser" not in sys.argv:
                webbrowser.open(URL)
            return
        if getattr(server, "should_exit", False):
            return
        time.sleep(0.25)


def main() -> int:
    data = configure()
    if ready():
        if "--no-browser" not in sys.argv:
            webbrowser.open(URL)
        return 0
    if listening(8765):
        raise SystemExit("端口 8765 已被其他程序占用。")

    import uvicorn
    from app.main import app

    log_path = data / "app.log"
    log_stream = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = log_stream
    sys.stderr = log_stream
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, workers=1, log_level="info")
    server = uvicorn.Server(config)
    threading.Thread(target=open_when_ready, args=(server,), daemon=True).start()
    try:
        server.run()
    finally:
        log_stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
