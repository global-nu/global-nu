#!/usr/bin/env python3
"""Download the source papers for the parameter-history page.

The history page is built by reading tables out of published papers. This
script only fetches them — it extracts nothing and decides nothing. The PDFs
land in a local cache that is never committed and never published: the site
links to arXiv and the journal, it does not redistribute the papers.

    python3 tools/fetch_history_sources.py

Cache: var/history-sources/<slug>.pdf
"""

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "var" / "history-sources"

# group, year, arXiv id. Order is the order of the timeline.
SOURCES = [
    # ---- Bari ----
    ("bari", 2002, "hep-ph/0206162"),
    ("bari", 2002, "hep-ph/0212127"),
    ("bari", 2003, "hep-ph/0308055"),
    ("bari", 2006, "hep-ph/0506083"),  # posted 2005, published Prog. Part. Nucl. Phys. 57, 742 (2006)
    ("bari", 2008, "0806.2649"),
    ("bari", 2011, "1106.6028"),
    ("bari", 2012, "1205.5254"),
    ("bari", 2013, "1312.2878"),
    ("bari", 2016, "1601.07777"),
    ("bari", 2017, "1703.04471"),
    ("bari", 2018, "1804.09678"),
    ("bari", 2021, "2107.00532"),
    ("bari", 2025, "2503.07752"),
    ("bari", 2026, "2511.21650"),
    # ---- NuFit ----
    ("nufit", 2001, "hep-ph/0009350"),  # posted 2000, published Phys. Rev. D 63, 033005 (2001)
    ("nufit", 2004, "hep-ph/0405172"),
    ("nufit", 2010, "1001.4524"),
    ("nufit", 2012, "1209.3023"),
    ("nufit", 2018, "1811.05487"),
    ("nufit", 2020, "2007.14792"),
    ("nufit", 2024, "2410.05380"),
    # ---- Valencia ----
    ("valencia", 2018, "1708.01186"),
    ("valencia", 2018, "1806.11051"),
    ("valencia", 2020, "2006.11237"),
]

UA = "global-nu-site/0.1 (https://global-nu.org; antonio.marrone@ba.infn.it)"


def slug(group: str, year: int, eprint: str) -> str:
    return f"{group}-{year}-{eprint.replace('/', '_')}"


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    got = skipped = failed = 0
    for group, year, eprint in SOURCES:
        dest = CACHE / f"{slug(group, year, eprint)}.pdf"
        if dest.exists() and dest.stat().st_size > 40_000:
            skipped += 1
            continue
        url = f"https://arxiv.org/pdf/{eprint}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
        except Exception as exc:                       # noqa: BLE001
            print(f"  FAIL {eprint}: {exc}")
            failed += 1
            continue
        if not data.startswith(b"%PDF"):
            print(f"  FAIL {eprint}: not a PDF ({len(data)} bytes)")
            failed += 1
            continue
        dest.write_bytes(data)
        print(f"  ok   {eprint:<16} {len(data)//1024:>5} KB  -> {dest.name}")
        got += 1
        time.sleep(3)          # arXiv asks for a gap between automated requests

    print(f"\n{got} downloaded, {skipped} already cached, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
