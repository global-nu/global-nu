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

Two structural problems that were cosmetic at 13 experiments are real at 44:

  * Several sites host more than one experiment, and their markers coincide.
    main() buckets by rounded projected position and draws one <g
    class="map-pin"> per bucket. A bucket holding more than one experiment
    carries data-fan="1", a visible count badge, and hidden <g class="map-exp">
    children — one per experiment, positioned on a small circle around the
    parent — for map.js (a later piece of work) to reveal on click. A bucket
    holding one experiment still gets a single, always-visible map-exp child,
    so the markup is uniform whether or not a site fans out.

  * IceCube sits at the South Pole, off the bottom of the equirectangular
    frame this map otherwise draws (the frame is cropped at 78°S — see the
    comment at CROP_SOUTH_LAT below). Extending the main frame to -90° is not
    an option: an equirectangular projection stretches the pole into a line as
    wide as the world, turning Antarctica into an empty band about a sixth of
    the map's height. Instead, _south_polar_coastline() recovers Antarctica's
    shape by inverting worldmap.py's projection back to (lon, lat) — exact for
    an equirectangular map — and _azeq() reprojects the result azimuthally
    about the pole, into a small inset drawn in a corner of the frame. IceCube
    gets the same <g class="map-pin"> markup there as everywhere else, so
    filtering and any per-experiment card need no special case for it.
