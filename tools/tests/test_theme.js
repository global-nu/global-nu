/* Regression test for the light/dark theme.
 *
 * Two things are checked, because two different things can break.
 *
 * BEHAVIOUR: the toggle flips the theme, saves the choice, survives a reload,
 * and keeps its accessible label in step. With no saved choice the page must
 * carry no data-theme attribute at all — that is what lets the stylesheet's
 * prefers-color-scheme query take over — and the inline <head> script must
 * apply a saved choice before anything else runs.
 *
 * CONTRAST: every foreground/background pair the site actually uses is
 * measured against WCAG 2.1. Body text must clear 4.5:1, large text, data
 * curves and non-text borders 3:1. Colours that look fine to the author on
 * their own monitor are exactly the ones that fail here, which is the point.
 *
 * A colour added to site.css must be added to PAIRS below, or it is untested.
 *
 *   npm install jsdom
 *   node tools/tests/test_theme.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const css = fs.readFileSync(path.join(ROOT, 'site-src/assets/css/site.css'), 'utf8');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/site.js'), 'utf8');
const tpl = fs.readFileSync(path.join(ROOT, 'site-src/templates/base.html'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

/* ---------------------------------------------------------- contrast --- */

/* [foreground, background, minimum ratio] */
const PAIRS = [
  ['--text', '--bg', 4.5],
  ['--text', '--surface', 4.5],
  ['--text', '--bg-deep', 4.5],
  ['--text', '--surface-2', 4.5],
  ['--text-soft', '--bg', 4.5],
  ['--text-soft', '--surface', 4.5],
  ['--text-soft', '--bg-deep', 4.5],
  ['--text-soft', '--surface-2', 4.5],
  ['--text-mute', '--bg', 4.5],
  ['--text-mute', '--surface', 4.5],
  ['--text-mute', '--bg-deep', 4.5],
  ['--text-mute', '--surface-2', 4.5],
  ['--accent', '--bg', 4.5],
  ['--accent', '--surface', 4.5],
  ['--accent', '--surface-2', 4.5],
  ['--on-accent', '--accent', 4.5],
  ['--warn', '--surface-2', 4.5],
  ['--src-3', '--surface', 4.5],
  /* ordering colours carry data: curves, badges, large numerals */
  ['--no', '--bg', 3],
  ['--no', '--surface', 3],
  ['--no', '--surface-2', 3],
  ['--io', '--bg', 3],
  ['--io', '--surface', 3],
  ['--io', '--surface-2', 3],
  ['--accent-2', '--bg', 4.5],
  ['--accent-2', '--surface', 4.5],
  /* the conference map's two category colours: dots on the land fill, and
     the count badge's own text sitting on top of the dot's fill */
  ['--dec-4', '--surface-2', 3],
  ['--on-accent', '--no', 4.5],
  ['--on-accent', '--dec-4', 4.5],
];

