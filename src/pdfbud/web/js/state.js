// Shared state and small helpers. Every other script reads these.
const $ = id => document.getElementById(id);
const noDoc = () => document.body.classList.contains('noDoc');
const dpr = window.devicePixelRatio || 1;
const ZOOMS = [.5, .75, 1, 1.25, 1.5, 2, 3, 4];
const S = {
  doc: 0,                                           // counts opened files: late answers about an earlier file are ignored
  layout: 0,                                        // counts page layouts (zoom, resize): late pictures of an old layout are ignored
  page: 0, sizes: [], mode: 'view', zoom: 1, fitW: 600, msg: '', tops: [], kind: null,
  cache: new Map(),                                 // page -> { img, lines, fields, sharp }
  find: { m: [], now: 0, seq: 0, byPage: new Map(), truncated: false },
  want: { vis: [], near: [] }, must: new Map(), busy: new Set(), lastScroll: 0,    // the page drawing queue
  jumpSeq: 0, thumbBusy: false, idleT: 0, dragged: false,
  picked: null, clip: null,                         // the box you clicked, and the box you copied
};
const H = [[]], cur = () => H.at(-1);                       // history: every action pushes a new change list
const commit = fn => { H.push(fn(cur())); S.msg = ''; render(); };
const undo = () => H.length > 1 && (H.pop(), S.msg = '', render());
const mine = () => cur().filter(c => c.p === S.page);
const same = (a, b) => a.join() === b.join();
const k = n => S.fitW / S.sizes[n][0];                      // css px per PDF point on page n
const fam = f => /Times/.test(f) ? 'Times, serif' : /Courier/.test(f) ? 'Courier, monospace' : 'Helvetica, Arial, sans-serif';
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : /(x|s|ch|sh)$/.test(w) ? 'es' : 's'}`;
const pageEl = n => $('col').children[n];
