#!/usr/bin/env python3
"""The experiment list, loaded once and ordered once.

Both the world map and the tiles on the Resources page are drawn from this
module, so the two cannot name different experiments or put them in different
orders. Before it existed the list lived twice — in experiments.yaml and as
hand-written HTML — and every addition cost two edits, which is why the list
stayed at thirteen entries with Daya Bay absent.

The ordering is a claim, not a preference: within a role, experiments are
ranked by their weight in the current global fit, and `rank` records where
each one sits. The claim is written down so it can be argued with.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "experiments.yaml"

# Display order of the groups, and the heading each one gets.
ROLES: list[tuple[str, str]] = [
    ("theta13",     "Reactor · θ₁₃"),
    ("theta12_dm2", "Reactor · θ₁₂ and δm²"),
    ("solar",       "Solar neutrinos"),
    ("lbl",         "Long-baseline accelerator"),
    ("atmospheric", "Atmospheric neutrinos"),
    ("sterile",     "Short baseline and sterile searches"),
    ("mass",        "Absolute mass"),
    ("0nubb",       "Neutrinoless double-beta decay"),
]

STATUSES: tuple[str, ...] = ("running", "completed", "construction", "proposed")

# How a status is written on the page. Absent status prints nothing at all,
# which is the honest outcome when it could not be established.
STATUS_LABEL = {
    "running":      "taking data",
    "completed":    "completed",
    "construction": "under construction",
    "proposed":     "proposed",
}


def load() -> list[dict]:
    """Every record in the file. Raises SystemExit on a malformed file."""
    raw = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    records = (raw or {}).get("experiments")
    if not records:
        sys.exit(f"{DATA} holds no experiments")
    for r in records:
        if not r.get("name"):
            sys.exit(f"{DATA}: a record has no name")
    return records


def ordered() -> list[tuple[str, str, list[dict]]]:
    """(role, heading, records) — grouped in ROLES order, ranked within each."""
    out = []
    records = load()
    for key, heading in ROLES:
        group = sorted((r for r in records if r.get("role") == key),
                       key=lambda r: (r.get("rank", 10_000), r["name"]))
        if group:
            out.append((key, heading, group))
    return out


def label(record: dict) -> str:
    """The one line printed under a name, on the tile and in the map card."""
    bits = [b for b in (record.get("place") or
                        f'{record.get("city", "")}, {record.get("country", "")}',
                        record.get("note"),
                        STATUS_LABEL.get(record.get("status", ""))) if b]
    return " · ".join(bits)
