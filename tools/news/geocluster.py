"""Single-linkage clustering by on-screen distance.

Shared by tools/make_map.py (the experiments map, drawn once at build time
from static YAML) and tools/news/figures.py (the conference map, redrawn
every morning from that morning's fetched records) so the merge rule — and
any future change to it, such as the complete-linkage alternative
make_map.py's own MERGE_DIST comment already contemplates — can only be
edited in one place rather than drifting between two copies that happen to
agree today. The two callers stay separate *generators*, running at
different times over different data; only the geometric test for "close
enough on screen to be treated as the same marker" is shared.
"""

from __future__ import annotations

import math


def cluster_by_distance(points: list[tuple[float, float]],
                        merge_dist: float) -> list[list[int]]:
    """Bucket point indices by single-linkage union-find.

    Two points land in the same bucket if SOME chain of pairwise distances,
    each at most `merge_dist`, connects them — not necessarily the two
    points themselves. (make_map.py's own comment on MERGE_DIST spells out
    what that costs on a long chain, and why complete-linkage — every
    pairwise distance within the bucket under the threshold — would close
    the gap at the price of a real clustering algorithm instead of one
    loop; not implemented here for the same reason it was not implemented
    there.)

    Returns each bucket as a list of the original indices into `points`, in
    first-encountered order; a point with nothing else nearby comes back as
    a bucket of one. Order between buckets is unspecified — callers that
    care (e.g. "draw small clusters first") should sort the result
    themselves.
    """
    n = len(points)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        xi, yi = points[i]
        for j in range(i + 1, n):
            xj, yj = points[j]
            if math.hypot(xi - xj, yi - yj) <= merge_dist:
                union(i, j)

    buckets: dict[int, list[int]] = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)
    return list(buckets.values())
