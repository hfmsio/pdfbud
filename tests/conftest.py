import pymupdf
import pytest


@pytest.fixture
def ink():
    """ink(page, box): the share of dark pixels inside a box of the page as drawn (displayed space)."""
    def share(page, box):
        pm = page.get_pixmap(clip=pymupdf.Rect(box))
        return sum(1 for i in range(0, len(pm.samples), pm.n) if pm.samples[i] < 128) / (pm.width * pm.height)
    return share
