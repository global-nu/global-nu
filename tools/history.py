#!/usr/bin/env python3
"""The parameter history, loaded once and validated once.

The page generator, the data exporter and the tests all read history.yaml
through here, so none of them can disagree about what a record means.

A recorded value takes one of two shapes and never both:

    {best: 2.23, s1: [...], s3: [...]}     a measurement
    {upper: 5.0, level: "3sigma"}          a limit

The level is not decoration. Older papers bound parameters at whatever
confidence suited them, and a bound printed without its level cannot be
compared with another bound — so a limit that does not name one is refused
here rather than drawn misleadingly on a panel.

A limit is an *upper* bound: the page has one limit marker, a downward arrow,
and a `lower` bound is refused by validate_value() until there is a marker
that can draw one. Recording one today would pass validation and then crash
the generator, which reads entry["upper"] at every draw site.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "history.yaml"

# Extended when a paper demands it, not decided in advance.
LEVELS: tuple[str, ...] = ("3sigma", "2sigma", "90%CL", "95%CL")

LEVEL_TEXT = {"3sigma": "3σ", "2sigma": "2σ", "90%CL": "90% CL", "95%CL": "95% CL"}

# A conversion between conventions is a subtraction of two decimal fractions,
# and it leaves IEEE artefacts far below anything a paper ever printed:
# 2.4355 comes out of to_our_Dm2() as 2.4354999999999998. Every converted
# number is rounded to this many decimal places before it is written to an
# export or printed on a label. Ten places is orders of magnitude finer than
# the four or five significant digits the papers publish, so the rounding can
# only remove arithmetic noise — it can never touch a digit a source printed.
VALUE_DP = 10


def round_value(v: float) -> float:
    """A value with the arithmetic noise of a convention conversion removed."""
    return round(v, VALUE_DP)


def value_text(v: float) -> str:
    """A recorded value as text, at the precision the register records it in.

    Never formatted with :g or :.4g. Those round to six (or four) significant
    figures and strip trailing zeros, so sin²θ₁₂ = 0.30 — recorded as 3.0 in
    units of 1e-1, because that is how the paper printed it — would render as
    "3", claiming one significant digit where the source gave two. This is the
    same rule limit_label() follows for a bound: the printed precision is
    whatever history.yaml spells, and nothing here may narrow it.

    round_value() first, so a value that reached this function through a
    convention conversion does not carry its arithmetic noise onto a label.
    """
    return str(round_value(v))


def kind_of(entry: dict) -> str:
    """Classify entry: "measurement", "limit", or "" when it is neither
    (including when it is both — the caller distinguishes those cases)."""
    measured = "best" in entry
    bounded = "upper" in entry or "lower" in entry
    if measured and not bounded:
        return "measurement"
    if bounded and not measured:
        return "limit"
    return ""


def validate_value(pname: str, ordering: str, entry: dict) -> None:
    """Raise SystemExit naming the offender, or return quietly."""
    where = f"{pname}/{ordering}"
    kind = kind_of(entry)
    if kind == "":
        measured = "best" in entry
        bounded = "upper" in entry or "lower" in entry
        if measured and bounded:
            sys.exit(f"{DATA.name}: {where} is both a measurement and a limit: {entry!r}")
        sys.exit(f"{DATA.name}: {where} is neither a measurement nor a limit: {entry!r}")
    if kind == "limit":
        # Only an upper bound can be drawn today: marker() has one limit
        # shape, "limit-upper", and both draw sites read entry["upper"]. A
        # record carrying "lower" would validate here, reach the generator
        # and die there with a KeyError — or worse, be drawn as if it bounded
        # the parameter from above. Refused until there is a limit-lower
        # marker to draw it with.
        if "lower" in entry and "upper" in entry:
            sys.exit(f"{DATA.name}: {where} carries both an upper and a lower bound, "
                     f"which is a range, not a limit: {entry!r}")
        if "lower" in entry:
            sys.exit(f"{DATA.name}: {where} is a lower limit, which this site cannot "
                     "yet draw: marker() has only a limit-upper shape and both draw "
                     "sites read entry['upper']. Add a limit-lower marker to "
                     "tools/make_history.py (and the draw sites that place it) before "
                     f"recording one: {entry!r}")
        level = entry.get("level")
        if not level:
            sys.exit(f"{DATA.name}: {where} is a limit with no confidence level")
        if level not in LEVELS:
            sys.exit(f"{DATA.name}: {where} has level {level!r}, "
                     f"which is not one of {', '.join(LEVELS)}")


def level_text(entry: dict) -> str:
    """A limit's confidence level as a reader sees it, the one rendering used
    both in the marker's label and in the text printed beside it — the two
    cannot drift apart because there is only one of them."""
    return LEVEL_TEXT.get(entry.get("level", ""), entry.get("level", ""))


def limit_label(entry: dict) -> str:
    """What a reader sees on the marker: the bound and the level it holds at.

    The bound is interpolated as written, not formatted with :g — :g rounds
    to 6 significant figures and would silently drop a paper's digits, and it
    strips trailing zeros, so the printed precision follows however the value
    is spelled in history.yaml (5 vs. 5.0 render differently on purpose)."""
    level = level_text(entry)
    if "upper" in entry:
        return f"< {entry['upper']} ({level})"
    return f"> {entry['lower']} ({level})"


def load() -> dict:
    """The whole document, with every value validated."""
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    if not (doc or {}).get("releases"):
        sys.exit(f"{DATA} holds no releases")
    for rel in doc["releases"]:
        for pname, byo in (rel.get("values") or {}).items():
            for ordering, entry in byo.items():
                validate_value(pname, ordering, entry)
    return doc
