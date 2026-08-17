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

# How far the shared axis of both range figures reaches, as a percentage of
# each row's own best fit, and where it is ticked.
#
# The figure used to scale every row to its own 3σ interval, which made all
# six bars the same length whatever the error was: the drawing said nothing
# about precision, which is the one thing a reader looks at it to learn. One
# axis in relative terms fixes that — a row twice as uncertain is twice as
# wide — at the cost of a decision about where to stop it.
#
# ±25% is chosen against the data rather than for roundness. On the current
# release the six 3σ half-widths are 2.5, 6.8, 7.2, 13.4, 15.2 and 54.2
# percent: a limit that contained δ/π would have to reach ±70%, and would
# then draw the three best-measured parameters as near-identical stubs a few
# pixels long — trading one uninformative figure for another. ±25% holds five
# of the six at a readable size and sends δ/π off the edge, which is a fair
# description of what is actually known about the CP phase. Anything that
# runs off is drawn to the boundary, marked with an arrow, and has its true
# extent printed beside it: see _rel_range_row.
#
# The results-page figure adds the inverted-ordering rows, and they change
# nothing here: their half-widths are 2.5, 7.4, 12.8 and 24.0 percent, so the
# same limit leaves exactly one row — δ/π in normal ordering — running off.
REL_LIMIT = 25.0
REL_TICKS = (-20, -10, 0, 10, 20)

# File-name stem per parameter, where the parameter key alone will not do.
# The include names on the pages are these slugs, not the keys.
SPARK_SLUG = {"Dm2": "Dm2-abs"}


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


def ranges_svg(meta: dict, bari: list[dict]) -> str:
    rel = next(r for r in bari if r.get("current"))
    rows = []
    for pname in PARAMS:
        byo = (rel.get("values") or {}).get(pname) or {}
        for ordering in ("no", "io", "any"):
            if ordering in byo and byo[ordering].get("s3"):
                rows.append((pname, ordering, byo[ordering]))
    W = 760
    # TOP leaves room above the first row for the axis tick labels, which sit
    # 18px above the top gridline: at the old 26 their baseline landed at y=8
    # and the type was cut off by the top edge of the viewBox.
    ROW, TOP = 40, 38
    H = TOP + ROW * len(rows) + 22
    # L holds the longest label — "|Δm²| / 10⁻³ eV² (NO)", 130px in Inter at
    # 12.5px — plus its 12px gap and room for a wider fallback face.
    L, R = 164, 74
    top_rule, bot_rule = TOP - 12, TOP + ROW * len(rows)

    out = _rel_axis(L, R, W, top_rule, bot_rule)
    for i, (pname, ordering, e) in enumerate(rows):
        y = TOP + i * ROW + ROW / 2
        label = meta[pname]["label"]
        colour = {"no": "var(--no)", "io": "var(--io)"}.get(ordering, "var(--accent)")
        tag = {"no": " (NO)", "io": " (IO)"}.get(ordering, "")
        out.extend(_rel_range_row(pname, ordering, label, tag,
                                  meta[pname].get("unit"), e, y, colour, L, R, W))

    out.append(f'<text x="{L}" y="{H-4:.0f}" font-size="10" fill="currentColor" '
               f'opacity=".6">width = 3σ range as a percentage of the best fit</text>')

    body = "\n".join(out)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Best fit with 1σ and 3σ '
            'ranges for each oscillation parameter of the current release, each row '
            'labelled with the parameter and the units its values are given in. All '
            'rows share one horizontal scale, measured in percent of each row\'s own '
            'best fit, so the width of a row is how well that parameter is known: the '
            'narrowest is the mass splitting |Δm²| and the widest by far is the CP '
            'phase δ in normal ordering, which runs past the edge of the axis">\n'
            f'{body}\n</svg>')


