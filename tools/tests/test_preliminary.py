#!/usr/bin/env python3
"""A release published as PRELIMINARY is marked everywhere and downloadable nowhere.

    ./.venv/bin/python3 tools/tests/test_preliminary.py

Reads site.yaml `preliminary` and the built site/ (tools/preliminary.py does
the work). With no preliminary release it checks that no page carries the
marker. Otherwise:

  1. every page that shows the release has the PRELIMINARY banner, and the
     Results page and the home panel their badge;
  2. no page links to a file of the release, and no "draft" wording is left;
  3. site/release-2026a holds images only, and site/data no package of it;
  4. the sections that hand out files (6D χ², downloads, notebook) are gone,
     and the 6D scripts are not loaded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


def visible(page: str) -> str:
    page = re.sub(r"<(script|style|template)\b.*?</\1>", " ", page, flags=re.S)
    return re.sub(r"<[^>]+>", " ", page)


def main() -> None:
    cfg = yaml.safe_load((ROOT / "site-src/site.yaml").read_text(encoding="utf-8"))
    rid = str(cfg.get("preliminary") or "")
    pages = {p.relative_to(SITE).as_posix(): p.read_text(encoding="utf-8")
             for p in SITE.rglob("*.html")}
    if not rid:
        marked = [u for u, s in pages.items() if "prelim-banner" in s]
        check("no page carries the PRELIMINARY banner", not marked, ", ".join(marked))
    else:
        shows = [u for u, s in pages.items() if rid in s or "release-2026a/" in s]
        check(f"release {rid} is on the home page and on results.html",
              {"index.html", "results.html"} <= set(shows), ", ".join(shows))
        unmarked = [u for u in shows if 'class="prelim-banner"' not in pages[u]]
        check(f"every page showing {rid} has the banner ({len(shows)} pages)",
              not unmarked, ", ".join(unmarked))
        for u, where in (("results.html", "</h1>"), ("index.html", "</h2>")):
            check(f"{u}: PRELIMINARY badge in the release heading",
                  re.search(r'prelim--badge">Preliminary</span>' + where, pages[u]) is not None)

        bad_links = sorted({f"{u}: {h}" for u, s in pages.items()
                            for h in re.findall(r'href="((?:\.\./)*(?:release-2026a/|data/releases/(?:2026\.a|latest))[^"]*)"', s)})
        check("no page links to a file of the release", not bad_links, ", ".join(bad_links[:5]))
        drafty = sorted({f"{u}: …{m.group(0)}…" for u in shows
                         for m in re.finditer(r".{0,30}\b(?:[Dd]raft\b|not published\)).{0,30}", visible(pages[u]))})
        check("no draft wording on those pages", not drafty, " | ".join(drafty[:4]))

        rel = SITE / "release-2026a"
        files = [p for p in rel.rglob("*") if p.is_file()] if rel.exists() else []
        non_img = [p.relative_to(SITE).as_posix() for p in files if p.suffix not in (".png", ".svg")]
        check(f"site/release-2026a holds images only ({len(files)} files)", not non_img, ", ".join(non_img[:5]))
        missing = sorted({s for page in pages.values()
                          for s in re.findall(r'src="(release-2026a/[^"?]+)', page)
                          if not (SITE / s).is_file()})
        check("every release figure a page shows is published", not missing, ", ".join(missing))
        pkgs = [p.name for p in (SITE / "data/releases").glob("*")] if (SITE / "data/releases").exists() else []
        check("no release package under site/data/releases", not pkgs, ", ".join(pkgs))
        cur = (SITE / "data/current/parameters.csv")
        check("data/current holds no value of the preliminary release",
              cur.exists() and rid not in cur.read_text(encoding="utf-8"))

        # Every image a page shows resolves to a published file (a fragment
        # spliced from the release once pointed at figures/, which is not here).
        broken = sorted({f"{u}: {src}" for u, page in pages.items()
                         for src in re.findall(r'<img\b[^>]*\bsrc="([^"?#]+)', page)
                         if not src.startswith(("http:", "https:", "data:", "//"))
                         and not ((SITE / u).parent / src).resolve().is_file()})
        check("every <img> on every page resolves to a published file", not broken,
              ", ".join(broken[:5]))

        # The latest data everywhere. A component that reads a published data
        # file (data/history.json …) cannot show the preliminary release, which
        # has no file: on a page that shows the release, every such component
        # must carry its rows in the page. The history chart once read the
        # public register only, and 2026.a was missing from it.
        import json
        for u in shows:
            for m in re.finditer(r'<div class="explorer"[^>]*>', pages[u]):
                tail = pages[u][m.end():m.end() + 200]
                check(f"{u}: the interactive chart carries its rows in the page",
                      tail.startswith('<script type="application/json" class="explorer__data">'))
        hist = pages.get("history.html", "")
        m = re.search(r'class="explorer__data">(.*?)</script>', hist, re.S)
        rows = json.loads(m.group(1))["rows"] if m else []
        have = {(r["group"], str(r.get("year_label") or r["year"]), r["parameter"]) for r in rows}
        for key in [("bari", rid, p) for p in ("dm2", "sin2_th12", "Dm2", "sin2_th13", "sin2_th23", "delta_pi")] \
                + [("nufit", "2025", p) for p in ("dm2", "sin2_th12", "Dm2", "sin2_th13", "sin2_th23")]:
            check(f"history chart has {key[0]} {key[1]} {key[2]}", key in have)
        check("history panels show Bari " + rid, f"Bari, {rid}:" in hist)
        check("history panels show NuFit 2025 (NuFIT 6.1)", "NuFit, 2025:" in hist)
        check("history chart: downloads off", 'data-no-download=' in hist)
        check("no page calls an older release 'current release'",
              not any('<span class="tag">current release</span>' in pages[u] for u in shows))
        check("home precision chart has the release's point", f"{rid}: 1σ accuracy" in pages["index.html"])
        check("results comparison is with NuFIT 6.1", "NuFIT 6.1</th>" in pages["results.html"])

        res = pages["results.html"]
        for marker in ('<section id="chi2-6d-sezione"', "Run it in the browser", "Quick start",
                       "The same tables as PDF", "relpage/engine.js", "relpage/panel.js",
                       'class="gd-f"'):
            check(f"results.html: no {marker!r}", marker not in res)
        check("results.html: the data notice is there", 'class="prelim-files"' in res)

    print()
    if problems:
        print("  ! preliminary release not published as intended:")
        for p in problems:
            print("      " + p)
        sys.exit(1)
    print(f"all {checks} checks pass")


if __name__ == "__main__":
    main()
