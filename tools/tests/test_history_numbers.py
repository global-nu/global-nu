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

A limit's `upper` (or `lower`) is checked exactly like a measurement's `best`
— same forms(), same PDF search — and, when the record carries a
`source_quote`, that sentence is independently checked to occur in the same
paper's extracted text, AND to actually mention the level the record claims
(a quote that occurs in the paper but never says "3σ" does not support a
record claiming `level: 3sigma`). Until this was added, a limit's bound, its
level and its source_quote were verified by nothing at all: the register's
first real limit (NuFit 2004's sin²θ₁₃, Table 1) was trust-only, one reviewer
reading page 20 by hand.

The level-mention check is deliberately narrow: it does not prove the level
is the *right* one for that value — nothing mechanical can tell "3σ" the
column from "3σ" the neighbouring column in the same sentence — only that the
quote is not silent about it. A caption quoting several levels at once (as
NuFit 2004's does: "2σ, 3σ, and 4σ") will support any of the levels it lists;
it will not support one it never mentions, which is the failure this closes.

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
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

DATA = ROOT / "site-src" / "data" / "history.yaml"
CACHE = ROOT / "var" / "history-sources"

UNIT_EXP = {"1e-1": -1, "1e-2": -2, "1e-3": -3, "1e-5": -5, "1": 0}


def pdf_for(rel: dict) -> Path:
    """The cached-PDF path a release's own group/year/arxiv fields point to."""
    slug = f"{rel['group']}-{rel['year']}-{rel['arxiv'].replace('/', '_')}"
    return CACHE / f"{slug}.pdf"


def pdf_text(path: Path) -> str:
    """Full text with the spaces PDF extraction sprinkles inside numbers
    removed: "0. 016" and "2 .47" are the same number as "0.016" and "2.47"."""
    raw = "".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    raw = re.sub(r"(?<=[.,])\s+(?=\d)", "", raw)
    raw = re.sub(r"(?<=\d)\s+(?=[.,]\d)", "", raw)
    # Papers set the minus sign as U+2212 (and sometimes an en dash); the
    # values in history.yaml carry a plain hyphen.
    raw = raw.replace("\u2212", "-")
    # …and the sign is often separated from its digits by the line break the
    # extractor turns into a space: "-2.413" is printed as "- 2.413".
    return re.sub(r"-\s+(?=\d)", "-", raw)


# Typographic ligatures a PDF font substitutes for a plain letter sequence:
# "fit" prints as "ﬁt", "flavour" as "ﬂavour". Word-search via forms() never
# meets these (it looks for digits), but a source_quote is prose and does.
LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
             "ﬃ": "ffi", "ﬄ": "ffl"}


def normalize_for_quote(s: str) -> str:
    """Fold a string down to a form tolerant of what PDF extraction does to a
    quoted sentence: ligatures expanded to their letters, then every run of
    whitespace removed entirely. Whitespace is not just collapsed to one
    space because extraction does not merely widen it — it inserts space
    inside words that have none in the paper and drops space that is there,
    unpredictably around symbols like sigma ("2σ," in the source prints as
    "2 σ ," in nufit-2004's extracted text). Nothing else is normalised:
    wording, punctuation and digits still have to match exactly, so a quote
    that misremembers the paper still fails this check."""
    for lig, plain in LIGATURES.items():
        s = s.replace(lig, plain)
    return re.sub(r"\s+", "", s)


def level_forms(level: str) -> list[str]:
    """Acceptable renderings of a confidence level inside a quoted sentence.

    A "Nsigma" level accepts three spellings: the sigma glyph the way
    tools.history.LEVEL_TEXT renders it ("3σ"), and the two plain-ASCII
    spellings a paper's own typesetting might use instead of the glyph
    ("3 sigma", "3-sigma") — a paper sets its own captions, not ours, and
    plenty of journals avoid non-ASCII symbols in running text. Matched
    case-insensitively by the caller, so "Sigma" or "SIGMA" also count.

    A "NN%CL" level accepts only tools.history.LEVEL_TEXT's own rendering
    ("90% CL"), which is already plain ASCII — there is no glyph to spell out
    an alternative for."""
    text = history.LEVEL_TEXT.get(level, level)
    m = re.match(r"(\d+)sigma$", level)
    if not m:
        return [text]
    n = m.group(1)
    return [text, f"{n} sigma", f"{n}-sigma"]


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
        pdf = pdf_for(rel)
        slug = pdf.stem
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
                # A limit's bound is checked the same way as a measurement's
                # best fit: same forms(), same PDF search. "upper" and
                # "lower" are mutually exclusive (history.kind_of / the
                # limit's own shape), so at most one of these ever fires.
                for key in ("upper", "lower"):
                    if key in entry:
                        items.append((key, entry[key]))
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

                # A limit's source_quote, when the record carries one, is a
                # sentence from the paper naming what the bound's level is —
                # checked here rather than trusted, the same principle as
                # every number above.
                quote = entry.get("source_quote")
                if quote:
                    total += 1
                    if normalize_for_quote(quote) in normalize_for_quote(text):
                        found += 1
                        n_ok += 1
                    else:
                        n_bad += 1
                        problems.append(
                            f"{slug}  {pname} {ordering} source_quote={quote!r} "
                            "not found in the source (after ligature and "
                            "whitespace normalisation)")

                    # The quote occurring in the paper proves the SENTENCE is
                    # real; it does not prove it supports THIS record's
                    # level. A record claiming level: 2sigma whose quote only
                    # ever says "3σ" would pass every check above — this one
                    # exists to catch exactly that.
                    level = entry.get("level")
                    if level:
                        total += 1
                        wanted = level_forms(level)
                        quote_l = quote.lower()
                        if any(f.lower() in quote_l for f in wanted):
                            found += 1
                            n_ok += 1
                        else:
                            n_bad += 1
                            problems.append(
                                f"{slug}  {pname} {ordering} level={level!r} not "
                                f"supported by source_quote={quote!r} "
                                f"(looked for {' or '.join(wanted)})")
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
