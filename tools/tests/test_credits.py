#!/usr/bin/env python3
"""A credit line must credit, not enumerate.

    ./.venv/bin/python3 tools/tests/test_credits.py

Commons stores whatever the uploader put in the Artist field. For
File:JUNO Detector with labels.jpg that is the collaboration's entire author
list, and it was printed under the photograph. The licence asks for
attribution in a reasonable manner; seven hundred names in a caption is not
reasonable, and the full field stays in photos.yaml with a link to the file's
page on Commons, which is where attribution is properly discharged.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.fetch_commons_images import short_author   # noqa: E402

fail: list[str] = []
checks = 0


def check(label: str, got: str, want: str) -> None:
    global checks
    checks += 1
    if got == want:
        print(f"  ok   {label}")
    else:
        fail.append(label)
        print(f"  FAIL {label}\n         got:  {got!r}\n         want: {want!r}")


check("a collaboration keeps its name and drops its roster",
      short_author("JUNO Collaboration: Angel Abusleme, Thomas Adam, "
                   "Shakeel Ahmad, Rizwan Ahmed, Sebastiano Aiello"),
      "JUNO Collaboration")

check("a collaboration named without a colon is kept whole",
      short_author("Borexino Collaboration"),
      "Borexino Collaboration")

check("one photographer is left alone",
      short_author("Christopher Michel"),
      "Christopher Michel")

check("two names are left alone",
      short_author("Fermilab, Reidar Hahn"),
      "Fermilab, Reidar Hahn")

check("exactly three names are left alone",
      short_author("Ann Alpha, Ben Beta, Carl Gamma"),
      "Ann Alpha, Ben Beta, Carl Gamma")

check("more than three names collapse to the first",
      short_author("Ann Alpha, Ben Beta, Carl Gamma, Dana Delta"),
      "Ann Alpha et al.")

check("an empty field stays empty",
      short_author(""),
      "")

print()
if fail:
    print(f"{len(fail)} check(s) failed")
    sys.exit(1)
print(f"all {checks} checks pass — credits name a source, not a roster")