# --------------------------------------------------------------------------- #
# 2b. compact ranges for the home-page hero, normal ordering only
# --------------------------------------------------------------------------- #
def _rel_axis(L: float, R: float, W: float, top: float, bottom: float,
              *, font: float = 9.5) -> list[str]:
    """The shared axis both range figures are drawn against: gridlines every
    ten percent, a solid rule at zero, and the ticks labelled.

    The zero line is not decoration. Every row is centred on its *own* best
    fit, so the thing all the rows have in common is that one line; without it
    drawn, the figure looks like a set of bars floating at arbitrary offsets.
    """
    half = (W - R - L) / 2.0
    centre = L + half
    out = []
    for t in REL_TICKS:
        x = centre + t / REL_LIMIT * half
        zero = t == 0
        dash = "" if zero else ' stroke-dasharray="3 5"'
        out.append(f'<line class="{"rr__zero" if zero else "rr__grid"}" '
                   f'x1="{x:.1f}" y1="{top:.0f}" x2="{x:.1f}" y2="{bottom:.0f}" '
                   f'stroke="currentColor" stroke-width="1" '
                   f'opacity="{".35" if zero else ".14"}"{dash}/>')
        out.append(f'<text x="{x:.1f}" y="{top - 6:.0f}" text-anchor="middle" '
                   f'font-size="{font}" fill="currentColor" opacity=".62">'
                   f'{"best fit" if zero else f"{t:+d}%"}</text>')
    return out


def _rel_range_row(pname: str, ordering: str, label: str, tag: str,
                   unit: str | None, e: dict, y: float, colour: str,
                   L: float, R: float, W: float, *, font: float = 12.5,
                   value_font: float = 12) -> list[str]:
    """One row of a ranges figure: label, 3σ line, 1σ band, best-fit point,
    and the numeric best fit — every row on the one shared axis of _rel_axis.

    Each row is centred on its own best fit and measured outward in percent of
    it, so lengths are comparable down the column. Both figures used to give
    each row its own axis instead, mapping its 3σ interval onto the full width
    of the row; that drew every interval the same length whatever the error
    was, and the results page's caption claimed in as many words that the
    widths compared precision.

    `unit` is the parameter's normalisation, written into the row label after
    the parameter name, so the number at the end of the row can be read on its
    own. Both figures pass it: the results-page one sits under Table I, whose
    header carries the normalisation, but the figure is wide, captioned and
    linked in its own right, and a rule with an exception is the kind that
    stops being followed. The label is the only place it can go — the value
    column is 48px wide in the hero — and it is the place the home page's stat
    cards already put it.

    A row wider than the axis is drawn to the boundary and marked there with
    an arrow, with its true extent printed beside it. Clipping without saying
    so would be worse than the flaw this replaced: a bar that stops at the
    edge reads as a measurement that stops there.
    """
    lo3, hi3 = e["s3"]
    lo1, hi1 = e.get("s1") or e["s3"]
    best = e["best"]
    half = (W - R - L) / 2.0
    centre = L + half

    def pct(v: float) -> float:
        return (v - best) / best * 100.0

    def sx(v: float) -> float:
        x = centre + pct(v) / REL_LIMIT * half
        return min(max(x, L), W - R)

    lo_pct, hi_pct = pct(lo3), pct(hi3)
    off_lo, off_hi = lo_pct < -REL_LIMIT, hi_pct > REL_LIMIT

    def num(p: float) -> str:
        return f"{'−' if p < 0 else '+'}{abs(p):.0f}%"

    out = [
        f'<g class="rr" data-param="{pname}" data-ordering="{ordering}">',
        f'<text x="{L-12}" y="{y+4:.0f}" text-anchor="end" font-size="{font}" '
        f'font-weight="600" fill="currentColor">{label}{unit_suffix(unit)}{tag}</text>',
        f'<line class="s3" x1="{sx(lo3):.1f}" y1="{y:.0f}" x2="{sx(hi3):.1f}" y2="{y:.0f}" '
        f'stroke="{colour}" stroke-width="3" stroke-linecap="round" opacity=".28">'
        f'<title>3σ: {lo3:g} – {hi3:g}  ({num(lo_pct)} / {num(hi_pct)})</title></line>',
        f'<line class="s1" x1="{sx(lo1):.1f}" y1="{y:.0f}" x2="{sx(hi1):.1f}" y2="{y:.0f}" '
        f'stroke="{colour}" stroke-width="7" stroke-linecap="round" opacity=".55">'
        f'<title>1σ: {lo1:g} – {hi1:g}  ({num(pct(lo1))} / {num(pct(hi1))})</title></line>',
        f'<circle class="best" cx="{centre:.1f}" cy="{y:.0f}" r="5" fill="{colour}" '
        f'stroke="var(--surface)" stroke-width="2" paint-order="stroke">'
        f'<title>best fit {best:g}</title></circle>',
        f'<text x="{W-R+10}" y="{y+4:.0f}" font-size="{value_font}" '
        f'font-family="var(--mono)" fill="currentColor" opacity=".75">{best:g}</text>',
    ]

    # The arrow head is drawn as two strokes rather than a filled triangle so
    # it reads at the same weight as the 3σ rule it terminates.
    for side, runs_off, pctv in ((-1, off_lo, lo_pct), (1, off_hi, hi_pct)):
        if not runs_off:
            continue
        edge = L if side < 0 else W - R
        tipx = edge + side * 4
        out.append(f'<path class="rr__off" d="M{edge - side * 5:.1f} {y - 4:.0f}'
                   f'L{tipx:.1f} {y:.0f}L{edge - side * 5:.1f} {y + 4:.0f}" '
                   f'fill="none" stroke="{colour}" stroke-width="2" '
                   'stroke-linecap="round" stroke-linejoin="round"/>')
        out.append(f'<text class="rr__offpct" x="{edge - side * 11:.1f}" y="{y - 9:.0f}" '
                   f'text-anchor="{"start" if side < 0 else "end"}" font-size="9" '
                   f'font-family="var(--mono)" fill="currentColor" opacity=".7">'
                   f'{num(pctv)}</text>')

    out.append("</g>")
    return out


