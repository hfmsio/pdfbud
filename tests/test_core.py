import pymupdf
import pytest

from pdfbud import ocr
from pdfbud.core.reading import fields, lines, scan_pages
from pdfbud.core.redact import apply, bad_chars
from pdfbud.core.search import find


@pytest.fixture
def doc(tmp_path):
    d = pymupdf.open()
    p = d.new_page()
    p.insert_text((72, 100), "Account: 4455 8821 0093 1177", fontname="helv", fontsize=12)
    p.insert_text((72, 130), "Name: Jane Example", fontname="helv", fontsize=12)
    w = pymupdf.Widget()  # a filled form field and a note over the account line: boxes must not leave them behind
    w.field_type, w.field_name, w.rect, w.field_value = pymupdf.PDF_WIDGET_TYPE_TEXT, "acct", pymupdf.Rect(180, 88, 260, 104), "WIDGET-SECRET"
    p.add_widget(w)
    p.add_text_annot((100, 92), "NOTE-SECRET")
    p.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 88, 240, 104), "uri": "https://under-the-box.example"})  # goes with the box
    p.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 300, 200, 316), "uri": "https://elsewhere.example"})  # must survive
    for name, kind, rect in (("fname", pymupdf.PDF_WIDGET_TYPE_TEXT, (72, 200, 200, 216)), ("agree", pymupdf.PDF_WIDGET_TYPE_CHECKBOX, (72, 230, 86, 244)),
                             ("state", pymupdf.PDF_WIDGET_TYPE_COMBOBOX, (72, 260, 140, 276))):  # fields away from every box
        f = pymupdf.Widget()
        f.field_type, f.field_name, f.rect = kind, name, pymupdf.Rect(*rect)
        if kind == pymupdf.PDF_WIDGET_TYPE_COMBOBOX:
            f.choice_values, f.field_value = ["CA", "NY"], "CA"
        p.add_widget(f)
    d.set_metadata({"author": "Jane"})
    f = tmp_path / "in.pdf"
    d.save(f)
    return pymupdf.open(f)


def test_box_removes_text_edit_replaces_and_metadata_is_wiped(doc):
    acct, name = (next(ln for ln in lines(doc[0]) if s in ln["text"]) for s in ("Account", "Name"))
    form = {f["name"]: f for f in fields(doc[0]) if f["name"] != "acct"}
    assert {k: v["kind"] for k, v in form.items()} == {"fname": "text", "agree": "check", "state": "choice"}
    assert form["state"]["choices"] == ["CA", "NY"] and form["agree"]["value"] is False
    out = pymupdf.open(stream=apply(doc, [
        {"p": 0, "box": acct["box"]},
        {"p": 0, **name, "text": "Name: John"},
        {"p": 0, "field": form["fname"]["xref"], "value": "Filled In", "box": form["fname"]["box"]},
        {"p": 0, "field": form["agree"]["xref"], "value": True, "box": form["agree"]["box"]},
        {"p": 0, "field": form["state"]["xref"], "value": "NY", "box": form["state"]["box"]},
    ]))
    text = out[0].get_text()
    assert "4455" not in text and "Jane" not in text
    assert "Name: John" in text
    assert out.metadata["author"] == ""
    assert {w.field_name: w.field_value for w in out[0].widgets()} == {"fname": "Filled In", "agree": "Yes", "state": "NY"}  # filled, still fillable, "acct" gone
    assert not list(out[0].annots()) and "SECRET" not in text
    assert [lk["uri"] for lk in out[0].get_links()] == ["https://elsewhere.example"]


@pytest.fixture
def words():
    d = pymupdf.open()
    p = d.new_page()
    for i, t in enumerate(["Name: Jane Example", "Email: jane@example.com and a@b.org",
                           "Card 4111 1111 1111 1111 or 1234 5678 9012 3456", "SSN 123-45-6789 bad 000-12-3456",
                           "Phone (555) 010-4477", "Paid $1,250.00 on 10/02/2026"]):
        p.insert_text((72, 100 + i * 20), t, fontname="helv", fontsize=11)
    return [pg.get_text("words") for pg in d]


@pytest.mark.parametrize("q,kind,fuzzy,want", [
    ("jane", None, False, 2), ("Exampel", None, True, 1), ("Exampel", None, False, 0), ("", None, False, 0),
    ("", "email", False, 2), ("", "card", False, 1), ("", "ssn", False, 1),  # card and SSN checks drop the fakes
    ("", "phone", False, 1), ("", "date", False, 1), ("", "money", False, 1),
])
def test_find(words, q, kind, fuzzy, want):
    assert len(find(words, q, kind, fuzzy)) == want


