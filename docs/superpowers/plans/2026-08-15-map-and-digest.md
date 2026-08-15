# Conference Map and Digest Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redraw the conference map on the model of Antonio's home page — cropped instead of squashed, two colours with a legend, a numbered badge per venue, zoom — add a hover panel naming the conferences at a marker, and give the digest entry the home page's form.

**Architecture:** Nothing is replaced wholesale. `figures.conference_map` keeps its clustering (`geocluster.cluster_by_distance`) and its photograph plumbing and changes how it draws: the projection stops being squashed, a cluster becomes one marker carrying one invisible `.conf-item` child per conference, and colour comes from each record's own `extra.scope`. Zoom is a straight port of the home page's already-generic `svgzoom.js`. `confmap.js` grows a hover panel and learns to list several conferences under one photograph.

**Tech Stack:** Python 3 (stdlib + PyYAML, in `.venv`), vanilla ES5-style JS (IIFE, `var`, no build step, no dependency), CSS custom properties. Python tests are standalone scripts run as `./.venv/bin/python3 tools/tests/test_X.py`; JS tests are `node tools/tests/test_X.js` using the vendored JSDOM. There is no pytest and no bundler in this project.

**Spec:** `docs/superpowers/specs/2026-08-15-map-and-digest-design.md`

## Global Constraints

- **No third-party host.** Nothing added here may load from another origin. Every asset is served from the site itself.
- **Every enhancement is guarded.** With a script never running, the page must still draw and still read. The SVG is content; JS only adds to it.
- **`var`, IIFE, `"use strict"`, no build step** in every JS file — match `site.js`, `map.js`, `confmap.js`.
- **Amber is reserved.** On the conferences page amber already means *in progress right now*. It must not become a category colour.
- **Category colours:** neutrino `--no` (`#1f9fd4` dark / `#0b62a4` light, unchanged from today); general particle physics `--dec-4` (`#8c63c9` dark / `#6d28d9` light). Badge text `--on-accent` (`#06121c` dark / `#ffffff` light).
- **Crop, do not squash:** 82°N to 58°S, the home page's numbers.
- **Marker radius:** `3.2 + 1.5 × min(n − 1, 4)`.
- **`data-lat` / `data-lon` are always the venue's real coordinates**, never a visual position — the Google Maps link is built from them.
- **The `<figure class="figure confmap-figure">` wrapper, its `<h4>Map</h4>` and its caption stay.** The home page has no frame, but this caption is load-bearing: it says how many meetings are placed and that the rest keep their row without a dot. Removing the frame is not in scope, and dropping it silently would lose that sentence.
- **Run the build as** `./.venv/bin/python3 build.py`, from the repository root.
- **The reference implementation** is `/Users/antonio/Documents/My Home Page - Claude/tools/news/figures.py::conference_map` (line 205) and `.../site-src/assets/js/svgzoom.js`. Read them; do not guess at them.

---

### Task 1: The digest entry's new form

Independent of the map, so it ships first and alone.

**Files:**
- Modify: `tools/news/render.py` (`_links_row` at 75-92, `_digest_list` at 208-221; new `_human_date`)
- Modify: `site-src/assets/css/site.css` (`.list--news` block at 562-571)
- Test: `tools/tests/test_digest_entry.py`

