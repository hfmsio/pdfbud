"""One open PDF: drawing its pages, searching it, reading its scans, saving a changed copy. No window code.

Everything that leaves this class is in displayed space (the page as seen, rotation included). Inside, words and
lines stay in page space, as PyMuPDF reports them."""
import base64
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from . import ocr
from .core.reading import fields, lines, scan_pages
from .core.redact import apply
from .core.search import find

THUMB_WIDTH = 192
SCAN_DPI = 200
CAP = 5000  # most matches one search returns
MAX_PIXELS = 20_000_000  # no page picture gets bigger than this, however tall the page


def _load(path):
    try:
        doc = pymupdf.open(path)
    except pymupdf.EmptyFileError:
        raise ValueError("This file is empty.") from None
    except Exception:
        raise ValueError("This is not a readable PDF.") from None
    if doc.needs_pass:
        raise ValueError("This PDF is password-protected, which pdfbud does not support yet.")
    if not len(doc):
        raise ValueError("This PDF has no pages.")
    return doc


def _zoom(pg, width):  # picture scale: the wanted width, but never past MAX_PIXELS
    return min(width / pg.rect.width, (MAX_PIXELS / (pg.rect.width * pg.rect.height)) ** .5)


class Session:
    def __init__(self):
        self._lock = threading.Lock()  # PyMuPDF documents are not thread safe
        self._run = None  # the scan reader: its thread, stop flag and document
        self._clear()

    def _clear(self):
        self._doc = self.path = self._words = None
        self._scans, self._ocr = [], {}  # scan page numbers, page -> clickable lines read from them
        self._rot, self._derot = [], []  # page space -> displayed space, and back

    def open(self, path):  # a file that cannot be opened raises and leaves the current one untouched
        doc = _load(path)
        self.ocr_stop()
        with self._lock:
            self._clear()
            self.path, self._doc = Path(path), doc
            self._words = [None] * len(doc)
            self._scans = scan_pages(doc)
            self._rot, self._derot = [p.rotation_matrix for p in doc], [p.derotation_matrix for p in doc]
            threading.Thread(target=self._warm, args=(doc,), daemon=True).start()
            return {"name": self.path.name, "path": str(self.path), "pages": len(doc),
                    "scans": self._scans, "ocr": ocr.available(),
                    "sizes": [[p.rect.width, p.rect.height] for p in doc]}

    def close(self):
        self.ocr_stop()
        with self._lock:
            self._clear()

    def _warm(self, doc):  # reads each page's words, letting page drawing in between
        for i in range(len(doc)):
            with self._lock:
                if self._doc is not doc:
                    return
                if self._words[i] is None:
                    self._words[i] = doc[i].get_text("words")

    def _png(self, n, width):
        pg = self._doc[n]
        z = _zoom(pg, width)
        return pg, pg.get_pixmap(matrix=pymupdf.Matrix(z, z)).tobytes("png")

    @staticmethod
    def _data_url(png):
        return "data:image/png;base64," + base64.b64encode(png).decode()

    def _shown(self, n, box):  # a box from page space to displayed space
        return list(pymupdf.Rect(box) * self._rot[n])

    def page(self, n, width, draft=False):  # draft: small and fast, no text lines
        with self._lock:
            pg, png = self._png(n, width)
            if draft:
                return {"img": self._data_url(png)}
            words = self._words[n] if self._words[n] is not None else pg.get_text("words")
            return {"img": self._data_url(png),
                    "words": [[*self._shown(n, w[:4]), w[4]] for w in words],  # real word boxes: selections snap to these
                    "lines": [{**ln, "box": self._shown(n, ln["box"])} for ln in [*lines(pg), *self._ocr.get(n, [])]],
                    "fields": [{**f, "box": self._shown(n, f["box"])} for f in fields(pg)]}

    def thumb(self, n):
        with self._lock:
            return self._data_url(self._png(n, THUMB_WIDTH)[1])

    def search(self, q="", kind=None, fuzzy=False):  # {matches, truncated}: truncated means there were more than CAP
        doc, words = self._doc, self._words
        if doc is None:
            return {"matches": [], "truncated": False}
        self._warm(doc)  # fills any pages the background pass has not reached yet
        found = find(words, q, kind, fuzzy, cap=CAP + 1) if self._doc is doc else []
        return {"matches": [{**m, "boxes": [self._shown(m["p"], b) for b in m["boxes"]], "ocr": m["p"] in self._ocr}
                            for m in found[:CAP]], "truncated": len(found) > CAP}

    def ocr_start(self):  # reads the scanned pages one at a time in the background
        run = self._run
        if run and run.thread.is_alive() and not run.stop.is_set() and run.doc is self._doc:
            return
        doc, stop = self._doc, threading.Event()
        todo = [i for i in self._scans if i not in self._ocr]

        def work():
            for i in todo:
                with self._lock:
                    if stop.is_set() or self._doc is not doc:
                        return
                    pg = doc[i]
                    z = min(SCAN_DPI / 72, _zoom(pg, 1e9))
                    png, W, H = pg.get_pixmap(matrix=pymupdf.Matrix(z, z)).tobytes("png"), pg.rect.width, pg.rect.height
                words = ocr.read_words(png, W, H)  # the slow part runs outside the lock, so pages keep drawing
                with self._lock:
                    if self._doc is not doc:
                        return
                    back = self._derot[i]  # the reader saw the displayed page; words are kept in page space
                    words = [(*pymupdf.Rect(w[:4]) * back, *w[4:]) for w in words]
                    self._words[i], self._ocr[i] = words, ocr.lines(words)

        thread = threading.Thread(target=work, daemon=True)
        self._run = SimpleNamespace(thread=thread, stop=stop, doc=doc)
        thread.start()

    def ocr_stop(self):
        if self._run:
            self._run.stop.set()

    def ocr_status(self):
        run = self._run
        live = bool(run and run.thread.is_alive() and not run.stop.is_set() and run.doc is self._doc)
        return {"read": sorted(self._ocr), "running": live}

    def suggest_name(self):  # name-redacted.pdf, or name-redacted-1.pdf and so on, so nothing is overwritten
        name, i = self.path.stem + "-redacted.pdf", 1
        while self.path.with_name(name).exists():
            name, i = f"{self.path.stem}-redacted-{i}.pdf", i + 1
        return name

    def save(self, changes, out):  # reopens the file so the loaded copy stays untouched
        out = Path(out)
        if out.suffix.lower() != ".pdf":
            out = out.with_name(out.name + ".pdf")
        if out.exists() and os.path.samefile(out, self.path):
            raise ValueError("pick a different name, the original is never overwritten")
        with self._lock:
            out.write_bytes(apply(pymupdf.open(self.path), changes))
        return out
