"""Venue coordinates for the conference map.

Nominatim (OpenStreetMap) is the geocoder because it needs no API key, so
the nightly job can use it unattended; a paid Google Maps key would be the
alternative. Results were spot-checked against Google Maps when this module
was introduced (2026-08-10). Every answer — including "not found" — is
cached in var/news/geocache.json, so the steady-state run performs zero
geocoding requests and the map still renders with the network down.

A city that cannot be located falls back to the host country's centroid in
the caller (figures.conference_map), which is the precision INSPIRE itself
provides: city name and country code, no coordinates.

To fix a wrong entry, delete its line from geocache.json (or edit the
coordinates in place, lon/lat) and re-run; only missing keys are queried.

Every lookup is scoped to its country via Nominatim's countrycodes filter —
deliberately, so a wrong answer fails closed to "not found" rather than
landing in the right country by luck. locate() carries exactly one narrow
exception to that: country code "AQ" (Antarctica), which OpenStreetMap has
no administrative boundary for at all, so a countrycodes=aq query can never
return anything, for any Antarctic venue. That one code retries unscoped and
then checks the answer is actually south of 60°S before trusting it. This is
not licence to drop scoping elsewhere — every other country code does have a
boundary Nominatim can filter against, and should keep using it.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "var" / "news" / "geocache.json"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "global-nu-site/1.0 (https://global-nu.org)"

# Politeness: Nominatim asks for at most 1 request/second, and a nightly run
# should only ever meet a handful of unseen cities. The cap also bounds the
# damage of a source suddenly emitting garbage city names.
PAUSE_S = 1.1
MAX_NEW_PER_RUN = 25

_cache: dict[str, list[float] | None] | None = None
_new = 0


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _save() -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(_cache, indent=1, sort_keys=True,
                                ensure_ascii=False), encoding="utf-8")


def _query(params: dict) -> list:
    qs = urllib.parse.urlencode({**params, "format": "jsonv2", "limit": 1})
    req = urllib.request.Request(f"{ENDPOINT}?{qs}",
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as fh:
        return json.load(fh)


def locate(city: str, country_code: str) -> tuple[float, float] | None:
    """(lon, lat) of a venue city, or None if it cannot be located.

    Cache first; at most MAX_NEW_PER_RUN network lookups per process. A
    transient network failure returns None WITHOUT caching it, so the next
    run tries again; an empty geocoder answer is cached as null for good.
    """
    global _new
    city = (city or "").strip()
    code = (country_code or "").strip().upper()
    if not city or not code:
        return None

    cache = _load()
    key = f"{city.lower()}|{code}"
    if key in cache:
        v = cache[key]
        return (v[0], v[1]) if v else None
    if _new >= MAX_NEW_PER_RUN:
        return None

    _new += 1
    try:
        time.sleep(PAUSE_S)
        rows = _query({"city": city, "countrycodes": code.lower()})
        if not rows:
            # Free-text pass: catches venues that are not city names —
            # "CERN", "Otranto, Lecce", "University of California".
            time.sleep(PAUSE_S)
            rows = _query({"q": city, "countrycodes": code.lower()})
        if not rows and code == "AQ":
            # Deliberate, narrow exception to the countrycodes scoping
            # above: Antarctica carries no sovereign administrative boundary
            # under the Antarctic Treaty, so OpenStreetMap has no "AQ"
            # polygon for Nominatim's countrycodes filter to match against —
            # every country-scoped query on an Antarctic venue returns
            # empty, confirmed against Nominatim directly (McMurdo Station
            # and Amundsen-Scott both fail the same way). Retried once,
            # free-text and country-unscoped, which is the only way an
            # Antarctic venue can ever be found through this endpoint. This
            # is the one place a result is accepted without a country to
            # check it against, which is why the result is still required to
            # actually be in Antarctica (see the latitude check below)
            # before it's trusted — do not lift the countrycodes scoping for
            # any other country on this same reasoning; every other country
            # does have a boundary Nominatim can filter against.
            time.sleep(PAUSE_S)
            rows = _query({"q": city})
            if rows and float(rows[0]["lat"]) > -60.0:
                # An unscoped free-text query can match anywhere on Earth;
                # without a country polygon to confirm against, the only
                # check left is that the answer is actually far enough
                # south to be Antarctica. A hit north of that fails closed
                # rather than caching a dot in the wrong hemisphere.
                rows = []
    except OSError:
        return None                      # transient: retry on the next run

    if rows:
        cache[key] = [round(float(rows[0]["lon"]), 4),
                      round(float(rows[0]["lat"]), 4)]
    else:
        cache[key] = None
    _save()
    v = cache[key]
    return (v[0], v[1]) if v else None
