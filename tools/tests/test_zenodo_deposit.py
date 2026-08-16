#!/usr/bin/env python3
"""Check the Zenodo package before anything permanent is minted.

    ./.venv/bin/python3 tools/tests/test_zenodo_deposit.py

A DOI cannot be withdrawn. Everything a deposit will assert is checked here,
against the register itself, while it is still only a directory on disk.
"""
from __future__ import annotations

import json
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

    rel = {r["identifier"] for r in meta.get("related_identifiers", [])}
    check("the deposit is bound to the 2025 paper",
          "10.1103/PhysRevD.111.093006" in rel, str(sorted(rel)))
    check("the deposit is bound to the site",
          any("global-nu.org" in r for r in rel), str(sorted(rel)))

    # The README must describe exactly the columns the files actually carry,
    # and it is generated from FIELD_DOCS so it cannot drift. Check that the
    # generation really happened rather than trusting it.
    readme = (work / "README.md").read_text(encoding="utf-8")
    for field, _ in make_history_data.FIELD_DOCS:
        check(f"README documents the column {field}", f"`{field}`" in readme)
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
