#!/usr/bin/env python3
"""Check the Zenodo package before anything permanent is minted.

    ./.venv/bin/python3 tools/tests/test_zenodo_deposit.py

A DOI cannot be withdrawn. Everything a deposit will assert is checked here,
against the register itself, while it is still only a directory on disk.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import register_meta                          # noqa: E402
import make_zenodo_deposit                                # noqa: E402
import make_history_data                                  # noqa: E402

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


work = Path(tempfile.mkdtemp(prefix="gnu-zenodo-"))
try:
    meta = make_zenodo_deposit.build_package(work)
    facts = register_meta.register_facts()

    for name in ("history.json", "history.csv", "README.md", "LICENSE.txt",
                 "zenodo.json"):
        check(f"package contains {name}", (work / name).exists())

    check("upload_type is dataset", meta["upload_type"] == "dataset")
    check("the title carries the register's real year span",
          f"({facts['years'][0]}–{facts['years'][1]})" in meta["title"],
          meta["title"])

    creators = meta.get("creators") or []
    check("one creator, with an ORCID", len(creators) == 1 and creators[0].get("orcid"),
          str(creators))
    check("the ORCID is Antonio's",
          creators and creators[0].get("orcid") == "0000-0001-6096-1880",
          str(creators))

    check("licence is CC BY 4.0", meta.get("license") == "cc-by-4.0",
          str(meta.get("license")))

    check("the title is the one register_meta computes",
          meta["title"] == facts["title"],
          "the page asserts this record's DOI; it must name it identically")

    # The relation, not just the identifier. A related identifier states what
    # this dataset IS with respect to that work, permanently. "isSupplementTo"
    # a paper would claim the register is that article's supplementary
    # material; it is a compilation drawing on some twenty-five papers by
    # three groups, and the 2025 Bari paper is one source among them. Checking
    # only for presence cannot tell a true relation from a false one.
    rel = {r["identifier"]: r["relation"]
           for r in meta.get("related_identifiers", [])}
    check("the 2025 paper is referenced, not supplemented",
          rel.get("10.1103/PhysRevD.111.093006") == "references", str(rel))
    check("the preprint is referenced, not supplemented",
          rel.get("arXiv:2503.07752") == "references", str(rel))
    site_rel = {v for k, v in rel.items() if "global-nu.org" in k}
    check("the site page documents the deposit",
          site_rel == {"isDocumentedBy"}, str(rel))
    check("no related identifier claims the deposit supplements a work",
          "isSupplementTo" not in rel.values(), str(rel))

    # The README must describe exactly the columns the files actually carry,
    # and it is generated from FIELD_DOCS so it cannot drift. Check that the
    # generation really happened rather than trusting it.
    readme = (work / "README.md").read_text(encoding="utf-8")
    for field, _ in make_history_data.FIELD_DOCS:
        check(f"README documents the column {field}", f"`{field}`" in readme)
    # FIELD_DOCS is written as HTML for the web page, so it carries entities
    # as well as tags. A deposit README is read as plain text, and "&sigma;"
    # on a permanent record is simply wrong where the word or the letter
    # belongs. This became worth enforcing when the interval columns were
    # added on 2026-08-16: their documentation is full of entities.
    check("README carries no undecoded HTML entities",
          not re.search(r"&[a-zA-Z]+;|&#\d+;", readme),
          "; ".join(sorted(set(re.findall(r"&[a-zA-Z]+;|&#\d+;", readme)))[:6]))

    check("README carries no HTML tags from the page version",
          "<code>" not in readme and "<a " not in readme,
          "FIELD_DOCS is HTML for the web page; it must be converted for a text README")

    check("the deposited JSON is the published export",
          (work / "history.json").read_bytes() == register_meta.EXPORT.read_bytes())

    payload = json.loads((work / "zenodo.json").read_text(encoding="utf-8"))
    check("zenodo.json holds the same metadata that was returned",
          payload.get("metadata", payload) == meta)
finally:
    shutil.rmtree(work, ignore_errors=True)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the package says what the register says")
