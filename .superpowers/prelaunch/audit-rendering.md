# Pre-publication rendering/behaviour audit — global-nu

Date: 2026-08-14
Method: site served locally (`python3 -m http.server 8899` from `site/`), driven
headlessly with Playwright/Chromium (`.venv/bin/python3`). All screenshots are
in `.superpowers/prelaunch/shots/`. Read-only — nothing in the repo was
modified.

**Verdict: publishable as-is.** No Critical or Important findings. Two Minor
polish notes below; everything else the brief asked for came up clean, with
the verification method stated for each.

---

## Methodology note (worth recording, not a site bug)

The first screenshot pass used `page.screenshot(full_page=True)` immediately
after `goto()`. That produced two false alarms that were **not** real bugs:

1. Large blank gaps below the fold on `index.html` — caused by the site's
   `.reveal` scroll-triggered `IntersectionObserver` (`assets/js/site.js`),
   which only adds the `is-in` (opacity:1) class once an element has actually
   scrolled into the viewport. A full-page screenshot taken without scrolling
   never triggers it.
2. The sticky header (`assets/css/site.css:204`, `position:sticky`) appearing
   twice, once at its natural position and once "stuck" mid-page — an
   artifact of Playwright's full-page capture combined with a non-zero
   scroll position at capture time.

Fixed by re-running the capture: scroll the full page in 600px increments
(triggering the observer), then `scrollTo(0,0)` before the full-page
screenshot. All 63 screenshots referenced below are from the corrected run.
Flagging this because it's exactly the kind of thing a screenshot-only audit
would have reported as a broken figure/duplicated header when it was neither.

---

## 1. Every page, both themes, three widths

Covered: index, results, history, digest, news, conferences, resources,
search, about, 404 × {light, dark} × {1280, 700, 375} = 60 screenshots, named
`shots/<page>-<theme>-<width>.png`, plus interaction screenshots.

Reviewed all 60 at full size, with close crops (via PIL) of the history.html
comparison panels and index.html stat cards in both themes at native
resolution. No overlapping labels, no clipped text, no illegible small text,
no failed figure renders, no dark-on-dark/light-on-light patches found.

Also ran an automated horizontal-overflow check (`document.body.scrollWidth`
vs `window.innerWidth`) across all 10 pages × 3 widths = 30 combinations:
**zero pages overflow horizontally at any width.** Tables that are wider than
their column (e.g. the releases table and the CSV/JSON schema table on
history.html at 375px) are correctly contained in `.table-scroll` wrappers
that scroll internally — verified this is by design, not breakage.

Clean: index stat cards (both themes, all widths) and history.html comparison
panels (both themes, all widths, checked via magnified crops) — the two
areas called out for close reading — render sharp axis text, correctly
placed 3σ error bars, and correct light/dark contrast.

## 2. Console errors

Captured `page.on("console")` and `page.on("pageerror")` on all 60 page
loads. Result: **zero page errors anywhere**; the only console output on
every single page is one benign warning —
`goatcounter: not counting because of: localhost` — which is goatcounter's
documented behaviour when the analytics beacon is loaded from `localhost`
and does not occur on the real domain. No other warnings or errors.

(One additional, expected console error appeared only on search.html when a
query is run — see §5.)

## 3. Figure zoom

**history.html (SVG panel):** measured the panel's `<svg>` bounding box
before opening (261×126px, on-page) and the overlay's `<svg>` bounding box
after opening (1184×710px) — a genuine ~4.5× area enlargement, not the
"opened but same size" failure mode. Zoom-in button applies
`transform: scale(1.5)`; drag-to-pan applies a matching `translate()`;
Escape removes the overlay and returns focus (see §9). Screenshots:
`history-zoom-open.png`, `history-zoom-in.png`, `history-zoom-drag.png`.

**results.html (PNG figure):** opened the first `<img>`-based figure
(`prd111-093006-fig3-global-projections.png`, natural resolution
1445×1060). On-page box 1044×766 → overlay box 1184×668, i.e. displayed
close to native resolution and stayed crisp (screenshot
`results-zoom-open.png`) — no visible upscaling blur at this size.

