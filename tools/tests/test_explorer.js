/* The history explorer draws the right points and reads them out.
 *
 *   the default view (|Δm²|, NO, all groups, 3σ, GLOBAL-NU) has one marker per
 *     row quoted for normal ordering or for both, and switching to IO swaps in
 *     the rows quoted for inverted ordering or both;
 *   a group switched off loses every one of its markers, and the last group
 *     left on cannot be switched off;
 *   "As published" for Δm² reads out the signed number the paper printed (NuFit
 *     inverted ordering prints a negative one) while the chart plots |value|;
 *   a click on a point puts that row's journal in the readout, Escape clears it;
 *   and when the data file cannot be fetched the container says so in one
 *     sentence and holds nothing else.
 *
 *   node tools/tests/test_explorer.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/explorer.js'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(ROOT, 'data-exports/history.json'), 'utf8'));

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };
const check = (c, m) => (c ? ok(m) : bad(m));
const tick = () => new Promise(r => setTimeout(r, 20));

async function boot(fetchImpl) {
  const dom = new JSDOM('<!doctype html><body><div class="explorer" data-src="data/history.json"></div></body>',
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.fetch = fetchImpl;
  dom.window.eval(js);
  await tick();
  return dom.window;
}
const good = () => Promise.resolve({ ok: true, json: () => Promise.resolve(data) });

const markers = w => Array.from(w.document.querySelectorAll('.explorer__pt'));
const click = (w, el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
const btn = (w, text) => Array.from(w.document.querySelectorAll('.explorer__btn'))
  .find(b => b.textContent.replace(/[●■◆]/g, '').trim() === text);
const rowsOf = (ords, grp) => data.rows.filter(r => r.parameter === 'Dm2' && ords.includes(r.ordering) &&
  r.value_our_convention != null && (!grp || r.group === grp));

(async () => {
  /* 1. default render */
  let w = await boot(good);
  const nNO = rowsOf(['no', 'any']).length;
  check(markers(w).length === nNO, `default view draws ${nNO} markers (got ${markers(w).length})`);
  const sum = w.document.querySelector('.explorer__summary');
  check(sum.getAttribute('aria-live') === 'polite' && /normal ordering, 3σ, GLOBAL-NU convention: \d+ points from Bari, NuFit, Valencia/.test(sum.textContent),
        'live summary: ' + sum.textContent);
  const small = Array.from(w.document.querySelectorAll('.explorer__btn'))
    .filter(b => !b.closest('.explorer__dl'))
    .every(b => b.hasAttribute('aria-pressed') || b.classList.contains('explorer__toggle'));
  check(small, 'every control button carries aria-pressed');
  const api = w.document.querySelector('.explorer').__explorer;
  const csvRows = api.csvTable().trim().split('\n').length - 2;
  const marks = w.document.querySelectorAll('.explorer svg g[tabindex]').length;
  check(csvRows === marks, `CSV download has one row per point shown (${csvRows} rows, ${marks} markers)`);
  const svgText = api.standaloneSvg();
  // jsdom does not resolve CSS variables in computed styles, so only the
  // structure is checked here; the colours are checked in a real browser.
  check(svgText && svgText.includes('xmlns="http://www.w3.org/2000/svg"') && /<rect[^>]*style="fill:/.test(svgText),
        'SVG download is standalone: namespace and background set');
  check(/GLOBAL-NU|Converted to/.test(w.document.querySelector('.explorer__note').textContent) &&
        w.document.querySelector('.explorer__note a').getAttribute('href') === '#method',
        'convention note shown, with a link to #method');

  /* 2. IO */
  click(w, btn(w, 'IO'));
  const nIO = rowsOf(['io', 'any']).length;
  check(markers(w).length === nIO && nIO !== nNO, `IO view draws ${nIO} markers (got ${markers(w).length})`);
  click(w, btn(w, 'NO'));

  /* 3. group toggles */
  click(w, btn(w, 'NuFit'));
  const noNufit = rowsOf(['no', 'any']).filter(r => r.group !== 'nufit').length;
  check(markers(w).length === noNufit && markers(w).every(m => !/NuFit/.test(m.getAttribute('aria-label'))),
        `NuFit off removes its markers (${markers(w).length} left, expected ${noNufit})`);
  click(w, btn(w, 'Valencia'));
  click(w, btn(w, 'Bari'));
  const only = markers(w).length;
  check(btn(w, 'Bari').getAttribute('aria-pressed') === 'true' && only === rowsOf(['no', 'any'], 'bari').length,
        'last remaining group (Bari) cannot be switched off');
  check(/At least one group/.test(w.document.querySelector('.explorer__hint').textContent), 'refusal is explained');
  click(w, btn(w, 'NuFit')); click(w, btn(w, 'Valencia'));

  /* 4. 1σ with a missing range */
  click(w, btn(w, '1σ'));
  const nf = markers(w).find(m => /NuFit 2012/.test(m.getAttribute('aria-label')));
  click(w, nf);
  check(/no 1σ range published/.test(w.document.querySelector('.explorer__readout').textContent),
        'a row without a 1σ range says so and keeps its marker');
  click(w, btn(w, '3σ'));

  /* 5. as published: signed printed value for a NuFit IO row */
  click(w, btn(w, 'IO'));
  click(w, btn(w, 'As published'));
  check(/three groups quote different quantities/.test(w.document.querySelector('.explorer__note').textContent),
        'as-published note shown');
  const nfIO = data.rows.find(r => r.parameter === 'Dm2' && r.group === 'nufit' && r.ordering === 'io' && r.year === 2024);
  const m2024 = markers(w).find(m => /NuFit 2024/.test(m.getAttribute('aria-label')));
  click(w, m2024);
  const ro = w.document.querySelector('.explorer__readout').textContent;
  check(nfIO.value_as_published < 0 && ro.indexOf(String(nfIO.value_as_published)) >= 0,
        `NuFit IO readout shows the signed printed value ${nfIO.value_as_published}`);
  check(m2024.getAttribute('transform') !== null &&
        +m2024.getAttribute('transform').match(/,([-\d.]+)\)/)[1] > 0, 'marker plotted (absolute value, inside the chart)');
  click(w, btn(w, 'GLOBAL-NU convention'));
  click(w, btn(w, 'NO'));

  /* 6. click fills the readout; Escape clears it */
  const tgt = data.rows.find(r => r.parameter === 'Dm2' && r.group === 'bari' && r.year === 2017 && r.ordering === 'no');
  click(w, markers(w).find(m => /Bari 2017/.test(m.getAttribute('aria-label'))));
  const rd = w.document.querySelector('.explorer__readout');
  check(rd.textContent.indexOf(tgt.journal) >= 0 && rd.querySelector('a').getAttribute('href') === 'https://arxiv.org/abs/' + tgt.arxiv,
        `click shows "${tgt.journal}" with its arXiv link`);
  check(/propagated|identical/.test(rd.textContent) === !!tgt.interval_method, 'interval method shown only when present');
  w.document.querySelector('.explorer').dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  check(rd.textContent.indexOf(tgt.journal) < 0, 'Escape clears the selection');

  /* 7. table */
  const tg = w.document.querySelector('.explorer__toggle');
  click(w, tg);
  const trs = w.document.querySelectorAll('.table-scroll table.data tbody tr').length;
  check(trs === markers(w).length && !w.document.querySelector('.table-scroll').hidden, `table lists the ${trs} plotted points`);

  /* 8. other parameter, ordering "any" hollow */
  click(w, btn(w, 'δm² / 1e-5 eV²'));
  check(markers(w).length === data.rows.filter(r => r.parameter === 'dm2' && ['no', 'any'].includes(r.ordering)).length,
        'δm² view draws its rows');

  /* 9. failure */
  w = await boot(() => Promise.reject(new Error('offline')));
  const box = w.document.querySelector('.explorer');
  check(box.textContent === 'The interactive chart could not load its data; the static panels below show the same points.' &&
        box.children.length === 1, 'fetch failure leaves the one fallback sentence');

  console.log(fail.length ? `\n${fail.length} FAILED` : '\nall explorer checks passed');
  process.exit(fail.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
