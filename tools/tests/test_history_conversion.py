#!/usr/bin/env python3
"""Check the convention conversion used on the comparison panels.

The other groups do not report our Δm². Converting their number is one
subtraction — and getting its sign wrong would put another group's analysis on
our page under our label, which is the single worst failure this site can have.
So the rule is not trusted to a comment: it is recomputed here from the
identity, independently of the implementation, and the two must agree.

    ./.venv/bin/python3 tools/tests/test_history_conversion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from make_history import our_Dm2                        # noqa: E402

DATA = ROOT / "site-src" / "data" / "history.yaml"


def expected(rel: dict, ordering: str) -> float | None:
    """Δm² = Δm²₃₁ − δm²/2, worked out from scratch for each report style.

    Splittings are in 1e-3 eV², δm² in 1e-5 eV², so δm²/2 is dm2/200 here.
    """
    v = rel.get("values") or {}
    kind = rel.get("reported_splitting")
    if kind not in ("Dm2_3l", "abs_Dm2_31"):
        # Nothing to convert — e.g. hep-ph/0009350, which reports no Dm2 of
        # any kind (see that release's own "note" field). dm2 itself may be
        # absent too in that case, so it must not be looked up below.
        return None
    dm2_half = v["dm2"]["any"]["best"] / 200.0

    if kind == "Dm2_3l":
        # Dm2_31 (>0) for NO; Dm2_32 (<0) for IO, and Dm2_31 = Dm2_32 + dm2.
        # Some predecessor releases (e.g. hep-ph/0405172) fit only NO, so the
        # requested ordering may simply be absent — that is not a conversion
        # error, just nothing to compare for this release.
        entry = v.get("Dm2_3l", {}).get(ordering)
        if entry is None:
            return None
        signed = (entry["best"] - dm2_half) if ordering == "no" else (entry["best"] + dm2_half)
        return abs(signed)
    if kind == "abs_Dm2_31":
        # |Dm2_31| for both orderings: signed value is -|Dm2_31| in IO.
        entry = v.get("abs_Dm2_31", {}).get(ordering)
        if entry is None:
            return None
        return (entry["best"] - dm2_half) if ordering == "no" else (entry["best"] + dm2_half)
    return None


def main() -> None:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    bad, checked = [], 0
    for rel in doc["releases"]:
        if rel["group"] == "bari":
            # Nothing to convert: verify the code says so rather than inventing.
            for ordering in ("no", "io"):
                got = our_Dm2(rel, ordering)
                published = ((rel.get("values") or {}).get("Dm2") or {}).get(ordering)
                if got is not published:
                    bad.append(f"{rel['arxiv']} {ordering}: Bari values must be passed through unchanged")
            continue
        for ordering in ("no", "io"):
            want = expected(rel, ordering)
            if want is None:
                continue
            got = our_Dm2(rel, ordering)
            checked += 1
            if got is None or abs(got["best"] - want) > 1e-9:
                bad.append(f"{rel['group']} {rel['year']} {ordering}: "
                           f"code {got and got['best']!r} vs identity {want!r}")
            else:
                print(f"  ok   {rel['group']:<9} {rel['year']} {ordering.upper()}  "
                      f"{rel['reported_splitting']} → Δm² = {want:.4f} (1e-3 eV²)")

    # A converted inverted-ordering value must not come out on the wrong side
    # of the normal-ordering one for the same release: |Δm²|(IO) < |Δm²|(NO)
    # in every published global fit, and a sign slip would flip that.
    for rel in doc["releases"]:
        if rel["group"] == "bari":
            continue
        no, io = our_Dm2(rel, "no"), our_Dm2(rel, "io")
        if no and io and not (io["best"] < no["best"]):
            bad.append(f"{rel['group']} {rel['year']}: |Δm²| IO {io['best']:.4f} "
                       f"is not below NO {no['best']:.4f} — check the sign of the shift")

    if bad:
        print("\n  ! conversion problems:")
        for b in bad:
            print("      " + b)
        sys.exit(1)
    print(f"\nall {checked} conversions agree with the identity, and IO stays below NO")


if __name__ == "__main__":
    main()
