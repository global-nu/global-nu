#!/usr/bin/env python3
"""Check the structured metadata the site publishes about itself.

    ./.venv/bin/python3 tools/tests/test_metadata.py

A malformed JSON-LD block is invisible to the eye and mute to a crawler: the
page renders, the build succeeds, and the dataset simply never appears in
Google Dataset Search. Everything here is a guard against a silent failure.

Run build.py first — this reads the built tree, not the sources.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT))

from tools import register_meta                          # noqa: E402

CFG = yaml.safe_load((ROOT / "site-src" / "site.yaml").read_text(encoding="utf-8"))
DOI = (CFG.get("dataset") or {}).get("doi") or ""

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


LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def blocks(page: str) -> list[dict]:
    text = (SITE / page).read_text(encoding="utf-8")
    out = []
    for raw in LD.findall(text):
        out.append(json.loads(raw))
    return out


if not (SITE / "history.html").exists():
    check("site/ holds built pages", False,
          "run ./.venv/bin/python3 build.py first")
else:
    # --- history.html: the Dataset ---------------------------------------
    try:
        found = blocks("history.html")
        parsed = True
    except json.JSONDecodeError as exc:
        found, parsed = [], False
        check("history.html JSON-LD parses", False, str(exc))
    if parsed:
        check("history.html JSON-LD parses", True)

    ds = next((b for b in found if b.get("@type") == "Dataset"), None)
    check("history.html carries a Dataset block", ds is not None,
          f"found types {[b.get('@type') for b in found]}")

    if ds:
        for field in ("@context", "name", "description", "url", "license",
                      "creator", "distribution", "temporalCoverage",
                      "variableMeasured"):
            check(f"Dataset has {field}", field in ds)

        check("Dataset licence is CC BY 4.0",
              ds.get("license") == "https://creativecommons.org/licenses/by/4.0/",
              str(ds.get("license")))

        # Every distributed file must actually be there. This is the case
        # where an export is renamed and the metadata quietly points at
        # nothing — a 404 that only a machine ever sees.
        for dist in ds.get("distribution", []):
            url = dist.get("contentUrl", "")
            rel = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
            check(f"distribution exists: {rel}", (SITE / rel).exists(), url)

        facts = register_meta.register_facts()
        check("temporalCoverage is the register's, not a typed one",
              ds.get("temporalCoverage") == facts["temporal_coverage"],
              f"page {ds.get('temporalCoverage')!r} vs register "
              f"{facts['temporal_coverage']!r}")

        page_vars = {v.get("name") for v in ds.get("variableMeasured", [])}
        reg_vars = {v["name"] for v in facts["variables"]}
        check("variableMeasured is the register's parameter list",
              page_vars == reg_vars, f"page {sorted(page_vars)} vs register "
                                     f"{sorted(reg_vars)}")

        if facts["date_modified"]:
            check("dateModified is the register's commit date, not the build date",
                  ds.get("dateModified") == facts["date_modified"],
                  f"page {ds.get('dateModified')!r} vs git "
                  f"{facts['date_modified']!r}")

    # --- the DOI, present or absent, must be consistent everywhere -------
    hist = (SITE / "history.html").read_text(encoding="utf-8")
    if DOI:
        check("configured DOI has the shape 10.xxxx/...",
              re.fullmatch(r"10\.\d{4,9}/\S+", DOI) is not None, DOI)
        check("history.html declares citation_doi",
              f'name="citation_doi" content="{DOI}"' in hist)
        check("Dataset carries the DOI as identifier",
              bool(ds) and DOI in json.dumps(ds))
    else:
        check("with no DOI configured, no citation_doi is emitted",
              "citation_doi" not in hist,
              "the page is claiming an identifier that does not exist")
        check("with no DOI configured, the Dataset has no identifier",
              not bool(ds) or "identifier" not in ds)

    # --- citation_* belongs on the dataset page and nowhere else ---------
    for page in sorted(SITE.glob("*.html")):
        has = "citation_title" in page.read_text(encoding="utf-8")
        if page.name == "history.html":
            check("history.html carries citation_* tags", has)
        else:
            check(f"{page.name} carries no citation_* tags", not has,
                  "Google Scholar would index it as a separate scholarly work")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the published metadata says what the data says")
