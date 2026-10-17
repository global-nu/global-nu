/* Collaudo della lettura della riga libera (parseFree) nella pagina
 * Literature search: chi e' un autore e chi no.
 *
 * Un autore e' solo cio' che la query dichiara tale: a:X / author:X / "by X",
 * iniziali o particella + cognome maiuscolo ("E. Lisi", "A.M. Marrone"), o due
 * parole maiuscole in una query corta, o un cognome maiuscolo in una query
 * altrimenti minuscola ("Marrone constraints on ..."). Minuscole, composti con trattino e
 * nomi comuni ("determination") sono argomenti. Le chip mostrano la lettura.
 *
 *   node tools/tests/test_search_parse.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/search.js'), 'utf8');

const fail = [];
const check = (cond, what, extra) => {
  if (cond) console.log('  ok   ' + what);
  else { fail.push(what); console.log('  FAIL ' + what + (extra ? ' — ' + extra : '')); }
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

const HTML = `<!doctype html><body>
<form id="lit-form">
  <input id="q-free" type="search"><div id="lit-chips"></div>
  <div id="lit-mode"><button type="button" data-mode="precise" aria-pressed="true">P</button>
    <button type="button" data-mode="broad" aria-pressed="false">B</button></div>
  <details id="lit-adv">
    <input id="q-author" type="text"><input id="q-title" type="text">
    <input id="q-topic" type="text"><input id="q-collab" type="text">
    <select id="adv-time"><option value="any" selected>any</option><option value="custom">c</option></select>
    <input id="q-from" type="text"><input id="q-to" type="text">
    <select id="adv-disc"><option value="all" selected>all</option></select>
    <input type="checkbox" id="src-inspire" checked><input type="checkbox" id="src-crossref" checked>
    <input type="checkbox" id="src-openalex" checked><input type="checkbox" id="src-arxiv" checked>
    <input type="checkbox" id="src-s2" checked><button type="button" id="lit-clear">Clear</button>
  </details>
  <button type="submit">Search</button>
</form>
<div id="lit-outbound"></div>
<div id="lit-pane"><p id="lit-status"></p><div id="lit-badges" hidden></div>
  <div id="lit-sort" hidden></div><div id="lit-filters" hidden></div><div id="lit-results"></div></div></body>`;

async function read(q) {
  const dom = new JSDOM(HTML, { runScripts: 'outside-only', url: 'https://global-nu.org/search.html' });
  const w = dom.window, d = w.document;
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = () => Promise.reject(new Error('offline'));
  w.eval(js);
  const f = d.getElementById('q-free');
  f.value = q;
  f.dispatchEvent(new w.Event('input', { bubbles: true }));
  await sleep(400);                         // the page may debounce the parse
  const v = id => d.getElementById(id).value;
  const r = { author: v('q-author'), topic: v('q-topic'), from: v('q-from'), to: v('q-to'),
              chips: d.getElementById('lit-chips').textContent };
  w.close();
  return r;
}

(async () => {
  console.log('--- la query della revisione ---');
  let r = await read('neutrino mass ordering determination with long-baseline accelerator ' +
                     'and medium-baseline reactor experiments 2019-2026');
  check(r.author === '', 'nessun autore', 'autori: "' + r.author + '"');
  check(/long-baseline/.test(r.topic) && /medium-baseline/.test(r.topic) &&
        /determination/.test(r.topic), 'long-baseline, medium-baseline, determination sono argomenti', r.topic);
  check(r.from === '2019' && r.to === '2026', 'date 2019 -> 2026', r.from + ' -> ' + r.to);
  check(!/Author/.test(r.chips) && /Dates/.test(r.chips), 'le chip non mostrano Author e mostrano Dates', r.chips);

  console.log('--- autori dichiarati ---');
  r = await read('by Lisi neutrino mass');
  check(r.author === 'Lisi' && /neutrino/.test(r.topic) && /mass/.test(r.topic) && !/Lisi/.test(r.topic),
        '"by Lisi neutrino mass"', r.author + ' | ' + r.topic);
  r = await read('by Marrone and Lisi solar neutrinos');
  check(r.author === 'Marrone; Lisi' && /solar/.test(r.topic), '"by Marrone and Lisi ..."', r.author + ' | ' + r.topic);
  r = await read('by Marrone, Lisi');
  check(r.author === 'Marrone; Lisi', '"by Marrone, Lisi"', r.author);
  r = await read('author:Marrone');
  check(r.author === 'Marrone', 'author:Marrone', r.author);
  r = await read('a:Smith dark matter');
  check(r.author === 'Smith' && /dark/.test(r.topic), 'a:Smith', r.author + ' | ' + r.topic);

  console.log('--- forme nome-cognome ---');
  r = await read('E. Lisi solar neutrinos');
  check(r.author === 'E. Lisi' && /solar/.test(r.topic), '"E. Lisi solar neutrinos"', r.author + ' | ' + r.topic);
  r = await read('A.M. Marrone reactor');
  check(r.author === 'A.M. Marrone', '"A.M. Marrone"', r.author);
  r = await read('Lisi Marrone');
  check(r.author === 'Lisi; Marrone', '"Lisi Marrone": due cognomi maiuscoli, query corta', r.author);
  r = await read('Lisi Marrone 2019-2019');
  check(r.author === 'Lisi; Marrone' && r.from === '2019' && r.to === '2019', '"Lisi Marrone 2019-2019"', r.author);

  r = await read('Feruglio modular forms');
  check(r.author === 'Feruglio' && /modular/.test(r.topic), '"Feruglio modular forms"', r.author + ' | ' + r.topic);

  console.log('--- cognome maiuscolo in una query altrimenti minuscola ---');
  for (const [q, want] of [['Marrone solar neutrinos', 'Marrone'],
                           ['Marrone constraints on neutrino masses from cosmology and oscillations', 'Marrone'],
                           ['neutrino mass ordering with JUNO and Capozzi', 'Capozzi'],
                           ['global fit of oscillation data Lisi Marrone 2020-2024', 'Lisi; Marrone'],
                           ['Lisi Marrone neutrino oscillation global fit 2020-2024', 'Lisi; Marrone']]) {
    r = await read(q);
    check(r.author === want, '"' + q + '" -> ' + want, 'autori: "' + r.author + '"');
  }

  console.log('--- cognomi scritti in minuscolo ---');
  for (const [q, want] of [['marrone solar neutrinos', 'Marrone'], ['e. lisi reactor', 'E. Lisi'],
                           ['a.m. marrone solar', 'A.M. Marrone'], ['lisi marrone', 'Lisi; Marrone'],
                           ['feruglio modular forms', 'Feruglio'], ['lisi marrone juno', 'Lisi; Marrone'],
                           ['marrone constraints on neutrino masses from cosmology', 'Marrone']]) {
    r = await read(q);
    check(r.author === want, '"' + q + '" -> ' + want, 'autori: "' + r.author + '"');
  }
  for (const q of ['sterile neutrino dark radiation', 'neutrino mass from cosmological data',
                   'solar neutrino results from borexino and super kamiokande', 'precise reactor results']) {
    r = await read(q);
    check(r.author === '', '"' + q + '" senza autori', 'autori: "' + r.author + '"');
  }

  console.log('--- cio\' che non e\' un autore ---');
  for (const q of ['a determination of theta13 with long-baseline data',
                   'Determination of the mass ordering', 'double-beta decay measurement analysis',
                   'Measurement Analysis', 'Long-Baseline Reactor',
                   'Precise determination of neutrino mixing', 'New physics in reactor experiments',
                   'Neutrino Mass Ordering With Medium Baseline Reactors',
                   'Sterile neutrino searches at short baseline', 'Recent results from JUNO']) {
    r = await read(q);
    check(r.author === '', '"' + q + '" senza autori', 'autori: "' + r.author + '"');
  }
  r = await read('Marrone 2018');
  check(r.author === 'Marrone' && r.from === '2018' && r.to === '2018', '"Marrone 2018": non e\' marzo 2018', r.author + ' ' + r.from + '->' + r.to);
  r = await read('neutrino decay 2005');
  check(r.from === '2005' && r.to === '2005' && /decay/.test(r.topic), '"decay 2005": non e\' dicembre', r.from + '->' + r.to + ' ' + r.topic);
  r = await read('T2K NOvA 2025');
  check(r.from === '2025' && r.to === '2025', '"NOvA 2025": non e\' novembre', r.from + '->' + r.to);
  r = await read('reactor neutrinos march 2020');
  check(r.from === '2020-03', '"march 2020" e\' ancora un mese', r.from);
  r = await read('sept. 2019 solar');
  check(r.from === '2019-09', '"sept. 2019"', r.from);
  r = await read('last two years neutrino');
  check(r.author === '' && r.from !== '', 'date relative ancora lette', r.from);

  console.log(fail.length ? '\nFALLITI: ' + fail.length : '\nTUTTI I CONTROLLI SUPERATI');
  process.exit(fail.length ? 1 : 0);
})();