"""

from __future__ import annotations

import html
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import experiments                        # noqa: E402
from tools.fetch_commons_images import short_author    # noqa: E402
from tools.news import geocode                        # noqa: E402
from tools.news import worldmap as wm                 # noqa: E402

OUT = ROOT / "site-src" / "data" / "figures" / "map-experiments.svg"

KINDS = [
    ("reactor", "Reactor", "var(--dec-2)"),
    ("accelerator", "Accelerator", "var(--dec-1)"),
    ("natural", "Atmospheric, solar, astrophysical", "var(--dec-5)"),
    ("mass", "Absolute mass and 0νββ", "var(--dec-4)"),
]
COLOUR = {k: c for k, _, c in KINDS}
KIND_ORDER = {k: i for i, (k, _, _) in enumerate(KINDS)}
KIND_LABEL = {k: label for k, label, _ in KINDS}

PHOTOS_FILE = ROOT / "site-src" / "data" / "photos.yaml"

# Marker geometry, in viewBox units (the frame is 720 wide).
HALO_R = 6.5
DOT_R = 3.2
FAN_R = 10.0            # radius of the circle fanned children sit on
CLUSTER_HALO_R = 8.0
CLUSTER_R = 5.4

# Two experiments this close project to the same dot: one solid marker (r =
# DOT_R) would sit almost entirely on top of the other, hiding whichever was
# drawn first as completely as if they shared one coordinate. At 13 sites this
# never came up; at 44 it does — Kamioka's five-experiment cluster and T2K
# (Tokai) and K2K (Tsukuba), ~100 km away in reality, project within a couple
# of viewBox units of each other. Bucketing on distance rather than exact
# rounded equality catches these the same way the brief's literal recipe
# catches true coincidences, without merging anything that reads as clearly
# separate once drawn — the next-closest pair of *distinct* markers on the
# current data ends up a comfortable 7.5 units apart. This never changes what
# a marker claims: each experiment keeps its own looked-up city in its own
# <title>; only which markers share one pin depends on it.
#
# The merge below is single-linkage (union-find): it chains through
# intermediaries rather than bounding a cluster's overall spread. Tokai and
# Tsukuba are themselves 6.7 units apart — over MERGE_DIST — and end up in
# Kamioka's bucket anyway, each separately close enough to Hida. On today's
# data that's harmless (5 of the 7 members sit exactly at Hida, so the
# centroid lands under a unit away from it), but nothing here stops a longer
# chain from dragging a future centroid noticeably away from every member it
# claims to represent. A complete-linkage rule — only merge when *every*
# pairwise distance in the resulting cluster stays within MERGE_DIST — would
# close that gap, at the cost of turning this back into a real clustering
# algorithm instead of one loop; it would also, on today's data, pull K2K
# back out of the Kamioka bucket into a lone marker sitting 5.8 units from
# a much larger one, which is close to the original overlap this constant
# exists to fix. Left as single-linkage deliberately; revisit if the roster
# grows enough for a chain to actually misplace a centroid.
MERGE_DIST = 2 * DOT_R

# The main frame stops here: an equirectangular Antarctica south of this
# would be a band as wide as the map and empty except for IceCube, which is
# why it goes in a polar inset instead (see the module docstring).
CROP_SOUTH_LAT = -78.0

# The inset spans this latitude down to the pole...
INSET_CUTOFF_LAT = -60.0
# ...except for points essentially AT the pole: worldmap.py's polygon closes
# itself by running along y=360 (lat=-90) from one edge of the equirectangular
# frame to the other, standing in for the pole itself, which has no single
# x-coordinate in that projection. Reprojected azimuthally, that fake segment
# becomes a spike from the rim straight through the inset's centre and back
# out — an artefact of the closure, not a coastline. Points this close to -90
# are dropped rather than drawn.
INSET_POLE_ARTIFACT_LAT = -89.9
INSET_R = 42.0
INSET_MARGIN = 16.0


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "site"


def _esc(text: str) -> str:
    """Safe for both an XML attribute value and element text — none of the
    current records need it (checked against experiments.yaml), but a name,
    city or note is hand-typed prose and a future one might."""
    return html.escape(text, quote=True)


def _title(e: dict) -> str:
    title = f'{_esc(e["name"])} — {_esc(e["city"])}, {_esc(e["country"])}'
    if e.get("note"):
        title += f' · {_esc(e["note"])}'
    return title


def _load_photos() -> dict[str, dict]:
    """Accepted photographs from photos.yaml, indexed by subject — only
    entries marked `keep`, the same gate the (now-removed) gallery used, so a
    picture that failed review there still cannot appear on the map's card.
    Missing or unreadable is not fatal: the map is drawn either way, just
    without pictures, which is the honest outcome when the manifest cannot
    be trusted rather than a build that refuses to run."""
    if not PHOTOS_FILE.exists():
        return {}
    doc = yaml.safe_load(PHOTOS_FILE.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for p in doc.get("photos", []):
        if p.get("status") == "keep" and p.get("subject") not in out:
            out[p["subject"]] = p
    return out


PHOTOS = _load_photos()


def _exp_attrs(e: dict) -> str:
    """Extra data-* attributes on a <g class="map-exp">, everything map.js
    needs to build the card without a second fetch: where the experiment is,
    what it constrains, whether it is still running, a link out, and — for
    the few experiments with an accepted photograph — the picture and its
    credit. Kept apart from <title>, which exists for the no-JS/hover case
    and is prose, not a record meant to be parsed back apart.

    The credit is built from short_author(), not from photos.yaml's own
    author_short field: that field was itself produced by short_author() at
    fetch time, but computing it again here keeps the map's one and only
    source of that logic in tools/fetch_commons_images.py rather than
    trusting a value that could go stale if the manifest were hand-edited.
    """
    bits = [
        f' data-kind-label="{_esc(KIND_LABEL.get(e["kind"], e["kind"]))}"',
        f' data-place="{_esc(e["city"])}, {_esc(e["country"])}"',
        f' data-url="{_esc(e["url"])}"',
    ]
    if e.get("note"):
        bits.append(f' data-note="{_esc(e["note"])}"')
    status = e.get("status")
    if status:
        bits.append(f' data-status="{_esc(experiments.STATUS_LABEL.get(status, status))}"')

    p = PHOTOS.get(e.get("photo")) if e.get("photo") else None
    if p and p.get("file") and p.get("page") and p.get("licence"):
        author = short_author(p.get("author") or "") or "unknown author"
        bits.append(f' data-photo="images/{_esc(p["file"])}"')
        bits.append(f' data-photo-alt="{_esc(p.get("caption") or p["subject"])}"')
        bits.append(f' data-photo-author="{_esc(author)}"')
        bits.append(f' data-photo-licence="{_esc(p["licence"])}"')
        bits.append(f' data-photo-licence-url="{_esc(p.get("licence_url") or "")}"')
        bits.append(f' data-photo-page="{_esc(p["page"])}"')
    return "".join(bits)


def _marker(cx: float, cy: float, colour: str) -> str:
    """The halo-and-dot pair every experiment is drawn with."""
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{HALO_R}" fill="{colour}" opacity=".18"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{DOT_R}" fill="{colour}" '
        f'stroke="var(--bg)" stroke-width="1.1" paint-order="stroke"/>'
    )


def _representative_place(group: list[dict]) -> tuple[str, str, bool]:
    """The (city, country) named in a bucket's combined title, and whether
    every member actually shares it. MERGE_DIST can bucket experiments that
    are close on the map but not in the same city (T2K's Tokai and K2K's
    Tsukuba join Kamioka's Hida) — the most common place stands in for the
    bucket's slug, but the title says "near" rather than "at" when the group
    isn't all one place, so it never claims a precision the data doesn't have."""
    places = [(e["city"], e["country"]) for e in group]
    counts: dict[tuple[str, str], int] = {}
    for p in places:
        counts[p] = counts.get(p, 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1])[0]
    return best[0], best[1], len(counts) == 1


def _render_pin(cx: float, cy: float, group: list[dict]) -> str:
    """One <g class="map-pin"> for a bucket of one or more co-located
    experiments, already deduplicated by name."""
    city, country, same_city = _representative_place(group)
    site = _slug(city)
    kinds = sorted({e["kind"] for e in group}, key=lambda k: KIND_ORDER.get(k, 99))
    names = "|".join(_esc(e["name"]) for e in group)

    if len(group) == 1:
        e = group[0]
        colour = COLOUR.get(e["kind"], "var(--accent)")
        return (
            f'<g class="map-pin" data-site="{site}" data-kinds="{" ".join(kinds)}" '
            f'data-names="{names}"><title>{_title(e)}</title>'
            f'<g class="map-exp" data-experiment="{_esc(e["name"])}" data-kind="{e["kind"]}"'
            f'{_exp_attrs(e)}><title>{_title(e)}</title>{_marker(cx, cy, colour)}</g></g>'
        )

    n = len(group)
    where = f'{_esc(city)}, {_esc(country)}' if same_city else f'near {_esc(city)}, {_esc(country)}'
    combined = f'{n} experiments — {where}: ' + ", ".join(_esc(e["name"]) for e in group)
    parts = [
        f'<g class="map-pin" data-fan="1" data-site="{site}" '
        f'data-kinds="{" ".join(kinds)}" data-names="{names}">'
        f'<title>{combined}</title>',
        f'<g class="map-pin__cluster">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CLUSTER_HALO_R}" fill="var(--accent)" opacity=".18"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CLUSTER_R}" fill="var(--accent)" '
        f'stroke="var(--bg)" stroke-width="1.1" paint-order="stroke"/>'
        f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-family="var(--mono)" font-size="5.6" fill="var(--on-accent)">{n}</text></g>',
    ]
    for i, e in enumerate(group):
        angle = math.radians(-90 + i * 360 / n)
        fx = cx + FAN_R * math.cos(angle)
        fy = cy + FAN_R * math.sin(angle)
        colour = COLOUR.get(e["kind"], "var(--accent)")
        parts.append(
            f'<g class="map-exp" data-experiment="{_esc(e["name"])}" data-kind="{e["kind"]}"'
            f'{_exp_attrs(e)} hidden=""><title>{_title(e)}</title>{_marker(fx, fy, colour)}</g>'
        )
    parts.append("</g>")
    return "".join(parts)


def _south_polar_coastline(
    land_path: str,
    cutoff_lat: float = INSET_CUTOFF_LAT,
    pole_artifact_lat: float = INSET_POLE_ARTIFACT_LAT,
) -> list[list[tuple[float, float]]]:
    """Recover the part of worldmap.py's coastline south of cutoff_lat, as
    (lon, lat) subpaths.

    LAND_PATH is a sequence of closed subpaths ("M x,y x,y ... Z", every pair
    absolute, no curves — worldmap.py's own docstring gives the forward
    projection: x=(lon+180)*720/360, y=(90-lat)*360/180). Equirectangular is
    exact to invert, so this is exact too:  lon = x/2 - 180, lat = 90 - y/2.
    """
    subpaths = []
    for raw in re.findall(r"M([^M]+)", land_path):
        raw = raw.rstrip().rstrip("Z")
        pts = []
        for tok in raw.split():
            xs, ys = tok.split(",")
            x, y = float(xs), float(ys)
            lon = x / 2.0 - 180.0
            lat = 90.0 - y / 2.0
            if pole_artifact_lat < lat <= cutoff_lat:
                pts.append((lon, lat))
        if len(pts) >= 3:
            subpaths.append(pts)
    return subpaths


def _azeq(lon: float, lat: float, cutoff_lat: float, r: float) -> tuple[float, float]:
    """Azimuthal-equidistant projection about the south pole: distance from
    the pole maps linearly onto [0, r], lon=0 points up, angle grows
    clockwise. lon=180 and lon=-180 land on the same point, as they must."""
    colat = 90.0 + lat                      # 0 at the pole, 90+cutoff_lat at the rim
    span = 90.0 + cutoff_lat
    frac = colat / span
    theta = math.radians(lon)
    return r * frac * math.sin(theta), -r * frac * math.cos(theta)


def _render_south_pole_inset(cx0: float, cy0: float, icecube: dict, lon: float, lat: float) -> str:
    coastline = _south_polar_coastline(wm.LAND_PATH)
    d = " ".join(
        "M" + " ".join(f"{x:.2f},{y:.2f}" for x, y in
                        (_azeq(lo, la, INSET_CUTOFF_LAT, INSET_R) for lo, la in sub)) + "Z"
        for sub in coastline
    )
    dx, dy = _azeq(lon, lat, INSET_CUTOFF_LAT, INSET_R)
    colour = COLOUR.get(icecube["kind"], "var(--accent)")
    clip_id = f'polar-clip-{_slug(icecube["name"])}'  # unique per entry, in case a second one ever joins IceCube here

    box = INSET_R + 6
    parts = [
        f'<g class="map-inset" transform="translate({cx0:.1f},{cy0:.1f})">',
        "<title>South Pole</title>",
        f'<rect x="{-box:.1f}" y="{-box:.1f}" width="{2*box:.1f}" height="{2*box+14:.1f}" '
        'rx="5" fill="var(--surface)" stroke="var(--line-strong)" stroke-width="0.6"/>',
        f'<clipPath id="{clip_id}"><circle cx="0" cy="0" r="{INSET_R}"/></clipPath>',
        f'<g clip-path="url(#{clip_id})">'
        f'<circle cx="0" cy="0" r="{INSET_R}" fill="var(--bg)"/>'
        f'<path d="{d}" fill="var(--surface-2)" stroke="var(--line-strong)" '
        'stroke-width="0.6" vector-effect="non-scaling-stroke"/></g>',
        f'<circle cx="0" cy="0" r="{INSET_R}" fill="none" stroke="var(--line-strong)" stroke-width="0.8"/>',
        f'<text x="0" y="{box+10:.1f}" text-anchor="middle" font-family="var(--mono)" '
        'font-size="7" fill="var(--text-mute)">South Pole</text>',
        f'<g class="map-pin" data-site="south-pole" data-kinds="{icecube["kind"]}" '
        f'data-names="{_esc(icecube["name"])}"><title>{_title(icecube)}</title>'
        f'<g class="map-exp" data-experiment="{_esc(icecube["name"])}" data-kind="{icecube["kind"]}"'
        f'{_exp_attrs(icecube)}><title>{_title(icecube)}</title>{_marker(dx, dy, colour)}</g></g>',
        "</g>",
    ]
    return "".join(parts)


def main() -> None:
    entries = experiments.load()

    placed, polar, missing = [], [], []
    for e in entries:
        spot = geocode.locate(e["city"], e["country"])
        if spot is None:
            missing.append(f'{e["name"]} ({e["city"]}, {e["country"]})')
            continue
        lon, lat = spot
        if lat <= CROP_SOUTH_LAT:
            polar.append((e, lon, lat))
            continue
        x, y = wm.project(lon, lat)
        placed.append((e, x, y))

    if not placed and not polar:
        sys.exit("nothing could be located — is the network up? "
                 "(a rerun uses the cache and needs none)")

    # Cropped north of the far south: an equirectangular Antarctica is a band
    # the width of the world, which is why anything at or south of
    # CROP_SOUTH_LAT is drawn in the polar inset instead (see module
    # docstring).
    top = wm.project(0, 84)[1]
    bottom = wm.project(0, CROP_SOUTH_LAT)[1]
    h = bottom - top
    w = wm.WIDTH

    # Step 1: bucket co-located experiments by projected position, merging
    # any two markers within MERGE_DIST of each other — true coincidences
    # (same city, e.g. every Gran Sasso record) as well as near ones that
    # would otherwise render as one marker hiding another (see MERGE_DIST's
    # comment). Deduplicate by name within a bucket afterwards: the same
    # experiment can appear twice in the YAML under two roles —
    # Super-Kamiokande under both atmospheric and solar — and that must fan
    # out to one child, not two.
    parent_of = list(range(len(placed)))

    def _find(i: int) -> int:
        while parent_of[i] != i:
            parent_of[i] = parent_of[parent_of[i]]
            i = parent_of[i]
        return i

    def _union(i: int, j: int) -> None:
        ri, rj = _find(i), _find(j)
        if ri != rj:
            parent_of[ri] = rj

    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            if math.hypot(placed[i][1] - placed[j][1], placed[i][2] - placed[j][2]) <= MERGE_DIST:
                _union(i, j)

    clusters: dict[int, list[tuple[dict, float, float]]] = {}
    for i, member in enumerate(placed):
        clusters.setdefault(_find(i), []).append(member)

    sites = []
    for members in clusters.values():
        seen: dict[str, tuple[dict, float, float]] = {}
        for e, x, y in members:
            seen.setdefault(e["name"], (e, x, y))
        uniq = list(seen.values())
        cx = sum(x for _, x, _ in uniq) / len(uniq)
        cy = sum(y for _, _, y in uniq) / len(uniq)
        sites.append((cx, cy, [e for e, _, _ in uniq]))

    parts = [
        f'<svg viewBox="0 {top:.0f} {w:.0f} {h:.0f}" role="img" '
        'aria-label="World map of the neutrino experiments listed on this page">',
        "<title>Where the experiments are</title>",
        f'<path d="{wm.LAND_PATH}" fill="var(--surface-2)" stroke="var(--line-strong)" '
        'stroke-width="0.6" vector-effect="non-scaling-stroke"/>',
    ]
    # Fan (multi-experiment) pins draw last, on top of any single pin left
    # close enough to overlap them, so a cluster's count badge — the one
    # piece of markup a reader needs in order to know there's more to see —
    # is never the one left hidden underneath.
    for cx, cy, group in sorted(sites, key=lambda s: len(s[2])):
        parts.append(_render_pin(cx, cy, group))

    # Step 2: the south-polar inset, lower-left corner of the frame.
    if polar:
        cx0 = INSET_MARGIN + INSET_R
        cy0 = (top + h) - INSET_MARGIN - INSET_R
        for e, lon, lat in polar:
            parts.append(_render_south_pole_inset(cx0, cy0, e, lon, lat))

    parts.append("</svg>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")

    all_placed = placed + [(e, 0.0, 0.0) for e, _, _ in polar]
    print(f"map: {len(all_placed)} experiments placed -> {OUT.relative_to(ROOT)}")
    n_sites = len(sites) + (1 if polar else 0)
    n_fan = sum(1 for _, _, g in sites if len(g) > 1)
    print(f"  {n_sites} markers ({n_fan} fanned)")
    for m in missing:
        print(f"  ! not located, left off the map: {m}")

    legend = " ".join(f'<span data-filter="{k}"><i style="background:{c}"></i>{label}</span>'
                      for k, label, c in
                      [(k, l, c) for k, l, c in KINDS
                       if any(e["kind"] == k for e, _, _ in all_placed)])
    (OUT.parent / "map-experiments-legend.svg").write_text(
        f'<div class="legend legend--chart">{legend}</div>', encoding="utf-8")
    print("legend written alongside")


if __name__ == "__main__":
    main()
