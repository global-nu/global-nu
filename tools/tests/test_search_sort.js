/* Collaudo dei controlli di ordinamento della pagina Literature search
 * (site-src/assets/js/search.js).
 *
 * Non un controllo di sintassi: la pagina viene costruita in jsdom con gli
 * stessi id di site-src/content/search.md, le cinque API vengono sostituite da
 * risposte finte con la forma REALE dei loro payload (i campi delle categorie
 * sono quelli verificati sulle API vive: arxiv_eprints[].categories e
 * inspire_categories in INSPIRE, subjects con subjectScheme "arXiv" in
 * DataCite, primary_topic in OpenAlex, s2FieldsOfStudy in Semantic Scholar),
 * e poi si preme davvero sui pulsanti.
 *
 * Quello che questo file difende, in ordine di importanza:
 *   - un record senza la chiave di ordinamento (nessuna data, nessun conteggio
 *     di citazioni) finisce IN FONDO in tutte e due le direzioni. Farlo
 *     galleggiare in cima all'ordinamento crescente sarebbe un bug travestito
 *     da ordine;
 *   - una sola chiave per il tempo, la data di pubblicazione: due lavori
 *     dello stesso anno restano ordinati fra loro per mese, e uno datato al
 *     solo anno ordina al suo gennaio invece di sparire in fondo;
 *   - la classificazione in sottocampi legge la fonte giusta per ogni
 *     database, e la fisica del neutrino vince sulla categoria arXiv;
 *   - i contatori dei filtri non cambiano quando si filtra;
 *   - una nuova ricerca azzera i filtri ma conserva l'ordinamento scelto.
 *
 *   npm install jsdom
 *   node tools/tests/test_search_sort.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/search.js'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

/* ------------------------------------------------------------ la pagina --- */
/* Gli stessi id del sorgente della pagina. Se search.md ne rinomina uno il
 * test non fallisce da solo, quindi il primo controllo qui sotto verifica che
 * ogni id usato sia davvero presente nel markdown della pagina. */
const IDS = ['lit-form', 'q-free', 'q-author', 'q-title', 'q-topic', 'q-collab',
             'q-from', 'q-to', 'lit-chips', 'lit-status', 'lit-results',
             'lit-outbound', 'lit-sort', 'lit-filters', 'lit-pane', 'lit-clear',
             'src-inspire', 'src-crossref', 'src-openalex', 'src-arxiv', 'src-s2'];

const page = fs.readFileSync(path.join(ROOT, 'site-src/content/search.md'), 'utf8');
const missing = IDS.filter(id => page.indexOf('"' + id + '"') === -1 &&
                                 page.indexOf('#' + id) === -1);
missing.length ? bad('id non presenti in search.md: ' + missing.join(', '))
               : ok('gli id usati dal test esistono tutti in search.md');

/* Un controllo sul CSS, non sul DOM, e per una ragione precisa: le due barre
 * sono `display:flex`, e una regola d'autore batte quella dello user agent,
 * quindi senza una regola esplicita l'attributo `hidden` non le nasconderebbe
 * affatto. jsdom non riproduce il difetto — il suo getComputedStyle applica
 * `hidden` da se' e risponde "none" anche quando un browser vero mostrerebbe
 * la barra — percio' l'invariante si verifica sul testo del foglio di stile,
 * che e' dove vive. */
const css = fs.readFileSync(path.join(ROOT, 'site-src/assets/css/site.css'), 'utf8');
/\.lit-sort\[hidden\]\s*\{[^}]*display\s*:\s*none/.test(css)
  ? ok('.lit-sort[hidden] azzera il display:flex')
  : bad('manca .lit-sort[hidden]{display:none}: le barre resterebbero visibili');

