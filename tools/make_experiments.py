#!/usr/bin/env python3
"""Render the Resources tiles from site-src/data/experiments.yaml.

    ./.venv/bin/python3 tools/make_experiments.py

Output is an include, picked up by build.py's <!--include:experiments-tiles-->.
Nothing here decides what exists or in what order — that is tools/experiments.py,
which the map reads too.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import experiments                        # noqa: E402

OUT = ROOT / "site-src" / "data" / "figures" / "experiments-tiles.html"


COLUMNS = 4


def _balanced(groups: list, ncols: int = COLUMNS) -> list[list]:
    """Deal the groups into ncols columns of near-equal height.

    A tile is about as tall as its entries plus a fixed overhead (heading,
    padding, the gap below), so the weight is 2 per entry + 3. Every deal is
    tried -- there are a handful of tiles -- and the one whose tallest column
    is shortest wins; inside a column the curated order is kept.
    """
    from itertools import product

    weight = [2 * len(g[2]) + 3 for g in groups]
    best, best_key = None, None
    for deal in product(range(ncols), repeat=len(groups)):
        load = [0] * ncols
        for w, c in zip(weight, deal):
            load[c] += w
        key = (max(load), sorted(load, reverse=True), deal)
        if best_key is None or key < best_key:
            best, best_key = deal, key
    cols: list[list] = [[] for _ in range(ncols)]
    for g, c in zip(groups, best):
        cols[c].append(g)
    return [c for c in cols if c]


def tiles_html() -> str:
    parts = ['<div class="tiles tiles--cols reveal">']
    columns = _balanced(list(experiments.ordered()))
    for col in columns:
      for n, (_key, heading, group) in enumerate(col):
        parts.append('<article class="tile"' + (' data-first' if n == 0 else '') + '>')
        parts.append(f'<h3>{html.escape(heading)}</h3>')
        parts.append('<ul class="list">')
        for r in group:
            name = html.escape(r["name"])
            parts.append(
                f'<li data-experiment="{name}">'
                f'<b><a href="{html.escape(r["url"])}">{name}</a></b>'
                f'<span>{html.escape(experiments.label(r))}</span></li>')
        parts.append("</ul></article>")
    parts.append("</div>")
    return "\n".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tiles_html(), encoding="utf-8")
    total = sum(len(g) for _k, _h, g in experiments.ordered())
    print(f"tiles: {total} experiments -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
