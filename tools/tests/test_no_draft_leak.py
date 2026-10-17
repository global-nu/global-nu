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

Checks 2 and 4 read every published *text* artefact: the pages, and the data
files the site publishes beside them (JSON and CSV under site/data/). An
embargoed number in a downloadable table is as public as one on a page.
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
    # Every published text artefact, not only the pages. The site now ships
    # data files as well — site/data/chi2.json, history.json, history.csv —
    # and a number that leaked into one of those is published just as
    # loudly as one on a page, at a URL people are invited to download. A
    # glob that reads only *.html would look complete and check none of them.
    PUBLISHED_TEXT = ("*.html", "*.json", "*.csv")
    # A release published as PRELIMINARY (site.yaml `preliminary`) is meant to
    # be on the pages; what must still not be published is any FILE of it.
    # Then every check below reads the files the site hands out (everything
    # but pages, stylesheets and images), and tools/tests/test_preliminary.py
    # checks the pages.
    import yaml
    prelim = str(yaml.safe_load((ROOT / "site-src/site.yaml").read_text(encoding="utf-8"))
                 .get("preliminary") or "")
    if prelim:
        print(f"  release {prelim} is published as preliminary: checking its files, not its pages")
        PUBLISHED_TEXT = ("*.json", "*.csv", "*.txt", "*.bib", "*.md", "*.atom", "*.ics", "*.yaml", "*.js")
    site_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for pattern in PUBLISHED_TEXT
        for p in sorted(SITE.rglob(pattern))
        if not (prelim and p.is_relative_to(SITE / "assets")))

    # 1. no draft file was copied. By CONTENT, not by name: the draft build
    # overlays public files on purpose (data/current/parameters.csv exists in
    # both, with different numbers), so a name clash is expected and proves
    # nothing, while a renamed copy of a draft file would slip past a name
    # check. A draft file whose bytes also exist among the public inputs
    # (a schema, say) is not embargoed and is skipped.
    import hashlib
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    public_inputs = {sha(p) for d in (ROOT / "site-src", ROOT / "data-exports")
                     for p in d.rglob("*") if p.is_file()}
    if DRAFTS.exists():
        embargoed = {}
        for p in DRAFTS.rglob("*"):
            if p.is_file() and p.suffix not in (".py", ".pyc"):
                h = sha(p)
                if h not in public_inputs:
                    embargoed[h] = p.relative_to(ROOT).as_posix()
        site_hashes = {sha(p): p.relative_to(SITE).as_posix()
                       for p in SITE.rglob("*") if p.is_file()}
        clash = sorted(f"{site_hashes[h]} = {embargoed[h]}" for h in embargoed.keys() & site_hashes.keys()
                       # the figures a preliminary page shows are published as pictures
                       if not (prelim and site_hashes[h].startswith("release-2026a/figures/")
                               and site_hashes[h].endswith((".png", ".svg"))))
        check(f"no draft file's content is in site/ ({len(embargoed)} draft files)",
              not clash, ", ".join(clash[:6]))
        draft_pages = {p.with_suffix(".html").name for p in (DRAFTS / "content").glob("*.md")}
        public_pages = {p.with_suffix(".html").name for p in (ROOT / "site-src" / "content").rglob("*.md")}
        only_draft = [] if prelim else sorted((draft_pages - public_pages) & site_files)
        check("no draft-only page exists in site/", not only_draft, ", ".join(only_draft))
    else:
        check("no drafts/ directory present", True)

    # 2. no link to a draft page
    # Only pages that exist ONLY in the draft count: a draft page may override
    # a public one at the same URL (the draft Results page does), and links to
    # that URL from public pages are links to the public page.
    public_urls = set()
    for md in (ROOT / "site-src" / "content").rglob("*.md"):
        m = re.search(r"^url:\s*(\S+)", md.read_text(encoding="utf-8"), re.M)
        public_urls.add(m.group(1) if m else md.with_suffix(".html").name)
    draft_urls = []
    for md in (DRAFTS / "content").glob("*.md") if DRAFTS.exists() else []:
        m = re.search(r"^url:\s*(\S+)", md.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) not in public_urls:
            draft_urls.append(m.group(1))
    linked = [] if prelim else [u for u in draft_urls if u in site_text]
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

    # 5. the unpublished release itself: its name, its package path, and its
    # best fits as the draft prints them (those with four or more significant
    # digits). Whole tokens only.
    rel_yaml = DRAFTS / "data" / "releases.yaml"
    if rel_yaml.exists():
        import yaml
        from decimal import Decimal
        doc = yaml.safe_load(rel_yaml.read_text(encoding="utf-8"))
        markers = []
        tokens = []
        for r in doc["releases"]:
            markers += [r["id"], r.get("version") or "", r.get("package") or ""]
            for p, by in r["values"].items():
                for o, e in by.items():
                    tokens.append(e["best"])
                    if p.startswith("sin2"):
                        scale = {"sin2_th12": "0.1", "sin2_th13": "0.01", "sin2_th23": "0.1"}[p]
                        tokens.append(str(Decimal(e["best"]) * Decimal(scale)))
        markers = [m for m in markers if m]
        # Only values with at least four significant digits identify the draft:
        # sin²θ₁₃ = 2.22 or δ/π = 1.19, printed at the release table's own
        # precision, coincide with numbers other papers published.
        tokens = [t for t in tokens if len(t.replace("-", "").replace(".", "").lstrip("0")) >= 4]
        found = [m for m in markers if m in site_text]
        check(f"the draft release's name and path appear nowhere in site/ ({', '.join(markers)})",
              not found, ", ".join(found))
        hits = sorted({t for t in tokens
                       if re.search(r"(?<![\d.])" + re.escape(t) + r"(?![\d])", site_text)})
        check(f"none of the draft release's {len(set(tokens))} printed best fits appears in site/",
              not hits, ", ".join(hits[:8]))
    else:
        check("no draft release to check for", True)

    print()
    if problems:
        print("  ! embargoed material has leaked:")
        for p in problems:
            print("      " + p)
        sys.exit(1)
    print(f"all {checks} checks pass — nothing embargoed is in the published tree")


if __name__ == "__main__":
    main()
