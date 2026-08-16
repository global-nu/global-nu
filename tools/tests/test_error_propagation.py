#!/usr/bin/env python3
"""Converting Δm² between conventions propagates the error. It does not shift it.

    ./.venv/bin/python3 tools/tests/test_error_propagation.py

Δm² = X ∓ u, with X the splitting the other group reports and u = δm²/2. Both
are measured, so both carry an uncertainty, and the interval on Δm² is

    σ²(Δm²) = σ²(X) + σ²(u) ∓ 2ρ·σ(X)·σ(u)

The site used to translate the published interval rigidly — keeping σ(X) and
dropping σ(u) entirely. That is not a propagation, it is an assumption that
δm² is known exactly, and it is wrong: on the 2025 release σ(u) is 4% of σ(X),
so the width was understated. The correlation term is a separate matter: ρ is
not published, so it is omitted and the omission is declared, which understates
or overstates the error by up to about 4% either way.

Each side of an asymmetric interval propagates on its own. Squeezing an
asymmetric range into one σ first would lose the asymmetry the paper reported.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import make_history                                       # noqa: E402

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


# A symmetric published interval, and an offset with its own error.
X, LO, HI = 2.5, 2.45, 2.55          # σ(X) = 0.05 either side
U, SIG_U = 0.04, 0.03                # a deliberately large σ(u), to be visible

lo, hi = make_history.propagate_interval(X, (LO, HI), -1, U, SIG_U)

check("the centre moves by exactly the offset",
      abs((lo + hi) / 2 - (X - U)) < 1e-12, f"{(lo + hi) / 2} vs {X - U}")

want = math.hypot(0.05, SIG_U)
check("each half-width grows in quadrature with σ(u)",
      abs((hi - lo) / 2 - want) < 1e-12, f"{(hi - lo) / 2} vs {want}")

check("the interval is WIDER than the published one, never equal",
      (hi - lo) > (HI - LO) + 1e-12,
      "a rigid translation would leave the width untouched — that is the bug")

# σ(u) = 0 is the only case in which a translation is right, and it must then
# reproduce it exactly: a good propagation contains the old behaviour as a
# limit rather than contradicting it.
lo0, hi0 = make_history.propagate_interval(X, (LO, HI), -1, U, 0.0)
check("with σ(u) = 0 it reduces to the rigid shift",
      abs(lo0 - (LO - U)) < 1e-12 and abs(hi0 - (HI - U)) < 1e-12)

# Adding the offset instead of subtracting it.
lop, hip = make_history.propagate_interval(X, (LO, HI), +1, U, SIG_U)
check("the sign of the offset is honoured",
      abs((lop + hip) / 2 - (X + U)) < 1e-12)
check("and the width does not depend on that sign when ρ is unknown",
      abs((hip - lop) - (hi - lo)) < 1e-12)

# Asymmetry must survive: propagate each side, do not average them first.
loa, hia = make_history.propagate_interval(2.5, (2.40, 2.55), -1, U, SIG_U)
centre = 2.5 - U
check("an asymmetric interval stays asymmetric",
      abs((centre - loa) - (hia - centre)) > 1e-6,
      "averaging the two sides would throw away what the paper reported")
check("its lower side propagates from the lower half-width",
      abs((centre - loa) - math.hypot(0.10, SIG_U)) < 1e-12)
check("its upper side propagates from the upper half-width",
      abs((hia - centre) - math.hypot(0.05, SIG_U)) < 1e-12)

# When ρ IS known the cross term enters, with the sign of the conversion.
lor, hir = make_history.propagate_interval(X, (LO, HI), -1, U, SIG_U, rho=1.0)
want_rho = math.sqrt(0.05**2 + SIG_U**2 - 2 * 1.0 * 0.05 * SIG_U)
check("a known ρ enters with the sign of the conversion",
      abs((hir - lor) / 2 - want_rho) < 1e-12, f"{(hir - lor) / 2} vs {want_rho}")
check("and a positive ρ narrows the interval where the offset is subtracted",
      (hir - lor) < (hi - lo))

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the conversion propagates the error, it does "
      "not translate it")
