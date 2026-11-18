// ---- scanned pages: read in the background with the Mac's text recognition ----
const OCR = { state: 'idle', stopping: false, dismissed: false, timer: 0, ok: false, scans: new Set(), read: new Set() };
function renderNotice() {
  const n = OCR.scans.size, running = OCR.state === 'running', left = [...OCR.scans].filter(p => !OCR.read.has(p)).length;
  $('notice').hidden = !n || OCR.dismissed;
  const unread = OCR.ok && left > 0 && !running;
  $('scanchip').hidden = !(n && OCR.dismissed && unread);
  $('scanchip').textContent = `${plural(left, 'unread scan')}: show`;
  $('read').hidden = running || (OCR.ok && !left); $('prog').hidden = $('stop').hidden = !running;
  $('read').disabled = !OCR.ok; $('read').title = OCR.ok ? '' : 'Needs macOS';
  $('prog').firstElementChild.style.width = (OCR.read.size / n * 100 || 0) + '%';
  $('ntext').textContent = !OCR.ok ? "Reading scanned pages isn't available on this computer (it needs macOS). You can still redact scans by drawing boxes."
    : running ? `Reading scanned page ${Math.min(OCR.read.size + 1, n)} of ${n}. Search already works on the other pages.`
    : !left ? 'Scanned pages read. Matches on them have a dashed outline: the computer can miss or misread words, so check those pages by eye.'
    : OCR.state === 'stopped' ? 'Stopped. Pages read so far stay searchable.'
    : `${plural(n, 'page')} ${n === 1 ? "is a scan, so search can't read it" : "are scans, so search can't read them"} yet.`;
}
function resetOcr(scans, ok) {
  clearInterval(OCR.timer); Object.assign(OCR, { state: 'idle', stopping: false, dismissed: false, timer: 0, ok, scans: new Set(scans), read: new Set() }); renderNotice();
}
async function ocrPoll(gen) {
  const s = await pywebview.api.ocr_status().catch(() => null);
  if (!s || gen !== S.doc) return;
  const fresh = s.read.filter(p => !OCR.read.has(p));
  OCR.read = new Set(s.read);
  fresh.forEach(p => { const c = S.cache.get(p); if (c) c.sharp = false; });             // redraw them, so they pick up their clickable lines
  if (fresh.length) { pump(); if ($('q').value.trim() || S.kind) doFind(); render(); }
  if (!s.running) { clearInterval(OCR.timer); OCR.timer = 0; OCR.state = OCR.stopping ? 'stopped' : 'done'; }
  renderNotice();
}
$('read').onclick = async () => {
  OCR.state = 'running'; OCR.stopping = false; renderNotice();
  await pywebview.api.ocr_start();
  const gen = S.doc; OCR.timer = setInterval(() => ocrPoll(gen), 500);
};
$('stop').onclick = () => { OCR.stopping = true; pywebview.api.ocr_stop(); };
$('ndismiss').onclick = () => { OCR.dismissed = true; renderNotice(); };
$('scanchip').onclick = () => { OCR.dismissed = false; renderNotice(); };
