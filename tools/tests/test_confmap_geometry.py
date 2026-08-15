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

# The marker must sit where projection puts it, undistorted. Parsed off the
# marker's own <circle>, not substring-matched against the whole document:
# wm.LAND_PATH is thousands of two-decimal coordinates, so an f'{y:.1f}' in
# svg check can pass by coincidence — which is exactly what it did against
# the old, squashed code (see the control below).
x, y = wm.project(16.87, 41.12)
# The marker's own <circle> sits at the origin of a translated <g> now (see
# _conf_marker: r has no cx/cy, translate(x y) on the group carries the
# position instead, so svgzoom.js can counter-scale the whole group by its
# data-fixed anchor). The position check below reads that translate, not a
# cx/cy pair that no longer exists.
cm = re.search(r'class="conf-pin".*?transform="translate\(([-\d.]+) ([-\d.]+)\)"', svg)
check("the marker's circle is present", cm is not None, svg[:200])
if cm:
    cx, cy = float(cm.group(1)), float(cm.group(2))
    check("the marker sits at the undistorted projection",
          abs(cx - x) < 0.05 and abs(cy - y) < 0.05,
          f"circle at {cx},{cy}; expected {x:.1f},{y:.1f}")

    # Control: proves the check above actually discriminates. Under the old
    # scale(1,.5) squash this same marker drew at y*0.5, ~49 units away from
    # the true y for Bari — nowhere near the <0.05 tolerance above, so a
    # regression back to the squash fails this check rather than silently
    # passing it the way the old substring match did.
    squashed_y = y * 0.5
    check("this check would have caught the old squash (control)",
          abs(cy - squashed_y) > 5.0,
          f"cy={cy}, squashed would be {squashed_y:.1f} — too close to tell apart")

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
check("the general marker uses the accent-2 token",
      "var(--accent-2)" in svgm,
      "not --dec-4: --on-accent on it measured 4.27:1 in the dark theme")
check("amber is not used as a category colour",
      "var(--io)" not in svgm,
      "amber already means 'in progress right now' on this page")
check("the legend names both categories",
      "Neutrino" in svgm and "General particle physics" in svgm, svgm[-700:])

only_nu = figures.conference_map([MIXED[0]])
check("a legend entry with nothing to label is not drawn",
      "General particle physics" not in only_nu)

# --- a legend must never label a colour that isn't on any dot -------------
# MIXED above can't catch this: Bari and Tokyo are thousands of units apart,
# so they never share a cluster. Two conferences at the SAME spot cluster
# into ONE marker, painted from confs[0] alone (_marker_scope) — so if the
# legend were built from every raw point instead of that same confs[0], it
# could draw a swatch for the scope that got folded away, describing a
# colour that appears nowhere on the map.
SAME_SPOT = [
    ({"id": "n2", "title": "A Neutrino Meeting Here", "url": "https://n2.example/",
      "extra": {"place": "Bari, Italy", "city": "Bari", "span": "1-5 Sep 2026",
                "scope": "neutrino"}}, 16.87, 41.12),
    ({"id": "g2", "title": "A General Meeting Here", "url": "https://g2.example/",
      "extra": {"place": "Bari, Italy", "city": "Bari", "span": "1-5 Sep 2026",
                "scope": "general"}}, 16.87, 41.12),
]
svgs = figures.conference_map(SAME_SPOT)

check("two conferences at the same spot draw ONE marker",
      svgs.count('class="conf-pin"') == 1,
      f'found {svgs.count(chr(34) + "conf-pin" + chr(34))} markers')

# A dot's own circle: <circle r="..." fill="COLOUR" stroke="var(--bg)" ...>.
# The legend's swatch circle carries cx/cy and no stroke, so this pattern
# only matches colours actually worn by a marker on the map.
dot_colours = set(re.findall(
    r'<circle r="[\d.]+" fill="(var\(--[\w-]+\))" stroke="var\(--bg\)"', svgs))
# The legend's own swatch: <circle cx="..." cy="..." r="4" fill="COLOUR"/>.
legend_colours = set(re.findall(
    r'<circle cx="[\d.]+" cy="[\d.]+" r="4" fill="(var\(--[\w-]+\))"/>', svgs))

check("only the first conference's colour is actually on the map",
      dot_colours == {"var(--no)"}, dot_colours)
check("the legend never advertises a colour no dot wears",
      legend_colours <= dot_colours,
      f"legend={legend_colours} dots={dot_colours}")
check("the general conference is folded into the neutrino dot, so its "
      "legend entry is not drawn",
      "General particle physics" not in svgs)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the map is cropped, not squashed")
