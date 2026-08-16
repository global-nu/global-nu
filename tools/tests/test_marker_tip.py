#!/usr/bin/env python3
"""Every plotted point carries its own facts, and says what its interval is.

    ./.venv/bin/python3 tools/tests/test_marker_tip.py

The panels are read at two sizes. Small, in the page, a marker is four pixels
across and the only way to ask what it is was the SVG <title> the browser
shows after a second, in system grey. Enlarged, where the point is big enough
to aim at, that same tooltip is all there was. The hover panel this file
guards renders from data- attributes rather than by parsing that <title>
string, so these checks are what stands between a plotted point and a popup
that shows the wrong group or a blank.

The first check is not about the popup at all. panel() drew every interval
labelled "3σ" whichever it was, and nine entries in history.yaml publish only
a 1σ range — a 1σ interval was reaching the site announced as 3σ. Surfacing
the same number in a panel a reader can actually read makes that worse, so it
is fixed here and pinned by the first check below.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import history                             # noqa: E402
import make_history                                    # noqa: E402

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


# --- an interval is labelled by what it is ---------------------------------

ONE_SIGMA_ONLY = [{
    "group": "bari", "year": 2012,
    "values": {"delta_pi": {"no": {"best": 1.08, "s1": [0.77, 1.36]}}},
}]
THREE_SIGMA = [{
    "group": "bari", "year": 2018,
    "values": {"delta_pi": {"no": {"best": 1.32, "s3": [0.83, 1.99]}}},
}]
META = {"label": "δ/π", "unit": "1"}

svg1 = make_history.panel("delta_pi", META, ONE_SIGMA_ONLY)
# The drawing only: the caption below it names 3σ legitimately, to say that
# this panel had to fall back from it.
drawing1 = svg1.split("</svg>")[0]
check("a 1σ-only entry is never announced as 3σ",
      "3σ" not in drawing1 and "1σ 0.77–1.36" in drawing1,
      drawing1[-400:])

svg3 = make_history.panel("delta_pi", META, THREE_SIGMA)
check("a genuine 3σ entry still says 3σ",
      "3σ 0.83–1.99" in svg3, svg3[:400])

check("the caption warns when a panel had to fall back to 1σ",
      "1σ" in svg1.split('class="cap"')[1],
      svg1.split('class="cap"')[-1][:220])

check("the caption stays quiet when every point is 3σ",
      "1σ" not in svg3.split('class="cap"')[1],
      svg3.split('class="cap"')[-1][:220])


# --- every marker carries its facts ----------------------------------------

doc = history.load()
params = doc["meta"]["parameters"]
all_releases = sorted(doc["releases"], key=lambda r: (r["year"], r["group"]))
bari = [r for r in all_releases if r["group"] == "bari"]

drawn = "\n".join(
    [make_history.panel(k, v, bari) for k, v in params.items()] +
    [make_history.compare_panel(k, v, all_releases) for k, v in params.items()])

MARKERS = re.findall(r'<g class="pt"[^>]*>', drawn)
check("the panels draw markers at all", len(MARKERS) > 100, f"found {len(MARKERS)}")

REQUIRED = ("data-group", "data-year", "data-param", "data-value",
            "data-unit", "data-ordering")
missing = [m for m in MARKERS if any(a + '="' not in m for a in REQUIRED)]
check("every marker carries group, year, parameter, value, unit and ordering",
      not missing, f"{len(missing)} without, first: {missing[0] if missing else ''}")

blank = [m for m in MARKERS
         if re.search(r'data-(group|year|param|value|unit|ordering)=""', m)]
check("and none of those facts is empty",
      not blank, f"{len(blank)} blank, first: {blank[0] if blank else ''}")

limits = [m for m in MARKERS if 'data-kind="limit"' in m]
check("limits are marked as limits", len(limits) > 0, "no limit markers found")
check("every limit carries the level its bound holds at",
      all(re.search(r'data-level="[^"]+"', m) for m in limits),
      next((m for m in limits if not re.search(r'data-level="[^"]+"', m)), ""))

check("a measurement's range, when it has one, carries its own level",
      all(re.match(r'^[13]σ ', re.search(r'data-range="([^"]*)"', m).group(1))
          for m in MARKERS
          if re.search(r'data-range="([^"]+)"', m)),
      "a data-range that does not open with its sigma level")

check("the <title> survives as the no-JavaScript fallback",
      drawn.count("<title>") >= len(MARKERS),
      f"{drawn.count('<title>')} titles for {len(MARKERS)} markers")

check("every marker has a hit area wider than the ink",
      drawn.count('class="pt__hit"') == len(MARKERS),
      f"{drawn.count('class=\"pt__hit\"')} hit areas for {len(MARKERS)} markers")

check("the hit area is invisible and does not steal the ink's colour",
      'class="pt__hit"' not in drawn or 'fill="none" pointer-events="all"' in drawn,
      "hit circles must be unfilled but still receive the pointer")


# --- a marker cannot be drawn mute -----------------------------------------

try:
    make_history.marker("no", 1, 2, "red", "label")
except SystemExit as exc:
    check("drawing a marker without its facts is refused", "facts" in str(exc), str(exc))
except TypeError:
    check("drawing a marker without its facts is refused", True)
else:
    check("drawing a marker without its facts is refused", False,
          "marker() drew a point carrying nothing to show")

print(f"\n{checks - len(problems)}/{checks} checks passed")
if problems:
    print("failed: " + ", ".join(problems))
    raise SystemExit(1)
