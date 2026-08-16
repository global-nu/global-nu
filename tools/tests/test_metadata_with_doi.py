#!/usr/bin/env python3
"""Build the site with a DOI configured, and check every claim it enables.

    ./.venv/bin/python3 tools/tests/test_metadata_with_doi.py

The real DOI arrives only after the Zenodo deposit, and the moment after a
permanent identifier is minted is the worst moment to discover that the build
mishandles it. This builds into a throwaway tree with a placeholder DOI, so
both states — with and without — are covered before the deposit is made.

The modified config is written to a temp file and the build is pointed at it
with --config; site-src/site.yaml is never touched. Editing the real config
and restoring it afterwards protected the file but not the window: the daily
job runs build.py from the checkout at 07:30 and then commits and pushes
site/, so a run of this suite overlapping that job would publish a fabricated
DOI, Dataset identifier and llms.txt line to the live site. A file that is
never written cannot be published.

The copy is made by text substitution, not by parsing site.yaml into a dict
and dumping it back: a round trip through yaml.safe_dump would silently strip
every comment in the file, including the ones explaining why an empty DOI (or
an empty GoatCounter code) must make the build emit nothing rather than an
empty tag.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAKE_DOI = "10.5281/zenodo.9999999"

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


cfg_path = ROOT / "site-src" / "site.yaml"
original = cfg_path.read_text(encoding="utf-8")

work = Path(tempfile.mkdtemp(prefix="gnu-doi-"))

try:
    # One occurrence, or the substitution below is aimed at a line we have not
    # identified — and a DOI written into the wrong key would make the test
    # pass against a build that never saw one. Stop rather than pick.
    needle = 'doi: ""'
    found = original.count(needle)
    check("the empty doi: \"\" line is present exactly once", found == 1,
          f"found {found} occurrences — cannot tell which one is the dataset DOI")
    if found != 1:
        sys.exit(f"  ! aborting: {found} candidate doi: \"\" lines in site.yaml")

    doi_cfg = work / "site-with-doi.yaml"
    doi_cfg.write_text(original.replace(needle, f'doi: "{FAKE_DOI}"', 1),
                       encoding="utf-8")

    out = work / "site"
    run = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python3"), "build.py",
         "--out", str(out), "--config", str(doi_cfg), "--no-images"],
        cwd=ROOT, capture_output=True, text=True)
    check("the build succeeds with a DOI configured", run.returncode == 0,
          (run.stderr or run.stdout)[-800:])

    if run.returncode == 0:
        hist = (out / "history.html").read_text(encoding="utf-8")
        check("citation_doi is emitted",
              f'name="citation_doi" content="{FAKE_DOI}"' in hist)

        block = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', hist, re.S)
        ds = json.loads(block.group(1)) if block else {}
        check("the Dataset identifier is the DOI URL",
              ds.get("identifier") == f"https://doi.org/{FAKE_DOI}",
              str(ds.get("identifier")))

        # The DOI resolves to a Zenodo record whose title comes from
        # register_meta. If the page named the dataset differently, one
        # identifier would carry two names.
        sys.path.insert(0, str(ROOT))
        from tools import register_meta
        formal = register_meta.register_facts()["title"]
        check("the Dataset asserting the DOI carries the formal title",
              ds.get("name") == formal, str(ds.get("name")))
        check("citation_title is that same title",
              f'name="citation_title" content="{formal}"' in hist)

        llms = (out / "llms.txt").read_text(encoding="utf-8")
        check("llms.txt states the DOI", FAKE_DOI in llms)
        check("llms.txt has no unsubstituted placeholder", "{{" not in llms)
finally:
    shutil.rmtree(work, ignore_errors=True)

check("site.yaml is byte-identical to what it was before this test ran",
      cfg_path.read_text(encoding="utf-8") == original,
      "the real config was modified — this test must never write to it")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the site is correct with a DOI and without one")
