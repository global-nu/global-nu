#!/usr/bin/env python3
"""fetch_arxiv's second route: the per-category RSS feeds.

    ./.venv/bin/python3 tools/tests/test_arxiv_rss.py

Why there are two routes at all: arXiv's /api/query answered HTTP 429 "Rate
exceeded" on five days between August and September 2026, three of them
consecutive, and the digest page sat on 12 September's preprints for two days
with nothing but its timestamp to say why. The RSS feeds live on a different
host with a different limiter and answered normally on every one of those
days.

They are not the same question, though, and most of what is checked here is
the code refusing to pretend they are:

  * a "replace" announcement is a new VERSION of an old paper. Listing it as
    today's preprint is the one thing a digest must never do, and it is what
    a naive reading of the feed produces — replacements outnumber genuinely
    new papers in every feed sampled (12 replace against 7 new in hep-ex on
    the day this was written);
  * the feed writes its own metadata into the abstract ("arXiv:2609.12610v1
    Announce Type: new \\nAbstract: ..."), which would otherwise be scored as
    if it were the paper's words, and printed on the page;
  * a cross-listed paper is in two feeds and is one paper;
  * the version in the link must be dropped, or tomorrow's v2 reads as a new
    paper;
  * every record says which route found it, because the page says it too.

No network: each response is a stub.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import cache, fetch_arxiv                       # noqa: E402
from tools.news import common                                   # noqa: E402

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


CFG = {
    "arxiv": {
        "enabled": True,
        "categories": ["hep-ex", "hep-ph"],
        "window_hours": 168,
        "max_fetch": 400,
        "keywords": {"high": ["neutrino", "oscillation"], "low": ["seesaw"]},
    }
}


def item(aid: str, title: str, announce: str, *, cat: str = "hep-ex",
         extra_cat: str = "", authors: str = "A. One, B. Two",
         abstract: str = "A study of neutrino oscillation parameters.") -> str:
    cats = f"<category>{cat}</category>"
    if extra_cat:
        cats += f"<category>{extra_cat}</category>"
    return f"""
  <item>
    <title>{title}</title>
    <link>https://arxiv.org/abs/{aid}</link>
    <description>arXiv:{aid} Announce Type: {announce}
Abstract: {abstract}</description>
    <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">{authors}</dc:creator>
    {cats}
    <pubDate>Mon, 14 Sep 2026 00:00:00 -0400</pubDate>
    <arxiv:announce_type xmlns:arxiv="http://arxiv.org/schemas/atom">{announce}</arxiv:announce_type>
  </item>"""


def feed(*items: str) -> str:
    return ("""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>hep-ex updates</title>
    <pubDate>Mon, 14 Sep 2026 00:00:00 -0400</pubDate>"""
            + "".join(items) + """
  </channel>
</rss>""")


HEP_EX = feed(
    item("2609.00001v1", "Neutrino oscillation results from a long baseline", "new"),
    item("2609.00002v2", "Neutrino oscillation results, revised again", "replace"),
    item("2609.00003v1", "A cross-listed neutrino paper", "cross",
         cat="hep-ex", extra_cat="hep-ph"),
    item("2609.00004v1", "Precision charm spectroscopy", "new",
         abstract="Nothing here is about the topic at hand."),
    item("2609.00005v3", "An old oscillation paper, cross-listed again",
         "replace-cross"),
)
HEP_PH = feed(
    item("2609.00003v1", "A cross-listed neutrino paper", "new", cat="hep-ph"),
    item("2609.00006v1", "Seesaw textures", "new", cat="hep-ph",
         authors="A. One, B. Two, C. Three, D. Four, E. Five",
         abstract="A seesaw model of neutrino mass."),
    item("2609.00007v1", "Neutrino mass from a modular symmetry", "new",
         cat="hep-ph", authors=r"H. Almaz\'an, Rita de C\'assia, J. M\"uller",
         abstract="A neutrino oscillation study."),
)

FEEDS = {"hep-ex": HEP_EX, "hep-ph": HEP_PH}


class _Response:
    def __init__(self, body: str):
        self.content = body.encode("utf-8")
        self.text = body
        self.status_code = 200
        self.url = "stub"


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def _add(self, msg, *a):
        self.lines.append(msg % a if a else msg)

    info = warning = error = _add

    def debug(self, *a, **k):
        pass


def run_fetch(*, api_answers: str | None):
    """fetch() with the API stubbed to answer, or to refuse."""
    asked: list[str] = []

    def fake_http_get(url, **kw):
        asked.append(url)
        if url.startswith(fetch_arxiv.API):
            return _Response(api_answers) if api_answers is not None else None
        for cat, body in FEEDS.items():
            if url.endswith(f"/{cat}"):
                return _Response(body)
        return None

    stored = {}
    real_get, real_store = fetch_arxiv.http_get, cache.store
    fetch_arxiv.http_get = fake_http_get
    cache.store = lambda source, records, errors=None: stored.update(
        {"source": source, "records": records, "errors": errors})
    log = _Log()
    try:
        recs = fetch_arxiv.fetch(CFG, log)
    finally:
        fetch_arxiv.http_get, cache.store = real_get, real_store
    return recs, asked, log, stored


# An API answer with one on-topic entry, to prove the feeds stay untouched.
API_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2609.09999v1</id>
    <title>Neutrino oscillation from the API</title>
    <summary>Measuring neutrino oscillation.</summary>
    <published>{published}</published>
    <author><name>A. One</name></author>
    <category term="hep-ex"/>
  </entry>
</feed>"""

