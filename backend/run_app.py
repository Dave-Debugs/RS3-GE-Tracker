import uvicorn
import multiprocessing
import sys
import threading
import time
import webbrowser
from PIL import Image
import pystray
import os

def open_browser(icon=None, item=None):
    webbrowser.open("http://127.0.0.1:8000")

def quit_app(icon, item):
    icon.stop()
    os._exit(0)

def run_server():
    try:
        import sys, io
        if sys.stdout is None: sys.stdout = io.StringIO()
        if sys.stderr is None: sys.stderr = io.StringIO()
        if getattr(sys, 'frozen', False):
            sys.path.insert(0, sys._MEIPASS)
        from app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
    except Exception as e:
        import traceback
        with open("server_error.log", "w") as f:
            f.write(traceback.format_exc())

def create_icon():
    try:
        icon_path = os.path.join(sys._MEIPASS, "icon.ico") if getattr(sys, 'frozen', False) else "icon.ico"
        image = Image.open(icon_path)
    except Exception as e:
        with open("icon_error.log", "w") as f:
            f.write(str(e))
        image = Image.new('RGB', (64, 64), color = (0, 128, 0))
    
    icon = pystray.Icon("RS3Tracker", image, "RS3 GE Tracker", menu=pystray.Menu(
        pystray.MenuItem("Open in Browser", open_browser, default=True),
        pystray.MenuItem("Quit", quit_app)
    ))
    return icon

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        import sys, io, urllib.request
        if sys.stdout is None: sys.stdout = io.StringIO()
        if sys.stderr is None: sys.stderr = io.StringIO()

        def quit_action(icon, item):
            icon.stop()
            os._exit(0)

        icon_path = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(__file__)), "icon.ico")
        image = Image.open(icon_path)

        icon = pystray.Icon("RS3 GE Tracker", image, "RS3 GE Tracker", menu=pystray.Menu(
            pystray.MenuItem("Open in Browser", lambda: webbrowser.open("http://127.0.0.1:8000")),
            pystray.MenuItem("Quit", quit_action)
        ))

        def wait_and_open_browser(icon):
            icon.visible = True
            for _ in range(30):
                try:
                    urllib.request.urlopen("http://127.0.0.1:8000", timeout=1)
                    webbrowser.open("http://127.0.0.1:8000")
                    break
                except Exception:
                    time.sleep(0.5)

        t = threading.Thread(target=run_server, daemon=True)
        t.start()

        icon.run(setup=wait_and_open_browser)
    except Exception as e:
        import traceback
        with open("main_error.log", "w") as f:
            f.write(traceback.format_exc())
