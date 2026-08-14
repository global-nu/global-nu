"""A photograph of the host city — or nothing, never one without its credit.

    photos.for_city("Shanghai", "CN", log) -> {"file", "page", "author",
                                               "licence", "licence_url"} | None

Consumes exactly three names from tools.fetch_commons_images, per the brief:
`search` (Commons image search, one candidate list per query), `licence_ok`
(the one rule for what may be republished — CC0, public domain, CC BY or
CC BY-SA, nothing else — re-applied here explicitly rather than trusted off
a candidate dict's own `accepted` flag, since a candidate is easy to build by
hand in a caller or a test and this module should not have to trust that
whoever built it also ran the check), and `short_author` (the same collapse
that turns a seven-hundred-name collaboration credit into one usable line —
see tools/tests/test_credits.py). No new licence rule is written here.

City, not venue: the query is always the conference's *city* — "Shanghai",
never "Sede Afundación" — because Commons has a good photograph of the
former and essentially never of the latter. Cities repeat between
conferences (two workshops in Trieste in the same year, say), so a result is
cached by (city, country_code): the same city is looked up on Commons at
most once per process (PHOTO_CACHE below is loaded lazily and updated in
memory), AND, once written to disk, never looked up again on a later run
either — the same idea as venue.py's VENUE_CACHE, and for the same two
reasons: politeness to somebody else's API, and a daily job that should not
re-download an unchanging photograph every morning. A negative result (no
usable candidate) is cached too, exactly like venue.py's cache of a page
that answered but carried nothing — a cache that only remembered successes
would re-query every unphotographed city every morning.

Every accepted image is resized to 640px on its long side — site.yaml's
`images.max_side: 1600` is sized for a results-page figure, not a thumbnail
in a map card — and written under site-src/images-src/, where build.py's
ordinary image pipeline picks it up like any other picture already there.
Nothing here is ever hot-linked to Commons at render time: the whole point
of downloading and resizing is that the published page makes no request to
an external host to show the picture.

If a city yields no licence-clean, fully-credited candidate, `for_city`
returns None. `None` is always an acceptable answer here; a photograph
missing its author, its licence or its Commons file-page link is not, so a
candidate lacking any of the three is skipped rather than shipped short —
"a photograph without its credit is a licence violation, not a cosmetic
slip."
"""

from __future__ import annotations

import io
import json
import logging
import re
import urllib.request
from pathlib import Path

from tools.fetch_commons_images import UA, licence_ok, search, short_author

ROOT = Path(__file__).resolve().parents[2]
IMAGES_SRC = ROOT / "site-src" / "images-src"
PHOTO_CACHE = ROOT / "var" / "news" / "photocache.json"

# 640, not site.yaml's 1600: see the module docstring.
MAX_SIDE = 640
JPEG_QUALITY = 78
CANDIDATES_PER_CITY = 5

# A "photograph", not merely a freely-licensed file: Commons' full-text
# search for a city name routinely surfaces its municipal coat of arms, a
# topographic map, or a tourism-board slogan graphic — each one a genuine,
# correctly-licensed File: page that is not a photograph of anything. Found
# for real against live data (Corfu, Daejeon, Tendo all resolved to one of
# these on the first run), not invented: every one of the three was an .svg,
# and Tendo's ("Emblem of Tendo, Yamagata (1956-1963).svg") rendered as a
# solid black square in the browser once downloaded — see _save_thumb's
# alpha-compositing comment for why. SVG is disqualifying outright: a vector
# file on Commons is a diagram, flag, map or emblem, essentially never a
# photograph. The title-prefix list below catches the same content when it
# happens to be uploaded as a raster (PNG) image instead — same non-photo
# subjects, different file format.
_NON_PHOTO_SUFFIXES = (".svg",)
_NON_PHOTO_PREFIXES = (
    "flag of", "coat of arms of", "crest of", "seal of", "emblem of",
    "logo of", "locator map", "map of", "topographic map",
)


def _looks_like_a_photograph(title: str) -> bool:
    name = title.split(":", 1)[-1].strip().lower()
    if name.endswith(_NON_PHOTO_SUFFIXES):
        return False
    return not name.startswith(_NON_PHOTO_PREFIXES)


_cache: dict[str, dict | None] | None = None


def _key(city: str, country_code: str) -> str:
    return f"{city.strip().lower()}|{(country_code or '').strip().upper()}"