import datetime as _dt                                          # noqa: E402

_now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# --------------------------------------------------------------------- #
# the API is preferred, and the feeds are not touched when it answers
# --------------------------------------------------------------------- #
recs, asked, log, _ = run_fetch(api_answers=API_ATOM.format(published=_now))
check("when the API answers, its records are what comes back",
      len(recs) == 1 and recs[0]["id"] == "arxiv:2609.09999", recs)
check("...marked as having come by the API route",
      recs and recs[0]["extra"].get("route") == "api", recs[0]["extra"] if recs else None)
check("...and no RSS feed is fetched at all",
      not any("rss" in u for u in asked), asked)

# --------------------------------------------------------------------- #
# the API refuses: the feeds answer instead
# --------------------------------------------------------------------- #
recs, asked, log, stored = run_fetch(api_answers=None)
ids = [r["id"] for r in recs]

check("when the API refuses, every configured feed is read",
      sum("rss" in u for u in asked) == 2, asked)
check("...and the records come back marked as the RSS route",
      recs and all(r["extra"].get("route") == "rss" for r in recs),
      [r["extra"].get("route") for r in recs])

check("a 'new' announcement is kept", "arxiv:2609.00001" in ids, ids)
check("a 'cross' announcement is kept — new to this category",
      "arxiv:2609.00003" in ids, ids)
check("a 'replace' is NOT listed: it is a revision of an older paper, not "
      "today's preprint",
      "arxiv:2609.00002" not in ids, ids)
check("a 'replace-cross' is not listed either",
      "arxiv:2609.00005" not in ids, ids)
check("an off-topic new preprint is dropped by the keyword score",
      "arxiv:2609.00004" not in ids, ids)
check("a paper announced in two of the configured feeds appears once",
      ids.count("arxiv:2609.00003") == 1, ids)

by_id = {r["id"]: r for r in recs}
_cross = by_id.get("arxiv:2609.00003")
check("the version suffix is dropped from the id, so tomorrow's v2 is the "
      "same paper",
      _cross is not None and "v1" not in _cross["id"], _cross and _cross["id"])
check("...and from the links, which point at the versionless abstract page",
      _cross is not None and _cross["url"] == "https://arxiv.org/abs/2609.00003",
      _cross and _cross["url"])

_first = by_id.get("arxiv:2609.00001")
check("the feed's own preamble is stripped from the abstract, not scored and "
      "not printed",
      _first is not None and "Announce Type" not in _first["summary"]
      and not _first["summary"].lower().startswith("abstract"),
      _first and _first["summary"][:80])
check("the abstract itself survives that stripping",
      _first is not None and _first["summary"].startswith("A study of neutrino"),
      _first and _first["summary"][:60])
check("the record carries the announcement date, not the day it was rendered",
      _first is not None and _first["date"] == "2026-09-14",
      _first and _first["date"])
check("the primary category leads, which is what the page's "
      "experimental/theory split reads",
      _first is not None and _first["extra"]["categories"][0] == "hep-ex",
      _first and _first["extra"]["categories"])

_seesaw = by_id.get("arxiv:2609.00006")
check("a long author list is cut to three and marked et al.",
      _seesaw is not None and _seesaw["authors"] == "A. One, B. Two, C. Three et al.",
      _seesaw and _seesaw["authors"])

# The feeds hand names back as LaTeX; the API hands the same names back as
# Unicode. A person's name must not depend on which route was up that day.
_accented = by_id.get("arxiv:2609.00007")
check("LaTeX accents in an author list are resolved to the letters they stand "
      "for, as the API route already returns them",
      _accented is not None
      and _accented["authors"] == "H. Almazán, Rita de Cássia, J. Müller",
      _accented and _accented["authors"])
check("a name with no LaTeX in it is passed through untouched",
      fetch_arxiv._delatex("J. Waiton, B. Palmeiro")
      == "J. Waiton, B. Palmeiro")
check("an unknown LaTeX command is left alone rather than guessed at — a "
      "visible oddity beats a plausible wrong name",
      fetch_arxiv._delatex(r"A. \textbf Name") == r"A. \textbf Name",
      fetch_arxiv._delatex(r"A. \textbf Name"))

check("the records are ordered by score, highest first",
      [r["extra"]["score"] for r in recs]
      == sorted((r["extra"]["score"] for r in recs), reverse=True),
      [r["extra"]["score"] for r in recs])

check("the fallback is logged as a fallback, naming what it is and is not",
      any("RSS" in line and "168h window" in line for line in log.lines),
      log.lines)
check("the cache records the API failure alongside the recovered records",
      stored.get("errors") and any("unreachable" in e for e in stored["errors"])
      and stored.get("records"), stored.get("errors"))

# --------------------------------------------------------------------- #
# both routes gone
# --------------------------------------------------------------------- #
_real_feeds = dict(FEEDS)
FEEDS.clear()
recs, asked, log, stored = run_fetch(api_answers=None)
FEEDS.update(_real_feeds)
check("with the API refusing and no feed reachable, nothing is returned — "
      "the page keeps its own content and its own timestamp",
      recs == [], recs)
check("...and the log says both routes were tried, not just the first",
      any("feeds gave nothing" in line for line in log.lines), log.lines)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the feed route lists what was announced "
      f"today, and nothing else")