**Interfaces:**
- Produces:
  - `render._human_date(iso: str) -> str` — `"2026-08-13"` → `"13 Aug 2026"`; returns the input unchanged if it does not parse
  - `render._links_row(rec: dict, skip: set[str] | None = None) -> str` — the existing function, gaining an optional set of link keys to leave out

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_digest_entry.py`:

```python
#!/usr/bin/env python3
"""Check the shape of one digest entry.

    ./.venv/bin/python3 tools/tests/test_digest_entry.py

The entry's title now carries the arXiv link, so the separate links row must
disappear when arXiv was the only thing in it — and must survive when the
record also has a DOI or a journal. Getting that wrong loses a published
paper's real citation links, silently, on a page nobody re-reads daily.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import render                            # noqa: E402

checks = 0
problems = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
        return
    problems.append(label)
    print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


PREPRINT = {
    "title": "MANGO: An Autodiff Neutrino Oscillation Engine",
    "authors": "Pierre Granger",
    "date": "2026-08-13",
    "links": {"arxiv": "https://arxiv.org/abs/2508.09999"},
    "extra": {"categories": ["hep-ex", "hep-ph"]},
}
PUBLISHED = {
    "title": "A published one",
    "authors": "N. J. Ayres, Z. Berezhiani",
    "date": "2026-08-12",
    "links": {"arxiv": "https://arxiv.org/abs/2508.00001",
              "doi": "https://doi.org/10.1103/xyz"},
    "extra": {"categories": ["hep-ex"]},
}

check("a human date replaces the ISO one",
      render._human_date("2026-08-13") == "13 Aug 2026",
      render._human_date("2026-08-13"))
check("an unparseable date is passed through untouched",
      render._human_date("not a date") == "not a date")

html = render._digest_list([PREPRINT])
check("the title is a link to arXiv",
      '<a href="https://arxiv.org/abs/2508.09999">MANGO' in html, html[:300])
check("the date is printed in human form", "13 Aug 2026" in html, html[:300])
check("the ISO date is gone", "2026-08-13" not in html, html[:300])
check("each category is its own pill",
      html.count('<span class="tag">') == 2, html[:400])
check("the categories are not run together in one string",
      "hep-ex, hep-ph" not in html, html[:400])
check("a preprint whose only link was arXiv has no links row",
      'class="cites"' not in html, html[:400])

html2 = render._digest_list([PUBLISHED])
check("a record with a DOI keeps its links row",
      'class="cites"' in html2 and "10.1103/xyz" in html2, html2[:400])
check("that row no longer repeats the arXiv link",
      html2.count("2508.00001") == 1, html2[:400])

# The cap is content, not form, and this change must not move it.
many = dict(PREPRINT)
many["extra"] = {"categories": ["hep-ph", "hep-ex", "astro-ph.CO", "hep-th"]}
check("the three-category cap is unchanged",
      render._digest_list([many]).count('<span class="tag">') == 3)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the digest entry has its new form")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_digest_entry.py`
Expected: FAIL with `AttributeError: module 'tools.news.render' has no attribute '_human_date'`

- [ ] **Step 3: Write the implementation**

In `tools/news/render.py`, add after `_stamp` (line 72):

```python
def _human_date(iso: str) -> str:
    """"2026-08-13" -> "13 Aug 2026".

    Returned unchanged if it does not parse: the records come from an API,
    and a date this function cannot read is still better shown as it arrived
    than swallowed.
    """
    try:
        return _dt.date.fromisoformat(str(iso)).strftime("%-d %b %Y")
    except (ValueError, TypeError):
        return str(iso)
```

Change `_links_row`'s signature and its loop (lines 75-92):

```python
def _links_row(rec: dict, skip: set[str] | None = None) -> str:
    """arXiv / INSPIRE / DOI, whichever the record actually carries.

    Only links that came with the record are emitted: a DOI is never
    constructed from an arXiv id, because a paper that is not published yet
    would get a link that 404s.

    `skip` leaves out link keys the caller has already shown elsewhere. The
    digest passes {"arxiv"} because the entry's title now carries that link;
    the row still appears for a record that also has a DOI or a journal, and
    disappears only when arXiv was all it had.
    """
    order = [("arxiv", "arXiv"), ("inspire", "INSPIRE"), ("doi", "DOI"),
             ("journal", "Journal"), ("source", "Source")]
    skip = skip or set()
    seen, out = set(), []
    for key, label in order:
        if key in skip:
            continue
        url = (rec.get("links") or {}).get(key)
        if url and url not in seen:
            seen.add(url)
            out.append(f'<a href="{_esc(url)}">{label}</a>')
    if not out and rec.get("url") and "url" not in skip:
        out.append(f'<a href="{_esc(rec["url"])}">Read it</a>')
    return " · ".join(out)
```

Replace `_digest_list` (lines 208-221):

```python
def _digest_list(records: list[dict]) -> str:
    if not records:
        return ('<p class="small muted">Nothing matched today. arXiv does not '
                'announce at weekends, so an empty section here is usually a '
                'quiet Sunday rather than a failure.</p>\n')
    out = ['<ul class="list list--news">\n']
    for rec in records:
        title = _title(rec)
        arxiv = (rec.get("links") or {}).get("arxiv")
        # The title carries the arXiv link, so the links row below drops it.
        # A record with no arXiv link keeps a plain title and an untouched
        # row — nothing is lost for the records this does not apply to.
        head = f'<a href="{_esc(arxiv)}">{title}</a>' if arxiv else title
        meta = " · ".join(x for x in (rec.get("authors"),
                                      _human_date(rec.get("date", ""))) if x)
        tags = "".join(
            f'<span class="tag">{_esc(c)}</span>'
            for c in (rec.get("extra") or {}).get("categories", [])[:3])
        rest = _links_row(rec, skip={"arxiv"} if arxiv else None)
        row = f'<span class="cites">{rest}</span>' if rest else ""
        out.append(f'<li><b>{head}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="tags">{tags}</span>{row}</li>\n')
    out.append('</ul>\n')
    return "".join(out)
```

- [ ] **Step 4: Add the styles**

In `site-src/assets/css/site.css`, after the `.list--news` block (line 571), add:

```css
/* The digest entry, given room. The categories were a comma-joined string
   inside the grey meta line; as pills they are scannable, and .tag already
   exists (see the badge rules above) so this only has to lay them out. */
.list--news li{padding:1.05rem 0}
.list--news .tags{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.4rem}
.list--news .tags .tag{font-family:var(--mono);font-size:.72rem;
  color:var(--text-mute)}
.list--news .cites{margin-top:.35rem}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_digest_entry.py`
Expected: PASS.

- [ ] **Step 6: Rebuild and look at the page**

`build.py` converts `site-src/content/digest.md` into a page; it does not
write that Markdown. The daily job does, through `render.digest()`. So
running only `build.py` would rebuild yesterday's markup and prove nothing.

Run the job, then the build:

```bash
./update-daily
./.venv/bin/python3 build.py
```

`./update-daily` fetches. If the network is unavailable it falls back to
today's cached records under `var/news/cache/`, which is fine here — but if
neither works, say so rather than letting a stale page stand in for a
rebuilt one.

Then open `site/digest.html` and confirm by eye: the title is a link, the
date reads `13 Aug 2026`, the categories are pills, and a preprint whose only
link was arXiv has no links row beneath it.

- [ ] **Step 7: Run the existing suite**

```bash
./.venv/bin/python3 tools/tests/test_built_pages.py
./.venv/bin/python3 tools/tests/test_pipeline.py
```

Expected: PASS. `test_built_pages.py` is the guard that no page ships
unconverted Markdown, which a change to generated HTML can break.

- [ ] **Step 8: Commit**

```bash
git add tools/news/render.py site-src/assets/css/site.css \
        tools/tests/test_digest_entry.py site-src/content/digest.md site/
git commit -m "Give the digest entry the form Antonio prefers: linked title, human date, pills"
```

---

### Task 2: Crop the map instead of squashing it

**Files:**
- Modify: `tools/news/figures.py` (constants at 232-243, `_map_xy` at 246-248, `conference_map`'s SVG header at 380-392)
- Modify: `tools/news/render.py` (the caption at 429-446)
- Test: `tools/tests/test_confmap_geometry.py`

**Interfaces:**
- Consumes: `tools.news.worldmap::project(lon, lat) -> (x, y)`, `worldmap.WIDTH`
- Produces: `figures.MAP_TOP_LAT = 82.0`, `figures.MAP_BOTTOM_LAT = -58.0`; `figures._map_xy` is **deleted** — callers use `wm.project` directly

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_confmap_geometry.py`:

```python
#!/usr/bin/env python3
"""The conference map must not distort the world.

    ./.venv/bin/python3 tools/tests/test_confmap_geometry.py

