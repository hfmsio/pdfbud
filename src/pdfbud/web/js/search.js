// ---- search ----
function renderFind() {
  const f = S.find, m = f.m, pages = new Set(m.map(x => x.p)).size, has = !!$('q').value.trim() || !!S.kind;
  $('count').textContent = m.length ? (f.truncated ? `${m.length}+ matches: narrow the search` : `${f.now + 1} of ${m.length}, ${plural(pages, 'page')}`)
    : (has ? 'No matches' : 'Type to search');
  ['fprev', 'fnext'].forEach(i => $(i).disabled = !m.length);
  $('all').disabled = !m.length || f.truncated;                // redacting only the first part of a long list would leave the rest
  $('all').textContent = m.length ? `Redact all (${m.length})` : 'Redact all';
}
function setHits(m, truncated = false) {
  const f = S.find; f.m = m; f.now = 0; f.truncated = truncated; f.byPage = new Map();
  m.forEach((x, i) => f.byPage.has(x.p) ? f.byPage.get(x.p).push([i, x]) : f.byPage.set(x.p, [[i, x]]));
  render(); if (m.length) jump();
}
async function jump() {                                      // draw the target page first, then move, so there is no blank
  const f = S.find, x = f.m[f.now]; if (!x) return;
  const seq = ++S.jumpSeq, near = [f.m[f.now + 1], f.m[f.now - 1]].filter(Boolean);
  await ensure(x.p);
  if (seq !== S.jumpSeq) return;
  scrollToY(S.tops[x.p] + x.boxes[0][1] * k(x.p) - $('stage').clientHeight / 3);
  near.forEach(y => ensure(y.p));                              // warm the next and previous match pages
}
const step = d => { const f = S.find; if (!f.m.length) return; f.now = (f.now + d + f.m.length) % f.m.length; render(); jump(); };
async function doFind() {
  const q = $('q').value.trim(), seq = ++S.find.seq;
  if (!q && !S.kind) return setHits([]);
  $('count').textContent = 'Searching…';
  const r = await pywebview.api.search(q, S.kind, $('fz').checked);
  if (seq === S.find.seq) setHits(r.matches, r.truncated);
}
const clearChips = () => document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
function resetFind() { $('q').value = ''; S.kind = null; clearChips(); S.find.seq++; setHits([]); }
let ft; $('q').oninput = () => { S.kind = null; clearChips(); clearTimeout(ft); ft = setTimeout(doFind, 200); };
$('qx').onclick = () => { resetFind(); $('q').focus(); };
$('fz').onchange = doFind;
document.querySelectorAll('.chip').forEach(c => c.onclick = () => {
  const on = c.classList.contains('on'); clearChips();
  S.kind = on ? null : c.dataset.k; c.classList.toggle('on', !on); $('q').value = ''; doFind();
});
$('fnext').onclick = () => step(1); $('fprev').onclick = () => step(-1);
$('all').onclick = () => addBoxes(S.find.m.flatMap(x => x.boxes.map(b => ({ p: x.p, box: b }))));
