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

    _check_quantified_scale()


def _check_quantified_scale() -> None:
    """The page says how big the conversion is. Those numbers must be computed.

    Antonio asked, on 2026-08-16, that the effect of the conversion on the
    *errors* be stated wherever the conversion is. The honest way to state it
    is with numbers — the offset is δm²/2, which on the most recent Bari
    release is a sizeable fraction of Δm² while the uncertainty it adds is
    almost nothing — and the moment those numbers are typed into the prose
    they begin to rot: the next global fit changes both. So the page computes
    them from the register, and this checks that what it printed is what the
    register currently says.
    """
    import math
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import make_history                                   # noqa: PLC0415

    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    got = make_history.conversion_scale(doc)

    rel = [r for r in doc["releases"]
           if r["group"] == "bari" and "Dm2" in (r.get("values") or {})][-1]
    dm2 = rel["values"]["dm2"]["any"]
    Dm2 = rel["values"]["Dm2"]["no"]
    off = dm2["best"] / 2 / 100.0                       # 1e-5 → 1e-3 eV²
    sig_dm2 = (dm2["s1"][1] - dm2["s1"][0]) / 2 / 2 / 100.0
    sig_Dm2 = (Dm2["s1"][1] - Dm2["s1"][0]) / 2

    want_sigma = off / sig_Dm2
    want_infl = 100.0 * (math.hypot(sig_Dm2, sig_dm2) / sig_Dm2 - 1.0)

    bad = []
    if got["year"] != rel["year"]:
        bad.append(f"release: page {got['year']}, register {rel['year']}")
    if abs(got["offset_sigma"] - want_sigma) > 0.05:
        bad.append(f"offset in sigma: page {got['offset_sigma']:.2f}, "
                   f"recomputed {want_sigma:.2f}")
    if abs(got["error_inflation_pct"] - want_infl) > 0.005:
        bad.append(f"error inflation: page {got['error_inflation_pct']:.3f}%, "
                   f"recomputed {want_infl:.3f}%")

    if bad:
        print("\n  ! the quantified conversion scale does not match the register:")
        for b in bad:
            print("      " + b)
        sys.exit(1)
    print(f"  and the quantified scale matches the register: the offset is "
          f"{got['offset_sigma']:.1f}σ of Δm² while the error grows "
          f"{got['error_inflation_pct']:.2f}% ({got['year']} Bari release)")


if __name__ == "__main__":
    main()
