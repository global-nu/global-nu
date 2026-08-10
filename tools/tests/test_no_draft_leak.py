#!/usr/bin/env python3
"""Check that nothing embargoed has leaked into what gets published.

    ./.venv/bin/python3 tools/tests/test_no_draft_leak.py

This is the most important test in the project. A wrong number on a page is an
error; an unpublished result on a public page is a different kind of failure,
and the only defence that works is one that looks at the artefacts rather than
at intentions.

Four checks, each answering a way it could go wrong:

  1. no file from drafts/ was copied into site/
  2. no page in site/ links to a draft page
  3. git tracks nothing under drafts/ or site-draft/ — the repository becomes
     public, so "not deployed" is not enough
  4. the actual numbers of the draft release appear nowhere in site/ — the
     check that survives someone pasting a table by hand
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
DRAFTS = ROOT / "drafts"

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


def main() -> None:
    if not SITE.exists():
        sys.exit("site/ not found — run build.py first")

    site_files = {p.name for p in SITE.rglob("*") if p.is_file()}
    site_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in SITE.rglob("*.html"))

    # 1. no draft file by name
    if DRAFTS.exists():
        draft_names = {p.with_suffix(".html").name for p in (DRAFTS / "content").glob("*.md")}
        draft_names |= {p.name for p in (DRAFTS / "data").rglob("*") if p.is_file()}
        clash = sorted(draft_names & site_files)
        check("no draft file was copied into site/", not clash, ", ".join(clash))
    else:
        check("no drafts/ directory present", True)

    # 2. no link to a draft page
    draft_urls = []
    for md in (DRAFTS / "content").glob("*.md") if DRAFTS.exists() else []:
        m = re.search(r"^url:\s*(\S+)", md.read_text(encoding="utf-8"), re.M)
        if m:
            draft_urls.append(m.group(1))
    linked = [u for u in draft_urls if u in site_text]
    check("no published page links to a draft page", not linked, ", ".join(linked))

    # 3. git tracks nothing embargoed
    tracked = subprocess.run(["git", "ls-files", "drafts", "site-draft"],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    check("git tracks nothing under drafts/ or site-draft/", not tracked,
          " ".join(tracked[:5]))

    # 4. the numbers themselves are absent
    chi2 = DRAFTS / "data" / "chi2.json"
    if chi2.exists():
        doc = json.loads(chi2.read_text(encoding="utf-8"))
        values: list[float] = []
        for ds in doc["datasets"].values():
            for p in ds["params"].values():
                values += p["no"][:40] + p["io"][:40]
        random.seed(0)
        sample = random.sample(values, min(60, len(values)))
        # Full published precision, matched as a whole token. Five significant
        # digits looked safe and was not: "11.87" is also a longitude on the
        # coastline path of the world map, and "44.06" appears verbatim as a
        # coordinate pair. A Δχ² carries five decimals, and at that length a
        # coincidence with a map coordinate does not happen.
        hits = [f"{v:.5f}" for v in sample
                if re.search(r"(?<![\d.])" + re.escape(f"{v:.5f}") + r"(?![\d])",
                             site_text)]
        check(f"none of {len(sample)} sampled Δχ² values appears in site/",
              not hits, ", ".join(hits[:6]))
    else:
        check("no draft Δχ² data to check for", True)

    print()
    if problems:
        print("  ! embargoed material has leaked:")
        for p in problems:
            print("      " + p)
        sys.exit(1)
    print(f"all {checks} checks pass — nothing embargoed is in the published tree")


if __name__ == "__main__":
    main()
