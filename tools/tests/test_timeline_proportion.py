#!/usr/bin/env python3
"""The conference timeline scrolls sideways, and does not dwarf the map above it.

    ./.venv/bin/python3 tools/tests/test_timeline_proportion.py

Two properties of the same rule, neither of them visible to a structural
test.

The first is the timeline's whole design: it draws a year of calendar at a
fixed scale — figures.VIEW units to figures.MONTHS_VISIBLE months — and is
therefore WIDER than the card it sits in, which scrolls
(`.figure .timeline-scroll` in site.css). Every other figure on the site
fills its card instead, via the generic `.figure svg{width:100%}`; if that
rule ever wins here, the whole year is scaled back into one screenful and
every meeting in a busy month lands inside the same four pixels — the exact
squash the fixed scale exists to prevent, and the page would look fine while
being useless. So the checks below measure what a browser actually laid out:
that the drawing overflows its scroll box, and that a screenful really is
about four months.

The second is the older bug this file was written for. Task 6's browser pass
found `.figure svg{width:100%}` stretching the then-520x326 strip to fill a
~1064px card, computing a 667px-tall drawing — nearly three times the map's
239px on the same page. Keeping the drawing at its own size settles that too
(a fixed scale cannot stretch), but the assertion stays: it is cheap, and it
is the one that fails if some future rule starts scaling this figure by its
card again.

Nothing in the JS suite catches either one, and nothing could: jsdom does not
lay out CSS, so `width:100%` and `width:auto` are indistinguishable to it —
both just sit in a stylesheet no assertion reads. This is the third
SVG-sizing bug on this project invisible to structural tests (after a figure
zoom that didn't enlarge anything, and a card clipped to its own title). The
only thing that catches them is asking a real browser to lay the page out and
measuring what comes back — hence Playwright here rather than another jsdom
fixture.

Requires the `playwright` package and its Chromium build, both provisioned
by ./setup-venv.sh — see the `playwright install chromium` step there.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.news.figures import VIEW as VIEW_UNITS        # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PAGE = SITE / "conferences.html"

# 1280px is where the old stretching bug showed, and it is also the width the
# figure's scale is drawn for: a ~1064px card at this viewport is about four
# months of calendar. A narrower screen shows less of the year rather than
# smaller type, so the months-visible check below is asserted here only.
VIEWPORT = {"width": 1280, "height": 900}

# Broken (drawing scaled to its card): measured 2.79x. Fixed: measured 0.94x.
# 2.0 sits with real margin on both sides — the test is asking "does the
# timeline still dwarf the map", not "is the ratio some exact number".
MAX_HEIGHT_RATIO = 2.0

# Four months, give or take the length of the months in view. The window is
# wide because this asserts the DESIGN (a screenful is a few months, not a
# year and not a fortnight), not the arithmetic, which test_figures.py owns.
MONTHS_VISIBLE = (3.0, 5.5)

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


if not PAGE.exists():
    check("site/conferences.html exists", False, "run ./.venv/bin/python3 build.py first")
else:
    url = "file://" + str(PAGE.resolve())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        page.goto(url)
        page.wait_for_selector(".figure .timeline-scroll svg")

        timeline_svg = page.query_selector(".figure .timeline-scroll svg")
        map_svg = page.query_selector(".confmap-figure svg")

        check("timeline svg found in the rendered page", timeline_svg is not None)
        check("map svg found in the rendered page", map_svg is not None)

        if timeline_svg is not None and map_svg is not None:
            timeline_box = timeline_svg.bounding_box()
            map_box = map_svg.bounding_box()

            check(
                "both figures render with non-zero size",
                bool(timeline_box and map_box and timeline_box["height"] > 0 and map_box["height"] > 0),
                f"timeline={timeline_box}  map={map_box}",
            )

            if timeline_box and map_box and map_box["height"] > 0:
                ratio = timeline_box["height"] / map_box["height"]
                check(
                    f"timeline svg height stays within {MAX_HEIGHT_RATIO}x the map svg's "
                    f"height at {VIEWPORT['width']}px (measured {ratio:.2f}x)",
                    ratio <= MAX_HEIGHT_RATIO,
                    f"timeline height={timeline_box['height']:.1f}px, "
                    f"map height={map_box['height']:.1f}px, ratio={ratio:.2f}",
                )

        # The drawing must overflow its scroll box — that is the feature.
        geom = page.evaluate("""() => {
            const box = document.querySelector('.figure .timeline-scroll');
            const svg = box.querySelector('svg');
            const r = svg.getBoundingClientRect();
            return {card: box.clientWidth, drawn: r.width,
                    units: svg.viewBox.baseVal.width};
        }""")
        check(f"the drawing is wider than the card it scrolls in "
              f"({geom['drawn']:.0f}px drawn, {geom['card']:.0f}px of card)",
              geom["drawn"] > geom["card"] * 1.5, str(geom))

        # ...and a cardful of it is a few months, not the whole year.
        per_unit = geom["drawn"] / geom["units"] if geom["units"] else 0
        months = (geom["card"] / per_unit) / (VIEW_UNITS / 4) if per_unit else 0
        lo_m, hi_m = MONTHS_VISIBLE
        check(f"a cardful of the timeline is {months:.1f} months of calendar, "
              f"within the intended {lo_m}–{hi_m}",
              lo_m <= months <= hi_m, str(geom))

        browser.close()

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the timeline scrolls at its own scale, and does not dwarf the map above it")
