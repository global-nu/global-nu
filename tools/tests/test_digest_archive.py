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
# Deep-copied: dict(store) shares the inner lists, so with a shallow baseline
# `store == before` would hold even if merge had appended the bad record to a
# day in place. The copy is what makes this check test what it names.
import copy                                              # noqa: E402

before = copy.deepcopy(store)
store = archive.merge(store, [{"id": "arxiv:9", "title": "No date"}])
check("a record with no date is dropped rather than filed under today",
      store == before,
      "guessing a date would put a paper in a day it was not announced in")

# --- a date that is not an ISO day is refused too -------------------------
# A non-empty but unparseable date used to become a key in the store, which is
# persisted. From then on _human_day raised on every run, _safe swallowed it,
# update_index never ran, and the archive was dead for good with one WARNING a
# day as the only sign. A dropped record costs one paper; a bad key costs all
# of it. "20260803" and "2026-W01-1" parse as dates but slice to the months
# "2026080" and "2026-W0", so the shape is checked, not only the parse.
for bad in ["2026-8-3", "13 Aug 2026", "not a date", "20260803",
            "2026-W01-1", "2026-02-31"]:
    poisoned = archive.merge(store, [rec("arxiv:bad", bad)])
    check(f"a record dated {bad!r} is dropped, not made a key",
          poisoned == store,
          f"keys now {sorted(poisoned)} — one bad key kills the archive "
          f"permanently and silently")

check("a well-formed date is still accepted",
      "2026-08-20" in archive.merge(store, [rec("arxiv:ok", "2026-08-20")]),
      "the validation must not reject the dates the digest actually supplies")

# --- days keep a stable order inside themselves --------------------------
many = archive.merge({}, [rec("arxiv:b", "2026-08-12"), rec("arxiv:a", "2026-08-12")])
again = archive.merge({}, [rec("arxiv:a", "2026-08-12"), rec("arxiv:b", "2026-08-12")])
check("a day's records are ordered deterministically",
      [r["id"] for r in many["2026-08-12"]] == [r["id"] for r in again["2026-08-12"]],
      "an unstable order would rewrite the archive pages every single run")

# --- the pages ------------------------------------------------------------
import re                                                # noqa: E402

day_md = archive.day_markdown("2026-08-12",
                              [rec("arxiv:1", "2026-08-12", "First"),
                               rec("arxiv:2", "2026-08-12", "Second")])

check("the day page declares its own url",
      "url: digest/2026-08-12.html" in day_md, day_md[:200])
check("the day page's title names the day in words",
      "12 August 2026" in day_md, day_md[:200])
check("the day page lists both papers",
      "First" in day_md and "Second" in day_md)
check("the day page says it was generated by a script, with no model",
      "No model is involved" in day_md,
      "the main digest says this; an archive of it must be able to say it too")
check("the day page carries its own count",
      "2 preprints" in day_md, day_md[:400])

month_md = archive.month_markdown(
    "2026-08",
    {"2026-08-13": [rec("arxiv:3", "2026-08-13", "Later")],
     "2026-08-12": [rec("arxiv:1", "2026-08-12", "Earlier")]})

check("the month page declares its own url",
      "url: digest/2026-08.html" in month_md)
check("the month page names the month",
      "August 2026" in month_md, month_md[:200])
check("the month page keeps the days visible as sections",
      "13 August" in month_md and "12 August" in month_md,
      "a flat month loses which day a paper belongs to")
check("the month page runs most recent first",
      month_md.index("13 August") < month_md.index("12 August"))
check("the month page contains every paper of its days",
      "Later" in month_md and "Earlier" in month_md)

# A month page must never reach outside its own month: a paper filed in
# September appearing on the August page would be a silent factual error.
check("month_markdown is given only its own days",
      "2026-09" not in month_md)

# --- the pages carry no wall clock ----------------------------------------
# write_pages regenerates every archive page on every run, including a quiet
# Sunday that fetched nothing. A timestamp in the page would therefore give
# every archived page different bytes on every run, in both the source tree
# and the built site, and the daily job commits both — after a year that is
# ~250 day pages plus 12 month pages of noise in every morning's commit. It
# would also be meaningless: a page about 8 August is fixed by its day, not by
# when the file was last written.
for label, md in (("day", day_md), ("month", month_md)):
    check(f"the {label} page carries no 'last update' timestamp",
          "Last successful update" not in md,
          "every archive page is rewritten on every run; a stamp makes each "
          "one differ every time and the daily commit becomes noise")

check("the month page still says no model is involved",
      "No model is involved" in month_md,
      "dropping the stamp must not drop the sentence the banner exists for")

# The claim above is only worth anything if it is checked end to end.
_again = archive.day_markdown("2026-08-12",
                              [rec("arxiv:1", "2026-08-12", "First"),
                               rec("arxiv:2", "2026-08-12", "Second")])
