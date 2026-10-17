/* Controllo dal vivo della ricerca bibliografica: NON fa parte della batteria
 * automatica (il nome non comincia per test_). Carica search.js in jsdom con
 * il VERO fetch, interroga le API pubbliche in modalita Precise e stampa i
 * primi 8 titoli per ogni query, con le fonti. Segnala (FLAG) ogni titolo fra
 * i primi 5 che
 *   - contiene un segnale negativo di ENTITIES per un'entita citata nella query
 *     (JUNO/Jupiter, DUNE/sand dune, ...), oppure
 *   - non contiene nessun termine della query in titolo + abstract.
 * Legge soltanto API pubbliche, non scrive nulla.
 *
 *   node tools/search_live_check.js            (node >= 18, jsdom da ./node_modules)
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/search.js'), 'utf8');

const QUERIES = ['JUNO oscillation 2025', 'Lisi Marrone modular symmetry',
                 'T2K last two years', 'neutrinoless double beta decay',
                 '2503.07752', '10.1103/PhysRevD.111.093006'];

const HTML = `<!doctype html><body>
<form id="lit-form"><input id="q-free" type="search"><div id="lit-chips"></div>
<div id="lit-mode"><button type="button" data-mode="precise" aria-pressed="true"></button>
<button type="button" data-mode="broad" aria-pressed="false"></button></div>
<input id="q-author"><input id="q-title"><input id="q-topic"><input id="q-collab">
<select id="adv-time"><option value="any" selected></option></select>
<input id="q-from"><input id="q-to">
<select id="adv-disc"><option value="all" selected></option></select>
<input type="checkbox" id="src-inspire" checked><input type="checkbox" id="src-crossref" checked>
<input type="checkbox" id="src-openalex" checked><input type="checkbox" id="src-arxiv" checked>
<input type="checkbox" id="src-s2" checked>
<button type="submit">Search</button><button type="button" id="lit-clear"></button></form>
<div id="lit-outbound"></div>
<div id="lit-pane"><p id="lit-status"></p><div id="lit-badges" hidden></div>
<div id="lit-sort" hidden></div><div id="lit-filters" hidden></div><div id="lit-results"></div></div></body>`;

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function one(q) {
  const dom = new JSDOM(HTML, { runScripts: 'outside-only', url: 'https://global-nu.org/search.html' });
  const w = dom.window, d = w.document;
  w.matchMedia = () => ({ matches: false });
  w.Element.prototype.scrollIntoView = function () {};
  // jsdom's AbortSignal is not undici's: the page's own 20 s timeout is
  // replaced by one here.
  w.fetch = (url) => fetch(url, { signal: AbortSignal.timeout(25000),
                                  headers: { 'User-Agent': 'global-nu-live-check' } });
  let api = null;
  w.__LIT_EXPOSE__ = a => { api = a; };
  w.eval(js);
  d.getElementById('q-free').value = q;
  d.getElementById('lit-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  const t0 = Date.now();
  await sleep(500);
  while ((api.pending().length || /Querying/.test(d.getElementById('lit-status').textContent)) &&
         Date.now() - t0 < 90000) await sleep(500);
  await sleep(1500);                      // the citation lookup, then the last redraw

  const f = {
    topic: d.getElementById('q-topic').value, title: d.getElementById('q-title').value,
    collab: d.getElementById('q-collab').value
  };
  const terms = api.gateTerms(f);
  const ents = Object.keys(api.ENTITIES).filter(k => api.ENTITY_RE[k].name.test(
    [f.topic, f.title, f.collab].join(' ')));
  const byTitle = {};
  api.rows().forEach(r => { byTitle[r.title] = r; });
  const items = Array.from(d.querySelectorAll('#lit-results li')).map(li => ({
    title: li.querySelector('.pub__title').textContent,
    sources: Array.from(li.querySelectorAll('.src')).map(s => s.textContent).join(', ')
  }));

  console.log('\n=== ' + q + '   [Precise]');
  console.log('    chips: ' + d.getElementById('lit-chips').textContent.replace(/\s+/g, ' ').trim());
  console.log('    ' + d.getElementById('lit-status').textContent);
  const bad = Array.from(d.querySelectorAll('#lit-badges .lit-badge')).map(b =>
    b.textContent + (b.title ? ' (' + b.title + ')' : ''));
  if (bad.length) console.log('    badges: ' + bad.join(' | '));
  let flags = 0;
  items.slice(0, 8).forEach((it, i) => {
    const r = byTitle[it.title] || {};
    const text = it.title + ' ' + (r.abstract || '') + ' ' + (r.keywords || []).join(' ');
    const norm = ' ' + api.normTitle(text) + ' ';
    const why = [];
    if (i < 5) {
      ents.forEach(k => api.ENTITY_RE[k].neg.forEach(re => {
        if (re.test(text)) why.push('negative cue ' + re.source.slice(0, 30) + ' for ' + k);
      }));
      if (terms.length && !terms.some(t => norm.indexOf(' ' + api.stemOf(t)) > -1)) {
        why.push('no query term in title+abstract');
      }
    }
    if (why.length) flags++;
    console.log('  ' + (i + 1) + '. ' + it.title.slice(0, 110) + '  [' + it.sources + ']' +
                (why.length ? '   FLAG: ' + why.join('; ') : ''));
  });
  if (!items.length) console.log('  (no results)');
  w.close();
  return flags;
}

(async () => {
  let flags = 0;
  for (const q of QUERIES) flags += await one(q);
  console.log('\n' + flags + ' flagged result(s) in the top 5 of ' + QUERIES.length + ' queries.');
  process.exit(0);
})().catch(e => { console.log(e.stack); process.exit(1); });