The map used to scale every y by 0.5 to stay short, and a caption apologised
for it in prose. Cropping the empty Arctic and the Antarctic smear gives the
same height on screen with the right shapes, so the squash — and the excuse —
are gone. This test is what stops either coming back.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import figures                           # noqa: E402
from tools.news import worldmap as wm                    # noqa: E402

checks = 0
problems = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
        return
    problems.append(label)
    print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


check("the vertical squash is gone",
      not hasattr(figures, "MAP_SCALE_Y"),
      "MAP_SCALE_Y still exists; the map is still compressed")
check("_map_xy is gone — callers project directly",
      not hasattr(figures, "_map_xy"))
check("the crop is 82N", figures.MAP_TOP_LAT == 82.0)
check("the crop is 58S", figures.MAP_BOTTOM_LAT == -58.0)

REC = {"id": "c1", "title": "A Conference", "url": "https://example.org/",
       "extra": {"place": "Bari, Italy", "city": "Bari", "span": "1-5 Sep 2026",
                 "scope": "neutrino"}}
svg = figures.conference_map([(REC, 16.87, 41.12)])

check("the map draws", bool(svg))

m = re.search(r'viewBox="0 ([\d.-]+) ([\d.]+) ([\d.]+)"', svg)
check("the viewBox is parseable", m is not None, svg[:200])
if m:
    top, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3))
    check("the viewBox top is 82N", abs(top - wm.project(0.0, 82.0)[1]) < 1.0,
          f"{top} vs {wm.project(0.0, 82.0)[1]}")
    check("the viewBox height reaches 58S",
          abs(h - (wm.project(0.0, -58.0)[1] - wm.project(0.0, 82.0)[1])) < 1.0)
    check("the width is the whole world", abs(w - wm.WIDTH) < 1.0)

check("nothing scales the land vertically any more",
      "scale(1," not in svg, "a scale(1,k) transform survived")

