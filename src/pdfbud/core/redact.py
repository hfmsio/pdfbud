"""Applying a list of changes to a document: boxes, replaced lines and filled form fields.

Boxes arrive in displayed space (as the page is seen, rotation included). PyMuPDF works in page space, so each box is
turned back with the page's derotation matrix before it is used."""
import re
from itertools import groupby

import pymupdf

FONT = {"Times": "tiro", "Courier": "cour"}  # family prefix -> base-14 name, default "helv"
PLAIN = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."})  # typography the base fonts lack


def plain(text):
    return text.translate(PLAIN)


def bad_chars(text):  # characters the replacement font cannot write
    return sorted({c for c in plain(text) if ord(c) > 255})


def apply(doc, changes):
    """Changes are {p, box} (black box), {p, box, text, ...} (replace a line) or {p, field, value} (fill a form field).
    Returns the bytes of the changed document, with its file info cleared."""
    removed = []
    for p, group in groupby(sorted(changes, key=lambda c: c["p"]), lambda c: c["p"]):
        page, cs = doc[p], list(group)
        removed += _redact(page, [c for c in cs if "field" not in c])
        _fill(page, [c for c in cs if "field" in c])
    doc.scrub(remove_links=False, hidden_text=False)  # metadata, XML, attached files, thumbnails; the text layer of scans stays
    _scrub_outline(doc, removed)
    _drop_xfa(doc)
    return doc.tobytes(garbage=4, deflate=True)


def _redact(page, cs):  # returns the text that was under the boxes
    rects = [pymupdf.Rect(c["box"]) * page.derotation_matrix for c in cs]
    for r in rects:
        _remove_touching(page, r)
    under = [page.get_textbox(r) for r in rects]
    for c, r in zip(cs, rects, strict=True):
        page.add_redact_annot(r, fill=_background(page, c["box"]) if "text" in c else (0, 0, 0))
    if cs:
        page.apply_redactions()  # deletes the text under every box, not just covers it
    for c in cs:
        if "text" in c:
            _write(page, c)
    return under


def _remove_touching(page, rect):  # form fields, notes, highlights, stamps and links hold things a black box cannot reach
    for a in [*(page.annots() or []), *(page.widgets() or [])]:
        if a.rect.intersects(rect):
            page.delete_widget(a) if isinstance(a, pymupdf.Widget) else page.delete_annot(a)
    for link in page.get_links():
        if pymupdf.Rect(link["from"]).intersects(rect):
            page.delete_link(link)


def _background(page, box):  # the colour behind a line (box in displayed space), so the new text sits on the same paper
    return tuple(v / 255 for v in page.get_pixmap(clip=box).pixel(0, 0)[:3])


def _write(page, c):
    text = plain(c["text"])
    if bad := bad_chars(text):
        raise ValueError(f"can't write {' '.join(bad)}: the font has Latin letters only")
    font = next((v for k, v in FONT.items() if c["font"].startswith(k)), "helv")
    room = max(page.rect.x1 - c["origin"][0] - 36, 24)
    size = min(c["size"], c["size"] * room / max(pymupdf.get_text_length(text, font, c["size"]), 1))
    page.insert_text(c["origin"], text, fontname=font, fontsize=max(size, 4), rotate=c.get("rotate", 0),
                     color=pymupdf.sRGB_to_pdf(c["color"]))


def _fill(page, cs):
    for c in cs:
        w = next((w for w in page.widgets() or [] if w.xref == c["field"]), None)
        if w:  # a box over the field may have removed it already
            w.field_value = c["value"]
            w.update()


def _scrub_outline(doc, removed):  # a bookmark title can quote text that was just redacted
    words = {w.casefold() for t in removed for w in re.findall(r"\w{4,}", t)}
    toc = doc.get_toc()
    hit = [e for e in toc if words & {w.casefold() for w in re.findall(r"\w{4,}", e[1])}]
    if hit:
        for e in hit:
            e[1] = "[redacted]"
        doc.set_toc(toc)


def _drop_xfa(doc):  # XFA form data would still hold what a box removed
    root = doc.pdf_catalog()
    if doc.xref_get_key(root, "AcroForm/XFA")[0] != "null":
        doc.xref_set_key(root, "AcroForm/XFA", "null")
