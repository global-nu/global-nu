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


def tiles_html() -> str:
    parts = ['<div class="tiles reveal">']
    for _key, heading, group in experiments.ordered():
        parts.append('<article class="tile">')
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
