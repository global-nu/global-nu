/* Collaudo della modalita' Precise / Broad, delle entita' ambigue e della resa
 * progressiva della pagina Literature search (site-src/assets/js/search.js).
 *
 * Stesso metodo di test_search_sort.js: la pagina e' costruita in jsdom con gli
 * id di site-src/content/search.md, le API sono sostituite da risposte finte
 * con la forma dei payload reali (INSPIRE: abstracts/keywords/collaborations;
 * OpenAlex: abstract_inverted_index, keywords, topics; Crossref: abstract in
 * JATS; Semantic Scholar: abstract; DataCite: descriptions), e si preme sui
 * pulsanti veri. Ogni scenario ha una pagina nuova.
 *
 *   node tools/tests/test_search_precise.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/search.js'), 'utf8');
const md = fs.readFileSync(path.join(ROOT, 'site-src/content/search.md'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };
const check = (cond, what, extra) => cond ? ok(what) : bad(what + (extra ? ' — ' + extra : ''));

const IDS = ['lit-form', 'q-free', 'q-author', 'q-title', 'q-topic', 'q-collab',
             'q-from', 'q-to', 'lit-chips', 'lit-status', 'lit-results',
             'lit-outbound', 'lit-sort', 'lit-filters', 'lit-pane', 'lit-clear',
             'lit-badges', 'lit-mode', 'lit-adv', 'adv-time', 'adv-disc',
             'src-inspire', 'src-crossref', 'src-openalex', 'src-arxiv', 'src-s2'];
const missing = IDS.filter(id => md.indexOf('id="' + id + '"') === -1 && md.indexOf('#' + id) === -1);
check(!missing.length, 'gli id usati dal test esistono in search.md', missing.join(', '));
check(/<details id="lit-adv"[^>]*>/.test(md) && !/<details id="lit-adv"[^>]*\bopen\b/.test(md),
      'Advanced options e un <details> chiuso di default');
check(/data-mode="precise" aria-pressed="true"/.test(md) &&
      /data-mode="broad" aria-pressed="false"/.test(md),
      'Precise e attivo di default (aria-pressed)');
check(md.indexOf('<link rel="stylesheet" href="assets/css/search.css">') > -1 &&
      fs.existsSync(path.join(ROOT, 'site-src/assets/css/search.css')),
      'search.css esiste ed e collegato da search.md');

const HTML = `<!doctype html><body>
<form id="lit-form">
  <input id="q-free" type="search">
  <div id="lit-chips"></div>
  <div id="lit-mode"><button type="button" data-mode="precise" aria-pressed="true">Precise</button>
    <button type="button" data-mode="broad" aria-pressed="false">Broad</button></div>
  <details id="lit-adv">
    <input id="q-author" type="text"><input id="q-title" type="text">
    <input id="q-topic" type="text"><input id="q-collab" type="text">
    <select id="adv-time"><option value="any" selected>any</option><option value="1">1</option>
      <option value="2">2</option><option value="5">5</option><option value="custom">c</option></select>
    <input id="q-from" type="text"><input id="q-to" type="text">
    <select id="adv-disc"><option value="all" selected>all</option><option value="neutrino">nu</option></select>
    <input type="checkbox" id="src-inspire" checked>
    <input type="checkbox" id="src-crossref" checked>
    <input type="checkbox" id="src-openalex" checked>
    <input type="checkbox" id="src-arxiv" checked>
    <input type="checkbox" id="src-s2" checked>
    <button type="button" id="lit-clear">Clear</button>
  </details>
  <button type="submit">Search</button>
</form>
<div id="lit-outbound"></div>
<div id="lit-pane">
  <p id="lit-status"></p><div id="lit-badges" hidden></div>
  <div id="lit-sort" hidden></div><div id="lit-filters" hidden></div>
  <div id="lit-results"></div>
</div></body>`;

/* ---------------------------------------------------------- payload finti --- */
const ins = o => ({ metadata: {
  control_number: o.id, earliest_date: o.date, citation_count: o.cites || 0,
  titles: [{ title: o.title }],
  authors: (o.authors || ['Rossi, Mario']).map(n => ({ full_name: n })),
  abstracts: o.abs ? [{ value: o.abs, source: 'arXiv' }] : undefined,
  keywords: (o.kw || []).map(v => ({ schema: 'INSPIRE', value: v })),
  collaborations: (o.collabs || []).map(v => ({ value: v })),
  arxiv_eprints: [{ value: o.arx || ('2501.' + String(10000 + o.id)), categories: o.cats || ['hep-ph'] }],
  inspire_categories: [{ term: 'Phenomenology-HEP' }],
  publication_info: [{ year: parseInt(o.date, 10) }],
  dois: [{ value: o.doi || ('10.1/' + o.id) }] } });
