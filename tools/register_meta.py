#!/usr/bin/env python3
"""The facts about the parameter register that published metadata states.

    ./.venv/bin/python3 tools/register_meta.py

Two consumers need the same three facts and must not compute them
differently: build.py, which writes the schema.org/Dataset block on
history.html, and tools/make_zenodo_deposit.py, which writes the Zenodo
metadata. Both import from here, so a new release changes one number in one
place and every published statement about the register follows.

The year span and the parameter list are read from data-exports/history.json
— the very file the Dataset says it distributes — rather than from the YAML.
Describing the file that is actually published is the honest choice: the
export canonicalises NuFit's Dm2_3l and Valencia's |Dm2_31| into the single
parameter Dm2, and it is that column a downloader gets.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "site-src" / "data" / "history.yaml"
EXPORT = ROOT / "data-exports" / "history.json"


def _last_commit_date() -> str | None:
    """The register's last commit date, as YYYY-MM-DD, or None.

    Not the build date. The site is rebuilt every morning by the 07:30 job;
    a dateModified of "today" would rewrite history.html on every run and
    fill the daily refresh commit with a diff whose only content is a date.

    The register carries no date field of its own, and the two alternatives
    are worse: a hand-maintained meta.updated: is a value somebody must
    remember to change, and a file mtime means nothing after a fresh clone.
    A commit date cannot rot and needs nobody to maintain it.

    None when git is unavailable or the file is untracked — the caller then
    omits the field rather than guessing one.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(REGISTER)],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    date = out.stdout.strip()
    # %cs is the committer date as YYYY-MM-DD. An empty result means the file
    # has no commits — a fresh working copy, or a rename not yet recorded.
    return date if len(date) == 10 and date[4] == date[7] == "-" else None


def register_facts() -> dict:
    """Year span, measured parameters, row count and last-changed date."""
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
    variables = [
        {"name": name,
         "label": (meta.get(name) or {}).get("label", name),
         "unit": (meta.get(name) or {}).get("unit", "1")}
        for name in sorted({r["parameter"] for r in rows})
    ]

    return {
        "temporal_coverage": f"{years[0]}/{years[1]}",
        "years": years,
        "variables": variables,
        "date_modified": _last_commit_date(),
        "n_rows": len(rows),
    }


if __name__ == "__main__":
    facts = register_facts()
    print(json.dumps(facts, indent=2, ensure_ascii=False))
