#!/usr/bin/env python3
"""figures.conference_timeline, and the caption render.conferences() builds
around it: a pure function over two lists and a date, tested directly rather
than only by prose reasoning.

    ./.venv/bin/python3 tools/tests/test_figures.py

Covered: a record starting today, one that ended yesterday, a missing `end`,
an unparseable `end`, `end` before `start`, a record with no readable `start`
at all (dropped, and logged — see figures.conference_timeline's `log`
argument), the max_rows slicing arithmetic render.conferences() turns into
the caption's numbers, including the n_up == 0 edge (every fetcher fails but
stale `recent` records remain) — and, separately, the (lon, lat) coordinate
order figures.conference_map and render.conferences() both have to get
right, at both hops: conference_map's own projection, and render.py's
`lon, lat = spot` unpacking of venue.locate_record's return value. Neither
hop is exercised by tools/tests/test_confmap.js, which only ever sees
numbers already burned into a hand-written SVG fixture.
"""
from __future__ import annotations

import datetime as _dt
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import figures, render, venue        # noqa: E402

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


class _Log:
    def __init__(self):
        self.calls = []

    def info(self, msg, *a):
        self.calls.append(msg % a if a else msg)

    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


TODAY = _dt.date(2026, 8, 14)


def rec(title, opening, closing=None, *, upcoming=True, in_progress=False,
       acronym=None, place=""):
    extra = {"opening": opening, "upcoming": upcoming,
             "in_progress": in_progress, "place": place}
    if closing is not None:
        extra["closing"] = closing
    if acronym:
        extra["acronym"] = acronym
    return {"id": title, "title": title, "url": "", "extra": extra}


def rects(svg: str) -> list[str]:
    """Every <rect ...> element as its raw attribute string, in order."""
    return re.findall(r"<rect ([^/]*?)/>", svg)


# --------------------------------------------------------------------- #
# date handling
# --------------------------------------------------------------------- #

# A record starting today must appear, drawn as an upcoming (ahead) bar, at
# the same x position as the TODAY line (start == today).
starts_today = rec("Starts Today", "2026-08-14", "2026-08-16")
svg = figures.conference_timeline([starts_today], [], today=TODAY)
row = rects(svg)
bar_x = re.search(r'x="([\d.]+)"', row[0]).group(1) if row else None
today_x = re.search(r'x1="([\d.]+)" y1="[^"]+" x2="[\d.]+" y2="[^"]+"\s*'
                    r'style="stroke:var\(--accent\)', svg)
check("a record starting today appears in the figure, as an upcoming bar",
      row and "var(--no)" in row[0] and "opacity:1" in row[0], row)
check("a record starting today's bar left edge aligns with the TODAY line",
      bar_x is not None and today_x is not None
      and abs(float(bar_x) - float(today_x.group(1))) < 0.15,
      f"bar x={bar_x}, TODAY line x={today_x and today_x.group(1)}")

# A record that ended yesterday (closing < today) is drawn muted, not as
# "ahead" — this is what `recent` records look like once they reach the
# figure via render.conferences()'s split.
ended_yesterday = rec("Ended Yesterday", "2026-08-10", "2026-08-13",
                      upcoming=False)
svg = figures.conference_timeline([], [ended_yesterday], today=TODAY)
row = rects(svg)
check("a record that ended yesterday still appears in the figure",
      len(row) == 1, svg)
check("a concluded record is drawn muted (text-mute, reduced opacity), not "
      "as an upcoming (--no) bar",
      row and "var(--text-mute)" in row[0] and 'opacity:.55' in row[0], row)

# A missing `end` falls back to `end = start` — a one-day meeting still gets
# a mark, at the minimum bar width the code guarantees (4.0).
no_end = rec("No End Date", "2026-08-20")
svg = figures.conference_timeline([no_end], [], today=TODAY)
row = rects(svg)
check("a record with no closing date still appears, one-day-wide",
      row and 'width="4.0"' in row[0], row)

