"""StudyMind native Windows shell with an embedded WebView2 window."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request

APP_NAME = "StudyMindAI"
URL = "http://127.0.0.1:8765"


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def configure() -> Path:
    root = bundle_root()
    app_dir = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME
    data = app_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("STUDYMIND_BUNDLE_ROOT", str(root))
    os.environ.setdefault("STUDYMIND_DATA_DIR", str(data))
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (data / "studymind.sqlite3").as_posix())
    os.environ.setdefault("EMBEDDING_MODE", "keyword")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    return app_dir


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


def wait_until_ready(server) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if ready():
            return
        if not server_thread.is_alive():
            raise RuntimeError("本地服务启动失败，请查看应用日志。")
        time.sleep(0.25)
    raise RuntimeError("本地服务启动超时，请查看应用日志。")


def run_server(server) -> None:
    server.run()


def main() -> int:
    global server_thread
    app_dir = configure()
    data = app_dir / "data"
    if listening(8765) and not ready():
        raise SystemExit("端口 8765 已被其他程序占用。")

    import uvicorn
    from app.main import app

    log_stream = (data / "app.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = log_stream
    sys.stderr = log_stream
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, workers=1, log_level="info")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=run_server, args=(server,), name="StudyMindServer", daemon=True)
    server_thread.start()

    try:
        wait_until_ready(server)
        import webview

        window = webview.create_window(
            "StudyMind AI · 智学助手",
            URL,
            width=1360,
            height=860,
            min_size=(1024, 680),
            background_color="#f6f7fb",
            text_select=True,
        )

        def closing() -> None:
            server.should_exit = True

        window.events.closed += closing
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(app_dir / "webview"),
        )
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)
        log_stream.close()
    return 0


server_thread: threading.Thread

if __name__ == "__main__":
    raise SystemExit(main())