def hero_ranges_svg(meta: dict, bari: list[dict]) -> str:
    rel = next(r for r in bari if r.get("current"))
    rows = [(pname, e) for pname in PARAMS if (e := entry(rel, pname)) and e.get("s3")]
    W = 520
    ROW, TOP = 34, 36
    H = TOP + ROW * len(rows) + 26
    # L holds the longest label — "|Δm²| / 10⁻³ eV²", 87px in Inter at 11.5px —
    # plus its 12px gap and room for a wider fallback face.
    L, R = 124, 58
    top_rule, bot_rule = TOP - 12, TOP + ROW * len(rows)

    out = _rel_axis(L, R, W, top_rule, bot_rule)
    for i, (pname, e) in enumerate(rows):
        y = TOP + i * ROW + ROW / 2
        # Which ordering this row's entry came from — entry() falls back from
        # the normal-ordering value to the one quoted for both, and the row
        # has to record which, not guess.
        byo = (rel.get("values") or {}).get(pname) or {}
        ordering = "no" if byo.get("no") is e else "any"
        out.extend(_rel_range_row(pname, ordering, meta[pname]["label"], "",
                                  meta[pname].get("unit"), e, y, "var(--no)",
                                  L, R, W, font=11.5, value_font=11))

    out.append(f'<text x="{L}" y="{H-6:.0f}" font-size="9.5" fill="currentColor" '
               f'opacity=".6">width = 3σ range as a percentage of the best fit</text>')
    out.append(f'<text x="{W-R}" y="{H-6:.0f}" text-anchor="end" font-size="9.5" '
               f'font-family="var(--mono)" fill="currentColor" opacity=".5">'
               f'arXiv:{rel["arxiv"]}</text>')

    body = "\n".join(out)
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Best fit with 1σ and 3σ '
            'ranges for each oscillation parameter, normal ordering, current release. '
            'All six rows share one horizontal scale, measured in percent of each '
            "parameter's own best fit, so the width of a row is how well that "
            'parameter is known: the narrowest is the mass splitting |Δm²| and the '
            'widest by far is the CP phase δ, which runs past the edge of the axis">\n'
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
    # Two parameter keys differ only in case — dm2 (δm²) and Dm2 (|Δm²|) — and
    # this machine's filesystem does not. spark-dm2.svg and spark-Dm2.svg were
    # one file, written twice: the second overwrote the first and the home
    # page drew |Δm²|'s curve inside the δm² card. Slugs must therefore differ
    # by more than case, and the guard below refuses to write a set that does
    # not, on any filesystem, so the bug cannot come back silently.
    slugs = {p: SPARK_SLUG.get(p, p) for p in PARAMS}
    seen: dict[str, str] = {}
    for pname, slug in slugs.items():
        clash = seen.get(slug.lower())
        if clash:
            raise SystemExit(
                f"spark slug {slug!r} for {pname!r} collides with {clash!r} on a "
                "case-insensitive filesystem — give one of them a distinct name "
                "in SPARK_SLUG")
        seen[slug.lower()] = pname
    for pname in PARAMS:
        svg = spark_svg(pname, bari)
        if svg:
            (OUT / f"spark-{slugs[pname]}.svg").write_text(svg, encoding="utf-8")
            written.append(f"spark-{slugs[pname]}")

    print(f"figures: {len(written)} written to {OUT.relative_to(ROOT)}")
    for name in written:
        print("   ", name)


if __name__ == "__main__":
    main()