# An unparseable `end` is treated exactly like a missing one: `_date()`
# returns None either way, so this is the same fallback exercised through a
# different input shape (garbage text rather than an absent key).
bad_end = rec("Bad End Date", "2026-08-20", "not-a-date")
svg = figures.conference_timeline([bad_end], [], today=TODAY)
row = rects(svg)
check("a record with an unparseable closing date falls back the same way "
      "a missing one does",
      row and 'width="4.0"' in row[0], row)

# `end` before `start` (a fetcher-side date swap) is corrected to `end = start`
# rather than drawing a bar with negative width. The width alone does not
# prove this — `w = max(x2 - x1, 4.0)` floors a negative width to 4.0 either
# way, so a broken correction and a working one produce the same width. What
# an uncorrected end<start actually breaks is the plot's own date span (`lo`/
# `hi`, derived from entries' starts and ends): with `end` left at 2026-08-10
# (before `start`, and before `today`) while `start` is 2026-08-20 (after
# `today`), the span collapses to zero days before padding and the bar's x
# position is extrapolated far outside the plot — checked directly below.
end_before_start = rec("Backwards Dates", "2026-08-20", "2026-08-10")
svg = figures.conference_timeline([end_before_start], [], today=TODAY)
row = rects(svg)
check("a closing date before the opening date is corrected to a one-day bar",
      row and 'width="4.0"' in row[0], row)
bar_x = float(re.search(r'x="([\d.]+)"', row[0]).group(1)) if row else None
check("the corrected bar is positioned inside the plot area, not "
     "extrapolated off-canvas by an uncorrected end<start",
      bar_x is not None and figures.LABEL_W <= bar_x <= figures.WIDTH,
      f"bar x={bar_x}, plot area=[{figures.LABEL_W}, {figures.WIDTH}]")

# A record with no readable `start` at all (missing or unparseable) is
# dropped from the figure — but the drop is now logged, once, aggregated,
# rather than silently. This is the fix for the "silent record drop" finding:
# a fetcher-side date regression on `extra.opening` would otherwise vanish
# from the figure with no trace, on a page that rebuilds unattended.
good = rec("Has A Date", "2026-08-20", "2026-08-22")
missing_start = rec("Missing Opening", "")
del missing_start["extra"]["opening"]
unparseable_start = rec("Bad Opening", "not-a-date")
log = _Log()
svg = figures.conference_timeline([good, missing_start, unparseable_start], [],
                                  today=TODAY, log=log)
check("records with no readable opening date are dropped from the figure",
      len(rects(svg)) == 1, svg)
check("the drop is logged exactly once, aggregated (not once per record)",
      len(log.calls) == 1, log.calls)
check("the log line names how many of how many rows were dropped",
      log.calls and "2 of 3" in log.calls[0], log.calls)

# Proof the log call is not simply unconditional: with nothing dropped, no
# call is made at all.
log2 = _Log()
figures.conference_timeline([good], [], today=TODAY, log=log2)
check("nothing is logged when nothing is dropped",
      log2.calls == [], log2.calls)


# --------------------------------------------------------------------- #
# max_rows slicing arithmetic and the caption's numbers
# --------------------------------------------------------------------- #

render.CONFERENCES_PAGE = Path(tempfile.mkdtemp()) / "conferences.md"


def _upcoming_recs(n, start=_dt.date(2026, 8, 15)):
    return [rec(f"Up {i}", (start + _dt.timedelta(days=i)).isoformat(),
               (start + _dt.timedelta(days=i + 1)).isoformat())
           for i in range(n)]


def _recent_recs(n, end=_dt.date(2026, 8, 10)):
    return [rec(f"Rec {i}", (end - _dt.timedelta(days=i + 1)).isoformat(),
               (end - _dt.timedelta(days=i)).isoformat(), upcoming=False)
           for i in range(n)]


def _caption(records) -> str:
    render.conferences(records, _Log(), stamp="test")
    text = render.CONFERENCES_PAGE.read_text(encoding="utf-8")
    m = re.search(r'<p class="cap">(.*?)</p>', text, re.S)
    return m.group(1) if m else ""

# Fewer upcoming than max_rows (14): recent fills the remaining rows, and the
# caption states both counts and both totals correctly.
cap = _caption(_upcoming_recs(5) + _recent_recs(20))
check("with 5 upcoming, the caption states the soonest 5",
      "The soonest 5 upcoming meetings" in cap, cap)
