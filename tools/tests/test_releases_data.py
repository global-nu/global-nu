#!/usr/bin/env python3
"""Check site-src/data/releases.yaml against the papers and the register.

    ./.venv/bin/python3 tools/tests/test_releases_data.py

releases.yaml is the one file every current or released value on the site is
generated from — the home panel, the Results tables, the downloadable CSV and
JSON. So it is checked at the source, before any page exists:

  1. every number of the 2025 release equals Table I of its PDF, row by row
     and in order (best, 1σ, 2σ, 3σ, accuracy; NO then IO);
  2. the 2026 (1,2)-sector values equal the "w/ SNO+ & JUNO 2025" row of its PDF;
  3. best fit, 1σ and 3σ agree with site-src/data/history.yaml, so the
     register and the release pages cannot drift apart;
  4. the printed accuracy equals (3σ range)/6/best fit, rounded as printed;
  5. the "current" composition names a release for each parameter, and only
     a release that actually quotes that parameter.

The PDF parsers are the ones tools/tests/test_release_numbers.py uses.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "tests"))

import test_release_numbers as trn          # noqa: E402
from tools import history                   # noqa: E402

SRC = ROOT / "site-src" / "data" / "releases.yaml"

# releases.yaml key -> row label used by the PDF parser
LABEL = {
    "dm2": "δm² / 10⁻⁵ eV²",
    "sin2_th12": "sin²θ₁₂ / 10⁻¹",
    "Dm2": "Δm² / 10⁻³ eV²",
    "sin2_th13": "sin²θ₁₃ / 10⁻²",
    "sin2_th23": "sin²θ₂₃ / 10⁻¹",
    "delta_pi": "δ/π",
}

problems: list[str] = []


def flat(entry: dict) -> list[str]:
    return [entry["best"], *entry["s1"], *entry["s2"], *entry["s3"], entry["acc"]]


def rows_of(values: dict) -> list[tuple[str, str, dict]]:
    out = []
    for p, by_ord in values.items():
        for o in ("any", "NO", "IO"):
            if o in by_ord:
                out.append((p, o, by_ord[o]))
    return out


def main() -> None:
    doc = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    rels = {r["id"]: r for r in doc["releases"]}
    checked = 0

    # 1. 2025 release against Table I of PRD 111, 093006
    pdf_rows = trn.table_numbers(trn.DEFAULT_PDF)
    r25 = rels["bari-2025"]
    for p, by_ord in r25["values"].items():
        ours = []
        for o in ("any", "NO", "IO"):
            if o in by_ord:
                ours += flat(by_ord[o])
        theirs = pdf_rows[LABEL[p]]
        checked += len(ours)
        if ours != theirs:
            problems.append(f"bari-2025 {p}: yaml {ours} != PDF {theirs}")

    # 2. 2026 update against its own Table I row
    pdf26 = trn.row_2026(trn.PDF_2026)
    r26 = rels["bari-2026-12"]
    for p in r26["updates"]:
        ours = flat(r26["values"][p]["any"])
        theirs = pdf26[LABEL[p]]
        checked += len(ours)
        if ours != theirs:
            problems.append(f"bari-2026-12 {p}: yaml {ours} != PDF {theirs}")

    # 3. agreement with the register
    reg = {(r["group"], r["arxiv"]): r for r in history.load()["releases"]}
    for rid in ("bari-2025", "bari-2026-12"):
        rel = rels[rid]
        entry = reg.get(("bari", rel["arxiv"]))
        if entry is None:
            problems.append(f"{rid}: arXiv {rel['arxiv']} not in history.yaml")
            continue
        for p, o, e in rows_of(rel["values"]):
            ro = entry["values"][p].get({"any": "any", "NO": "no", "IO": "io"}[o])
            if ro is None:
                problems.append(f"{rid} {p} {o}: not in history.yaml")
                continue
            for k in ("best", "s1", "s3"):
                mine = [float(x) for x in e[k]] if k != "best" else float(e[k])
                theirs = [float(x) for x in ro[k]] if k != "best" else float(ro[k])
                checked += 1
                if mine != theirs:
                    problems.append(f"{rid} {p} {o} {k}: {mine} vs register {theirs}")

    # 4. accuracy = (3σ range)/6/best. The papers compute it from unrounded
    # values, so recomputing from the printed ones is exact only up to the
    # rounding of the inputs: the printed figure must lie within the range
    # that rounding allows (each input ± half a unit of its last digit).
    def half_ulp(x: str) -> Decimal:
        return Decimal(5).scaleb(-len(x.split(".")[1]) - 1) if "." in x else Decimal("0.5")

    for rid, rel in rels.items():
        for p, o, e in rows_of(rel["values"]):
            (lo_s, hi_s), b_s = e["s3"], e["best"]
            lo, hi, b = Decimal(lo_s), Decimal(hi_s), Decimal(b_s)
            wmax = (hi + half_ulp(hi_s)) - (lo - half_ulp(lo_s))
            wmin = (hi - half_ulp(hi_s)) - (lo + half_ulp(lo_s))
            amax = wmax / 6 / (b - half_ulp(b_s)) * 100
            amin = wmin / 6 / (b + half_ulp(b_s)) * 100
            printed = Decimal(e["acc"])
            checked += 1
            if not (amin - half_ulp(e["acc"]) <= printed <= amax + half_ulp(e["acc"])):
                problems.append(f"{rid} {p} {o}: printed accuracy {e['acc']}% outside "
                                f"[{amin:.3f}, {amax:.3f}]% allowed by the printed range")

    # 5. current composition
    cur = doc["current"]
    for p in doc["parameters"]:
        rid = cur["from"].get(p)
        checked += 1
        if rid not in rels:
            problems.append(f"current: {p} names unknown release {rid!r}")
        elif p not in rels[rid]["values"]:
            problems.append(f"current: {p} taken from {rid}, which does not quote it")

    if problems:
        print("  ! releases.yaml disagrees with its sources:")
        for m in problems:
            print("      " + m)
        sys.exit(1)
    print(f"all {checked} checks pass — releases.yaml equals the papers and the register")


if __name__ == "__main__":
    main()
