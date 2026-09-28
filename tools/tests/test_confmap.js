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
         data-tier="core" data-tier-label="Neutrino physics"
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
       data-lon="16.8700">
      <title>First Conference — Bari, Italy — 1-5 Sep 2026</title>
      <circle r="4.7"/><text>2</text>
      <g class="conf-item" data-conf="conf:first" data-name="First Conference"
         data-tier="core" data-tier-label="Neutrino physics"
         data-dates="1-5 Sep 2026" data-url="https://first.example/"></g>
      <g class="conf-item" data-conf="conf:second" data-name="Second Conference"
         data-tier="adjacent" data-tier-label="Adjacent fields"
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
mcard && mcard.textContent.includes('2 conferences')
  ? ok('the card states the count next to the place, plural for two')
  : bad('the card does not state the conference count');

/* 10. a single-conference marker states the count too, correctly singular —
   the count line is not something that only appears once a marker is
   crowded; the grammar has to hold at the n=1 boundary as well. */
const single = d.querySelector('[data-conf="conf:2812345"]');
single.dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const scard = d.querySelector('.conf-card');
scard && scard.textContent.includes('1 conference') && !scard.textContent.includes('1 conferences')
  ? ok('a single-conference card states the count, singular')
  : bad('a single-conference card does not state the count correctly: '
      + (scard && scard.textContent));

// --- the hover panel -----------------------------------------------------
const hoverPin = d.querySelector('[data-place="Bari, Italy"]');
hoverPin.dispatchEvent(new d.defaultView.Event('mouseenter', {bubbles: true}));
const tip = d.querySelector('.conf-tip');
tip ? ok('hovering a marker opens a panel') : bad('hovering a marker opens a panel');
tip && tip.textContent.includes('Bari, Italy')
  ? ok('the panel names the place') : bad('the panel names the place');
tip && tip.textContent.includes('First Conference') &&
      tip.textContent.includes('Second Conference')
  ? ok('the panel names every conference') : bad('the panel names every conference');
tip && tip.textContent.includes('1-5 Sep 2026')
  ? ok('the panel gives the period') : bad('the panel gives the period');
tip && tip.querySelectorAll('img').length === 0
  ? ok('the panel loads no image') : bad('the panel loads an image');

hoverPin.dispatchEvent(new d.defaultView.Event('mouseleave', {bubbles: true}));
!d.querySelector('.conf-tip') || d.querySelector('.conf-tip').hidden
  ? ok('leaving the marker closes the panel') : bad('the panel stayed open');

// A control reachable by mouse but not by keyboard is a defect.
hoverPin.dispatchEvent(new d.defaultView.Event('focus', {bubbles: true}));
const kbTip = d.querySelector('.conf-tip');
kbTip && !kbTip.hidden
  ? ok('keyboard focus opens the panel too') : bad('keyboard focus opens the panel too');

/* The affinity tier, per meeting rather than per marker.
 *
 * A marker is painted with the STRONGEST tier at its venue (figures.py's
 * _marker_tier), so at a mixed venue the dot's colour is true of one meeting
 * and not of the others. The card and the hover panel must therefore chip
 * each meeting separately, or one colour would silently speak for several
 * subjects — which is the whole reason the map moved off edition scope. The
 * Bari marker holds one `core` and one `adjacent` meeting for this check.
 */
const dm = boot();
dm.querySelector('[data-place="Bari, Italy"]')
  .dispatchEvent(new dm.defaultView.Event('click', { bubbles: true }));
const mixedCard = dm.querySelector('.conf-card');
const cardChips = mixedCard ? [...mixedCard.querySelectorAll('.conf-aff')] : [];
cardChips.length === 2
  ? ok('the card chips every meeting at a mixed venue, not just one')
  : bad('the card shows ' + cardChips.length + ' tier chip(s), expected 2');