check("with 5 upcoming (of 14 rows), the remaining 9 rows go to recent",
      "the 9 most recently concluded" in cap, cap)
check("the caption's totals match the full record counts (5 upcoming, 20 recent)",
      "5 upcoming and 20 recent meetings are tracked in full below" in cap, cap)

# More upcoming than max_rows: recent gets none of the 14 rows at all, and
# the caption must not claim otherwise.
cap = _caption(_upcoming_recs(20) + _recent_recs(10))
check("with 20 upcoming, the caption caps the shown count at max_rows (14)",
      "The soonest 14 upcoming meetings" in cap, cap)
check("with upcoming already filling every row, recent is not mentioned as shown",
      "most recently concluded" not in cap, cap)
check("the caption's totals still report the true 20 upcoming and 10 recent",
      "20 upcoming and 10 recent meetings are tracked in full below" in cap, cap)

# n_up == 0: every fetcher failed to produce an upcoming record but stale
# `recent` records remain. This is the "soonest 0 upcoming meetings" bug —
# the caption must read as a sentence, not print a "soonest 0" clause.
cap = _caption(_recent_recs(6))
check("with zero upcoming, the caption never says 'soonest 0'",
      "soonest 0" not in cap.lower(), cap)
check("with zero upcoming, the caption instead leads with what recent is shown",
      "The 6 most recently concluded meetings" in cap, cap)
check("the caption's totals still report 0 upcoming",
      "0 upcoming and 6 recent meetings are tracked in full below" in cap, cap)


# --------------------------------------------------------------------- #
# coordinate order: longitude first, at BOTH hops, proven with a fixture a
# swap cannot pass by accident
# --------------------------------------------------------------------- #
# Sydney, not an arbitrary city: (lon, lat) = (151.2093, -33.8688) is both a
# positive (eastern) longitude and a negative (southern) latitude, so a
# (lat, lon) swap moves the dot somewhere unmistakably wrong rather than a
# few pixels off within the same hemisphere — -33.8688 read as a longitude
# lands WEST of the prime meridian (the wrong half of the frame), and
# 151.2093 read as a latitude is not even a valid one.
SYDNEY_LON, SYDNEY_LAT = 151.2093, -33.8688


def _pin_block(svg: str, conf_id: str) -> str:
    """The whole <g class="conf-pin" ...>...</g> for the marker holding one
    conference, so the attribute and position checks below read from the SAME
    marker rather than (accidentally) the first one in the document.

    A marker is one <g class="conf-pin"> per venue, holding one
    <g class="conf-item" data-conf="..."> per conference there (see
    figures._conf_marker) — data-conf identifies the conference but sits on
    the inner item, not on the outer pin, so this matches inward to the item
    first and then reaches back out to the pin's own closing tag.
    """
    m = re.search(
        rf'<g class="conf-pin"[^>]*>.*?'
        rf'<g class="conf-item"[^>]*data-conf="{re.escape(conf_id)}"[^>]*>'
        r'</g>(?:<g class="conf-item"[^>]*></g>)*</g>',
        svg, re.S)
    return m.group(0) if m else ""


def _num(pattern: str, block: str) -> float | None:
    m = re.search(pattern, block)
    return float(m.group(1)) if m else None


def _xy(block: str) -> tuple[float | None, float | None]:
    """The marker's drawn (x, y), off the conf-pin's own transform.

    A marker's <circle> sits at the origin of a translated <g> now — no cx/cy
    of its own (see figures._conf_marker) — so the position a reader sees
    comes from the group's transform="translate(x y)", not a shape attribute.
    """
    m = re.search(r'transform="translate\((-?[\d.]+) (-?[\d.]+)\)"', block)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


# Hop 1: figures.conference_map's own projection. A record is handed in
# already as (record, lon, lat) — conference_map's documented argument
# order — and the drawn marker must come back at the (lon, lat) it was
# given, not the transpose of it.
sydney_conf = {"id": "conf:sydney", "title": "Sydney Coordinate-Order Test",
              "url": "https://sydney.example.org/",
              "extra": {"place": "Sydney, Australia",
                       "span": "1-5 September 2026"}}