const html = `<!doctype html><body>
<form id="lit-form">
  <input id="q-free" type="search">
  <div id="lit-chips"></div>
  <input id="q-author" type="text"><input id="q-title" type="text">
  <input id="q-topic" type="text"><input id="q-collab" type="text">
  <input id="q-from" type="text"><input id="q-to" type="text">
  <label><input type="checkbox" id="src-inspire" checked></label>
  <label><input type="checkbox" id="src-crossref" checked></label>
  <label><input type="checkbox" id="src-openalex" checked></label>
  <label><input type="checkbox" id="src-arxiv" checked></label>
  <label><input type="checkbox" id="src-s2" checked></label>
  <button type="submit">Search</button>
  <button type="button" id="lit-clear">Clear</button>
</form>
<div id="lit-outbound"></div>
<div id="lit-pane">
  <p id="lit-status"></p>
  <div id="lit-sort" hidden></div>
  <div id="lit-filters" hidden></div>
  <div id="lit-results"></div>
</div></body>`;

const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'https://global-nu.org/search.html' });
const w = dom.window, d = w.document;
w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
w.Element.prototype.scrollIntoView = function () {};

/* --------------------------------------------------------- le risposte --- */
/* Otto lavori. Anni, citazioni e categorie scelti perche' ogni assertion piu'
 * avanti abbia un solo ordine possibile. */
let INSPIRE = { hits: { hits: [
  { metadata: {
      control_number: 1, earliest_date: '2024-05-10', citation_count: 120,
      titles: [{ title: 'Neutrino masses and modular symmetry' }],
      authors: [{ full_name: 'Lisi, Eligio' }, { full_name: 'Marrone, Antonio' }],
      arxiv_eprints: [{ value: '2405.00001', categories: ['hep-ph'] }],
      inspire_categories: [{ term: 'Phenomenology-HEP' }],
      publication_info: [{ year: 2024 }], dois: [{ value: '10.1/a' }] } },
  { metadata: {
      control_number: 2, earliest_date: '2019-02-03', citation_count: 40,
      titles: [{ title: 'Modular forms and string compactifications' }],
      authors: [{ full_name: 'Lisi, Eligio' }],
      arxiv_eprints: [{ value: '1902.00002', categories: ['hep-th'] }],
      inspire_categories: [{ term: 'Theory-HEP' }],
      publication_info: [{ year: 2019 }], dois: [{ value: '10.1/b' }] } },
  { metadata: {
      control_number: 3, earliest_date: '2024-01-15', citation_count: 10,
      titles: [{ title: 'Oscillations in matter revisited' }],
      authors: [{ full_name: 'Marrone, Antonio' }],
      arxiv_eprints: [{ value: '2401.00003', categories: ['hep-ph'] }],
      inspire_categories: [{ term: 'Phenomenology-HEP' }],
      publication_info: [{ year: 2024 }], dois: [{ value: '10.1/c' }] } }
] } };

let CROSSREF = { message: { items: [
  { DOI: '10.2/a', title: ['Neutrinoless double beta decay, a review'],
    author: [{ given: 'A', family: 'Rossi' }],
    issued: { 'date-parts': [[2022, 1, 20]] },
    'container-title': ['Rev. Mod. Phys.'] },
  // Nessuna data affatto: e' la riga che deve restare in fondo comunque.
  { DOI: '10.2/b', title: ['Proceedings contribution without a date'],
    author: [{ given: 'B', family: 'Bianchi' }],
    issued: { 'date-parts': [[]] }, 'container-title': ['Proceedings'] }
] } };

let OPENALEX = { results: [
  { id: 'W1', title: 'Dark matter searches with cosmic rays',
    publication_date: '2023-11-02', publication_year: 2023, cited_by_count: 300,
    authorships: [{ author: { display_name: 'C Verdi' } }],
    primary_location: { source: { display_name: 'JCAP' } },
    primary_topic: { display_name: 'Dark Matter and Cosmic Particles',
                     subfield: { display_name: 'Nuclear and High Energy Physics' } },
    doi: 'https://doi.org/10.3/a' }
] };

let DATACITE = { data: [
  { attributes: {
      doi: '10.48550/arxiv.2107.00004', publicationYear: 2021,
      dates: [{ dateType: 'Issued', date: '2021-07-15' }],
      titles: [{ title: 'Cosmological bounds from the microwave background' }],
      creators: [{ name: 'Neri, D' }],
      subjects: [
        { subject: 'Cosmology and Nongalactic Astrophysics (astro-ph.CO)',
          subjectScheme: 'arXiv' },
        { subject: 'FOS: Physical sciences',
          subjectScheme: 'Fields of Science and Technology (FOS)' }] } }
] };

