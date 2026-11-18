"""Finding text in the words of a document: exact, typo-tolerant, or one of the built-in patterns."""
import re
from bisect import bisect_right
from itertools import groupby

from rapidfuzz import fuzz

MONTH = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def luhn(s):
    d = [int(c) for c in s if c.isdigit()]
    return 13 <= len(d) <= 19 and sum(sum(divmod(x * 2, 10)) if i % 2 else x for i, x in enumerate(reversed(d))) % 10 == 0


def ssn_ok(s):
    a, b, c = s.split("-")
    return a not in ("000", "666") and a[0] != "9" and b != "00" and c != "0000"


KINDS = {  # name -> (pattern, optional check that weeds out false hits)
    "email": (r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", None),
    "phone": (r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)", None),
    "card": (r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", luhn),
    "ssn": (r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", ssn_ok),
    "date": (rf"\b\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}\b|\b(?:{MONTH})[a-z]*\.? \d{{1,2}},? \d{{4}}\b", None),
    "money": (r"\$\s?\d[\d,]*(?:\.\d\d)?", None),
}


def line_boxes(words):  # one box per text line the words sit on; words look like get_text("words")
    return [[min(w[0] for w in g), min(w[1] for w in g), max(w[2] for w in g), max(w[3] for w in g)]
            for g in (list(g) for _, g in groupby(words, key=lambda w: (w[5], w[6])))]


def _norm(s):
    return re.sub(r"[\W_]+", "", s.casefold())


def find(pages_words, q="", kind=None, fuzzy=False, cap=2000):
    """Matches as {p, boxes, text}. kind picks a built-in pattern; fuzzy tolerates typos in q."""
    if not kind and not q.strip():
        return []
    pat, ok = KINDS[kind] if kind else (re.escape(q.strip()), None)
    rx, out = re.compile(pat, re.I), []
    for p, ws in enumerate(pages_words):
        starts, pos = [], 0
        for w in ws:
            starts.append(pos)
            pos += len(w[4]) + 1
        if fuzzy and not kind:
            n, nq = len(q.split()), _norm(q)
            hits = [(i, i + n) for i in range(len(ws) - n + 1)
                    if fuzz.ratio(_norm(" ".join(w[4] for w in ws[i:i + n])), nq) >= 85]
        else:
            hits = [(bisect_right(starts, m.start()) - 1, bisect_right(starts, m.end() - 1))
                    for m in rx.finditer(" ".join(w[4] for w in ws)) if not ok or ok(m.group())]
        out += [{"p": p, "boxes": line_boxes(ws[i:j]), "text": " ".join(w[4] for w in ws[i:j])} for i, j in hits]
        if len(out) >= cap:
            break
    return out[:cap]
