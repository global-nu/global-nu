#!/usr/bin/env python3
"""The shape of a recorded value, checked before it can reach a page.

    ./.venv/bin/python3 tools/tests/test_history_schema.py

Until now every value in history.yaml was a measurement: a best fit with
ranges. Early papers bound a parameter instead of measuring it, and a bound
without its confidence level is not a datum — "sin²θ₁₃ < 0.05" means different
things at 90% CL and at 3σ. So a value is a measurement or a limit, never both
and never neither, and a limit names its level.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

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


# 1. the real file loads
doc = history.load()
check("history.yaml loads and validates", bool(doc.get("releases")))

# 2. classification
check("a best fit with ranges is a measurement",
      history.kind_of({"best": 2.23, "s3": [2.05, 2.41]}) == "measurement")
check("an upper bound with a level is a limit",
      history.kind_of({"upper": 5.0, "level": "3sigma"}) == "limit")

# 3. malformed records are rejected, built here rather than by editing the data
def rejects(entry: dict) -> bool:
    try:
        history.validate_value("sin2_th13", "no", entry)
        return False
    except SystemExit:
        return True

check("a value that is both a measurement and a limit is rejected",
      rejects({"best": 2.2, "s3": [2.0, 2.4], "upper": 5.0, "level": "3sigma"}))
check("a value that is neither is rejected", rejects({"note": "unclear"}))


def message(entry: dict) -> str:
    """The text of the SystemExit validate_value raises for entry."""
    try:
        history.validate_value("sin2_th13", "no", entry)
        return ""
    except SystemExit as exc:
        return str(exc)


# The two rejections above share a code path but must not share a sentence:
# "is neither" would send a reader hunting for a missing field when the real
# problem is an extra one.
check("the 'both' rejection says so, not 'neither'",
      "both a measurement and a limit"
      in message({"best": 2.2, "s3": [2.0, 2.4], "upper": 5.0, "level": "3sigma"}))
check("the 'neither' rejection says so, not 'both'",
      "neither a measurement nor a limit" in message({"note": "unclear"}))

check("a limit with no level is rejected", rejects({"upper": 5.0}))
check("a limit with an unknown level is rejected",
      rejects({"upper": 5.0, "level": "eyeballed"}))
check("a limit with a known level is accepted",
      not rejects({"upper": 5.0, "level": "90%CL"}))

# 4. the label a reader sees
check("a limit's label states the bound and the level",
      history.limit_label({"upper": 5.0, "level": "3sigma"}) == "< 5.0 (3σ)")

# 5. rendering
sys.path.insert(0, str(ROOT / "tools"))
import make_history                                     # noqa: E402

svg = make_history.marker("limit-upper", 100.0, 50.0, "var(--no)", "< 5.0 (3σ)")
diamond = make_history.marker("any", 100.0, 50.0, "var(--no)", "< 5.0 (3σ)")
check("a limit renders differently from the diamond fallback, same point",
      svg != diamond,
      f"limit:   {svg[:90]}\n         diamond: {diamond[:90]}")
check("a limit's marker is stroked and unfilled, unlike every filled shape",
      'fill="none"' in svg,
      f"got: {svg[:90]}")
check("a limit's marker carries its label", "< 5.0 (3σ)" in svg)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — every recorded value is a measurement or a limit")
