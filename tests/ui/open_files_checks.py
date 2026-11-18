"""Open-file checks: dropping a PDF on the window and Finder-style open requests (Dock drop, Open With).

Run by hand on a Mac: uv run python tests/ui/open_files_checks.py
"""
import os
import tempfile
import time

import pymupdf as fitz
import webview
from webview import dom
from webview.platforms.cocoa import BrowserView

from pdfbud import app
from pdfbud.api import Api

import quiet

W = tempfile.mkdtemp(prefix="pdfbud-ui-") + "/"
for name in ("fix.pdf", "second file.pdf"):
    doc = fitz.open()
    for i in range(3):
        doc.new_page().insert_text((72, 100), f"Page {i}", fontsize=14)
    doc.save(W + name)
api = Api(None)
quiet.install()
win = app.make_window(api, **quiet.window_options())
R = []
def ok(n, c, x=""): R.append(bool(c)); print(("PASS " if c else "FAIL ") + n, x, flush=True)
def js(c): return win.evaluate_js("(()=>{" + c + "})()")
def wait(c, t=15):
    e = time.time() + t
    while time.time() < e:
        try:
            if js("return " + c): return True
        except Exception: pass
        time.sleep(.2)
    return False
def run():
    if quiet.SHOW:
        win.on_top = True
    ok("starts at the empty screen", wait("document.body.classList.contains('noDoc') && typeof load==='function'"))
    t0 = time.time()
    while dom._dnd_state["num_listeners"] < 1 and time.time() - t0 < 10: time.sleep(.2)
    ok("drop listener registered with pywebview", dom._dnd_state["num_listeners"] >= 1, dom._dnd_state["num_listeners"])
    app.open_dropped(win, {"dataTransfer": {"files": [{"name": "x.txt", "pywebviewFullPath": W + "notes.txt"}]}})
    time.sleep(1); ok("a non-PDF drop is ignored", js("return document.body.classList.contains('noDoc')"))
    app.open_dropped(win, {"dataTransfer": {"files": [{"name": "fix.pdf", "pywebviewFullPath": W + "fix.pdf"}]}})
    ok("dropping a PDF opens it", wait("!document.body.classList.contains('noDoc') && S.sizes.length===3") and js("return $('path').title") == "Show in Finder: " + W + "fix.pdf")
    d = BrowserView._shared_app_delegate
    ok("app delegate answers open-file requests", d.respondsToSelector_(b"application:openFile:"))
    d.application_openFile_(None, W + "second file.pdf")
    ok("Dock drop / Open With on a running app opens the file (even with a space in the name)", wait("$('path').title.endsWith('second file.pdf')"))
    print("RESULT", sum(R), "/", len(R), flush=True)
    os._exit(0 if all(R) else 1)
webview.start(run)
