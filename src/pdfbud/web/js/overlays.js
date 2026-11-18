// What sits on a page: line buttons, boxes, edits, form fields and search hits, and the toolbar state that follows them.
function at(tag, cls, box, n) {
  const e = document.createElement(tag), z = k(n);
  e.className = cls;
  Object.assign(e.style, { left: box[0]*z+'px', top: box[1]*z+'px', width: (box[2]-box[0])*z+'px', height: (box[3]-box[1])*z+'px' });
  return e;
}
function lineBtn(n, l) {
  const b = at('button', 'ln', l.box, n);
  b.setAttribute('aria-label', (S.mode === 'hide' ? 'Redact line: ' : 'Edit line: ') + l.text);
  b.onclick = () => { if (S.dragged) return; S.mode === 'hide' ? commit(cs => [...cs, { p: n, box: l.box }]) : startEdit(n, l); };
  return b;
}
function changeEl(c) {
  const e = at('div', c.text === undefined ? 'box' : 'edited', c.box, c.p);
  if (c.text !== undefined) { e.textContent = c.text; e.style.font = `${c.size*k(c.p)}px/${(c.box[3]-c.box[1])*k(c.p)}px ${fam(c.font)}`; }
  const x = document.createElement('button');
  x.className = 'x'; x.textContent = '×'; x.setAttribute('aria-label', 'Remove this change');
  x.onclick = ev => { ev.stopPropagation(); commit(cs => cs.filter(q => q !== c)); };
  e.append(x);
  if (c.text === undefined) { e.classList.toggle('picked', c === S.picked); e.onclick = ev => { if (ev.target === e) pickBox(c); }; }
  return e;
}
const addBoxes = list => commit(cs => [...cs, ...list.filter(a => !cs.some(c => c.text === undefined && c.field === undefined && c.p === a.p && same(c.box, a.box)))]);
const hits = n => (S.find.byPage.get(n) || []).flatMap(([i, m]) => m.boxes.map(b => at('div', 'hit' + (i === S.find.now ? ' now' : '') + (m.ocr ? ' ocr' : ''), b, n)));

function fieldEl(n, f) {                                      // a form field laid over its place on the page
  const fill = cur().find(c => c.p === n && c.field === f.xref), v = fill ? fill.value : f.value;
  const e = at(f.kind === 'choice' ? 'select' : f.multiline ? 'textarea' : 'input', 'fld' + (fill ? ' filled' : ''), f.box, n);
  e.setAttribute('aria-label', f.name); e.style.fontSize = Math.min((f.box[3] - f.box[1]) * .7, 14) * k(n) + 'px';
  if (f.kind === 'check') { e.type = 'checkbox'; e.checked = v; }
  else if (f.kind === 'choice') { e.append(...f.choices.map(c => new Option(c, c))); e.value = v; }
  else e.value = v;
  e.onchange = () => commit(cs => [...cs.filter(c => !(c.p === n && c.field === f.xref)),
    { p: n, field: f.xref, name: f.name, value: f.kind === 'check' ? e.checked : e.value, box: f.box }]);
  return e;
}
function noteFields() {
  const f = S.cache.get(S.page)?.fields || [];
  $('fieldnote').hidden = !f.length; $('fieldnote').textContent = plural(f.length, 'fillable field') + ' on this page';
  $('ocrnote').hidden = !OCR.read.has(S.page);
}
function clearPage(n) { const p = pageEl(n); if (p) { [...p.children].forEach(l => l.replaceChildren()); p._tx = null; } }
function paint(n) {                                           // one page: its picture and text layer (kept apart, so a selection survives), then the clickable layer
  const p = pageEl(n), c = S.cache.get(n);
  if (!p) return;
  const [pic, txl, ov] = p.children, fs = c ? c.fields : [], filled = f => cur().some(x => x.p === n && x.field === f.xref);
  if (c && pic.firstChild !== c.img) pic.replaceChildren(c.img);
  if (c && S.mode === 'view' && p._tx !== c) { txl.replaceChildren(...textLines(n, c.lines)); fitText(txl); p._tx = c; }
  ov.replaceChildren(...(c && (S.mode === 'hide' || S.mode === 'edit') ? c.lines.filter(l => S.mode === 'hide' || !l.ocr).map(l => lineBtn(n, l)) : []),
                     ...fs.filter(f => S.mode === 'fill' || filled(f)).map(f => fieldEl(n, f)),
                     ...cur().filter(x => x.p === n && x.field === undefined).map(changeEl), ...hits(n));
}
function render() {
  const all = cur(), edits = all.filter(c => c.text !== undefined).length, fills = all.filter(c => c.field !== undefined).length, withChanges = new Set(all.map(c => c.p));
  new Set([...S.cache.keys(), ...withChanges, ...S.find.byPage.keys()]).forEach(paint);   // changes show even while a page picture reloads
  document.querySelectorAll('.th').forEach((t, n) => t.classList.toggle('has', withChanges.has(n)));
  $('save').disabled = !all.length; $('clear').disabled = !mine().length; $('undo').disabled = H.length < 2;
  $('cnt').textContent = all.length ? `(${all.length})` : '';
  window.pywebview?.api?.report_changes?.(all.length);       // the bridge may not be ready for the very first render
  $('status').textContent = S.msg || (all.length ? `${plural(all.length - edits - fills, 'box')}, ${plural(edits, 'edit')}${fills ? ', ' + plural(fills, 'field') : ''} on ${plural(withChanges.size, 'page')}` : 'No changes yet');
  $('fontnote').hidden = !edits; $('fontnote').textContent = `Font swapped on ${plural(edits, 'line')}`;
  noteFields(); navState(); renderFind();
}

