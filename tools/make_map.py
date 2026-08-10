#!/usr/bin/env python3
"""Draw the world map of experiments into site-src/data/figures/map-experiments.svg.

    ./.venv/bin/python3 tools/make_map.py

Geometry comes from tools/news/worldmap.py, generated once from Natural Earth
(public domain) by the personal site's make_worldmap.py and copied here.

Positions are looked up, not typed: each entry of site-src/data/experiments.yaml
names a place in words and tools/news/geocode.py resolves it through
OpenStreetMap, caching the answer in var/news/geocache.json. An entry that
cannot be resolved is reported and left off the map — a dot in roughly the
right country is worse than no dot, because a reader cannot tell the two
apart.

Colours are CSS variables so the map follows the theme, and every marker
carries an SVG <title> with the name, the place and what kind of experiment it
is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.news import geocode                      # noqa: E402
from tools.news import worldmap as wm               # noqa: E402

DATA = ROOT / "site-src" / "data" / "experiments.yaml"
OUT = ROOT / "site-src" / "data" / "figures" / "map-experiments.svg"

KINDS = [
    ("reactor", "Reactor", "var(--dec-2)"),
    ("accelerator", "Accelerator", "var(--dec-1)"),
    ("natural", "Atmospheric, solar, astrophysical", "var(--dec-5)"),
    ("mass", "Absolute mass and 0νββ", "var(--dec-4)"),
]
COLOUR = {k: c for k, _, c in KINDS}


def main() -> None:
    entries = yaml.safe_load(DATA.read_text(encoding="utf-8"))["experiments"]

    placed, missing = [], []
    for e in entries:
        spot = geocode.locate(e["city"], e["country"])
        if spot is None:
            missing.append(f'{e["name"]} ({e["city"]}, {e["country"]})')
            continue
        lon, lat = spot
        x, y = wm.project(lon, lat)
        placed.append((e, x, y))

    if not placed:
        sys.exit("nothing could be located — is the network up? "
                 "(a rerun uses the cache and needs none)")

    # Cropped north of the far south: an equirectangular Antarctica is a band
    # the width of the world and no experiment on this list sits on it, except
    # IceCube — which is why the crop stops at 78°S rather than higher.
    top = wm.project(0, 84)[1]
    bottom = wm.project(0, -78)[1]
    h = bottom - top
    w = wm.WIDTH

    parts = [
        f'<svg viewBox="0 {top:.0f} {w:.0f} {h:.0f}" role="img" '
        'aria-label="World map of the neutrino experiments listed on this page">',
        "<title>Where the experiments are</title>",
        f'<path d="{wm.LAND_PATH}" fill="var(--surface-2)" stroke="var(--line-strong)" '
        'stroke-width="0.6" vector-effect="non-scaling-stroke"/>',
    ]

    # Draw a halo first so overlapping sites stay legible, then the dot.
    for e, x, y in placed:
        colour = COLOUR.get(e["kind"], "var(--accent)")
        title = f'{e["name"]} — {e["city"]}, {e["country"]}'
        if e.get("note"):
            title += f' · {e["note"]}'
        parts.append(
            f'<g class="map-pin"><title>{title}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{colour}" opacity=".18"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{colour}" '
            f'stroke="var(--bg)" stroke-width="1.1" paint-order="stroke"/></g>')

    parts.append("</svg>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")

    print(f"map: {len(placed)} experiments placed -> {OUT.relative_to(ROOT)}")
    for m in missing:
        print(f"  ! not located, left off the map: {m}")

    legend = " ".join(f'<span><i style="background:{c}"></i>{label}</span>'
                      for _, label, c in
                      [(k, l, c) for k, l, c in KINDS
                       if any(e["kind"] == k for e, _, _ in placed)])
    (OUT.parent / "map-experiments-legend.svg").write_text(
        f'<div class="legend legend--chart">{legend}</div>', encoding="utf-8")
    print("legend written alongside")


if __name__ == "__main__":
    main()
