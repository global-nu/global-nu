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
    page can offer without shipping a line of JavaScript — and, beside it,
    the same facts as data- attributes, which figure.js renders as a proper
    panel once a figure has been enlarged and its points are big enough to
    aim at. The <title> stays: it is what answers when the script does not
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

DATA = ROOT / "site-src" / "data" / "history.yaml"
OUT = ROOT / "site-src" / "content" / "history.md"

# Panel geometry, in SVG user units.
W, H = 520, 250
PAD_L, PAD_R, PAD_T, PAD_B = 54, 14, 16, 34

# Radius of the invisible disc that makes a point hittable, against ink of
# 4.6. It does overlap its neighbours: compare_panel staggers groups in the
# same year by 3.4 units, which is less than the ink's own radius, so those
# markers already overlap before any hit area is added. SVG resolves an
# overlap by document order — the last drawn wins — not by which centre is
# nearer, so where two groups nearly coincide the hover panel answers for the
# topmost point. That is a property of the drawing, not of this number, and
# the enlarged view is the cure: at 4x the stagger is 14 screen pixels and
# the two are separately reachable. Kept at 9 rather than larger so that in
# panel(), where nothing is staggered, a disc still cannot reach the
# neighbouring year.
HIT_R = 9

GROUPS = [
    ("bari", "Bari", "var(--grp-bari)", "no"),
    ("nufit", "NuFit", "var(--grp-nufit)", "io"),
    ("valencia", "Valencia", "var(--grp-valencia)", "any"),
]

# How a group key is written on the page. `.capitalize()` used to do this job
# and lowercased everything after the first letter, so the citation table —
# the one place whose whole point is that the metadata is exact — printed
# another group's name as "Nufit" six times over.
GROUP_DISPLAY = {"bari": "Bari", "nufit": "NuFit", "valencia": "Valencia"}

ORDERINGS = [
    ("no", "Normal ordering", "var(--no)"),
    ("io", "Inverted ordering", "var(--io)"),
    ("any", "Both orderings", "var(--text-soft)"),
]

# A compare-panel point whose true value sits far enough below the rest of
# its series that including it in the axis range would crush the resolution
# of every later measurement. Listed as (year, group, parameter). Excluded
# from the axis range and from the connecting line to its neighbour, but
# still drawn — clamped to the panel floor, with a dashed tail and its own
# value printed beside it. Kept out of the *scale*, never out of the
# *picture*.
#
# The one entry here is NuFit's 2001 value for dm2 (the solar splitting,
# delta m^2): 3.3, quoted with no error bar, against a modern cluster in the
# high 6s to low 9s. It is the single earliest record in the whole register
# and the reason the axis would otherwise span roughly 2.6-9.8 instead of
# roughly 6.6-9.3.
#
# The floor-clamp treatment below only ever draws e["best"]: it has no
# rendering for a 3σ range, because a range that is itself off-scale can't be
# clamped the way a single point can without implying a width it doesn't
# have. An entry listed here that also carries "s3" is therefore refused at
# render time (see compare_panel) rather than silently drawn without its
# range — adding one has to be a decision, not a side effect of editing this
# set.
OFF_SCALE_COMPARE = {(2001, "nufit", "dm2")}

# How far above the axis baseline the floor-clamped marker sits, in the same
# SVG user units as W/H/PAD_*. Large enough that the dashed tail and the
# marker read as sitting *on* the floor rather than *in* the data — a value
# of 0 would put the marker on the axis line itself, indistinguishable from
# a genuine point that happens to be low; 14 clears the axis line, the tick
# labels below it, and leaves room for the tail to register as a tail rather
# than a pixel-length smudge.
OFF_SCALE_FLOOR_GAP = 14


def group_name(rel: dict) -> str:
    """The group as the citation table prints it.

    A release flagged `predecessor: true` is one published before the series
    it is filed under had that name — the 2001 and 2004 IFIC-Valencia fits,
    recorded under `nufit` for continuity of lineage. Printing them as plain
    "NuFit" states as fact a lineage judgement that is at least arguable,
    beside a separate "Valencia" column carrying two of the same authors. The
    label says which it is; the note above the table says why.
    """
    key = rel["group"]
    name = GROUP_DISPLAY.get(key)
    if name is None:
        raise SystemExit(f"unknown group key {key!r}: add it to GROUP_DISPLAY")
    return f"{name} (predecessor)" if rel.get("predecessor") else name


def nice_bounds(lo: float, hi: float) -> tuple[float, float]:
    """Pad a data range so marks never touch the frame."""
    if hi == lo:
        return lo - 1, hi + 1
    pad = (hi - lo) * 0.12
    return lo - pad, hi + pad


def bound_value(e: dict) -> float:
    """The number that fixes a record's vertical position: the best fit for a
    measurement, the printed bound for a limit. Used for the axis range, the
    year-to-year connecting line, and placing the marker itself, so a limit
    can never fall outside the area its own bound was used to compute."""
    return e["upper"] if history.kind_of(e) == "limit" else e["best"]


def interval_of(entry: dict) -> tuple[list | None, str]:
    """The interval to draw for an entry, together with the level it holds at.

    Nine entries in history.yaml publish a 1σ range and no 3σ one — Bari's
    δ/π from 2012 to 2017, and sin²θ13 in 2008. The panels used to fall back
    to that 1σ range and go on calling it "3σ", so a 1σ interval reached the
    site announced as three times its width. The level travels with the
    numbers here so that no caller can print one while drawing the other.
    """
    if entry.get("s3"):
        return entry["s3"], "3σ"
    if entry.get("s1"):
        return entry["s1"], "1σ"
    return None, ""


def range_text(entry: dict) -> str:
    """An entry's interval as the hover panel and the <title> both print it."""
    rng, level = interval_of(entry)
    if not rng:
        return ""
    return f"{level} {history.value_text(rng[0])}–{history.value_text(rng[1])}"


