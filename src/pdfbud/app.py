"""Starting the app: the window, dropped files, and open-file requests from Finder."""
import json
import sys
import threading
from pathlib import Path

import pymupdf
import webview
from webview.dom import DOMEventHandler

from . import mac, ocr
from .api import Api

WEB = Path(__file__).with_name("web")


def open_dropped(window, e):  # pywebview adds the full path of each dropped file; open the first PDF
    path = next((f["pywebviewFullPath"] for f in e["dataTransfer"].get("files", [])
                 if f.get("pywebviewFullPath", "").lower().endswith(".pdf")), None)
    if path:
        window.evaluate_js(f"load({json.dumps(path)})")


def confirm_discard(api, ask=None):  # True when the app may close; asks first if there are unsaved changes
    n = api.changes  # closing runs on the Mac main thread: asking the page from here would wait on that same thread forever
    return not n or (ask or mac.confirm)(f"Discard {n} unsaved changes?", "Discard and close", "Keep working")


def make_window(api, **options):  # options go to webview.create_window; the tests use them to keep the window out of the way
    window = webview.create_window("pdfbud", str(WEB / "index.html"), js_api=api, width=1100, height=1000,
                                   min_size=(760, 480), **options)
    screen = mac.Screen(window, lambda full: window.evaluate_js(f"setFS({str(full).lower()}, true)"))
    api._attach(window, screen)
    dropping = threading.Event()  # the drop handler is registered once

    def on_loaded():
        if not dropping.is_set():
            window.dom.document.events.drop += DOMEventHandler(lambda e: open_dropped(window, e), True, True)
            dropping.set()

    def on_screen_mode(full):
        if screen.changed(full):
            window.evaluate_js(f"setFS({str(full).lower()}, true)")

    def open_file(name):  # runs on the Mac main thread
        if not name.lower().endswith(".pdf"):  # the Mac also reports the script's own name when started from a terminal
            return False
        if api._request_open(name):  # hand the work to another thread, or the window locks up
            threading.Thread(target=window.evaluate_js, args=(f"load({json.dumps(name)})",), daemon=True).start()
        return True  # otherwise the page picks the file up when it is ready

    window.events.loaded += on_loaded
    window.events.closing += lambda: confirm_discard(api)
    window.events.maximized += lambda: on_screen_mode(True)
    window.events.restored += lambda: on_screen_mode(False)
    mac.on_open_files(open_file)
    return window


def self_check():  # for checking a packaged app from a terminal: can this build read text from a picture?
    pg = pymupdf.open().new_page(width=300, height=100)
    pg.insert_text((20, 60), "Hello 123", fontsize=30)
    read = ocr.read_words(pg.get_pixmap(dpi=200).tobytes("png"), 300, 100) if ocr.available() else []
    print(json.dumps({"ocr": ocr.available(), "read": " ".join(w[4] for w in read)}))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        self_check()
        return
    mac.name_app("pdfbud")
    make_window(Api(next((a for a in argv if a.lower().endswith(".pdf")), None)))
    webview.start()
