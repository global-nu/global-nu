#!/usr/bin/env python3
"""The facts about the parameter register that published metadata states.

    ./.venv/bin/python3 tools/register_meta.py

Two consumers need the same facts and must not state them differently:
build.py, which writes the schema.org/Dataset block on history.html, and
tools/make_zenodo_deposit.py, which writes the Zenodo metadata. Both import
from here, so a new release changes one number in one place and every
published statement about the register follows.

The formal title lives here for the same reason. Once a DOI exists, the page
asserts that identifier for a dataset it names, and the Zenodo landing page
the DOI resolves to names the same record: two names for one identifier is a
disagreement a reader — or an indexer — can catch. Computed once, it cannot
happen.

The year span, the row count, the list of parameters and the last-changed
date are all read from data-exports/history.json — the very file the Dataset
says it distributes — rather than from the YAML register. Describing the file
that is actually published is the honest choice: the export canonicalises
NuFit's Dm2_3l and Valencia's |Dm2_31| into the single parameter Dm2, and it
is that column a downloader gets. Only the display label and unit of each
parameter come from the register's meta.parameters, which is the sole place
they are written.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "site-src" / "data" / "history.yaml"
EXPORT = ROOT / "data-exports" / "history.json"

TITLE = ("Published global-fit values of the three-flavour neutrino "
         "oscillation parameters, with provenance and convention "
         "conversions ({lo}–{hi})")


def _last_commit_date() -> str | None:
    """The export's last commit date, as YYYY-MM-DD, or None.

    The export, not the register that generates it. Nothing keeps the two in
    step: the 07:30 job runs build.py but never tools/make_history_data.py,
    so a release can be added to site-src/data/history.yaml and committed
    while data-exports/history.json still holds the previous row set. Dating
    the metadata from the register would then advertise a fresh dateModified
    over a temporalCoverage, a row count and a parameter list that are stale.
    The Dataset describes what is distributed, so the distributed file's own
    last change is the truthful answer, and every fact in register_facts()
    then comes from one file and cannot disagree with itself.

    Not the build date. The site is rebuilt every morning by the 07:30 job;
    a dateModified of "today" would rewrite history.html on every run and
    fill the daily refresh commit with a diff whose only content is a date.

    The export carries no date field of its own, and the two alternatives are
    worse: a hand-maintained field is a value somebody must remember to
    change, and a file mtime means nothing after a fresh clone. A commit date
    cannot rot and needs nobody to maintain it.

    None when git is unavailable or the file is untracked — the caller then
    omits the field rather than guessing one.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(EXPORT)],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    date = out.stdout.strip()
    # %cs is the committer date as YYYY-MM-DD. An empty result means the file
    # has no commits — a fresh working copy, or a rename not yet recorded.
    return date if len(date) == 10 and date[4] == date[7] == "-" else None


def register_facts() -> dict:
    """Title, year span, measured parameters, row count and last-changed date."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import history

    doc = history.load()
    meta = (doc.get("meta") or {}).get("parameters") or {}

    rows = json.loads(EXPORT.read_text(encoding="utf-8"))["rows"]
    if not rows:
        raise SystemExit(f"{EXPORT} holds no rows — run tools/make_history_data.py")

    years = (min(r["year"] for r in rows), max(r["year"] for r in rows))

    # Sorted for a stable build: an unordered set would reshuffle the JSON-LD
    # from run to run and the daily commit would carry a phantom diff.
    #
    # A parameter absent from meta.parameters has no "unit" key at all rather
    # than a "1". Falling back to "1" would publish "dimensionless" where the
    # truth is "we do not know" — the register's own rule, that a fact which
    # cannot be established is left out rather than guessed, applied to the
    # metadata that describes it. Consumers omit the field when it is absent.
    variables = []
    for name in sorted({r["parameter"] for r in rows}):
        info = meta.get(name) or {}
        v = {"name": name, "label": info.get("label", name)}
        if info.get("unit"):
            v["unit"] = info["unit"]
        variables.append(v)

    return {
        "title": TITLE.format(lo=years[0], hi=years[1]),
        "temporal_coverage": f"{years[0]}/{years[1]}",
        "years": years,
        "variables": variables,
        "date_modified": _last_commit_date(),
        "n_rows": len(rows),
    }


if __name__ == "__main__":
    facts = register_facts()
    print(json.dumps(facts, indent=2, ensure_ascii=False))
