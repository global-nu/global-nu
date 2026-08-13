#!/usr/bin/env python3
"""The experiment list must exist once, and the pages must agree with it.

    ./.venv/bin/python3 tools/tests/test_experiments.py

Resources used to carry the list twice: once in experiments.yaml for the map,
once as hand-written tiles in resources.md. The YAML's header asked the two to
agree; nothing made them, and they drifted into thirteen entries with Daya Bay
and RENO missing while Double Chooz was present.

Five checks:
  1. every record satisfies the schema
  2. rank is unique within a role, so the order is total and not accidental
  3. every name in the YAML reaches the built resources.html
  4. every experiment name on the built page comes from the YAML
  5. every name in the YAML has a marker on the map, once per distinct site
Checks 3 and 4 are the same check in both directions on purpose: one catches a
name that was never rendered, the other catches a name hand-typed onto the
page. Check 5 is the map's own version of that drift test, but a plain set
comparison isn't enough for it: tools/make_map.py buckets co-located
experiments and fans a shared marker out into one <g class="map-exp"> per
experiment, and the same name can legitimately mark two different real
places — ICARUS ran at both Gran Sasso (Assergi, IT) and Fermilab (Batavia,
US), and both belong on the map. A set of names would still contain "ICARUS"
if one of those two vanished, so check 5 counts, per name, how many distinct
(city, country) pairs the YAML claims and how many map-exp markers the SVG
actually carries, and compares the two.
"""
from __future__ import annotations

import html
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import experiments                        # noqa: E402

PAGE = ROOT / "site" / "resources.html"
MAP = ROOT / "site-src" / "data" / "figures" / "map-experiments.svg"

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


# 1. schema — load() validates the real file, and rejects a malformed record.
# Built here rather than by mutating the real YAML.
try:
    records = experiments.load()
    check("load() accepts the real experiments.yaml", True)
except SystemExit as e:
    records = []
    check("load() accepts the real experiments.yaml", False, str(e))

bad_role = [{"name": "Bad Test Experiment", "role": "theta_13",
             "url": "https://example.invalid/", "source": "https://example.invalid/",
             "rank": 1}]
try:
    experiments._validate(bad_role)
    check("a record with an unknown role is rejected", False,
          "a typo'd role like theta_13 (for theta13) was silently accepted")
except SystemExit:
    check("a record with an unknown role is rejected", True)

bad_rank = [{"name": "Bad Test Experiment", "role": "mass",
             "url": "https://example.invalid/", "source": "https://example.invalid/",
             "rank": "one"}]
try:
    experiments._validate(bad_rank)
    check("a record with a non-integer rank is rejected", False,
          "a string rank was silently accepted")
except SystemExit:
    check("a record with a non-integer rank is rejected", True)

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
    page_html = PAGE.read_text(encoding="utf-8")
    tiles = re.findall(r'data-experiment="([^"]+)"', page_html)
    from_yaml = {r["name"] for r in records}
    on_page = set(tiles)

    missing = sorted(from_yaml - on_page)
    check("every experiment in the YAML reaches the page", not missing,
          f"absent from resources.html: {', '.join(missing[:8])}")

    extra = sorted(on_page - from_yaml)
    check("every experiment on the page comes from the YAML", not extra,
          f"on the page but not in the YAML: {', '.join(extra[:8])}")

# 5. the map SVG carries the right *number* of markers per name — not just
# the name at all. A record's expected marker count is how many distinct
# (city, country) pairs it holds across the YAML: 1 for Super-Kamiokande,
# whose two role-records name the same place, 2 for ICARUS, whose two
# role-records name different ones. Dropping one of ICARUS's two markers
# would still leave "ICARUS" in a set of names, which is why check 4/5's
# shape (sets, "3 & 4" above) isn't reused here.
if not MAP.exists():
    check("map-experiments.svg exists", False, "run ./.venv/bin/python3 tools/make_map.py first")
else:
    svg = MAP.read_text(encoding="utf-8")
    on_map = Counter(html.unescape(n) for n in re.findall(r'data-experiment="([^"]+)"', svg))

    expected_sites: dict[str, set[tuple[str, str]]] = {}
    for r in records:
        expected_sites.setdefault(r["name"], set()).add((r.get("city"), r.get("country")))
    expected_counts = {name: len(sites) for name, sites in expected_sites.items()}

    drifted = sorted(
        name for name, want in expected_counts.items()
        if on_map.get(name, 0) != want
    )
    detail = ", ".join(
        f'{name} (want {expected_counts[name]}, got {on_map.get(name, 0)})'
        for name in drifted[:8]
    )
    check("every experiment's distinct sites each have a marker on the map",
          not drifted, detail)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — {len(records)} experiments, named once")
