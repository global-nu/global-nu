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

Checks 1-5 compare identities and recompute arithmetic, but every one of them
reads the *committed* export's own numbers as its starting point, so none of
them can see a stale file: correct a `best` in history.yaml, forget to re-run
tools/make_history_data.py, and the old row stays perfectly self-consistent
while the superseded number keeps shipping at a stable, citable URL. Check 6
closes that by regenerating the rows from the current YAML in memory and
demanding the committed file equal them, row for row and field for field —
the drift check the rest of this file only looks like it is doing.
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
import make_history_data                                # noqa: E402

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
        # round() at the exporter's declared precision, not the exporter's
        # own rounding call: the arithmetic stays recomputed here, only the
        # published precision is read from history.VALUE_DP, which is the
        # one place it is decided. See that constant for why rounding there
        # can only remove IEEE noise from the subtraction.
        expected = round(make_history.to_our_Dm2(rel, r["ordering"], published),
                         history.VALUE_DP)
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

# 6. the committed export IS what the exporter produces from history.yaml as
# it stands today. Every check above starts from the numbers already in the
# file, so all of them pass on a stale export whose rows are internally
# consistent but no longer match the source — the single failure mode that
# matters here, because the file is published at a citable URL and a
# corrected value that never reached it is a superseded number still being
# handed out. Regenerated in memory; nothing is written.
expected_rows = make_history_data.build_rows(doc)

drift: list[str] = []
if len(expected_rows) != len(rows):
    drift.append(f"row count: committed {len(rows)}, regenerated {len(expected_rows)}")
for got, want in zip(rows, expected_rows):
    diffs = [f"{k}: committed {got.get(k)!r} vs current {want[k]!r}"
             for k in want if got.get(k) != want[k]]
    if diffs:
        drift.append(f"{want['group']} {want['year']} {want['parameter']}/"
                     f"{want['ordering']}: " + ", ".join(diffs))
check("the committed JSON export is what history.yaml produces today "
      "(re-run tools/make_history_data.py)", not drift, "; ".join(drift[:8]))

# …and the CSV alongside it, which is written in the same run and can go
# stale in exactly the same way. Compared as text, because that is what a CSV
# holds: the exporter writes None as an empty field and everything else via
# str(), so the expected text is built the same way.
csv_drift: list[str] = []
for got, want in zip(csv_rows, expected_rows):
    want_text = {k: ("" if want[k] is None else str(want[k]))
                 for k in make_history_data.FIELDS}
    diffs = [f"{k}: committed {got.get(k)!r} vs current {want_text[k]!r}"
             for k in want_text if got.get(k) != want_text[k]]
    if diffs:
        csv_drift.append(f"{want['group']} {want['year']} {want['parameter']}/"
                         f"{want['ordering']}: " + ", ".join(diffs))
check("the committed CSV export is what history.yaml produces today",
      not csv_drift, "; ".join(csv_drift[:8]))

# --------------------------------------------------------------------------- #
# the uncertainties, and how they survive a change of convention
#
# A register of measurements that exports only central values is not a register
# of measurements. And once the intervals are there, the question Antonio put
# on 2026-08-16 has to be answerable from the file itself: how do the errors
# transform when Dm2 is converted between conventions?
#
# The conversion is a constant offset of dm2/2. On the 2025 Bari release that
# offset is 1.8 sigma of Dm2, while the uncertainty it adds is 4% of sigma(Dm2)
# — 0.08% once added in quadrature. So the central value moves by nearly two
# standard deviations and the error bar essentially does not move at all, which
# is exactly why the two must be documented separately and neither guessed.
#
# `interval_method` records which treatment produced the converted interval, so
# a shifted one and a properly reprojected one can never be mistaken for each
# other in the file. Today nothing is reprojected: the published papers do not
# carry the joint dm2-Dm2 information that would take. The next Bari release
# can, and this column is where that shows up.
# --------------------------------------------------------------------------- #
INTERVAL_FIELDS = [
    "s1_lo_as_published", "s1_hi_as_published",
    "s3_lo_as_published", "s3_hi_as_published",
    "s1_lo_our_convention", "s1_hi_our_convention",
    "s3_lo_our_convention", "s3_hi_our_convention",
]

for field in INTERVAL_FIELDS + ["interval_method"]:
    check(f"the export carries {field}", field in make_history_data.FIELDS)

check("every exported column is documented",
      [n for n, _ in make_history_data.FIELD_DOCS] == make_history_data.FIELDS)

measured = [r for r in rows if r["kind"] == "measurement"]