**375px width:** opened a history.html figure at mobile width. Toolbar
(`.figbox__bar`, 343px wide) and caption (`.figbox__cap`, 343px wide) both
fit fully inside the 375px viewport with no clipping (measured
programmatically, confirmed against screenshot `history-zoom-375.png`).

**Minor (polish, not a bug):** at 375px the SVG panel itself has large blank
margins above and below the chart inside the overlay. Investigated: the
`<svg>` element's rendered box is confirmed to exactly fill the frame
(343×580px, measured) — the blank space is `preserveAspectRatio="xMidYMid
meet"` letterboxing a landscape 520×250 viewBox inside a portrait modal, the
correct and expected SVG behaviour, not a sizing failure. Still, it leaves a
lot of unused screen on phones; a mobile-specific max-height or aspect
adjustment would look tighter. Evidence: `history-zoom-375.png`.

## 4. The map (resources.html)

Driven interactively: zoom (+ button ×2), pan (drag), click the Kamioka pin
(`data-site="hida"`, a 7-experiment fan-out cluster), open JUNO's card,
toggle a filter off and on. All measured, not just screenshotted:

- Fan-out: clicking the Hida/Kamioka pin reveals all 7 previously-hidden
  `.map-exp` children (KamLAND, Hyper-Kamiokande, T2K, K2K, Super-Kamiokande,
  KamLAND-Zen, Kamiokande).
- JUNO's card: photo present, credit text exactly
  `"JUNO Collaboration · CC BY 4.0 · Wikimedia Commons"`, Commons link
  present and pointing to the correct file page. Screenshot:
  `map-juno-card.png`.
- Escape closes the card (`.map-card` count → 0).
- Filter toggle: clicking the "Reactor" legend entry sets
  `aria-pressed="false"` and hides reactor pins; clicking again restores
  `aria-pressed="true"`.
- **Confirmed the map does not open the figure-zoom overlay:** `.figbox`
  count stayed at 0 through every map click, fan-out, and card open —
  `assets/js/figure.js` explicitly excludes `.map-figure` from its wiring
  (`if (fig.classList.contains("map-figure")) return;`), and this was
  verified live, not just read in source.
- No console errors, no page errors during any map interaction.

Screenshots: `map-initial.png`, `map-zoomed.png`, `map-panned.png`,
`map-kamioka-fanout.png`, `map-juno-card.png`, `map-filter-off.png`.

## 5. Search

Loaded search.html, typed "lecture notes neutrino oscillations" into
`#q-free`, submitted, waited for network to settle. Network requests
observed (all with real hostnames, not mocked): INSPIRE-HEP (200), DataCite
i.e. arXiv (200), OpenAlex (200), Crossref (200), Semantic Scholar (failed).

Results rendered on-page merge real, relevant records from INSPIRE-HEP,
Crossref, and arXiv (via the documented DataCite proxy — arXiv's own
`export.arxiv.org` has no CORS header, so `search.js` deliberately reads
arXiv's DOI records from DataCite instead, which does; this is by design and
confirmed working).

