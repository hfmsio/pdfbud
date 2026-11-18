"""Builds packaging/pdfbud.icns from packaging/icon.png, the paperfold app icon (needs macOS iconutil).

The picture fills its square edge to edge, so it is shrunk onto a transparent canvas to match the margin of other Mac icons.
icon.svg is the editable master; it uses gradients that PyMuPDF cannot draw, which is why the build starts from the PNG.
"""
import subprocess
import tempfile
from pathlib import Path

import pymupdf

here = Path(__file__).parent
MARGIN = .097  # of the canvas, on every side


def render(size):
    page = pymupdf.open().new_page(width=size, height=size)
    lo, hi = size * MARGIN, size * (1 - MARGIN)
    page.insert_image(pymupdf.Rect(lo, lo, hi, hi), filename=str(here / "icon.png"))
    return page.get_pixmap(alpha=True)


with tempfile.TemporaryDirectory() as t:
    iconset = Path(t) / "pdfbud.iconset"
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            render(size * scale).save(iconset / name)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(here / "pdfbud.icns")], check=True)
