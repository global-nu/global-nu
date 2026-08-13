/* The map's behaviour, tested rather than assumed.
 *
 * Zoom stays inside its limits; panning moves the group; a legend toggle
 * hides one kind and only that kind; clicking a marker opens its card with
 * the right name; a shared site fans out into one child per experiment; a
 * photo credit renders with its author, licence and Commons link; every
 * marker — not just the legend — is reachable and operable from the
 * keyboard; the card manages focus like a dialog instead of merely being
 * labelled one; a real pointer sequence (not a synthetic click) still opens
 * a marker's card, distinguishing a tap from a drag; and the toolbar and the
 * card are anchored to different corners so a tall card can never cover the
 * controls.
 *
 *   node tools/tests/test_map.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/map.js'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'site-src/assets/css/site.css'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

const SVG = `
<figure class="figure map-figure">
  <svg id="m" viewBox="0 0 720 324">
    <g class="map-layer">
      <g class="map-pin" data-site="kamioka" data-kinds="natural accelerator"
         data-names="Super-Kamiokande|T2K" data-fan="1" transform="translate(600,120)">
        <title>Kamioka</title>
        <g class="map-exp" data-experiment="Super-Kamiokande" data-kind="natural"></g>
        <g class="map-exp" data-experiment="T2K" data-kind="accelerator"></g>
      </g>
      <g class="map-pin" data-site="chooz" data-kinds="reactor"
         data-names="Double Chooz" transform="translate(350,90)">
        <title>Double Chooz</title>
        <circle cx="350" cy="90" r="4"/>
        <g class="map-exp" data-experiment="Double Chooz" data-kind="reactor"></g>
      </g>
      <g class="map-pin" data-site="jiangmen" data-kinds="reactor"
         data-names="JUNO" transform="translate(500,150)">
        <title>Jiangmen</title>
        <g class="map-exp" data-experiment="JUNO" data-kind="reactor"
           data-photo="images/juno-detector.jpg"
           data-photo-alt="The JUNO detector, labelled"
           data-photo-author="JUNO Collaboration"
           data-photo-licence="CC BY 4.0"
           data-photo-licence-url="https://creativecommons.org/licenses/by/4.0"
           data-photo-page="https://commons.wikimedia.org/wiki/File:Juno.jpg"></g>
      </g>
    </g>
  </svg>
  <div class="legend legend--chart">
    <span data-filter="reactor"><i></i>Reactor</span>
    <span data-filter="natural"><i></i>Natural</span>
  </div>
</figure>`;

function boot() {
  const dom = new JSDOM(`<!doctype html><body>${SVG}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom.window.document;
}

/* 1. controls are injected and reachable */
let d = boot();
const zoomIn = d.querySelector('.map-ctl [data-zoom="in"]');
zoomIn ? ok('a zoom-in control is provided') : bad('no zoom-in control');
if (zoomIn && zoomIn.tagName === 'BUTTON') ok('the control is a button, so it is focusable');
else bad('the zoom control is not a button');

/* 2. zoom is bounded */
d = boot();
for (let i = 0; i < 40; i++) d.querySelector('[data-zoom="in"]').click();
let t = d.querySelector('.map-layer').getAttribute('transform') || '';
let scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale <= 8.001 ? ok('zooming in stops at the limit') : bad('zoom ran past its limit: ' + scale);

d = boot();
for (let i = 0; i < 40; i++) d.querySelector('[data-zoom="out"]').click();
t = d.querySelector('.map-layer').getAttribute('transform') || '';
scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale >= 0.999 ? ok('zooming out stops at the original scale') : bad('zoomed out past 1: ' + scale);

/* 3. markers keep their screen size */
d = boot();
d.querySelector('[data-zoom="in"]').click();
const pin = d.querySelector('.map-pin');
pin.getAttribute('transform').indexOf('scale') > -1
  ? ok('markers counter-scale so they stay the same size on screen')
  : bad('markers do not counter-scale and will grow into blobs');

/* 4. a legend entry filters its kind and only its kind */
d = boot();
d.querySelector('[data-filter="reactor"]').click();
const chooz = d.querySelector('[data-site="chooz"]');
const kamioka = d.querySelector('[data-site="kamioka"]');
chooz.hasAttribute('hidden') ? ok('turning off a kind hides its markers')
                             : bad('the filter did not hide the reactor marker');
!kamioka.hasAttribute('hidden') ? ok('a marker of another kind is untouched')
                                : bad('the filter hid an unrelated marker');