# What every plotted point must be able to say about itself. A point that
# cannot answer "which group, which year, which parameter, what value" is a
# point the hover panel would open blank on, and a reader would sooner
# distrust the whole figure than a single dot in it.
MARKER_FACTS = ("group", "year", "param", "value", "unit", "ordering")


def facts_attrs(facts: dict) -> str:
    """Render a point's facts as data- attributes for the hover panel.

    The panel reads these rather than parsing the <title> text, which is
    written for a human and would have to be re-parsed — and re-escaped —
    every time its wording changed.
    """
    missing = [k for k in MARKER_FACTS if not str(facts.get(k, "")).strip()]
    if missing:
        raise SystemExit(
            "marker(): a plotted point must carry its own facts — missing "
            f"{', '.join(missing)} in {facts!r}. See MARKER_FACTS.")
    return "".join(f' data-{k}="{html.escape(str(v), quote=True)}"'
                   for k, v in facts.items() if str(v).strip())


def marker(kind: str, x: float, y: float, colour: str, label: str,
           facts: dict | None = None, hollow: bool = False,
           level_text: str = "") -> str:
    """Circle for NO, square for IO, diamond for “both”: shape carries the
    same information as colour, for readers who cannot use the colour.

    hollow draws the same shape unfilled, outlined in the group colour
    instead of solid-filled with a background ring — used only for the
    floor-clamped off-scale marker in compare_panel, so a clamped point
    cannot be mistaken for a genuine plotted value at a glance: same shape
    and colour encode the same group, but the missing fill is a second,
    independent signal that this mark is not an ordinary point.

    level_text is the confidence level a "limit-upper" arrow holds at, as
    tools.history.LEVEL_TEXT renders it ("3σ", "90% CL"). It is drawn beside
    the arrow, on the panel — not only in the <title>, which is a hover
    layer no touch screen, no printout and no reader scanning the panel ever
    sees. Two arrows at different levels are not comparable, so a limit whose
    level the page does not show is a limit the page invites a reader to
    mis-compare: drawing one without a level is refused outright rather than
    left to the tooltip.

    Every label is escaped: a limit label opens with a literal "<", and a
    future parameter label containing "&" or "<" would otherwise break the
    page rather than show a wrong character.
    """
    ring = ' stroke="var(--bg)" stroke-width="2" paint-order="stroke"'
    fill = "none" if hollow else colour
    outline = f' stroke="{colour}" stroke-width="1.8"' if hollow else ring
    t = f"<title>{html.escape(label, quote=False)}</title>"

    # The ink is four pixels across, and a limit is a two-pixel stroke with no
    # fill at all: aiming at one with a mouse is luck, and with a finger it is
    # nothing. Every point therefore gets an invisible disc, drawn first so it
    # sits under the ink, wide enough to be hit — fill="none" so it cannot
    # print or show, pointer-events="all" so it is still a target.
    hit = (f'<circle class="pt__hit" cx="{x:.1f}" cy="{y + (5 if kind == "limit-upper" else 0):.1f}" '
           f'r="{HIT_R}" fill="none" pointer-events="all"/>')

    def wrap(ink: str) -> str:
        return f'<g class="pt"{facts_attrs(facts or {})}>{t}{hit}{ink}</g>'

    if kind == "no":
        return wrap(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.6" fill="{fill}"{outline}/>')
    if kind == "io":
        return wrap(f'<rect x="{x - 4.2:.1f}" y="{y - 4.2:.1f}" width="8.4" height="8.4" rx="1.2" '
                    f'fill="{fill}"{outline}/>')
    if kind == "limit-upper":
        if not level_text:
            raise SystemExit(
                "marker(): a limit arrow must be drawn with its confidence level "
                "(level_text=), because the page states that it prints one beside "
                f"every limit — label was {label!r}")
        # A downward arrow from the bound: the value lies below this line,
        # somewhere, and the drawing must not suggest a point estimate. The
        # level sits to its right, in the panel's recessive text token and at
        # the size of the axis labels — the smallest type this page asks
        # anyone to read — so it reads as annotation of the arrow rather than
        # as a second data mark, and still reads.
        return wrap(
                f'<path d="M{x - 5:.1f} {y:.1f}L{x + 5:.1f} {y:.1f}M{x:.1f} {y:.1f}'
                f'L{x:.1f} {y + 11:.1f}M{x - 3.4:.1f} {y + 7:.1f}L{x:.1f} {y + 11:.1f}'
                f'L{x + 3.4:.1f} {y + 7:.1f}" fill="none" stroke="{colour}" '
                f'stroke-width="2" stroke-linecap="round"/>'
                f'<text x="{x + 7:.1f}" y="{y + 3.5:.1f}" font-size="10.5" '
                f'fill="currentColor" opacity=".75">{html.escape(level_text, quote=False)}</text>')
    return wrap(f'<path d="M{x:.1f} {y - 5.2:.1f}L{x + 5.2:.1f} {y:.1f}'
                f'L{x:.1f} {y + 5.2:.1f}L{x - 5.2:.1f} {y:.1f}Z" fill="{fill}"{outline}/>')


def to_our_Dm2(rel: dict, ordering: str, value: float) -> float:
    """Convert a splitting reported in another convention into ours.

    Identity, for either ordering:  Dm2 = Dm2_31 - dm2/2.
      * NuFit reports Dm2_3l, i.e. Dm2_31 (>0) for NO and Dm2_32 (<0) for IO;
        Dm2_31 = Dm2_32 + dm2, so for IO  Dm2 = Dm2_32 + dm2/2.
      * Valencia reports |Dm2_31| for BOTH orderings, so for IO the signed
        value is -|Dm2_31| and  |Dm2| = |Dm2_31| + dm2/2.
    The sign of the correction therefore differs between the two groups, which
    is exactly why this file stores what each paper printed.

    dm2 is in 1e-5 eV2 and the splittings in 1e-3 eV2, hence the /200.
    """
    dm2 = rel["values"]["dm2"]["any"]["best"] / 200.0
    kind = rel["reported_splitting"]
    if kind == "Dm2_3l":
        return abs(value - dm2) if ordering == "no" else abs(value + dm2)
    if kind == "abs_Dm2_31":
        return value - dm2 if ordering == "no" else value + dm2
    raise SystemExit(f"unknown reported_splitting: {kind}")


def propagate_interval(best: float, interval: tuple[float, float], sign: int,
                       offset: float, sigma_offset: float,
                       rho: float | None = None) -> tuple[float, float]:
    """Convert an interval on X into one on Delta m^2 = X + sign*offset.

    Both quantities are measured, so the uncertainty on the offset u = dm2/2
    belongs in the answer:

        sigma^2(Dm2) = sigma^2(X) + sigma^2(u) + 2*sign*rho*sigma(X)*sigma(u)

    This is a propagation, not a translation. Shifting the published interval
    rigidly would keep sigma(X) and drop sigma(u) altogether — an assumption
    that dm2 is known exactly, which it is not. With sigma(u) = 0 the formula
    reduces to that shift, which is the only case where the shift is right.

    rho is the correlation between X and dm2. It is not published by any group
    in this register, so it is normally None and the cross term is omitted —
    an omission that costs up to about 4% of the width either way on the
    current release, and which is declared rather than hidden: see
    `interval_method` in the exported register.

    Each side propagates from its own half-width, so an asymmetric interval
    stays asymmetric. Collapsing it to a single sigma first would discard the
    asymmetry the source paper reported.
    """
    lo, hi = interval
    centre = best + sign * offset
    cross = 0.0 if rho is None else 2.0 * sign * rho * sigma_offset

    def side(half: float) -> float:
        var = half * half + sigma_offset * sigma_offset + cross * half
        # Numerically, a strong positive rho on a half-width comparable with
        # sigma(u) can drive the variance to a very small negative number.
        return math.sqrt(max(var, 0.0))

    return centre - side(best - lo), centre + side(hi - best)


def conversion_scale(doc: dict) -> dict:
    """How big the change of convention is, in units a reader can judge.

    Two numbers, both computed from the most recent Bari release rather than
    written into the prose, because the next global fit changes both and a
    typed figure would quietly stop being true.

      offset_sigma          the shift between conventions, delta m^2/2,
                            expressed in standard deviations of Delta m^2
      error_inflation_pct   what that shift's own uncertainty does to the
                            error bar, added in quadrature

    The pair is the whole answer to "what happens to the errors when you
    convert". The central value moves by more than the error bar; the error
    bar barely moves at all. Stating only the first invites a reader to think
    the two analyses disagree; stating only the second invites them to compare
    raw numbers across groups.

    Both use the 1 sigma interval, halved to a standard deviation. This is the
    constant-shift treatment, which neglects the delta m^2 - Delta m^2
    correlation: see `interval_method` in the exported register.
    """
    bari = [r for r in doc["releases"]
            if r["group"] == "bari" and "Dm2" in (r.get("values") or {})]
    rel = bari[-1]
    dm2 = rel["values"]["dm2"]["any"]
    Dm2 = rel["values"]["Dm2"]["no"]

    # dm2 is in 1e-5 eV^2 and the splittings in 1e-3, hence the /100.
    offset = dm2["best"] / 2 / 100.0
    sig_offset = (dm2["s1"][1] - dm2["s1"][0]) / 2 / 2 / 100.0
    sig_Dm2 = (Dm2["s1"][1] - Dm2["s1"][0]) / 2

    # What the correlation is worth, as a range. sigma^2(Dm2) = sigma^2(X)
    # + sigma^2(u) -+ 2 rho sigma(X) sigma(u) with u = dm2/2: rho = +-1 are the
    # extremes, and they bracket every possible value. The point of quoting
    # them is that they are far larger than the rho = 0 term, so "we neglected
    # the correlation" is a bigger admission than "we neglected sigma(dm2)".
    def _sig(rho: float) -> float:
        return math.sqrt(sig_Dm2**2 + sig_offset**2
                         - 2.0 * rho * sig_Dm2 * sig_offset)

    return {
        "year": rel["year"],
        "arxiv": rel["arxiv"],
        "offset": offset,
        "offset_sigma": offset / sig_Dm2,
        "offset_pct": 100.0 * offset / Dm2["best"],
        "sigma_Dm2": sig_Dm2,
        "sigma_offset": sig_offset,
        "error_inflation_pct":
            100.0 * (math.hypot(sig_Dm2, sig_offset) / sig_Dm2 - 1.0),
        "corr_swing_pct": 100.0 * (_sig(1.0) / sig_Dm2 - 1.0),
        "corr_swing_pct_neg": 100.0 * (_sig(-1.0) / sig_Dm2 - 1.0),
    }


def our_Dm2(rel: dict, ordering: str) -> dict | None:
    """The Dm2 entry of a release, in our convention, or None."""
    v = rel.get("values") or {}
    if rel["group"] == "bari":
        return (v.get("Dm2") or {}).get(ordering)
    src = v.get(rel.get("reported_splitting", ""))
    if not src or ordering not in src:
        return None
    e = src[ordering]
    out = {"best": to_our_Dm2(rel, ordering, e["best"])}
    for level in ("s1", "s3"):
        got = converted_interval(rel, ordering, e, level)
        if got:
            out[level] = list(got)
    return out


def converted_interval(rel: dict, ordering: str, entry: dict,
                       level: str) -> tuple[float, float] | None:
    """One published interval, converted into our convention. Or None.

    The offset's own uncertainty is taken at the SAME confidence level as the
    interval being converted — a 3 sigma range is widened by the 3 sigma
    uncertainty on delta m^2/2, not by the 1 sigma one. Mixing the two would
    understate a 3 sigma range by roughly a factor of three in that term.

    The modulus is applied after propagating, not before: NuFit reports a
    negative Dm2_32 in inverted ordering, and taking |.| reverses which end of
    the interval is which, so the endpoints are sorted afterwards. The old code
    converted the two endpoints separately and sorted for the same reason; what
    is new is that the width grows instead of being carried across unchanged.
    """
    pub = entry.get(level)
    dm2 = ((rel.get("values") or {}).get("dm2") or {}).get("any")
    if not pub or not dm2:
        return None

    # dm2 is in 1e-5 eV^2 and the splittings in 1e-3, so u = dm2/2 is dm2/200.
    offset = dm2["best"] / 200.0
    dm2_range = dm2.get(level)
    sigma_offset = ((dm2_range[1] - dm2_range[0]) / 2 / 200.0
                    if dm2_range else 0.0)
    sign = -1 if ordering == "no" else +1

    lo, hi = propagate_interval(entry["best"], (pub[0], pub[1]), sign,
                                offset, sigma_offset)
    if rel.get("reported_splitting") == "Dm2_3l":
        lo, hi = sorted((abs(lo), abs(hi)))

    # A propagated bound is a square root: its exact value has no last digit,
    # so how many to print is a decision rather than a fact. The only
    # defensible one is the precision of the source — printing further would
    # claim accuracy the paper never had. (history.VALUE_DP is 10, which is
    # right for the old subtraction of two printed decimals, where it removed
    # IEEE noise and could not reach a real digit. It is wrong here.)
    # ...but never so coarse that the conversion itself disappears. NuFit 2004
    # printed its 3 sigma range to one decimal while the offset is 0.0405, so
    # rounding to the source alone would give back the published numbers
    # unchanged and hide the conversion entirely — while the centre, an exact
    # subtraction, plainly moved. The offset's own precision is the floor.
    # The offset's precision comes from the SOURCE value, not from the
    # quotient: dm2/200 in binary floating point is 0.037049999999999995, whose
    # repr has eighteen decimals and means nothing. Dividing by 200 shifts by
    # two places and the halving can add one more, hence +3.
    dp = max(_decimals(pub[0]), _decimals(pub[1]), _decimals(dm2["best"]) + 3)
    return round(lo, dp), round(hi, dp)


def _decimals(value: float) -> int:
    """How many decimal places a source number was written with."""
    text = repr(float(value))
    if "e" in text or "E" in text or "." not in text:
        return 0
    return len(text.split(".")[1])


def compare_panel(pname: str, meta: dict, releases: list[dict]) -> str:
    """One parameter, normal ordering, the three groups against each other.

    OFF_SCALE_COMPARE points are left out of the axis-range and connecting-
    line calculations below, then drawn separately, clamped to the floor:
    see the constant's docstring for why.
    """
    series: dict[str, list[tuple[int, dict, str]]] = {g: [] for g, _, _, _ in GROUPS}
    for rel in releases:
        ordering = "Normal ordering"
        if pname == "Dm2":
            e = our_Dm2(rel, "no")
        else:
            byo = (rel.get("values") or {}).get(pname) or {}
            e = byo.get("no")
            if not e:
                # A paper that quotes one value for both orderings: the panel
                # plots it in the normal-ordering row, and the hover panel has
                # to say that it is not a normal-ordering number.
                e, ordering = byo.get("any"), "Both orderings"
        if e:
            series[rel["group"]].append((rel["year"], e, ordering))
    plotted = [(gid, y, e) for gid, v in series.items() for y, e, _ in v]
    if not plotted or sum(1 for v in series.values() if v) < 2:
        return ""

    years = sorted({y for _, y, _ in plotted})
    x0, x1 = min(years) - 0.8, max(years) + 0.8
    vals = []
    for gid, y, e in plotted:
        if (y, gid, pname) in OFF_SCALE_COMPARE:
            continue
        vals.append(bound_value(e))
        vals += list(e.get("s3") or [])
    if not vals:
        return ""
    y0, y1 = nice_bounds(min(vals), max(vals))
    sx = lambda v: PAD_L + (v - x0) / (x1 - x0) * (W - PAD_L - PAD_R)
    sy = lambda v: H - PAD_B - (v - y0) / (y1 - y0) * (H - PAD_T - PAD_B)

    out = [f'<line x1="{PAD_L}" y1="{H - PAD_B}" x2="{W - PAD_R}" y2="{H - PAD_B}" '
           'stroke="currentColor" stroke-width="1" opacity=".35"/>',
           f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H - PAD_B}" '
           'stroke="currentColor" stroke-width="1" opacity=".35"/>']
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

    label, unit = meta["label"], meta["unit"]
    # A small horizontal offset per group so coincident years stay readable.
    dx = {"bari": -3.4, "nufit": 0.0, "valencia": 3.4}
    off_here = []
    for gid, gname, colour, shape in GROUPS:
        pts_all = sorted(series[gid], key=lambda t: t[0])
        if not pts_all:
            continue
        # The connecting line and the 3σ rule only ever run between points
        # that share the axis: an off-scale point cannot be joined to its
        # neighbour without implying a scale it is not drawn on.
        pts_line = [(yr, e) for yr, e, _ in pts_all if (yr, gid, pname) not in OFF_SCALE_COMPARE]
        for yr, e in pts_line:
            if e.get("s3"):
                out.append(f'<line x1="{sx(yr) + dx[gid]:.1f}" y1="{sy(e["s3"][0]):.1f}" '
                           f'x2="{sx(yr) + dx[gid]:.1f}" y2="{sy(e["s3"][1]):.1f}" stroke="{colour}" '
                           'stroke-width="2" stroke-linecap="round" opacity=".34"/>')
        if len(pts_line) > 1:
            d = " ".join(f'{"M" if i == 0 else "L"}{sx(y) + dx[gid]:.1f} {sy(bound_value(e)):.1f}'
                         for i, (y, e) in enumerate(pts_line))
            out.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                       'stroke-linejoin="round" opacity=".5"/>')
        for yr, e, ordering in pts_all:
            x = sx(yr) + dx[gid]
            base = {"group": gname, "year": yr, "param": label,
                    "unit": unit, "ordering": ordering}
            if (yr, gid, pname) in OFF_SCALE_COMPARE:
                if e.get("s3"):
                    raise SystemExit(
                        f"{pname}: OFF_SCALE_COMPARE entry ({yr}, {gid!r}) carries a 3σ "
                        "range, which the floor-clamp treatment has no drawing for — it "
                        "would be silently lost. Either add explicit handling for a "
                        "ranged off-scale point, or drop it from OFF_SCALE_COMPARE.")
                off_here.append((gname, yr, e))
                y_floor = H - PAD_B - OFF_SCALE_FLOOR_GAP
                out.append(f'<line x1="{x:.1f}" y1="{y_floor:.1f}" x2="{x:.1f}" y2="{H - PAD_B:.1f}" '
                           f'stroke="{colour}" stroke-width="1.4" stroke-dasharray="2 3" opacity=".6"/>')
                out.append(marker(shape, x, y_floor, colour,
                                  f"{gname}, {yr}: {label} = {history.value_text(e['best'])} "
                                  f"({unit}) — below this panel's range, drawn at the floor, "
                                  "not to scale",
                                  facts={**base, "value": history.value_text(e["best"]),
                                         "range": range_text(e),
                                         "note": "Below this panel's range — drawn at the "
                                                 "floor, not to scale"},
                                  hollow=True))
                out.append(f'<text x="{x + 7:.1f}" y="{y_floor + 3.5:.1f}" font-size="9.5" '
                           f'fill="currentColor" opacity=".75">{history.value_text(e["best"])}</text>')
                continue
            if history.kind_of(e) == "limit":
                out.append(marker("limit-upper", x, sy(e["upper"]), colour,
                                  f"{gname}, {yr}: {label} {history.limit_label(e)} ({unit})",
                                  facts={**base, "value": history.limit_label(e),
                                         "kind": "limit",
                                         "level": history.level_text(e)},
                                  level_text=history.level_text(e)))
                continue
            rng = e.get("s3")
            span = (f', 3σ {history.value_text(rng[0])}–{history.value_text(rng[1])}'
                    if rng else "")
            out.append(marker(shape, x, sy(e["best"]), colour,
                              f"{gname}, {yr}: {label} = {history.value_text(e['best'])}"
                              f"{span} ({unit})",
                              facts={**base, "value": history.value_text(e["best"]),
                                     # What this panel drew, not what the paper
                                     # published: compare_panel rules only 3σ,
                                     # so a point whose 1σ is all there is has
                                     # no bar here and the panel must not claim
                                     # one it did not draw.
                                     "range": (f'3σ {history.value_text(rng[0])}–'
                                               f'{history.value_text(rng[1])}') if rng else ""}))

    conv = ("  Values of other groups converted to our convention."
            if pname == "Dm2" else "")
    off_note = ""
    if off_here:
        # "3.3 1e-5 eV²" reads as a typo in running prose, where the unit is
        # not sitting under a panel title to be read as a normalisation.
        parts = "; ".join(f"{gname} {yr} ({history.value_text(e['best'])}, in units "
                          f"of {unit})" for gname, yr, e in off_here)
        off_note = (f"  {parts} lies far below the rest of this series; drawn at the panel "
                    "floor and labelled with its value, not to scale, so the later "
                    "measurements keep their resolution.")
    return f"""<figure class="figure reveal">
<h4>{label} <span class="figure__unit">/ {unit} · normal ordering</span></h4>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label} in normal ordering, compared across the Bari, NuFit and Valencia global analyses">
{chr(10).join(out)}
</svg>
<p class="cap">Best fit with its 3σ range, normal ordering.{conv}{off_note}</p>
</figure>"""