let S2 = { data: [
  { paperId: 'S1', title: 'A study of magnetism in layered materials',
    authors: [{ name: 'E Gialli' }], year: 2015, publicationDate: '2015-03-01',
    venue: 'Phys. Rev. B', citationCount: 5, externalIds: { DOI: '10.4/a' },
    s2FieldsOfStudy: [{ category: 'Physics' }] }
] };

/* Il lookup dei conteggi e' una SECONDA chiamata a INSPIRE, distinta dalla
 * ricerca perche' chiede `fields=citation_count`. Qui risponde per due soli
 * record: quello che OpenAlex conta 300 (INSPIRE ne conta 250, e deve vincere
 * INSPIRE) e uno che nessun database contava. Per gli altri non risponde: un
 * lavoro che INSPIRE non conosce deve restare SENZA conteggio, non tenersi
 * quello di Semantic Scholar. */
let CITES = { hits: { hits: [
  { metadata: { citation_count: 250, dois: [{ value: '10.3/a' }], arxiv_eprints: [] } },
  { metadata: { citation_count: 7,   dois: [{ value: '10.2/a' }], arxiv_eprints: [] } }
] } };

const calls = [];
w.fetch = function (url) {
  calls.push(String(url));
  const u = String(url);
  const body = u.indexOf('fields=citation_count') > -1 ? CITES
             : u.indexOf('inspirehep.net') > -1 ? INSPIRE
             : u.indexOf('api.crossref.org') > -1 ? CROSSREF
             : u.indexOf('api.openalex.org') > -1 ? OPENALEX
             : u.indexOf('api.datacite.org') > -1 ? DATACITE
             : u.indexOf('semanticscholar.org') > -1 ? S2
             : null;
  if (!body) return Promise.reject(new Error('unexpected URL ' + u));
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
};

const errors = [];
w.addEventListener('error', e => errors.push(String(e.error || e.message)));
try { w.eval(js); } catch (e) { errors.push('THROW: ' + e.message); }
errors.length ? bad('errori a caricamento: ' + errors.join(' | '))
              : ok('nessun errore a caricamento');

/* ------------------------------------------------------------- utilita' --- */
const settle = () => new Promise(r => setTimeout(r, 20));
const titles = () => Array.from(d.querySelectorAll('#lit-results li .pub__title'))
                          .map(a => a.textContent);
const sortBtn = id => d.querySelector('#lit-sort [data-sort="' + id + '"]');
const click = el => el.dispatchEvent(new w.Event('click', { bubbles: true }));
const chipOf = t => {
  const li = Array.from(d.querySelectorAll('#lit-results li'))
                  .filter(x => x.querySelector('.pub__title').textContent === t)[0];
  return li ? li.querySelector('.sf').textContent : '(riga assente)';
};
const eq = (got, want, what) =>
  JSON.stringify(got) === JSON.stringify(want)
    ? ok(what) : bad(what + ' — atteso ' + JSON.stringify(want) +
                     ', ottenuto ' + JSON.stringify(got));

const T = {
  nu2024: 'Neutrino masses and modular symmetry',
  str:    'Modular forms and string compactifications',
  osc:    'Oscillations in matter revisited',
  bb:     'Neutrinoless double beta decay, a review',
  nodate: 'Proceedings contribution without a date',
  dm:     'Dark matter searches with cosmic rays',
  cmb:    'Cosmological bounds from the microwave background',
  mag:    'A study of magnetism in layered materials'
};