const inspireBody = hits => ({ hits: { hits: hits } });

const invert = text => {
  const ix = {};
  text.split(/\s+/).forEach((wd, i) => { (ix[wd] = ix[wd] || []).push(i); });
  return ix;
};
const oa = o => ({
  id: 'W' + o.id, title: o.title, publication_date: o.date,
  publication_year: parseInt(o.date, 10), cited_by_count: 5,
  authorships: [{ author: { display_name: 'A Author' } }],
  primary_location: { source: { display_name: o.venue || 'Some Journal' } },
  primary_topic: { display_name: o.topic || 'Particle physics', subfield: { display_name: 'Physics' } },
  abstract_inverted_index: o.abs ? invert(o.abs) : null,
  keywords: (o.kw || []).map(k => ({ display_name: k })),
  topics: [], doi: 'https://doi.org/' + (o.doi || '10.3/' + o.id) });
const cr = o => ({ DOI: o.doi || '10.2/' + o.id, title: [o.title],
  author: [{ given: 'B', family: 'Author' }],
  issued: { 'date-parts': [[parseInt(o.date, 10), 3, 1]] },
  'container-title': [o.venue || 'Some Journal'],
  abstract: o.abs ? '<jats:p>' + o.abs + '</jats:p>' : undefined });
const s2 = o => ({ paperId: 'S' + o.id, title: o.title, authors: [{ name: 'C Author' }],
  year: parseInt(o.date, 10), publicationDate: o.date, venue: o.venue || '',
  citationCount: 1, externalIds: { DOI: o.doi || '10.4/' + o.id },
  abstract: o.abs, s2FieldsOfStudy: [{ category: 'Physics' }] });

/* ------------------------------------------------------------- l'ambiente --- */
/* handler(source, url) -> body | { delay, body } | { reject: 'msg' } | undefined.
 * `source` e' inspire | cites | crossref | openalex | datacite | s2. */
