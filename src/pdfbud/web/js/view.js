// How the pages are shown: mode, zoom (buttons, pinch, Ctrl-scroll), refitting, and the Mac's full screen.
function setMode(m) {
  S.mode = m; S.picked = null; ['View', 'Hide', 'Edit', 'Fill'].forEach(x => $('m' + x).setAttribute('aria-pressed', x.toLowerCase() === m));
  $('col').className = 'col ' + m;
  $('hint').textContent = { view: 'Scroll to read. Switch to Redact or Edit text to make changes. ⌘F searches.',
    hide: 'Click a line or drag over anything to redact it. Click the x on a red box to remove it.',
    edit: 'Click a line to change it. Enter applies, Esc cancels. New text stays on one line.',
    fill: 'Click a field and type. Tab moves to the next field. Fields stay fillable in the saved copy.' }[m];
  render();
}

function relayout() {                                         // window or strip size changed: refit pages, keep place
  if (noDoc()) return;
  const st = $('stage'), ry = st.scrollTop / st.scrollHeight, rx = st.scrollLeft / st.scrollWidth;
  buildCol(); st.scrollTop = ry * st.scrollHeight; st.scrollLeft = rx * st.scrollWidth; render(); onScroll();
}
function zoomTo(z, px = $('stage').clientWidth / 2, py = $('stage').clientHeight / 2) {   // px, py: the screen point that stays put
  z = Math.max(ZOOMS[0], Math.min(ZOOMS.at(-1), z));
  if (Math.abs(z - S.zoom) < .005) return;
  const st = $('stage'), f = z / S.zoom, cx = st.scrollLeft + px, cy = st.scrollTop + py;
  S.zoom = z; $('zfit').textContent = Math.round(z * 100) + '%';
  buildCol(); st.scrollLeft = cx * f - px; st.scrollTop = cy * f - py; render(); onScroll();
}
const zoom = d => zoomTo(d > 0 ? ZOOMS.find(v => v > S.zoom + .01) ?? S.zoom : d < 0 ? [...ZOOMS].reverse().find(v => v < S.zoom - .01) ?? S.zoom : 1);
let live = null;                                              // pinch or Ctrl-scroll: scale at once, redraw sharply when it settles
function liveZoom(z, x, y, settle) {
  const st = $('stage'), col = $('col'), r = col.getBoundingClientRect();
  if (!live) live = { z0: S.zoom, ox: x - r.left, oy: y - r.top, px: x - st.getBoundingClientRect().left, py: y - st.getBoundingClientRect().top };
  live.z = Math.max(ZOOMS[0], Math.min(ZOOMS.at(-1), z));
  col.style.transformOrigin = `${live.ox}px ${live.oy}px`; col.style.transform = `scale(${live.z / live.z0})`;
  clearTimeout(live.t); if (settle) live.t = setTimeout(endLive, 180);
}
function endLive() { const l = live; if (!l) return; live = null; clearTimeout(l.t); $('col').style.transform = ''; zoomTo(l.z, l.px, l.py); }
let base = 1;
$('stage').addEventListener('gesturestart', e => { e.preventDefault(); endLive(); base = S.zoom; });
$('stage').addEventListener('gesturechange', e => { e.preventDefault(); liveZoom(base * e.scale, e.clientX, e.clientY, false); });
$('stage').addEventListener('gestureend', e => { e.preventDefault(); endLive(); });
$('stage').addEventListener('wheel', e => { if (!e.ctrlKey && !e.metaKey) return; e.preventDefault(); liveZoom((live ? live.z : S.zoom) * Math.exp(-e.deltaY / 200), e.clientX, e.clientY, true); }, { passive: false });
$('zin').onclick = () => zoom(1); $('zout').onclick = () => zoom(-1); $('zfit').onclick = () => zoom(0);
$('side').onclick = () => { $('strip').classList.toggle('closed'); $('side').classList.toggle('on'); relayout(); };
window.addEventListener('resize', (() => { let t; return () => { clearTimeout(t); t = setTimeout(relayout, 250); }; })());

// Full screen: the Mac's own, with the bars slid out of the way. The window tells us when it really changes (see setFS(.., true)).
const FS = { on: false, tt: 0 }, FS_IN = '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', FS_OUT = '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>';
function setFS(on, native) {
  if (FS.on === on) return;
  FS.on = on; document.body.classList.toggle('fs', on); document.body.classList.remove('reveal', 'revealSide');
  $('fs').querySelector('svg').innerHTML = on ? FS_OUT : FS_IN; $('fs').title = on ? 'Leave full screen (Esc)' : 'Full screen (⌃⌘F)';
  if (!native) pywebview.api.fullscreen(on);
  if (!noDoc()) relayout();
  $('toast').classList.toggle('on', on); clearTimeout(FS.tt); FS.tt = setTimeout(() => $('toast').classList.remove('on'), 2600);
}
$('fs').onclick = () => setFS(!FS.on);
document.addEventListener('mousemove', e => {
  if (!FS.on) return;
  const b = document.body.classList, ch = $('chrome'), typingInBar = ch.contains(document.activeElement) && /INPUT|SELECT/.test(document.activeElement.tagName);
  if (e.clientY < 8) b.add('reveal'); else if (b.contains('reveal') && !typingInBar && e.clientY > ch.offsetHeight + 30) b.remove('reveal');
  if (e.clientX < 8 && e.clientY > 40) b.add('revealSide'); else if (b.contains('revealSide') && e.clientX > 190) b.remove('revealSide');
});
