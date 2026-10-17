/* Banco di prova della lettura della riga libera di Literature search.
 *
 *   node tools/search_bench/bench.js [--seed N] [--n 100] [--fails]
 *
 * Genera N query a caso, con la lettura giusta nota per costruzione: chi sono
 * gli autori, quali le date. Le query mescolano come le scrive davvero un
 * fisico: cognomi del campo maiuscoli, minuscoli, con iniziali o particelle,
 * con o senza "by"; argomenti con parole comuni e composti col trattino;
 * date in piu' forme; ordine libero. Una query e' giusta se gli autori letti
 * sono esattamente quelli attesi (per cognome, maiuscole a parte), le date
 * coincidono e nessun cognome atteso resta nell'argomento.
 *
 * Questo file e' il criterio del loop di miglioramento: NON va modificato dal
 * loop (si migliora search.js, non il banco).
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/search.js'), 'utf8');

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const SEED = parseInt(arg('--seed', String(Date.now() % 1e9)), 10);
const N = parseInt(arg('--n', '100'), 10);
const SHOW = process.argv.includes('--fails');

function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const rnd = mulberry32(SEED);
const pick = a => a[Math.floor(rnd() * a.length)];
const chance = p => rnd() < p;

// Cognomi di chi scrive di neutrini (il cognome e' cio' che si confronta).
const SURNAMES = [
  'Lisi', 'Marrone', 'Capozzi', 'Montanino', 'Palazzo', 'Fogli', 'Melchiorri',
  'Maltoni', 'Schwetz', 'Esteban', 'Forero', 'Tortola', 'Valle', 'Feruglio',
  'Petcov', 'Smirnov', 'Strumia', 'Vissani', 'Lesgourgues', 'Pastor', 'Mena',
  'Hernandez', 'Huber', 'Kopp', 'Yanagida', 'Mohapatra', 'Senjanovic', 'King',
  'Altarelli', 'Bilenky', 'Giunti', 'Gariazzo', 'Mirizzi', 'Raffelt', 'Lunardini',
  'Beacom', 'Denton', 'Parke', 'Kayser', 'Akhmedov', 'Fukugita', 'Gonzalez-Garcia',
  'Di Valentino', 'de Salas', 'Dell\'Oro', 'Agostini', 'Vagnozzi', 'Hagstotz',
];
const INITIALS = 'ABCDEFGHIJKLMNOPRSTVW';

// Argomenti come li scrive un fisico: vocabolario, parole comuni, composti.
const TOPICS = [
  'neutrino mass ordering', 'sterile neutrino dark radiation', 'solar neutrino anomaly',
  'leptonic CP violation', 'theta13 measurement', 'long-baseline accelerator experiments',
  'neutrinoless double beta decay', 'modular flavour symmetry', 'coherent elastic scattering',
  'supernova neutrino bursts', 'nonstandard interactions', 'tritium endpoint spectrum',
  'cosmological neutrino mass bounds', 'geoneutrino flux', 'atmospheric oscillation parameters',
  'quasi-degenerate spectrum', 'Majorana phases', 'seesaw mechanism', 'keV sterile dark matter',
  'matter effects in the Earth', 'medium-baseline reactor', 'pseudo-Dirac neutrinos',
  'flavour ratios of astrophysical neutrinos', 'JUNO sensitivity', 'DUNE and Hyper-Kamiokande',
  'KATRIN upper limit', 'Planck and DESI', 'solar metallicity problem', 'ultralight dark matter',
  'texture zeros', 'radiative neutrino mass models', 'inverse seesaw', 'lepton flavour violation',
  'neutrino magnetic moment', 'decoherence in neutrino oscillations', 'octant of theta23',
  'global fit of oscillation data', 'precise determination of the mixing angles',
  'improved bounds on the absolute mass scale', 'tension between T2K and NOvA',
  'reactor antineutrino anomaly', 'gallium anomaly', 'Daya Bay final results',
  'Borexino CNO neutrinos', 'super kamiokande atmospheric data', 'IceCube high-energy events',
  'Hubble tension and neutrinos', 'big bang nucleosynthesis constraints', 'leptogenesis',
  'non-unitarity of the mixing matrix', 'neutrino decay', 'Lorentz violation',
];
const YEARS = () => 2000 + Math.floor(rnd() * 26);

function dateExpr() {
  const k = Math.floor(rnd() * 6);
  const a = YEARS(), b = Math.min(2026, a + 1 + Math.floor(rnd() * 6));
  switch (k) {
    case 0: return { text: `${a}-${b}`, from: String(a), to: String(b) };
    case 1: return { text: `since ${a}`, from: String(a), to: '' };
    case 2: return { text: `${a} to ${b}`, from: String(a), to: String(b) };
    case 3: return { text: `before ${b}`, from: '', to: String(b) };
    case 4: return { text: `${a}`, from: String(a), to: String(a) };
    default: return { text: `after ${a}`, from: String(a), to: '' };
  }
}

// Come appare un cognome nella query: com'e', minuscolo, con iniziali.
function nameForm(sur, lower) {
  let s = sur;
  if (chance(0.25)) {
    const ini = chance(0.7) ? pick(INITIALS) + '.' : pick(INITIALS) + '.' + pick(INITIALS) + '.';
    s = ini + ' ' + s;
  }
  return lower ? s.toLowerCase() : s;
}

function makeQuery() {
  const lower = chance(0.4);                       // tutto minuscolo
  const nAuth = chance(0.25) ? 0 : (chance(0.75) ? 1 : 2);
  const names = [];
  while (names.length < nAuth) { const s = pick(SURNAMES); if (!names.includes(s)) names.push(s); }
  const forms = names.map(n => nameForm(n, lower));
  let topic = chance(0.85) ? pick(TOPICS) : '';
  if (!topic && !nAuth) topic = pick(TOPICS);
  if (lower) topic = topic.toLowerCase();
  else if (topic && chance(0.3)) topic = topic.charAt(0).toUpperCase() + topic.slice(1); // sentence case
  const date = chance(0.4) ? dateExpr() : null;

  let who = forms.join(chance(0.5) ? ' and ' : ' ');
  if (nAuth && chance(0.25)) who = 'by ' + forms.join(chance(0.5) ? ' and ' : ', ');
  let parts;
  if (!nAuth) parts = [topic];
  else if (!topic) parts = [who];
  else parts = chance(0.55) ? [who, topic] : [topic, who];
  if (date) parts = chance(0.7) ? parts.concat(date.text) : [date.text].concat(parts);
  const q = parts.filter(Boolean).join(' ');
  return { q, authors: names, from: date ? date.from : '', to: date ? date.to : '' };
}

const surnameOf = a => a.toLowerCase().replace(/^(?:[a-z]\.\s*)+/, '').trim();

const HTML = `<!doctype html><body>
<form id="lit-form"><input id="q-free" type="search"><div id="lit-chips"></div>
  <div id="lit-mode"><button type="button" data-mode="precise" aria-pressed="true">P</button>
    <button type="button" data-mode="broad" aria-pressed="false">B</button></div>
  <details id="lit-adv"><input id="q-author"><input id="q-title"><input id="q-topic"><input id="q-collab">
    <select id="adv-time"><option value="any" selected>any</option><option value="custom">c</option></select>
    <input id="q-from"><input id="q-to"><select id="adv-disc"><option value="all" selected>all</option></select>
    <input type="checkbox" id="src-inspire" checked><input type="checkbox" id="src-crossref" checked>
    <input type="checkbox" id="src-openalex" checked><input type="checkbox" id="src-arxiv" checked>
    <input type="checkbox" id="src-s2" checked><button type="button" id="lit-clear">Clear</button></details>
  <button type="submit">Search</button></form><div id="lit-outbound"></div>
<div id="lit-pane"><p id="lit-status"></p><div id="lit-badges" hidden></div><div id="lit-sort" hidden></div>
  <div id="lit-filters" hidden></div><div id="lit-results"></div></div></body>`;

const dom = new JSDOM(HTML, { runScripts: 'outside-only', url: 'https://global-nu.org/search.html' });
const w = dom.window, d = w.document;
w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
w.fetch = () => Promise.reject(new Error('offline'));
w.eval(js);

let ok = 0;
const fails = [];
for (let i = 0; i < N; i++) {
  const g = makeQuery();
  const f = d.getElementById('q-free');
  f.value = g.q;
  f.dispatchEvent(new w.Event('input', { bubbles: true }));
  const v = id => d.getElementById(id).value;
  const got = v('q-author') ? v('q-author').split(/\s*;\s*/).map(surnameOf) : [];
  const want = g.authors.map(surnameOf);
  const topic = v('q-topic').toLowerCase();
  const authorsOk = got.length === want.length && want.every(a => got.includes(a));
  const datesOk = v('q-from') === g.from && v('q-to') === g.to;
  const leak = want.filter(a => new RegExp('(^|\\s)' + a.replace(/[.*+?^${}()|[\]\\']/g, '\\$&') + '(\\s|$)').test(topic));
  if (authorsOk && datesOk && !leak.length) ok++;
  else fails.push(`${JSON.stringify(g.q)}\n      want A=[${want.join('; ')}] ${g.from}->${g.to}` +
                  `   got A=[${got.join('; ')}] ${v('q-from')}->${v('q-to')} T="${v('q-topic')}"`);
}
w.close();
if (SHOW) fails.forEach(x => console.log('  FAIL ' + x));
console.log(`seed=${SEED} n=${N} ok=${ok} rate=${(ok / N).toFixed(2)}`);
