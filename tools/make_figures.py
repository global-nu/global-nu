#!/usr/bin/env python3
"""Build the SVG figures the pages include, from site-src/data/history.yaml.

    ./.venv/bin/python3 tools/make_figures.py    ->  site-src/data/figures/*.svg

Pages pull these in with `<!--include:name-->`; build.py substitutes the file
contents. Nothing is drawn from a number typed into this file: every value
comes from history.yaml, which is itself checked against the published tables
by tools/tests/test_history_numbers.py.

Colours are CSS variables, never literals, so the figures follow the theme.
Marks are thin, axes recessive, and each point carries an SVG <title> — the
hover layer a static page can offer with no JavaScript.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "history.yaml"
OUT = ROOT / "site-src" / "data" / "figures"

PARAMS = ["dm2", "Dm2", "sin2_th12", "sin2_th13", "sin2_th23", "delta_pi"]


def load() -> tuple[dict, list[dict]]:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    bari = sorted((r for r in doc["releases"] if r["group"] == "bari"),
                  key=lambda r: r["year"])
    return doc["meta"]["parameters"], bari


def entry(rel: dict, pname: str) -> dict | None:
    """The normal-ordering entry, or the one quoted for both orderings."""
    byo = (rel.get("values") or {}).get(pname) or {}
    return byo.get("no") or byo.get("any")


def accuracy(e: dict) -> float | None:
    """The papers' own definition: 1/6 of the 3σ range over the best fit, in
    percent. Derived here rather than transcribed, because it is arithmetic on
    two numbers that are already verified."""
    if not e.get("s3") or not e.get("best"):
        return None
    lo, hi = e["s3"]
    return (hi - lo) / 6.0 / abs(e["best"]) * 100.0


# --------------------------------------------------------------------------- #
# 1. precision over time
# --------------------------------------------------------------------------- #
def precision_svg(meta: dict, bari: list[dict]) -> str:
    W, H = 760, 330
    L, R, T, B = 52, 128, 18, 38
    series = []
    for i, pname in enumerate(PARAMS):
        pts = []
        for rel in bari:
            e = entry(rel, pname)
            a = accuracy(e) if e else None
            if a is not None:
                pts.append((rel["year"], a))
        if len(pts) > 1:
            series.append((pname, meta[pname]["label"], pts, f"var(--dec-{i % 5 + 1})"))

    years = sorted({y for _, _, pts, _ in series for y, _ in pts})
    x0, x1 = min(years), max(years)
    # A log scale: the whole point is that these span 0.8% to 20%.
    import math
    vals = [v for _, _, pts, _ in series for _, v in pts]
    lo, hi = min(vals) * 0.75, max(vals) * 1.3

    def sx(y: float) -> float:
        return L + (y - x0) / (x1 - x0) * (W - L - R)

    def sy(v: float) -> float:
        f = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        return H - B - f * (H - T - B)

    out = [f'<line x1="{L}" y1="{H-B}" x2="{W-R}" y2="{H-B}" stroke="currentColor" '
           'stroke-width="1" opacity=".35"/>',
           f'<line x1="{L}" y1="{T}" x2="{L}" y2="{H-B}" stroke="currentColor" '
           'stroke-width="1" opacity=".35"/>']
    for gv in (1, 2, 5, 10, 20):
        if lo <= gv <= hi:
            yy = sy(gv)
            out.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" '
                       'stroke="currentColor" stroke-width="1" stroke-dasharray="3 5" '
                       'opacity=".18"/>')
            out.append(f'<text x="{L-8}" y="{yy+3.5:.1f}" text-anchor="end" font-size="11" '
                       f'fill="currentColor" opacity=".62">{gv}%</text>')
    for y in years:
        out.append(f'<text x="{sx(y):.1f}" y="{H-B+18}" text-anchor="middle" font-size="11" '
                   f'fill="currentColor" opacity=".62">{y}</text>')

    ends = []
    for pname, label, pts, colour in series:
        d = " ".join(f'{"M" if i == 0 else "L"}{sx(y):.1f} {sy(v):.1f}'
                     for i, (y, v) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2.4" '
                   'stroke-linejoin="round" stroke-linecap="round" opacity=".9"/>')
        for y, v in pts:
            out.append(f'<circle cx="{sx(y):.1f}" cy="{sy(v):.1f}" r="3.4" fill="{colour}" '
                       f'stroke="var(--bg)" stroke-width="1.6" paint-order="stroke">'
                       f'<title>{label}, {y}: 1σ accuracy {v:.2g}%</title></circle>')
        ly, lv = pts[-1]
        ends.append([sx(ly), sy(lv), label, colour])

    # Direct labels live in a fixed column in the right margin, pushed apart
    # until none overlaps, with a leader line back to the curve's end. Placing
    # each at its own curve's end looked fine until two curves ended at the
    # same height — sin²θ₁₃ and sin²θ₁₂ printed on top of each other.
    ends.sort(key=lambda e: e[1])
    MIN_GAP = 16
    for i in range(1, len(ends)):
        if ends[i][1] - ends[i - 1][1] < MIN_GAP:
            ends[i][1] = ends[i - 1][1] + MIN_GAP
    lx = W - R + 26
    for ex, ey, label, colour in ends:
        out.append(f'<line x1="{ex + 6:.1f}" y1="{ey:.1f}" x2="{lx - 6:.1f}" y2="{ey:.1f}" '
                   f'stroke="{colour}" stroke-width="1" opacity=".45"/>')
        out.append(f'<text x="{lx:.1f}" y="{ey + 4:.1f}" font-size="12" '
                   f'font-weight="600" fill="{colour}">{label}</text>')

    body = "\n".join(out)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Formal 1σ accuracy of each '
            'oscillation parameter, by year of publication, on a logarithmic scale">\n'
            f'{body}\n</svg>')


# --------------------------------------------------------------------------- #
# 2. the current ranges, one row per parameter
# --------------------------------------------------------------------------- #
SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def unit_suffix(unit: str | None) -> str:
    """" / 10⁻⁵ eV²" for the "1e-5 eV²" of history.yaml, "" for none.

    The papers quote each parameter in a normalisation printed at the head of
    its table — 7.37 means 7.37×10⁻⁵ eV², 3.03 means 0.303 — and history.yaml
    keeps that normalisation in `unit` rather than converting. A figure that
    prints the value without it prints a number that is wrong by a factor of
    ten to a hundred thousand, which is what the home page did next to stat
    cards giving the same parameters as plain decimals.

    The written form is the stat cards' own: "δm² / 10⁻⁵ eV²". `unit: "1"` is
    a dimensionless, unnormalised value (δ/π) and gets nothing. Anything not
    of the form 1e<n> is passed through as written rather than reinterpreted.
    """
    if not unit or unit.strip() in ("", "1"):
        return ""
    head, _, rest = unit.strip().partition(" ")
    if head.startswith("1e") and head[2:].lstrip("-").isdigit():
        head = "10" + head[2:].translate(SUPERSCRIPT)
    return f" / {head} {rest}".rstrip()


def _range_row(y: float, label: str, tag: str, colour: str, e: dict,
                L: float, R: float, W: float, *, font: float = 12.5,
                value_font: float = 12, unit: str | None = None) -> list[str]:
    """One row of a ranges figure: label, 3σ line, 1σ band, best-fit point,
    and the numeric best fit — each row scaled to its own axis, because the
    widths being compared are precision, not magnitude.

    `unit` is the parameter's normalisation, written into the row label after
    the parameter name, so the number at the end of the row can be read on its
    own. Both figures pass it: the results-page one sits under Table I, whose
    header carries the normalisation, but the figure is wide, captioned and
    linked in its own right, and a rule with an exception is the kind that
    stops being followed. The label is the only place it can go — the value
    column is 48px wide in the hero — and it is the place the home page's stat
    cards already put it.

    Shared by ranges_svg (results page) and hero_ranges_svg (home page) so
    the two figures draw from one place and cannot disagree about a number
    or a scale.
    """
    lo3, hi3 = e["s3"]
    lo1, hi1 = e.get("s1") or e["s3"]
    span = hi3 - lo3
    pad = span * 0.10

    def sx(v: float) -> float:
        return L + (v - (lo3 - pad)) / (span + 2 * pad) * (W - L - R)

    return [
        f'<text x="{L-12}" y="{y+4:.0f}" text-anchor="end" font-size="{font}" '
        f'font-weight="600" fill="currentColor">{label}{unit_suffix(unit)}{tag}'
        f'</text>',
        f'<line x1="{sx(lo3):.1f}" y1="{y:.0f}" x2="{sx(hi3):.1f}" y2="{y:.0f}" '
        f'stroke="{colour}" stroke-width="3" stroke-linecap="round" opacity=".28">'
        f'<title>3σ: {lo3:g} – {hi3:g}</title></line>',
        f'<line x1="{sx(lo1):.1f}" y1="{y:.0f}" x2="{sx(hi1):.1f}" y2="{y:.0f}" '
        f'stroke="{colour}" stroke-width="7" stroke-linecap="round" opacity=".55">'
        f'<title>1σ: {lo1:g} – {hi1:g}</title></line>',
        f'<circle cx="{sx(e["best"]):.1f}" cy="{y:.0f}" r="5" fill="{colour}" '
        f'stroke="var(--surface)" stroke-width="2" paint-order="stroke">'
        f'<title>best fit {e["best"]:g}</title></circle>',
        f'<text x="{W-R+10}" y="{y+4:.0f}" font-size="{value_font}" '
        f'font-family="var(--mono)" fill="currentColor" opacity=".75">{e["best"]:g}</text>',
    ]


def ranges_svg(meta: dict, bari: list[dict]) -> str:
    rel = next(r for r in bari if r.get("current"))
    rows = []
    for pname in PARAMS:
        byo = (rel.get("values") or {}).get(pname) or {}
        for ordering in ("no", "io", "any"):
            if ordering in byo and byo[ordering].get("s3"):
                rows.append((pname, ordering, byo[ordering]))
    W = 760
    ROW, TOP = 40, 26
    H = TOP + ROW * len(rows) + 16
    # L holds the longest label — "|Δm²| / 10⁻³ eV² (NO)", 130px in Inter at
    # 12.5px — plus its 12px gap and room for a wider fallback face.
    L, R = 164, 74

    out = []
    for i, (pname, ordering, e) in enumerate(rows):
        y = TOP + i * ROW + ROW / 2
        label = meta[pname]["label"]
        colour = {"no": "var(--no)", "io": "var(--io)"}.get(ordering, "var(--accent)")
        tag = {"no": " (NO)", "io": " (IO)"}.get(ordering, "")
        out.extend(_range_row(y, label, tag, colour, e, L, R, W,
                               unit=meta[pname].get("unit")))

    body = "\n".join(out)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Best fit with 1σ and 3σ '
            'ranges for each oscillation parameter of the current release, each row '
            'labelled with the parameter and the units its values are given in">\n'
            f'{body}\n</svg>')


# --------------------------------------------------------------------------- #
# 2b. compact ranges for the home-page hero, normal ordering only
# --------------------------------------------------------------------------- #
def hero_ranges_svg(meta: dict, bari: list[dict]) -> str:
    rel = next(r for r in bari if r.get("current"))
    rows = [(pname, e) for pname in PARAMS if (e := entry(rel, pname)) and e.get("s3")]
    W = 520
    ROW, TOP = 34, 20
    H = TOP + ROW * len(rows) + 26
    # L holds the longest label — "|Δm²| / 10⁻³ eV²", 87px in Inter at 11.5px —
    # plus its 12px gap and room for a wider fallback face.
    L, R = 124, 58

    out = []
    for i, (pname, e) in enumerate(rows):
        y = TOP + i * ROW + ROW / 2
        label = meta[pname]["label"]
        out.extend(_range_row(y, label, "", "var(--no)", e, L, R, W,
                               font=11.5, value_font=11,
                               unit=meta[pname].get("unit")))
    out.append(f'<text x="{W-R}" y="{H-6:.0f}" text-anchor="end" font-size="9.5" '
               f'font-family="var(--mono)" fill="currentColor" opacity=".5">'
               f'arXiv:{rel["arxiv"]}</text>')

    body = "\n".join(out)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Best fit with 1σ and 3σ '
            'ranges for each oscillation parameter, normal ordering, current release, '
            'each row labelled with the parameter and the units its values are given '
            'in">\n'
            f'{body}\n</svg>')


# --------------------------------------------------------------------------- #
# 3. sparklines for the home page stat cards
# --------------------------------------------------------------------------- #
def spark_svg(pname: str, bari: list[dict]) -> str | None:
    pts = []
    for rel in bari:
        e = entry(rel, pname)
        if e and e.get("best") is not None:
            pts.append((rel["year"], e["best"], e.get("s3")))
    if len(pts) < 3:
        return None
    W, H, P = 240, 44, 5
    vals = [v for _, v, _ in pts] + [b for _, _, r in pts if r for b in r]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    xs = [P + i / (len(pts) - 1) * (W - 2 * P) for i in range(len(pts))]

    def sy(v: float) -> float:
        return H - P - (v - lo) / (hi - lo) * (H - 2 * P)

    band_top = " ".join(f"{x:.1f},{sy(r[1]):.1f}" if r else f"{x:.1f},{sy(v):.1f}"
                        for x, (_, v, r) in zip(xs, pts))
    band_bot = " ".join(f"{x:.1f},{sy(r[0]):.1f}" if r else f"{x:.1f},{sy(v):.1f}"
                        for x, (_, v, r) in reversed(list(zip(xs, pts))))
    line = " ".join(f'{"M" if i == 0 else "L"}{x:.1f} {sy(v):.1f}'
                    for i, (x, (_, v, _)) in enumerate(zip(xs, pts)))
    first, last = pts[0][0], pts[-1][0]
    return (f'<svg class="stat__spark" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Best fit from {first} to {last}, with its 3σ band">'
            f'<polygon class="band" points="{band_top} {band_bot}"/>'
            f'<path class="line" d="{line}"/>'
            f'<circle class="dot" cx="{xs[-1]:.1f}" cy="{sy(pts[-1][1]):.1f}" r="3"/>'
            f'</svg>'
            f'<span class="stat__sparklabel">{first} → {last}</span>')


def main() -> None:
    meta, bari = load()
    OUT.mkdir(parents=True, exist_ok=True)
    written = []

    (OUT / "precision.svg").write_text(precision_svg(meta, bari), encoding="utf-8")
    written.append("precision")
    (OUT / "ranges.svg").write_text(ranges_svg(meta, bari), encoding="utf-8")
    written.append("ranges")
    (OUT / "ranges-hero.svg").write_text(hero_ranges_svg(meta, bari), encoding="utf-8")
    written.append("ranges-hero")
    for pname in PARAMS:
        svg = spark_svg(pname, bari)
        if svg:
            (OUT / f"spark-{pname}.svg").write_text(svg, encoding="utf-8")
            written.append(f"spark-{pname}")

    print(f"figures: {len(written)} written to {OUT.relative_to(ROOT)}")
    for name in written:
        print("   ", name)


if __name__ == "__main__":
    main()