check("the same day and records render byte-identically",
      _again == day_md,
      "two runs on an unchanged store must produce an empty commit")

# --- the index block on the digest page -----------------------------------
block = archive.index_block({
    f"2026-08-{d:02d}": [rec(f"arxiv:{d}", f"2026-08-{d:02d}")]
    for d in range(1, 15)})

check("the index lists the ten most recent days by name",
      block.count('href="digest/2026-08-') >= 10, block[:300])
check("the newest day comes first",
      block.index("2026-08-14") < block.index("2026-08-13"))
check("older days are reached through their month, not listed one by one",
      'href="digest/2026-08.html"' in block,
      "fourteen days with no month link would grow without bound")
check("each listed day shows how many papers it holds",
      "1 paper" in block, block[:400])

# --- below the ten-day boundary, the month must still be linked ------------
# write_pages writes a month page for every month in the store, always. If the
# index only names a month once there are more than RECENT_DAYS days, then in
# the archive's first ten days the month page exists on disk and in the
# sitemap while no page on the site links to it: a search engine can reach it
# and a reader cannot. Four days is the ordinary state of a young archive.
few = {f"2026-08-{d:02d}": [rec(f"arxiv:{d}", f"2026-08-{d:02d}")]
       for d in range(1, 5)}
small = archive.index_block(few)

check("a month with fewer than ten archived days is still linked",
      'href="digest/2026-08.html"' in small,
      "write_pages writes site/digest/2026-08.html unconditionally; with no "
      "link to it the page is reachable only from the sitemap\n"
      f"         {small}")
check("and the month row is a row of its own, not a day's name",
      "All of August 2026" in small, small)

# Reachable, not merely present: the href the index emits has to be a page
# write_pages really writes. Checked against write_pages' own output rather
# than a literal, so the two cannot drift apart.
import tempfile                                          # noqa: E402

_tmp = Path(tempfile.mkdtemp(prefix="gnu-test-archive-index-"))
_real_dir = archive.CONTENT_DIR
archive.CONTENT_DIR = _tmp
try:
    written = archive.write_pages(few)
finally:
    archive.CONTENT_DIR = _real_dir

check("the month the index links to is a page write_pages wrote",
      "digest/2026-08.html" in written and (_tmp / "2026-08.md").exists(),
      str(written))
check("naming the months does not change how many days are named",
      small.count('href="digest/2026-08-') == 4,
      "the ten governs which days are named, nothing else\n"
      f"         {small}")

# --- an empty store must not empty the index ------------------------------
# var/ is gitignored, so var/news/archive.json is never committed: a fresh
# clone or a deleted var/ gives an empty store while every archived page is
# still in git and still on the site. Writing the empty index there would
# commit a digest page that links to none of them.
_idx_dir = Path(tempfile.mkdtemp(prefix="gnu-test-archive-empty-"))
_real_md = archive.DIGEST_MD
archive.DIGEST_MD = _idx_dir / "digest.md"
_populated = (f"intro\n\n{archive.BEGIN}\n"
              '<ul class="archive">\n  <li>a real row</li>\n</ul>\n'
              f"{archive.END}\n")
archive.DIGEST_MD.write_text(_populated, encoding="utf-8")
try:
    changed = archive.update_index({})
    after = archive.DIGEST_MD.read_text(encoding="utf-8")
finally:
    archive.DIGEST_MD = _real_md

check("an empty store reports no change", changed is False, repr(changed))
check("an empty store leaves the existing index untouched",
      after == _populated,
      "a lost var/ would otherwise commit an index linking to no archived "
      "page at all, while every one of them is still in git\n"
      f"         {after}")

# --- a run that changes nothing writes nothing ----------------------------
_store_dir = Path(tempfile.mkdtemp(prefix="gnu-test-archive-store-"))
_real_store = archive.STORE
archive.STORE = _store_dir / "archive.json"
try:
    first = archive.save(few)
    second = archive.save(few)
finally:
    archive.STORE = _real_store

check("saving a new store writes it", first is True, repr(first))
check("saving an unchanged store writes nothing", second is False,
      "save's docstring promises this; an unconditional write breaks it")

# --- the daily job must be able to commit what it just wrote --------------
from tools.news import pipeline                          # noqa: E402

check("the publish list covers the archive's source pages",
      "site-src/content/digest" in pipeline.PUBLISHED_BY_JOB,
      "a page the job writes but cannot commit leaves the tree dirty, and the "
      "next git pull --rebase refuses — the site then stops updating silently")
check("and their built output",
      "site/digest" in pipeline.PUBLISHED_BY_JOB,
      str(pipeline.PUBLISHED_BY_JOB))

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the store files each paper once, by its own date")
