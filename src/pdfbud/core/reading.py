"""Reading a page: its text lines, its form fields, and whether it is only a scan."""
import pymupdf

KIND = {"Text": "text", "CheckBox": "check", "ComboBox": "choice", "ListBox": "choice"}
ROTATE = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}  # a line's direction -> insert_text's rotate


def lines(page):
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            s = ln["spans"][0]
            yield dict(box=ln["bbox"], text="".join(x["text"] for x in ln["spans"]), size=s["size"], font=s["font"],
                       color=s["color"], origin=s["origin"], rotate=ROTATE.get((round(ln["dir"][0]), round(ln["dir"][1])), 0))


def fields(page):  # form fields the window can fill in; read-only ones, radio buttons and signatures are skipped
    for w in page.widgets() or []:
        kind = KIND.get(w.field_type_string)
        if kind and not w.field_flags & 1:
            v = w.field_value
            v = v not in ("Off", "", None, False) if kind == "check" else (v if isinstance(v, str) else (v[0] if v else ""))
            yield dict(xref=w.xref, name=w.field_name, kind=kind, box=list(w.rect), value=v,
                       choices=list(w.choice_values or []), multiline=bool(w.field_flags & 4096))


def scan_pages(doc):  # pages that are mostly one picture with next to no text of their own
    return [i for i, pg in enumerate(doc)
            if pg.get_images() and len(pg.get_text("words")) < 25
            and max((pymupdf.Rect(x["bbox"]).get_area() for x in pg.get_image_info()), default=0) > .4 * pg.rect.get_area()]
