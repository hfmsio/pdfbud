"""What the page can call. Thin on purpose: file dialogs and window actions here, everything else in Session."""
import threading
from pathlib import Path

import webview

from . import mac
from .core.redact import bad_chars
from .session import Session


class Api:  # underscore names stay hidden from the page
    def __init__(self, start=None):
        self._session, self._start = Session(), start
        self._window = self._screen = None
        self.changes = 0  # how many unsaved changes the page holds; the page reports it, so closing never has to ask the page
        self._ready, self._guard = threading.Event(), threading.Lock()  # set once the page has asked for its first file

    def _attach(self, window, screen):
        self._window, self._screen = window, screen

    def initial(self):  # the file the app was started with, if any; the page calls this once, when it is ready
        with self._guard:
            self._ready.set()
            start = self._start
        return start and self.open(start)

    def _request_open(self, path):  # a Finder open request: True if the page can load it now, else it waits for initial()
        with self._guard:
            if self._ready.is_set():
                return True
            self._start = path
            return False

    def open(self, path=None):
        path = path or next(iter(self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("PDF (*.pdf)",)) or []), None)
        return self._session.open(path) if path else None

    def close(self):
        self._session.close()

    def page(self, n, width, draft=False):
        return self._session.page(n, width, draft)

    def thumb(self, n):
        return self._session.thumb(n)

    def search(self, q="", kind=None, fuzzy=False):
        return self._session.search(q, kind, fuzzy)

    def bad_chars(self, text):  # characters an edited line cannot be written with
        return bad_chars(text)

    def ocr_start(self):
        self._session.ocr_start()

    def ocr_stop(self):
        self._session.ocr_stop()

    def ocr_status(self):
        return self._session.ocr_status()

    def save(self, changes):  # asks where to save; returns the new file's path, or None if cancelled
        path = self._session.path
        pick = self._window.create_file_dialog(webview.SAVE_DIALOG, directory=str(path.parent),
                                               save_filename=self._session.suggest_name())
        if not pick:
            return None
        out = self._session.save(changes, Path(pick if isinstance(pick, str) else pick[0]))
        mac.reveal(out)
        return str(out)

    def set_title(self, title):  # the window's title bar
        self._window.set_title(title)

    def report_changes(self, n):
        self.changes = n

    def copy_text(self, text):
        mac.copy(text)

    def reveal(self):  # show the open file in Finder
        if self._session.path:
            mac.reveal(self._session.path)

    def fullscreen(self, on):
        self._screen.set(on)
