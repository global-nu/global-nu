#!/usr/bin/env python3
"""geocluster.cluster_by_distance — the single-linkage bucketing shared by
tools/make_map.py's experiments map and tools/news/figures.py's conference
map, so a change to the merge rule (or the complete-linkage alternative
make_map.py's own MERGE_DIST comment already contemplates) happens once,
not twice with nothing keeping the copies honest.

    ./.venv/bin/python3 tools/tests/test_geocluster.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import geocluster                    # noqa: E402

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


# Two points inside the threshold merge into one bucket.
groups = geocluster.cluster_by_distance([(0.0, 0.0), (1.0, 0.0)], merge_dist=2.0)
check("two points within the threshold merge into one bucket",
      groups == [[0, 1]] or groups == [[1, 0]], groups)

# Two points outside it stay apart.
groups = geocluster.cluster_by_distance([(0.0, 0.0), (10.0, 0.0)], merge_dist=2.0)
check("two points outside the threshold stay in separate buckets",
      sorted(len(g) for g in groups) == [1, 1], groups)

# Single-linkage chaining: A-B and B-C are each within the threshold, but
# A-C alone is not — all three still land in one bucket, because the chain
# through B connects them (this is the documented single- vs
# complete-linkage trade-off, not a bug).
groups = geocluster.cluster_by_distance(
    [(0.0, 0.0), (2.0, 0.0), (4.0, 0.0)], merge_dist=2.0)
check("a chain through an intermediate point merges all three (single-linkage)",
      len(groups) == 1 and sorted(groups[0]) == [0, 1, 2], groups)

# An isolated point comes back as a bucket of one, not dropped.
groups = geocluster.cluster_by_distance(
    [(0.0, 0.0), (100.0, 100.0)], merge_dist=2.0)
check("a point with nothing nearby is still returned, as a bucket of one",
      sorted(len(g) for g in groups) == [1, 1], groups)

# Every original index appears exactly once across all buckets — nothing
# dropped, nothing duplicated.
pts = [(float(i), 0.0) for i in range(6)]
groups = geocluster.cluster_by_distance(pts, merge_dist=0.5)
seen = sorted(i for g in groups for i in g)
check("every input index appears exactly once across the returned buckets",
      seen == list(range(6)), seen)

# The empty case does not crash and returns nothing.
check("no points yields no buckets",
      geocluster.cluster_by_distance([], merge_dist=1.0) == [])

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — shared clustering, exercised directly")
