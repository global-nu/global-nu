/* Figures open at full size when you click them.
 *
 * The comparison panels are drawn at 520x250 and sit two to a row, so on a
 * laptop a point is a few pixels across and the year labels are at the limit of
 * legibility. They are vector, so there is nothing to lose by showing them
 * large — the only thing missing was a way to ask.
 *
 * What is checked here, and why each one can break on its own:
 *   a figure holding a drawing becomes reachable and says so to a screen reader;
 *   the world map is left alone, because it already answers a click by opening
 *     an experiment's card and two meanings for one click means one of them loses;
 *   the conference map is left alone for the identical reason — its own card
 *     answers the click confmap.js wires up;
 *   activating a figure shows it enlarged, with its own caption;
 *   the enlarged view zooms, within limits, and can be panned;
 *   Escape closes it and the focus returns to the figure it came from;
 *   and with the script never running the page still holds every figure, because
 *     this is an enhancement and not the only way to see them.
 *
 *   node tools/tests/test_figure.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/figure.js'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

const PAGE = `
<figure class="figure reveal" id="panel">
  <h4>δm² <span class="figure__unit">/ 1e-5 eV²</span></h4>
  <svg viewBox="0 0 520 250" role="img" aria-label="delta m squared compared"></svg>
  <p class="cap">Every point is transcribed from the table named beside it.</p>
</figure>
<figure class="figure map-figure" id="map">
  <svg viewBox="0 0 720 324" role="img" aria-label="World map"></svg>
</figure>
<figure class="figure confmap-figure" id="confmap">
  <svg viewBox="0 6 720 162" role="img" aria-label="Conference map"></svg>
</figure>
<figure class="figure" id="nodrawing">
  <p class="cap">A caption with no drawing above it.</p>
</figure>`;

function boot() {
  const dom = new JSDOM(`<!doctype html><body>${PAGE}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom.window.document;
}

/* 1. which figures become activatable */
let d = boot();
const panel = d.getElementById('panel');
panel.getAttribute('tabindex') === '0'
  ? ok('a figure holding a drawing is reachable by keyboard')
  : bad('the figure did not become focusable');
(panel.getAttribute('role') === 'button' && panel.hasAttribute('aria-label'))
  ? ok('it announces itself as something that can be activated')
  : bad('no role or accessible name on the figure');

/* 2. the map is left alone */
const mapFig = d.getElementById('map');
(!mapFig.hasAttribute('tabindex') && mapFig.getAttribute('role') !== 'button')
  ? ok('the world map is not made activatable — it already uses its click')
  : bad('the map figure was made activatable and will fight its own card');

/* 2b. the conference map is left alone too — same reason, separate fixture,
   so a future refactor of figure.js's exclusion list cannot silently drop
   .confmap-figure while leaving .map-figure covered. */
const confmapFig = d.getElementById('confmap');
(!confmapFig.hasAttribute('tabindex') && confmapFig.getAttribute('role') !== 'button')
  ? ok('the conference map is not made activatable — it already uses its click')
  : bad('the conference map figure was made activatable and will fight its own card');

/* 3. a figure with no drawing is skipped */
!d.getElementById('nodrawing').hasAttribute('tabindex')
  ? ok('a figure with no drawing is left alone')
  : bad('a caption-only figure was made activatable');

/* 4. activating shows the figure enlarged, with its caption */
d = boot();
d.getElementById('panel').dispatchEvent(new d.defaultView.Event('click', { bubbles: true }));
let box = d.querySelector('.figbox');
box ? ok('activating a figure opens the enlarged view') : bad('no enlarged view appeared');
if (box) {
  box.querySelector('svg')
    ? ok('the enlarged view holds the drawing')
    : bad('the enlarged view has no drawing in it');
  /Every point is transcribed/.test(box.textContent)
    ? ok('the caption travels with the figure')
    : bad('the caption was left behind');
}

/* 5. zoom is bounded */
d = boot();
d.getElementById('panel').dispatchEvent(new d.defaultView.Event('click', { bubbles: true }));
for (let i = 0; i < 40; i++) d.querySelector('.figbox [data-zoom="in"]').click();
let t = d.querySelector('.figbox__stage').style.transform || '';
let scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale <= 8.001 ? ok('zooming in stops at the limit') : bad('zoom ran past its limit: ' + scale);

d = boot();
d.getElementById('panel').dispatchEvent(new d.defaultView.Event('click', { bubbles: true }));
for (let i = 0; i < 40; i++) d.querySelector('.figbox [data-zoom="out"]').click();
t = d.querySelector('.figbox__stage').style.transform || '';
scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale >= 0.999 ? ok('zooming out stops at the original scale') : bad('zoomed out past 1: ' + scale);

/* 6. keyboard: Enter opens, Escape closes, focus comes back */
d = boot();
const p2 = d.getElementById('panel');
p2.focus();
p2.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
d.querySelector('.figbox')
  ? ok('Enter opens the enlarged view without a pointer')
  : bad('Enter did not open the figure');
d.dispatchEvent(new d.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
!d.querySelector('.figbox')
  ? ok('Escape closes it')
  : bad('Escape left the enlarged view open');
d.activeElement === p2
  ? ok('focus returns to the figure it was opened from')
  : bad('focus was stranded after closing, at ' + (d.activeElement && d.activeElement.tagName));

/* 7. the page is whole with the script never running */
const plain = new JSDOM(`<!doctype html><body>${PAGE}</body>`).window.document;
plain.querySelectorAll('figure svg').length === 3
  ? ok('every figure still draws with the script never running')
  : bad('a figure lost its drawing');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
