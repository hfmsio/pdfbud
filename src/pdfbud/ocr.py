"""Reading text from a page picture with Apple's text recognition (macOS only)."""
import re
import sys
from itertools import groupby

from .core.search import line_boxes


def available():
    if sys.platform != "darwin":
        return False
    try:
        import Vision  # noqa: F401
    except ImportError:
        return False
    return True


def read_words(png, W, H):
    """Words read from a page picture, in the same shape as get_text('words'). Vision gives boxes as fractions of the
    page with the origin at the bottom left."""
    import Vision
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(True)
    Vision.VNImageRequestHandler.alloc().initWithData_options_(png, None).performRequests_error_([req], None)
    seen = sorted(req.results() or [], key=lambda o: -(o.boundingBox().origin.y + o.boundingBox().size.height))
    out = []
    for line, obs in enumerate(seen):
        cand = obs.topCandidates_(1)[0]
        for n, m in enumerate(re.finditer(r"\S+", cand.string())):
            box, _ = cand.boundingBoxForRange_error_((m.start(), m.end() - m.start()), None)
            b = (box or obs).boundingBox()
            out.append((b.origin.x * W, (1 - b.origin.y - b.size.height) * H, (b.origin.x + b.size.width) * W,
                        (1 - b.origin.y) * H, m.group(), line, 0, n))
    return out


def lines(words):  # clickable lines for pages read this way (Redact mode only)
    groups = (list(g) for _, g in groupby(words, key=lambda w: w[5]))
    return [dict(box=b[0], text=" ".join(w[4] for w in g), size=(b[0][3] - b[0][1]) * .8,
                 font="", color=0, origin=(0, 0), ocr=True)
            for g in groups for b in [line_boxes(g)]]
