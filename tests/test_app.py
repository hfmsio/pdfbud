from pdfbud.api import Api
from pdfbud.app import confirm_discard


def test_closing_asks_only_when_there_are_unsaved_changes():
    asked = []

    def ask(*a):
        asked.append(a)
        return False

    api = Api()
    assert confirm_discard(api, ask) and not asked  # nothing unsaved: closes without asking
    api.report_changes(3)
    assert not confirm_discard(api, ask) and len(asked) == 1 and "3" in asked[0][0]
    assert confirm_discard(api, lambda *a: True)  # the user chose to discard


def test_a_finder_request_before_the_page_is_ready_waits_for_it():
    api = Api()
    assert api._request_open("/tmp/a.pdf") is False and api._start == "/tmp/a.pdf"
    api._start = None  # (the file itself is not opened in this test)
    api.initial()  # the page says it is ready
    assert api._request_open("/tmp/b.pdf") is True
