#!/usr/bin/env python3
"""Generate the parameter-history page from site-src/data/history.yaml.

The page is never written by hand: it is a rendering of the data file, so a
number can only reach the site by first being transcribed into history.yaml
and verified there by tools/tests/test_history_numbers.py.

    ./.venv/bin/python3 tools/make_history.py

Writes site-src/content/history.md.

Chart conventions (see the dataviz method):
  * one axis, small multiples — one panel per parameter, never a dual scale
  * the two mass orderings are a categorical pair, encoded by colour AND by
    marker shape, so identity never rests on colour alone
  * marks are thin, markers ≥ 8px, grid and axes recessive, labels in text
    tokens rather than in the series colour
  * every point carries an SVG <title>, which is the hover layer a static
    page can offer without shipping a line of JavaScript
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "history.yaml"
OUT = ROOT / "site-src" / "content" / "history.md"

# Panel geometry, in SVG user units.
W, H = 520, 250
PAD_L, PAD_R, PAD_T, PAD_B = 54, 14, 16, 34

ORDERINGS = [
    ("no", "Normal ordering", "var(--no)"),
    ("io", "Inverted ordering", "var(--io)"),
    ("any", "Both orderings", "var(--text-soft)"),
]


def nice_bounds(lo: float, hi: float) -> tuple[float, float]:
    """Pad a data range so marks never touch the frame."""
    if hi == lo:
        return lo - 1, hi + 1
    pad = (hi - lo) * 0.12
    return lo - pad, hi + pad


def marker(kind: str, x: float, y: float, colour: str, label: str) -> str:
    """Circle for NO, square for IO, diamond for “both”: shape carries the
    same information as colour, for readers who cannot use the colour."""
    ring = ' stroke="var(--bg)" stroke-width="2" paint-order="stroke"'
    t = f"<title>{label}</title>"
    if kind == "no":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.6" fill="{colour}"{ring}>{t}</circle>'
    if kind == "io":
        return (f'<rect x="{x - 4.2:.1f}" y="{y - 4.2:.1f}" width="8.4" height="8.4" rx="1.2" '
                f'fill="{colour}"{ring}>{t}</rect>')
    return (f'<path d="M{x:.1f} {y - 5.2:.1f}L{x + 5.2:.1f} {y:.1f}'
            f'L{x:.1f} {y + 5.2:.1f}L{x - 5.2:.1f} {y:.1f}Z" fill="{colour}"{ring}>{t}</path>')


def panel(pname: str, meta: dict, releases: list[dict]) -> str:
    """One small multiple: best fit and 3σ range against publication year."""
    series: dict[str, list[tuple[int, dict]]] = {k: [] for k, _, _ in ORDERINGS}
    for rel in releases:
        entry = (rel.get("values") or {}).get(pname)
        if not entry:
            continue
        for key in series:
            if key in entry:
                series[key].append((rel["year"], entry[key]))

    points = [(y, e) for s in series.values() for y, e in s]
    if not points:
        return ""

    years = sorted({y for y, _ in points})
    x0, x1 = min(years) - 0.8, max(years) + 0.8
    vals = []
    for _, e in points:
        vals.append(e["best"])
        vals += list(e.get("s3") or e.get("s1") or [])
    y0, y1 = nice_bounds(min(vals), max(vals))

    def sx(v: float) -> float:
        return PAD_L + (v - x0) / (x1 - x0) * (W - PAD_L - PAD_R)

    def sy(v: float) -> float:
        return H - PAD_B - (v - y0) / (y1 - y0) * (H - PAD_T - PAD_B)

    out: list[str] = []
    # recessive frame and horizontal guides
    out.append(f'<line x1="{PAD_L}" y1="{H - PAD_B}" x2="{W - PAD_R}" y2="{H - PAD_B}" '
               'stroke="currentColor" stroke-width="1" opacity=".35"/>')
    out.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H - PAD_B}" '
               'stroke="currentColor" stroke-width="1" opacity=".35"/>')
    for i in range(4):
        v = y0 + (y1 - y0) * i / 3
        yy = sy(v)
        out.append(f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W - PAD_R}" y2="{yy:.1f}" '
                   'stroke="currentColor" stroke-width="1" stroke-dasharray="3 5" opacity=".18"/>')
        out.append(f'<text x="{PAD_L - 8}" y="{yy + 3.5:.1f}" text-anchor="end" font-size="10.5" '
                   f'fill="currentColor" opacity=".62">{v:.3g}</text>')
    for yr in years:
        out.append(f'<text x="{sx(yr):.1f}" y="{H - PAD_B + 18}" text-anchor="middle" '
                   f'font-size="10.5" fill="currentColor" opacity=".62">{str(yr)[2:]}</text>')

    label = meta["label"]
    unit = meta["unit"]
    for kind, name, colour in ORDERINGS:
        pts = sorted(series[kind])
        if not pts:
            continue
        # 3σ range as a thin vertical rule behind the marker
        for yr, e in pts:
            rng = e.get("s3") or e.get("s1")
            if rng:
                out.append(f'<line x1="{sx(yr):.1f}" y1="{sy(rng[0]):.1f}" '
                           f'x2="{sx(yr):.1f}" y2="{sy(rng[1]):.1f}" stroke="{colour}" '
                           'stroke-width="2" stroke-linecap="round" opacity=".38"/>')
        if len(pts) > 1:
            d = " ".join(f'{"M" if i == 0 else "L"}{sx(y):.1f} {sy(e["best"]):.1f}'
                         for i, (y, e) in enumerate(pts))
            out.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                       'stroke-linejoin="round" opacity=".55"/>')
        for yr, e in pts:
            rng = e.get("s3") or e.get("s1")
            span = f', 3σ {rng[0]:g}–{rng[1]:g}' if rng else ""
            out.append(marker(kind, sx(yr), sy(e["best"]), colour,
                              f"{name}, {yr}: {label} = {e['best']:g}{span} ({unit})"))

    body = "\n".join(out)
    return f"""<figure class="figure">
