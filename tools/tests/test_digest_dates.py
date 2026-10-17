#!/usr/bin/env python3
"""The digest names each date for what it is.

    ./.venv/bin/python3 tools/tests/test_digest_dates.py

A digest headed "today" that printed one undifferentiated date per paper
read as if it listed old papers: the date was the first submission (API
route) or the announcement (RSS route), and nothing said which. Records now
carry `submitted`, `updated` and `announced` separately; records written
before that carry only `date`, read through `route`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.news import render  # noqa: E402

cases = [
    ({"date": "2026-10-09", "extra": {"route": "api", "submitted": "2026-10-09", "updated": "2026-10-14"}},
     "first submitted 9 Oct 2026 · updated 14 Oct 2026"),
    ({"date": "2026-10-16", "extra": {"route": "rss", "announced": "2026-10-16"}},
     "announced 16 Oct 2026"),
    ({"date": "2026-10-10", "extra": {"route": "api"}}, "first submitted 10 Oct 2026"),   # legacy record
    ({"date": "2026-10-16", "extra": {"route": "rss"}}, "announced 16 Oct 2026"),          # legacy record
]
bad = []
for rec, want in cases:
    got = render._record_dates(rec)
    print(f"  {'ok  ' if got == want else 'FAIL'} {want!r}")
    if got != want:
        bad.append(f"{rec} -> {got!r}")

api = [c[0] for c in cases if c[0]["extra"]["route"] == "api"]
line = render._digest_window(api, via_rss=False)
ok = "first submitted 9 Oct 2026 – 10 Oct 2026" in line and "announced" not in line.split(".")[0]
print(f"  {'ok  ' if ok else 'FAIL'} API edition line states a submission range, not an announcement")
if not ok:
    bad.append(line)
rss = [c[0] for c in cases if c[0]["extra"]["route"] == "rss"]
ok = "arXiv announcement of 16 Oct 2026" in render._digest_window(rss, via_rss=True)
print(f"  {'ok  ' if ok else 'FAIL'} RSS edition line states the announcement day")
if not ok:
    bad.append("rss line")
if bad:
    sys.exit(1)
print("all digest-date checks pass")
