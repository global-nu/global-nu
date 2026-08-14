#!/usr/bin/env python3
"""Export the parameter-history register as citable data.

    ./.venv/bin/python3 tools/make_history_data.py

Writes data-exports/history.json and data-exports/history.csv. build.py
already copies everything under data-exports/ into site/data/ (the same step
tools/make_chi2_data.py uses for chi2.json) — see DATA_EXPORTS in build.py —
so nothing else needs to change for these two files to become
https://global-nu.org/data/history.json and .../data/history.csv.

Every row carries the value twice, under names that cannot be confused:

    value_as_published    exactly what the paper printed, in the paper's own
                           convention and normalisation
    value_our_convention   the same quantity converted to this site's
                           convention by tools.make_history.to_our_Dm2()

Only "Dm2" (Delta m^2 = m3^2 - (m1^2 + m2^2)/2, our convention) is ever
converted, because it is the only quantity the three groups report
differently: NuFit prints Dm2_3l (Dm2_31 for normal ordering, Dm2_32 for
inverted) and Valencia prints |Dm2_31| for both orderings; both are stored in
history.yaml under those names and exported here under the canonical
parameter "Dm2", converted via to_our_Dm2(). Bari already publishes in our
convention, so its own Dm2 rows carry the same number in both columns — as do
all rows of the other five parameters (dm2, sin2_th12, sin2_th13, sin2_th23,
delta_pi), which every group reports the same way. That repetition is the
correct output: a downloader gets a directly comparable column across all six
parameters without first having to know which one needed work.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import make_history                                     # noqa: E402

OUT_DIR = ROOT / "data-exports"

# The YAML keys that all record the same physical quantity — Delta m^2 —
# under whichever name the group that reported it uses.
DM2_KEYS = {"Dm2", "Dm2_3l", "abs_Dm2_31"}

FIELDS = ["group", "year", "arxiv", "journal", "table", "parameter", "ordering",
          "convention", "kind", "value_as_published", "value_our_convention",
          "unit", "level"]

NOTE = (
    "The Bari/NuFit/Valencia parameter-history register. value_as_published "
    "is exactly what the cited paper printed, in its own convention and "
    "normalisation (see the `convention` and `unit` fields of each row). "
    "value_our_convention is the same quantity in this group's convention, "
    "delta m^2 = m2^2 - m1^2 > 0 and Dm2 = m3^2 - (m1^2 + m2^2)/2: identical "
    "to value_as_published for every parameter except Dm2, where NuFit and "
    "Valencia report a different quantity (Dm2_3l, |Dm2_31|) and the "
    "conversion is performed by tools/make_history.py's to_our_Dm2(). See "
    "history-schema.html for the full field-by-field documentation."
)


def build_rows(doc: dict) -> list[dict]:
    units = {k: v["unit"] for k, v in doc["meta"]["parameters"].items()}
    releases = sorted(doc["releases"], key=lambda r: (r["year"], r["group"]))

    rows: list[dict] = []
    for rel in releases:
        for pname, by_ordering in (rel.get("values") or {}).items():
            canonical = "Dm2" if pname in DM2_KEYS else pname
            for ordering, entry in by_ordering.items():
                kind = history.kind_of(entry)
                published = (entry["best"] if kind == "measurement"
                             else entry.get("upper", entry.get("lower")))
                if pname in ("Dm2_3l", "abs_Dm2_31"):
                    # Rounded, because the conversion is a subtraction of two
                    # decimal fractions in binary floating point and leaves
                    # sixteen digits of IEEE artefact on a number the paper
                    # printed to four: 2.4355 comes out as 2.4354999999999998.
                    # A citable export must not publish that. See
                    # history.VALUE_DP for why the rounding cannot reach a
                    # digit any source actually printed. value_as_published
                    # is never rounded — it is not computed.
                    converted = history.round_value(
                        make_history.to_our_Dm2(rel, ordering, published))
                else:
                    converted = published
                rows.append({
                    "group": rel["group"],
                    "year": rel["year"],
                    "arxiv": rel["arxiv"],
                    "journal": rel["journal"],
                    "table": rel["table"],
                    "parameter": canonical,
                    "ordering": ordering,
                    "convention": rel["convention"],
                    "kind": kind,
                    "value_as_published": published,
                    "value_our_convention": converted,
                    "unit": units[canonical],
                    "level": entry.get("level") if kind == "limit" else None,
                })
    return rows


def main() -> None:
    doc = history.load()
    rows = build_rows(doc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUT_DIR / "history.json"
    json_path.write_text(
        json.dumps({"note": NOTE, "rows": rows}, separators=(",", ":")),
        encoding="utf-8")

    csv_path = OUT_DIR / "history.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["level"] = out["level"] or ""
            writer.writerow(out)

    n_limits = sum(1 for r in rows if r["kind"] == "limit")
    n_releases = len({(r["group"], r["year"]) for r in rows})
    print(f"wrote {json_path.relative_to(ROOT)} and {csv_path.relative_to(ROOT)}: "
          f"{len(rows)} rows ({n_limits} limits) across {n_releases} releases")


if __name__ == "__main__":
    main()
