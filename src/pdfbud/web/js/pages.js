// The column of pages: sized up front, drawn near the screen, scrolled and shown in a strip of thumbnails.
// ---- the column: pages are sized up front, pictures are drawn only near the screen ----
function buildCol() {
  S.fitW = Math.max(300, Math.min($('stage').clientWidth - 40, 1100)) * S.zoom;
  $('col').replaceChildren(...S.sizes.map((s, n) => {
    const p = document.createElement('div');
    p.className = 'page'; p.dataset.n = n; p.dataset.label = 'Page ' + (n + 1);
    p.innerHTML = '<div class="pic"></div><div class="txl"></div><div class="ov"></div>';
    p.style.width = S.fitW + 'px'; p.style.height = Math.round(s[1] * k(n)) + 'px';
    return p;
  }));
  S.cache.clear(); S.layout++;
  S.tops = [...$('col').children].map(p => p.offsetTop);
}
// Drawing pages: a quick blurry draft first so nothing is blank, a sharp copy once scrolling slows.
// Jobs are picked at the moment a slot frees up, so pages you have already scrolled past are never drawn.
const idle = () => performance.now() - S.lastScroll > 150;
function nextJob() {
  const has = n => S.cache.get(n), free = n => !S.busy.has(n);
  for (const n of S.must.keys()) if (free(n) && !has(n)?.sharp) return [n, false];       // a jump is waiting on this page
  for (const n of S.want.vis) if (!has(n) && free(n)) return [n, true];                  // anything beats a blank page
  for (const n of S.want.near) if (!has(n) && free(n)) return [n, true];
  if (idle()) for (const n of [...S.want.vis, ...S.want.near]) if (!has(n)?.sharp && free(n)) return [n, false];
}
async function run([n, draft]) {
  const gen = S.layout; S.busy.add(n);
  try {
    const r = await pywebview.api.page(n, draft ? 600 : Math.min(Math.round(S.fitW * dpr), 3200), draft);
    if (gen !== S.layout) return;
    const img = Object.assign(new Image(), { alt: 'Page ' + (n + 1), src: r.img });
    await img.decode().catch(() => {});
    if (gen !== S.layout || !(S.must.has(n) || S.want.vis.includes(n) || S.want.near.includes(n))) return;   // scrolled away meanwhile: drop it
    if (!draft || !S.cache.get(n)) { S.cache.set(n, { img, lines: r.lines || [], words: r.words || [], fields: r.fields || [], sharp: !draft }); paint(n); }
  } catch (e) { /* page vanished while closing */ }
  finally {
    S.busy.delete(n);
    if ((S.cache.get(n)?.sharp || gen !== S.layout) && S.must.has(n)) { S.must.get(n).forEach(f => f()); S.must.delete(n); }
    pump();
  }
}
function pump() { while (S.busy.size < 2) { const j = nextJob(); if (!j) return; run(j); } }
const ensure = n => S.cache.get(n)?.sharp ? Promise.resolve() : new Promise(res => { (S.must.get(n) || S.must.set(n, []).get(n)).push(res); pump(); });

function onScroll() {
  const st = $('stage').scrollTop, vh = $('stage').clientHeight, T = S.tops;
  if (!T.length) return;
  S.lastScroll = performance.now();
  let n = 0; while (n + 1 < T.length && T[n + 1] <= st + vh / 3) n++;
  const span = (lo, hi) => T.map((t, i) => i).filter(i => T[i] + S.sizes[i][1] * k(i) >= lo && T[i] <= hi);
  const vis = span(st, st + vh), near = span(st - 1500, st + vh + 1500).filter(i => !vis.includes(i)).sort((x, y) => Math.abs(x - n) - Math.abs(y - n));
  S.want = { vis, near };
  const lo = Math.min(...vis, ...near) - 6, hi = Math.max(...vis, ...near) + 6;
  S.cache.forEach((_, i) => { if (i < lo || i > hi) { S.cache.delete(i); clearPage(i); } });
  pump(); clearTimeout(S.idleT); S.idleT = setTimeout(() => { pump(); pumpThumbs(); }, 170);   // sharp pass once scrolling stops
  if (n !== S.page || $('pg').value !== String(n + 1)) { S.page = n; $('clear').disabled = !mine().length; $('pg').value = n + 1; navThumb(); noteFields(); navState(); }
}
function navThumb() {
  document.querySelectorAll('.th.now').forEach(t => t.classList.remove('now'));
  const t = $('strip').children[S.page]; t && (t.classList.add('now'), t.scrollIntoView({ block: 'nearest' }));
}
let anim = 0;                                                 // our own glide: the browser's cannot be cancelled by the next move
function scrollToY(top) {
  const st = $('stage'), y0 = st.scrollTop, t0 = performance.now(), id = ++anim;
  if (Math.abs(top - y0) > st.clientHeight * 2) { st.scrollTop = top; return; }   // far jumps are instant: a long glide only shows blank pages going by
  (function step(now) {
    if (id !== anim) return;
    const p = Math.min(1, (now - t0) / 260);
    st.scrollTop = y0 + (top - y0) * (1 - (1 - p) ** 3); if (p < 1) requestAnimationFrame(step);
  })(t0);
}
const go = n => { S.jumpSeq++; scrollToY(S.tops[Math.max(0, Math.min(S.sizes.length - 1, n))]); };   // your own move cancels a search jump still waiting
function navState() { $('first').disabled = $('prev').disabled = S.page <= 0; $('next').disabled = $('last').disabled = S.page >= S.sizes.length - 1; }

const tw = new Set();                                         // thumbnails on screen; drawn one at a time when scrolling is idle
function pumpThumbs() {
  if (!idle() || S.thumbBusy) return;
  const t = [...tw].find(e => !e.querySelector('img').src); if (!t) return;
  const gen = S.layout; S.thumbBusy = true;
  pywebview.api.thumb(+t.dataset.n).then(src => { if (gen === S.layout) t.querySelector('img').src = src; }).catch(() => {})
    .finally(() => { S.thumbBusy = false; setTimeout(pumpThumbs, 0); });
}
function buildStrip() {
  tw.clear(); S.thumbBusy = false;
  const io = new IntersectionObserver(es => { es.forEach(e => e.isIntersecting ? tw.add(e.target) : tw.delete(e.target)); pumpThumbs(); },
    { root: $('strip'), rootMargin: '300px' });
  $('strip').replaceChildren(...S.sizes.map((s, n) => {
    const t = document.createElement('div');
    t.className = 'th' + (n ? '' : ' now'); t.dataset.n = n;
    t.innerHTML = `<i style="height:${96 * s[1] / s[0]}px"><img alt=""></i>${n + 1}${OCR.scans.has(n) ? ' · scan' : ''}`;
    t.onclick = () => go(n); io.observe(t); return t;
  }));
}