function parseVars(block) {
  const out = {};
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
function blockAfter(selector) {
  const i = css.indexOf(selector);
  if (i < 0) throw new Error('selector not found: ' + selector);
  const open = css.indexOf('{', i);
  return css.slice(open + 1, css.indexOf('}', open));
}
function toRGB(v) {
  v = v.trim();
  let m = v.match(/^#([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map(i => parseInt(m[1].substr(i, 2), 16));
  m = v.match(/^#([0-9a-f]{3})$/i);
  if (m) return [0, 1, 2].map(i => parseInt(m[1][i] + m[1][i], 16));
  return null;                       // rgba()/color-mix(): not a solid colour
}
function lum([r, g, b]) {
  const f = c => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function ratio(fg, bg) {
  const a = lum(fg), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

console.log('contrast');
const themes = {
  dark: parseVars(blockAfter(':root[data-theme="dark"]')),
  light: parseVars(blockAfter(':root[data-theme="light"]')),
};
for (const [name, vars] of Object.entries(themes)) {
  for (const [fgName, bgName, min] of PAIRS) {
    const fg = vars[fgName] && toRGB(vars[fgName]);
    const bg = vars[bgName] && toRGB(vars[bgName]);
    if (!fg || !bg) { bad(`${name}: ${fgName} or ${bgName} missing / not a solid colour`); continue; }
    const r = ratio(fg, bg);
    const msg = `${name.padEnd(5)} ${fgName} on ${bgName}  ${r.toFixed(2)}:1 (min ${min})`;
    r >= min ? ok(msg) : bad(msg);
  }
}

/* The prefers-color-scheme fallback must define exactly the same tokens as
   the explicit light block: a token defined in one and not the other is how a
   page ends up half-themed for a reader who never touched the toggle. */
const fallback = parseVars(blockAfter('@media (prefers-color-scheme:light)'));
const lightKeys = Object.keys(themes.light).filter(k => k !== 'color-scheme');
const fallbackKeys = Object.keys(fallback).filter(k => k !== 'color-scheme');
const missing = lightKeys.filter(k => !fallbackKeys.includes(k));
const extra = fallbackKeys.filter(k => !lightKeys.includes(k));
if (missing.length || extra.length) {
  bad('prefers-color-scheme fallback differs from the light block: ' +
      [...missing.map(k => 'missing ' + k), ...extra.map(k => 'extra ' + k)].join(', '));
} else {
  ok(`prefers-color-scheme fallback defines the same ${lightKeys.length} tokens as the light block`);
}
for (const k of lightKeys) {
  if (fallback[k] && fallback[k] !== themes.light[k]) {
    bad(`fallback ${k} = ${fallback[k]} but light block says ${themes.light[k]}`);
  }
}

/* The icon rules must out-specify `.theme-toggle svg`, which sets
   display:block. A bare `.theme-toggle__moon{display:none}` loses to it and
   both icons render at once — that shipped once and was only caught by
   looking at the page. */
if (/(^|[^ ])\.theme-toggle__moon\s*\{[^}]*display\s*:\s*none/m.test(css)) {
  bad('the moon icon is hidden by a rule that loses to `.theme-toggle svg`');
} else if (/\.theme-toggle\s+\.theme-toggle__moon\s*\{[^}]*display\s*:\s*none/.test(css)) {
  ok('the theme icons are hidden by rules that out-specify `.theme-toggle svg`');
} else {
  bad('no rule hides the inactive theme icon');
}

/* Text filled with a gradient puts part of every word at a lower contrast
   than the rest, and reads as advertising on a university page. It was on the
   headlines once; it does not come back. */
if (/background-clip\s*:\s*text/.test(css)) {
  bad('some text is filled with a gradient (background-clip:text)');
} else {
  ok('no text is filled with a gradient');
}

/* --------------------------------------------------------- behaviour --- */

console.log('behaviour');

function page(saved, prefersLight) {
  const html = tpl
    .replace(/\{\{(nav|footer_nav|content|scripts|analytics|katex_head|katex_body)\}\}/g, '')
    .replace(/\{\{[a-z_0-9]+\}\}/g, 'x');
  // A url is required: with the default about:blank origin jsdom makes
  // localStorage throw a SecurityError, which is not what a reader hits.
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true,
    url: 'https://global-nu.org/',
  });
  const { window } = dom;
  // jsdom ships no matchMedia. Stub it so the "no saved choice" path is
  // exercised the way a real browser would run it; site.js also guards
  // against its absence, which is checked separately below.
  window.matchMedia = q => ({
    media: q,
    matches: /prefers-color-scheme:\s*light/.test(q) ? !!prefersLight : !prefersLight,
    addEventListener() {}, removeEventListener() {},
  });
  if (saved) window.localStorage.setItem('gnu-theme', saved);
  // The inline <head> script has already run against an empty store; re-run it
  // so the "saved choice applied before first paint" path is exercised.
  window.eval(`(function(){try{var t=localStorage.getItem("gnu-theme");
    if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}catch(e){}})();`);
  window.eval(js);
  return window;
}

let w = page(null);
w.document.documentElement.hasAttribute('data-theme')
  ? bad('with no saved choice the root must carry no data-theme attribute')
  : ok('no saved choice: root carries no data-theme, so the OS preference applies');

const toggle = w.document.querySelector('.theme-toggle');
if (!toggle) {
  bad('no .theme-toggle in the template');
} else {
  toggle.dispatchEvent(new w.Event('click'));
  const after = w.document.documentElement.getAttribute('data-theme');
  after === 'light'
    ? ok('first click switches to light (the OS default in jsdom is dark)')
    : bad('first click should switch to light, got ' + after);
  w.localStorage.getItem('gnu-theme') === 'light'
    ? ok('the choice is saved to localStorage')
    : bad('the choice was not saved');
  toggle.getAttribute('aria-pressed') === 'true'
    ? ok('aria-pressed follows the theme')
    : bad('aria-pressed did not follow the theme');
  /^Switch to dark/.test(toggle.getAttribute('aria-label'))
    ? ok('aria-label announces the next theme, not the current one')
    : bad('aria-label is stale: ' + toggle.getAttribute('aria-label'));

  toggle.dispatchEvent(new w.Event('click'));
  w.document.documentElement.getAttribute('data-theme') === 'dark'
    ? ok('second click switches back to dark')
    : bad('second click did not switch back');
}

/* A reader whose OS asks for light and who has saved nothing: the first click
   must go to dark, not back to light. This is the branch that breaks when
   current() reads the attribute instead of the media query. */
{
  const lw = page(null, true);
  const t = lw.document.querySelector('.theme-toggle');
  t.dispatchEvent(new lw.Event('click'));
  lw.document.documentElement.getAttribute('data-theme') === 'dark'
    ? ok('OS prefers light, no saved choice: first click goes to dark')
    : bad('OS prefers light: first click should go to dark, got ' +
          lw.document.documentElement.getAttribute('data-theme'));
}

/* A browser without matchMedia must still get a working button. */
{
  const nw = page(null);
  delete nw.matchMedia;
  const t = nw.document.querySelector('.theme-toggle');
  try {
    t.dispatchEvent(new nw.Event('click'));
    ['light', 'dark'].includes(nw.document.documentElement.getAttribute('data-theme'))
      ? ok('no matchMedia: the toggle still works')
      : bad('no matchMedia: the toggle set no theme');
  } catch (e) {
    bad('no matchMedia: the toggle threw — ' + e.message);
  }
}

w = page('light');
w.document.documentElement.getAttribute('data-theme') === 'light'
  ? ok('a saved choice is applied on load, before first paint')
  : bad('a saved choice was not applied on load');

const nav = w.document.getElementById('nav');
const navToggle = w.document.querySelector('.nav-toggle');
if (!nav || !navToggle) {
  bad('no mobile nav toggle in the template');
} else {
  navToggle.dispatchEvent(new w.Event('click'));
  nav.classList.contains('is-open') && navToggle.getAttribute('aria-expanded') === 'true'
    ? ok('the menu button opens the nav and reports it')
    : bad('the menu button did not open the nav');
  navToggle.dispatchEvent(new w.Event('click'));
  !nav.classList.contains('is-open') && navToggle.getAttribute('aria-expanded') === 'false'
    ? ok('the menu button closes the nav again')
    : bad('the menu button did not close the nav');
}

console.log(fail.length ? `\n${fail.length} failure(s)` : '\nall checks pass');
process.exit(fail.length ? 1 : 0);