svg = figures.conference_map([(sydney_conf, SYDNEY_LON, SYDNEY_LAT)])
block = _pin_block(svg, "conf:sydney")
check("conference_map draws the marker svg carries a matching conf-pin block",
      bool(block), svg[:200])

lat_attr = _num(r'data-lat="(-?[\d.]+)"', block)
lon_attr = _num(r'data-lon="(-?[\d.]+)"', block)
check("the drawn marker's data-lat equals the (lon, lat) tuple's SECOND element",
      lat_attr is not None and abs(lat_attr - SYDNEY_LAT) < 1e-6,
      f"data-lat={lat_attr}")
check("the drawn marker's data-lon equals the (lon, lat) tuple's FIRST element",
      lon_attr is not None and abs(lon_attr - SYDNEY_LON) < 1e-6,
      f"data-lon={lon_attr}")

cx, cy = _xy(block)
equator_y = figures.wm.project(0.0, 0.0)[1]
centre_x = figures.wm.WIDTH / 2.0
check("a southern-hemisphere conference is drawn BELOW the equator line "
     "(larger y — a swapped lat/lon would place it far outside the frame "
     "instead, since 151.2 is not a valid latitude)",
      cy is not None and cy > equator_y,
      f"cy={cy}, equator_y={equator_y}")
check("an eastern-longitude conference is drawn EAST of the prime meridian "
     "(x > width/2 — a swapped lat/lon would put -33.87 in as a longitude "
     "and land WEST of it instead)",
      cx is not None and cx > centre_x,
      f"cx={cx}, centre_x={centre_x}")

# Hop 2: render.conferences()'s own `lon, lat = spot` unpacking of
# venue.locate_record's return value — the one line test_confmap.js cannot
# reach at all, because its fixture SVG already has numbers baked in and
# never runs venue.locate_record or render.py. venue.locate_record is
# monkeypatched (never touches the network — same insulation
# test_conferences.py uses for the identical reason) so the real
# render.conferences() -> figures.conference_map() path runs end to end,
# with a single Sydney-coordinate record standing in for whatever the
# cascade would actually have found.
sydney_rec = rec("Sydney Hop Test", "2026-09-01", "2026-09-05",
                 place="Sydney, Australia")
_orig_locate_record = venue.locate_record
venue.locate_record = lambda record, log: (SYDNEY_LON, SYDNEY_LAT)
try:
    render.conferences([sydney_rec], _Log(), stamp="test")
    hop_html = render.CONFERENCES_PAGE.read_text(encoding="utf-8")
finally:
    venue.locate_record = _orig_locate_record

hop_block = _pin_block(hop_html, "Sydney Hop Test")
check("render.conferences() draws a conf-pin for the mocked record",
      bool(hop_block), hop_html[:200])
hop_lat = _num(r'data-lat="(-?[\d.]+)"', hop_block)
hop_lon = _num(r'data-lon="(-?[\d.]+)"', hop_block)
check("through render.conferences()'s own lon,lat = spot unpacking, "
     "data-lat still matches locate_record's SECOND element",
      hop_lat is not None and abs(hop_lat - SYDNEY_LAT) < 1e-6,
      f"data-lat={hop_lat}")
check("through render.conferences()'s own lon,lat = spot unpacking, "
     "data-lon still matches locate_record's FIRST element",
      hop_lon is not None and abs(hop_lon - SYDNEY_LON) < 1e-6,
      f"data-lon={hop_lon}")
hop_cx, hop_cy = _xy(hop_block)
check("the same record, drawn via render.conferences(), still lands south "
     "of the equator line",
      hop_cy is not None and hop_cy > equator_y,
      f"cy={hop_cy}, equator_y={equator_y}")
check("the same record, drawn via render.conferences(), still lands east "
     "of the prime meridian",
      hop_cx is not None and hop_cx > centre_x,
      f"cx={hop_cx}, centre_x={centre_x}")


print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — conference_timeline's date handling and "
     "render.conferences()'s caption arithmetic")
