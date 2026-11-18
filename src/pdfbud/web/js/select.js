// Select and copy text, cut it (black it out and copy it), and copy a box to another page.
// Selection works in View mode on an invisible text layer made from each page's lines, so it works on scans once they are read.
function textLines(n, lines) {                                // one block per upright line, placed over the line on the picture
  const z = k(n);
  return lines.filter(l => l.text.trim() && l.box[2] - l.box[0] > (l.box[3] - l.box[1]) * 1.2).map(l => {
    const d = document.createElement('div'), h = (l.box[3] - l.box[1]) * z;
    d.className = 'tx'; d.textContent = l.text; d.dataset.w = (l.box[2] - l.box[0]) * z; d._l = l;
    Object.assign(d.style, { left: l.box[0] * z + 'px', top: l.box[1] * z + 'px', height: h + 'px', lineHeight: h + 'px', fontSize: h * .82 + 'px' });
    return d;
  });
}
function fitText(txl) {                                       // stretch each line of invisible text to the width of the line on the page
  const blocks = [...txl.children], widths = blocks.map(d => d.getBoundingClientRect().width);
  blocks.forEach((d, i) => { if (widths[i] > 0) d.style.transform = `scaleX(${d.dataset.w / widths[i]})`; });
}

const inText = n => n && (n.nodeType === 1 ? n : n.parentElement)?.closest('.txl');
const selRange = () => { const s = getSelection(); return s.rangeCount && !s.isCollapsed && (inText(s.anchorNode) || inText(s.focusNode)) ? s.getRangeAt(0) : null; };
const hasSelection = () => !!selRange();
const wordCount = () => getSelection().toString().split(/\s+/).filter(Boolean).length;
const say = text => { S.msg = text; render(); };

function snapToWords(tx, n, from, to) {                       // the real boxes of the words a selection touches, whole words only
  const l = tx._l, text = tx.textContent, tokens = [...text.matchAll(/\S+/g)];
  const words = (S.cache.get(n)?.words || []).filter(w => { const cx = (w[0] + w[2]) / 2, cy = (w[1] + w[3]) / 2; return cy >= l.box[1] && cy <= l.box[3] && cx >= l.box[0] - 1 && cx <= l.box[2] + 1; }).sort((a, b) => a[0] - b[0]);
  if (tokens.length !== words.length || tokens.some((t, i) => t[0] !== words[i][4])) return l.box;   // cannot match the words one to one: take the whole line, never less
  const hit = words.filter((_, i) => tokens[i].index < to && tokens[i].index + tokens[i][0].length > from);
  return hit.length ? [Math.min(...hit.map(w => w[0])), Math.min(...hit.map(w => w[1])), Math.max(...hit.map(w => w[2])), Math.max(...hit.map(w => w[3]))] : null;
}
function selectionBoxes() {                                   // a box over every word the selection touches, taken from the file's own word positions
  const range = selRange(), out = [];
  if (!range) return out;
  for (const tx of document.querySelectorAll('.col .tx')) {
    if (!range.intersectsNode(tx)) continue;
    const len = tx.textContent.length, at = (node, o, rest) => node === tx ? (o ? len : 0) : tx.contains(node) ? o : rest;
    const box = snapToWords(tx, +tx.closest('.page').dataset.n, at(range.startContainer, range.startOffset, 0), at(range.endContainer, range.endOffset, len));
    if (box) out.push({ p: +tx.closest('.page').dataset.n, box });
  }
  return out;
}
function copySelection() {                                    // the Mac clipboard, through Python: the page may not write it without a click it trusts
  const text = getSelection().toString(); pywebview.api.copy_text(text); return text.split(/\s+/).filter(Boolean).length;
}
function redactSelection() { const boxes = selectionBoxes(); getSelection().removeAllRanges(); placeBar(); addBoxes(boxes); return boxes.length; }
function cutSelection() {
  const n = copySelection(), boxes = redactSelection();
  say(boxes ? `Copied ${plural(n, 'word')} and blacked them out. Undo brings them back.` : `Copied ${plural(n, 'word')}. Nothing could be blacked out there.`);
}
function selectPage() { const r = document.createRange(); r.selectNodeContents(pageEl(S.page).children[1]); getSelection().removeAllRanges(); getSelection().addRange(r); }

function placeBar() {                                         // the small bar above a selection
  const range = selRange(), bar = $('sel');
  bar.classList.toggle('on', !!range);
  if (!range) return;
  const r = range.getBoundingClientRect();
  bar.style.left = Math.max(8, Math.min(r.left, innerWidth - bar.offsetWidth - 8)) + 'px'; bar.style.top = Math.max(8, r.top - 44) + 'px';
}
document.addEventListener('selectionchange', () => requestAnimationFrame(placeBar));
$('stage').addEventListener('scroll', () => requestAnimationFrame(placeBar), { passive: true });
$('sel').addEventListener('mousedown', e => e.preventDefault());                    // pressing a button must not clear the selection
$('sCopy').onclick = () => say(`Copied ${plural(copySelection(), 'word')}`);
$('sCut').onclick = cutSelection;
$('sRed').onclick = () => { const n = redactSelection(); say(`Blacked out ${plural(n, 'line')}. Undo brings them back.`); };
document.addEventListener('copy', () => { const n = wordCount(); if (n && hasSelection()) { S.msg = `Copied ${plural(n, 'word')}`; $('status').textContent = S.msg; } });

function pickBox(c) { S.picked = c; render(); say('Box selected. ⌘C copies it, then ⌘V on another page.'); }
function copyBox() {
  if (!S.picked || !cur().includes(S.picked)) return false;
  S.clip = { box: [...S.picked.box], size: S.sizes[S.picked.p] }; say('Box copied. Go to another page and press ⌘V.'); return true;
}
function pasteBox() {                                         // the same box, in the same spot, on the page you are looking at (scaled when that page is a different size)
  if (!S.clip || noDoc()) return false;
  const [w, h] = S.sizes[S.page], [cw, ch] = S.clip.size, [sx, sy] = [w / cw, h / ch], b = S.clip.box, box = [b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy];
  if (cur().some(c => c.text === undefined && c.field === undefined && c.p === S.page && same(c.box, box))) { say('That box is already on this page.'); return true; }
  addBoxes([{ p: S.page, box }]);
  S.picked = cur().at(-1); say(`Box pasted on page ${S.page + 1}${sx === 1 && sy === 1 ? ', same spot' : ', scaled to this page'}.`); return true;
}
