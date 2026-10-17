#!/usr/bin/env python3
"""No sync-conflict copies in anything that is built or published.

    ./.venv/bin/python3 tools/tests/test_no_conflict_copies.py

The project lives on an iCloud-synced Desktop. When a file is rewritten while
the sync is uploading it, the provider keeps both and names the second
"parameters 2.csv". In site/ such a copy would be committed by the daily job
and published; in the inputs it would be copied into the site. The pattern is
a space and a number before the extension.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = ["site", "site-draft", "site-src", "data-exports", "drafts", "tools"]
RX = re.compile(r" \d+(\.[^.]+)+$")
hits = [p.relative_to(ROOT).as_posix()
        for t in TREES if (ROOT / t).exists()
        for p in (ROOT / t).rglob("*")
        if p.is_file() and RX.search(p.name) and "__pycache__" not in p.parts]
for h in hits[:30]:
    print("  FAIL conflict copy: " + h)
if hits:
    sys.exit(1)
print(f"no conflict copies in {', '.join(t for t in TREES if (ROOT / t).exists())}")
