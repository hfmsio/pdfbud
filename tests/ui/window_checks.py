"""Real-window checks: drives the app in a real window with scripted clicks, drags, keys and a Save dialog.

Run by hand on a Mac, with the window kept in front (a hidden window stops its animations):
    uv run python tests/ui/window_checks.py
It builds its own sample PDFs in a temp folder and takes about two minutes.
"""
import hashlib
import os
import subprocess
import threading
import tempfile
import time
from pathlib import Path

import pymupdf as fitz
import webview
from webview.platforms.cocoa import BrowserView

from pdfbud import app, mac, ocr
from pdfbud.api import Api

import quiet

REAL_RUN = subprocess.run  # kept for the clipboard commands: the next line stops Finder windows from opening
CALLS = []
CLIP = []  # the user's clipboard text, saved before the copy checks
mac.subprocess.run = lambda *a, **k: CALLS.append(list(a[0]))  # no Finder windows pop up
W = Path(tempfile.mkdtemp(prefix="pdfbud-ui-"))
src, big = W / "fix.pdf", W / "big.pdf"
d = fitz.open()
extra = [["Email: jane@example.com", "Card 4111 1111 1111 1111", "Not a card 1234 5678 9012 3456"], ["Email: bob@example.com", "Jane Example"], ["Email: z@example.com"]]
for i in range(3):
    p = d.new_page()
    for j in range(10): p.insert_text((72, 80 + j*30), f"P{i} L{j} Account ref {i}{j}", fontname="helv", fontsize=12)
    for j, t in enumerate(extra[i]): p.insert_text((72, 420 + j*30), t, fontname="helv", fontsize=12)
for name, kind, rect in (("fname", fitz.PDF_WIDGET_TYPE_TEXT, (72, 500, 260, 518)), ("agree", fitz.PDF_WIDGET_TYPE_CHECKBOX, (72, 540, 88, 556)), ("state", fitz.PDF_WIDGET_TYPE_COMBOBOX, (72, 580, 160, 598))):
    w = fitz.Widget(); w.field_type, w.field_name, w.rect = kind, name, fitz.Rect(*rect)
    if kind == fitz.PDF_WIDGET_TYPE_COMBOBOX: w.choice_values, w.field_value = ["CA", "NY", "TX"], "CA"
    d[1].add_widget(w)
d.set_metadata({"author": "Jane"}); d.save(src)
b = fitz.open()
for i in range(200):
    p = b.new_page(); p.insert_text((72, 100), f"Big page {i} Account", fontname="helv", fontsize=12)
b.save(big)
mixed = W / "mixed.pdf"
t_ = fitz.open(); tp = t_.new_page(width=600, height=400)
tp.insert_text((50, 80), "Account summary typed text", fontname="helv", fontsize=22)
sp = t_.new_page(width=600, height=400)
for i, line in enumerate(["Account Card 4111 1111 1111 1111", "Thank you for your order", "Call Jane at 555 010 4477"]): sp.insert_text((50, 80 + i*60), line, fontname="helv", fontsize=22)
png = sp.get_pixmap(dpi=200).tobytes("png"); m_ = fitz.open(); m_.insert_pdf(t_, from_page=0, to_page=0); pg_ = m_.new_page(width=600, height=400); pg_.insert_image(pg_.rect, stream=png); m_.save(mixed)
before = hashlib.md5(src.read_bytes()).hexdigest()
api = Api(str(src))
quiet.install()
win = app.make_window(api, **quiet.window_options())
R = []
def ok(name, cond, extra=""): R.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name, extra, flush=True)
def js(c): return win.evaluate_js("(()=>{" + c + "})()")
def wait(c, t=20):
    e = time.time() + t
    while time.time() < e:
        try:
            if js("return " + c): return True
        except Exception: pass
        time.sleep(.2)
    return False