/* 5. clicking a marker opens a card naming it */
d = boot();
d.querySelector('[data-site="chooz"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const card = d.querySelector('.map-card');
card && /Double Chooz/.test(card.textContent)
  ? ok('clicking a marker opens a card naming the experiment')
  : bad('no card, or the card does not name the experiment');

/* 6. a shared site fans out */
d = boot();
d.querySelector('[data-site="kamioka"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const shown = [...d.querySelectorAll('[data-site="kamioka"] .map-exp')]
  .filter(g => !g.hasAttribute('hidden'));
shown.length === 2 ? ok('a shared site fans out into one child per experiment')
                   : bad('the fan-out revealed ' + shown.length + ' of 2');

/* 7. the SVG stays readable with the script never running */
const plain = new JSDOM(`<!doctype html><body>${SVG}</body>`).window.document;
plain.querySelectorAll('.map-pin title').length === 3
  ? ok('every marker keeps its <title>, so the map reads with JS off')
  : bad('a marker lost its <title>');

/* 8. a photo credit renders with all three parts: author, licence, and a
   link to the file's own Commons page — photoBlock() in map.js, otherwise
   never exercised by this suite because no earlier fixture marker carried
   data-photo*. */
d = boot();
d.querySelector('[data-site="jiangmen"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const photoCard = d.querySelector('.map-card');
const photoImg = photoCard && photoCard.querySelector('.map-card__photo img');
const credit = photoCard && photoCard.querySelector('.map-card__credit');
photoImg && photoImg.getAttribute('src') === 'images/juno-detector.jpg'
  ? ok('a photo credit renders an <img> with the expected src')
  : bad('no photo <img>, or the wrong src');
credit && /JUNO Collaboration/.test(credit.textContent)
  ? ok('the credit names the author')
  : bad('the credit is missing the author');
credit && [...credit.querySelectorAll('a')].some(a =>
    a.textContent === 'CC BY 4.0' && a.href.indexOf('creativecommons.org') > -1)
  ? ok('the credit links the licence')
  : bad('the credit does not link the licence');
credit && [...credit.querySelectorAll('a')].some(a =>
    a.textContent === 'Wikimedia Commons' && a.href.indexOf('commons.wikimedia.org') > -1)
  ? ok("the credit links to the photo's own page on Commons")
  : bad('the credit does not link to Commons');

/* 9. markers are reachable from the keyboard, not just the legend */
d = boot();
const choozKb = d.querySelector('[data-site="chooz"]');
choozKb.getAttribute('tabindex') === '0'
  ? ok('a marker is a keyboard tab stop')
  : bad('a marker has no tabindex, so it cannot be reached from the keyboard');
choozKb.focus();
choozKb.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
const kbCard = d.querySelector('.map-card');
kbCard && /Double Chooz/.test(kbCard.textContent)
  ? ok('pressing Enter on a focused marker opens its card, same as a click')
  : bad('Enter on a focused marker did not open its card');

/* 10. the card manages focus: opening moves focus in, Escape returns it to
   the marker that opened it — without this a role="dialog" is announced but
   does not behave like one. */
d = boot();
const choozFocus = d.querySelector('[data-site="chooz"]');
choozFocus.focus();
choozFocus.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
const opened = d.querySelector('.map-card');
opened && opened.contains(d.activeElement)
  ? ok('opening the card moves focus into it')
  : bad('the card opened but focus stayed outside it');
d.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
(!d.querySelector('.map-card') && d.activeElement === choozFocus)
  ? ok('Escape closes the card and returns focus to the marker that opened it')
  : bad('focus did not return to the opening marker after Escape');

/* 11. Tab does not walk focus out of an open card. Uses the JUNO marker
   rather than Double Chooz: its card's only focusable elements would
   otherwise be the lone close button, where "first" and "last" are the same
   element and the check would pass trivially even with no trap at all — the
   photo credit's two links give the card enough focusable elements for
   wrapping to mean something. */
d = boot();
d.querySelector('[data-site="jiangmen"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const dlg = d.querySelector('.map-card');
const focusables = [...dlg.querySelectorAll('button, a[href], [tabindex]:not([tabindex="-1"])')];
focusables.length > 1
  ? ok('the card has more than one focusable element, so the wrap check below is meaningful')
  : bad('the card has only one focusable element (' + focusables.length + '); the wrap check cannot bite');
focusables[focusables.length - 1].focus();
dlg.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
d.activeElement === focusables[0]
  ? ok('Tab from the last focusable element in the card wraps back to the first')
  : bad('Tab escaped the open card instead of being trapped inside it');

/* 12. a real pointer sequence — not the synthetic `click` check 5 uses —
   still opens a marker's card, and a drag that passes through a marker does
   not pop it open as a side effect. This is the path the previous
   implementer's browser testing found broken: an earlier version of map.js
   called svg.setPointerCapture(e.pointerId) on every pointerdown, which in
   a real browser redirects the pointerup/mouseup target to the capturing
   element and silently stops a native `click` from ever synthesizing — so
   no marker could be opened by an actual click, only by a synthetic
   dispatchEvent(new Event('click')), exactly what check 5 above does. That
   is why check 5 kept passing while real clicks were broken (see the
   comment in map.js's wireInteractions). Two things below would have failed
   against that code: setPointerCapture must never be called (jsdom does not
   model the browser's click-suppression itself, so this is the faithful
   jsdom-testable proxy for "a real click still fires"), and pointermove/up
   dispatched on `document` — not `svg` — must still be picked up, which is
   what actually lets a drag that crosses a marker suppress that marker's
   click. */
d = boot();
const PointerEvent = d.defaultView.PointerEvent;
const choozPtr = d.querySelector('[data-site="chooz"]');
const svgPtr = d.querySelector('svg');
let capturedCalled = false;
svgPtr.setPointerCapture = function () { capturedCalled = true; };

// a small, click-like sequence: down and up within the drag threshold
choozPtr.dispatchEvent(new PointerEvent('pointerdown',
  { bubbles: true, pointerId: 1, clientX: 10, clientY: 10 }));
d.dispatchEvent(new PointerEvent('pointermove',
  { bubbles: true, pointerId: 1, clientX: 11, clientY: 10 }));
d.dispatchEvent(new PointerEvent('pointerup',
  { bubbles: true, pointerId: 1, clientX: 11, clientY: 10 }));
!capturedCalled
  ? ok('a pointer sequence never calls setPointerCapture, so a real click still fires')
  : bad('setPointerCapture was called, which silently breaks native clicks in a real browser');

choozPtr.dispatchEvent(new d.defaultView.Event('click', { bubbles: true }));
const tapCard = d.querySelector('.map-card');
tapCard && /Double Chooz/.test(tapCard.textContent)
  ? ok('the click that follows a small pointer sequence still opens the card')
  : bad('a real pointer-down/up sequence left the card unopened');

// a genuine drag: down, then well past the drag threshold, released on
// `document` rather than back over the marker
d = boot();
const choozDrag = d.querySelector('[data-site="chooz"]');
choozDrag.dispatchEvent(new d.defaultView.PointerEvent('pointerdown',
  { bubbles: true, pointerId: 2, clientX: 10, clientY: 10 }));
d.dispatchEvent(new d.defaultView.PointerEvent('pointermove',
  { bubbles: true, pointerId: 2, clientX: 60, clientY: 10 }));
d.dispatchEvent(new d.defaultView.PointerEvent('pointerup',
  { bubbles: true, pointerId: 2, clientX: 60, clientY: 10 }));
choozDrag.dispatchEvent(new d.defaultView.Event('click', { bubbles: true }));
!d.querySelector('.map-card')
  ? ok('a drag that passes through a marker does not pop its card open')
  : bad('a drag opened the card as an unwanted side effect');

/* 13. the toolbar and the card anchor to different corners, so a tall card
   can never grow over the controls (found only by looking, in a real
   browser, at the Assergi fan of eight experiments). */
function corner(selector) {
  const re = new RegExp(selector.replace(/[.]/g, '\\.') + '\\{([^}]*)\\}');
  const m = css.match(re);
  if (!m) return null;
  const body = m[1];
  const vert = /(^|;)\s*top\s*:/.test(body) ? 'top'
             : /(^|;)\s*bottom\s*:/.test(body) ? 'bottom' : null;
  const horiz = /(^|;)\s*left\s*:/.test(body) ? 'left'
              : /(^|;)\s*right\s*:/.test(body) ? 'right' : null;
  return vert && horiz ? vert + '-' + horiz : null;
}
const ctlCorner = corner('.map-ctl');
const cardCorner = corner('.map-card');
ctlCorner && cardCorner && ctlCorner !== cardCorner
  ? ok('the toolbar (' + ctlCorner + ') and the card (' + cardCorner + ') anchor to different corners')
  : bad('the toolbar (' + ctlCorner + ') and the card (' + cardCorner + ') can occupy the same corner');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
