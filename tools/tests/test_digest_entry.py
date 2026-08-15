#!/usr/bin/env python3
"""Check the shape of one digest entry.

    ./.venv/bin/python3 tools/tests/test_digest_entry.py

The entry's title now carries the arXiv link, so the separate links row must
disappear when arXiv was the only thing in it — and must survive when the
record also has a DOI or a journal. Getting that wrong loses a published
paper's real citation links, silently, on a page nobody re-reads daily.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import render                            # noqa: E402

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


PREPRINT = {
    "title": "MANGO: An Autodiff Neutrino Oscillation Engine",
    "authors": "Pierre Granger",
    "date": "2026-08-13",
    # `url` is always present on a real record (cache.py's contract), and for
    # an arXiv-sourced one it is the same address as links["arxiv"] — the
    # fixture matches that shape so this test would have caught the "Read
    # it" link that duplicated the title's link when it wasn't.
    "url": "https://arxiv.org/abs/2508.09999",
    "links": {"arxiv": "https://arxiv.org/abs/2508.09999"},
    "extra": {"categories": ["hep-ex", "hep-ph"]},
}
PUBLISHED = {
    "title": "A published one",
    "authors": "N. J. Ayres, Z. Berezhiani",
    "date": "2026-08-12",
    "url": "https://arxiv.org/abs/2508.00001",
    "links": {"arxiv": "https://arxiv.org/abs/2508.00001",
              "doi": "https://doi.org/10.1103/xyz"},
    "extra": {"categories": ["hep-ex"]},
}

check("a human date replaces the ISO one",
      render._human_date("2026-08-13") == "13 Aug 2026",
      render._human_date("2026-08-13"))
check("an unparseable date is passed through untouched",
      render._human_date("not a date") == "not a date")

html = render._digest_list([PREPRINT])
check("the title is a link to arXiv",
      '<a href="https://arxiv.org/abs/2508.09999">MANGO' in html, html[:300])
check("the date is printed in human form", "13 Aug 2026" in html, html[:300])
check("the ISO date is gone", "2026-08-13" not in html, html[:300])
check("each category is its own pill",
      html.count('<span class="tag">') == 2, html[:400])
check("the categories are not run together in one string",
      "hep-ex, hep-ph" not in html, html[:400])
check("a preprint whose only link was arXiv has no links row",
      'class="cites"' not in html, html[:400])

html2 = render._digest_list([PUBLISHED])
check("a record with a DOI keeps its links row",
      'class="cites"' in html2 and "10.1103/xyz" in html2, html2[:400])
check("that row no longer repeats the arXiv link",
      html2.count("2508.00001") == 1, html2[:400])

# The cap is content, not form, and this change must not move it.
many = dict(PREPRINT)
many["extra"] = {"categories": ["hep-ph", "hep-ex", "astro-ph.CO", "hep-th"]}
check("the three-category cap is unchanged",
      render._digest_list([many]).count('<span class="tag">') == 3)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the digest entry has its new form")
