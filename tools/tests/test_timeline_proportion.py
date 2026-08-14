#!/usr/bin/env python3
"""The conference timeline must not dwarf the map above it.

    ./.venv/bin/python3 tools/tests/test_timeline_proportion.py

Task 6's browser pass found a real bug: the timeline's own
`<svg viewBox="0 0 520 326">` is a tall, 14-row Gantt strip. The generic
`.figure svg{width:100%}` rule stretched it to fill its ~1064px-wide card
at 1280px, computing a 667px-tall drawing — nearly three times the height of
the map figure's own svg (`viewBox="0 6 720 162"`, wide and short, 239px at
the same width) on the same page. The fix
(`.figure .timeline-scroll svg{max-width:620px}` in site.css) holds the
timeline near its own designed proportions instead of the card's.

Nothing in the JS suite caught this, and nothing could: jsdom does not lay
out CSS, so `width:100%` and `max-width:620px` are indistinguishable to it —
both just sit in a stylesheet no assertion reads. This is the third
SVG-sizing bug on this project invisible to structural tests (after a figure
zoom that didn't enlarge anything, and a card clipped to its own title). The
common thread: an SVG's viewBox is its intrinsic size, so `width:100%` in a
permissive container resolves to something nobody intended while every
DOM-shape assertion still passes. The only thing that catches it is asking a
real browser to lay the page out and measuring what comes back — hence
Playwright here rather than another jsdom fixture.

This check asserts the *proportion* the fix protects — the timeline's
rendered height against the map's, not the literal `620px` — so it survives
a future change to the cap's value but still fails the moment the cap (or
the behaviour it produces) goes away. Measured on this page, on this
machine: with the fix in place the timeline's svg renders at 1.62x the
map's svg height at 1280px; with the `max-width` rule deleted, 2.79x. The
threshold below (2.0) sits with real margin on both sides of that gap.

Requires the `playwright` package and its Chromium build, both provisioned
by ./setup-venv.sh — see the `playwright install chromium` step there.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PAGE = SITE / "conferences.html"

# Wide enough that the timeline's natural (uncapped) width would exceed the
# 620px cap — Task 6's own Step 4 measured this bug at 1280px; at 700px and
# 375px the card is already narrower than 620px and the cap never engages,
# which is why this check targets the width where the bug actually showed.
VIEWPORT = {"width": 1280, "height": 900}

# Broken (cap removed): measured 2.79x. Fixed: measured 1.62x. 2.0 sits with
# real margin on both sides — the test is asking "does the timeline still
# dwarf the map", not "is the ratio some exact number".
MAX_HEIGHT_RATIO = 2.0

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

        browser.close()

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — timeline no longer dwarfs the map above it")
