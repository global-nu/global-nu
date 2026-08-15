"""Illustrations for the news pages, drawn from the data the run already has.

Why drawn and not photographed: the site makes no request to an external host
at runtime, and a conference's own banner image is somebody else's to
republish. So a figure here is generated straight from the records that also
produce the text beside it — it cannot disagree with them, because there is
only one source.

Inline SVG, not a file under images-src/: inline markup inherits the page's
CSS custom properties, so a figure follows the theme toggle in both
directions the way an <img> never could, and build.py's image pipeline is
never involved.

Ported from ~/Documents/My Home Page - Claude/tools/news/figures.py, whose
`conference_timeline` draws the same shape from the same record fields
(`extra.opening`/`closing`/`acronym`/`place`/`upcoming`/`in_progress`, which
this site's fetchers already fill in identically — see conferences.py). Only
the styling changes here: that site paints with `--gold`/`--cyan`, tokens this
site does not have. Below, an upcoming bar is `--no`, a bar for a meeting
running right now is `--io`, and "today" is `--accent` — reusing the ordering
pair for a completely different distinction. That is a deliberate borrow of
two hues already proven against every background at the 3:1 a data-carrying
mark needs (see PAIRS in tools/tests/test_theme.js), not a claim that this
figure has anything to do with the mass ordering.
"""

from __future__ import annotations

import datetime as _dt
import html
import logging

from . import geocluster, photos
from . import worldmap as wm


