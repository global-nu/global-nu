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
