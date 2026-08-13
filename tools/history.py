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
        level = entry.get("level")
        if not level:
            sys.exit(f"{DATA.name}: {where} is a limit with no confidence level")
        if level not in LEVELS:
            sys.exit(f"{DATA.name}: {where} has level {level!r}, "
                     f"which is not one of {', '.join(LEVELS)}")


def limit_label(entry: dict) -> str:
    """What a reader sees on the marker: the bound and the level it holds at.

    The bound is interpolated as written, not formatted with :g — :g rounds
    to 6 significant figures and would silently drop a paper's digits, and it
    strips trailing zeros, so the printed precision follows however the value
    is spelled in history.yaml (5 vs. 5.0 render differently on purpose)."""
    level = LEVEL_TEXT.get(entry.get("level", ""), entry.get("level", ""))
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