# The marker must sit where projection puts it, undistorted.
x, y = wm.project(16.87, 41.12)
check("the marker sits at the undistorted projection",
      f'{x:.1f}' in svg and f'{y:.1f}' in svg,
      f"expected {x:.1f},{y:.1f}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the map is cropped, not squashed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: FAIL at `the vertical squash is gone` — `MAP_SCALE_Y` is still defined.

- [ ] **Step 3: Change the constants**

In `tools/news/figures.py`, replace lines 232-243:

```python
# Cropped rather than compressed. In an equirectangular projection Antarctica
# smears into a band the width of the world, and the empty Arctic wasted a
# third of the height; no conference has ever been held in either. Cropping
# them away gives the same height on the page as the old scale(1,.5) squash
# did, with the shapes undistorted — there is no trade between the two.
MAP_TOP_LAT = 82.0
MAP_BOTTOM_LAT = -58.0

MAP_DOT_R = 3.0
# Two markers this close would sit almost entirely on top of one another,
# hiding whichever was drawn first — the same problem make_map.py's
# MERGE_DIST exists to catch, reused at the same "2 dot-radii" rule rather
# than a second, invented one.
MAP_MERGE_DIST = 2 * MAP_DOT_R
```

Delete `MAP_HALO_R`, `MAP_SCALE_Y` and `MAP_FAN_R` — the halo goes with the
new marker in Task 3, and the fan-out with the badge.

Delete `_map_xy` (lines 246-248) entirely.

- [ ] **Step 4: Change the projection call and the SVG header**

In `conference_map`, replace the `points` line and the header block:

```python
    points = [(conf, lon, lat, wm.project(lon, lat)) for conf, lon, lat in located]
    groups = geocluster.cluster_by_distance(
        [p[3] for p in points], MAP_MERGE_DIST)
    clusters: dict[int, list[int]] = {idx: idxs for idx, idxs in enumerate(groups)}

    top = wm.project(0.0, MAP_TOP_LAT)[1]
    bottom = wm.project(0.0, MAP_BOTTOM_LAT)[1]
    height = bottom - top

    parts = [
        f'<svg data-zoomable="1" viewBox="0 {top:.0f} {wm.WIDTH:.0f} '
        f'{height:.0f}" role="img" '
        'aria-label="World map of upcoming neutrino conferences" '
        'xmlns="http://www.w3.org/2000/svg">',
        "<title>Where the upcoming conferences are</title>",
        f'<path d="{wm.LAND_PATH}" fill="var(--surface-2)" '
        'stroke="var(--line-strong)" stroke-width="0.6" '
        'vector-effect="non-scaling-stroke"/>',
    ]
```

Note the `<g transform="scale(1,…)">` wrapper around the land path is gone,
and `data-zoomable="1"` is added now so Task 5 has nothing to change here.

Also update `conference_map`'s docstring: the sentence explaining that
bucketing happens "in the FINAL (already-squished) pixel space" is no longer
true — the space is no longer squished. Say instead that bucketing happens in
projected pixel space, because "coincident" is a statement about what a reader
sees on the drawn map.

- [ ] **Step 5: Remove the caption's excuse**

In `tools/news/render.py`, delete the comment block at 438-442 and the
`map_caption +=` statement at 443-446 — the whole passage beginning
`# figures.conference_map draws at half the experiments map's` and ending
`"of experiments.")`. The rest of the caption is unaffected.

- [ ] **Step 6: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/news/figures.py tools/news/render.py \
        tools/tests/test_confmap_geometry.py
git commit -m "Crop the conference map instead of squashing it, and drop the apology"
```

---

### Task 3: One marker per venue, with a count

**Files:**
- Modify: `tools/news/figures.py` (`_conf_pin` at 286-335 becomes `_conf_marker`; `conference_map`'s drawing loop)
- Modify: `tools/tests/test_confmap_geometry.py` (marker checks)

**Interfaces:**
- Consumes: `figures.MAP_MERGE_DIST`, `geocluster.cluster_by_distance`
- Produces: `figures._conf_marker(confs: list[dict], lon: float, lat: float, x: float, y: float, photo: dict | None) -> str` — one `<g class="conf-pin">` holding one `<g class="conf-item">` per conference

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_confmap_geometry.py`, before the final `print()`:

```python
# --- one marker per venue, not per conference ----------------------------
TWO = [
    ({"id": "a", "title": "First Conference", "url": "https://a.example/",
      "extra": {"place": "Bari, Italy", "city": "Bari", "span": "1-5 Sep 2026",
                "scope": "neutrino"}}, 16.87, 41.12),
    ({"id": "b", "title": "Second Conference", "url": "https://b.example/",
      "extra": {"place": "Bari, Italy", "city": "Bari", "span": "8-9 Sep 2026",
                "scope": "neutrino"}}, 16.87, 41.12),
]
svg2 = figures.conference_map(TWO)

check("two conferences in one city draw ONE marker",
      svg2.count('class="conf-pin"') == 1,
      f'found {svg2.count(chr(34) + "conf-pin" + chr(34))} markers')
check("the marker holds one conf-item per conference",
      svg2.count('class="conf-item"') == 2)
check("the count is drawn on the marker", ">2</text>" in svg2, svg2[-900:])
check("every conference keeps its own name",
      "First Conference" in svg2 and "Second Conference" in svg2)
check("every conference keeps its own dates",
      "1-5 Sep 2026" in svg2 and "8-9 Sep 2026" in svg2)
check("every conference keeps its own url",
      "https://a.example/" in svg2 and "https://b.example/" in svg2)
check("the venue's real coordinates are on the marker",
      'data-lat="41.1200"' in svg2 and 'data-lon="16.8700"' in svg2)
check("the fan-out is gone", not hasattr(figures, "MAP_FAN_R"))
check("the halo is gone", not hasattr(figures, "MAP_HALO_R"))
check("the marker is anchored for counter-scaling", 'data-fixed=' in svg2)
check("the city is named on the marker", 'class="map-name"' in svg2)

single = figures.conference_map([TWO[0]])
check("a lone conference draws no count badge", ">1</text>" not in single)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: FAIL at `two conferences in one city draw ONE marker` — the fan-out
still draws two.

- [ ] **Step 3: Replace `_conf_pin` with `_conf_marker`**

In `tools/news/figures.py`, replace `_conf_pin` (lines 286-335) with:

```python
def _conf_marker(confs: list[dict], lon: float, lat: float,
                 x: float, y: float, photo: dict | None = None) -> str:
    """One <g class="conf-pin"> for a venue, holding every conference at it.

    A marker used to be one conference, and a city with two fanned them into
    two dots a few units apart. It is now one dot with the count on it — what
    makes the home page's map legible across a crowded Europe — so the
    conferences have to live inside it. `map.js` already does exactly this
    with `.map-exp` children inside one experiment pin; this follows that
    pattern rather than inventing a second one.

    Each `<g class="conf-item">` draws nothing. It carries one conference's
    name, dates and URL for confmap.js to read, on hover and on click.

    data-lat/data-lon are the venue's REAL coordinates: confmap.js builds the
    Google Maps link from them, and a link is only as honest as the numbers
    that produced it.

    `photo`, when given, is the dict photos.for_city returns — file, page,
    author, licence, licence_url — carried as five data-photo* attributes so
    confmap.js can render the image and its full credit without a second
    lookup. It sits on the marker, not on a conference, because it is a
    photograph of the CITY: photos.for_city caches by city, and every
    conference here shares one.
    """
    first = confs[0]
    extra = first.get("extra") or {}
    place = extra.get("place") or extra.get("city") or ""
    city = extra.get("city") or place
    n = len(confs)
    r = 3.2 + 1.5 * min(n - 1, 4)
    colour = ("var(--dec-4)" if (extra.get("scope") or "") == "general"
              else "var(--no)")

    title = "; ".join(
        _map_title(c.get("title", ""), place,
                   (c.get("extra") or {}).get("span", ""))
        for c in confs)

    attrs = (
        f' data-place="{_e(place)}"'
        f' data-lat="{lat:.4f}"'
        f' data-lon="{lon:.4f}"'
    )
    if photo:
        attrs += (
            f' data-photo="{_e(photo["file"])}"'
            f' data-photo-author="{_e(photo["author"])}"'
            f' data-photo-licence="{_e(photo["licence"])}"'
            f' data-photo-licence-url="{_e(photo.get("licence_url") or "")}"'
            f' data-photo-page="{_e(photo["page"])}"'
        )

    items = "".join(
        f'<g class="conf-item" data-conf="{_e(c.get("id", ""))}"'
        f' data-name="{_e(c.get("title", ""))}"'
        f' data-dates="{_e((c.get("extra") or {}).get("span", ""))}"'
        f' data-url="{_e(c.get("url", ""))}"></g>'
        for c in confs)

    # The shapes sit at the origin inside a translated group, and data-fixed
    # holds the anchor: svgzoom.js counter-scales every [data-fixed] group so
    # a dot keeps its on-screen size as the map is zoomed, and a crowd comes
    # apart instead of growing into one blob.
    count = (f'<text y="2.4" text-anchor="middle" '
             f'style="fill:var(--on-accent);font-size:6px;font-weight:700;'
             f'font-family:var(--display,sans-serif)">{n}</text>'
             if n > 1 else "")

    return (
        f'<g class="conf-pin"{attrs} data-fixed="{x:.1f} {y:.1f}" '
        f'transform="translate({x:.1f} {y:.1f})" tabindex="0">'
        f'<title>{_e(title)}</title>'
        f'<circle r="{r:.1f}" fill="{colour}" stroke="var(--bg)" '
        f'stroke-width="1.1" paint-order="stroke"/>'
        f'{count}'
        f'<text y="{-r - 3:.1f}" text-anchor="middle" class="map-name" '
        f'style="fill:var(--text-mute);font-size:8px;'
        f'font-family:var(--body,sans-serif)">{_e(_trim(city, 18))}</text>'
        f'{items}</g>'
    )
```

- [ ] **Step 4: Replace the drawing loop**

In `conference_map`, replace the whole "Step 2: draw" loop (the block from
`for members in sorted(clusters.values(), key=len):` to the end of the
fan-out) with:

```python
    # Step 2: draw one marker per cluster. A cluster of one is a city with one
    # conference; a cluster of several is a city with several, and the count
    # goes on the dot instead of fanning them into separate ones.
    for members in sorted(clusters.values(), key=len):
        confs = [points[i][0] for i in members]
        # The cluster's position is the mean of its members', but the
        # coordinates carried on the marker are the first conference's real
        # ones — the Google Maps link must land on a venue, not on a centroid.
        cx = sum(points[i][3][0] for i in members) / len(members)
        cy = sum(points[i][3][1] for i in members) / len(members)
        _, lon, lat, _ = points[members[0]]
        parts.append(_conf_marker(confs, lon, lat, cx, cy,
                                  _lookup_photo(confs[0], log)))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: PASS, including the earlier geometry checks.

- [ ] **Step 6: Commit**

```bash
git add tools/news/figures.py tools/tests/test_confmap_geometry.py
git commit -m "One marker per city, with the count on it, instead of a fan of dots"
```

---

### Task 4: Two colours, a legend, and the contrast to prove them

**Files:**
- Modify: `tools/news/figures.py` (`conference_map` — the legend)
- Modify: `tools/tests/test_theme.js` (the two category colours and the badge text)

**Interfaces:**
- Consumes: `_conf_marker`'s colour choice from Task 3 (`var(--dec-4)` when `extra.scope == "general"`, else `var(--no)`)

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_confmap_geometry.py`, before the final `print()`:

```python
# --- two colours, and a legend that explains them ------------------------
MIXED = [
    ({"id": "n", "title": "A Neutrino Meeting", "url": "https://n.example/",
      "extra": {"place": "Bari, Italy", "city": "Bari", "span": "1-5 Sep 2026",
                "scope": "neutrino"}}, 16.87, 41.12),
    ({"id": "g", "title": "A General Meeting", "url": "https://g.example/",
      "extra": {"place": "Tokyo, Japan", "city": "Tokyo", "span": "3-4 Oct 2026",
                "scope": "general"}}, 139.69, 35.69),
]
svgm = figures.conference_map(MIXED)

check("the neutrino marker uses the blue token", "var(--no)" in svgm)
check("the general marker uses the purple token", "var(--dec-4)" in svgm)
check("amber is not used as a category colour",
      "var(--io)" not in svgm,
      "amber already means 'in progress right now' on this page")
check("the legend names both categories",
      "Neutrino" in svgm and "General particle physics" in svgm, svgm[-700:])

only_nu = figures.conference_map([MIXED[0]])
check("a legend entry with nothing to label is not drawn",
      "General particle physics" not in only_nu)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: FAIL at `the legend names both categories`.

- [ ] **Step 3: Draw the legend**

In `tools/news/figures.py`, in `conference_map`, immediately before
`parts.append("</svg>")`, insert:

```python
    # A legend, so two colours are not a puzzle. Only categories actually on
    # the map are listed: a key to something the reader cannot see is noise.
    present = {(p[0].get("extra") or {}).get("scope") or "neutrino"
               for p in points}
    lx, ly = 12.0, top + height - 8.0
    for scope, colour, label in (
            ("neutrino", "var(--no)", "Neutrino"),
            ("general", "var(--dec-4)", "General particle physics")):
        if scope not in present:
            continue
        parts.append(f'<circle cx="{lx + 4:.1f}" cy="{ly - 3:.1f}" r="4" '
                     f'fill="{colour}"/>')
        parts.append(
            f'<text x="{lx + 13:.1f}" y="{ly:.1f}" style="fill:var(--text-mute);'
            f'font-size:9px;font-family:var(--body,sans-serif)">'
            f'{_e(label)}</text>')
        lx += 15 + 6.0 * len(label)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_confmap_geometry.py`
Expected: PASS.

- [ ] **Step 5: Put the colours through the contrast test**

Read `tools/tests/test_theme.js` and find the list of colour pairs it checks.
Add four entries, following whatever shape that list already uses:

- `--no` on `--surface-2` (the map's land fill), both themes
- `--dec-4` on `--surface-2`, both themes
- `--on-accent` on `--no` — the count inside a blue badge
- `--on-accent` on `--dec-4` — the count inside a purple badge

The last two are the ones at risk: `--on-accent` was chosen to sit on
`--accent`, not on these. Do not adjust a colour to make the test pass without
saying so — if a pair fails, report the measured ratio and stop.

Run: `node tools/tests/test_theme.js`
Expected: PASS, with the four new pairs listed.

- [ ] **Step 6: Commit**

```bash
git add tools/news/figures.py tools/tests/test_confmap_geometry.py \
        tools/tests/test_theme.js
git commit -m "Colour the markers by domain, with a legend and measured contrast"
```

---

### Task 5: Zoom, and the city names it reveals

**Files:**
- Create: `site-src/assets/js/svgzoom.js` (ported from the home page)
- Modify: `site-src/assets/css/site.css`
- Modify: `tools/news/render.py` (the conferences page's script list, near line 318)

**Interfaces:**
- Consumes: `data-zoomable="1"` on the SVG (added in Task 2) and `data-fixed="x y"` on each marker (added in Task 3)
- Produces: a `.svgzoom` wrapper element with a `.svgzoom__bar` of `.svgzoom__btn` controls, and the class `.svgzoom--zoomed` while zoomed

- [ ] **Step 1: Copy the file**

```bash
cp "/Users/antonio/Documents/My Home Page - Claude/site-src/assets/js/svgzoom.js" \
   site-src/assets/js/svgzoom.js
```

Read the copy end to end. It is already generic — it drives any
`svg[data-zoomable]` by its viewBox alone and counter-scales every
`[data-fixed]` group. Change nothing except the first line of the header
comment, so it names this site rather than the other one, and add a sentence
recording where it came from and why it is not `map.js` generalised:

```
/* global-nu — pan & zoom for inline SVGs marked data-zoomable, by viewBox
 * alone.
 *
 * Ported unchanged from Antonio's home page, which is where this behaviour
 * was written and proven. Not map.js generalised: figure.js already argues
 * the case in its own header — duplicating one clamp and one transform
 * string costs less than coupling a working, tested interaction to a second
 * caller — and that reasoning applies here without modification. map.js
 * still owns the experiments map, and figure.js still excludes both maps
 * from its lightbox, because each already answers a click with its own card.
```

- [ ] **Step 2: Add the styles**

In `site-src/assets/css/site.css`, add (the home page's rules at 688-706 are
the reference; read them and match this site's tokens):

```css
/* Pan/zoom wrapper that svgzoom.js builds around svg[data-zoomable]. */
.svgzoom{position:relative}
.svgzoom--zoomed .confmap-figure svg,.svgzoom--zoomed svg{cursor:grab}
.svgzoom--zoomed svg:active{cursor:grabbing}
.svgzoom__bar{position:absolute;top:.4rem;right:.4rem;display:flex;
  flex-direction:column;gap:.25rem;z-index:2}
.svgzoom__btn{width:1.9rem;height:1.9rem;border-radius:var(--r-sm);
  border:1px solid var(--line);background:var(--surface);color:var(--text);
  opacity:.5;transition:opacity .2s;cursor:pointer}
.svgzoom__btn:hover,.svgzoom__btn:focus-visible,
.svgzoom--zoomed .svgzoom__btn{opacity:1}
.svgzoom__btn:disabled{opacity:.25;cursor:default}
/* Thirty-odd city labels collide at rest, so they fade in only when the map
   is zoomed. With no JS there is no .svgzoom wrapper and the labels simply
   stay visible — the right fallback, not a broken one. */
.map-name{transition:opacity .2s}
.svgzoom:not(.svgzoom--zoomed) .map-name{opacity:0}
```

- [ ] **Step 3: Load the script on the conferences page**

In `tools/news/render.py`, find the conferences page's front matter (around
line 318, where `assets/js/confmap.js` is listed) and add
`assets/js/svgzoom.js` beside it, in the same shape the existing entry uses.

- [ ] **Step 4: Rebuild and check the wrapper appears**

```bash
./update-daily || ./.venv/bin/python3 build.py
./.venv/bin/python3 build.py
grep -c 'svgzoom' site/conferences.html
```

Expected: at least 1 — the script tag. The `.svgzoom` wrapper itself is built
by the script at runtime, so it will not be in the file.

- [ ] **Step 5: Verify the zoom in a real browser**

```bash
./.venv/bin/python3 - <<'PY'
from playwright.sync_api import sync_playwright
import pathlib
page_url = "file://" + str(pathlib.Path("site/conferences.html").resolve())
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1280,"height":900})
    pg.goto(page_url); pg.wait_for_timeout(600)
    print("wrapper:", pg.eval_on_selector_all(".svgzoom", "e => e.length"))
    print("buttons:", pg.eval_on_selector_all(".svgzoom__btn", "e => e.length"))
    print("labels hidden at rest:", pg.eval_on_selector(
        ".map-name", "e => getComputedStyle(e).opacity"))
    pg.click(".svgzoom__btn"); pg.wait_for_timeout(400)
    print("labels after zoom:", pg.eval_on_selector(
        ".map-name", "e => getComputedStyle(e).opacity"))
    b.close()
PY
```

Expected: a wrapper, three buttons, opacity `0` at rest and `1` after zooming.

- [ ] **Step 6: Commit**

```bash
git add site-src/assets/js/svgzoom.js site-src/assets/css/site.css \
        tools/news/render.py site-src/content/conferences.md site/
git commit -m "Zoom the conference map, and reveal the city names when it is zoomed"
```

---

### Task 6: The card lists every conference at the marker

**Files:**
- Modify: `site-src/assets/js/confmap.js` (`open(pin)` at 131-215)
- Modify: `tools/tests/test_confmap.js`

**Interfaces:**
- Consumes: the marker structure from Task 3 — `.conf-pin[data-place][data-lat][data-lon][data-photo*]` containing `.conf-item[data-conf][data-name][data-dates][data-url]`

- [ ] **Step 1: Write the failing test**

In `tools/tests/test_confmap.js`, change the synthetic `SVG` constant so one
marker holds two conferences, in the new shape:

```javascript
<g class="conf-pin" data-place="Bari, Italy" data-lat="41.1200"
   data-lon="16.8700" tabindex="0">
  <title>First Conference — Bari, Italy — 1-5 Sep 2026</title>
  <circle r="4.7"/><text>2</text>
  <g class="conf-item" data-conf="conf:first" data-name="First Conference"
     data-dates="1-5 Sep 2026" data-url="https://first.example/"></g>
  <g class="conf-item" data-conf="conf:second" data-name="Second Conference"
     data-dates="8-9 Sep 2026" data-url="https://second.example/"></g>
</g>
```

Keep the existing single-conference markers and the Trieste photo marker,
updated to the same shape (one `.conf-item` each). Then add these checks
after the card is opened on the two-conference marker:

```javascript
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node tools/tests/test_confmap.js`
Expected: FAIL — `open()` still reads `data-name` from the pin, which no
longer carries one.

- [ ] **Step 3: Change `open(pin)`**

In `site-src/assets/js/confmap.js`, `open(pin)` currently reads `data-name`,
`data-dates` and `data-url` off the pin. Read them off the children instead,
and render one heading block per conference under the single photograph:

```javascript
    function items(pin) {
      var out = [], els = pin.querySelectorAll(".conf-item"), i;
      for (i = 0; i < els.length; i++) {
        out.push({
          name: els[i].getAttribute("data-name") || "",
          dates: els[i].getAttribute("data-dates") || "",
          url: els[i].getAttribute("data-url") || ""
        });
      }
      return out;
    }
```

In `open(pin)`, replace the three `pin.getAttribute("data-name"/"data-dates"/
"data-url")` reads with `var confs = items(pin);` and build one block per
entry — the heading (a link when the conference has a URL, plain text when it
does not) followed by its dates. `data-place`, `data-lat`, `data-lon` and the
five `data-photo*` reads stay exactly as they are: they are per venue, and the
photograph is rendered once, above the list.

Add a comment saying why the photograph is not per conference: it is a
photograph of the city, `photos.for_city` caches by city, and every conference
on this marker shares it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node tools/tests/test_confmap.js`
Expected: PASS, including the pre-existing checks — Escape still closes the
card and returns focus, and the Trieste marker still renders the image with
all three parts of its credit.

- [ ] **Step 5: Check the credit is still inside the card**

Run: `./.venv/bin/python3 tools/tests/test_confcard_credit.py`
Expected: PASS. This is the fix from 2026-08-14 and the easiest thing here to
break — the card is taller now that it lists several conferences.

- [ ] **Step 6: Commit**

```bash
git add site-src/assets/js/confmap.js tools/tests/test_confmap.js
git commit -m "The card lists every conference at a marker, under one photograph"
```

---

### Task 7: The hover panel

**Files:**
- Modify: `site-src/assets/js/confmap.js`
- Modify: `site-src/assets/css/site.css`
- Modify: `tools/tests/test_confmap.js`

**Interfaces:**
- Consumes: `items(pin)` from Task 6
- Produces: an element with class `conf-tip` appended to the figure's stage

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_confmap.js`:

```javascript
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node tools/tests/test_confmap.js`
Expected: FAIL at `hovering a marker opens a panel`.

- [ ] **Step 3: Implement the panel**

In `site-src/assets/js/confmap.js`, inside `wireCard`, add a `wireTip`
alongside it. One `.conf-tip` element is created once and reused — creating a
node per hover would churn the DOM on every marker the pointer crosses.

```javascript
    /* A light panel: the place, then one line per conference with its name
     * and dates. No image, so crossing a crowded Europe loads nothing. The
     * full card, with the photograph, stays on click — two weights of
     * answer for two weights of gesture. */
    function wireTip(fig, stage, pins) {
      var tip = document.createElement("div");
      tip.className = "conf-tip";
      tip.hidden = true;
      stage.appendChild(tip);

      function show(pin) {
        var place = pin.getAttribute("data-place") || "";
        var confs = items(pin), i;
        tip.textContent = "";
        if (place) {
          var head = document.createElement("b");
          head.textContent = place;
          tip.appendChild(head);
        }
        for (i = 0; i < confs.length; i++) {
          var line = document.createElement("p");
          line.textContent = confs[i].dates
            ? confs[i].name + " · " + confs[i].dates
            : confs[i].name;
          tip.appendChild(line);
        }
        tip.hidden = false;
      }

      function hide() { tip.hidden = true; }

      for (var i = 0; i < pins.length; i++) {
        pins[i].addEventListener("mouseenter", (function (p) {
          return function () { show(p); };
        })(pins[i]));
        pins[i].addEventListener("mouseleave", hide);
        pins[i].addEventListener("focus", (function (p) {
          return function () { show(p); };
        })(pins[i]));
        pins[i].addEventListener("blur", hide);
      }
    }
```

Call it from `init()` next to `wireCard`, passing the same figure, the stage
that `ensureStage(svg)` returns, and the same pin list.

- [ ] **Step 4: Add the styles**

In `site-src/assets/css/site.css`:

```css
/* The map's hover panel: light, immediate, and never an image. The full
   card with the photograph is what a click is for. */
.conf-tip{position:absolute;top:.6rem;left:.6rem;max-width:22rem;z-index:3;
  padding:.5rem .7rem;border:1px solid var(--line);border-radius:var(--r-sm);
  background:var(--surface);box-shadow:var(--shadow);pointer-events:none}
.conf-tip[hidden]{display:none}
.conf-tip b{display:block;font-size:.8rem;color:var(--text)}
.conf-tip p{margin:.2rem 0 0;font-size:.78rem;color:var(--text-soft)}
```

- [ ] **Step 5: Run both JS tests**

```bash
node tools/tests/test_confmap.js
node tools/tests/test_theme.js
```

Expected: PASS. `test_theme.js` covers the panel's text-on-surface pair.

- [ ] **Step 6: Commit**

```bash
git add site-src/assets/js/confmap.js site-src/assets/css/site.css \
        tools/tests/test_confmap.js
git commit -m "Name the conferences at a marker on hover, and on keyboard focus"
```

---

### Task 8: Look at it

Green tests on this project have repeatedly passed over things a browser
showed immediately. This task is that browser.

**Files:**
- Modify: whatever the screenshots show is wrong

- [ ] **Step 1: Rebuild everything**

```bash
./update-daily
./.venv/bin/python3 build.py
```

- [ ] **Step 2: Shoot both pages, both themes, three widths**

```bash
mkdir -p /tmp/shots && ./.venv/bin/python3 - <<'PY'
from playwright.sync_api import sync_playwright
import pathlib
root = pathlib.Path("site").resolve()
with sync_playwright() as p:
    b = p.chromium.launch()
    for theme in ("light", "dark"):
        for w in (375, 700, 1280):
            pg = b.new_page(viewport={"width": w, "height": 1000})
            for page in ("conferences", "digest"):
                pg.goto("file://" + str(root / f"{page}.html"))
                pg.evaluate(f"localStorage.setItem('gnu-theme','{theme}')")
                pg.reload(); pg.wait_for_timeout(500)
                pg.screenshot(path=f"/tmp/shots/{page}-{theme}-{w}.png",
                              full_page=True)
            pg.close()
    b.close()
print("12 screenshots in /tmp/shots")
PY
```

- [ ] **Step 3: Read every screenshot**

Look at all twelve. The things most likely to be wrong, in order:

1. The legend colliding with Australia or South America at 375 px.
2. The count badge illegible on the purple fill in one theme.
3. The zoom buttons sitting over the map's top-right corner content.
4. The city labels visible at rest because the `.svgzoom` wrapper failed to
   build, or invisible after zoom because the selector does not match.
5. The digest pills wrapping badly at 375 px.
6. The card's photo credit pushed below the card's lower edge now that the
   card lists several conferences — the 2026-08-14 bug, re-opened.

- [ ] **Step 4: Fix what the screenshots show, and re-shoot**

For each problem, fix it, re-run Step 2, and look again. Do not declare this
task done on a screenshot you have not re-taken after the last edit.

- [ ] **Step 5: Run the whole suite**

```bash
for t in tools/tests/test_*.py; do echo "--- $t"; ./.venv/bin/python3 "$t" || echo "FAILED $t"; done
for t in tools/tests/test_*.js; do echo "--- $t"; node "$t" || echo "FAILED $t"; done
```

Expected: every one passes. Report any failure with its output rather than
working around it.

- [ ] **Step 6: Commit and publish**

```bash
git add -A
git commit -m "The conference map and the digest entry, seen in a browser before shipping"
git push
git subtree push --prefix site origin gh-pages
```

- [ ] **Step 7: Verify on the live page**

```bash
curl -s https://global-nu.org/conferences.html | grep -c 'class="conf-item"'
curl -s https://global-nu.org/conferences.html | grep -c 'svgzoom'
curl -s https://global-nu.org/digest.html | grep -c '<span class="tag">'
```

Expected: a non-zero count for each. Then open both pages in a browser and
hover a marker with two conferences on it.

---

## Self-review

**Spec coverage.** Every section maps to a task: the crop and the caption to
Task 2; one marker per venue with the badge to Task 3; the two colours, the
legend and the amber constraint to Task 4; zoom, `svgzoom.js` and the city
names to Task 5; the card listing N conferences to Task 6; the hover panel,
including keyboard focus, to Task 7; the digest entry to Task 1; the browser
check to Task 8. The spec's out-of-scope list is respected — no task touches
`map.js`, the experiments map, `figure.js`'s exclusions, the conference list,
the timeline, or the Experimental/Theory split.

**Placeholders.** None. Two steps deliberately say "read the existing list and
match its shape" — Task 4 Step 5 (`test_theme.js`'s pair list) and Task 5
Step 3 (the page's script list) — because those files' conventions must be
followed rather than guessed at from here; both name the exact file and the
exact entries to add.

**Type consistency.** `_conf_marker(confs, lon, lat, x, y, photo)` is defined
in Task 3 and called only there. `items(pin)` is defined in Task 6 and
consumed in Task 7. The marker contract — `.conf-pin` carrying
`data-place`/`data-lat`/`data-lon`/`data-photo*`, containing `.conf-item`
children carrying `data-conf`/`data-name`/`data-dates`/`data-url` — is written
identically in Tasks 3, 6 and 7. `_links_row(rec, skip=None)` and
`_human_date(iso)` are defined and used in Task 1 only.

**One thing to watch.** Task 1 Step 6 and Task 5 Step 4 both need the
generated `digest.md` / `conferences.md` regenerated, and the only reliable
way to do that is `./update-daily`, which fetches. If the network is
unavailable, the pipeline's cache under `var/news/cache/` holds today's
records and the run will use them — but say so in the commit rather than
letting a stale page pass for a rebuilt one.
