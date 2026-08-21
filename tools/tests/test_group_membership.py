#!/usr/bin/env python3
"""The group listed on the site is the group, not a paper's author list.

    ./.venv/bin/python3 tools/tests/test_group_membership.py

Both the About page and the README used to head a section "The group" and then
print the six authors of the 2025 release. Two of those six are cosmologists
from Rome and Sheffield who collaborated on that paper; one member of the group
was missing entirely. The page named the wrong people as the group and left a
member off, which is the kind of error no test catches and everyone reads.

THE RULE, stated by Antonio Marrone on 2026-08-21 and enforced below: someone
belongs on the group list when they sign a release with a Bari affiliation —
Università di Bari or INFN Bari. Everyone else is a collaborator, named beside
the paper they joined and never in the list. Francesco Capozzi is on the list
having moved to L'Aquila; he is a member, and the affiliation printed beside
him is his current one, from INSPIRE.

Changing the membership means changing GROUP below, deliberately — which is the
point of pinning it here rather than trusting prose in two files to agree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Surname -> the affiliation the pages must print. Alphabetical, as the
# group's own papers sign.
GROUP = {
    "Capozzi": "L’Aquila and INFN LNGS",
    "Lisi": "INFN Bari",
    "Marcone": "Università di Bari and INFN Bari",
    "Marrone": "Università di Bari and INFN Bari",
    "Palazzo": "Università di Bari and INFN Bari",
}

# Named on papers, never in the group list.
COLLABORATORS = ("Giarè", "Melchiorri")

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


about = (ROOT / "site-src" / "content" / "about.md").read_text(encoding="utf-8")
readme = (ROOT / "README.md").read_text(encoding="utf-8")

# --- the About page --------------------------------------------------------

m = re.search(r'<p class="group-list">(.*?)</p>', about, re.S)
check("the About page marks its group list, so it can be checked at all", bool(m))

if m:
    block = " ".join(m.group(1).split())
    names = re.findall(r"<strong>([^<]+)</strong>", block)
    surnames = [n.split()[-1] for n in names]
    check("the About page lists exactly the group, in order",
          surnames == list(GROUP), f"found {surnames}")

    for surname, aff in GROUP.items():
        check(f"{surname} is printed with the right affiliation",
              re.search(re.escape(surname) + r"</strong> \(" + re.escape(aff) + r"\)",
                        block) is not None,
              f"expected “{aff}” after {surname} in: {block[:300]}")

    for outsider in COLLABORATORS:
        check(f"{outsider} is not inside the group list",
              outsider not in block, block[:300])
        check(f"{outsider} is still named on the page, beside their paper",
              outsider in about.replace(block, ""),
              "a collaborator dropped from the page altogether, rather than moved")

# The claim that had gone stale: the 2025 paper was called "the most recent
# release" after a 2026 paper had appeared.
check("the About page does not call the 2025 paper the most recent release",
      not re.search(r"most recent release[^.]{0,120}093006", about, re.S),
      "PRD 111 093006 (2025) is the most recent FULL release; 2026 is newer")

# --- the README ------------------------------------------------------------

m = re.search(r"## The group\s*\n+(.+)", readme)
check("the README has a group section", bool(m))
if m:
    line = m.group(1).strip()
    check("the README names the same five, in the same order",
          [s.strip(" .") for s in line.split(",")] == list(GROUP),
          f"found {line!r}")

for outsider in COLLABORATORS:
    check(f"the README does not present {outsider} as a member",
          not re.search(r"## The group\s*\n+[^\n]*" + re.escape(outsider), readme),
          "a collaborator on the membership line")

check("the README states the rule, so the next edit knows it",
      "Bari affiliation" in readme)

print(f"\n{checks - len(problems)}/{checks} checks passed")
if problems:
    print("failed: " + ", ".join(problems))
    raise SystemExit(1)