async function main() {
  d.getElementById('q-free').value = 'Lisi Marrone';
  d.getElementById('lit-form')
   .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await settle();

  /* --- la ricerca ha prodotto qualcosa --------------------------------- */
  console.log('\n--- la ricerca ---');
  calls.filter(u => u.indexOf('fields=citation_count') === -1).length === 5
    ? ok('cinque database interrogati') : bad('chiamate: ' + calls.length);
  calls.filter(u => u.indexOf('fields=citation_count') > -1).length === 1
    ? ok('piu una sola richiesta a INSPIRE per i conteggi mancanti')
    : bad('richieste di conteggio: ' +
          calls.filter(u => u.indexOf('fields=citation_count') > -1).length);
  titles().length === 8 ? ok('otto lavori sulla pagina')
                        : bad('righe: ' + titles().length);

  /* --- la classificazione in sottocampi -------------------------------- */
  console.log('\n--- sottocampi ---');
  eq(chipOf(T.nu2024), 'Neutrino physics',
     'hep-ph + "neutrino" nel titolo -> fisica del neutrino, non fenomenologia');
  eq(chipOf(T.str), 'Fields, strings & math. physics', 'hep-th -> teoria');
  eq(chipOf(T.cmb), 'Cosmology & gravitation',
     'astro-ph.CO letto dal subjectScheme arXiv di DataCite');
  eq(chipOf(T.dm), 'Astroparticle & HE astrophysics',
     'primary_topic di OpenAlex quando non c-e categoria arXiv');
  eq(chipOf(T.bb), 'Neutrino physics',
     '"double beta" nel titolo, senza nessuna categoria da Crossref');
  eq(chipOf(T.mag), 'Other physics', 's2FieldsOfStudy come ultima risorsa');
  // Volutamente NON "Neutrino physics": il titolo non dice neutrino e nessun
  // database lo classifica cosi'. Il classificatore usa quello che le fonti
  // dicono e si ferma li'; dedurre l'argomento dalla parola "oscillations"
  // sarebbe indovinare, ed e' esattamente cio' che non deve fare.
  eq(chipOf(T.osc), 'Particle phenomenology',
     'senza la parola nel titolo resta la categoria arXiv: niente deduzioni');
  eq(chipOf(T.nodate), 'Unclassified',
     'nessun segnale: non classificato, non indovinato');

  /* --- le citazioni ------------------------------------------------------ */
  console.log('\n--- citazioni: solo quelle di INSPIRE ---');
  const citaz = t => {
    const li = [...d.querySelectorAll('#lit-results li')]
      .filter(x => x.querySelector('.pub__title').textContent === t)[0];
    if (!li) return '(riga assente)';
    const c = [...li.querySelectorAll('.muted')].map(x => x.textContent).join('');
    return c || '(nessun conteggio)';
  };
  eq(citaz(T.dm), '250 citations',
     'OpenAlex ne contava 300: vince il 250 di INSPIRE');
  eq(citaz(T.mag), '(nessun conteggio)',
     'i 5 di Semantic Scholar non si mostrano: INSPIRE non conosce il lavoro');
  eq(citaz(T.bb), '7 citations',
     'un record che nessun database contava prende il conteggio da INSPIRE');
  eq(citaz(T.nu2024), '120 citations', 'il conteggio di INSPIRE resta quello di INSPIRE');

  /* --- vista di rilevanza: i gruppi di corrispondenza ------------------ */
  console.log('\n--- vista di rilevanza (predefinita) ---');
  sortBtn('relevance').getAttribute('aria-pressed') === 'true'
    ? ok('rilevanza attiva all-apertura') : bad('rilevanza non attiva');
  d.querySelectorAll('#lit-results .lit-bucket').length >= 2
    ? ok('i gruppi per qualita di corrispondenza restano')
    : bad('gruppi: ' + d.querySelectorAll('#lit-results .lit-bucket').length);
  titles()[0] === T.nu2024
    ? ok('in cima il lavoro con entrambi gli autori')
    : bad('primo: ' + titles()[0]);
  const heads = () => Array.from(d.querySelectorAll('#lit-results .lit-group'))
                           .map(h => h.firstChild.textContent.trim());
  const gruppi = heads();
  // Il rovesciamento deve rovesciare anche la SEQUENZA dei gruppi. Finche' non
  // lo faceva, il primo click su "Relevance" lasciava la pagina identica
  // mentre la riga di stato e il nome accessibile del pulsante annunciavano
  // "weakest match first": un controllo che dice di aver invertito e non lo ha
  // fatto e' peggio di nessun controllo.
  click(sortBtn('relevance'));
  eq(heads(), gruppi.slice().reverse(),
     'rilevanza crescente: i gruppi si rovesciano davvero');
  titles()[0] !== T.nu2024
    ? ok('e la corrispondenza migliore non e piu la prima riga')
    : bad('la riga migliore e rimasta in cima con ordine crescente');
  click(sortBtn('relevance'));            // torniamo a decrescente
  eq(heads(), gruppi, 'un altro click rimette i gruppi come prima');

  /* --- data di pubblicazione ------------------------------------------- */
  console.log('\n--- data di pubblicazione ---');
  // Non esiste piu' un pulsante "Month": una chiave sola, alla risoluzione
  // piu' fine. Se qualcuno rimettesse la coppia, questa riga lo direbbe.
  sortBtn('year') === null
    ? ok('una sola chiave per il tempo: il pulsante Year non esiste piu')
    : bad('il pulsante Year e tornato');
  [...d.querySelectorAll('#lit-sort [data-sort]')].length === 4
    ? ok('quattro chiavi in tutto') : bad('chiavi: ' +
        d.querySelectorAll('#lit-sort [data-sort]').length);
  click(sortBtn('date'));
  d.querySelectorAll('#lit-results .lit-bucket').length === 0
    ? ok('lista unica: ordinare per data non puo convivere coi gruppi')
    : bad('i gruppi sono rimasti');
  eq(titles(), [T.nu2024, T.osc, T.dm, T.bb, T.cmb, T.str, T.mag, T.nodate],
     'decrescente: mag 2024, gen 2024, 2023, 2022, 2021, 2019, 2015, senza data');
  titles().indexOf(T.nu2024) < titles().indexOf(T.osc)
    ? ok('maggio prima di gennaio dello stesso anno: il mese conta ancora')
    : bad('due lavori del 2024 non sono ordinati per mese');
  click(sortBtn('date'));
  eq(titles(), [T.mag, T.str, T.cmb, T.bb, T.dm, T.osc, T.nu2024, T.nodate],
     'crescente: si ribalta, e la riga senza data resta ULTIMA');

  /* --- citazioni -------------------------------------------------------- */
  console.log('\n--- citazioni ---');
  click(sortBtn('citations'));
  eq(titles().slice(0, 5), [T.dm, T.nu2024, T.str, T.osc, T.bb],
     'decrescente: 250, 120, 40, 10, 7 — tutti conteggi di INSPIRE');
  const tail = titles().slice(5);
  tail.indexOf(T.mag) > -1 && tail.indexOf(T.nodate) > -1 && tail.indexOf(T.cmb) > -1
    ? ok('chi non ha un conteggio di INSPIRE sta in coda, anche se un altro database lo contava')
    : bad('coda: ' + JSON.stringify(tail));
  click(sortBtn('citations'));
  eq(titles().slice(0, 5), [T.bb, T.osc, T.str, T.nu2024, T.dm],
     'crescente: 7, 10, 40, 120, 250');
  titles().slice(5).indexOf(T.nodate) > -1
    ? ok('senza citazioni ancora in coda, non in cima')
    : bad('un record senza citazioni e risalito in cima');

  /* --- sottocampo ------------------------------------------------------- */
  console.log('\n--- raggruppamento per sottocampo ---');
  click(sortBtn('subfield'));
  heads()[0] === 'Neutrino physics'
    ? ok('gruppo piu numeroso per primo (2 lavori sul neutrino, gli altri 1)')
    : bad('primo gruppo: ' + heads()[0]);
  click(sortBtn('subfield'));
  heads()[heads().length - 1] === 'Neutrino physics'
    ? ok('ribaltato: il gruppo piu numeroso per ultimo')
    : bad('ultimo gruppo: ' + heads()[heads().length - 1]);

  /* --- filtri per sottocampo ------------------------------------------- */
  console.log('\n--- filtri ---');
  click(sortBtn('date'));                     // torniamo a una lista piatta
  const filt = id => d.querySelector('#lit-filters [data-sf="' + id + '"]');
  const nOf = id => filt(id).querySelector('.lit-filter__n').textContent;
  filt('neutrino') ? ok('esiste il filtro del sottocampo neutrino')
                   : bad('filtro neutrino assente');
  const before = nOf('neutrino');
  click(filt('neutrino'));
  titles().length === 6
    ? ok('nascosti i due lavori sul neutrino') : bad('righe: ' + titles().length);
  nOf('neutrino') === before
    ? ok('il contatore del filtro non cambia quando si filtra')
    : bad('contatore cambiato: ' + before + ' -> ' + nOf('neutrino'));
  filt('neutrino').getAttribute('aria-pressed') === 'false'
    ? ok('aria-pressed segue lo stato del filtro') : bad('aria-pressed non aggiornato');
  /^\d+ papers from \d+ databases?.*6 shown/.test(d.getElementById('lit-status').textContent)
    ? ok('la riga di stato dice quante righe sono mostrate')
    : bad('stato: ' + d.getElementById('lit-status').textContent);
  click(d.querySelector('#lit-filters [data-sf="*"]'));
  titles().length === 8 ? ok('"Show all" li rimette tutti')
                        : bad('dopo Show all: ' + titles().length);

  /* --- che cosa viene chiesto ai database ------------------------------- */
  console.log('\n--- la query mandata ai database ---');
  // La ricerca, non il lookup dei conteggi: quest'ultimo e' anche lui una
  // chiamata a inspirehep.net, ed e' l'ULTIMA, quindi senza questo filtro
  // il controllo misurerebbe la richiesta sbagliata.
  const inspireUrl = () => calls.filter(u => u.indexOf('inspirehep.net') > -1 &&
                                             u.indexOf('fields=citation_count') === -1).pop();
  // La chiave scelta vale per la ricerca SUCCESSIVA: e' quella che decide
  // quali venti record ogni database restituisce. Qui la chiave attiva e'
  // gia' "date", quindi basta rilanciare.
  d.getElementById('lit-form')
   .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await settle();
  /sort=mostrecent/.test(inspireUrl())
    ? ok('con la chiave data INSPIRE riceve sort=mostrecent')
    : bad('INSPIRE: ' + inspireUrl());
  click(sortBtn('citations'));
  d.getElementById('lit-form')
   .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await settle();
  // Volutamente NESSUN sort: chiedere a INSPIRE i piu' citati restituisce i
  // piu' citati che CONTENGONO le parole, non i piu' citati sull-argomento.
  /sort=/.test(inspireUrl())
    ? bad('la chiave citazioni e stata spinta sul database: ' + inspireUrl())
    : ok('con la chiave citazioni INSPIRE non riceve nessun sort');
  click(sortBtn('date'));

  /* --- il fuoco da tastiera --------------------------------------------- */
  console.log('\n--- tastiera ---');
  // Le barre vengono ridisegnate per intero a ogni click: senza refocus() chi
  // usa la tastiera preme Invio su "Year" e si ritrova il fuoco all'inizio del
  // documento, senza modo di ribaltare l'ordine se non ritabulando tutto.
  const yb = sortBtn('citations');
  yb.focus();
  click(yb);
  d.activeElement === sortBtn('citations')
    ? ok('dopo il click il fuoco resta sul pulsante usato')
    : bad('fuoco perso: ' + (d.activeElement && d.activeElement.tagName));
  const nf = filt('neutrino');
  nf.focus();
  click(nf);
  d.activeElement === filt('neutrino')
    ? ok('lo stesso per il filtro') : bad('fuoco perso sul filtro');
  click(d.querySelector('#lit-filters [data-sf="*"]'));
  d.activeElement && d.activeElement.hasAttribute('data-sf')
    ? ok('"Show all" sparisce usandolo e il fuoco va su un altro chip')
    : bad('dopo Show all il fuoco e finito nel nulla');
  click(sortBtn('date'));                     // torniamo all'ordinamento per data

  /* --- una nuova ricerca ------------------------------------------------ */
  console.log('\n--- una nuova ricerca ---');
  click(filt('neutrino'));                    // filtro attivo prima di ricercare
  d.getElementById('lit-form')
   .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await settle();
  titles().length === 8
    ? ok('il filtro e azzerato dalla nuova ricerca')
    : bad('righe dopo la nuova ricerca: ' + titles().length);
  sortBtn('date').getAttribute('aria-pressed') === 'true'
    ? ok("l'ordinamento scelto sopravvive alla nuova ricerca")
    : bad('ordinamento perso');

  /* --- lo stato dice cosa sta facendo ----------------------------------- */
  const st = d.getElementById('lit-status').textContent;
  /ordered by date/.test(st) ? ok('lo stato nomina la chiave attiva')
                             : bad('stato: ' + st);

  /* --- il pulsante Clear ------------------------------------------------ */
  click(d.getElementById('lit-clear'));
  // La barra dell-ordinamento RESTA: la chiave viene spinta sui database per
  // anno e mese, quindi deve poter essere scelta prima di cercare. Sparisce
  // invece quella dei filtri, che puo' solo restringere una risposta esistente.
  !d.getElementById('lit-sort').hidden && d.getElementById('lit-filters').hidden
   && d.getElementById('lit-results').innerHTML === ''
    ? ok('Clear svuota i risultati, toglie i filtri e lascia l-ordinamento')
    : bad('Clear: sort hidden=' + d.getElementById('lit-sort').hidden +
          ', filters hidden=' + d.getElementById('lit-filters').hidden);

  /* --- forme ostili e la sede come segnale ------------------------------ */
  /* Le API rispondono anche con campi nulli o assenti, e una sola eccezione
   * qui dentro svuoterebbe la pagina invece di degradarla. Qui vengono
   * mandate apposta: eprint nullo, categorie nulle, una voce di categoria
   * vuota, subjects nulli, nessun primary_topic, nessun autore, titolo nullo,
   * date assenti. E in mezzo un record che dice di che parla SOLO con la
   * sede, che e' il modo in cui un volume di atti tradisce il proprio
   * argomento. */
  console.log('\n--- forme ostili ---');
  INSPIRE = { hits: { hits: [
    { metadata: { control_number: 9, titles: [{ title: null }], authors: null,
                  arxiv_eprints: null, inspire_categories: [{}],
                  publication_info: null, dois: null, citation_count: null } }
  ] } };
  CROSSREF = { message: { items: [
    { DOI: '10.9/a', title: ['Systematic uncertainties in a water detector'],
      author: null, issued: null, subject: ['Instrumentation'],
      'container-title': ['Proceedings of the XXIX International Conference on '
                          + 'Neutrino Physics and Astrophysics'] }
  ] } };
  OPENALEX = { results: [
    { id: 'W9', title: null, authorships: null, primary_location: null,
      primary_topic: null, publication_year: null, cited_by_count: null }
  ] };
  DATACITE = { data: [{ attributes: { doi: null, titles: null, creators: null,
                                      subjects: null, dates: null } }] };
  S2 = { data: [{ paperId: 'S9', title: null, authors: null, year: null,
                  s2FieldsOfStudy: null, externalIds: null }] };

  const prima = errors.length;
  // Clear, qui sopra, ha svuotato il modulo: senza una chiave la ricerca non
  // parte nemmeno.
  d.getElementById('q-free').value = 'Lisi Marrone';
  d.getElementById('lit-form')
   .dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await settle();
  ['relevance', 'date', 'citations', 'subfield'].forEach(function (k) {
    click(sortBtn(k)); click(sortBtn(k));
  });
  errors.length === prima
    ? ok('nessuna eccezione con campi nulli e ordinando su tutte le chiavi')
    : bad('eccezioni: ' + errors.slice(prima).join(' | '));
  d.querySelectorAll('#lit-results li').length >= 1
    ? ok('la pagina degrada invece di svuotarsi')
    : bad('nessuna riga sopravvissuta alle forme ostili');
  chipOf('Systematic uncertainties in a water detector') === 'Neutrino physics'
    ? ok('la sede basta: atti di una conferenza sui neutrini -> neutrini')
    : bad('sede ignorata: ' + chipOf('Systematic uncertainties in a water detector'));

  console.log('');
  if (fail.length) {
    console.log('FALLITI ' + fail.length + ' CONTROLLI');
    process.exit(1);
  }
  console.log('TUTTI I CONTROLLI SUPERATI');
}

main().catch(e => { console.log('  FAIL eccezione: ' + e.stack); process.exit(1); });
