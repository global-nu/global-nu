#!/usr/bin/env python3
"""Every news summary says what it is, where it came from, and how to fix it.

    ./.venv/bin/python3 tools/tests/test_news_meta.py

An automatic summary must never look like one of the group's results. Each
item carries the AI label first, its sources with their own dates, the date
the summary was written, a "human reviewed" label only when the item says
so, and a correction link with an encoded subject.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.news import render  # noqa: E402

known = {
    "feed:a": {"id": "feed:a", "source": "feed", "date": "2026-10-06", "extra": {"feed": "IceCube"},
               "url": "https://icecube.wisc.edu/news/x", "title": "Halzen wins"},
    "inspire:1": {"id": "inspire:1", "source": "inspire", "date": "2026-10-04",
                  "url": "https://inspirehep.net/literature/1", "title": "A paper",
                  "extra": {"reference": "Phys.Rev.Lett. 137 (2026) 161402"}},
}
bad = []


def check(label, ok):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        bad.append(label)


m = render._news_meta({"ids": ["feed:a", "inspire:1"], "heading": "A & B"}, known, "16 Oct 2026")
check("AI label comes first", m.startswith('<p class="newsmeta"><span class="vbadge vbadge--ai">AI-generated</span>'))
item = render._news_item({"ids": ["feed:a", "inspire:1"], "heading": "A & B", "text": "t"}, known, "16 Oct 2026", "A & B")
check("each source is a button with its own date",
      item.count('class="news-src"') == 2 and "IceCube" in item and "6 Oct 2026" in item
      and "INSPIRE-HEP, Phys.Rev.Lett. 137 (2026) 161402" in item and "4 Oct 2026" in item)
thy = render._news_item({"ids": ["inspire:1"], "text": "t"}, known, "16 Oct 2026", None)
check("an item without a heading takes its paper's title", '<h3 class="news-item__h">A paper</h3>' in thy)
check("summary date", "Summary written 16 Oct 2026" in m)
check("no human-reviewed label unless the item says so", "human reviewed" not in m)
check("correction link with encoded subject", "mailto:antonio.marrone@ba.infn.it?subject=global-nu%20news%20correction%3A%20A%20%26amp%3B%20B" in m
      or "subject=global-nu%20news%20correction%3A%20A%20%26%20B" in m)
m2 = render._news_meta({"ids": ["feed:a"], "heading": "x", "reviewed": True}, known, "")
check("human reviewed label when the item is reviewed", "vbadge--human" in m2)
if bad:
    sys.exit(1)
print("all news-provenance checks pass")
