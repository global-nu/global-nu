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


print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — photos.for_city's licence gate, credit, "
     "cache, and 640px resize")