def _e(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


# --------------------------------------------------------------------------- #
# the conference timeline
# --------------------------------------------------------------------------- #
# Small on purpose: this sits above the two lists that are the point of the
# page, and a reader who scrolled here for "what's next" should not have to
# scroll past a tall figure to reach it. 520 wide matches the home page's
# ranges-hero figure rather than the 760 of a full-width table, because a
# narrower viewBox keeps the row labels legible when the SVG is scaled down
# to a 375px screen — the ratio of text to viewBox width is what survives the
# shrink, not the absolute font-size.
ROW = 20
PAD_TOP = 26
PAD_BOTTOM = 20
LABEL_W = 122          # room for the acronym column, in viewBox units
WIDTH = 520


def _date(value: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _trim(text: str, limit: int) -> str:
    """Cut on a word boundary — 'Santa Barbara, United Stat' reads as a bug."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;")
    return (cut or text[:limit]) + "…"


def _short(conf: dict, limit: int = 20) -> str:
    """The acronym if a source gave one, otherwise a trimmed title."""
    extra = conf.get("extra", {})
    return _trim(extra.get("acronym") or conf.get("title", ""), limit)


def conference_timeline(upcoming: list[dict], recent: list[dict],
                        today: _dt.date | None = None,
                        max_rows: int = 14,
                        log: logging.Logger | None = None) -> str:
    """A Gantt-style strip: one bar per conference, with a line for today.

    Reading a list of date ranges is work; seeing which one is next, which is
    running and which has just finished is immediate. That is the whole point
    of putting it here, above the lists that spell the same thing out in text.

    `upcoming` and `recent` are expected pre-sorted the way conferences.py
    already sorts them for the page: soonest-first and most-recent-first
    respectively. Rows fill from `upcoming` first — the meetings a reader can
    still act on — and only the room `upcoming` leaves goes to `recent`. With
    more upcoming meetings than `max_rows`, `recent` gets none at all; that is
    the correct trade, not an accident of the slicing, because a meeting
    already over is the one thing on this page nobody needs to plan around.
    """
    today = today or _dt.date.today()
    rows = upcoming[:max_rows]
    rows = rows + recent[:max(0, max_rows - len(rows))]

    entries = []
    dropped = 0
    for c in rows:
        extra = c.get("extra", {})
        start = _date(extra.get("opening", ""))
        if start is None:
            dropped += 1
            continue
        end = _date(extra.get("closing", "")) or start
        if end < start:
            end = start
        entries.append((c, start, end))
    if dropped and log is not None:
        # A missing/unparseable extra.opening is a fetcher-side date
        # regression, not an expected shape — the record still appears in the
        # text lists below (they don't need a parsed date), so this figure is
        # the only place it would otherwise vanish silently. Aggregated, one
        # line, same level fetch_nu_unbound.fetch() already uses for the
        # identical situation ("N dropped for an unreadable date").
        log.info("conference timeline: %d of %d row(s) dropped for a "
                 "missing/unreadable opening date", dropped, len(rows))
    if not entries:
        return ""

    lo = min(s for _, s, _ in entries)
    hi = max(e for _, _, e in entries)
    lo = min(lo, today)
    hi = max(hi, today)
    span = max((hi - lo).days, 1)
    # A little air either side so the first bar does not touch the axis.
    pad = max(int(span * 0.04), 3)
    lo -= _dt.timedelta(days=pad)
    hi += _dt.timedelta(days=pad)
    span = (hi - lo).days

    plot_w = WIDTH - LABEL_W - 16
    height = PAD_TOP + ROW * len(entries) + PAD_BOTTOM

    def x_of(d: _dt.date) -> float:
        return LABEL_W + plot_w * ((d - lo).days / span)

    parts = [
        f'<svg viewBox="0 0 {WIDTH} {height}" '
        f'role="img" width="{WIDTH}" height="{height}" '
        f'aria-label="Timeline of upcoming and recently concluded neutrino '
        f'conferences" xmlns="http://www.w3.org/2000/svg">',
        '<title>Conference timeline</title>',
    ]

    # Month gridlines, labelled at the top.
    month = _dt.date(lo.year, lo.month, 1)
    while month <= hi:
        if month >= lo:
            x = x_of(month)
            parts.append(
                f'<line x1="{x:.1f}" y1="{PAD_TOP - 12}" x2="{x:.1f}" '
                f'y2="{height - PAD_BOTTOM + 5}" '
                f'style="stroke:var(--line);stroke-width:1"/>')
            parts.append(
                f'<text x="{x + 3:.1f}" y="{PAD_TOP - 15}" '
                f'style="fill:var(--text-mute);font-size:9.5px;'
                f'font-family:var(--display,sans-serif)">'
                f'{_e(month.strftime("%b"))}</text>')
        month = _dt.date(month.year + (month.month == 12),
                         month.month % 12 + 1, 1)

    # Today.
    tx = x_of(today)
    parts.append(
        f'<line x1="{tx:.1f}" y1="{PAD_TOP - 18}" x2="{tx:.1f}" '
        f'y2="{height - PAD_BOTTOM + 5}" '
        f'style="stroke:var(--accent);stroke-width:1.5;stroke-dasharray:3 3"/>')
    parts.append(
        f'<text x="{tx:.1f}" y="{height - PAD_BOTTOM + 17}" text-anchor="middle" '
        f'style="fill:var(--accent);font-size:9px;letter-spacing:.08em;'
        f'font-family:var(--display,sans-serif)">TODAY</text>')

    for i, (c, start, end) in enumerate(entries):
        y = PAD_TOP + i * ROW
        extra = c.get("extra", {})
        ahead = bool(extra.get("upcoming"))
        running = bool(extra.get("in_progress"))
        colour = "var(--no)" if ahead else "var(--text-mute)"
        if running:
            colour = "var(--io)"
        x1, x2 = x_of(start), x_of(end)
        w = max(x2 - x1, 4.0)          # a one-day meeting still needs a mark
        opacity = "1" if ahead else ".55"

        parts.append(
            f'<rect x="{x1:.1f}" y="{y + 4}" width="{w:.1f}" height="10" rx="5" '
            f'style="fill:{colour};opacity:{opacity}"/>')
        parts.append(
            f'<text x="{LABEL_W - 10}" y="{y + 12.5}" text-anchor="end" '
            f'style="fill:var(--text-soft);font-size:10.5px;opacity:{opacity};'
            f'font-family:var(--body,sans-serif)">{_e(_short(c))}</text>')
        # The place, set after the bar, only when there is room for it.
        place = _trim(extra.get("place", ""), 18)
        if place and x1 + w + 6 < WIDTH - 40:
            parts.append(
                f'<text x="{x1 + w + 6:.1f}" y="{y + 12.5}" '
                f'style="fill:var(--text-mute);font-size:9px;opacity:{opacity};'
                f'font-family:var(--body,sans-serif)">{_e(place)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# the conference map
# --------------------------------------------------------------------------- #
# Cropped rather than compressed. In an equirectangular projection Antarctica
# smears into a band the width of the world, and the empty Arctic wasted a
# third of the height; no conference has ever been held in either. Cropping
# them away still leaves a taller frame than the old scale(1,.5) squash did —
# 280 units against 162, since .figure svg{height:auto} sizes the card by
# this viewBox's own aspect ratio — a real ~73% more vertical space on the
# page. That is the accepted cost of undistorted shapes, paid deliberately,
# not a trade this crop avoids.
MAP_TOP_LAT = 82.0
MAP_BOTTOM_LAT = -58.0

MAP_DOT_R = 3.0
# Two markers this close would sit almost entirely on top of one another,
# hiding whichever was drawn first — the same problem make_map.py's
# MERGE_DIST exists to catch, reused at the same "2 dot-radii" rule rather
# than a second, invented one.
MAP_MERGE_DIST = 2 * MAP_DOT_R


def _map_title(name: str, place: str, dates: str) -> str:
    title = f"{name} — {place}" if place else name
    return f"{title} · {dates}" if dates else title


def _photo_city(conf: dict) -> tuple[str, str] | None:
    """The (city, ISO2 country code) to ask photos.for_city for, or None
    when the record does not carry enough structure to ask cleanly.

    Only `extra.city` and `extra.country_code` are trusted — both are
    already-parsed fields a fetcher set (fetch_inspire.py, fetch_nu_unbound.py
    — see conferences.py), never derived here by splitting `extra.place` or
    `extra.address` on a comma. Guessing a city out of an address string
    risks exactly the "venue, not city" mistake this whole feature exists to
    avoid — Indico's own address field can read "Sede Afundación, Cantón
    Grande 8, A Coruña, 15003, Spain", and a naive split would hand Commons
    "Sede Afundación" to search on, not "A Coruña". Indico never sets
    extra.city/country_code (see fetch_indico.py), so its records simply get
    no photo — no photo beats a wrong one, same as everywhere else here.
    """
    extra = conf.get("extra") or {}
    city = (extra.get("city") or "").strip()
    code = (extra.get("country_code") or "").strip().upper()
    if city and len(code) == 2:
        return city, code
    return None


def _lookup_photo(conf: dict, log: logging.Logger) -> dict | None:
    city_code = _photo_city(conf)
    if not city_code:
        return None
    return photos.for_city(city_code[0], city_code[1], log)


def _conf_marker(confs: list[dict], lon: float, lat: float,
                 x: float, y: float, photo: dict | None = None) -> str:
    """One <g class="conf-pin"> for a venue, holding every conference at it.

    A marker used to be one conference, and a city with two fanned them into
    two dots a few units apart. It is now one dot with the count on it — what
    makes the home page's map legible across a crowded Europe — so the
    conferences have to live inside it. `map.js` already does exactly this
    with `.map-exp` children inside one experiment pin; this follows that
    pattern rather than inventing a second one.

    Each `<g class="conf-item">` draws nothing. It carries one conference's
    name, dates and URL for confmap.js to read, on hover and on click.

    data-lat/data-lon are the venue's REAL coordinates: confmap.js builds the
    Google Maps link from them, and a link is only as honest as the numbers
    that produced it.

    `photo`, when given, is the dict photos.for_city returns — file, page,
    author, licence, licence_url — carried as five data-photo* attributes so
    confmap.js can render the image and its full credit without a second
    lookup. It sits on the marker, not on a conference, because it is a
    photograph of the CITY: photos.for_city caches by city, and every
    conference here shares one.
    """
    first = confs[0]
    extra = first.get("extra") or {}
    place = extra.get("place") or extra.get("city") or ""
    city = extra.get("city") or place
    n = len(confs)
    r = 3.2 + 1.5 * min(n - 1, 4)
    colour = ("var(--dec-4)" if (extra.get("scope") or "") == "general"
              else "var(--no)")

    title = "; ".join(
        _map_title(c.get("title", ""), place,
                   (c.get("extra") or {}).get("span", ""))
        for c in confs)

    attrs = (
        f' data-place="{_e(place)}"'
        f' data-lat="{lat:.4f}"'
        f' data-lon="{lon:.4f}"'
    )
    if photo:
        attrs += (
            f' data-photo="{_e(photo["file"])}"'
            f' data-photo-author="{_e(photo["author"])}"'
            f' data-photo-licence="{_e(photo["licence"])}"'
            f' data-photo-licence-url="{_e(photo.get("licence_url") or "")}"'
            f' data-photo-page="{_e(photo["page"])}"'
        )

    items = "".join(
        f'<g class="conf-item" data-conf="{_e(c.get("id", ""))}"'
        f' data-name="{_e(c.get("title", ""))}"'
        f' data-dates="{_e((c.get("extra") or {}).get("span", ""))}"'
        f' data-url="{_e(c.get("url", ""))}"></g>'
        for c in confs)

    # The shapes sit at the origin inside a translated group, and data-fixed
    # holds the anchor: svgzoom.js counter-scales every [data-fixed] group so
    # a dot keeps its on-screen size as the map is zoomed, and a crowd comes
    # apart instead of growing into one blob.
    count = (f'<text y="2.4" text-anchor="middle" '
             f'style="fill:var(--on-accent);font-size:6px;font-weight:700;'
             f'font-family:var(--display,sans-serif)">{n}</text>'
             if n > 1 else "")

    return (
        f'<g class="conf-pin"{attrs} data-fixed="{x:.1f} {y:.1f}" '
        f'transform="translate({x:.1f} {y:.1f})" tabindex="0">'
        f'<title>{_e(title)}</title>'
        f'<circle r="{r:.1f}" fill="{colour}" stroke="var(--bg)" '
        f'stroke-width="1.1" paint-order="stroke"/>'
        f'{count}'
        f'<text y="{-r - 3:.1f}" text-anchor="middle" class="map-name" '
        f'style="fill:var(--text-mute);font-size:8px;'
        f'font-family:var(--body,sans-serif)">{_e(_trim(city, 18))}</text>'
        f'{items}</g>'
    )


def conference_map(located: list[tuple[dict, float, float]],
                   log: logging.Logger | None = None) -> str:
    """A world map of upcoming conferences, one dot per venue.

    `located` holds only conferences the caller already ran through
    venue.locate_record — recently-concluded conferences and ones the cascade
    could not place are never passed in, per the spec ("a dot in roughly the
    right country is worse than no dot"); this function draws exactly what it
    is given and invents nothing.

    Each element is (record, lon, lat) — the same (lon, lat) order
    venue.locate_record and worldmap.project both use, LONGITUDE FIRST.
    Getting this order backwards would put every conference in the wrong
    hemisphere while still producing a map that looks plausible at a glance —
    the worst kind of wrong for a public scientific page — so callers and
    tests should assert the order explicitly rather than trust a reading of
    it.

    Every marker is also offered a photograph of its city, via
    photos.for_city (see _photo_city/_lookup_photo above) — `log` is passed
    through for that lookup's own reporting and defaults to this module's
    own logger so an existing caller (render.conferences()) need not change
    to keep working.
    """
    if not located:
        return ""
    log = log or logging.getLogger(__name__)

    # Step 1: project and cluster. The bucketing is geocluster's
    # cluster_by_distance — make_map.py's own single-linkage algorithm,
    # shared rather than reimplemented, per the brief. Bucketing happens in
    # projected pixel space, because "coincident" is a statement about what
    # a reader sees on the drawn map, not about the underlying globe.
    points = [(conf, lon, lat, wm.project(lon, lat)) for conf, lon, lat in located]
    groups = geocluster.cluster_by_distance(
        [p[3] for p in points], MAP_MERGE_DIST)
    clusters: dict[int, list[int]] = {idx: idxs for idx, idxs in enumerate(groups)}

    top = wm.project(0.0, MAP_TOP_LAT)[1]
    bottom = wm.project(0.0, MAP_BOTTOM_LAT)[1]
    height = bottom - top

    parts = [
        f'<svg data-zoomable="1" viewBox="0 {top:.0f} {wm.WIDTH:.0f} '
        f'{height:.0f}" role="img" '
        'aria-label="World map of upcoming neutrino conferences" '
        'xmlns="http://www.w3.org/2000/svg">',
        "<title>Where the upcoming conferences are</title>",
        f'<path d="{wm.LAND_PATH}" fill="var(--surface-2)" '
        'stroke="var(--line-strong)" stroke-width="0.6" '
        'vector-effect="non-scaling-stroke"/>',
    ]

    # Step 2: draw one marker per cluster. A cluster of one is a city with one
    # conference; a cluster of several is a city with several, and the count
    # goes on the dot instead of fanning them into separate ones.
    for members in sorted(clusters.values(), key=len):
        confs = [points[i][0] for i in members]
        # The cluster's position is the mean of its members', but the
        # coordinates carried on the marker are the first conference's real
        # ones — the Google Maps link must land on a venue, not on a centroid.
        cx = sum(points[i][3][0] for i in members) / len(members)
        cy = sum(points[i][3][1] for i in members) / len(members)
        _, lon, lat, _ = points[members[0]]
        parts.append(_conf_marker(confs, lon, lat, cx, cy,
                                  _lookup_photo(confs[0], log)))

    parts.append("</svg>")
    return "\n".join(parts)