def panel(pname: str, meta: dict, releases: list[dict]) -> str:
    """One small multiple: best fit and 3σ range against publication year."""
    series: dict[str, list[tuple[int, dict, dict]]] = {k: [] for k, _, _ in ORDERINGS}
    for rel in releases:
        entry = (rel.get("values") or {}).get(pname)
        if not entry:
            continue
        for key in series:
            if key in entry:
                # The release travels with its point: the hover panel names
                # the group, and deriving it from "these are all Bari" would
                # be a comment pretending to be code the day it stops being.
                series[key].append((rel["year"], entry[key], rel))

    points = [(y, e) for s in series.values() for y, e, _ in s]
    if not points:
        return ""

    years = sorted({y for y, _ in points})
    x0, x1 = min(years) - 0.8, max(years) + 0.8
    vals = []
    for _, e in points:
        vals.append(bound_value(e))
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
    fell_back = False
    for kind, name, colour in ORDERINGS:
        pts = sorted(series[kind], key=lambda t: t[0])
        if not pts:
            continue
        # The interval as a thin vertical rule behind the marker
        for yr, e, _ in pts:
            rng, level = interval_of(e)
            if rng:
                fell_back = fell_back or level == "1σ"
                out.append(f'<line x1="{sx(yr):.1f}" y1="{sy(rng[0]):.1f}" '
                           f'x2="{sx(yr):.1f}" y2="{sy(rng[1]):.1f}" stroke="{colour}" '
                           'stroke-width="2" stroke-linecap="round" opacity=".38"/>')
        if len(pts) > 1:
            d = " ".join(f'{"M" if i == 0 else "L"}{sx(y):.1f} {sy(bound_value(e)):.1f}'
                         for i, (y, e, _) in enumerate(pts))
            out.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2" '
                       'stroke-linejoin="round" opacity=".55"/>')
        for yr, e, rel in pts:
            base = {"group": group_name(rel), "year": yr, "param": label,
                    "unit": unit, "ordering": name}
            if history.kind_of(e) == "limit":
                out.append(marker("limit-upper", sx(yr), sy(e["upper"]), colour,
                                  f"{name}, {yr}: {label} {history.limit_label(e)} ({unit})",
                                  facts={**base, "value": history.limit_label(e),
                                         "kind": "limit",
                                         "level": history.level_text(e)},
                                  level_text=history.level_text(e)))
                continue
            span = range_text(e)
            out.append(marker(kind, sx(yr), sy(e["best"]), colour,
                              f"{name}, {yr}: {label} = {history.value_text(e['best'])}"
                              f"{', ' + span if span else ''} ({unit})",
                              facts={**base, "value": history.value_text(e["best"]),
                                     "range": span}))

    # Nine entries publish a 1σ range and no 3σ one. The rule is drawn either
    # way — a measurement with no error bar at all would read as a claim of
    # precision it never made — but a panel that draws two different levels
    # must say so, and each point states its own on hover.
    fallback_note = ("  Where a paper published no 3σ range, its 1σ range is drawn "
                     "instead; every point states which it is." if fell_back else "")
    # The accessible name has to carry the same caveat. A screen reader hears
    # this sentence instead of seeing the panel, so a name that says "3σ
    # ranges" over a panel drawing 1σ ones misleads the one reader who cannot
    # check it against the drawing.
    ranges = "3σ ranges" if not fell_back else "the range each paper published"
    body = "\n".join(out)
    return f"""<figure class="figure reveal">
<h4>{label} <span class="figure__unit">/ {unit}</span></h4>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label} best-fit values and {ranges} by publication year, for the two mass orderings">
{body}
</svg>
<p class="cap">Best fit with its 3σ range, by year of publication.{fallback_note} Values and
sources in the table below.</p>
</figure>"""


