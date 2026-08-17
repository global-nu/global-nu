#!/usr/bin/env python3
"""Both range figures share one scale, so their widths mean something.

    ./.venv/bin/python3 tools/tests/test_relative_scale.py

Each figure used to draw every row on its own axis: a row's 3σ interval was
mapped onto the full width of the row, so all the bars came out the same
length whatever the error was. |Δm²|, known to ±2.5%, and δ/π, known to
±54%, were drawn as the same picture — and the results page's caption said,
in as many words, that the widths compared precision. They did not.

The rows now share one axis, in percent of each row's own best fit, so bar
length *is* precision and the eye can compare rows without reading a number.
The checks below are what keeps that true for both figures: a single shared
scale, lengths in the right proportion, and — the failure mode a shared axis
introduces — no row ever quietly clipped at the edge without saying so.
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
LIM = make_figures.REL_LIMIT

ROW_RE = re.compile(
    r'<g class="rr" data-param="([^"]+)" data-ordering="([^"]+)">(.*?)</g>', re.S)


def line_span(chunk: str, cls: str) -> tuple[float, float] | None:
    m = re.search(rf'<line class="{cls}" x1="([-\d.]+)"[^>]*x2="([-\d.]+)"', chunk)
    return (float(m.group(1)), float(m.group(2))) if m else None


def dot_x(chunk: str) -> float | None:
    m = re.search(r'<circle class="best" cx="([-\d.]+)"', chunk)
    return float(m.group(1)) if m else None


def audit(name: str, svg: str, expect_rows: int) -> None:
    """Every structural guarantee, asked of one figure."""
    rows = ROW_RE.findall(svg)
    check(f"{name}: draws every row it should", len(rows) == expect_rows,
          f"found {len(rows)}, expected {expect_rows}")
    if not rows:
        return

    centres = [dot_x(body) for _, _, body in rows]
    check(f"{name}: every best fit sits on one shared centre — one axis, not many",
          all(c is not None for c in centres) and len(set(centres)) == 1,
          f"best-fit x positions: {sorted(set(centres))}")

    wanted, drawn = {}, {}
    for pname, ordering, body in rows:
        e = ((rel.get("values") or {}).get(pname) or {}).get(ordering)
        check(f"{name}: {pname} ({ordering}) is a row that exists in the data", bool(e))
        if not e:
            continue
        lo, hi = e["s3"]
        b = e["best"]
        key = (pname, ordering)
        wanted[key] = ((lo - b) / b * 100.0, (hi - b) / b * 100.0)
        span = line_span(body, "s3")
        if span:
            drawn[key] = span

        runs_off = wanted[key][0] < -LIM or wanted[key][1] > LIM
        marked = 'class="rr__off"' in body
        check(f"{name}: {pname} ({ordering}) "
              f"{'runs off the axis and says so' if runs_off else 'fits, and is not marked'}",
              runs_off == marked,
              f"relative 3σ {wanted[key][0]:+.1f}%/{wanted[key][1]:+.1f}%, "
              f"limit ±{LIM}%, marked={marked}")
        if runs_off:
            printed = body.replace("−", "-")
            check(f"{name}: {pname} ({ordering}) has its true extent printed, not just cut off",
                  f"{wanted[key][0]:+.0f}" in printed or f"{wanted[key][1]:+.0f}" in printed,
                  body[-400:])
        check(f"{name}: {pname} ({ordering}) still prints its best fit as a number",
              f"{b:g}" in body, body[-300:])
        check(f"{name}: {pname} ({ordering}) keeps the absolute range in its hover text",
              f"{lo:g}" in body and f"{hi:g}" in body, body[:400])

    # The check that fails if a per-row scale is ever reintroduced: under one,
    # every bar is the same length and this ratio collapses to 1.
    inside = [k for k in wanted
              if max(abs(v) for v in wanted[k]) < LIM * 0.98 and k in drawn]
    check(f"{name}: at least two rows fit inside the axis, to compare", len(inside) >= 2,
          f"rows inside: {inside}")
    if len(inside) >= 2:
        by_width = sorted(inside, key=lambda k: wanted[k][1] - wanted[k][0])
        a, b_ = by_width[0], by_width[-1]
        want_ratio = (wanted[b_][1] - wanted[b_][0]) / (wanted[a][1] - wanted[a][0])
        got_ratio = (drawn[b_][1] - drawn[b_][0]) / (drawn[a][1] - drawn[a][0])
        check(f"{name}: a row twice as uncertain is drawn twice as wide",
              abs(want_ratio - got_ratio) < 0.02,
              f"{a} vs {b_}: wanted {want_ratio:.3f}, drawn {got_ratio:.3f}")
        check(f"{name}: the most precise row is the shortest drawn",
              min(drawn, key=lambda k: drawn[k][1] - drawn[k][0])
              == min(wanted, key=lambda k: wanted[k][1] - wanted[k][0]),
              f"shortest drawn {min(drawn, key=lambda k: drawn[k][1] - drawn[k][0])}, "
              f"most precise {min(wanted, key=lambda k: wanted[k][1] - wanted[k][0])}")

    check(f"{name}: the axis is labelled in percent", svg.count("%") >= 3)
    check(f"{name}: the zero line is drawn, every row being centred on its best fit",
          'class="rr__zero"' in svg)


# The hero: normal ordering (or the value quoted for both), one row each.
hero_rows = sum(1 for p in make_figures.PARAMS
                if (e := make_figures.entry(rel, p)) and e.get("s3"))
audit("hero", make_figures.hero_ranges_svg(meta, bari), hero_rows)

print()

# The results page: every ordering the release publishes.
full_rows = sum(1 for p in make_figures.PARAMS
                for o in ("no", "io", "any")
                if ((rel.get("values") or {}).get(p) or {}).get(o, {}).get("s3"))
audit("results", make_figures.ranges_svg(meta, bari), full_rows)

# One row clipping is what exercises the off-scale path at all; if a future
# release brings every parameter inside the axis, that path stops being
# tested and this says so rather than passing quietly.
print()
check("at least one row in the register runs off the axis, exercising the marking",
      any(max(abs((v - e["best"]) / e["best"] * 100.0) for v in e["s3"]) > LIM
          for p in make_figures.PARAMS
          for o in ("no", "io", "any")
          if (e := ((rel.get("values") or {}).get(p) or {}).get(o)) and e.get("s3")),
      "no row exceeds the limit — the off-scale drawing is untested by real data")

print(f"\n{checks - len(problems)}/{checks} checks passed")
if problems:
    print("failed: " + ", ".join(problems))
    raise SystemExit(1)
