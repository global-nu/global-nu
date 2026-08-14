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
from tools.news import fetch_inspire, fetch_nu_unbound, render   # noqa: E402

problems: list[str] = []
checks = 0


class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


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

# render.conferences() must split on whether a conference is still ahead
# (extra.upcoming), not on which part of the field it covers (extra.scope,
# "neutrino" vs "general" — the axis conferences.split_scope() uses for the
# two sections a later task builds). Redirected to a scratch file so this
# does not overwrite the real site-src/content/conferences.md.
render.CONFERENCES_PAGE = Path(tempfile.mkdtemp()) / "conferences.md"


def _render_split(records):
    render.conferences(records, _Log(), stamp="test")
    text = render.CONFERENCES_PAGE.read_text(encoding="utf-8")
    upcoming_block, _, recent_block = text.partition('<h2>Recent</h2>')
    return upcoming_block, recent_block


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

up_block, recent_block = _render_split([still_ahead, already_over, general_upcoming])
check("a record with extra.upcoming=True renders under Upcoming, not Recent",
      "Still Ahead 2099" in up_block and "Still Ahead 2099" not in recent_block)
check("a record with extra.upcoming=False renders under Recent, not Upcoming",
      "Already Over 2020" in recent_block and "Already Over 2020" not in up_block)
check("a record whose extra.scope is 'general' is not thereby treated as concluded",
      "General Physics Meeting 2099" in up_block
      and "General Physics Meeting 2099" not in recent_block)

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

# The failure cache: a page that answers but carries nothing is fetched once,
# never again. Monkeypatch venue.http_get to count calls.
_calls = []


def _counting_http_get(url, **kwargs):
    _calls.append(url)
    return None                          # "unreachable", same as a dead page


_orig_http_get = venue.http_get
_orig_venue_cache = venue.VENUE_CACHE
_orig_mem_cache = venue._cache
venue.http_get = _counting_http_get
venue.VENUE_CACHE = Path(tempfile.mkdtemp()) / "venuecache.json"
venue._cache = None                  # do not inherit an earlier block's cache
try:
    first = venue._from_page("https://dead.example.org/", _Log())
    # Force the SECOND call to re-parse the JSON file rather than reuse the
    # in-memory dict left by the first call — otherwise this only proves the
    # in-memory short-circuit works, and never touches VENUE_CACHE.read_text
    # at all, which is half of what "cached to disk" is supposed to mean.
    venue._cache = None
    second = venue._from_page("https://dead.example.org/", _Log())
    check("a page yielding nothing is fetched once",
          len(_calls) == 1, f"http_get called {len(_calls)} times: {_calls}")
    check("both calls agree it found nothing",
          first is None and second is None)
finally:
    venue.http_get = _orig_http_get
    venue.VENUE_CACHE = _orig_venue_cache
    venue._cache = _orig_mem_cache


# Indico's own JSON-LD literally says `"address":"No address set"` when an
# organiser never filled the venue in (seen on a real record while building
# this cascade: indico.cern.ch/event/1677041/). That string must not be
# mistaken for a real address.
class _FakeResponse:
    def __init__(self, text):
        self.text = text


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

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — three sources, merged into one listing")