cardChips.map(c => c.className).join(' ') === 'conf-aff conf-aff--core conf-aff conf-aff--adjacent'
  ? ok('each chip carries its own meeting\'s tier class')
  : bad('chip classes: ' + cardChips.map(c => c.className).join(' | '));
cardChips.map(c => c.textContent).join('|') === 'Neutrino physics|Adjacent fields'
  ? ok('each chip is labelled as the record labels it')
  : bad('chip labels: ' + cardChips.map(c => c.textContent).join('|'));
mixedCard && /1-5 Sep 2026/.test(mixedCard.textContent)
  ? ok('the dates survive alongside the chip')
  : bad('the chip displaced the dates');

const dt2 = boot();
const mixedPin = dt2.querySelector('[data-place="Bari, Italy"]');
mixedPin.dispatchEvent(new dt2.defaultView.Event('mouseenter', { bubbles: true }));
const mixedTip = dt2.querySelector('.conf-tip');
const tipChips = mixedTip ? [...mixedTip.querySelectorAll('.conf-aff')] : [];
tipChips.length === 2
  ? ok('the hover panel chips every meeting too')
  : bad('the hover panel shows ' + tipChips.length + ' tier chip(s), expected 2');

/* A marker whose items carry no tier at all — an older cached page, or a
 * caller that never tagged — must render without chips, not with empty ones. */
const dn = boot();
dn.querySelector('[data-place="Erice, Italy"]')
  .dispatchEvent(new dn.defaultView.Event('click', { bubbles: true }));
const untaggedCard = dn.querySelector('.conf-card');
untaggedCard && untaggedCard.querySelectorAll('.conf-aff').length === 0
  ? ok('a meeting with no tier gets no chip, not an empty one')
  : bad('an untagged meeting rendered a chip');

/* The timeline and the lists open the SAME card. Their bars (with the label
 * that travels beside each one) and rows carry one conference's data-*
 * (figures.conf_attrs); when the map has a marker for that conference, the
 * card borrows its coordinates and photo. */
const ROWS = `
<figure class="figure"><div class="timeline-scroll"><svg>
  <g class="conf-bar" data-conf="conf:2812345" data-name="NuFact 2026" data-dates="31 Aug – 5 Sep 2026"
     data-place="Shanghai" data-url="https://nufact2026.example.org/" data-tier="core"
     data-tier-label="Neutrino physics"><rect x="1" y="1" width="9" height="10"/><text>NuFact 2026</text></g>
  <g class="conf-bar" data-conf="conf:trieste-photo" data-name="Neutrino Physics in Trieste"
     data-dates="3–7 Nov 2026" data-place="SISSA, Trieste" data-url="https://trieste.example.org/"
     data-tier="" data-tier-label=""><rect x="20" y="1" width="9" height="10"/><text>NuTrieste</text></g>
  <g class="conf-bar" data-conf="conf:nomap" data-name="Unplaced Workshop" data-dates="1 Dec 2026"
     data-place="" data-url="" data-tier="" data-tier-label=""><rect x="40" y="1" width="9" height="10"/></g>
</svg></div></figure>
<ul class="list list--news conf-list">
  <li data-conf="conf:erice" data-name="Erice School 2026" data-dates="14–22 Sep 2026"
      data-place="Erice, Italy" data-url="https://erice.example.org/" data-tier="" data-tier-label=""><b>Erice School 2026</b><span>14–22 Sep 2026 · Erice</span><span class="cites"><a href="https://erice.example.org/">Details</a></span></li>
</ul>`;

