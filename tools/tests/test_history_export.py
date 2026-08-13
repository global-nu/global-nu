#!/usr/bin/env python3
"""The exported register agrees with history.yaml, and its two value columns
mean what they say.

    ./.venv/bin/python3 tools/make_history_data.py   # first, to write the export
    ./.venv/bin/python3 tools/tests/test_history_export.py

Same "both directions" shape as test_experiments.py's page/YAML drift check:
every point recorded in history.yaml must reach the export, and every row in
the export must trace back to a point in history.yaml — one direction alone
would miss a value the exporter silently dropped, the other would miss a row
invented that history.yaml does not contain.

Check 4 does not trust the exporter's own arithmetic: it recomputes
value_our_convention independently by calling tools.make_history.to_our_Dm2()
itself — the same interface the exporter is required to use — rather than
re-reading the number the exporter already wrote.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import make_history                                     # noqa: E402

JSON_PATH = ROOT / "data-exports" / "history.json"
CSV_PATH = ROOT / "data-exports" / "history.csv"

# The YAML keys that all record the same physical quantity, Delta m^2, under
# different names depending on which group's convention it is printed in:
# Bari's own "Dm2" already IS our convention; NuFit's "Dm2_3l" and Valencia's
# "abs_Dm2_31" are not. All three are exported under the canonical parameter
# name "Dm2" — see tools/make_history_data.py.
DM2_KEYS = {"Dm2", "Dm2_3l", "abs_Dm2_31"}

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        if detail:
            print(f"         {detail}")
        problems.append(label)


if not JSON_PATH.exists() or not CSV_PATH.exists():
    sys.exit("data-exports/history.json or history.csv not found — run "
             "./.venv/bin/python3 tools/make_history_data.py first")

doc = history.load()
export = json.loads(JSON_PATH.read_text(encoding="utf-8"))
rows = export["rows"]

with CSV_PATH.open(encoding="utf-8", newline="") as fh:
    csv_rows = list(csv.DictReader(fh))

# 1 & 2. every YAML point reaches the export, and every export row traces to
# a YAML point — both directions.
from_yaml: set[tuple] = set()
for rel in doc["releases"]:
    for pname, by_ordering in (rel.get("values") or {}).items():
        canonical = "Dm2" if pname in DM2_KEYS else pname
        for ordering in by_ordering:
            from_yaml.add((rel["group"], rel["year"], canonical, ordering))

in_export = {(r["group"], r["year"], r["parameter"], r["ordering"]) for r in rows}

missing = sorted(from_yaml - in_export)
check("every point in history.yaml reaches the export", not missing,
      "; ".join(f"{g} {y} {p}/{o}" for g, y, p, o in missing[:8]))

extra = sorted(in_export - from_yaml)
check("every row in the export traces back to a point in history.yaml", not extra,
      "; ".join(f"{g} {y} {p}/{o}" for g, y, p, o in extra[:8]))

# 3. CSV and JSON agree on row count
check("the CSV has the same row count as the JSON",
      len(csv_rows) == len(rows),
      f"json={len(rows)} csv={len(csv_rows)}")

# 4. value_our_convention holds the right number, recomputed independently —
# to_our_Dm2() for a Dm2 row not sourced from Bari (Bari already publishes in
# our convention, so its own Dm2 needs no conversion and has no
# reported_splitting field for to_our_Dm2 to read), value_as_published
# verbatim for every other row.
rel_by_group_year = {(r["group"], r["year"]): r for r in doc["releases"]}
bad_conversion = []
for r in rows:
    rel = rel_by_group_year[(r["group"], r["year"])]
    published = r["value_as_published"]
    converted = r["value_our_convention"]
    if r["parameter"] == "Dm2" and rel["group"] != "bari":
        expected = make_history.to_our_Dm2(rel, r["ordering"], published)
        ok = converted == expected
    else:
        ok = converted == published
    if not ok:
        bad_conversion.append(
            f"{r['group']} {r['year']} {r['parameter']}/{r['ordering']}: "
            f"published={published} our={converted}")
check("value_our_convention holds the right number for every row",
      not bad_conversion, "; ".join(bad_conversion[:8]))

# 5. the level column is present exactly for limit rows — not sometimes
# missing from a limit, not spuriously present on a measurement.
bad_level = [
    f"{r['group']} {r['year']} {r['parameter']}/{r['ordering']}"
    for r in rows
    if (r["kind"] == "limit") != bool(r.get("level"))
]
check("level is present for every limit row and only for limit rows",
      not bad_level, "; ".join(bad_level[:8]))

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
n_limits = sum(1 for r in rows if r["kind"] == "limit")
print(f"all {checks} checks pass — {len(rows)} rows ({n_limits} limits), "
      "exported and traced back to history.yaml in both directions")