def run():
    if quiet.SHOW:
        win.on_top = True
    try:
        ok("opens in View mode with no line buttons", wait("S.sizes.length===3 && S.cache.get(0)?.sharp && S.mode==='view' && pageEl(0).querySelectorAll('.ln').length===0"))
        ok("View button is pressed", js("return $('mView').getAttribute('aria-pressed')==='true'"))
        js("setMode('hide')")
        ok("Redact mode adds line buttons", js("return pageEl(0).querySelectorAll('.ln').length>=13"))
        ok("page strip has thumbnails", wait("document.querySelectorAll('.th').length===3 && document.querySelector('.th img').src.startsWith('data:image')"))
        ok("footer shows path", js("return $('path').title") == "Show in Finder: " + str(src))
        ok("path has a folder icon and its text is the file path", js("return !!$('path').querySelector('svg') && $('ptext').textContent.endsWith('fix.pdf') && getComputedStyle($('path')).display!=='none'"))
        js("$('path').click()")
        ok("clicking the path shows the file in Finder", wait("true") and (time.sleep(.6) or True) and CALLS[-1] == ["open", "-R", str(src)], CALLS[-1:] )
        ok("shortcut keys are marked handled, so no Mac beep", js("""const t=k=>{const e=new KeyboardEvent('keydown',{key:k,cancelable:true,bubbles:true}); window.dispatchEvent(e); return e.defaultPrevented};
          const r=['ArrowRight','ArrowLeft','v','r','e','f','p'].map(t); setMode('hide'); if (document.getElementById('blk').checked) document.getElementById('blk').click(); return r.every(Boolean) && !t('x')"""))
        ok("save disabled with no changes", js("return $('save').disabled"))
        js("pageEl(0).querySelector('.ln').click()")
        ok("click line redacts it", js("return cur().length===1 && pageEl(0).querySelectorAll('.box').length===1"))
        js("""const b=S.cache.get(0).lines[7].box,z=k(0),r=pageEl(0).getBoundingClientRect(),cx=r.left+(b[0]+b[2])/2*z,cy=r.top+(b[1]+b[3])/2*z;
          pageEl(0).dispatchEvent(new MouseEvent('mousedown',{clientX:r.left+b[0]*z-4,clientY:cy-3,bubbles:true}));
          window.dispatchEvent(new MouseEvent('mousemove',{clientX:r.left+b[2]*z+4,clientY:cy+3}));
          window.dispatchEvent(new MouseEvent('mouseup',{}));""")
        ok("drag draws free box", js("return cur().length===2"))
        ok("the status line says 2 boxes, not boxs", js("return $('status').textContent.startsWith('2 boxes, 0 edits')"))
        w0 = js("return pageEl(0).querySelector('.box').getBoundingClientRect().width")
        js("$('zin').click()")
        ok("zoom in grows page and box together", wait("S.zoom===1.25 && !!pageEl(0).querySelector('.box')") and abs(js("return pageEl(0).querySelector('.box').getBoundingClientRect().width") / w0 - 1.25) < .03 and js("return $('zfit').textContent")=='125%')
        js("$('zin').click(); $('zin').click(); $('zin').click()")
        ok("zoomed in far scrolls sideways", wait("S.zoom===2.0 || S.zoom===3") and js("return $('stage').scrollWidth > $('stage').clientWidth"))
        js("$('zfit').click()")
        ok("fit button restores width", wait("S.zoom===1 && !!pageEl(0).querySelector('.box')") and abs(js("return pageEl(0).querySelector('.box').getBoundingClientRect().width") - w0) < 1.5)
        js("""const e=new Event('gesturestart',{cancelable:true}); $('stage').dispatchEvent(e);
          const c=new Event('gesturechange',{cancelable:true}); c.scale=1.6; c.clientX=400; c.clientY=300; $('stage').dispatchEvent(c);""")
        ok("pinch scales the page at once", js("return $('col').style.transform.startsWith('scale(1.6') && S.zoom===1"))
        js("$('stage').dispatchEvent(new Event('gestureend',{cancelable:true}))")
        ok("pinch end redraws at the new zoom", wait("S.zoom>1.59 && S.zoom<1.61 && $('col').style.transform==='' && !!pageEl(0).querySelector('.box')") and js("return $('zfit').textContent")=='160%')
        js("$('stage').dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:200,clientX:400,clientY:300,cancelable:true,bubbles:true}))")
        ok("Ctrl-scroll zooms out and settles", wait("S.zoom<1.4 && $('col').style.transform===''"), js("return S.zoom"))
        js("$('zfit').click()")
        ok("fit after pinch", wait("S.zoom===1"))
        js("setMode('view')")
        ok("View hides line buttons but keeps boxes", js("return pageEl(0).querySelectorAll('.ln').length===0 && pageEl(0).querySelectorAll('.box').length===2"))
        js("setMode('hide')")
        js("setMode('edit')"); wait("pageEl(0).querySelectorAll('.ln').length>=13")
        js("pageEl(0).querySelectorAll('.ln')[2].click()")
        js("const i=document.querySelector('.ed'); i.value='P0 L2 CHANGED TEXT'; i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}))")
        ok("edit commits and previews", js("return cur().length===3 && !!pageEl(0).querySelector('.edited')"))
        js("setMode('hide'); go(1)")
        ok("smooth scroll to page 2 draws it and updates nav", wait("S.page===1 && S.cache.get(1)?.sharp && $('pg').value==='2' && $('strip').children[1].classList.contains('now')"))
        js("pageEl(1).querySelectorAll('.ln')[5].click()")
        ok("redact on page 2", js("return cur().length===4 && mine().length===1"))
        ok("thumb shows change dot", js("return $('strip').children[1].classList.contains('has')"))
        js("undo()"); ok("undo works", js("return cur().length===3"))
        js("pageEl(1).querySelectorAll('.ln')[5].click()")
        # fill forms
        js("setMode('fill')")
        ok("Fill mode shows 3 fields on page 2 and no line buttons", wait("pageEl(1).querySelectorAll('.fld').length===3 && pageEl(1).querySelectorAll('.ln').length===0"))
        ok("footer counts the fillable fields", js("return $('fieldnote').textContent")=="3 fillable fields on this page")
        nb = js("return cur().length")
        js("const t=[...pageEl(1).querySelectorAll('.fld')].find(e=>e.tagName==='INPUT'&&e.type!=='checkbox'); t.value='Filled Name'; t.dispatchEvent(new Event('change'))")
        js("const c=[...pageEl(1).querySelectorAll('.fld')].find(e=>e.type==='checkbox'); c.checked=true; c.dispatchEvent(new Event('change'))")
        js("const c=pageEl(1).querySelector('select.fld'); c.value='NY'; c.dispatchEvent(new Event('change'))")
        ok("three field changes recorded and counted", js("return cur().length===%d && $('status').textContent.includes('3 fields')" % (nb + 3)))
        ok("typed value survives a redraw", js("return [...pageEl(1).querySelectorAll('.fld')].some(e=>e.value==='Filled Name')"))
        js("setMode('view')")
        ok("filled fields stay visible but locked in View mode", js("return pageEl(1).querySelectorAll('.fld.filled').length===3 && getComputedStyle(pageEl(1).querySelector('.fld')).pointerEvents==='none'"))
        js("undo(); undo(); undo()"); ok("undo takes the fills back one by one", js("return cur().length===%d" % nb))
        js("setMode('fill')")
        js("const t=[...pageEl(1).querySelectorAll('.fld')].find(e=>e.tagName==='INPUT'&&e.type!=='checkbox'); t.value='Filled Name'; t.dispatchEvent(new Event('change'))")
        js("const c=[...pageEl(1).querySelectorAll('.fld')].find(e=>e.type==='checkbox'); c.checked=true; c.dispatchEvent(new Event('change'))")
        js("const c=pageEl(1).querySelector('select.fld'); c.value='NY'; c.dispatchEvent(new Event('change'))")
        js("setMode('hide')")
        # review fixes: a file that will not open, unsaved changes, characters the font lacks
        bad = W / "empty.pdf"; bad.write_bytes(b"")
        n_now = js("return cur().length")
        js("load(%r)" % str(bad))
        ok("opening with unsaved changes warns first and keeps them", js("return S.msg.startsWith('You have') && cur().length===%d" % n_now))
        js("load(%r)" % str(bad))
        ok("a file that cannot be opened says why, and the current file stays open", wait("S.msg.startsWith('Could not open') && S.msg.includes('empty')") and js("return S.sizes.length===3 && cur().length===%d" % n_now))
        js("setMode('edit')"); wait("pageEl(0).querySelectorAll('.ln').length>=13")
        js("pageEl(0).querySelectorAll('.ln')[4].click()")
        js("const i=document.querySelector('.ed'); i.value='costs 5 \u20ac'; i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}))")
        ok("a character the font cannot write is refused with a message and the box stays", wait("S.msg.startsWith(\"Can't write\") && !!document.querySelector('.ed')"))
        js("document.querySelector('.ed').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"); js("setMode('hide')")
        # full screen: the page logic (the real Mac full screen is tried at the end)
        seen = lambda sel: js("const e=document.querySelector('%s'), r=e.getBoundingClientRect(); return getComputedStyle(e).display!=='none' && r.bottom>2 && r.right>2" % sel)
        h0 = js("return $('stage').clientHeight")
        js("setFS(true, true)")
        ok("full screen slides the toolbar, strip and footer away and gives the page more room",
           wait("document.body.classList.contains('fs') && document.querySelector('#chrome').getBoundingClientRect().bottom<=0") and not seen(".foot") and not seen(".side") and js("return $('stage').clientHeight") > h0 + 60)
        ok("a hint says how to get the bars back", js("return $('toast').classList.contains('on')"))
        js("document.dispatchEvent(new MouseEvent('mousemove',{clientX:300,clientY:2,bubbles:true}))")
        ok("the top edge brings the toolbar back", wait("document.body.classList.contains('reveal') && document.querySelector('#chrome').getBoundingClientRect().top>=-1"))
        js("$('q').focus(); document.dispatchEvent(new MouseEvent('mousemove',{clientX:300,clientY:700,bubbles:true}))"); time.sleep(.5)
        ok("while you type in the search box the toolbar stays", js("return document.body.classList.contains('reveal')"))
        js("$('q').blur(); document.dispatchEvent(new MouseEvent('mousemove',{clientX:300,clientY:700,bubbles:true}))")
        ok("moving away tucks the toolbar back", wait("!document.body.classList.contains('reveal')"))
        js("document.dispatchEvent(new MouseEvent('mousemove',{clientX:2,clientY:300,bubbles:true}))")
        ok("the left edge brings the page strip back", wait("document.body.classList.contains('revealSide') && document.querySelector('.side').getBoundingClientRect().left>=-1"))
        js("document.dispatchEvent(new MouseEvent('mousemove',{clientX:600,clientY:300,bubbles:true}))")
        ok("moving away tucks the strip back", wait("!document.body.classList.contains('revealSide')"))
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
        left = wait("!FS.on && !document.body.classList.contains('fs')")
        time.sleep(.4)
        ok("Esc leaves full screen and everything returns", left and seen(".foot") and seen(".side") and abs(js("return $('stage').clientHeight") - h0) < 24,
           [left, seen(".foot"), seen(".side"), h0, js("return $('stage').clientHeight")])
        js("setMode('view')"); js("$('q').value='Account'; $('q').oninput()")
        ok("the search box shows a clear button only when it has text", wait("S.find.m.length>0") and js("return getComputedStyle($('qx')).display!=='none'") and js("$('q').value=''; return getComputedStyle($('qx')).display==='none'"))
        js("$('q').value='Account'; $('q').oninput()"); wait("S.find.m.length>0")
        js("$('qx').click()")
        ok("clicking it empties the box, drops the hits and keeps the cursor in the box", wait("S.find.m.length===0") and js("return $('q').value==='' && document.activeElement===$('q')"))
        js("$('q').blur()")
        ok("the window title bar reads pdfbud - file name", wait("document.title.startsWith('pdfbud - ')") and BrowserView.get_instance("pywebview_window", win).window.title() == js("return document.title"))
        # select and copy, cut, copy and paste a box
        clip0 = REAL_RUN(["pbpaste"], capture_output=True).stdout  # the clipboard is put back at the end of this section, or if a check crashes
        CLIP.append(clip0)
        pasteboard = lambda: REAL_RUN(["pbpaste"], capture_output=True, text=True).stdout
        base = js("return cur().length")
        js("setMode('view')")
        ok("View mode lays invisible text over every line, stretched to the line's width", wait("pageEl(0).querySelectorAll('.tx').length>=13") and js("""const l=S.cache.get(0).lines[0], t=pageEl(0).querySelector('.tx'); return t.textContent===l.text && Math.abs(t.getBoundingClientRect().width-(l.box[2]-l.box[0])*k(0))<3"""))
        select = "const t=pageEl(0).querySelectorAll('.tx')[%d], r=document.createRange(); r.selectNodeContents(t); const s=getSelection(); s.removeAllRanges(); s.addRange(r); return t.textContent"
        # a selection that starts and ends inside a word must still black out the whole word, from the file's own word positions
        truth = next(w for w in fitz.open(src)[0].get_text("words") if w[4] == "Account" and abs(w[1] - 158) < 14)  # the word on the 4th line
        got = js("""const t=[...pageEl(0).querySelectorAll('.tx')].find(x=>x.textContent.startsWith('P0 L3')), i=t.textContent.indexOf('Account'), r=document.createRange();
                    r.setStart(t.firstChild, i+2); r.setEnd(t.firstChild, i+5); const s=getSelection(); s.removeAllRanges(); s.addRange(r); return selectionBoxes()""")
        ok("a selection inside a word gives a box that covers the whole word and nothing beside it", len(got) == 1 and got[0]["box"][0] <= truth[0] + .01 and got[0]["box"][2] >= truth[2] - .01 and got[0]["box"][2] - truth[2] < 1 and truth[0] - got[0]["box"][0] < 1, repr((got, truth[:4])))
        line3 = js(select % 3)
        ok("selecting a line shows the Copy, Cut and Redact bar", wait("$('sel').classList.contains('on')") and js("return getSelection().toString()") == line3)
        js("$('sCopy').click()")
        time.sleep(.6); ok("Copy puts the words on the Mac clipboard", pasteboard().strip() == line3, repr(pasteboard()[:30]))
        line4 = js(select % 4)
        js("$('sCut').click()")
        ok("Cut copies the words and blacks them out in one step", wait("cur().length===%d" % (base + 1)) and pasteboard().strip() == line4 and js("const c=cur().at(-1), l=S.cache.get(0).lines[4]; return c.p===0 && c.box[0]<=l.box[0]+3 && c.box[2]>=l.box[2]-3 && c.box[1]<l.box[3] && c.box[3]>l.box[1]"))
        js("undo()"); ok("Undo takes the cut back", js("return cur().length===%d" % base))
        js("go(0)"); wait("S.page===0")
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'a',metaKey:true,bubbles:true,cancelable:true}))")
        ok("Cmd+A selects all the text on the page and shows the bar", wait("getSelection().toString().includes('P0 L0') && getSelection().toString().includes('P0 L9')") and wait("hasSelection() && $('sel').classList.contains('on')"))
        js("getSelection().removeAllRanges()")
        js("setMode('hide')")
        js("pageEl(0).querySelector('.ln').click()")
        wait("cur().length===%d" % (base + 1))
        js("pageEl(0).querySelector('.box').click()")
        ok("clicking a box picks it", wait("!!S.picked && !!pageEl(0).querySelector('.box.picked')"))
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'c',metaKey:true,bubbles:true,cancelable:true}))")
        ok("Cmd+C copies the picked box", js("return !!S.clip"))
        js("go(1)"); wait("S.page===1")
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'v',metaKey:true,bubbles:true,cancelable:true}))")
        ok("Cmd+V pastes it on another page in the same spot", wait("cur().length===%d" % (base + 2)) and js("const c=cur().at(-1); return c.p===1 && c.box.join()===S.clip.box.join() && S.msg.includes('pasted')"))
        js("undo(); undo(); go(0)")
        wait("cur().length===%d && S.page===0" % base)
        REAL_RUN(["pbcopy"], input=clip0)
        # quitting with unsaved changes must not hang: the closing check runs on the Mac main thread, like Cmd+Q does
        js("commit(cs => [...cs, { p: 0, box: [10, 10, 60, 30] }])"); wait("$('cnt').textContent==='(%d)'" % (base + 1)); time.sleep(.3)
        asked, answer = [], threading.Event()
        mac.confirm = lambda *a: asked.append(a) or False
        from PyObjCTools import AppHelper
        AppHelper.callAfter(lambda: (answer.__setattr__("v", BrowserView.should_close(win)), answer.set()))
        ok("Cmd+Q with unsaved changes asks once and, on Keep working, stays open instead of hanging", answer.wait(5) and len(asked) == 1 and not answer.v and f"{base + 1} unsaved" in asked[0][0], repr(asked))
        js("undo()")
        ok("this section left the changes and the clipboard as they were", js("return cur().length===%d" % base))
        # search
        js("$('q').value='Account'; $('q').dispatchEvent(new Event('input'))")
        ok("exact search finds 30 lines", wait("S.find.m.length===30"), js("return $('count').textContent"))
        js("$('fnext').click()"); ok("next match steps", js("return $('count').textContent.startsWith('2 of 30')"))
        js("document.querySelector('[data-k=email]').click()")
        ok("emails chip finds 3 on 3 pages", wait("S.find.m.length===3 && new Set(S.find.m.map(x=>x.p)).size===3"))
        js("document.querySelector('[data-k=card]').click()")
        ok("cards chip drops the fake number", wait("S.find.m.length===1"))
        js("document.querySelector('[data-k=card]').click(); $('q').value='Exampel'; $('q').dispatchEvent(new Event('input'))")
        ok("typo search misses without Typos OK", wait("S.find.m.length===0 && $('count').textContent==='No matches'"))
        js("$('fz').checked=true; $('fz').dispatchEvent(new Event('change'))")
        ok("typo search finds Example with Typos OK", wait("S.find.m.length>=1"))
        js("$('fz').checked=false; document.querySelector('[data-k=email]').click()")
        wait("S.find.m.length===3"); n0 = js("return cur().length")
        js("$('all').click()")
        ok("Redact all adds a box per email", js("return cur().length===%d" % (n0 + 3)))
        js("undo()"); ok("Redact all undoes in one step", js("return cur().length===%d" % n0))
        js("$('all').click()")
        js("$('blk').click()")
        ok("preview turns boxes black", js("return getComputedStyle(document.querySelector('.box')).backgroundColor==='rgb(0, 0, 0)'"))
        js("$('blk').click()")
        js("$('pg').value='3'; $('pg').dispatchEvent(new Event('change'))")
        good = wait("S.page===2", 8)
        if not good: print("DEBUG", js("return JSON.stringify({page:S.page, st:$('stage').scrollTop, vh:$('stage').clientHeight, sh:$('stage').scrollHeight, tops:S.tops, pg:$('pg').value, mode:S.mode, zoom:S.zoom, fitW:S.fitW, sizes:S.sizes.length, find:S.find.m.length})"), flush=True)
        ok("page box jumps to page 3", good)
        # save as: cancel, same-as-original, chosen name
        win.create_file_dialog = lambda *a, **k: None
        js("$('save').click()"); ok("cancelled save says so", wait("S.msg==='Save cancelled'"))
        win.create_file_dialog = lambda *a, **k: str(src)
        js("$('save').click()"); ok("refuses to overwrite original", wait("S.msg.startsWith('Could not save')"))
        win.create_file_dialog = lambda *a, **k: str(W / "chosen name")
        js("$('save').click()")
        ok("save as uses the chosen name", wait("S.msg==='Saved chosen name.pdf'"), js("return S.msg"))
        o = fitz.open(W / "chosen name.pdf"); t0, t1, t2 = (o[i].get_text() for i in range(3))
        ok("page1: boxed line gone, neighbours kept", "P0 L0 " not in t0 and "P0 L1 " in t0)
        ok("page1: free box removed its line only", "P0 L7 " not in t0 and "P0 L6 " in t0 and "P0 L8 " in t0, [ln[:8] for ln in t0.splitlines() if ln.startswith("P0 L")])
        ok("page1: edit written", "P0 L2 CHANGED TEXT" in t0 and "P0 L2 Account" not in t0)
        ok("page2: line gone", "P1 L5 " not in t1 and "P1 L4 " in t1)
        ok("all 3 emails gone", all("@example.com" not in t for t in (t0, t1, t2)))
        ok("fake card kept, real card untouched", "1234 5678" in t0 and "4111" in t0)
        ok("form fields filled and still fillable", {w.field_name: w.field_value for w in o[1].widgets()} == {"fname": "Filled Name", "agree": "Yes", "state": "NY"})
        ok("metadata wiped", o.metadata["author"] == "")
        ok("original untouched", hashlib.md5(src.read_bytes()).hexdigest() == before)
        KW="window.dispatchEvent(new KeyboardEvent('keydown',{key:'w',metaKey:true}))"
        js(KW); ok("Cmd+W asks first when there are changes", js("return $('close').textContent.startsWith('Discard')"))
        js(KW)
        ok("second Cmd+W returns to start", wait("document.body.classList.contains('noDoc') && S.sizes.length===0") and api._session._doc is None)
        ok("the start page shows the logo, the name and the drop hint", wait("document.querySelector('.empty .logo')?.naturalWidth>0") and js("const e=document.querySelector('.empty'); return getComputedStyle(e).display!=='none' && e.querySelector('.brand').textContent==='pdfbud' && e.textContent.includes('Drop a PDF here')"))
        # 200 pages
        js("pywebview.api.open(%r).then(show)" % str(big))
        ok("200-page file opens, only nearby pages drawn", wait("S.sizes.length===200 && S.cache.has(0) && S.cache.size<=12"), js("return S.cache.size"))
        js("$('stage').scrollTop=S.tops[150]")
        wait('S.page===150', 10)
        ok("scrolled to page 151: drawn, page 1 released", wait("S.page===150 && S.cache.has(150) && !S.cache.has(0) && S.cache.size<=16"), js("return S.cache.size"))
        js("$('q').value='Account'; $('q').dispatchEvent(new Event('input'))")
        js("resetFind()")
        js("window.__n=0; const o=pywebview.api.page; pywebview.api.page=(...a)=>{window.__n++; return o(...a)}")
        js("let i=0; window.__t=setInterval(()=>{ $('stage').scrollTop=S.tops[(i*37+11)%190]; if(++i>25) clearInterval(window.__t) },30)")
        wait("window.__t && !S.busy.size", 20); time.sleep(1.2)
        ok("fast scrolling skips pages already scrolled past", js("return window.__n") < 130, "page requests: %s" % js("return window.__n"))
        ok("after fast scrolling every visible page has a picture", wait("S.want.vis.length>0 && S.want.vis.every(n => !!pageEl(n).querySelector('img'))", 6))
        ok("and the sharp copy follows once it settles", wait("S.want.vis.every(n => S.cache.get(n)?.sharp)", 8))
        js("$('q').value='Account'; $('q').dispatchEvent(new Event('input'))")
        js("resetFind()")
        js("$('last').click()")
        ok("Last page button jumps to page 200 and greys out next and last", wait("S.page===199 && $('last').disabled && $('next').disabled && !$('first').disabled && !!pageEl(199).querySelector('img')"))
        js("$('first').click()")
        ok("First page button jumps back to page 1", wait("S.page===0 && $('first').disabled && $('prev').disabled && !$('last').disabled"))
        ok("Home and End are marked handled", js("""const t=k=>{const e=new KeyboardEvent('keydown',{key:k,cancelable:true,bubbles:true}); window.dispatchEvent(e); return e.defaultPrevented}; return t('End') && t('Home')"""))
        ok("End key goes to the last page", wait("S.page===199 || true") and (js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}))") or True) and wait("S.page===199"))
        js("$('stage').scrollTop=S.tops[100]"); wait("S.page===100")
        js("$('q').value='Account'; $('q').dispatchEvent(new Event('input'))")
        ok("search across 200 pages", wait("S.find.m.length===200", 30), js("return $('count').textContent"))
        js("S.find.now=148; step(1)")
        ok("far jump draws the target page before arriving", wait("S.page===149 && !!pageEl(149).querySelector('img')"), js("return S.page"))
        ok("neighbour match pages are warmed", wait("S.cache.has(150) && S.cache.has(148)"))
        js("S.find.now=0; step(-1)")
        ok("wraps to the last match, far away", wait("S.find.now===199 && S.page>=198 && !!pageEl(199).querySelector('img')"))
        # scanned pages
        js("pywebview.api.open(%r).then(show)" % str(mixed))
        ok("mixed file opens and the notice counts 1 scan", wait("S.sizes.length===2 && !$('notice').hidden && $('ntext').textContent.startsWith('1 page is a scan')"), js("return $('ntext').textContent"))
        ok("the scan's thumbnail says scan", js("return $('strip').children[1].textContent.includes('scan') && !$('strip').children[0].textContent.includes('scan')"))
        shown = lambda i: js("return getComputedStyle($('%s')).display!=='none'" % i)
        ok("notice is really drawn, with Read button and no Stop button", shown("notice") and shown("read") and not shown("stop") and shown("ndismiss"))
        js("$('ndismiss').click()")
        ok("the x hides the whole bar and a small chip in the footer offers it back", not shown("notice") and shown("scanchip") and js("return $('scanchip').textContent")=="1 unread scan: show")
        js("$('scanchip').click()")
        ok("clicking the chip brings the bar back", shown("notice") and not shown("scanchip"))
        js("$('q').value='Account'; $('q').dispatchEvent(new Event('input'))")
        ok("before reading, search only finds the typed page", wait("S.find.m.length===1 && S.find.m[0].p===0"))
        js("$('read').click()")
        ok("reading shows progress then finishes", wait("OCR.state==='done' && OCR.read.has(1)", 60), js("return $('ntext').textContent"))
        ok("when reading is done, Read and Stop are really gone from the screen", not shown("read") and not shown("stop") and shown("notice"))
        js("$('ndismiss').click()")
        ok("after reading, the x hides the bar and no chip nags", not shown("notice") and not shown("scanchip"))
        ok("search now also finds the scanned page, marked as read by the computer", wait("S.find.m.length===2 && S.find.m.some(m=>m.p===1 && m.ocr)", 15))
        js("document.querySelector('[data-k=card]').click()")
        ok("card check finds the real card on the scan", wait("S.find.m.length===1 && S.find.m[0].p===1 && S.find.m[0].ocr"))
        js("go(1)"); wait("S.page===1")
        ok("footer says check this page, and the hit is dashed", wait("!$('ocrnote').hidden && !!pageEl(1).querySelector('.hit.ocr')"))
        js("setMode('view')")
        ok("a scan that has been read can be selected and copied too", wait("pageEl(1).querySelectorAll('.tx').length===3") and js("""const r=document.createRange(); r.selectNodeContents(pageEl(1).children[1]); const s=getSelection(); s.removeAllRanges(); s.addRange(r); return s.toString().includes('Thank you for your order')"""))
        js("getSelection().removeAllRanges()")
        js("setMode('hide')")
        ok("Redact mode offers the scan's lines as clickable lines", wait("pageEl(1).querySelectorAll('.ln').length===3"))
        js("$('all').click()")
        ok("Redact all boxes the card on the scan", js("return cur().length===1 && cur()[0].p===1"))
        win.create_file_dialog = lambda *a, **k: str(W / "scanout")
        js("$('save').click()"); ok("scan saved", wait("S.msg==='Saved scanout.pdf'"))
        o2 = fitz.open(W / "scanout.pdf"); pg2 = o2[1]
        read2 = " ".join(w[4] for w in ocr.read_words(pg2.get_pixmap(dpi=200).tobytes("png"), pg2.rect.width, pg2.rect.height))
        ok("on the saved scan the card number can no longer be read, the rest still can", "4111" not in read2 and "Thank you for your order" in read2, read2[:80])
        js("OCR.ok=false; renderNotice()")
        ok("without the reader the button is off and says why", js("return $('read').disabled && $('read').title==='Needs macOS' && $('ntext').textContent.includes('needs macOS')"))
        if quiet.SHOW:  # the Mac's real full screen takes over the display, so it only runs when you are watching
            js("$('fs').click()")
            ok("the button puts the window in the Mac's full screen", wait("FS.on && innerWidth >= screen.width - 2", 20), js("return innerWidth + ' of ' + screen.width"))
            js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
            back = wait("!FS.on && innerWidth < screen.width - 40", 20)
            ok("Esc brings the window back", back, js("return JSON.stringify({fs:FS.on, w:innerWidth, sw:screen.width, cls:document.body.className, noDoc:document.body.classList.contains('noDoc'), act:document.activeElement.id||document.activeElement.tagName})"))
            js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'f',ctrlKey:true,metaKey:true,bubbles:true,cancelable:true}))")
            ok("Control-Command-F goes full screen", wait("FS.on && innerWidth >= screen.width - 2", 20), js("return JSON.stringify({fs:FS.on, w:innerWidth, sw:screen.width, noDoc:document.body.classList.contains('noDoc')})"))
            js("$('fs').click()")
            ok("and the button leaves it again", wait("!FS.on && innerWidth < screen.width - 40", 20))
        else:
            print("SKIPPED real full screen checks (set PDFBUD_SHOW=1 to run them)", flush=True)
    except Exception as e:
        ok("driver crashed", False, repr(e))
        if CLIP:
            REAL_RUN(["pbcopy"], input=CLIP[0])
    finally:
        win.destroy()
webview.start(run)
print("RESULT", sum(R), "/", len(R), flush=True)
os._exit(0 if all(R) else 1)
