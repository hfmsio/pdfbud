import time

import pymupdf
import pytest

from pdfbud import ocr
from pdfbud import session as session_module
from pdfbud.session import MAX_PIXELS, Session


@pytest.fixture
def session(tmp_path):
    d = pymupdf.open()
    for i in range(3):
        d.new_page().insert_text((72, 100), f"Page {i} Account 4455 secret@example.com", fontname="helv", fontsize=12)
    f = tmp_path / "doc.pdf"
    d.save(f)
    s = Session()
    s.info = s.open(f)
    return s


def test_session_opens_draws_searches_and_saves_a_copy(session, tmp_path):
    assert session.info["pages"] == 3 and len(session.info["sizes"]) == 3 and session.info["scans"] == []
    assert set(session.page(0, 300, draft=True)) == {"img"}
    assert {"img", "lines", "fields"} <= set(session.page(0, 300))
    hits = session.search(kind="email")["matches"]
    assert [h["p"] for h in hits] == [0, 1, 2]
    out = session.save([{"p": 1, "box": hits[1]["boxes"][0]}], tmp_path / "copy")
    assert out.name == "copy.pdf" and "secret@example.com" not in pymupdf.open(out)[1].get_text()
    assert "secret@example.com" in pymupdf.open(out)[0].get_text()
    with pytest.raises(ValueError):
        session.save([], session.path)  # the original is never overwritten
    assert session.suggest_name() == "doc-redacted.pdf"
    session.close()
    assert session.search("Account")["matches"] == []


def test_a_file_that_cannot_be_opened_leaves_the_current_one_alone(session, tmp_path):
    (tmp_path / "empty.pdf").write_bytes(b"")
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-1.4 not really")
    locked = pymupdf.open()
    locked.new_page().insert_text((50, 50), "secret")
    locked.save(tmp_path / "locked.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    for name, message in (("empty", "empty"), ("bad", "readable"), ("locked", "password")):
        with pytest.raises(ValueError, match=message):
            session.open(tmp_path / f"{name}.pdf")
    assert session.path.name == "doc.pdf" and "img" in session.page(0, 100)  # still the same open document


def test_save_adds_pdf_to_the_name_and_never_overwrites_the_original(session, tmp_path):
    assert session.save([], tmp_path / "Q3 report 2.5").name == "Q3 report 2.5.pdf"
    (tmp_path / "A").write_text("x")
    if (tmp_path / "a").exists():  # a case-insensitive disk: DOC.PDF is the same file as doc.pdf
        with pytest.raises(ValueError):
            session.save([], tmp_path / "DOC.PDF")


def test_a_very_tall_page_is_drawn_small_and_search_says_when_it_stopped_early(tmp_path, monkeypatch):
    d = pymupdf.open()
    d.new_page(width=100, height=14400).insert_text((10, 100), "match match match match match", fontsize=8)
    d.save(tmp_path / "tall.pdf")
    s = Session()
    s.open(tmp_path / "tall.pdf")
    pix = pymupdf.Pixmap(__import__("base64").b64decode(s.page(0, 3200, draft=True)["img"].split(",")[1]))
    assert pix.width * pix.height <= MAX_PIXELS * 1.02
    monkeypatch.setattr(session_module, "CAP", 3)
    found = s.search("match")
    assert len(found["matches"]) == 3 and found["truncated"]


@pytest.mark.parametrize("rot", [90, 180, 270])
def test_a_rotated_page_gives_boxes_in_displayed_space(tmp_path, ink, rot):
    d = pymupdf.open()
    p = d.new_page(width=400, height=300)
    p.insert_text((50, 100), "ALPHA BRAVO", fontsize=22)
    p.set_rotation(rot)
    d.save(tmp_path / "rot.pdf")
    s = Session()
    s.open(tmp_path / "rot.pdf")
    shown = pymupdf.open(tmp_path / "rot.pdf")[0]
    assert ink(shown, s.page(0, 400)["lines"][0]["box"]) > .08  # the line box sits on its ink in the picture
    assert ink(shown, s.search("BRAVO")["matches"][0]["boxes"][0]) > .08  # and so does a search hit
    out = pymupdf.open(stream=pymupdf.open(s.save([{"p": 0, "box": s.search("BRAVO")["matches"][0]["boxes"][0]}], tmp_path / "o")).tobytes())
    assert "BRAVO" not in out[0].get_text() and "ALPHA" in out[0].get_text()


@pytest.mark.skipif(not ocr.available(), reason="needs macOS text recognition")
def test_scans_on_a_rotated_page_are_read_into_displayed_space(tmp_path, ink):
    src = pymupdf.open()
    src.new_page(width=600, height=400).insert_text((50, 100), "Thank you for your order", fontsize=24)
    d = pymupdf.open()
    q = d.new_page(width=600, height=400)
    q.insert_image(q.rect, stream=src[0].get_pixmap(dpi=150).tobytes("png"))
    q.set_rotation(90)
    d.save(tmp_path / "scan.pdf")
    s = Session()
    s.open(tmp_path / "scan.pdf")
    s.ocr_start()
    end = time.time() + 30
    while 0 not in s.ocr_status()["read"] and time.time() < end:
        time.sleep(.2)
    hit = s.search("Thank")["matches"][0]
    assert hit["ocr"] and ink(pymupdf.open(tmp_path / "scan.pdf")[0], hit["boxes"][0]) > .08
    s.ocr_stop()
    assert not s.ocr_status()["running"]
