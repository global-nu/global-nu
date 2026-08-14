#!/usr/bin/env python3
"""The conferences page's sources, and the rules that bind them.

    ./.venv/bin/python3 tools/tests/test_conferences.py

The page was fed by Indico alone, so it showed whatever Indico's generic
categories held — a Czech-Slovak HEP workshop and an HL-LHC meeting led the
published page while NuFact and the Erice school were absent. These checks are
about the sources being there and the merge holding, not about any one day's
listing, so every record here is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tempfile

from tools.news import conferences as conf          # noqa: E402
from tools.news import fetch_inspire, fetch_nu_unbound, figures, geocode, photos, render   # noqa: E402

problems: list[str] = []
checks = 0


class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


class _FakeResponse:
    """A stand-in for requests.Response, carrying only what venue.py reads."""
    def __init__(self, text):
        self.text = text


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


check("the Neutrino Unbound fetcher exists and is callable",
      callable(getattr(fetch_nu_unbound, "fetch", None)))
check("INSPIRE can be asked for conferences, not only literature",
      callable(getattr(fetch_inspire, "fetch_conferences", None)))
check("INSPIRE conferences split into upcoming and concluded",
      callable(getattr(fetch_inspire, "split", None)))


def rec(name, url, city, country, opening, closing, provider, scope="neutrino"):
    return {"id": f"{provider}:{name}", "title": name, "url": url,
            "extra": {"acronym": name.split()[0], "place": f"{city}, {country}",
                      "city": city, "country_code": country,
                      "opening": opening, "closing": closing,
                      "provider": provider, "scope": scope, "upcoming": True}}


# One conference, listed by two sources, must merge into one entry that
# remembers both — this is what conferences.py is for and what three sources
# will exercise every morning.
nufact_nu = rec("NuFact 2026", "https://nufact2026.example.org/",
                "Shanghai", "CN", "2026-08-31", "2026-09-05", "nu-unbound")
nufact_in = rec("NuFact 2026", "https://inspirehep.net/conferences/2812345",
                "Shanghai", "CN", "2026-08-31", "2026-09-05", "inspire")
other = rec("Erice School 2026", "https://erice.example.org/",
            "Erice", "IT", "2026-09-14", "2026-09-22", "nu-unbound")

merged = conf.merge([[nufact_nu], [nufact_in], [other]], _Log())
check("a conference listed by two sources merges into one entry",
      len(merged) == 2, f"got {len(merged)}: {[m['title'] for m in merged]}")
lead = next((m for m in merged if m["title"] == "NuFact 2026"), None)
check("the merged entry records both providers",
      bool(lead) and len(set((lead.get("extra") or {}).get("providers") or [])) >= 2,
      f"providers: {(lead or {}).get('extra', {}).get('providers')}")

# render.conferences() now builds two blocks — "Neutrino conferences" and
# "General particle physics" — via conferences.split_scope(records, scope),
# and within EACH block still separates what is ahead (extra.upcoming) from
# what just concluded, the axis Task 1 found a real bug on (extra.scope is
# the field DOMAIN, never the tense). Redirected to a scratch file so this
# does not overwrite the real site-src/content/conferences.md.
render.CONFERENCES_PAGE = Path(tempfile.mkdtemp()) / "conferences.md"


def _render_page(records):
    render.conferences(records, _Log(), stamp="test")
    return render.CONFERENCES_PAGE.read_text(encoding="utf-8")


def _domain_blocks(text):
    """The page's two domain sections, each still cut on their own
    Upcoming/Recent boundary."""
    _, _, after_nu = text.partition('<h2>Neutrino conferences</h2>')
    nu_block, _, general_block = after_nu.partition('<h2>General particle physics</h2>')
    nu_up, _, nu_recent = nu_block.partition('<h3>Recent</h3>')
    gen_up, _, gen_recent = general_block.partition('<h3>Recent</h3>')
    return nu_up, nu_recent, gen_up, gen_recent


still_ahead = rec("Still Ahead 2099", "https://ahead.example.org/", "Bari", "IT",
                  "2099-01-01", "2099-01-05", "nu-unbound")
still_ahead["extra"]["upcoming"] = True

already_over = rec("Already Over 2020", "https://over.example.org/", "Bari", "IT",
                   "2020-01-01", "2020-01-05", "nu-unbound")
already_over["extra"]["upcoming"] = False

# Upcoming AND scope="general" — the exact combination the bug got wrong: the
# old predicate read `scope != "past"` as "upcoming", so a general-scope
# record was never the cause, but the fix must not swap one field-confusion
# for another in the other direction.
general_upcoming = rec("General Physics Meeting 2099", "https://general.example.org/",
                       "Bari", "IT", "2099-02-01", "2099-02-05", "nu-unbound",
                       scope="general")
general_upcoming["extra"]["upcoming"] = True

# render.conferences() now calls venue.locate_record for every `upcoming`
# record (Task 4), which in turn calls geocode.locate() for a record with no
# clean cached answer — a real Nominatim request, plus PAUSE_S's courtesy
# sleep. These three records all carry a real place ("Bari, IT"), so without
# this stub the render calls below would phone a stranger's server on a
# clean checkout — silent here only because geocache.json on THIS machine
# already has "bari|IT" cached from earlier local runs. Monkeypatched the
# same way venue.http_get is stubbed further down this file: no network, no
# dependence on a local cache file, no sleep.
_orig_geocode_locate = geocode.locate


def _fake_geocode_locate(city, country_code):
    return (16.8622, 41.1171) if city and country_code else None  # a fixed, offline "Bari"


# figures.conference_map() now also asks photos.for_city() for every located
# record's city (Task 5) — a real Commons search for "Bari" without this
# stub, same silent-on-this-machine trap the geocode stub above exists to
# avoid, just against a different stranger's server. Stubbed the same way:
# reassigned, restored in the same `finally`.
_orig_photos_for_city = photos.for_city


def _fake_photos_for_city(city, country_code, log):
    return None


geocode.locate = _fake_geocode_locate
photos.for_city = _fake_photos_for_city
try:
    page = _render_page([still_ahead, already_over, general_upcoming])
finally:
    geocode.locate = _orig_geocode_locate
    photos.for_city = _orig_photos_for_city
nu_up, nu_recent, gen_up, gen_recent = _domain_blocks(page)

check("a record with extra.upcoming=True renders under Upcoming, not Recent",
      "Still Ahead 2099" in nu_up and "Still Ahead 2099" not in nu_recent)
check("a record with extra.upcoming=False renders under Recent, not Upcoming",
      "Already Over 2020" in nu_recent and "Already Over 2020" not in nu_up)
check("a record whose extra.scope is 'general' is not thereby treated as concluded",
      "General Physics Meeting 2099" in gen_up
      and "General Physics Meeting 2099" not in gen_recent)
check("a neutrino-scope record does not leak into the general block",
      "Still Ahead 2099" not in gen_up and "Already Over 2020" not in gen_recent)
check("a general-scope record does not leak into the neutrino block",
      "General Physics Meeting 2099" not in nu_up
      and "General Physics Meeting 2099" not in nu_recent)

# CRITICAL (final whole-branch review): a record whose extra.upcoming/
# in_progress were computed on some EARLIER "today" — a stale 304 replay
# from fetch_nu_unbound (see its module docstring) or a re-render via
# pipeline.run(from_cache=True) — must not keep reading as upcoming, coloured
# as running-right-now, once its own extra.closing has actually passed.
# conferences.sort_for_page is the one point every source's records pass
# through before the page is built, so it is where the tense is re-derived
# from the dates themselves (conferences._refresh_tense) rather than trusted
# off whatever a fetcher wrote on some earlier morning. Same class of bug as
# commit c2f4162, re-entered through the conditional-fetch door.
stale_upcoming = rec("Stale Meeting 2020", "https://stale.example.org/", "Bari", "IT",
                     "2020-01-01", "2020-01-05", "nu-unbound")
stale_upcoming["extra"]["upcoming"] = True         # stale: as if flagged on a
stale_upcoming["extra"]["in_progress"] = True      # much earlier "today"

genuinely_ahead = rec("Genuinely Ahead 2099", "https://ahead2.example.org/", "Bari", "IT",
                      "2099-03-01", "2099-03-05", "nu-unbound")
genuinely_ahead["extra"]["upcoming"] = True

refreshed = conf.sort_for_page([stale_upcoming, genuinely_ahead])
stale_after = next(r for r in refreshed if r["title"] == "Stale Meeting 2020")
ahead_after = next(r for r in refreshed if r["title"] == "Genuinely Ahead 2099")

check("sort_for_page recomputes a stale upcoming=True to False once closing is past",
      stale_after["extra"]["upcoming"] is False, stale_after["extra"])
check("sort_for_page recomputes a stale in_progress=True to False along with it",
      stale_after["extra"]["in_progress"] is False, stale_after["extra"])
check("sort_for_page leaves a genuinely still-ahead record's flags untouched",
      ahead_after["extra"]["upcoming"] is True, ahead_after["extra"])

geocode.locate = _fake_geocode_locate
photos.for_city = _fake_photos_for_city
try:
    stale_page = _render_page(refreshed)
finally:
    geocode.locate = _orig_geocode_locate
    photos.for_city = _orig_photos_for_city
s_nu_up, s_nu_recent, _, _ = _domain_blocks(stale_page)

check("a record with a stale-but-corrected upcoming flag renders under Recent, not Upcoming",
      "Stale Meeting 2020" in s_nu_recent and "Stale Meeting 2020" not in s_nu_up)

_map_start = stale_page.find('<h4>Map</h4>')
_map_end = stale_page.find('</figure>', _map_start) if _map_start >= 0 else -1
_map_html = stale_page[_map_start:_map_end] if _map_start >= 0 else ""
check("the corrected-to-recent record is off the map; the genuinely-ahead one is on it",
      bool(_map_html) and "Stale Meeting 2020" not in _map_html
      and "Genuinely Ahead 2099" in _map_html,
      _map_html[:300])

_timeline_svg = figures.conference_timeline([], [stale_after], max_rows=14)
check("the corrected-to-recent record's own timeline bar is grey (uncoloured), "
      "not blue (upcoming) or amber (running now)",
      "var(--text-mute)" in _timeline_svg and "var(--io)" not in _timeline_svg
      and "var(--no)" not in _timeline_svg,
      _timeline_svg)

from tools.news import venue                        # noqa: E402

# The cascade prefers structured data and only then the conference's own page.
r_clean = rec("NuFact 2026", "https://nufact.example.org/", "Shanghai", "CN",
              "2026-08-31", "2026-09-05", "nu-unbound")
check("a clean place string is used as-is",
      venue.address_of(r_clean, _Log()) == "Shanghai, CN")

r_indico = {"id": "x", "title": "Invisibles", "url": "https://ex.org/",
            "extra": {"place": "", "city": "", "country_code": "",
                      "address": "Sede Afundación, Cantón Grande 8, "
                                 "A Coruña, 15003, Spain"}}
check("Indico's verbose address is used when there is no clean place",
      "A Coruña" in (venue.address_of(r_indico, _Log()) or ""))

r_none = {"id": "y", "title": "Nowhere", "url": "", "extra": {}}
check("a record with nothing to go on yields no address",
      venue.address_of(r_none, _Log()) is None)
check("and therefore no coordinates",
      venue.locate_record(r_none, _Log()) is None)

# Two different kinds of "nothing", which must be cached differently (final
# whole-branch review, IMPORTANT): a page genuinely FETCHED and found to
# carry no address is cached, exactly like geocode.py caches an empty
# geocoder answer as null "for good". A page NOT reached at all — http_get
# returns None alike for a connection error, a timeout and a non-200 — is
# transient and must NOT be cached, or a 403 hit once (a hostile
# User-Agent filter) or an hour of maintenance would cost that conference
# its map marker forever, exactly the failure geocode.py's own docstring
# warns against and venue.py used to not follow.

# 1. A genuine fetch that carries nothing: cached, fetched once.
_calls = []


def _counting_http_get_found(url, **kwargs):
    _calls.append(url)
    return _FakeResponse("<html><body>no structured data here</body></html>")


_orig_http_get = venue.http_get
_orig_venue_cache = venue.VENUE_CACHE
_orig_mem_cache = venue._cache
venue.http_get = _counting_http_get_found
venue.VENUE_CACHE = Path(tempfile.mkdtemp()) / "venuecache.json"
venue._cache = None                  # do not inherit an earlier block's cache
try:
    first = venue._from_page("https://empty.example.org/", _Log())
    # Force the SECOND call to re-parse the JSON file rather than reuse the
    # in-memory dict left by the first call — otherwise this only proves the
    # in-memory short-circuit works, and never touches VENUE_CACHE.read_text
    # at all, which is half of what "cached to disk" is supposed to mean.
    venue._cache = None
    second = venue._from_page("https://empty.example.org/", _Log())
    check("a page genuinely fetched but carrying nothing is fetched once, "
          "then cached",
          len(_calls) == 1, f"http_get called {len(_calls)} times: {_calls}")
    check("both calls agree it found nothing",
          first is None and second is None)
finally:
    venue.http_get = _orig_http_get
    venue.VENUE_CACHE = _orig_venue_cache
    venue._cache = _orig_mem_cache

# 2. A page NOT reached at all (http_get returns None): never cached, so
# every call retries — the regression this branch's final review found.
_unreached_calls = []


def _counting_http_get_unreached(url, **kwargs):
    _unreached_calls.append(url)
    return None                          # connection error / timeout / non-200


_orig_http_get = venue.http_get
_orig_venue_cache = venue.VENUE_CACHE
_orig_mem_cache = venue._cache
venue.http_get = _counting_http_get_unreached
venue.VENUE_CACHE = Path(tempfile.mkdtemp()) / "venuecache.json"
venue._cache = None
try:
    first = venue._from_page("https://down.example.org/", _Log())
    venue._cache = None                  # force a cold reload, as above
    second = venue._from_page("https://down.example.org/", _Log())
    check("a page that was never reached is retried on the next call, not cached",
          len(_unreached_calls) == 2,
          f"http_get called {len(_unreached_calls)} times: {_unreached_calls}")
    check("an unreached page still answers None both times",
          first is None and second is None)
finally:
    venue.http_get = _orig_http_get
    venue.VENUE_CACHE = _orig_venue_cache
    venue._cache = _orig_mem_cache


# Indico's own JSON-LD literally says `"address":"No address set"` when an
# organiser never filled the venue in (seen on a real record while building
# this cascade: indico.cern.ch/event/1677041/). That string must not be
# mistaken for a real address.
_placeholder_html = (
    '<script type="application/ld+json">'
    '{"@type": "Event", "name": "No location set",'
    ' "location": {"@type": "Place", "address": "No address set"}}'
    '</script>')


def _placeholder_http_get(url, **kwargs):
    return _FakeResponse(_placeholder_html)


_orig_http_get = venue.http_get
_orig_venue_cache = venue.VENUE_CACHE
_orig_mem_cache = venue._cache
venue.http_get = _placeholder_http_get
venue.VENUE_CACHE = Path(tempfile.mkdtemp()) / "venuecache.json"
venue._cache = None
try:
    found = venue._from_page("https://indico.example.org/event/1/", _Log())
    check("Indico's 'No address set' placeholder is not mistaken for a real address",
          found is None, f"got {found!r}")
finally:
    venue.http_get = _orig_http_get
    venue.VENUE_CACHE = _orig_venue_cache
    venue._cache = _orig_mem_cache


# The microdata fallback (schema.org itemprop=... without a JSON-LD script)
# used to scan the whole page for each of the five address fields
# independently, with no itemscope/itemtype boundary — so a page carrying
# more than one microdata block (a footer Organization, then the actual
# venue) would stitch the first streetAddress it found to the first
# addressLocality it found to the first addressCountry it found, regardless
# of which block each came from. That is exactly the "a dot in roughly the
# right country is worse than no dot" failure this whole module exists to
# avoid, so the fallback was removed rather than scoped: this project has no
# HTML parser to track itemscope boundaries correctly, and JSON-LD (walked
# with real @type/nesting checks, above) already covers the pages that
# publish structured venue data properly.
_two_block_html = (
    '<div itemscope itemtype="http://schema.org/Organization">'
    '  <span itemprop="streetAddress">1 Institute Ave</span>'
    '  <span itemprop="addressCountry">Testland</span>'
    '</div>'
    '<div itemscope itemtype="http://schema.org/Place">'
    '  <span itemprop="addressLocality">Realcity</span>'
    '  <span itemprop="addressCountry">Otherland</span>'
    '</div>')


def _two_block_http_get(url, **kwargs):
    return _FakeResponse(_two_block_html)


_orig_http_get = venue.http_get
_orig_venue_cache = venue.VENUE_CACHE
_orig_mem_cache = venue._cache
venue.http_get = _two_block_http_get
venue.VENUE_CACHE = Path(tempfile.mkdtemp()) / "venuecache.json"
venue._cache = None
try:
    found = venue._from_page("https://example.org/two-blocks/", _Log())
    blended = found is not None and "Institute Ave" in found and "Realcity" in found
    check("a page with two microdata blocks never blends fields across them",
          not blended, f"got {found!r}")
finally:
    venue.http_get = _orig_http_get
    venue.VENUE_CACHE = _orig_venue_cache
    venue._cache = _orig_mem_cache

# A trailing period after the country name — seen in a real record
# ("Heidelberg, Germany.") — must not stop the country from being recognised.
check("a trailing period after the country name does not break the split",
      venue._split_country("Heidelberg, Germany.") == ("Heidelberg", "DE"),
      f"got {venue._split_country('Heidelberg, Germany.')!r}")


# Minor (final whole-branch review): venue._cache_save and geocode._save must
# go through common.write_json (atomic: write to .tmp, then rename) rather
# than Path.write_text (truncates before writing — an interrupted run leaves
# a truncated file that each module's own `except (FileNotFoundError,
# ValueError)` then silently reads back as an empty cache). Call-monitoring,
# not a crash simulation: this proves the save path is routed through the
# atomic helper, which is the property asked for.
import tools.news.venue as _venue_mod                # noqa: E402
import tools.news.geocode as _geocode_mod            # noqa: E402

_write_json_calls = []
_orig_venue_write_json = _venue_mod.write_json
_orig_geocode_write_json = _geocode_mod.write_json
_venue_mod.write_json = lambda path, payload: _write_json_calls.append(("venue", path))
_geocode_mod._cache = {"probe|XX": None}
_geocode_mod.write_json = lambda path, payload: _write_json_calls.append(("geocode", path))
try:
    _venue_mod._cache = {"https://probe.example.org/": None}
    _venue_mod._cache_save()
    _geocode_mod._save()
finally:
    _venue_mod.write_json = _orig_venue_write_json
    _geocode_mod.write_json = _orig_geocode_write_json

check("venue._cache_save writes through the atomic common.write_json helper",
      ("venue", venue.VENUE_CACHE) in _write_json_calls, _write_json_calls)
check("geocode._save writes through the atomic common.write_json helper",
      any(tag == "geocode" for tag, _ in _write_json_calls), _write_json_calls)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — three sources, merged into one listing")
