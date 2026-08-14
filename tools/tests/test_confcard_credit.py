#!/usr/bin/env python3
"""A conference card's photo credit must be visible without scrolling.

    ./.venv/bin/python3 tools/tests/test_confcard_credit.py

The conference map's card (site-src/assets/js/confmap.js, styled by
.conf-card in site.css) shows a Wikimedia Commons photograph of the host
city when photos.py found one under a licence that permits reuse. CC BY and
CC BY-SA both require attribution "reasonable to the medium" — the credit
line (author, licence, Commons link) is not decoration, it is the thing
that makes publishing the photograph legal at all.

.conf-card's `max-height:min(60vh,20rem)` combined with `overflow-y:auto`
was copied forward from an earlier fix (Task 4) that capped the card
against the viewport so it stopped clipping mid-title. That fix solved the
title case but not the photo case: a card with a photo is taller than
20rem's worth of title+dates+links+photo+credit, so the credit rendered
~20px below the card's own visible bottom edge at every measured viewport
size — reachable only by scrolling *inside* the card, which a reader has no
reason to try since nothing above the fold hints there is more below it.

jsdom (tools/tests/test_confmap.js) cannot catch this: it never lays out
CSS, so a credit element sitting outside its container's visible box and
one sitting comfortably inside it look identical to a DOM query — both are
just present in the tree. This is the fourth SVG/CSS sizing bug on this
project invisible to structural tests; test_timeline_proportion.py is the
precedent for using a real, Playwright-driven Chromium instead.

The fix (site-src/assets/css/site.css) shrinks .conf-card__photo img from
.map-card's 4:3 to 5:2 rather than raising the card's max-height — raising
it was tried first and rejected because this card is anchored bottom-left
of a stage that sits near the page top on a short viewport, so a taller
card grows upward into the sticky .site-header (verified with a real
screenshot, see the CSS comment). The photo is decoration; the credit
under it is the obligation, so the photo is what gives way.

Requires the `playwright` package and its Chromium build, both provisioned
by ./setup-venv.sh.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PAGE = SITE / "conferences.html"

# The three viewports the live-site defect was measured at: a normal desktop
# window, a short desktop window (the case that most tightens the 60vh
# term), and a phone in portrait, where wrapped title/meta/actions text
# leaves the least headroom to give back.
VIEWPORTS = [
    {"width": 1280, "height": 900},
    {"width": 1280, "height": 600},
    {"width": 375, "height": 700},
]

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
        for vp in VIEWPORTS:
            label_vp = f"{vp['width']}x{vp['height']}"
            page = browser.new_page(viewport=vp)
            page.goto(url)
            page.wait_for_selector(".conf-pin")

            # Any conference pin carrying a photo — not a specific city name,
            # since the conference list is refreshed daily and today's
            # photographed cities are not guaranteed to still be in the data
            # tomorrow. The other markers omit data-photo entirely.
            pin = page.query_selector(".conf-pin[data-photo]")
            check(f"[{label_vp}] a conference pin with a photo exists", pin is not None)

            if pin is not None:
                pin.scroll_into_view_if_needed()
                pin.dispatch_event("click")
                page.wait_for_selector(".conf-card")

                card = page.query_selector(".conf-card")
                credit = page.query_selector(".conf-card__credit")
                check(f"[{label_vp}] card opens", card is not None)
                check(f"[{label_vp}] credit element renders", credit is not None)

                if card is not None and credit is not None:
                    card_box = card.bounding_box()
                    credit_box = credit.bounding_box()
                    check(
                        f"[{label_vp}] both the card and the credit have a real box",
                        bool(card_box and credit_box and card_box["height"] > 0
                             and credit_box["height"] > 0),
                        f"card={card_box}  credit={credit_box}",
                    )

                    if card_box and credit_box:
                        card_top = card_box["y"]
                        card_bottom = card_box["y"] + card_box["height"]
                        credit_top = credit_box["y"]
                        credit_bottom = credit_box["y"] + credit_box["height"]
                        inside = credit_top >= card_top and credit_bottom <= card_bottom

                        check(
                            f"[{label_vp}] the credit's bounding box lies within the "
                            f"card's visible box (no scrolling needed to read it)",
                            inside,
                            f"card=[{card_top:.1f}, {card_bottom:.1f}]  "
                            f"credit=[{credit_top:.1f}, {credit_bottom:.1f}]  "
                            f"credit sits {credit_bottom - card_bottom:.1f}px past the "
                            f"card's visible bottom" if not inside else "",
                        )

            page.close()
        browser.close()

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the photo credit is visible without scrolling "
      f"at every measured viewport")
