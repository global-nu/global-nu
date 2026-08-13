#!/usr/bin/env python3
"""The shape of a recorded value, checked before it can reach a page.

    ./.venv/bin/python3 tools/tests/test_history_schema.py

Until now every value in history.yaml was a measurement: a best fit with
ranges. Early papers bound a parameter instead of measuring it, and a bound
without its confidence level is not a datum — "sin²θ₁₃ < 0.05" means different
things at 90% CL and at 3σ. So a value is a measurement or a limit, never both
and never neither, and a limit names its level.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

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


# 1. the real file loads
doc = history.load()
check("history.yaml loads and validates", bool(doc.get("releases")))

# 2. classification
check("a best fit with ranges is a measurement",
      history.kind_of({"best": 2.23, "s3": [2.05, 2.41]}) == "measurement")
check("an upper bound with a level is a limit",
      history.kind_of({"upper": 5.0, "level": "3sigma"}) == "limit")

# 3. malformed records are rejected, built here rather than by editing the data
def rejects(entry: dict) -> bool:
    try:
        history.validate_value("sin2_th13", "no", entry)
        return False
    except SystemExit:
        return True

check("a value that is both a measurement and a limit is rejected",
      rejects({"best": 2.2, "s3": [2.0, 2.4], "upper": 5.0, "level": "3sigma"}))
check("a value that is neither is rejected", rejects({"note": "unclear"}))


def message(entry: dict) -> str:
    """The text of the SystemExit validate_value raises for entry."""
    try:
        history.validate_value("sin2_th13", "no", entry)
        return ""
    except SystemExit as exc:
        return str(exc)


# The two rejections above share a code path but must not share a sentence:
# "is neither" would send a reader hunting for a missing field when the real
# problem is an extra one.
check("the 'both' rejection says so, not 'neither'",
      "both a measurement and a limit"
      in message({"best": 2.2, "s3": [2.0, 2.4], "upper": 5.0, "level": "3sigma"}))
check("the 'neither' rejection says so, not 'both'",
      "neither a measurement nor a limit" in message({"note": "unclear"}))

check("a limit with no level is rejected", rejects({"upper": 5.0}))
check("a limit with an unknown level is rejected",
      rejects({"upper": 5.0, "level": "eyeballed"}))
check("a limit with a known level is accepted",
      not rejects({"upper": 5.0, "level": "90%CL"}))

# 4. the label a reader sees
check("a limit's label states the bound and the level",
      history.limit_label({"upper": 5.0, "level": "3sigma"}) == "< 5.0 (3σ)")

# 5. rendering
sys.path.insert(0, str(ROOT / "tools"))
import make_history                                     # noqa: E402

svg = make_history.marker("limit-upper", 100.0, 50.0, "var(--no)", "< 5.0 (3σ)")
diamond = make_history.marker("any", 100.0, 50.0, "var(--no)", "< 5.0 (3σ)")
check("a limit renders differently from the diamond fallback, same point",
      svg != diamond,
      f"limit:   {svg[:90]}\n         diamond: {diamond[:90]}")
check("a limit's marker is stroked and unfilled, unlike every filled shape",
      'fill="none"' in svg,
      f"got: {svg[:90]}")
check("a limit's marker carries its label", "< 5.0 (3σ)" in svg)

# 6. integration: the bound survives into compare_panel() and panel()
#
# marker() is unit-tested above in isolation. That proves the shape is right
# but nothing above ever calls compare_panel() or panel() with a limit, so a
# future edit that re-inlines e["best"] at any of the six call sites those
# two functions touch (axis range, connecting line, marker placement — times
# two functions) would go undetected here. The visible symptom of that bug is
# not a crash: it is a limit drawn outside the panel, which looks like a
# finished chart and is not. These checks parse the actual emitted SVG rather
# than recomputing the expected position, so they fail if the geometry the
# functions produce ever drifts from the geometry this file assumes.
META = {"label": "Synthetic θ", "unit": "1"}

# A bound far outside the surrounding measurements: if a call site drops the
# bound from the values that set the panel's vertical range, the axis is
# sized from the measurements alone and the arrow lands off the top of the
# frame — exactly the failure this check exists to catch.
PANEL_RELEASES = [
    {"year": 2000, "values": {"synthetic_param": {"no": {"upper": 50.0, "level": "3sigma"}}}},
    {"year": 2010, "values": {"synthetic_param": {"no": {"best": 5.0, "s3": [4.0, 6.0]}}}},
    {"year": 2012, "values": {"synthetic_param": {"no": {"best": 5.2, "s3": [4.2, 6.2]}}}},
]
COMPARE_RELEASES = [
    {"group": "bari", "year": 2000,
     "values": {"synthetic_param": {"no": {"upper": 50.0, "level": "3sigma"}}}},
    {"group": "nufit", "year": 2010,
     "values": {"synthetic_param": {"any": {"best": 5.0, "s3": [4.0, 6.0]}}}},
    {"group": "valencia", "year": 2012,
     "values": {"synthetic_param": {"any": {"best": 5.2, "s3": [4.2, 6.2]}}}},
]


def limit_marker_y(svg_out: str, label: str) -> float | None:
    """The y-coordinate of the arrow whose <title> is exactly label, parsed
    out of the emitted path — not recomputed, so a broken call site shows up
    here instead of being masked by re-deriving the same formula. Anchored on
    the label text (unique per point) and on the shape's own structural
    signature (unfilled, stroke-linecap="round", closes with </path> rather
    than self-closing) so it cannot match the group's connecting line, which
    is also an unfilled stroked <path> but self-closes with no <title>."""
    pattern = re.compile(
        r'<path d="M[-\d.]+ (-?[\d.]+)L[^"]*" fill="none" stroke="[^"]+" '
        r'stroke-width="2" stroke-linecap="round">'
        + re.escape(f"<title>{label}</title>") + r"</path>")
    m = pattern.search(svg_out)
    return float(m.group(1)) if m else None


panel_svg = make_history.panel("synthetic_param", META, PANEL_RELEASES)
panel_label = "Normal ordering, 2000: Synthetic θ < 50.0 (3σ) (1)"
panel_y = limit_marker_y(panel_svg, panel_label)
check("panel() draws the limit as its own unfilled, stroked arrow",
      panel_y is not None, f"label not found as an arrow in: {panel_svg[:200]}")
check("panel() keeps the limit's bound inside the plotted area",
      panel_y is not None and make_history.PAD_T <= panel_y <= make_history.H - make_history.PAD_B,
      f"y={panel_y}, plotted area is [{make_history.PAD_T}, {make_history.H - make_history.PAD_B}]")

compare_svg = make_history.compare_panel("synthetic_param", META, COMPARE_RELEASES)
compare_label = "Bari, 2000: Synthetic θ < 50.0 (3σ) (1)"
compare_y = limit_marker_y(compare_svg, compare_label)
check("compare_panel() draws the limit as its own unfilled, stroked arrow",
      compare_y is not None, f"label not found as an arrow in: {compare_svg[:200]}")
check("compare_panel() keeps the limit's bound inside the plotted area",
      compare_y is not None
      and make_history.PAD_T <= compare_y <= make_history.H - make_history.PAD_B,
      f"y={compare_y}, plotted area is [{make_history.PAD_T}, {make_history.H - make_history.PAD_B}]")

# 6b. integration: OFF_SCALE_COMPARE excludes a point from the axis-range
# calculation and from the connecting line, but never drops it — it is drawn
# clamped to the panel floor, in a hollow variant of the group's own shape,
# with its true value printed beside it and carried in its <title>. And a
# listed point that also carries a 3σ range is refused outright, because the
# floor-clamp has no drawing for a range and silently losing one is exactly
# the failure this section exists to catch.
#
# Exercised through compare_panel() with OFF_SCALE_COMPARE temporarily
# monkeypatched to a synthetic membership (saved and restored below), so
# these checks do not depend on which point history.yaml happens to mark
# off-scale today, the same way the synthetic releases above don't depend on
# what's really in the register.
OFFSCALE_RELEASES = [
    {"group": "bari", "year": 1999,
     "values": {"synthetic_param": {"any": {"best": 0.1}}}},          # off-scale
    {"group": "bari", "year": 2011,
     "values": {"synthetic_param": {"any": {"best": 5.1, "s3": [4.1, 6.1]}}}},
    {"group": "bari", "year": 2020,
     "values": {"synthetic_param": {"any": {"best": 5.3, "s3": [4.3, 6.3]}}}},
    {"group": "nufit", "year": 2010,
     "values": {"synthetic_param": {"any": {"best": 5.0, "s3": [4.0, 6.0]}}}},
    {"group": "valencia", "year": 2012,
     "values": {"synthetic_param": {"any": {"best": 5.2, "s3": [4.2, 6.2]}}}},
]
OFFSCALE_ENTRY = (1999, "bari", "synthetic_param")


def y_axis_ticks(svg_out: str) -> list[float]:
    """The four horizontal-guide labels, in the order drawn — index 0 is the
    axis floor, y0. Picked out from the year labels below the axis by
    text-anchor="end", which only the y-tick labels use (year labels use
    text-anchor="middle")."""
    return [float(v) for v in re.findall(r'text-anchor="end"[^>]*>(-?[\d.]+)<', svg_out)]


def offscale_marker_y(svg_out: str, title: str) -> float | None:
    """The y-coordinate of the hollow circle whose <title> is exactly title,
    parsed from the emitted markup rather than recomputed — the same
    approach as limit_marker_y above. fill="none" is baked into the pattern:
    if a future edit stops passing hollow=True for the clamped marker, this
    stops matching even though *a* circle with that title still exists."""
    pattern = re.compile(
        r'<circle cx="[-\d.]+" cy="(-?[\d.]+)" r="4.6" fill="none" stroke="[^"]+" '
        r'stroke-width="1.8">' + re.escape(f"<title>{title}</title>") + r"</circle>")
    m = pattern.search(svg_out)
    return float(m.group(1)) if m else None


_orig_off_scale = make_history.OFF_SCALE_COMPARE
make_history.OFF_SCALE_COMPARE = {OFFSCALE_ENTRY}
try:
    offscale_svg = make_history.compare_panel("synthetic_param", META, OFFSCALE_RELEASES)
finally:
    make_history.OFF_SCALE_COMPARE = _orig_off_scale

check("compare_panel() still draws a panel when a point is off-scale, not ''",
      offscale_svg != "")

ticks = y_axis_ticks(offscale_svg)
expected_y0 = make_history.nice_bounds(4.0, 6.3)[0]     # driven by the on-scale values alone
leaked_y0 = make_history.nice_bounds(0.1, 6.3)[0]       # what y0 would be if 0.1 leaked in
check("the off-scale point is excluded from the axis-range calculation",
      bool(ticks) and abs(ticks[0] - expected_y0) < 0.01 and abs(ticks[0] - leaked_y0) > 0.5,
      f"ticks={ticks}, expected y0~{expected_y0:.3g} (would be ~{leaked_y0:.3g} if it leaked in)")

line_m = re.search(
    r'<path d="([^"]+)" fill="none" stroke="var\(--grp-bari\)" stroke-width="2" '
    r'stroke-linejoin="round"', offscale_svg)
check("the off-scale point is excluded from the connecting line",
      line_m is not None and line_m.group(1).count("L") == 1,
      f"bari path d={line_m.group(1) if line_m else None!r} "
      "(expected one 'L', joining only the two on-scale points)")

offscale_title = ("Bari, 1999: Synthetic θ = 0.1 (1) — below this panel's range, "
                   "drawn at the floor, not to scale")
offscale_y = offscale_marker_y(offscale_svg, offscale_title)
expected_floor = make_history.H - make_history.PAD_B - make_history.OFF_SCALE_FLOOR_GAP
check("the off-scale point is still drawn — clamped to the floor, in a hollow marker",
      offscale_y is not None and abs(offscale_y - expected_floor) < 0.05,
      f"y={offscale_y}, expected floor {expected_floor}")

check("the true value is in the marker's <title>",
      offscale_title in offscale_svg)

numeral_y_text = f'{expected_floor + 3.5:.1f}'
check("the inline numeral beside the clamped marker matches its true value",
      f'y="{numeral_y_text}" font-size="9.5" fill="currentColor" opacity=".75">0.1<'
      in offscale_svg,
      offscale_svg[:400])


def offscale_with_range_raises() -> bool:
    """A listed OFF_SCALE_COMPARE point carrying an s3 range must be refused,
    not silently drawn without its range: the floor-clamp branch has no
    drawing for a range, so letting one through would lose it invisibly."""
    releases = [
        {"group": "bari", "year": 1999,
         "values": {"synthetic_param": {"any": {"best": 0.1, "s3": [0.05, 0.15]}}}},
        {"group": "nufit", "year": 2010,
         "values": {"synthetic_param": {"any": {"best": 5.0, "s3": [4.0, 6.0]}}}},
        {"group": "valencia", "year": 2012,
         "values": {"synthetic_param": {"any": {"best": 5.2, "s3": [4.2, 6.2]}}}},
    ]
    orig = make_history.OFF_SCALE_COMPARE
    make_history.OFF_SCALE_COMPARE = {OFFSCALE_ENTRY}
    try:
        make_history.compare_panel("synthetic_param", META, releases)
        return False
    except SystemExit:
        return True
    finally:
        make_history.OFF_SCALE_COMPARE = orig


check("an OFF_SCALE_COMPARE entry carrying a 3σ range is refused, not silently "
      "drawn without it",
      offscale_with_range_raises())

# 7. the cited table exists in the cited paper
sys.path.insert(0, str(ROOT / "tools" / "tests"))
import test_history_numbers as thn                      # noqa: E402


def table_cited(ident: str, text: str) -> bool:
    """Whether table identifier ident (e.g. "Table I") is really cited in
    text — not merely a character prefix of a longer identifier that happens
    to be printed there. Plain substring containment is unsound: "table i" is
    a prefix of "table ii", "table iii", "table iv", "table ix", so a record
    that wrongly cites Table I in a four-table paper would pass a substring
    check even though its value actually belongs to Table II. Requiring that
    nothing numeral-ish immediately follows the match closes that hole."""
    return bool(re.search(rf"{re.escape(ident)}\b(?![ivxlc0-9])", text, re.I))


# A low numeral must not be satisfied by a higher one that contains it as a
# character prefix — this is exactly the failure mode a plain `in` check
# missed: "Table I" would read as present in text that only ever prints
# "Table II". Regression coverage for that, isolated from any real PDF.
check("a low table numeral is not satisfied by a higher one containing it as a prefix",
      not table_cited("Table I", "the results are shown in Table II below"))
check("the identifier printed on its own is still found",
      table_cited("Table II", "the results are shown in Table II below"))
check("a numeral followed by punctuation or end of text is still found",
      table_cited("Table I", "as reported in Table I.")
      and table_cited("Table I", "as reported in Table I"))

missing = []
for rel in doc["releases"]:
    pdf = thn.pdf_for(rel)
    if pdf is None or not pdf.exists():
        continue                       # absent cache is the numbers test's problem
    text = thn.pdf_text(pdf)
    field = rel.get("table", "")
    ident = re.match(r"(Table\s+[IVXLC0-9]+)", field, re.I)
    if not ident:
        # Not every release quotes a table: bari 2008 is a focused analysis
        # whose one quotable number is given in the text as Eq. (3), not in
        # any table (see that release's own "note" field). This check is
        # specifically about verifying a *table* citation, so a field that
        # plainly names a different kind of source (an equation) is outside
        # its scope rather than a citation error — skip it rather than fail.
        # Anything else that fails to parse as "Table ..." is a real
        # candidate for a mis-set field and does fail.
        if re.match(r"eq\.?\s*\(", field, re.I):
            continue
        missing.append(f'{rel["group"]} {rel["year"]}: table field names no table')
        continue
    if not table_cited(ident.group(1), text):
        missing.append(f'{rel["group"]} {rel["year"]}: {ident.group(1)} not found in the PDF')

check("every cited table exists in the paper it is cited from", not missing,
      "; ".join(missing[:5]))

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — every recorded value is a measurement or a limit")