def main() -> None:
    doc = history.load()

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
    all_releases = sorted(doc["releases"], key=lambda r: (r["year"], r["group"]))
    releases = [r for r in all_releases if r["group"] == "bari"]

    panels = "\n\n".join(p for p in (panel(k, v, releases) for k, v in params.items()) if p)
    compare = "\n\n".join(
        p for p in (compare_panel(k, v, all_releases) for k, v in params.items()) if p)

    others = [r for r in all_releases if r["group"] != "bari"]
    # How big the change of convention actually is, computed rather than
    # written into the prose below — see conversion_scale's docstring.
    scale = conversion_scale(doc)
    other_rows = "\n".join(
        f'<tr><th scope="row">{r["year"]}</th>'
        f'<td class="ref">{group_name(r)} — {r["title"]}'
        f'<span class="ref__meta">{r["journal"]}</span></td>'
        f'<td><a href="https://arxiv.org/abs/{r["arxiv"]}">arXiv:{r["arxiv"]}</a></td>'
        f'<td>{r["table"]}{("<br>" + r["variant"]) if r.get("variant") else ""}</td>'
        f'<td class="mono small">{r["convention"]}</td></tr>'
        for r in others)

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

    # Range endpoints on a release the register flags `derived: true`: the
    # paper states the value as a central value ± error and the endpoint is
    # computed from it, so test_history_numbers.py does not search the source
    # for it (it skips every non-`best` value on such a release, and prints
    # "N declared as derived, not searched"). Counted here rather than typed,
    # so the sentence on the page cannot drift from the data — the page used
    # to say every value was verified against its source table, which was
    # true of all but these.
    n_derived = sum(
        1
        for r in releases
        if r.get("derived")
        for e in (r.get("values") or {}).values()
        for o in e.values()
        for k in ("s1", "s2", "s3")
        if k in o
        for _ in (o[k] if isinstance(o[k], list) else [o[k]])
    )

    # Lazy: make_history_data imports this module, so importing it at the top
    # would be a cycle. The field table is generated from its FIELD_DOCS so the
    # documentation cannot describe columns the export does not emit.
    import make_history_data as mhd
    field_rows = "\n".join(
        f"<tr><td><code>{name}</code></td><td>{doc}</td></tr>"
        for name, doc in mhd.FIELD_DOCS)

    page = f"""---
title: Parameter history
url: history.html
description: >-
  How the neutrino oscillation parameters moved across the Bari, NuFit and
  Valencia global analyses, from the first hint of θ₁₃ to subpercent
  precision — every point traced to the table it came from.
katex: false
jsonld: dataset
---

<!-- Generated by tools/make_history.py from site-src/data/history.yaml.
     Do not edit this file: edit the data and regenerate. -->

<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Parameter history</p>
    <h1>Bari, NuFit and Valencia, on the same axes</h1>
    <p class="lede">How the oscillation parameters have moved across three
    independent global analyses, and, in finer grain, across every published
    update of the Bari fit: best fit and 3σ range, for both mass orderings.
    No point is interpolated, rescaled or read off a figure.</p>
  </div>
</section>

::: section #compare

<div class="section-head">
  <h2>Compared with the other groups</h2>
  <p>normal ordering · {len(others)} releases from NuFit and Valencia</p>
</div>

<div class="callout">
<h4>Reading a comparison across conventions</h4>
<p>The three groups do not report the same quantity. We use
Δm² = m₃² − ½(m₁² + m₂²), which is the same thing as the half-sum
<strong>Δm² = ½(Δm²₃₁ + Δm²₃₂)</strong> — and written that way the conversion
can be read off directly, since Δm²₃₁ − Δm²₃₂ = δm². NuFit reports Δm²₃ℓ,
which is Δm²₃₁ &gt; 0 for normal ordering and Δm²₃₂ &lt; 0 for inverted.
Valencia reports |Δm²₃₁| for <em>both</em> orderings.</p>
<p>From the identity Δm² = Δm²₃₁ − δm²/2, the correction is −δm²/2 for normal
ordering in every case. In inverted ordering the two groups differ, and the
difference is clearest stated on the modulus, which is what every number on
this page is plotted as. NuFit publishes Δm²₃ℓ = Δm²₃₂ &lt; 0, and adding
δm²/2 to a negative number makes its modulus <em>smaller</em>: the shift is
<strong>−δm²/2 for NuFit</strong>. Valencia publishes |Δm²₃₁|, already a
modulus, and the same addition makes it <em>larger</em>: the shift is
<strong>+δm²/2 for Valencia</strong>. Same identity, opposite effect on the
plotted number — which is why this site stores what each paper printed and
converts in code, where the rule can be read:
<code>tools/make_history.py</code>, function <code>to_our_Dm2</code>.</p>
<p><strong>What this does to the errors.</strong> The offset carries its own
uncertainty, so the converted interval is <em>wider</em> than the published
one — it is propagated, not translated. The two effects are of completely
different sizes, and on the {scale['year']}
Bari release they can be put in numbers: the offset δm²/2 is
<strong>{scale['offset_sigma']:.1f}σ of Δm²</strong> — larger than the error
bar itself — while the uncertainty it adds grows that error bar by
<strong>{scale['error_inflation_pct']:.2f}%</strong>. So the central value
moves by more than one standard deviation and the uncertainty effectively does
not move at all. That is the whole reason two groups' Δm² must never be
compared as printed, and equally the reason their error bars can be carried
across almost unchanged.</p>
<p><strong>How to propagate the error properly.</strong> Write the conversion
as Δm² = X ∓ u, with X the splitting the other group reports and
u = δm²/2. Then, in the Gaussian approximation,</p>
<p class="formula" style="text-align:center;font-family:var(--mono)">
σ²(Δm²) = σ²(X) + σ²(u) ∓ 2ρ·σ(X)·σ(u)
</p>
<p>where ρ = corr(X, δm²) and the sign of the last term follows the sign in the
conversion — minus where δm²/2 is subtracted (normal ordering, and Valencia's
|Δm²₃₁|), plus where it is added. More generally, for any linear combination
Z = aX + bY, σ²(Z) = a²σ²(X) + b²σ²(Y) + 2ab·ρ·σ(X)·σ(Y). ρ is read off the
two-dimensional Δχ² map in the (δm², Δm²) plane — the orientation of its 1σ
ellipse, equivalently the off-diagonal element of the inverse Hessian at the
minimum. It is exactly what a group has in hand and does not publish.</p>
<p><strong>And the correlation term dominates.</strong> On the
{scale['year']} release σ(X) = {scale['sigma_Dm2']:.4f} and
σ(u) = {scale['sigma_offset']:.5f} (10⁻³ eV²). Setting ρ = 0 changes the error
by {scale['error_inflation_pct']:+.2f}%; letting ρ run over its full range
moves it between <strong>{scale['corr_swing_pct']:+.1f}%</strong> and
<strong>{scale['corr_swing_pct_neg']:+.1f}%</strong>. Neglecting the
correlation is therefore up to fifty times larger an error than neglecting
σ(δm²) altogether. That is why the correlation term is the one piece still
missing, and why its absence is declared rather than assumed away.</p>
<p class="small muted">Every number above is computed from the register, so it
follows the fit rather than aging with the prose. The formula assumes
parabolic χ² and symmetric errors; where the interval is markedly asymmetric
the honest route is to propagate the χ² map itself rather than a σ. What the
ranges here get is the first two terms: the centre moves by u and σ(u) is
added in quadrature to each half-width, at the interval's own confidence
level. Only ρ is dropped, because no group publishes it. The exported register
records which treatment produced each interval in its
<code>interval_method</code> column: <code>propagated</code> today,
<code>propagated_rho</code> for any release that can supply ρ.</p>
<p class="small muted">NuFit prints δ<sub>CP</sub> in degrees only, so it does
not appear on the δ/π panel. Where a fit has two quasi-degenerate θ₂₃ minima,
the marker is the first one quoted and the 3σ range spans both.</p>
</div>

<div class="legend legend--chart" style="margin-top:1.4rem">
  <span><i class="k-bari"></i>Bari (circle)</span>
  <span><i class="k-nufit"></i>NuFit (square)</span>
  <span><i class="k-valencia"></i>Valencia (diamond)</span>
  <span><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style="vertical-align:middle;margin-right:.35rem"><path d="M2 2L12 2M7 2L7 12M3.6 8L7 12L10.4 8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>Upper limit, level printed on the marker</span>
  <span>Open a panel to read each point: group, year, value and range</span>
</div>

<div class="panels">

{compare}

</div>

<div class="prose" style="margin-top:2rem">
<p class="small muted">The 2001 and 2004 entries predate the NuFit name. They
are earlier IFIC-Valencia global fits — Gonzalez-Garcia, Maltoni, Peña-Garay
and Valle in 2001; Maltoni, Schwetz, Tórtola and Valle in 2004 — grouped here
with the later NuFit papers for continuity of lineage, and marked as
predecessors rather than presented as NuFit releases. Two of those authors
also appear on the Valencia papers listed below, so the three series are less
separate before 2012 than three columns suggest.</p>
</div>

<div class="table-scroll" style="margin-top:1.2rem">
<table class="data data--refs">
<caption>The releases of the other groups included above, with the convention
each one publishes in. Their values are stored exactly as printed and converted
only at rendering time.</caption>
<thead><tr><th scope="col">Year</th><th scope="col">Paper</th><th scope="col">Preprint</th><th scope="col">Source</th><th scope="col">Convention</th></tr></thead>
<tbody>
{other_rows}
</tbody>
</table>
</div>

:::

::: section alt glow

<div class="section-head">
  <h2>The Bari series</h2>
  <p>{len(releases)} releases · best fit and 3σ range, for both mass orderings</p>
</div>

<div class="callout">
<h4>How to read these panels</h4>
<p>Values are shown in the normalisation used in the papers, given under each
title. The vertical rule is the 3σ range; the marker is the best fit —
a circle for normal ordering, a square for inverted, a diamond where the
analysis quotes a single value for both. Hover a marker for the numbers.</p>
<p>All entries use our convention Δm² = m₃² − ½(m₁² + m₂²) and δm² = m₂² − m₁²
&gt; 0. Analyses by other groups use different conventions and are not plotted
here: the comparison above converts first, and states the conversion.</p>
</div>

<div class="legend legend--chart" style="margin-top:1.4rem">
  <span><i class="k-no"></i>Normal ordering (circle)</span>
  <span><i class="k-io"></i>Inverted ordering (square)</span>
  <span><i class="k-any"></i>Quoted for both (diamond)</span>
  <span><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" style="vertical-align:middle;margin-right:.35rem"><path d="M2 2L12 2M7 2L7 12M3.6 8L7 12L10.4 8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>Upper limit, level printed on the marker</span>
  <span>Open a panel to read each point: group, year, value and range</span>
</div>

<div class="panels">

{panels}

</div>

:::

::: section

<div class="section-head">
  <h2>The releases</h2>
  <p>{len(releases)} releases · {n_values} values, {n_values - n_derived} of them checked against the source they name</p>
</div>

<div class="table-scroll">
<table class="data data--refs">
<caption>Every value on this page is transcribed from the table or equations
named here. Every best fit, and every range endpoint the paper prints, is
checked against that source by <code>tools/tests/test_history_numbers.py</code>,
which re-reads each paper on every run. The exceptions are {n_derived} range
endpoints in the two earliest releases, where the paper states a central value
± an error and the endpoints are computed from it: the register marks those
releases as derived, and the test does not search the source for a number the
source never printed. Papers marked as partial updates revise only part of the
parameter set.</caption>
<thead><tr><th scope="col">Year</th><th scope="col">Paper</th><th scope="col">Preprint</th><th scope="col">Source table</th><th scope="col"></th></tr></thead>
<tbody>
{table}
</tbody>
</table>
</div>

<div class="prose" style="margin-top:2rem">
<p class="small muted">The solar-sector-only papers of 2002–2003 that precede this
series are deliberately not on this page: none of them tabulates the full
parameter set this page tracks. They are listed, with the reason, in the
excluded section of the source data (site-src/data/history.yaml).</p>
</div>

:::

::: section alt #data

<div class="section-head">
  <h2>The register as data</h2>
  <p>same rows, two formats, stable URLs</p>
</div>

<div class="table-scroll">
<table class="data">
<thead><tr><th scope="col">File</th><th scope="col">Format</th><th scope="col">URL</th></tr></thead>
<tbody>
<tr><td>Parameter history</td><td>JSON</td><td><a href="data/history.json">/data/history.json</a></td></tr>
<tr><td>Parameter history</td><td>CSV</td><td><a href="data/history.csv">/data/history.csv</a></td></tr>
</tbody>
</table>
</div>

<div class="prose" style="margin-top:1.2rem">
<p>Both files hold exactly the same rows and the same columns — CSV for a
spreadsheet or a quick <code>pandas.read_csv</code>, JSON for a script. The
URLs are stable: a regenerated release corrects rows in place, it does not move
the file. They are written by <code>tools/make_history_data.py</code> from the
same <code>history.yaml</code> this page is drawn from, so the page and the
files cannot disagree — nothing is retyped between them.</p>

<p>The JSON file is an <strong>object, not a bare array</strong>: the rows sit
under a <code>rows</code> key, and beside them a <code>note</code> says in one
sentence what the two value columns mean, so a copy that has been downloaded
and passed on still carries its own reading instructions. The CSV has nowhere
to put that note: its first line is the header of the {len(mhd.FIELD_DOCS)} field names,
and every line after it is one row, in the same order.</p>

<h3>The two value columns</h3>

<p>Every row carries the value <strong>twice</strong>, under names that cannot
be confused. <code>value_as_published</code> is exactly what the paper printed,
in the paper's own convention and normalisation.
<code>value_our_convention</code> is the same quantity converted to ours:
δm² = m₂² − m₁² &gt; 0 and Δm² = m₃² − (m₁² + m₂²)/2.</p>

<p>Only <code>Dm2</code> is ever converted. NuFit reports Δm²₃ℓ and Valencia
reports |Δm²₃₁| for <em>both</em> orderings — neither is our Δm², and the sign
of the correction is not even the same for the two groups, as the note at the
top of this page works through. The conversion lives in one function,
<code>to_our_Dm2()</code> in <code>tools/make_history.py</code>, and nowhere
else. For every other parameter, and for Bari's own <code>Dm2</code> which
already is our convention, the two columns hold the identical number. That
repetition is deliberate: a downloader gets one column that is directly
comparable across all six parameters and all three groups, without first having
to know which value needed the arithmetic.</p>
</div>

<div class="table-scroll" style="margin-top:1.4rem">
<table class="data">
<caption>{len(mhd.FIELD_DOCS)} columns, one row per (group, year, parameter, ordering)
point. This table is generated from the exporter's own field list, so it cannot
describe a column the files do not carry.</caption>
<thead><tr><th scope="col">Field</th><th scope="col">Meaning</th></tr></thead>
<tbody>
{field_rows}
</tbody>
</table>
</div>

:::
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(releases)} releases, {n_values} values, "
          f"{len(params)} panels")


if __name__ == "__main__":
    main()
