#!/usr/bin/env python3
"""tools.news.photos.for_city — the licence gate, the credit, and the cache.

    ./.venv/bin/python3 tools/tests/test_photos.py

Covered: a city whose only candidate carries a licence that forbids reuse
yields None, never a guess; a returned record always carries an author, a
licence and a Commons file-page link (the three parts a credit needs — "a
photograph without its credit is a licence violation, not a cosmetic slip");
the same city asked twice makes exactly one call to
tools.fetch_commons_images.search; and, separately, `_save_thumb`'s own
resize actually lands at 640px on the long side using real Pillow, with a
fake network layer rather than a live Commons fetch.

`photos.search` and `photos._save_thumb` are monkeypatched exactly the way
tools/tests/test_conferences.py monkeypatches venue.http_get: reassigned on
the module, restored in a `finally`. This suite never touches the network.
"""
from __future__ import annotations

import datetime as _dt
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import photos                        # noqa: E402

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
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass


def _isolate() -> None:
    """A fresh disk cache and image directory per block, so one check's
    fixtures cannot leak into the next — the same isolation
    test_conferences.py gives venue.VENUE_CACHE."""
    photos.PHOTO_CACHE = Path(tempfile.mkdtemp()) / "photocache.json"
    photos._cache = None
    photos.IMAGES_SRC = Path(tempfile.mkdtemp())
    photos._revalidated_this_run = 0     # fresh per-run revalidation budget


def _good_candidate(**over):
    cand = {
        "title": "File:Trieste Old Port.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Trieste_Old_Port.jpg",
        "thumb": "https://upload.wikimedia.org/fake/trieste.jpg",
        "author": "Fermilab, Reidar Hahn",
        "licence": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
    }
    cand.update(over)
    return cand


def _fake_save_thumb_ok(url, dest, log):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"not-really-a-jpeg-but-good-enough-for-the-cache-check")
    return True


_orig_search = photos.search
_orig_save_thumb = photos._save_thumb


# --------------------------------------------------------------------- #
# 1. no acceptable licence -> None
# --------------------------------------------------------------------- #
_isolate()


def _search_all_refused(term, query, limit=5):
    return [_good_candidate(licence="All rights reserved", licence_url="")]


