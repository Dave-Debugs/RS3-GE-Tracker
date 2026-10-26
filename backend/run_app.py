import sys
import io
if sys.stdout is None:
    class DummyOutput:
        def write(self, x): pass
        def flush(self): pass
        def isatty(self): return False
    sys.stdout = DummyOutput()
if sys.stderr is None:
    sys.stderr = DummyOutput()

import ctypes
import json
import multiprocessing
import os
import threading
import time
import urllib.request
import webbrowser
from PIL import Image
import pystray
import uvicorn


def _log_dir() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = os.path.join(local_app_data, "RS3 GE Tracker")
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))


def open_browser(icon=None, item=None):
    webbrowser.open("http://127.0.0.1:8000")


def quit_app(icon, item):
    icon.stop()
    os._exit(0)


def _msgbox(text: str, title: str, flags: int = 0x40) -> int:
    try:
        return ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        return 0


def check_updates_tray(icon=None, item=None):
    def _worker():
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/updater/check")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data.get("update_available"):
                cur = data.get("current_version", "1.3.0")
                _msgbox(
                    f"You are running the latest version of RS3 GE Tracker (v{cur}).",
                    "No Updates Available",
                    0x40,
                )
                return
            latest = data.get("latest_version", "")
            dl_url = data.get("download_url")
            chk_url = data.get("checksum_url")
            asset_name = data.get("asset_name", "")
            ans = _msgbox(
                f"A new version of RS3 GE Tracker (v{latest}) is available!\n\n"
                "Would you like to download and install it now?",
                "Update Available",
                0x04 | 0x40,
            )
            if ans == 6 and dl_url:
                payload = json.dumps({
                    "download_url": dl_url,
                    "checksum_url": chk_url,
                    "asset_name": asset_name,
                }).encode("utf-8")
                apply_req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/updater/apply",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(apply_req, timeout=120) as apply_resp:
                    res = json.loads(apply_resp.read().decode("utf-8"))
                if res.get("ok") and not res.get("applied") and data.get("release_url"):
                    webbrowser.open(data["release_url"])
            elif ans == 6 and data.get("release_url"):
                webbrowser.open(data["release_url"])
        except Exception as e:
            _msgbox(f"Could not check for updates:\n{e}", "Update Error", 0x30)

    threading.Thread(target=_worker, daemon=True).start()


def run_server():
    try:
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()
        if getattr(sys, "frozen", False):
            sys.path.insert(0, sys._MEIPASS)
        from app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
    except Exception:
        import traceback
        with open(os.path.join(_log_dir(), "server_error.log"), "w") as f:
            f.write(traceback.format_exc())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()

        icon_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "icon.ico")
        try:
            image = Image.open(icon_path)
        except Exception:
            image = Image.new("RGB", (64, 64), color=(0, 128, 0))

        icon = pystray.Icon(
            "RS3 GE Tracker",
            image,
            "RS3 GE Tracker v1.3",
            menu=pystray.Menu(
                pystray.MenuItem("Open in Browser", open_browser, default=True),
                pystray.MenuItem("Check for Updates...", check_updates_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", quit_app),
            ),
        )

        def wait_and_open_browser(tray_icon):
            tray_icon.visible = True
            for _ in range(30):
                try:
                    urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1)
                    webbrowser.open("http://127.0.0.1:8000")
                    break
                except Exception:
                    time.sleep(0.5)

        t = threading.Thread(target=run_server, daemon=True)
        t.start()

        icon.run(setup=wait_and_open_browser)
    except Exception:
        import traceback
        with open(os.path.join(_log_dir(), "main_error.log"), "w") as f:
            f.write(traceback.format_exc())
