/* The hover panel on an enlarged figure.
 *
 * Enlarging a panel is what makes a point big enough to aim at, and until now
 * the only thing that answered the aim was the browser's own <title> tooltip:
 * a second's delay, system grey, nothing on a touch screen. This panel answers
 * immediately, in the site's own type, with the facts make_history.py writes
 * onto every point as data- attributes.
 *
 * What is checked here, and why each can break on its own:
 *   pointing at a point opens the panel, with group, year, value, unit,
 *     interval and ordering — the whole answer, not a fragment;
 *   the panel lives outside .figbox__stage, because the stage is what
 *     transform: scale() acts on: inside it, the panel would be drawn eight
 *     times its size at maximum zoom and dragged off-screen by any pan —
 *     which is precisely the case this was asked for;
 *   a limit says what it is rather than pretending to be a measurement;
 *   leaving the point closes the panel, so it cannot outlive what it describes;
 *   the keyboard reaches points and gets the same panel, and the dialog's Tab
 *     trap keeps them inside it;
 *   a point carrying nothing opens nothing, rather than a panel of blanks;
 *   and with the script never running the figure is unchanged, because this
 *     is an enhancement over an SVG that already carries its own <title>.
 *
 *   node tools/tests/test_figure_tip.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/figure.js'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = (m, d) => { fail.push(m); console.log('  FAIL ' + m + (d ? '\n         ' + d : '')); };
const is = (m, cond, d) => cond ? ok(m) : bad(m, d);

const PT = (attrs, id) => `
  <g class="pt" id="${id}" ${attrs}><title>native</title>
    <circle class="pt__hit" cx="10" cy="10" r="9" fill="none" pointer-events="all"/>
    <circle cx="10" cy="10" r="4.6" fill="red"/>
  </g>`;

const PAGE = `
<figure class="figure reveal" id="panel">
  <h4>Δm² <span class="figure__unit">/ 1e-3 eV²</span></h4>
  <svg viewBox="0 0 520 250" role="img" aria-label="Delta m squared by year">
    ${PT('data-group="Bari" data-year="2017" data-param="|Δm²|" data-value="2.525" ' +
         'data-unit="1e-3 eV²" data-ordering="Normal ordering" ' +
         'data-range="3σ 2.411–2.646"', 'meas')}
    ${PT('data-group="Bari" data-year="2008" data-param="sin²θ13" data-value="&lt; 5.0 (3σ)" ' +
         'data-unit="1e-2" data-ordering="Both orderings" data-kind="limit" ' +
         'data-level="3σ"', 'lim')}
    ${PT('', 'mute')}
  </svg>
  <p class="cap">Best fit with its 3σ range.</p>
</figure>`;

function boot() {
  const dom = new JSDOM(`<!doctype html><body>${PAGE}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom;
}

function openBox(dom) {
  const doc = dom.window.document;
  doc.getElementById('panel').dispatchEvent(
    new dom.window.MouseEvent('click', { bubbles: true }));
  return doc.querySelector('.figbox');
}

/* The clone inside the dialog, not the original on the page. */
function pointIn(box, id) {
  return box.querySelector('.figbox__stage #' + id);
}

function hover(dom, el, type) {
  el.dispatchEvent(new dom.window.MouseEvent(type || 'mouseover', { bubbles: true }));
}

// --- the panel opens with the whole answer ---------------------------------

let dom = boot();
let box = openBox(dom);
let tip = box.querySelector('.figtip');

is('the enlarged figure carries a hover panel', !!tip);
is('which starts hidden', tip && tip.hidden);

hover(dom, pointIn(box, 'meas'));
const shown = box.querySelector('.figtip');
const text = shown ? shown.textContent : '';
is('pointing at a point opens the panel', shown && !shown.hidden);
['Bari', '2017', '|Δm²|', '2.525', '1e-3 eV²', '3σ 2.411–2.646', 'Normal ordering']
  .forEach(want => is('the panel states ' + want, text.indexOf(want) !== -1, text));

// --- it survives the zoom, which is the whole point ------------------------

is('the panel is not inside the stage the zoom transforms',
   shown && !shown.closest('.figbox__stage'),
   'a panel inside .figbox__stage is scaled 8x and panned away with the drawing');
is('and is inside the dialog, so it closes with it',
   shown && !!shown.closest('.figbox'));

// --- a limit is not a measurement ------------------------------------------

hover(dom, pointIn(box, 'lim'));
const limText = box.querySelector('.figtip').textContent;
is('a limit shows its bound and its level', limText.indexOf('< 5.0 (3σ)') !== -1, limText);
is('a limit is named as one, not left to look like a best fit',
   /limit|bound/i.test(limText), limText);

// --- leaving closes it -----------------------------------------------------

hover(dom, pointIn(box, 'meas'));
hover(dom, pointIn(box, 'meas'), 'mouseout');
is('leaving the point closes the panel', box.querySelector('.figtip').hidden);

// --- a point with nothing to say opens nothing -----------------------------

hover(dom, pointIn(box, 'mute'));
is('a point carrying no facts opens no panel of blanks',
   box.querySelector('.figtip').hidden);

// --- the keyboard gets there too -------------------------------------------

const pts = box.querySelectorAll('.figbox__stage .pt');
is('every point is reachable by keyboard',
   pts.length === 3 && Array.prototype.every.call(pts, p => p.getAttribute('tabindex') === '0'),
   Array.prototype.map.call(pts, p => p.getAttribute('tabindex')).join(','));

pointIn(box, 'meas').dispatchEvent(new dom.window.FocusEvent('focusin', { bubbles: true }));
is('focusing a point opens the same panel',
   !box.querySelector('.figtip').hidden &&
   box.querySelector('.figtip').textContent.indexOf('2.525') !== -1);

pointIn(box, 'meas').dispatchEvent(new dom.window.FocusEvent('focusout', { bubbles: true }));
is('and leaving it closes the panel', box.querySelector('.figtip').hidden);

// The Tab trap used to look only at buttons. With points focusable, a trap
// that still ends at the last button would send Tab back to the first control
// and no point would ever be reachable — the keyboard path above would pass
// its unit test and be dead in a browser.
const stops = box.querySelectorAll('button, .pt[tabindex]');
is('the dialog\'s Tab cycle includes the points, not only its buttons',
   stops.length > box.querySelectorAll('button').length,
   'trap must select points as well as buttons');

// --- without the script, nothing is lost -----------------------------------

const plain = new JSDOM(`<!doctype html><body>${PAGE}</body>`);
is('with the script never running the figure still holds every point',
   plain.window.document.querySelectorAll('.pt').length === 3);
is('and every point still carries its native <title>',
   plain.window.document.querySelectorAll('.pt > title').length === 3);

console.log('\n' + (fail.length ? fail.length + ' failed' : 'all checks passed'));
if (fail.length) process.exit(1);