OpenAlex: returned HTTP 200 with 4,375 matching records (confirmed by
querying its API directly) but no individually "OpenAlex"-labelled result
appeared in the rendered list. Traced this to the site's own deliberate
dedup logic (`mergeByTitle`/`mergeAll` in search.js, which reports "N
duplicate records merged") — OpenAlex's top hits share DOIs with Crossref's,
so they were folded into the Crossref-labelled rows rather than lost. Not a
bug.

Semantic Scholar: the one fetch that failed, with a browser console error
("blocked by CORS policy") and a `net::ERR_FAILED`. Traced to
`api.semanticscholar.org` returning HTTP 429 (confirmed independently via
curl, which surfaced the same AWS API Gateway `TooManyRequestsException`)
without CORS headers — Chromium reports rate-limited/header-less responses
as generic CORS failures. This is explicitly anticipated in the source:
`search.js:588-591` — *"the shared anonymous pool rate-limits aggressively
(HTTP 429); the failure is reported like any other source and the search
still answers from the rest."* The page displayed exactly the designed
degradation message, "Semantic Scholar unavailable (Failed to fetch)", and
the rest of the search continued to work. Not a bug; noted for the record
since a real visitor may see it too, but it's a known, gracefully-handled
limitation of a free third-party API, not a defect in this site.

No unaccounted-for console errors on search.html.

## 6. Links

Crawled every `[href]` and `[src]` across all 10 pages after each page's
`networkidle`: 22 unique internal URLs (pages, `#anchor` fragments, JS, CSS,
`data/history.json`/`.csv`, the two results-page PNGs) — **all returned
200**. Additionally checked assets not reachable by static DOM crawl: 6
`@font-face` files referenced only from CSS, and the 4 map-card photos
(JUNO, IceCube, Borexino, ProtoDUNE-VD) loaded only on-demand via
`data-photo` — **all 200**.

Sampled 10 external links (arXiv abstracts, INSPIRE record, Indico event,
and experiment homepages ICARUS/ANTARES): **all 10 returned 200** via
`curl -L`. None needed the "unverified" 403 caveat.

## 7. Downloads

`data/history.json`: valid JSON, `{"note": ..., "rows": [...]}`, 141 rows,
each row a well-formed dict.
`data/history.csv`: valid CSV, 142 lines including header, 141 data rows.
**Row counts match exactly (141 = 141).** First rows cross-checked and
agree field-for-field.

## 8. Meta coherence

Extracted the actual `<head><title>` (not SVG `<title>` tooltips, of which
there are many, correctly, inside the chart markup) for all 10 pages: every
title matches its filename and nav label (`index.html` → "Home — global-nu",
`history.html` → "Parameter history — global-nu", etc.). `og:title` and
`og:url` match the canonical URL and filename on every page, including
404.html (canonical `https://global-nu.org/404.html`, correctly *excluded*
from sitemap.xml).

`sitemap.xml`: lists all 9 real pages (index, results, history, digest,
news, conferences, resources, search, about) with matching URLs and today's
`lastmod`; 404.html correctly omitted.
`robots.txt`: `Allow: /`, points to the correct sitemap URL. Sane.
Favicon: `<link rel="icon" href="assets/favicon.svg">` present on pages
checked, and `assets/favicon.svg` returns 200 and is a valid SVG.
`.nojekyll`: present at `site/.nojekyll` (0 bytes, as expected).

## 9. Keyboard alone

**history.html:** started from page top and pressed real `Tab` repeatedly
(no `.focus()` shortcut) — reached the first openable figure at the 12th
Tab stop, confirming it's actually in the natural tab order. `Enter` opened
the `.figbox` overlay and moved focus inside it. Tabbed 6 more times:
focus never left `.figbox` (confirmed via `document.activeElement.closest`
on every step — the focus trap in `figure.js`'s `onKey` works). `Escape`
closed the overlay and `document.activeElement` was exactly the originating
`<figure class="figure ... figure--openable">` element — focus return
confirmed precisely, not just "something got focus."

**resources.html:** the Hida/Kamioka marker is reachable and focusable
(`role="button" tabindex="0"`, per `map.js`). `Enter` opened its card and
moved focus inside (`.map-card`). `Escape` closed the card and returned
focus to the marker (`document.activeElement` had `data-site="hida"` again).

Both flows work exactly as specified, with no dead ends or focus loss.

---

## Findings summary

| # | Severity | Page/theme/width | Finding | Evidence |
|---|----------|-------------------|---------|----------|
| 1 | Minor | history.html, both themes, 375px | Zoomed SVG comparison panels letterbox heavily on phones (landscape chart in a portrait modal) — correct `preserveAspectRatio` behaviour, not broken, but wastes vertical space | `shots/history-zoom-375.png` |
| 2 | Minor (informational) | search.html | Semantic Scholar occasionally fails via the anonymous pool's rate limit, surfacing as a browser CORS error; already anticipated and gracefully degraded by the site's own code and UI message | console capture in §5 |

No Critical findings (broken function, unreadable content). No Important
findings (visibly wrong but usable). All nine audit categories came up
clean by the verification methods described above; the two items logged are
polish-level and do not block launch.

## Verdict

**Publishable as-is.**
