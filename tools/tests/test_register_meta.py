#!/usr/bin/env python3
"""Check that the facts the metadata states are computed, not typed.

    ./.venv/bin/python3 tools/tests/test_register_meta.py

Every one of these values appears in published metadata — the
schema.org/Dataset block on history.html and the Zenodo deposit. A
hand-written year span or parameter list is a value that rots the first time
a release is added, and nothing on the page would show it had.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import register_meta                          # noqa: E402

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


import subprocess                                       # noqa: E402


def _git_date(path) -> str | None:
    """The same question the module asks git, asked independently here."""
    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                         cwd=ROOT, capture_output=True, text=True, check=False)
    d = out.stdout.strip()
    return d if len(d) == 10 else None


facts = register_meta.register_facts()
rows = json.loads(register_meta.EXPORT.read_text(encoding="utf-8"))["rows"]

lo, hi = min(r["year"] for r in rows), max(r["year"] for r in rows)
check("temporalCoverage spans the register's real years",
      facts["temporal_coverage"] == f"{lo}/{hi}",
      f"got {facts['temporal_coverage']!r}, export says {lo}/{hi}")

check("years agrees with temporal_coverage", facts["years"] == (lo, hi))

check("n_rows counts every exported row",
      facts["n_rows"] == len(rows), f"got {facts['n_rows']}, export has {len(rows)}")

named = {v["name"] for v in facts["variables"]}
exported = {r["parameter"] for r in rows}
check("variableMeasured lists exactly the exported parameters",
      named == exported, f"metadata {sorted(named)} vs export {sorted(exported)}")

# A unit is omitted, never defaulted, when meta.parameters does not carry one
# — so an omission here is real, and every exported parameter is expected to
# have one today. This fails if a new parameter reaches the export without a
# unit, which is the case the omission exists to handle honestly.
check("every variable carries a label and a unit",
      all(v.get("label") and v.get("unit") for v in facts["variables"]),
      str([v for v in facts["variables"] if not (v.get("label") and v.get("unit"))]))

check("the title is computed, and carries the register's real year span",
      facts["title"] == register_meta.TITLE.format(lo=lo, hi=hi),
      facts["title"])
check("the title states the span the rows actually cover",
      f"({lo}–{hi})" in facts["title"], facts["title"])

# date_modified may legitimately be None (no git, or the file untracked), but
# it must never be today's build date dressed up as the export's date.
import datetime as _dt                                    # noqa: E402
dm = facts["date_modified"]
check("date_modified is an ISO date or None",
      dm is None or len(dm) == 10 and dm[4] == dm[7] == "-", f"got {dm!r}")
check("date_modified is exactly the export's own last commit date",
      dm == _git_date(register_meta.EXPORT),
      f"module says {dm!r}, git says {_git_date(register_meta.EXPORT)!r}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the register's facts are computed from the register")
