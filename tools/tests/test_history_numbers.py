#!/usr/bin/env python3
"""Check every number in history.yaml against the paper it cites.

Same principle as test_release_numbers.py, applied to the whole timeline: the
values are not compared against a copy kept in this file, they are looked for
in the text of the cached PDF of the paper each entry names. A number that
cannot be found in its own source is either a transcription error or a value
that came from somewhere else — both are failures.

Two accepted forms per value, because papers differ in how they normalise a
row: the number as recorded (matching a table printed in units of 1e-1, 1e-2,
…) and the same number scaled by that unit (matching a table printed in
absolute values). Nothing else is accepted.

    ./setup-venv.sh && ./.venv/bin/python3 tools/tests/test_history_numbers.py

Needs the cached sources: python3 tools/fetch_history_sources.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "site-src" / "data" / "history.yaml"
CACHE = ROOT / "var" / "history-sources"

UNIT_EXP = {"1e-1": -1, "1e-2": -2, "1e-3": -3, "1e-5": -5, "1": 0}


def pdf_text(path: Path) -> str:
    """Full text with the spaces PDF extraction sprinkles inside numbers
    removed: "0. 016" and "2 .47" are the same number as "0.016" and "2.47"."""
    raw = "".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    raw = re.sub(r"(?<=\d)\s+(?=[.,]\d)", "", raw)
    raw = re.sub(r"(?<=[.,])\s+(?=\d)", "", raw)
    # Papers set the minus sign as U+2212 (and sometimes an en dash); the
    # values in history.yaml carry a plain hyphen.
    raw = raw.replace("\u2212", "-")
    # …and the sign is often separated from its digits by the line break the
    # extractor turns into a space: "-2.413" is printed as "- 2.413".
    return re.sub(r"-\s+(?=\d)", "-", raw)


def forms(value: float, unit: str) -> list[str]:
    """How this value may legitimately appear in the paper."""
    out = {f"{value:g}"}
    exp = UNIT_EXP.get(unit)
    if exp:
        scaled = value * (10 ** exp)
        # keep the same number of significant digits as recorded
        digits = len(f"{value:g}".split(".")[-1]) if "." in f"{value:g}" else 0
        out.add(f"{scaled:.{digits - exp}f}")
    return sorted(out)


def main() -> None:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    units = {k: v["unit"] for k, v in doc["meta"]["parameters"].items()}
    units.update({k: v["unit"] for k, v in doc["meta"].get("reported", {}).items()})

    total = found = skipped = 0
    problems: list[str] = []

    for rel in doc["releases"]:
        slug = f"{rel['group']}-{rel['year']}-{rel['arxiv'].replace('/', '_')}"
        pdf = CACHE / f"{slug}.pdf"
        if not pdf.exists():
            problems.append(f"{slug}: source PDF not cached — run tools/fetch_history_sources.py")
            continue
        text = pdf_text(pdf)

        n_ok = n_bad = 0
        for pname, by_ordering in (rel.get("values") or {}).items():
            unit = units[pname]
            for ordering, entry in by_ordering.items():
                items: list[tuple[str, float]] = []
                if "best" in entry:
                    items.append(("best", entry["best"]))
                for key in ("s1", "s2", "s3"):
                    for v in entry.get(key, []) or []:
                        items.append((key, v))
                for key, v in items:
                    # A value the paper states as central ± error is computed,
                    # not printed: the entry declares it and it is not searched.
                    if rel.get("derived") and key != "best":
                        skipped += 1
                        continue
                    total += 1
                    if any(f in text for f in forms(v, unit)):
                        found += 1
                        n_ok += 1
                    else:
                        n_bad += 1
                        problems.append(
                            f"{slug}  {pname} {ordering} {key}={v} "
                            f"(looked for {' or '.join(forms(v, unit))})")
        flag = "" if not n_bad else f"  <-- {n_bad} NOT FOUND"
        print(f"  {slug:<34} {n_ok:>3} values verified against {rel['table']}{flag}")

    print()
    if problems:
        print("  ! values not found in their own source:")
        for p in problems:
            print("      " + p)
        print(f"\n{found}/{total} verified, {len(problems)} problem(s)")
        sys.exit(1)
    print(f"all {found} values verified against the cited tables"
          + (f" ({skipped} declared as derived, not searched)" if skipped else ""))


if __name__ == "__main__":
    main()
