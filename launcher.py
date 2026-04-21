"""
Strata — launcher (pywebview edition)
Serves templates via a local HTTP server to avoid Edge file:// restrictions
in MSIX sandbox. No Flask — uses Python's built-in http.server.
"""

import os
import sys
import threading
import traceback
import socket
import http.server
import ctypes
import urllib.request
import urllib.parse
import json
import uuid
import platform

MIXPANEL_TOKEN = "d8dafeb70e4d1eaff78262d01e1d3b83"

def get_device_id():
    """Get or create a persistent anonymous device ID."""
    try:
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        id_file = os.path.join(appdata, "Strata", ".device_id")
        os.makedirs(os.path.dirname(id_file), exist_ok=True)
        if os.path.exists(id_file):
            with open(id_file) as f:
                return f.read().strip()
        device_id = str(uuid.uuid4())
        with open(id_file, "w") as f:
            f.write(device_id)
        return device_id
    except Exception:
        return str(uuid.uuid4())

def track(event, properties=None):
    """Send an event to Mixpanel. Runs in background, never blocks the app."""
    def _send():
        try:
            device_id = get_device_id()
            data = {
                "event": event,
                "properties": {
                    "token":        MIXPANEL_TOKEN,
                    "distinct_id":  device_id,
                    "app_version":  "1.0.0",
                    "os":           platform.system(),
                    "os_version":   platform.version(),
                    **(properties or {})
                }
            }
            encoded = urllib.parse.urlencode({
                "data": json.dumps(data)
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.mixpanel.com/track",
                data=encoded,
                method="POST"
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass  # Never let analytics crash the app
    threading.Thread(target=_send, daemon=True).start()

def show_error(title, message):
    """Show a native Windows error dialog without requiring tkinter."""
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)
    else:
        print(f"ERROR: {title}\n{message}", file=sys.stderr)


# ── 1. Locate bundled resources ───────────────────────────────────────────────
def resource_path(*parts):
    """
    Find resource files handling:
    - Dev mode (running from source)
    - PyInstaller (_MEIPASS)
    - Nuitka onefile (__compiled__ + sys.executable dir)
    - Nuitka standalone (next to exe)
    """
    candidates = []

    # PyInstaller
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, *parts))

    # Nuitka onefile extracts to a temp dir next to the exe
    # The exe itself is sys.executable
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(exe_dir, *parts))

    # Nuitka standalone — resources next to the compiled exe
    try:
        # __compiled__ exists in Nuitka-compiled code
        compiled_dir = os.path.dirname(os.path.abspath(__compiled__.__file__))
        candidates.append(os.path.join(compiled_dir, *parts))
    except NameError:
        pass

    # Dev mode — next to launcher.py
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, *parts))
    except NameError:
        pass

    # Nuitka onefile: resources extracted to AppData temp on first run
    appdata = os.environ.get("LOCALAPPDATA", "")
    if appdata:
        candidates.append(os.path.join(appdata, "Strata", "app", *parts))

    for path in candidates:
        if os.path.exists(path):
            return path

    return candidates[0] if candidates else os.path.join(*parts)


# ── 2. Find a free port ───────────────────────────────────────────────────────
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# ── 3. Start local HTTP server for templates ──────────────────────────────────
def start_template_server(template_dir, port):
    """
    Serve the templates folder on localhost so Edge WebView2
    loads them over http:// instead of file:// — avoids sandbox restrictions.
    """
    os.chdir(template_dir)

    handler = http.server.SimpleHTTPRequestHandler
    # Silence request logs
    handler.log_message = lambda *args: None

    server = http.server.HTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ── 4. Persistent data directory ─────────────────────────────────────────────
def get_data_dir():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    if not os.path.isdir(docs):
        docs = os.path.expanduser("~")
    data_dir = os.path.join(docs, "Strata")
    try:
        os.makedirs(data_dir, exist_ok=True)
        test = os.path.join(data_dir, ".write_test")
        open(test, "w").close()
        os.remove(test)
    except Exception:
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        data_dir = os.path.join(appdata, "Strata")
        os.makedirs(data_dir, exist_ok=True)
    return data_dir


# ── 5. Set env vars before importing app ─────────────────────────────────────
os.environ["UNIVERSAL_SEARCH_DATA"] = get_data_dir()

# PyInstaller: app.py is inside _MEIPASS
if hasattr(sys, "_MEIPASS"):
    sys.path.insert(0, sys._MEIPASS)

# Nuitka: app.py is compiled in, but we add exe dir as fallback
exe_dir = os.path.dirname(os.path.abspath(sys.executable))
if exe_dir not in sys.path:
    sys.path.insert(0, exe_dir)


# ── 6. Import the API ─────────────────────────────────────────────────────────
try:
    import app as _app_module
    api = _app_module.Api()
except Exception as e:
    show_error("Strata — Startup Error",
        f"Failed to load application:\n\n{e}\n\n{traceback.format_exc()}")
    sys.exit(1)


# ── 7. Main ───────────────────────────────────────────────────────────────────
def main():
    import webview

    # Track app launch
    track("App Launched")

    data_dir     = os.environ["UNIVERSAL_SEARCH_DATA"]
    template_dir = resource_path("templates")

    # Nuitka fallback — search for templates folder if resource_path missed
    if not os.path.exists(template_dir):
        import tempfile
        search_roots = [
            os.path.dirname(os.path.abspath(sys.executable)),
            os.path.dirname(os.path.abspath(sys.argv[0])),
            tempfile.gettempdir(),
        ]
        for root_dir in search_roots:
            candidate = os.path.join(root_dir, "templates")
            if os.path.exists(os.path.join(candidate, "index.html")):
                template_dir = candidate
                break
            # Also check one level deeper (Nuitka extraction patterns)
            for sub in os.listdir(root_dir) if os.path.isdir(root_dir) else []:
                candidate = os.path.join(root_dir, sub, "templates")
                if os.path.exists(os.path.join(candidate, "index.html")):
                    template_dir = candidate
                    break

    if not os.path.exists(template_dir):
        show_error("Strata — Startup Error",
            f"Could not find application files.\n\nSearched: {template_dir}\n\nPlease reinstall Strata.")
        sys.exit(1)

    # Start local HTTP server so Edge can load the HTML without file:// issues
    port   = find_free_port()
    server = start_template_server(template_dir, port)
    url    = f"http://127.0.0.1:{port}/index.html"

    print("=" * 54)
    print("  Strata")
    print("=" * 54)
    print(f"  Python      : {sys.version.split()[0]}")
    print(f"  Data folder : {data_dir}")
    print(f"  Templates   : {template_dir}")
    print(f"  Server URL  : {url}")
    print("=" * 54)

    # Set Edge WebView2 user data dir via environment variable
    # (MSIX sandbox blocks writes to Temp, which is WebView2's default)
    appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    webview_data_dir = os.path.join(appdata, "Strata", "WebView2")
    os.makedirs(webview_data_dir, exist_ok=True)
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = webview_data_dir

    window = webview.create_window(
        title     = "Strata",
        url       = url,
        js_api    = api,
        width     = 1280,
        height    = 860,
        min_size  = (900, 600),
        resizable = True,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        show_error("Strata — Error",
            f"Unexpected error:\n\n{e}\n\n{traceback.format_exc()}")