def _slug(city: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", city.strip().lower()).strip("-")
    return f"conf-{text or 'city'}"[:60]


def _cache_load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PHOTO_CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _cache_save() -> None:
    PHOTO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    PHOTO_CACHE.write_text(
        json.dumps(_cache, indent=1, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")


# --------------------------------------------------------------------------- #
# download + resize — a seam of its own so a test can prove the licence gate
# and the cache without touching the network or requiring Pillow, and prove
# the resize separately without touching the network either.
# --------------------------------------------------------------------------- #
def _fetch_bytes(url: str, log: logging.Logger) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as exc:                              # noqa: BLE001
        log.warning("photos: download failed for %s (%s)", url, exc.__class__.__name__)
        return None


def _save_thumb(url: str, dest: Path, log: logging.Logger) -> bool:
    """Fetch `url` and write it to `dest`, resized to MAX_SIDE on its long
    side. False on any failure — a photo this project cannot process is
    skipped, the same "None is fine, a guess/broken file is not" rule as
    everywhere else here."""
    data = _fetch_bytes(url, log)
    if data is None:
        return False
    try:
        from PIL import Image
    except ImportError:
        log.warning("photos: Pillow not installed — the photo is skipped, "
                    "not published unresized")
        return False
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.mode in ("RGBA", "LA", "P"):
            # A naive .convert("RGB") on an image carrying transparency
            # DISCARDS the alpha channel rather than compositing it, and
            # Commons' thumbnail renderer for anything non-photographic
            # (a coat of arms, an emblem) commonly hands back exactly this
            # shape — mostly-transparent RGBA where the "colour" behind the
            # transparent pixels is unset (often literal 0,0,0). The result
            # is a solid black square, found for real in a browser (Tendo's
            # accepted candidate, before _looks_like_a_photograph existed to
            # refuse it — see that function's comment). That filter should
            # make this path rare in practice, but any raster PHOTOGRAPH
            # that happens to carry an alpha border deserves the same fix,
            # so transparency is always composited onto white, never
            # silently dropped.
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        elif im.mode != "RGB" and im.mode != "L":
            im = im.convert("RGB")
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    except Exception as exc:                              # noqa: BLE001
        log.warning("photos: could not process the image for %s (%s)",
                    dest.name, exc.__class__.__name__)
        return False
    return True


# --------------------------------------------------------------------------- #
def for_city(city: str, country_code: str, log: logging.Logger) -> dict | None:
    """A credited photograph of `city`, or None.

    Looks up Commons at most once per (city, country_code): a cache hit,
    positive or negative, returns immediately without calling `search`. A
    cache entry naming a file that is no longer on disk is treated as a miss
    and re-fetched — the manifest must never point at a picture that is not
    actually there to serve.
    """
    city = (city or "").strip()
    if not city:
        return None
    country_code = (country_code or "").strip().upper()
    key = _key(city, country_code)

    cache = _cache_load()
    if key in cache:
        cached = cache[key]
        if cached is None:
            return None
        if (IMAGES_SRC / Path(cached["file"]).name).exists():
            return cached
        # else: the manifest remembers a file no longer on disk — fall
        # through and fetch again rather than emit a dangling <img src>.

    try:
        candidates = search(city, city, limit=CANDIDATES_PER_CITY)
    except Exception as exc:                              # noqa: BLE001
        log.warning("photos: Commons search failed for %r (%s)",
                    city, exc.__class__.__name__)
        candidates = []

    result = None
    for cand in candidates:
        title = cand.get("title", "")
        if not _looks_like_a_photograph(title):
            log.info("photos: %s is not a photograph (map/emblem/flag) — "
                     "skipped for %r", title, city)
            continue
        ok, why = licence_ok(cand.get("licence", ""), title)
        if not ok:
            log.info("photos: %s refused for %r (%s)", title, city, why)
            continue
        author = short_author(cand.get("author", ""))
        page, licence = cand.get("page", ""), cand.get("licence", "")
        if not (author and page and licence and cand.get("thumb")):
            # A candidate cannot ship without all three parts of its credit
            # — see the module docstring — so an incomplete one is skipped,
            # not published bare.
            continue
        dest = IMAGES_SRC / f"{_slug(city)}.jpg"
        if not _save_thumb(cand["thumb"], dest, log):
            continue
        result = {
            "file": f"images/{dest.name}",
            "page": page,
            "author": author,
            "licence": licence,
            "licence_url": cand.get("licence_url") or "",
        }
        break

    if result is None:
        log.info("photos: no usable, fully-credited candidate for %r — no photo", city)

    cache[key] = result
    _cache_save()
    return result