# Six of these — the oldest releases — carry a best fit and no interval,
# because the cited table printed none. The register transcribes what a paper
# printed and does not invent a range, so "every measurement has an interval"
# is a claim about the literature that is simply false. What must hold is that
# an interval is never half-present.
for level in ("s1", "s3"):
    for suffix in ("as_published", "our_convention"):
        lo, hi = f"{level}_lo_{suffix}", f"{level}_hi_{suffix}"
        check(f"no row carries half of {level}_{suffix}",
              all((r[lo] is None) == (r[hi] is None) for r in rows),
              "one end of an interval without the other is unusable")

check("interval_method is set exactly when there is an interval to describe",
      all(bool(r.get("interval_method"))
          == any(r.get(f) is not None for f in INTERVAL_FIELDS)
          for r in measured),
      "naming the method of an interval that does not exist says nothing")

check("interval_method only ever takes a value the documentation defines",
      {r.get("interval_method") for r in measured}
      <= {"identical", "propagated", "propagated_rho", None},
      str({r.get("interval_method") for r in measured}))

# Five of the six parameters are reported the same way by every group, so
# nothing is converted and the two conventions must hold identical numbers.
unconverted = [r for r in measured if r["parameter"] != "Dm2"]
check("a parameter nobody converts is marked identical",
      all(r["interval_method"] in ("identical", None) for r in unconverted),
      str({r["interval_method"] for r in unconverted}))
check("and its two conventions carry the same interval",
      all(r["s3_lo_as_published"] == r["s3_lo_our_convention"]
          and r["s3_hi_as_published"] == r["s3_hi_our_convention"]
          for r in unconverted if r["s3_lo_as_published"] is not None))

# Dm2 as reported by NuFit and Valencia is the one that moves.
converted = [r for r in measured
             if r["parameter"] == "Dm2" and r["group"] != "bari"]
check("a converted Dm2 row is marked propagated, not identical",
      converted and all(r["interval_method"] == "propagated" for r in converted),
      str({r["interval_method"] for r in converted}))
check("a converted Dm2 row's interval really did move",
      all(r["s3_lo_as_published"] != r["s3_lo_our_convention"]
          for r in converted if r["s3_lo_as_published"] is not None),
      "an unchanged interval on a converted row means the shift was not applied")

# The width is what a reader compares across groups; the offset must not
# change it. Anything else would mean the endpoints were shifted by different
# amounts, which is not what a constant offset does.
grew = 0
for r in converted:
    if r["s3_lo_as_published"] is None:
        continue
    w_pub = r["s3_hi_as_published"] - r["s3_lo_as_published"]
    w_our = r["s3_hi_our_convention"] - r["s3_lo_our_convention"]
    # Propagation can only add variance, so the converted range is never
    # narrower. It is often EQUAL, and that is not a failure: the bounds are
    # printed at the source's own precision, and for most releases sigma(dm2)/2
    # is smaller than the last digit the paper printed. Claiming otherwise
    # would mean printing digits nobody measured.
    check(f"the propagated 3s width never shrank for {r['group']} {r['year']} "
          f"{r['ordering']}", w_our >= w_pub - 1e-12,
          f"published {w_pub:.5f} vs converted {w_our:.5f} — narrower is "
          f"impossible when a variance is added")
    if w_our > w_pub + 1e-12:
        grew += 1

check("and on at least one release the growth is visible at published precision",
      grew > 0,
      "if sigma(u) never moved a printed digit anywhere, check it is in the "
      "arithmetic at all")

# A propagated bound is the square root of a sum of squares: its exact value
# has no last digit, so the number of decimals published is a decision. The
# only defensible one is the precision of the inputs — anything finer claims
# accuracy the source papers never printed.
def _dp(x: float) -> int:
    s = repr(float(x))
    return len(s.split(".")[1]) if "." in s and "e" not in s else 0


for r in measured:
    for level in ("s1", "s3"):
        pub_lo, our_lo = r[f"{level}_lo_as_published"], r[f"{level}_lo_our_convention"]
        if pub_lo is None or our_lo is None or r["interval_method"] != "propagated":
            continue
        # The offset dm2/2 sets a floor: rounding below it would hide the
        # conversion. Two extra places cover it on every release here.
        want = max(_dp(pub_lo), _dp(r[f"{level}_hi_as_published"])) + 3
        got = max(_dp(our_lo), _dp(r[f"{level}_hi_our_convention"]))
        check(f"{r['group']} {r['year']} {r['ordering']} {level}: the propagated "
              f"bound is not printed finer than its source",
              got <= want, f"source {want} decimals, converted {got}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
n_limits = sum(1 for r in rows if r["kind"] == "limit")
print(f"all {checks} checks pass — {len(rows)} rows ({n_limits} limits), "
      "exported and traced back to history.yaml in both directions")
