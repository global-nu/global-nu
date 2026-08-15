/* The conference map's card, tested rather than assumed.
 *
 * Unlike map.js (pan/zoom/filter/fan-out over dozens of experiments),
 * confmap.js only ever answers one question per click: which conference, and
 * where. So this suite is smaller than test_map.js on purpose — clicking a
 * marker opens a card naming the conference; the card links out to the
 * conference itself and, separately, to Google Maps built from the marker's
 * own coordinates (never from the venue string — see confmap.js's comment on
 * why "Old Trafford" as a text search lands in Manchester); Escape closes the
 * card and returns focus to the marker; and with the script never running the
 * SVG still reads via each marker's <title>. A third marker (Trieste, below)
 * carries the five data-photo* attributes tools/news/photos.py adds when
 * Commons has a licence-clean, credited photograph of the conference's city
 * — its card must render the image AND all three parts of the credit
 * (author, licence, the Commons file-page link); the other two markers carry
 * none of those attributes, so their cards must render no image at all —
 * the regression guard that keeps the photo check from being vacuous.
 *
 *   node tools/tests/test_confmap.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/confmap.js'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

const SVG = `
<figure class="figure confmap-figure">
  <svg id="cm" viewBox="0 6 720 162" role="img" aria-label="Where the upcoming conferences are">
    <title>Where the upcoming conferences are</title>
    <path d="M0,0 L720,0 L720,162 L0,162Z" class="confmap-land"/>
    <g class="conf-pin" data-conf="conf:2812345"
       data-place="Shanghai, China"
       data-lat="31.23" data-lon="121.47">
      <title>NuFact 2026 — Shanghai, China</title>
      <circle cx="601.6" cy="58.9" r="3.0"/>
      <g class="conf-item" data-conf="conf:2812345" data-name="NuFact 2026"
         data-dates="31 Aug – 5 Sep 2026" data-url="https://nufact2026.example.org/"></g>
    </g>
    <g class="conf-pin" data-conf="nu:2026-09-14-erice"
       data-place="Erice, Italy"
       data-lat="37.93" data-lon="12.83">
      <title>Erice School 2026 — Erice, Italy</title>
      <circle cx="384.6" cy="26.0" r="3.0"/>
      <g class="conf-item" data-conf="nu:2026-09-14-erice" data-name="Erice School 2026"
         data-dates="14–22 Sep 2026" data-url="https://erice.example.org/"></g>
    </g>
    <g class="conf-pin" data-conf="conf:trieste-photo"
       data-place="Trieste, Italy"
       data-lat="45.6495" data-lon="13.7768"
       data-photo="images/conf-trieste.jpg"
       data-photo-author="Fermilab, Reidar Hahn"
       data-photo-licence="CC BY-SA 4.0"
       data-photo-licence-url="https://creativecommons.org/licenses/by-sa/4.0"
       data-photo-page="https://commons.wikimedia.org/wiki/File:Trieste.jpg">
      <title>Neutrino Physics in Trieste — Trieste, Italy</title>
      <circle cx="420.0" cy="40.0" r="3.0"/>
      <g class="conf-item" data-conf="conf:trieste-photo" data-name="Neutrino Physics in Trieste"
         data-dates="3–7 Nov 2026" data-url="https://trieste.example.org/"></g>
    </g>
    <g class="conf-pin" data-place="Bari, Italy" data-lat="41.1200"
       data-lon="16.8700" tabindex="0">
      <title>First Conference — Bari, Italy — 1-5 Sep 2026</title>
      <circle r="4.7"/><text>2</text>
      <g class="conf-item" data-conf="conf:first" data-name="First Conference"
         data-dates="1-5 Sep 2026" data-url="https://first.example/"></g>
      <g class="conf-item" data-conf="conf:second" data-name="Second Conference"
         data-dates="8-9 Sep 2026" data-url="https://second.example/"></g>
    </g>
  </svg>
</figure>`;

function boot() {
  const dom = new JSDOM(`<!doctype html><body>${SVG}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom.window.document;
}

/* 1. clicking a marker opens a card naming the conference */
let d = boot();
d.querySelector('[data-conf="conf:2812345"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const card = d.querySelector('.conf-card');
card && /NuFact 2026/.test(card.textContent)
  ? ok('clicking a marker opens a card naming the conference')
  : bad('no card, or the card does not name the conference');

/* 2. the card carries a link to the conference itself */
const confLink = card && [...card.querySelectorAll('a')].find(a => a.href === 'https://nufact2026.example.org/');
confLink
  ? ok('the card links to the conference itself')
  : bad('the card carries no link to the conference');

/* 3. the card carries an "Open in Google Maps" link built from the marker's
   own coordinates — not from the venue string, which is why the assertion
   checks for the numbers rather than for "Shanghai" appearing in the URL.
   The brief's query string is lat BEFORE lon — the opposite order from
   venue.locate_record's own (lon, lat) — so this asserts the exact
   "query=<lat>,<lon>" substring, not merely that both numbers appear
   somewhere in the href: a version of gmapsUrl built as lon + "," + lat
   would still pass an indexOf-per-number check (both numbers are still in
   the string, just swapped) while putting every conference in the wrong
   hemisphere. That regression was caught only by tightening this assertion
   — see the RED/GREEN mutation transcript in task-4-report.md. */
const gmapLink = card && [...card.querySelectorAll('a')].find(a =>
  (a.href || '').indexOf('google.com/maps') > -1);
gmapLink
  ? ok('the card carries a Google Maps link')
  : bad('the card carries no Google Maps link');
gmapLink && gmapLink.href.indexOf('query=31.23,121.47') > -1
  ? ok('the Google Maps link is built lat-before-lon from the marker\'s '
      + 'data-lat and data-lon, in that exact order')
  : bad('the Google Maps link does not carry "query=31.23,121.47" verbatim: '
      + (gmapLink && gmapLink.href));
gmapLink && gmapLink.target === '_blank'
  ? ok('the Google Maps link opens in a new tab (target="_blank")')
  : bad('the Google Maps link does not set target="_blank"');
gmapLink && /noopener/.test(gmapLink.rel || '')
  ? ok('the Google Maps link carries rel="noopener" (or better)')
  : bad('the Google Maps link is missing rel="noopener"');

/* 4. Escape closes the card and returns focus to the marker that opened it */
d = boot();
const pin1 = d.querySelector('[data-conf="conf:2812345"]');
pin1.focus();
pin1.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
const opened = d.querySelector('.conf-card');
opened && opened.contains(d.activeElement)
  ? ok('opening the card (via keyboard) moves focus into it')
  : bad('the card opened but focus stayed outside it');
d.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
(!d.querySelector('.conf-card') && d.activeElement === pin1)
  ? ok('Escape closes the card and returns focus to the marker that opened it')
  : bad('focus did not return to the opening marker after Escape');

/* 5. every marker is a keyboard tab stop, reachable without a mouse */
d = boot();
const pin2 = d.querySelector('[data-conf="nu:2026-09-14-erice"]');
pin2.getAttribute('tabindex') === '0'
  ? ok('a marker is a keyboard tab stop')
  : bad('a marker has no tabindex, so it cannot be reached from the keyboard');
pin2.focus();
pin2.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
const kbCard = d.querySelector('.conf-card');
kbCard && /Erice School 2026/.test(kbCard.textContent)
  ? ok('pressing Enter on a focused marker opens its card, same as a click')
  : bad('Enter on a focused marker did not open its card');

/* 6. no marker loses the <title> that carries it once the script has run —
   NOT a check against a fresh, un-scripted JSDOM: that would pass no matter
   what confmap.js does (or does not do), since a document the script never
   touches trivially still has whatever the fixture put in it. This boots
   the script exactly as checks 1-5 do, so it can actually fail if a future
   change to open()/wireCard() ever strips or replaces a marker's <title> —
   e.g. by rebuilding the pin's innerHTML instead of only appending a card
   elsewhere in the figure. */
d = boot();
d.querySelectorAll('.conf-pin title').length === 4
  ? ok('every marker keeps its <title> after the script has run')
  : bad('a marker lost its <title>');

/* 7. a marker carrying photo attributes renders the image and all three
   parts of the credit — author, licence, the Commons file-page link. */
d = boot();
const photoPin = d.querySelector('[data-conf="conf:trieste-photo"]');
photoPin.dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const photoCard = d.querySelector('.conf-card');
const img = photoCard && photoCard.querySelector('.conf-card__photo img');
img
  ? ok('a marker carrying data-photo renders an <img> in the card')
  : bad('no <img> rendered for a marker carrying data-photo');
img && img.getAttribute('src') === 'images/conf-trieste.jpg'
  ? ok('the rendered image src is built from the marker\'s data-photo')
  : bad('the rendered image src does not match data-photo: ' + (img && img.src));

const credit = photoCard && photoCard.querySelector('.conf-card__credit');
const creditText = (credit && credit.textContent) || '';
/Fermilab, Reidar Hahn/.test(creditText)
  ? ok('the credit names the author')
  : bad('the credit is missing the author: ' + creditText);
/CC BY-SA 4\.0/.test(creditText)
  ? ok('the credit states the licence')
  : bad('the credit is missing the licence: ' + creditText);
const creditLinks = credit ? [...credit.querySelectorAll('a')] : [];
const licenceLink = creditLinks.find(a => a.href === 'https://creativecommons.org/licenses/by-sa/4.0');
licenceLink
  ? ok('the licence name links to the licence URL')
  : bad('no link to the licence URL found in the credit');
const pageLink = creditLinks.find(a => a.href === 'https://commons.wikimedia.org/wiki/File:Trieste.jpg');
pageLink
  ? ok('the credit links to the photograph\'s Commons file page')
  : bad('no link to the Commons file page found in the credit');
pageLink && pageLink.target === '_blank' && /noopener/.test(pageLink.rel || '')
  ? ok('the Commons file-page link opens in a new tab with rel="noopener"')
  : bad('the Commons file-page link is missing target="_blank"/rel="noopener": '
      + (pageLink && pageLink.target) + ' / ' + (pageLink && pageLink.rel));

/* 8. a marker with none of the five data-photo* attributes renders no image
   at all — the regression guard that keeps check 7 from being vacuous
   (proving the assertions can fail, not merely that they can pass). */
d = boot();
const plainPin = d.querySelector('[data-conf="conf:2812345"]');
plainPin.dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const plainCard = d.querySelector('.conf-card');
plainCard && !plainCard.querySelector('.conf-card__photo')
  ? ok('a marker with no data-photo renders no photo block at all')
  : bad('a photo block was rendered for a marker that carries no data-photo');

/* 9. a marker holding several conferences (Task 6's shape: one .conf-pin,
   several .conf-item children) lists every one of them, each with its own
   dates and its own link, under a single, non-repeated photograph. */
d = boot();
const multi = d.querySelector('[data-place="Bari, Italy"]');
multi.dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const mcard = d.querySelector('.conf-card');
mcard && mcard.textContent.includes('First Conference')
  ? ok('the card names the first conference')
  : bad('the card names the first conference');
mcard && mcard.textContent.includes('Second Conference')
  ? ok('the card names the second conference')
  : bad('the card names the second conference');
mcard && mcard.textContent.includes('8-9 Sep 2026')
  ? ok('each conference keeps its own dates')
  : bad('each conference keeps its own dates');
const links = mcard ? [...mcard.querySelectorAll('a')].map(a => a.href) : [];
links.includes('https://first.example/') && links.includes('https://second.example/')
  ? ok('each conference links to itself')
  : bad('each conference links to itself: ' + links.join(', '));
mcard && mcard.querySelectorAll('.conf-card__photo').length <= 1
  ? ok('the city photograph is rendered once, not once per conference')
  : bad('the photograph was repeated per conference');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