@pytest.mark.skipif(not ocr.available(), reason="needs macOS text recognition")
def test_scanned_page_is_read_and_a_box_makes_the_number_unreadable():
    src = pymupdf.open()
    p = src.new_page(width=600, height=400)
    p.insert_text((50, 80), "Card 4111 1111 1111 1111", fontname="helv", fontsize=22)
    p.insert_text((50, 140), "Thank you for your order", fontname="helv", fontsize=22)
    d = pymupdf.open()
    q = d.new_page(width=600, height=400)
    q.insert_image(q.rect, stream=p.get_pixmap(dpi=200).tobytes("png"))  # a picture with no text layer

    def read(page):
        return ocr.read_words(page.get_pixmap(dpi=200).tobytes("png"), 600, 400)

    assert scan_pages(d) == [0] and not q.get_text("words")
    (hit,) = find([read(q)], kind="card")
    out = pymupdf.open(stream=apply(d, [{"p": 0, "box": hit["boxes"][0]}]))
    after = " ".join(w[4] for w in read(out[0]))
    assert "4111" not in after and "Thank you for your order" in after


@pytest.mark.parametrize("rot", [90, 180, 270])
def test_boxes_arrive_in_displayed_space_on_rotated_pages(ink, rot):
    d = pymupdf.open()
    p = d.new_page(width=400, height=300)
    p.insert_text((50, 100), "ALPHA BRAVO", fontsize=22)
    p.insert_text((50, 200), "CHARLIE DELTA", fontsize=22)
    p.set_rotation(rot)
    word = next(w for w in p.get_text("words") if w[4] == "BRAVO")
    shown = pymupdf.Rect(word[:4]) * p.rotation_matrix
    assert ink(p, shown) > .08  # the box really sits on the word in the picture
    text = pymupdf.open(stream=apply(d, [{"p": 0, "box": list(shown)}]))[0].get_text()
    assert "BRAVO" not in text and all(w in text for w in ("ALPHA", "CHARLIE", "DELTA"))


def test_saving_keeps_the_text_layer_of_scans_and_clears_what_a_box_quoted(tmp_path):
    d = pymupdf.open()
    p = d.new_page(width=300, height=200)
    p.insert_text((40, 100), "Hidden layer words", fontsize=18, render_mode=3)  # invisible text over a scan
    q = d.new_page()
    q.insert_text((50, 100), "Letter to Jane Example", fontsize=14)
    d.set_toc([[1, "Letter to Jane Example", 2], [1, "Appendix", 2]])
    root = d.pdf_catalog()
    d.xref_set_key(root, "AcroForm", "<< /Fields [] /XFA (form data) >>")
    words = q.get_text("words")
    box = [words[2][0], words[2][1], words[3][2], words[3][3]]  # "Jane Example"
    out = pymupdf.open(stream=apply(d, [{"p": 1, "box": box}]))
    assert out[0].get_text().strip() == "Hidden layer words"  # untouched page keeps its invisible text
    assert out.get_toc() == [[1, "[redacted]", 2], [1, "Appendix", 2]]  # the bookmark that quoted the box
    assert out.xref_get_key(out.pdf_catalog(), "AcroForm/XFA")[0] == "null"


def test_edited_lines_keep_typography_and_refuse_characters_the_font_lacks():
    d = pymupdf.open()
    p = d.new_page()
    p.insert_text((50, 100), "Plain line here", fontname="helv", fontsize=14)
    ln = next(lines(p))
    out = pymupdf.open(stream=apply(d, [{"p": 0, **ln, "text": "It’s a “test” – ok…"}]))
    assert "It's a" in out[0].get_text() and "-" in out[0].get_text()
    assert bad_chars("5€ and ’ and é") == ["€"]
    with pytest.raises(ValueError, match="€"):
        apply(pymupdf.open(stream=d.tobytes()), [{"p": 0, **ln, "text": "5€"}])


@pytest.mark.parametrize("rot", [90, 270])
def test_editing_a_line_on_a_rotated_page_keeps_its_place_and_direction(rot):
    d = pymupdf.open()
    p = d.new_page(width=400, height=300)
    p.set_rotation(rot)
    p.insert_text((200, 150), "Old words", fontsize=20, rotate=(360 - rot) % 360)  # written so it reads upright on the rotated page
    ln = next(lines(p))
    shown = pymupdf.Rect(ln["box"]) * p.rotation_matrix
    out = pymupdf.open(stream=apply(d, [{"p": 0, **ln, "box": list(shown), "text": "New words"}]))[0]
    new = next(w for w in out.get_text("words") if w[4] == "New")
    assert "Old" not in out.get_text() and pymupdf.Rect(new[:4]).intersects(pymupdf.Rect(ln["box"]))  # same place
    assert next(lines(out))["rotate"] == ln["rotate"]  # and written in the same direction