function bootRows(withMap) {
  const dom = new JSDOM(`<!doctype html><body>${withMap ? SVG : ''}${ROWS}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom.window.document;
}
const click = (doc, el, extra) => {
  const ev = new doc.defaultView.MouseEvent('click', Object.assign({ bubbles: true, cancelable: true }, extra || {}));
  el.dispatchEvent(ev);
  return ev;
};

let dr = bootRows(true);
click(dr, dr.querySelector('.conf-bar rect'));
let rc = dr.querySelector('.conf-card');
rc && /NuFact 2026/.test(rc.textContent)
  && [...rc.querySelectorAll('a')].some(a => a.href === 'https://nufact2026.example.org/')
  ? ok('a timeline bar opens the card, linking to the conference site')
  : bad('a timeline bar did not open a card with the conference link');
rc && [...rc.querySelectorAll('a')].some(a => a.href.indexOf('query=31.23,121.47') > -1)
  ? ok('the bar\'s card borrows the map marker\'s coordinates for Google Maps')
  : bad('the bar\'s card has no Google Maps link from the marker');
rc && rc.classList.contains('conf-card--float') && rc.parentNode === dr.body
  ? ok('a card opened outside the map floats in <body>, not inside the map')
  : bad('the row card is not a floating card in <body>');

click(dr, dr.querySelector('.conf-bar[data-conf="conf:trieste-photo"] text'));
rc = dr.querySelector('.conf-card');
dr.querySelectorAll('.conf-card').length === 1 && rc && /Neutrino Physics in Trieste/.test(rc.textContent)
  ? ok('a bar\'s label opens the card too, replacing the previous one')
  : bad('a bar label did not open its card (or left the old one open)');
rc && rc.querySelector('.conf-card__photo img') && /SISSA, Trieste/.test(rc.textContent)
  ? ok('the card shows the city photo from the marker and the row\'s own place')
  : bad('the label card lost the photo or the place');

const nm = dr.querySelector('.conf-bar[data-conf="conf:nomap"]');
nm.getAttribute('role') === 'button' && nm.getAttribute('tabindex') === '0'
  ? ok('timeline bars become keyboard buttons') : bad('timeline bars are not focusable');
nm.focus();
nm.dispatchEvent(new dr.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
rc = dr.querySelector('.conf-card');
rc && /Unplaced Workshop/.test(rc.textContent) && !rc.querySelector('a[href*="google.com/maps"]')
  && !rc.querySelector('.conf-card__title a')
  ? ok('Enter opens it; with no marker and no URL there is no Maps link and no title link')
  : bad('the unplaced, unlinked card is wrong');
dr.dispatchEvent(new dr.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
!dr.querySelector('.conf-card')
  ? ok('Escape closes it') : bad('Escape did not close the row card');

click(dr, dr.querySelector('.conf-list b'));
rc = dr.querySelector('.conf-card');
rc && /Erice School 2026/.test(rc.textContent)
  && [...rc.querySelectorAll('a')].some(a => a.href === 'https://erice.example.org/')
  ? ok('a click on a list row opens the card with the conference link')
  : bad('a list row click did not open the card');
click(dr, dr.body);
!dr.querySelector('.conf-card') ? ok('a click elsewhere closes it') : bad('the card stayed open');
const la = dr.querySelector('.conf-list a');
let ev = click(dr, la);
ev.defaultPrevented && dr.querySelector('.conf-card')
  ? ok('a plain click on "Details" opens the card instead of navigating')
  : bad('"Details" did not open the card');
click(dr, dr.body);
ev = click(dr, la, { metaKey: true });
!ev.defaultPrevented && !dr.querySelector('.conf-card')
  ? ok('a modifier-click on "Details" is left to the browser (new tab)')
  : bad('a modifier-click was intercepted');
la.closest('li').hasAttribute('tabindex')
  ? bad('a linked row got an extra tab stop')
  : ok('a linked row adds no tab stop of its own');

const d0 = bootRows(false);
click(d0, d0.querySelector('.conf-bar rect'));
rc = d0.querySelector('.conf-card');
rc && /NuFact 2026/.test(rc.textContent) && !rc.querySelector('a[href*="google.com/maps"]')
  ? ok('with no map on the page the timeline still opens the card (no Maps link)')
  : bad('without the map the timeline card fails');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