function newEnv(handler) {
  const dom = new JSDOM(HTML, { runScripts: 'outside-only', url: 'https://global-nu.org/search.html' });
  const w = dom.window, d = w.document;
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.Element.prototype.scrollIntoView = function () {};
  const calls = [];
  w.fetch = function (url) {
    const u = String(url);
    calls.push(u);
    const src = u.indexOf('fields=citation_count') > -1 ? 'cites'
      : u.indexOf('inspirehep.net') > -1 ? 'inspire'
      : u.indexOf('api.crossref.org') > -1 ? 'crossref'
      : u.indexOf('api.openalex.org') > -1 ? 'openalex'
      : u.indexOf('api.datacite.org') > -1 ? 'datacite'
      : u.indexOf('semanticscholar.org') > -1 ? 's2' : null;
    let r = src ? handler(src, u) : undefined;
    if (r === undefined) {
      r = src === 'inspire' || src === 'cites' ? inspireBody([])
        : src === 'crossref' ? { message: { items: [] } }
        : src === 'openalex' ? { results: [] }
        : src === 'datacite' || src === 's2' ? { data: [] } : undefined;
    }
    if (r === undefined) return Promise.reject(new Error('unexpected URL ' + u));
    const go = () => {
      if (r && r.reject) return Promise.reject(new Error(r.reject));
      const body = r && r.__body !== undefined ? r.__body : r;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    };
    return r && r.delay ? new Promise(res => setTimeout(res, r.delay)).then(go) : go();
  };
  const errors = [];
  w.addEventListener('error', e => errors.push(String(e.error || e.message)));
  try { w.eval(js); } catch (e) { errors.push('THROW: ' + e.message); }
  return {
    w, d, calls, errors,
    titles: () => Array.from(d.querySelectorAll('#lit-results li .pub__title')).map(a => a.textContent),
    badges: () => Array.from(d.querySelectorAll('#lit-badges .lit-badge')),
    click: el => el.dispatchEvent(new w.Event('click', { bubbles: true })),
    async search(q, wait) {
      d.getElementById('q-free').value = q;
      d.getElementById('q-free').dispatchEvent(new w.Event('input', { bubbles: true }));
      d.getElementById('lit-form')
       .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
      await sleep(wait === undefined ? 80 : wait);
    },
    async close() { await sleep(60); w.close(); }
  };
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const has = (list, t) => list.indexOf(t) > -1;
const Y = new Date().getFullYear();

async function main() {
  /* (i) JUNO: la sonda NASA con la stessa parola ------------------------- */
  console.log('\n--- (i) JUNO oscillation 2025 ---');
  const JUNO_T = 'Sensitivity of JUNO to neutrino oscillation parameters with reactor antineutrinos';
  const NASA_OA = 'Juno measurements of oscillation modes in the Jovian magnetosphere';
  const NASA_CR = 'Oscillation of the Juno spacecraft spin during Jupiter orbit insertion';
  const NASA_S2 = 'Magnetospheric oscillation seen by Juno at Jupiter';
  const juno = ins({ id: 1, date: '2025-02-10', title: JUNO_T, cites: 12, collabs: ['JUNO'],
                     authors: ['Wang, Li'], cats: ['hep-ex'],
                     abs: 'JUNO is a 20 kton liquid scintillator detector in Jiangmen measuring reactor antineutrino oscillation.' });
  let e = newEnv((src) => {
    if (src === 'inspire') return inspireBody([juno]);
    if (src === 'openalex') return { results: [
      oa({ id: 1, date: '2025-04-01', title: NASA_OA, venue: 'JGR Space Physics',
           abs: 'Juno spacecraft magnetometer data show Jupiter magnetosphere oscillation near the Jovian dynamo.' }),
      oa({ id: 2, date: '2025-02-10', title: JUNO_T, doi: '10.1/1',
           abs: 'JUNO is a liquid scintillator detector in Jiangmen measuring reactor antineutrino oscillation.' })] };
    if (src === 'crossref') return { message: { items: [
      cr({ id: 3, date: '2025-05-01', title: NASA_CR, venue: 'Space Science Reviews',
           abs: 'Spacecraft telemetry from NASA Juno during Jupiter orbit insertion shows spin oscillation.' })] } };
    if (src === 's2') return { data: [
      s2({ id: 4, date: '2025-06-01', title: NASA_S2, venue: 'Icarus',
           abs: 'Juno crosses the Jovian magnetosphere where oscillation of the current sheet is observed.' })] };
  });
  await e.search('JUNO oscillation 2025');
  let t = e.titles();
  check(!e.errors.length, 'nessun errore a caricamento', e.errors.join('|'));
  check(!has(t, NASA_OA) && !has(t, NASA_CR) && !has(t, NASA_S2),
        'Precise: le tre carte NASA (OpenAlex, Crossref, S2) sono scartate', JSON.stringify(t));
  check(has(t, JUNO_T), 'Precise: la carta JUNO sui neutrini da reattore resta');
  check(t[0] === JUNO_T, 'Precise: la carta JUNO e prima', t[0]);
  check(/off-topic/.test(e.d.getElementById('lit-status').textContent),
        'la riga di stato conta i record scartati');
  const before = e.calls.length;
  e.click(e.d.querySelector('[data-mode="broad"]'));
  t = e.titles();
  check(e.d.querySelector('[data-mode="broad"]').getAttribute('aria-pressed') === 'true' &&
        e.d.querySelector('[data-mode="precise"]').getAttribute('aria-pressed') === 'false',
        'il pulsante Broad passa ad aria-pressed=true');
  check(has(t, NASA_OA) && has(t, NASA_CR) && has(t, NASA_S2) && has(t, JUNO_T),
        'Broad: le carte NASA tornano (titolo con tutte le parole, o fisica "nativa")', JSON.stringify(t));
  check(e.calls.filter(u => u.indexOf('fields=citation_count') === -1).length === before ||
        e.calls.length - before <= 1,
        'cambiare modalita non richiede di nuovo i database (al piu il lookup dei conteggi)');
  e.click(e.d.querySelector('[data-mode="precise"]'));
  check(!has(e.titles(), NASA_S2) && e.titles()[0] === JUNO_T, 'e si torna a Precise senza ricercare');
  await e.close();

  /* (ii) Lisi Marrone modular symmetry ----------------------------------- */
  console.log('\n--- (ii) Lisi Marrone modular symmetry ---');
  const PLAIN = 'Global analysis of three-neutrino oscillations after the 2024 data';
  const MOD = 'Neutrino masses from modular invariance';
  e = newEnv((src) => src === 'inspire' ? inspireBody([
    ins({ id: 10, date: '2024-03-03', title: PLAIN, authors: ['Lisi, Eligio', 'Marrone, Antonio'],
          abs: 'We update the oscillation fit with reactor and accelerator data.' }),
    ins({ id: 11, date: '2024-04-04', title: MOD, authors: ['Lisi, Eligio', 'Marrone, Antonio'],
          abs: 'A modular symmetry of level 3 fixes the neutrino mass matrix.' })]) : undefined);
  await e.search('Lisi Marrone modular symmetry');
  t = e.titles();
  check(!has(t, PLAIN) && has(t, MOD),
        'Precise: senza "modular" (ne "symmetry") da nessuna parte il lavoro Lisi-Marrone cade', JSON.stringify(t));
  e.click(e.d.querySelector('[data-mode="broad"]'));
  check(has(e.titles(), PLAIN), 'Broad: lo stesso lavoro resta (INSPIRE e fisica nativa)');
  await e.close();

  /* (iii) T2K last two years --------------------------------------------- */
  console.log('\n--- (iii) T2K last two years ---');
  const expFrom = (() => { const x = new Date(); x.setFullYear(x.getFullYear() - 2);
                           return x.toISOString().slice(0, 10); })();
  const NEW_T2K = 'T2K measurement of neutrino oscillation with a joint fit';
  const OLD_T2K = 'T2K first results on neutrino oscillation from muon neutrino disappearance';
  const t2kHits = [
    ins({ id: 20, date: (Y - 1) + '-05-05', title: NEW_T2K, collabs: ['T2K'], cats: ['hep-ex'],
          abs: 'T2K is a long-baseline accelerator neutrino experiment from Tokai to Kamioka.' }),
    ins({ id: 21, date: (Y - 7) + '-06-06', title: OLD_T2K, collabs: ['T2K'], cats: ['hep-ex'],
          abs: 'T2K reports muon neutrino disappearance in the Tokai to Kamioka beam.' })];
  e = newEnv((src, u) => {
    if (src !== 'inspire') return undefined;
    // il finto INSPIRE rispetta `de > ANNO`, come fa quello vero
    const q = new URL(u).searchParams.get('q');
    const m = /de > (\d{4})/.exec(q);
    return inspireBody(t2kHits.filter(h => !m || parseInt(h.metadata.earliest_date, 10) >= parseInt(m[1], 10)));
  });
  await e.search('T2K last two years');
  t = e.titles();
  check(e.d.getElementById('q-from').value === expFrom && e.d.getElementById('q-to').value === '',
        'last two years -> From = ' + expFrom, e.d.getElementById('q-from').value);
  const inspireQ = e.calls.filter(u => u.indexOf('inspirehep') > -1 && u.indexOf('fields=citation_count') === -1)[0];
  check(inspireQ && new URL(inspireQ).searchParams.get('q').indexOf('de > ' + (Y - 2)) > -1,
        'INSPIRE riceve de > ' + (Y - 2), inspireQ && new URL(inspireQ).searchParams.get('q'));
  check(e.calls.some(u => u.indexOf('openalex') > -1 && decodeURIComponent(u).indexOf('from_publication_date:' + expFrom) > -1),
        'OpenAlex riceve from_publication_date=' + expFrom);
  check(has(t, NEW_T2K) && !has(t, OLD_T2K), 'il T2K vecchio e escluso, quello recente resta', JSON.stringify(t));
  await e.close();

  /* (iv) neutrinoless double beta decay: parole sparse nel titolo -------- */
  console.log('\n--- (iv) neutrinoless double beta decay ---');
  const SPARSE = 'Rare double charged lepton decay searches in xenon detectors';
  const WRONG = 'Double decay of excited states in a toy model';
  e = newEnv((src) => src === 'inspire' ? inspireBody([
    ins({ id: 30, date: '2024-01-01', title: SPARSE, cats: ['hep-ex'],
          abs: 'We search for neutrinoless double beta processes with a xenon time projection chamber.' }),
    ins({ id: 31, date: '2024-01-02', title: WRONG, cats: ['hep-th'],
          abs: 'Excited states of a toy model are studied.' })]) : undefined);
  await e.search('neutrinoless double beta decay');
  t = e.titles();
  check(has(t, SPARSE), 'Precise: "neutrinoless double beta" nell-abstract basta, con solo double e decay nel titolo', JSON.stringify(t));
  check(!has(t, WRONG), 'Precise: con solo double e decay in tutto il testo cade (2 di 4)');
  await e.close();

  /* (v) identificatori: mai filtrati ------------------------------------- */
  console.log('\n--- (v) arXiv id e DOI ---');
  const ODD = 'A record that shares no word with the query';
  const idHit = ins({ id: 40, date: '2025-03-10', title: ODD, arx: '2503.07752', doi: '10.1103/PhysRevD.111.093006',
                      abs: 'Nothing relevant here.' });
  for (const q of ['2503.07752', '2503.07752 neutrino mixing', '10.1103/PhysRevD.111.093006',
                   '10.1103/PhysRevD.111.093006 neutrino mixing']) {
    e = newEnv((src) => src === 'inspire' ? inspireBody([idHit]) : undefined);
    await e.search(q);
    check(has(e.titles(), ODD), 'Precise non filtra "' + q + '"', JSON.stringify(e.titles()));
    await e.close();
  }

  /* (vi) un database che fallisce non blocca gli altri ------------------- */
  console.log('\n--- (vi) fonte che fallisce ---');
  e = newEnv((src) => src === 'inspire' ? inspireBody([
    ins({ id: 50, date: '2024-01-01', title: 'Neutrino masses and mixing in a nutshell', authors: ['Lisi, Eligio'] })])
    : src === 's2' ? { reject: 'HTTP 429' } : undefined);
  await e.search('Lisi Marrone');
  const bs = e.badges();
  const fb = bs.filter(b => /Semantic Scholar temporarily unavailable/.test(b.textContent))[0];
  check(!!fb, 'compare il badge "Semantic Scholar temporarily unavailable"', bs.map(b => b.textContent).join(' | '));
  check(fb && fb.getAttribute('role') === 'status', 'il badge ha role="status"');
  check(fb && /429/.test(fb.getAttribute('title') || ''), 'l-errore tecnico sta nel title', fb && fb.getAttribute('title'));
  check(has(e.titles(), 'Neutrino masses and mixing in a nutshell'), 'i risultati delle altre fonti sono sulla pagina');
  check(!/Semantic Scholar unavailable/.test(e.d.getElementById('lit-results').textContent),
        'nessun messaggio bloccante nei risultati');
  check(!bs.some(b => /…/.test(b.textContent)), 'nessun badge "in attesa" resta a fine ricerca');
  await e.close();

  /* (vii) risultati prima che la fonte piu lenta risponda ---------------- */
  console.log('\n--- (vii) resa progressiva ---');
  e = newEnv((src) => src === 'inspire' ? { delay: 400, __body: inspireBody([
      ins({ id: 60, date: '2024-01-01', title: 'Slow INSPIRE paper on neutrino mixing', authors: ['Lisi, Eligio'] })]) }
    : src === 'openalex' ? { results: [oa({ id: 61, date: '2024-02-02',
        title: 'Fast OpenAlex paper on neutrino mixing', abs: 'neutrino mixing' })] }
    : undefined);
  await e.search('neutrino mixing', 120);
  check(has(e.titles(), 'Fast OpenAlex paper on neutrino mixing'), 'il risultato veloce e gia visibile');
  check(e.badges().some(b => /^INSPIRE-HEP …/.test(b.textContent)) && !has(e.titles(), 'Slow INSPIRE paper on neutrino mixing'),
        'INSPIRE-HEP mostra il badge "in attesa", i suoi record non ci sono ancora');
  check(/1 paper from \d+ databases?/.test(e.d.getElementById('lit-status').textContent) &&
        /still waiting for INSPIRE-HEP/.test(e.d.getElementById('lit-status').textContent),
        'la riga di stato conta gia i risultati', e.d.getElementById('lit-status').textContent);
  // l'ordinamento scelto durante l'attesa sopravvive alla ridisegnatura
  e.click(e.d.querySelector('#lit-sort [data-sort="date"]'));
  await sleep(450);
  check(has(e.titles(), 'Slow INSPIRE paper on neutrino mixing') && e.badges().length === 0,
        'dopo l-arrivo di INSPIRE il badge sparisce e il record compare');
  check(e.d.querySelector('#lit-sort [data-sort="date"]').getAttribute('aria-pressed') === 'true',
        'l-ordinamento scelto nel frattempo e rimasto');
  await e.close();

  /* (viii) DUNE: la duna di sabbia --------------------------------------- */
  console.log('\n--- (viii) DUNE ---');
  const SAND = 'Oscillation of dune crests under aeolian transport';
  const DUNE = 'DUNE far detector oscillation sensitivity with liquid argon';
  e = newEnv((src) => src === 'openalex' ? { results: [
    oa({ id: 70, date: '2024-01-01', title: SAND, abs: 'Sand dune migration in desert wind fields.' }),
    oa({ id: 71, date: '2024-01-02', title: DUNE, abs: 'DUNE will measure neutrino oscillation with a liquid argon far detector.' })] }
    : undefined);
  await e.search('DUNE oscillation');
  check(has(e.titles(), DUNE) && !has(e.titles(), SAND), 'Precise: la duna di sabbia cade, DUNE resta', JSON.stringify(e.titles()));
  await e.close();

  /* (ix) disciplina e tempo ---------------------------------------------- */
  console.log('\n--- (ix) filtri avanzati ---');
  e = newEnv((src) => src === 'inspire' ? inspireBody([
    ins({ id: 80, date: '2024-01-01', title: 'Neutrino masses in seesaw models' }),
    ins({ id: 81, date: '2024-01-02', title: 'Higgs couplings at the collider', cats: ['hep-ex'] }),
    ins({ id: 82, date: '2024-01-03', title: 'Sensitivity of JUNO to the mass ordering', cats: ['hep-ex'],
          abs: 'We study the reactor antineutrino spectrum measured with the liquid scintillator.' }),
    ins({ id: 83, date: '2024-01-04', title: 'Dark matter direct detection near the floor', cats: ['hep-ex'],
          abs: 'The neutrino floor limits the reach of xenon detectors.' })]) : undefined);
  await e.search('Rossi');
  check(e.titles().length === 4, 'tutta la fisica: quattro record');
  e.d.getElementById('adv-disc').value = 'neutrino';
  e.d.getElementById('adv-disc').dispatchEvent(new e.w.Event('change', { bubbles: true }));
  check(e.titles().length === 2 && e.titles().some(t => /JUNO/.test(t)) && !e.titles().some(t => /Dark matter/.test(t)),
        'disciplina "neutrino physics": JUNO nel titolo confermato dall\'abstract entra, il "neutrino floor" no', JSON.stringify(e.titles()));
  e.d.getElementById('adv-disc').value = 'all';
  e.d.getElementById('adv-disc').dispatchEvent(new e.w.Event('change', { bubbles: true }));
  e.d.getElementById('adv-time').value = '5';
  e.d.getElementById('adv-time').dispatchEvent(new e.w.Event('change', { bubbles: true }));
  const f5 = new Date(); f5.setFullYear(f5.getFullYear() - 5);
  check(e.d.getElementById('q-from').value === f5.toISOString().slice(0, 10), 'Published: last 5 years scrive in From');
  await e.close();

  console.log('');
  if (fail.length) { console.log('FALLITI ' + fail.length + ' CONTROLLI'); process.exit(1); }
  console.log('TUTTI I CONTROLLI SUPERATI');
  process.exit(0);
}

main().catch(err => { console.log('  FAIL eccezione: ' + err.stack); process.exit(1); });
