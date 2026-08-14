/* Contrast check for the homepage mockups.
 *
 * Colours that look fine to the author on their own monitor are exactly the
 * ones that fail here, which is the point. Every foreground/background pair
 * each mockup actually uses is measured against WCAG 2.1: body text must
 * clear 4.5:1, large text and non-text borders 3:1.
 *
 * A design direction that cannot pass this is not a candidate.
 *
 *   node tools/tests/test_mockup_contrast.js
 */
const fs = require('fs');
const path = require('path');

const DIR = path.join(__dirname, '..', '..', 'mockups');

/* Pairs to measure, as [foreground token, background token, minimum ratio].
 * Same set for every mockup: the mockups differ in palette, not in what the
 * page is made of. */
const PAIRS = [
  ['--text', '--bg', 4.5],
  ['--text', '--surface', 4.5],
  ['--text-soft', '--bg', 4.5],
  ['--text-soft', '--surface', 4.5],
  ['--text-mute', '--bg', 4.5],
  ['--text-mute', '--surface', 4.5],
  ['--accent', '--bg', 4.5],
  ['--accent', '--surface', 4.5],
  ['--on-accent', '--accent', 4.5],
];
/* Accents used as data colours: lines and large numerals, so 3:1 applies. */
const LARGE = [
  ['--no', '--bg', 3],
  ['--io', '--bg', 3],
  ['--no', '--surface', 3],
  ['--io', '--surface', 3],
  ['--accent-2', '--bg', 3],
  ['--accent-warm', '--bg', 3],
];

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

/* Read the token block introduced by `selector` out of a <style> element. */
function blockAfter(css, selector) {
  const i = css.indexOf(selector);
  if (i < 0) return null;
  const open = css.indexOf('{', i);
  const body = css.slice(open + 1, css.indexOf('}', open));
  const out = {};
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

/* index.html is the chooser page that lists the three mockups side by side, not
 * a mockup itself: it is hand-written with literal colours and carries no theme
 * token blocks. Globbing every .html in the directory made it report two
 * missing blocks as if they were two failing colour pairs — a red test that
 * said nothing true, which is worse than no test, because a red one people
 * learn to ignore stops protecting the ones that matter. */
const NOT_A_MOCKUP = new Set(['index.html']);

let failures = 0;
for (const file of fs.readdirSync(DIR)
       .filter(f => f.endsWith('.html') && !NOT_A_MOCKUP.has(f)).sort()) {
  const css = fs.readFileSync(path.join(DIR, file), 'utf8');
  console.log('\n' + file);
  for (const theme of ['dark', 'light']) {
    const vars = blockAfter(css, `:root[data-theme="${theme}"]`);
    if (!vars) { console.log(`  ! no ${theme} token block`); failures++; continue; }
    for (const [fgName, bgName, min] of PAIRS.concat(LARGE)) {
      const fg = vars[fgName] && toRGB(vars[fgName]);
      const bg = vars[bgName] && toRGB(vars[bgName]);
      if (!fg || !bg) continue;                    // token absent in this mockup
      const r = ratio(fg, bg);
      const pass = r >= min;
      if (!pass) failures++;
      console.log(
        `  ${pass ? 'ok  ' : 'FAIL'} ${theme.padEnd(5)} ${fgName} on ${bgName}` +
        `  ${r.toFixed(2)}:1 (min ${min})`);
    }
  }
}

console.log(failures ? `\n${failures} failing pair(s)` : '\nall measured pairs pass');
process.exit(failures ? 1 : 0);