function startEdit(n, l) {
  const inp = at('input', 'ed', l.box, n);
  inp.value = l.text; inp.setAttribute('aria-label', 'Replace this line');
  inp.style.fontSize = l.size * k(n) + 'px'; inp.style.height = ''; inp.style.minHeight = (l.box[3]-l.box[1])*k(n)+'px';
  pageEl(n).append(inp); inp.focus(); inp.select();
  const done = async (ok, leaving) => {
    if (!inp.isConnected) return;
    const v = inp.value, changed = ok && v !== l.text;
    const bad = changed ? await pywebview.api.bad_chars(v) : [];
    if (!inp.isConnected) return;
    if (bad.length) {                                          // the font cannot write these: say so, keep the line as it was
      S.msg = $('status').textContent = `Can't write ${bad.join(' ')} here: the font has Latin letters only.`;
      return leaving ? (inp.remove(), render()) : inp.focus();
    }
    inp.remove();
    if (changed) commit(cs => [...cs.filter(c => !(c.text !== undefined && c.p === n && same(c.box, l.box))),
      { p: n, box: l.box, text: v, origin: l.origin, size: l.size, font: l.font, color: l.color, rotate: l.rotate }]);
  };
  inp.onkeydown = e => { if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); };
  inp.onblur = () => done(true, true);
}

let drag = null;                                              // free box: drag anywhere on a page in Redact mode
$('col').addEventListener('mousedown', e => {
  const pg = e.target.closest('.page');
  if (S.mode !== 'hide' || !pg || e.target.closest('.x')) return;
  const r = pg.getBoundingClientRect();
  drag = { pg, n: +pg.dataset.n, x: e.clientX - r.left, y: e.clientY - r.top, r, g: null };
});
window.onmousemove = e => {
  if (!drag) return;
  const d = drag, x = e.clientX - d.r.left, y = e.clientY - d.r.top;
  d.box = [Math.min(d.x, x), Math.min(d.y, y), Math.max(d.x, x), Math.max(d.y, y)];
  if (!d.g && d.box[2] - d.box[0] < 5 && d.box[3] - d.box[1] < 5) return;
  d.g = d.g || d.pg.appendChild(Object.assign(document.createElement('div'), { className: 'box' }));
  Object.assign(d.g.style, { left: d.box[0]+'px', top: d.box[1]+'px', width: d.box[2]-d.box[0]+'px', height: d.box[3]-d.box[1]+'px' });
};
window.onmouseup = () => {
  const d = drag; drag = null;
  if (!d || !d.g) return;
  d.g.remove(); S.dragged = true; setTimeout(() => S.dragged = false);
  commit(cs => [...cs, { p: d.n, box: d.box.map(v => v / k(d.n)) }]);
};