<h4>{label} <span class="figure__unit">/ {unit}</span></h4>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label} best-fit values and 3σ ranges by publication year, for the two mass orderings">
{body}
</svg>
<p class="cap">Best fit with its 3σ range, by year of publication. Values and
sources in the table below.</p>
</figure>"""


def main() -> None:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))

    # YAML 1.1 reads a bare `no` as the boolean False, which silently deletes
    # the whole normal-ordering series from every panel. The keys are quoted in
    # history.yaml; this refuses to build if a future edit unquotes one.
    for rel in doc["releases"]:
        for pname, entry in (rel.get("values") or {}).items():
            bad = [k for k in entry if not isinstance(k, str)]
            if bad:
                raise SystemExit(
                    f"{DATA.name}: {rel['year']} {pname} has non-string ordering "
                    f"key(s) {bad} — quote them, e.g. \"no\": {{...}}")

    params = doc["meta"]["parameters"]
    releases = [r for r in doc["releases"] if r["group"] == "bari"]
    releases.sort(key=lambda r: r["year"])

    panels = "\n\n".join(p for p in (panel(k, v, releases) for k, v in params.items()) if p)

    rows = []
    for r in releases:
        tags = []
        if r.get("partial"):
            tags.append('<span class="tag">partial update</span>')
        if r.get("current"):
            tags.append('<span class="tag">current release</span>')
        rows.append(
            f'<tr><th scope="row">{r["year"]}</th>'
            f'<td class="ref">{r["title"]}<span class="ref__meta">{r["journal"]}</span></td>'
            f'<td><a href="https://arxiv.org/abs/{r["arxiv"]}">arXiv:{r["arxiv"]}</a></td>'
            f'<td>{r["table"]}</td><td>{" ".join(tags)}</td></tr>')
    table = "\n".join(rows)

    n_values = sum(
        1
        for r in releases
        for e in (r.get("values") or {}).values()
        for o in e.values()
        for k in ("best", "s1", "s2", "s3")
        if k in o
        for _ in (o[k] if isinstance(o[k], list) else [o[k]])
    )

    page = f"""---
title: Parameter history
url: history.html
description: >-
  How the neutrino oscillation parameters moved across the Bari global
  analyses, from the first hint of θ₁₃ to subpercent precision — every point
  traced to the table it came from.
katex: false
---

<!-- Generated by tools/make_history.py from site-src/data/history.yaml.
     Do not edit this file: edit the data and regenerate. -->

<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Parameter history</p>
    <h1>From a hint of θ₁₃ to <i class="grad">subpercent precision</i></h1>
    <p class="lede">Every published update of the Bari global analysis, plotted
    as it was published: best fit and 3σ range, for both mass orderings. No
    point is interpolated, rescaled or read off a figure.</p>
  </div>
</section>

::: section

<div class="callout">
<h4>How to read these panels</h4>
<p>Values are shown in the normalisation used in the papers, given under each
title. The vertical rule is the 3σ range; the marker is the best fit —
a circle for normal ordering, a square for inverted, a diamond where the
analysis quotes a single value for both. Hover a marker for the numbers.</p>
<p>All entries use our convention Δm² = m₃² − ½(m₁² + m₂²) and δm² = m₂² − m₁²
&gt; 0. Analyses by other groups use different conventions and are not plotted
here: adding them means converting first, and stating the conversion.</p>
</div>

<div class="legend legend--chart" style="margin-top:1.4rem">
  <span><i class="k-no"></i>Normal ordering (circle)</span>
  <span><i class="k-io"></i>Inverted ordering (square)</span>
  <span><i class="k-any"></i>Quoted for both (diamond)</span>
</div>

<div class="panels">

{panels}

</div>

:::

::: section alt

<div class="section-head">
  <h2>The releases</h2>
  <p>{len(releases)} updates · {n_values} values, each verified against its source table</p>
</div>

<div class="table-scroll">
<table class="data data--refs">
<caption>Every value on this page is transcribed from the table named here and
checked against the paper by <code>tools/tests/test_history_numbers.py</code>,
which re-reads each source on every run. Papers marked as partial updates
revise only part of the parameter set.</caption>
<thead><tr><th scope="col">Year</th><th scope="col">Paper</th><th scope="col">Preprint</th><th scope="col">Source table</th><th scope="col"></th></tr></thead>
<tbody>
{table}
</tbody>
</table>
</div>

<div class="prose" style="margin-top:2rem">
<p class="small muted">Earlier analyses of the series — the solar-sector papers
of 2002–2003 and the first full three-flavour releases of 2005 — are not yet on
this page: their tables are laid out differently and are being transcribed with
the same care. The Valencia and NuFit timelines follow, each with its own
convention stated.</p>
</div>

:::
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(releases)} releases, {n_values} values, "
          f"{len(params)} panels")


if __name__ == "__main__":
    main()
