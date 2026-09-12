#!/usr/bin/env python3
"""The conference map must not distort the world.

    ./.venv/bin/python3 tools/tests/test_confmap_geometry.py

The map used to scale every y by 0.5 to stay short, and a caption apologised
for it in prose. Cropping the empty Arctic and the Antarctic smear gets the
shapes right instead, at the cost of a taller figure — 280 viewBox units
against the old 162, about 73% more height on the page, since .figure svg
sizes the card by the viewBox's own aspect ratio. That cost was accepted
deliberately; the squash, and the excuse for it, are gone. This test is what
stops either coming back.

It also polices what a marker may claim. A marker asserts a place — in its
<title>, its data-place, and everything confmap.js builds from those — so
only conferences at the SAME position may share one. See the NEAR fixture at
the end: fixtures that put every conference at one coordinate cannot tell a
position-identity grouping from a proximity merge, and for a while none of
them did.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import affinity                         # noqa: E402
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

# --- the colours are AFFINITY TIERS, and a legend that explains them ------
# The map used to colour by SCOPE (the neutrino calendar in --no, the general
# one in --accent-2). Antonio asked for closeness of the subject instead: the
# same five tiers the listing chips and the timeline bars already use, so the
# page carries one colour scale and not two. These checks moved with it.
def rec(id, title, tier, label, city, place, span="1-5 Sep 2026"):
    return {"id": id, "title": title, "url": f"https://{id}.example/",
            "extra": {"place": place, "city": city, "span": span,
                      "affinity": {"tier": tier, "label": label,
                                   "why": "fixture"}}}


MIXED = [
    (rec("n", "A Neutrino Meeting", "core", "Neutrino physics",
         "Bari", "Bari, Italy"), 16.87, 41.12),
    (rec("g", "A General Meeting", "broad", "Particle physics at large",
         "Tokyo", "Tokyo, Japan", "3-4 Oct 2026"), 139.69, 35.69),
]
svgm = figures.conference_map(MIXED)

check("a core marker wears the core tier token",
      affinity.TIER_COLOUR["core"] in svgm)
check("a broad marker wears the broad tier token",
      affinity.TIER_COLOUR["broad"] in svgm,
      "two tiers must not share a colour")
check("--dec-4 is still not used anywhere on the map",
      "var(--dec-4)" not in svgm,
      "its count digits measured 4.27:1 in the dark theme")
check("the legend names the tiers, in the records' own words",
      "Neutrino physics" in svgm and "Particle physics at large" in svgm,
      svgm[-700:])
check("the legend is worded like the section's other one",
      "Closeness of the subject" in svgm,
      "the map and the listing must not label one scale two ways")

only_nu = figures.conference_map([MIXED[0]])
check("a legend entry with nothing to label is not drawn",
      "Particle physics at large" not in only_nu)

# --- a mixed venue takes the STRONGEST tier present ----------------------
# Two conferences at the SAME spot cluster into ONE marker. The dot must be
# painted with the closest tier at that venue, not with whichever record
# sorts first: a city hosting one neutrino conference and one QCD workshop
# answers "yes, there is something here for you".
SAME_SPOT = [
    # The ADJACENT one first, so a "confs[0] decides" implementation fails.
    (rec("a2", "A QCD Workshop Here", "adjacent", "Adjacent fields",
         "Bari", "Bari, Italy"), 16.87, 41.12),
    (rec("n2", "A Neutrino Meeting Here", "core", "Neutrino physics",
         "Bari", "Bari, Italy"), 16.87, 41.12),
]
svgs = figures.conference_map(SAME_SPOT)

check("two conferences at the same spot draw ONE marker",
      svgs.count('class="conf-pin"') == 1,
      f'found {svgs.count(chr(34) + "conf-pin" + chr(34))} markers')

# A dot's own circle: <circle r="..." fill="COLOUR" stroke="var(--bg)" ...>.
dot_colours = set(re.findall(
    r'<circle r="[\d.]+" fill="(var\(--[\w-]+\))" stroke="var\(--bg\)"', svgs))
# The legend's own swatch: <circle cx="..." cy="..." r="4" fill="COLOUR"/>.
legend_colours = set(re.findall(
    r'<circle cx="[\d.]+" cy="[\d.]+" r="4" fill="(var\(--[\w-]+\))"/>', svgs))

check("a mixed venue takes the strongest tier, not the first record",
      dot_colours == {affinity.TIER_COLOUR["core"]},
      f"{dot_colours} — the adjacent record is listed first on purpose")
check("the legend's swatches are actually found by the test",
      bool(legend_colours), "the regex must match the markup it is checking")
check("the legend never advertises a colour no dot wears",
      legend_colours <= dot_colours,
      f"legend={legend_colours} dots={dot_colours}")

# "Does the legend say X" must be asked of the LEGEND, not of the whole SVG:
# the folded-away tier still appears in the marker's data attributes and in
# its <title>, which is exactly what we want.
legend_words = re.findall(
    r'<text x="[\d.]+" y="[\d.]+" style="fill:var\(--text-mute\);'
    r'font-size:9px;[^"]*">([^<]+)</text>', svgs)
check("the folded-away tier gets no legend entry of its own",
      "Adjacent fields" not in legend_words, str(legend_words))
check("the legend lists the tier the dot actually wears",
      "Neutrino physics" in legend_words, str(legend_words))
check("but the marker still NAMES the folded-away meeting's tier",
      'data-tier-label="Adjacent fields"' in svgs,
      "a mixed venue must not present its meetings under one label")
check("each meeting carries its own tier for the hover card",
      svgs.count('data-tier="core"') == 1
      and svgs.count('data-tier="adjacent"') == 1,
      "confmap.js reads these to chip each meeting separately")
check("an untagged record is `unknown`, not a guessed colour",
      f'fill="{affinity.TIER_COLOUR["unknown"]}"' in figures.conference_map(
          [({"id": "u", "title": "Untagged", "url": "https://u.example/",
             "extra": {"place": "Lima, Peru", "city": "Lima"}}, -77.0, -12.0)]))

# --- the legend must fit inside the map ----------------------------------
# The scope legend this replaced had two short labels and always fitted on
# one line. The five tier labels do not, so the legend wraps; this is what
# keeps it wrapping.
ALL_TIERS = [
    (rec(t, f"Meeting {t}", t, lab, f"City{i}", f"City{i}, Nowhere"),
     -150.0 + 40.0 * i, 10.0 + 3.0 * i)
    for i, (t, lab) in enumerate(
        [("core", "Neutrino physics"),
         ("related", "Astroparticle & underground"),
         ("broad", "Particle physics at large"),
         ("adjacent", "Adjacent fields"),
         ("unknown", "Not classified")])
]
svga = figures.conference_map(ALL_TIERS)
legend_text = re.findall(
    r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size:9px[^"]*">([^<]+)</text>',
    svga)
check("all five tiers reach the legend when all five are on the map",
      len(legend_text) == 6, f"{len(legend_text)} entries (5 tiers + the lead)")
widest = max(float(x) + 6.0 * len(t) for x, _, t in legend_text)
check("the legend does not run off the right edge of the map",
      widest <= wm.WIDTH,
      f"rightmost legend text ends at {widest:.0f}, map is {wm.WIDTH:.0f} wide")
check("it wraps onto more than one row to manage it",
      len({y for _, y, _ in legend_text}) > 1,
      str(sorted({y for _, y, _ in legend_text})))

# --- a marker must never speak for a city it is not in -------------------
# Every fixture above puts its conferences at ONE place and ONE coordinate,
# so each passes identically whether markers are grouped by identical
# position or merely by proximity — none of them can tell the two apart.
# This one can. Otranto and Corfu are ~1.5 degrees apart, i.e. ~3 units in
# a 720-unit-wide projection: inside the 6-unit proximity merge the map
# briefly used, and the reason the published map captioned a conference in
# Apulia "Corfu, Greece" and showed it a photograph of Corfu. Distinct
# cities are distinct venues; only an identical position may share a dot.
NEAR = [
    ({"id": "ot", "title": "Neutrino Oscillation Workshop",
      "url": "https://ot.example/",
      "extra": {"place": "Otranto (Lecce), Italy", "city": "Otranto",
                "span": "6-13 Sep 2026", "scope": "neutrino"}}, 18.49, 40.15),
    ({"id": "kf", "title": "Corfu Summer Institute", "url": "https://kf.example/",
      "extra": {"place": "Corfu, Greece", "city": "Corfu",
                "span": "1-10 Sep 2026", "scope": "neutrino"}}, 19.92, 39.62),
]
svgn = figures.conference_map(NEAR)

check("two nearby but DIFFERENT cities draw two markers",
      svgn.count('class="conf-pin"') == 2,
      f'found {svgn.count(chr(34) + "conf-pin" + chr(34))} markers')
check("neither nearby marker carries a count badge",
      ">2</text>" not in svgn,
      "a badge means 'this many conferences at this venue' — two cities is "
      "not one venue")

places = set(re.findall(r'<g class="conf-pin" data-place="([^"]*)"', svgn))
check("each marker keeps its own place",
      places == {"Otranto (Lecce), Italy", "Corfu, Greece"}, places)

coords = set(re.findall(r'data-lat="(-?[\d.]+)" data-lon="(-?[\d.]+)"', svgn))
check("each marker keeps its own coordinates",
      coords == {("40.1500", "18.4900"), ("39.6200", "19.9200")}, coords)

# The <title> is what a reader without JS gets, and the only place the
# conference name and the place appear together in the static SVG.
check("each conference's <title> names the city it is actually in",
      "Neutrino Oscillation Workshop — Otranto (Lecce), Italy" in svgn
      and "Corfu Summer Institute — Corfu, Greece" in svgn,
      re.findall(r"<title>[^<]*</title>", svgn))

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the map is cropped, not squashed")