photos.search = _search_all_refused
photos._save_thumb = _fake_save_thumb_ok
try:
    result = photos.for_city("Nowhereville", "XX", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("a city with no acceptable licence yields None", result is None, result)


# --------------------------------------------------------------------- #
# 2. a returned record always carries author, licence and page
# --------------------------------------------------------------------- #
_isolate()


def _search_one_good(term, query, limit=5):
    return [_good_candidate()]


photos.search = _search_one_good
photos._save_thumb = _fake_save_thumb_ok
try:
    result = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("a returned record carries an author", bool(result and result.get("author")), result)
check("a returned record carries a licence", bool(result and result.get("licence")), result)
check("a returned record carries a Commons file-page link",
      bool(result and result.get("page")), result)
check("the author is the short form short_author produces, not the raw field",
      result is not None and result["author"] == "Fermilab, Reidar Hahn", result)


# A candidate missing just one of the three (author, licence, page) is
# skipped entirely rather than shipped with a hole in its credit.
_isolate()


def _search_missing_author(term, query, limit=5):
    return [_good_candidate(author="")]


photos.search = _search_missing_author
photos._save_thumb = _fake_save_thumb_ok
try:
    result = photos.for_city("Blankville", "XX", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("a candidate missing its author is skipped, not published without one",
      result is None, result)


# A candidate that is not a photograph at all — a coat of arms, a topographic
# map, a slogan graphic — is refused even though it is genuinely, correctly
# licensed. Found for real against live data: Commons' search for "Tendo"
# returned "File:Emblem of Tendo, Yamagata (1956-1963).svg" as its first
# result, publc-domain and fully credited, which is not a photograph of
# Tendo and rendered as a solid black square once downloaded (see
# _save_thumb's alpha-compositing fix). The first candidate here is exactly
# that shape; the second is a real photograph, and must be the one used.
_isolate()


def _search_svg_then_photo(term, query, limit=5):
    return [
        _good_candidate(title="File:Emblem of Tendo, Yamagata.svg",
                        page="https://commons.wikimedia.org/wiki/File:Emblem_of_Tendo.svg"),
        _good_candidate(title="File:Tendo cityscape.jpg",
                        page="https://commons.wikimedia.org/wiki/File:Tendo_cityscape.jpg"),
    ]


photos.search = _search_svg_then_photo
photos._save_thumb = _fake_save_thumb_ok
try:
    result = photos.for_city("Tendo", "JP", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("an .svg candidate (emblem/map/flag, not a photograph) is skipped",
      result is not None and result["page"].endswith("Tendo_cityscape.jpg"),
      result)


# --------------------------------------------------------------------- #
# 3. the same city asked twice makes one network call
# --------------------------------------------------------------------- #
_isolate()
calls: list[tuple] = []


def _counting_search(term, query, limit=5):
    calls.append((term, query))
    return [_good_candidate()]


photos.search = _counting_search
photos._save_thumb = _fake_save_thumb_ok
try:
    first = photos.for_city("Shanghai", "CN", _Log())
    second = photos.for_city("Shanghai", "CN", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("the same city asked twice makes exactly one call to search()",
      len(calls) == 1, f"search() called {len(calls)} times: {calls}")
check("both calls return the same record",
      first is not None and first == second, (first, second))

# And a THIRD call, after nothing was reset, from a cold in-memory cache
# (_cache reloaded from disk) still makes no further call — proving the
# cache genuinely persisted to PHOTO_CACHE, not only the in-process dict.
photos._cache = None
photos.search = _counting_search
try:
    third = photos.for_city("Shanghai", "CN", _Log())
finally:
    photos.search = _orig_search
check("reloading the cache from disk still avoids a second network call",
      len(calls) == 1 and third == first,
      f"search() called {len(calls)} times; third={third}")


# --------------------------------------------------------------------- #
# 4. _save_thumb actually resizes to 640px on the long side (real Pillow,
#    fake network) — the numeric requirement Step 3 of the brief names
#    explicitly, checked independently of the licence/cache logic above.
# --------------------------------------------------------------------- #
_isolate()
from PIL import Image                                 # noqa: E402

big = Image.new("RGB", (2000, 1000), (120, 140, 160))
buf = io.BytesIO()
big.save(buf, "JPEG")
fake_bytes = buf.getvalue()


def _fake_fetch_bytes(url, log):
    return fake_bytes


_orig_fetch_bytes = photos._fetch_bytes
photos._fetch_bytes = _fake_fetch_bytes
dest = photos.IMAGES_SRC / "conf-resize-check.jpg"
try:
    ok = photos._save_thumb("https://upload.example/fake.jpg", dest, _Log())
finally:
    photos._fetch_bytes = _orig_fetch_bytes

check("_save_thumb reports success", ok, ok)
if ok and dest.exists():
    with Image.open(dest) as out:
        w, h = out.size
    check("the resized image is 640px on its long side, not 1600",
          max(w, h) == 640, f"got {w}x{h}")
    check("the resized image keeps its 2:1 aspect ratio",
          abs(w / h - 2.0) < 0.02, f"got {w}x{h}")
else:
    check("the resized file exists on disk", False, "dest never written")


# --------------------------------------------------------------------- #
# 5. an RGBA image with a transparent background is composited onto white,
#    not silently flattened to black. Real Pillow, fake network. This is
#    the actual failure a live run hit (Tendo's accepted candidate, before
#    _looks_like_a_photograph existed, rendered as a solid black square in
#    the browser) — reproduced here directly against _save_thumb rather
#    than only guarded against upstream by the title filter, since a
#    genuine photograph can carry an alpha border too.
# --------------------------------------------------------------------- #
_isolate()

transparent = Image.new("RGBA", (400, 300), (0, 0, 0, 0))     # fully transparent
buf2 = io.BytesIO()
transparent.save(buf2, "PNG")
fake_rgba_bytes = buf2.getvalue()


def _fake_fetch_rgba(url, log):
    return fake_rgba_bytes


photos._fetch_bytes = _fake_fetch_rgba
dest2 = photos.IMAGES_SRC / "conf-alpha-check.jpg"
try:
    ok2 = photos._save_thumb("https://upload.example/fake.png", dest2, _Log())
finally:
    photos._fetch_bytes = _orig_fetch_bytes

check("_save_thumb reports success for a transparent RGBA source", ok2, ok2)
if ok2 and dest2.exists():
    with Image.open(dest2) as out2:
        sample = out2.convert("RGB").getpixel((out2.width // 2, out2.height // 2))
    check("a fully transparent image is composited onto white, not left black",
          sample == (255, 255, 255), f"got pixel {sample}")
else:
    check("the alpha-composited file exists on disk", False, "dest2 never written")


# --------------------------------------------------------------------- #
# 6. two cities with the SAME NAME but different country codes must never
#    collide — different files, different credits, and neither overwrites
#    the other's file on disk or its cached answer.
#
#    Found by review, not by a test: the cache key was already (city,
#    country_code), but _slug and the Commons query were both keyed by city
#    alone. Cambridge, GB gets cached first, pointing at
#    images/conf-cambridge.jpg with its own author/licence. Cambridge, US
#    then correctly misses the cache (a different key), searches, downloads
#    ITS OWN photo — and writes it to the SAME path, silently overwriting
#    the GB file. The next run's disk-existence check (for_city's `if
#    (IMAGES_SRC / Path(cached["file"]).name).exists(): return cached`)
#    then finds the file still there and happily returns GB's cached
#    author/licence over what is now the US photograph: a real photographer
#    's name attached to someone else's work. This is that failure inverted
#    — not an uncredited photograph, but a MIS-credited one.
#
#    _search_by_country below also proves the query is actually
#    disambiguated (not just the cache key): it raises if for_city ever
#    asks Commons for "Cambridge" without a country attached, and returns a
#    different photograph for each of the two queries it does recognise.
# --------------------------------------------------------------------- #
_isolate()


def _search_by_country(term, query, limit=5):
    if "United Kingdom" in query:
        return [_good_candidate(
            title="File:Cambridge UK punting.jpg",
            page="https://commons.wikimedia.org/wiki/File:Cambridge_UK_punting.jpg",
            thumb="https://upload.wikimedia.org/fake/cambridge-uk.jpg",
            author="Andrew Dunn", licence="CC BY-SA 2.0",
            licence_url="https://creativecommons.org/licenses/by-sa/2.0")]
    if "United States" in query:
        return [_good_candidate(
            title="File:Harvard Square Cambridge MA.jpg",
            page="https://commons.wikimedia.org/wiki/File:Harvard_Square_Cambridge_MA.jpg",
            thumb="https://upload.wikimedia.org/fake/cambridge-ma.jpg",
            author="John Phelan", licence="CC BY 3.0",
            licence_url="https://creativecommons.org/licenses/by/3.0")]
    raise AssertionError(f"query not disambiguated by country: {query!r}")


# Content, not just a path, is what a filename collision actually clobbers:
# a fake _save_thumb that always writes the SAME placeholder bytes (like
# _fake_save_thumb_ok elsewhere in this file) would make "both files exist
# on disk" pass even when GB and US share one path, since the second write
# just re-creates an identical-looking file at the identical path — that
# would be a vacuous check of exactly the failure this section exists to
# catch. This one tags each file with the URL it was fetched from, so the
# check below can tell whether the byte on disk under GB's own name still
# came from GB's own thumb URL after US has also been looked up.
def _fake_save_thumb_tagged(url, dest, log):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(f"photo-bytes-from:{url}".encode())
    return True


photos.search = _search_by_country
photos._save_thumb = _fake_save_thumb_tagged
try:
    gb = photos.for_city("Cambridge", "GB", _Log())
    us = photos.for_city("Cambridge", "US", _Log())
    # A third call for GB, forcing a cold reload of the disk cache, proves
    # US's later write never clobbered GB's own cached answer.
    photos._cache = None
    gb_again = photos.for_city("Cambridge", "GB", _Log())
finally:
    photos.search = _orig_search
    photos._save_thumb = _orig_save_thumb

check("Cambridge GB and Cambridge US resolve to different files",
      gb is not None and us is not None and gb["file"] != us["file"],
      (gb and gb.get("file"), us and us.get("file")))
check("Cambridge GB and Cambridge US carry different credits",
      gb is not None and us is not None and gb["author"] != us["author"],
      (gb and gb.get("author"), us and us.get("author")))

gb_bytes = (gb and (photos.IMAGES_SRC / Path(gb["file"]).name).read_bytes()) if gb else None
us_bytes = (us and (photos.IMAGES_SRC / Path(us["file"]).name).read_bytes()) if us else None
check("the file under GB's own name still holds GB's own photo bytes, "
      "not US's (the file was not silently overwritten)",
      gb_bytes is not None and b"cambridge-uk" in gb_bytes
      and b"cambridge-ma" not in gb_bytes,
      gb_bytes)
check("the file under US's own name holds US's own photo bytes, not GB's",
      us_bytes is not None and b"cambridge-ma" in us_bytes
      and b"cambridge-uk" not in us_bytes,
      us_bytes)
check("Cambridge GB's cached answer survives Cambridge US being looked up later",
      gb_again == gb, (gb, gb_again))


# --------------------------------------------------------------------- #
# 7. _slug truncates the CITY portion, not the joined "city-code" string —
#    a long city name must never cost the disambiguating country code. Real
#    city names never reach this length, so this is a direct unit check of
#    the function rather than something reachable through for_city today.
# --------------------------------------------------------------------- #
_long_city = "A" * 80
_slug_result = photos._slug(_long_city, "GB")
check("a long city name's slug still ends with its country code",
      _slug_result.endswith("-gb"), _slug_result)
check("the slug never exceeds 60 characters",
      len(_slug_result) <= 60, (_slug_result, len(_slug_result)))

_short_slug = photos._slug("Cambridge", "GB")
check("a short city name's slug is unaffected by the truncation-order fix",
      _short_slug == "conf-cambridge-gb", _short_slug)


# --------------------------------------------------------------------- #
# 8. Revalidation (final whole-branch review, IMPORTANT): a cached credit's
#    author/licence/links must not be trusted forever. An entry old enough
#    (>= photos.REVALIDATE_AFTER_DAYS) is checked again against Commons, by
#    the exact file title stored in `page` — not a fresh full-text search,
#    which could legitimately stop returning an unchanged file for reasons
#    that have nothing to do with its status.
# --------------------------------------------------------------------- #
def _stale_entry(**over):
    e = {
        "file": "images/conf-trieste-it.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Trieste_Old_Port.jpg",
        "author": "Old Author",
        "licence": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "cached_at": (_dt.date.today()
                     - _dt.timedelta(days=photos.REVALIDATE_AFTER_DAYS + 1)).isoformat(),
    }
    e.update(over)
    return e


def _seed(city, country, entry):
    """Preload the cache with one entry and put a real file on disk for it
    — for_city's disk-existence check must pass before revalidation logic
    is ever reached."""
    cache = photos._cache_load()
    cache[photos._key(city, country)] = entry
    photos._cache_save()
    (photos.IMAGES_SRC / Path(entry["file"]).name).parent.mkdir(
        parents=True, exist_ok=True)
    (photos.IMAGES_SRC / Path(entry["file"]).name).write_bytes(b"old-jpeg-bytes")


def _commons_page(*, missing=False, licence="CC BY-SA 4.0", artist="New Author"):
    if missing:
        return {"query": {"pages": {"-1": {"ns": 6,
                                            "title": "File:Trieste Old Port.jpg",
                                            "missing": ""}}}}
    return {"query": {"pages": {"98765": {
        "pageid": 98765, "ns": 6, "title": "File:Trieste Old Port.jpg",
        "imageinfo": [{"extmetadata": {
            "LicenseShortName": {"value": licence},
            "Artist": {"value": artist},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
        }}]}}}}


_orig_commons_api = photos.commons_api


def _refuse_search(term, query, limit=5):
    raise AssertionError("for_city should not fall through to a fresh "
                          "search while a cached entry still exists")


# 8a. A due entry with an unchanged, still-acceptable licence: revalidated,
#     cached_at refreshed, and a genuinely corrected Artist field reaches
#     the returned credit.
_isolate()
_seed("Trieste", "IT", _stale_entry())
_api_calls = []


def _api_ok_new_author(params):
    _api_calls.append(params)
    return _commons_page(artist="New Author")


photos.commons_api = _api_ok_new_author
photos.search = _refuse_search
try:
    result = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a due entry triggers exactly one revalidation call",
      len(_api_calls) == 1, _api_calls)
check("revalidation asks about the exact cached title, not a fresh search",
      _api_calls and _api_calls[0].get("titles") == "File:Trieste Old Port.jpg",
      _api_calls)
check("a corrected Artist field on Commons reaches the returned credit",
      result is not None and result["author"] == "New Author", result)
check("revalidating a still-good entry stamps a fresh cached_at",
      result is not None and result["cached_at"] == _dt.date.today().isoformat(),
      result)

# 8b. A FRESH entry (cached_at == today) is not due: no revalidation call.
_isolate()
_seed("Trieste", "IT", _stale_entry(cached_at=_dt.date.today().isoformat()))
_api_calls2 = []
photos.commons_api = lambda params: (_api_calls2.append(params) or _commons_page())
photos.search = _refuse_search
try:
    result2 = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a freshly-cached entry is returned without a revalidation call",
      len(_api_calls2) == 0 and result2 is not None and result2["author"] == "Old Author",
      (_api_calls2, result2))

# 8c. A takedown: the file is gone from Commons. The photograph must STOP
#     being served — for_city returns None, and the None is itself cached
#     so tomorrow's run does not keep asking about a file that is gone.
_isolate()
_seed("Trieste", "IT", _stale_entry())
photos.commons_api = lambda params: _commons_page(missing=True)
photos.search = _refuse_search
try:
    result3 = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a file removed from Commons is no longer served",
      result3 is None, result3)
check("the takedown is itself cached (no photo, not re-served next call)",
      photos._cache.get(photos._key("Trieste", "IT")) is None,
      photos._cache.get(photos._key("Trieste", "IT")))

# 8d. A licence that no longer qualifies: same "stop serving" outcome,
#     judged by the identical licence_ok this module always uses.
_isolate()
_seed("Trieste", "IT", _stale_entry())
photos.commons_api = lambda params: _commons_page(licence="All rights reserved")
photos.search = _refuse_search
try:
    result4 = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a licence downgraded below the acceptable list is no longer served",
      result4 is None, result4)

# 8e. A per-run budget, in the style of geocode.MAX_NEW_PER_RUN: once spent,
#     further due entries are left exactly as cached (old author, old
#     cached_at) rather than triggering more Commons requests this run.
_isolate()
_seed("Trieste", "IT", _stale_entry())
photos._revalidated_this_run = photos.REVALIDATE_PER_RUN     # budget exhausted
_api_calls5 = []
photos.commons_api = lambda params: (_api_calls5.append(params) or _commons_page())
photos.search = _refuse_search
try:
    result5 = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a due entry is left untouched once the per-run revalidation budget is spent",
      len(_api_calls5) == 0 and result5 is not None and result5["author"] == "Old Author",
      (_api_calls5, result5))

# 8f. A revalidation fetch that fails outright (Commons unreachable) is
#     treated as transient, not as a takedown: the old credit keeps serving.
_isolate()
_seed("Trieste", "IT", _stale_entry())


def _api_raises(params):
    raise OSError("connection refused")


photos.commons_api = _api_raises
photos.search = _refuse_search
try:
    result6 = photos.for_city("Trieste", "IT", _Log())
finally:
    photos.commons_api = _orig_commons_api
    photos.search = _orig_search

check("a failed revalidation fetch keeps serving the old credit rather than "
      "treating a network error as a takedown",
      result6 is not None and result6["author"] == "Old Author", result6)


# --------------------------------------------------------------------- #
# 9. Minor (final whole-branch review): photos._cache_save must go through
#    common.write_json (atomic: .tmp then rename), not Path.write_text
#    (truncates before writing — an interrupted run leaves a truncated
#    file that _cache_load's except clause silently reads back as {}).
#    Call-monitoring, not a crash simulation: proves the save path is
#    routed through the atomic helper.
# --------------------------------------------------------------------- #
_isolate()
_write_json_calls = []
_orig_photos_write_json = photos.write_json
photos.write_json = lambda path, payload: _write_json_calls.append(path)
try:
    photos._cache = {"probe|xx": None}
    photos._cache_save()
finally:
    photos.write_json = _orig_photos_write_json

check("photos._cache_save writes through the atomic common.write_json helper",
      _write_json_calls == [photos.PHOTO_CACHE], _write_json_calls)


print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — photos.for_city's licence gate, credit, "
     "cache, and 640px resize")
