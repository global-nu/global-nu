#!/usr/bin/env python3
"""The digest archive files each paper once, under the day it was announced.

    ./.venv/bin/python3 tools/tests/test_digest_archive.py

The digest shows the best-scoring preprints of the last seven days, not of
today: 92 of 100 identifiers in the record cache appear on more than one day.
So an archive keyed on the run date would repeat almost everything, seven
times over. It is keyed on each record's own `date` instead, and merged by
arXiv identifier, which makes re-running a day a no-op and makes a late run
harmless — a paper announced on the 12th that first enters the window on the
14th still lands under the 12th.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import archive                           # noqa: E402

checks = 0
problems = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
        return
    problems.append(label)
    print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def rec(ident: str, date: str, title: str = "A paper") -> dict:
    return {"id": ident, "date": date, "title": title,
            "url": f"https://arxiv.org/abs/{ident.split(':')[1]}",
            "links": {"arxiv": f"https://arxiv.org/abs/{ident.split(':')[1]}"},
            "authors": "A. Author", "summary": "…",
            "extra": {"categories": ["hep-ph"]}}


# --- filed by the record's own date, not by when it was seen -------------
store = archive.merge({}, [rec("arxiv:1", "2026-08-12"),
                           rec("arxiv:2", "2026-08-13")])
check("each paper lands under its own announcement date",
      sorted(store) == ["2026-08-12", "2026-08-13"], str(sorted(store)))
check("and one paper per day here", all(len(v) == 1 for v in store.values()))

# --- the seven-day window must not multiply anything ---------------------
for _ in range(3):
    store = archive.merge(store, [rec("arxiv:1", "2026-08-12")])
check("a paper seen on three later runs is still stored once",
      len(store["2026-08-12"]) == 1,
      f"{len(store['2026-08-12'])} copies — the window is leaking into the store")

# --- an improved record replaces the older copy --------------------------
store = archive.merge(store, [rec("arxiv:1", "2026-08-12", title="A better title")])
check("a record whose fields improved is updated in place",
      store["2026-08-12"][0]["title"] == "A better title",
      store["2026-08-12"][0]["title"])
check("and still only once", len(store["2026-08-12"]) == 1)

# --- a record with no usable date is refused, not guessed ----------------
before = dict(store)
store = archive.merge(store, [{"id": "arxiv:9", "title": "No date"}])
check("a record with no date is dropped rather than filed under today",
      store == before,
      "guessing a date would put a paper in a day it was not announced in")

# --- days keep a stable order inside themselves --------------------------
many = archive.merge({}, [rec("arxiv:b", "2026-08-12"), rec("arxiv:a", "2026-08-12")])
again = archive.merge({}, [rec("arxiv:a", "2026-08-12"), rec("arxiv:b", "2026-08-12")])
check("a day's records are ordered deterministically",
      [r["id"] for r in many["2026-08-12"]] == [r["id"] for r in again["2026-08-12"]],
      "an unstable order would rewrite the archive pages every single run")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the store files each paper once, by its own date")
