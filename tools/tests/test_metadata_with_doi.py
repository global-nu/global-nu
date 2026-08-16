#!/usr/bin/env python3
"""Build the site with a DOI configured, and check every claim it enables.

    ./.venv/bin/python3 tools/tests/test_metadata_with_doi.py

The real DOI arrives only after the Zenodo deposit, and the moment after a
permanent identifier is minted is the worst moment to discover that the build
mishandles it. This builds into a throwaway tree with a placeholder DOI in
site.yaml, so both states — with and without — are covered before the deposit
is made. It never touches site/ and never writes a DOI into the real config.

site.yaml is edited by text substitution, not by parsing it into a dict and
dumping it back: a round trip through yaml.safe_dump would silently strip
every comment in the file, including the ones explaining why an empty DOI (or
an empty GoatCounter code) must make the build emit nothing rather than an
empty tag. The original bytes are saved to a temp file before anything is
touched, so a crash mid-test still leaves a way to recover the file by hand,
and the restore in `finally` is a plain byte-for-byte write-back.
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

# Save the untouched bytes to disk *before* editing anything in place, so a
# crash between the edit and the restore below still leaves a copy to recover
# from — the hand-written comments in site.yaml are not reproducible from a
# yaml.safe_dump round trip.
backup_dir = Path(tempfile.mkdtemp(prefix="gnu-doi-backup-"))
backup_path = backup_dir / "site.yaml.orig"
backup_path.write_text(original, encoding="utf-8")

work = Path(tempfile.mkdtemp(prefix="gnu-doi-"))

try:
    needle = 'doi: ""'
    check("the empty doi: \"\" line is present exactly once",
          original.count(needle) == 1,
          f"found {original.count(needle)} occurrences — refusing to guess which one")

    edited = original.replace(needle, f'doi: "{FAKE_DOI}"', 1)
    cfg_path.write_text(edited, encoding="utf-8")

    run = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python3"), "build.py",
         "--out", str(work), "--no-images"],
        cwd=ROOT, capture_output=True, text=True)
    check("the build succeeds with a DOI configured", run.returncode == 0,
          (run.stderr or run.stdout)[-800:])

    if run.returncode == 0:
        hist = (work / "history.html").read_text(encoding="utf-8")
        check("citation_doi is emitted",
              f'name="citation_doi" content="{FAKE_DOI}"' in hist)

        block = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', hist, re.S)
        ds = json.loads(block.group(1)) if block else {}
        check("the Dataset identifier is the DOI URL",
              ds.get("identifier") == f"https://doi.org/{FAKE_DOI}",
              str(ds.get("identifier")))

        llms = (work / "llms.txt").read_text(encoding="utf-8")
        check("llms.txt states the DOI", FAKE_DOI in llms)
        check("llms.txt has no unsubstituted placeholder", "{{" not in llms)
finally:
    cfg_path.write_text(original, encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(backup_dir, ignore_errors=True)

restored = cfg_path.read_text(encoding="utf-8")
check("site.yaml is byte-identical to what it was before this test ran",
      restored == original,
      "the real config was left modified — fix this before committing")
if restored != original:
    # Loud enough that it cannot be scrolled past: this is the one failure
    # mode that corrupts a file other tests and Antonio's editor both trust.
    print("  !!!! site-src/site.yaml was NOT restored correctly !!!!",
          file=sys.stderr)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the site is correct with a DOI and without one")
