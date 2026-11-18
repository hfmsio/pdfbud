// Opening, closing and saving a file, the keyboard, and start-up.
let armedOpen = 0;                                            // Open with unsaved changes: the first request warns, the second goes ahead
const attempt = async opened => { try { show(await opened); } catch (e) { S.msg = 'Could not open: ' + (e.message || e); render(); } };
function load(path) {
  const n = cur().length;
  if (n && !armedOpen) {
    S.msg = `You have ${plural(n, 'unsaved change')}. Open again to discard them.`; render();
    armedOpen = setTimeout(() => { armedOpen = 0; if (S.msg.startsWith('You have')) { S.msg = ''; render(); } }, 4000);
    return;
  }
  clearTimeout(armedOpen); armedOpen = 0;
  return attempt(pywebview.api.open(path || null));
}
const shortPath = p => p.length > 90 ? p.slice(0, 30) + '…' + p.slice(-59) : p;

function resetDoc(r) {                                        // r: the file's info from Python, or null once it is closed
  H.length = 0; H.push([]); S.msg = ''; S.page = 0; S.zoom = 1; S.doc++; S.layout++; S.picked = S.clip = null;
  S.sizes = r ? r.sizes : []; S.tops = []; S.cache.clear();
  $('zfit').textContent = '100%'; resetOcr(r?.scans || [], !!r?.ocr); resetFind();
  document.title = r ? 'pdfbud - ' + r.name : 'pdfbud'; pywebview.api.set_title(document.title);
  $('ptext').textContent = r ? shortPath(r.path) : ''; $('path').title = r ? 'Show in Finder: ' + r.path : ''; $('path').hidden = !r;
  $('close').disabled = !r; document.body.classList.toggle('noDoc', !r);
}
function show(r) {
  if (!r) return;
  resetDoc(r); setMode('view');
  buildCol(); buildStrip(); $('stage').scrollTop = 0; $('of').textContent = 'of ' + r.pages; $('pg').value = 1;
  render(); onScroll(); $('stage').focus();
}
async function save() {
  if (!cur().length) return;
  $('save').disabled = true; $('status').textContent = 'Saving…';
  try { const out = await pywebview.api.save(cur()); S.msg = out ? 'Saved ' + out.split('/').pop() : 'Save cancelled'; } catch (e) { S.msg = 'Could not save: ' + e; }
  render();
}
let armed = 0;                                                // Close with changes: the first click warns, the second closes
const closeText = (t, warn) => { $('close').querySelector('.lbl').textContent = t; $('close').classList.toggle('armed', warn); };
const disarm = () => { clearTimeout(armed); armed = 0; closeText('Close', false); };
$('close').onclick = async () => {
  const n = cur().length;
  if (n && !armed) { closeText(`Discard ${plural(n, 'change')}?`, true); armed = setTimeout(disarm, 4000); return; }
  disarm(); await pywebview.api.close();
  resetDoc(null); $('col').replaceChildren(); $('strip').replaceChildren(); render();
};

$('open').onclick = $('open2').onclick = () => load();
$('path').onclick = () => pywebview.api.reveal();
$('first').onclick = () => go(0); $('last').onclick = () => go(S.sizes.length - 1);
$('prev').onclick = () => go(S.page - 1); $('next').onclick = () => go(S.page + 1);
$('pg').onchange = e => go((parseInt(e.target.value) || 1) - 1);
$('mView').onclick = () => setMode('view'); $('mHide').onclick = () => setMode('hide'); $('mFill').onclick = () => setMode('fill'); $('mEdit').onclick = () => setMode('edit');
$('blk').onchange = e => $('stage').classList.toggle('preview', e.target.checked);
$('undo').onclick = undo; $('save').onclick = save;
$('clear').onclick = () => commit(cs => cs.filter(c => c.p !== S.page));
$('stage').addEventListener('scroll', () => requestAnimationFrame(onScroll), { passive: true });
$('stage').addEventListener('wheel', () => { S.jumpSeq++; anim++; }, { passive: true });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', e => e.preventDefault());                // the app side opens the file: pywebview passes its path to Python

const KEYS = { v: () => setMode('view'), r: () => setMode('hide'), e: () => setMode('edit'), f: () => setMode('fill'), p: () => $('blk').click(),
  ArrowLeft: () => go(S.page - 1), ArrowRight: () => go(S.page + 1), Home: () => go(0), End: () => go(S.sizes.length - 1), Escape: () => FS.on && setFS(false) };
window.addEventListener('keydown', e => {
  const t = e.target, typing = (t.tagName === 'INPUT' && t.type !== 'checkbox') || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA';
  if (typing && e.target === $('q')) {
    if (e.key === 'Enter') { e.preventDefault(); step(e.shiftKey ? -1 : 1); }
    if (e.key === 'Escape') { resetFind(); e.target.blur(); }
  }
  if (e.metaKey && e.key === 'o') { e.preventDefault(); load(); }
  else if (e.metaKey && e.key === 's') { e.preventDefault(); save(); }
  else if (e.metaKey && e.ctrlKey && e.key === 'f') { e.preventDefault(); setFS(!FS.on); }
  else if (e.metaKey && e.key === 'f') { e.preventDefault(); document.body.classList.add('reveal'); $('q').focus(); $('q').select(); }
  else if (e.metaKey && e.key === 'z' && !typing) { e.preventDefault(); undo(); }
  else if (e.metaKey && e.key === 'a' && !typing && S.mode === 'view' && !noDoc()) { e.preventDefault(); selectPage(); }
  else if (e.metaKey && e.key === 'x' && !typing && hasSelection()) { e.preventDefault(); cutSelection(); }
  else if (e.metaKey && e.key === 'c' && !typing && !hasSelection() && copyBox()) e.preventDefault();
  else if (e.metaKey && e.key === 'v' && !typing && pasteBox()) e.preventDefault();
  else if (e.metaKey && e.key === 'w' && !noDoc()) { e.preventDefault(); $('close').click(); }
  else if (e.metaKey && (e.key === '=' || e.key === '+')) { e.preventDefault(); zoom(1); }
  else if (e.metaKey && e.key === '-') { e.preventDefault(); zoom(-1); }
  else if (e.metaKey && e.key === '0') { e.preventDefault(); zoom(0); }
  else if (typing || e.metaKey || e.ctrlKey || noDoc()) return;
  else if (KEYS.hasOwnProperty(e.key)) { e.preventDefault(); KEYS[e.key](); }   // marking the key handled stops the Mac error beep
});

window.addEventListener('pywebviewready', () => attempt(pywebview.api.initial()));
setMode('view');
