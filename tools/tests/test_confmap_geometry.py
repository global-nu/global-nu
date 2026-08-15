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
cm = re.search(r'<circle cx="([-\d.]+)" cy="([-\d.]+)"', svg)
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

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the map is cropped, not squashed")
