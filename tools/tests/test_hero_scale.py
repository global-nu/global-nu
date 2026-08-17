#!/usr/bin/env python3
"""The hero figure's six rows share one scale, so their widths mean something.

    ./.venv/bin/python3 tools/tests/test_hero_scale.py

The figure used to draw each row on its own axis: every 3σ interval was
mapped onto the full width of its row, so all six bars came out the same
length whatever the error was. The drawing carried no information about
precision at all — |Δm²|, known to ±2.5%, and δ/π, known to ±54%, were the
same picture.

The rows now share one axis, in percent of each row's own best fit, so bar
length *is* precision and the eye can compare rows without reading a number.
The checks below are what keeps that true: a single shared scale, lengths in
the right proportion, and — the failure mode a shared axis introduces — no
row ever quietly clipped at the edge without saying so.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import make_figures                                     # noqa: E402

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


meta, bari = make_figures.load()
rel = next(r for r in bari if r.get("current"))
svg = make_figures.hero_ranges_svg(meta, bari)

ROW_RE = re.compile(r'<g class="rr"[^>]*data-param="([^"]+)"[^>]*>(.*?)</g>', re.S)
rows = ROW_RE.findall(svg)
check("the figure draws one row per parameter", len(rows) == 6, f"found {len(rows)}")


def attr(chunk: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', chunk)
    return m.group(1) if m else None


def line_span(chunk: str, cls: str) -> tuple[float, float] | None:
    m = re.search(rf'<line class="{cls}" x1="([-\d.]+)"[^>]*x2="([-\d.]+)"', chunk)
    return (float(m.group(1)), float(m.group(2))) if m else None


def dot_x(chunk: str) -> float | None:
    m = re.search(r'<circle class="best" cx="([-\d.]+)"', chunk)
    return float(m.group(1)) if m else None


# --- one scale, not six ----------------------------------------------------

centres = [dot_x(body) for _, body in rows]
check("every best fit sits on one shared centre line — one axis, not six",
      all(c is not None for c in centres) and len(set(centres)) == 1,
      f"best-fit x positions: {centres}")

# --- and the widths are in proportion to the errors ------------------------

wanted, drawn = {}, {}
for pname, body in rows:
    e = make_figures.entry(rel, pname)
    lo, hi = e["s3"]
    b = e["best"]
    wanted[pname] = ((lo - b) / b * 100.0, (hi - b) / b * 100.0)
    span = line_span(body, "s3")
    if span:
        drawn[pname] = span

# Two rows neither of which is clipped: their drawn 3σ lengths must stand in
# the same ratio as their relative widths. This is the check that fails if a
# future edit reintroduces a per-row scale — under which the ratio is 1.
inside = [p for p in wanted
          if max(abs(v) for v in wanted[p]) < make_figures.HERO_REL_LIMIT * 0.98
          and p in drawn]
check("at least two rows fit inside the axis, to compare against each other",
      len(inside) >= 2, f"rows inside the axis: {inside}")
if len(inside) >= 2:
    a, b_ = sorted(inside, key=lambda p: wanted[p][1] - wanted[p][0])[:2]
    want_ratio = ((wanted[b_][1] - wanted[b_][0]) / (wanted[a][1] - wanted[a][0]))
    got_ratio = ((drawn[b_][1] - drawn[b_][0]) / (drawn[a][1] - drawn[a][0]))
    check("a row twice as uncertain is drawn twice as wide",
          abs(want_ratio - got_ratio) < 0.02,
          f"{a} vs {b_}: wanted ratio {want_ratio:.3f}, drawn {got_ratio:.3f}")

check("the most precise parameter is drawn the shortest",
      min(drawn, key=lambda p: drawn[p][1] - drawn[p][0])
      == min(wanted, key=lambda p: wanted[p][1] - wanted[p][0]),
      f"shortest drawn: {min(drawn, key=lambda p: drawn[p][1] - drawn[p][0])}, "
      f"most precise: {min(wanted, key=lambda p: wanted[p][1] - wanted[p][0])}")

# --- nothing is clipped in silence -----------------------------------------

LIM = make_figures.HERO_REL_LIMIT
for pname, body in rows:
    lo_pct, hi_pct = wanted[pname]
    runs_off = lo_pct < -LIM or hi_pct > LIM
    marked = 'class="rr__off"' in body
    check(f"{pname}: {'runs off the axis and says so' if runs_off else 'fits, and is not marked'}",
          runs_off == marked,
          f"relative 3σ {lo_pct:+.1f}%/{hi_pct:+.1f}%, limit ±{LIM}%, marked={marked}")
    if runs_off:
        check(f"{pname}: its true extent is printed, not just cut off",
              f"{lo_pct:+.0f}" in body.replace("−", "-") or
              f"{hi_pct:+.0f}" in body.replace("−", "-"),
              body[-400:])

check("at least one row genuinely runs off the axis, so the marking is exercised",
      any(max(abs(v) for v in wanted[p]) > LIM for p in wanted),
      "no row exceeds the limit — the off-scale path is untested by real data")

# --- the axis is readable --------------------------------------------------

check("the axis is labelled in percent, so the width can be read as a number",
      svg.count("%") >= 3, "expected tick labels along the axis")
check("the zero line is drawn, since every row is centred on its own best fit",
      'class="rr__zero"' in svg)

# --- and the numbers themselves are still there ----------------------------

for pname, body in rows:
    e = make_figures.entry(rel, pname)
    check(f"{pname}: its best fit is still printed as a number",
          f"{e['best']:g}" in body, body[-300:])

check("the hover text keeps the absolute range, not only the percentage",
      all(f"{make_figures.entry(rel, p)['s3'][0]:g}" in body for p, body in rows),
      "a <title> that dropped the absolute numbers")

print(f"\n{checks - len(problems)}/{checks} checks passed")
if problems:
    print("failed: " + ", ".join(problems))
    raise SystemExit(1)
