#!/usr/bin/env python3
"""The synthesis budget is not a bet on who else is using the machine.

    ./.venv/bin/python3 tools/tests/test_synthesis_load.py

ON 22 SEPTEMBER 2026 the daily run finished with `last_status = ok` and the
page went out carrying the narrative of 21 September. Nothing looked broken.

What had happened: the one model call of the day died at its fixed 300 s
budget, `call_claude` returned None, and the pipeline did the sensible thing
and reused the last good narrative. The cause was not the model and not the
network — the Mac was at load average 230 on 24 cores, running 44 workers of
a JUNO analysis. All of it legitimate work on a machine bought to do exactly
that. The model simply never got scheduled enough to answer in five minutes.

A 24-core machine busy with physics is a machine being used well. The
pipeline is what has to adapt, so the budget now stretches with the load.

This suite makes no network call, starts no process and touches nothing under
var/: `machine_load` is replaced and only the arithmetic is checked, plus the
wiring — a stretched budget that nothing passes to `subprocess.run` would be
seven green tests next to a timeout that still fires at 300 s.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import synthesize as S                          # noqa: E402

SRC = (ROOT / "tools" / "news" / "synthesize.py").read_text(encoding="utf-8")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        failures.append(label)
    print(("  ok   " if ok else "  FAIL ") + label
          + (f"   {detail}" if detail else ""))


_real_load = S.machine_load


def at_load(load: float, cores: int = 24) -> None:
    S.machine_load = lambda: (float(load), cores)


# ------------------------------------------------------------------- 1 ---
# An idle machine keeps the old behaviour exactly. A fix that moves the
# normal case is a fix that has to be argued for twice.
at_load(3.0)
check("an idle machine still gets exactly its 300 s", S.load_aware(300) == 300,
      f"{S.load_aware(300)}s")
at_load(24.0)
check("one runnable per core is still 'idle' — the boundary is there",
      S.load_aware(300) == 300, f"{S.load_aware(300)}s")

# ------------------------------------------------------------------- 2 ---
# Under the load of 22 September the budget actually grows.
at_load(230.0)
check("at load 230 on 24 cores the call is no longer killed at 300 s",
      S.load_aware(300) > 300, f"{S.load_aware(300)}s")
check("but never past the cap", S.load_aware(300) <= S.TIMEOUT_MAX,
      f"{S.load_aware(300)}s of {S.TIMEOUT_MAX}s")
at_load(100000.0)
check("an absurd load does not stretch it further either",
      S.load_aware(300) <= S.TIMEOUT_MAX, f"{S.load_aware(300)}s")

# The cap has to stay well inside a daily run: the watchdog is at 12:30 and
# the run starts at 07:45.
check("the cap is a fraction of the day, not an open-ended wait",
      S.TIMEOUT_MAX <= 30 * 60, f"{S.TIMEOUT_MAX // 60} min")

# ------------------------------------------------------------------- 3 ---
# Degradation is silent by design — reusing yesterday's narrative is correct
# behaviour — so the log is the only place it can be noticed. The load has to
# be in it, and so has the consequence.
check("the timeout message says the page will carry the last good narrative",
      "last good narrative" in SRC)
check("and both messages carry the load and the core count",
      SRC.count("load %.1f on %d cores") >= 2,
      f"{SRC.count('load %.1f on %d cores')} occurrences")
check("the load is logged on the normal call too, not only on failure",
      "ds budget, " in SRC and "load %.1f on %d cores" in SRC)

# ------------------------------------------------------------------- 4 ---
# THE WIRING. A budget nobody passes to subprocess.run is decoration.
check("call_claude computes a load-aware budget", "load_aware(" in SRC)
check("and hands that budget to subprocess.run, not the raw config value",
      "timeout=budget," in SRC)
check("no raw 300 is left as the effective timeout",
      'timeout=int(conf.get("timeout", 300))' not in SRC)

S.machine_load = _real_load

# ---------------------------------------------------------------------------
print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("all checks pass")
