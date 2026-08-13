/* The map's behaviour, tested rather than assumed.
 *
 * Six things, each of which can break on its own:
 *   zoom stays inside its limits; panning moves the group; a legend toggle
 *   hides one kind and only that kind; clicking a marker opens its card with
 *   the right name; a shared site fans out into one child per experiment;
 *   and every control is reachable from the keyboard.
 *
 *   node tools/tests/test_map.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/map.js'), 'utf8');

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
        <g class="map-exp" data-experiment="Double Chooz" data-kind="reactor"></g>
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
plain.querySelectorAll('.map-pin title').length === 2
  ? ok('every marker keeps its <title>, so the map reads with JS off')
  : bad('a marker lost its <title>');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
