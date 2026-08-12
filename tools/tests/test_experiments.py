#!/usr/bin/env python3
"""The experiment list must exist once, and the pages must agree with it.

    ./.venv/bin/python3 tools/tests/test_experiments.py

Resources used to carry the list twice: once in experiments.yaml for the map,
once as hand-written tiles in resources.md. The YAML's header asked the two to
agree; nothing made them, and they drifted into thirteen entries with Daya Bay
and RENO missing while Double Chooz was present.

Four checks:
  1. every record satisfies the schema
  2. rank is unique within a role, so the order is total and not accidental
  3. every name in the YAML reaches the built resources.html
  4. every experiment name on the built page comes from the YAML
Checks 3 and 4 are the same check in both directions on purpose: one catches a
name that was never rendered, the other catches a name hand-typed onto the
page.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import experiments                        # noqa: E402

PAGE = ROOT / "site" / "resources.html"

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


records = experiments.load()

# 1. schema
roles = {k for k, _ in experiments.ROLES}
bad = [f'{r.get("name", "?")}: {why}'
       for r in records
       for why in [
           None if r.get("role") in roles else f'unknown role {r.get("role")!r}',
           # A record may carry no status at all — that is the honest outcome
           # when a collaboration's own page does not state one. What it must
           # not carry is a status outside the controlled vocabulary.
           None if "status" not in r or r.get("status") in experiments.STATUSES
           else f'unknown status {r.get("status")!r}',
           None if isinstance(r.get("rank"), int) else "rank is not an integer",
           None if r.get("url") else "no url",
           None if r.get("source") else "no source recorded for its status",
       ] if why]
check("every record satisfies the schema", not bad, "; ".join(bad[:5]))

# 2. rank unique within a role
dupes = []
for key, _heading, group in experiments.ordered():
    seen: dict[int, str] = {}
    for r in group:
        if r["rank"] in seen:
            dupes.append(f'{key}: {seen[r["rank"]]} and {r["name"]} share rank {r["rank"]}')
        seen[r["rank"]] = r["name"]
check("rank is unique within each role", not dupes, "; ".join(dupes[:5]))

# 3 & 4. the page and the YAML agree, both ways
if not PAGE.exists():
    check("resources.html exists", False, "run ./.venv/bin/python3 build.py first")
else:
    html = PAGE.read_text(encoding="utf-8")
    tiles = re.findall(r'data-experiment="([^"]+)"', html)
    from_yaml = {r["name"] for r in records}
    on_page = set(tiles)

    missing = sorted(from_yaml - on_page)
    check("every experiment in the YAML reaches the page", not missing,
          f"absent from resources.html: {', '.join(missing[:8])}")

    extra = sorted(on_page - from_yaml)
    check("every experiment on the page comes from the YAML", not extra,
          f"on the page but not in the YAML: {', '.join(extra[:8])}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — {len(records)} experiments, named once")
