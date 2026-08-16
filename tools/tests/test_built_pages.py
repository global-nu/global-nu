#!/usr/bin/env python3
"""Check that no page ships unconverted Markdown.

    ./.venv/bin/python3 tools/tests/test_built_pages.py

python-markdown treats a block-level raw HTML element as opaque: everything
inside a hand-written <div> is passed through untouched. A heading written as
`## Contact` inside one does not become an <h2>, it becomes the characters
`## Contact` on a published page — and a link written as [text](url) stays
literal, so a reader sees the syntax and the navigation is simply gone.

That is exactly what about.html shipped: four literal headings and a dead link
to the parameter history. The fix is the project's own `:::` fence, whose
wrappers are substituted after conversion precisely so this cannot happen
(see expand_fences in build.py). This test is the guard, because the failure is
silent — the build succeeds, the page renders, and only a reader notices.

Code blocks are excluded: `## ` inside <pre> or <code> is content, not a
mistake.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"

# Markdown that should never survive into a built page.
LEAKS = [
    ("ATX heading", re.compile(r"^#{1,6} .*", re.M)),
    ("link", re.compile(r"\[[^\]\n]+\]\([^)\s]+\)")),
    ("bullet list item", re.compile(r"^[*+-] .*", re.M)),
    ("ordered list item", re.compile(r"^\d+\. .*", re.M)),
]

# <pre>…</pre> and <code>…</code> hold literal text on purpose.
CODE = re.compile(r"<pre\b.*?</pre>|<code\b.*?</code>", re.S | re.I)

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


# rglob, not glob: site/digest/ holds the archive's day and month pages, and
# a page generated fresh every morning is exactly the kind of thing to ship
# with a leak — a flat glob silently never looked at them.
pages = sorted(SITE.rglob("*.html"))
if not pages:
    check("site/ holds built pages", False, "run ./.venv/bin/python3 build.py first")
else:
    for page in pages:
        text = CODE.sub("", page.read_text(encoding="utf-8"))
        found = []
        for name, pattern in LEAKS:
            for m in pattern.finditer(text):
                snippet = " ".join(m.group(0).split())[:60]
                found.append(f"{name}: {snippet}")
        detail = "; ".join(found[:4])
        if len(found) > 4:
            detail += f"  (+{len(found) - 4} more)"
        check(f"{page.name} converts all of its Markdown", not found, detail)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — every page converted its Markdown")
