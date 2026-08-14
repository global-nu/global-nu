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
 * SVG still reads via each marker's <title>.
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
    <g class="conf-pin" data-conf="conf:2812345" data-name="NuFact 2026"
       data-place="Shanghai, China" data-dates="31 Aug – 5 Sep 2026"
       data-url="https://nufact2026.example.org/"
       data-lat="31.23" data-lon="121.47">
      <title>NuFact 2026 — Shanghai, China</title>
      <circle cx="601.6" cy="58.9" r="3.0"/>
    </g>
    <g class="conf-pin" data-conf="nu:2026-09-14-erice" data-name="Erice School 2026"
       data-place="Erice, Italy" data-dates="14–22 Sep 2026"
       data-url="https://erice.example.org/"
       data-lat="37.93" data-lon="12.83">
      <title>Erice School 2026 — Erice, Italy</title>
      <circle cx="384.6" cy="26.0" r="3.0"/>
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
   checks for the numbers rather than for "Shanghai" appearing in the URL. */
const gmapLink = card && [...card.querySelectorAll('a')].find(a =>
  (a.href || '').indexOf('google.com/maps') > -1);
gmapLink
  ? ok('the card carries a Google Maps link')
  : bad('the card carries no Google Maps link');
gmapLink && gmapLink.href.indexOf('31.23') > -1 && gmapLink.href.indexOf('121.47') > -1
  ? ok('the Google Maps link is built from the marker\'s data-lat and data-lon')
  : bad('the Google Maps link does not carry the marker\'s coordinates: ' + (gmapLink && gmapLink.href));
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

/* 6. the SVG stays readable with the script never running: no marker loses
   the <title> that carries it when JS is off. */
const plain = new JSDOM(`<!doctype html><body>${SVG}</body>`).window.document;
plain.querySelectorAll('.conf-pin title').length === 2
  ? ok('every marker keeps its <title>, so the map reads with JS off')
  : bad('a marker lost its <title>');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
