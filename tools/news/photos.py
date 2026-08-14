"""A photograph of the host city — or nothing, never one without its credit.

    photos.for_city("Shanghai", "CN", log) -> {"file", "page", "author",
                                               "licence", "licence_url"} | None

Consumes exactly three names from tools.fetch_commons_images for a first
lookup, per the brief: `search` (Commons image search, one candidate list per
query), `licence_ok` (the one rule for what may be republished — CC0, public
domain, CC BY or CC BY-SA, nothing else — re-applied here explicitly rather
than trusted off a candidate dict's own `accepted` flag, since a candidate is
easy to build by hand in a caller or a test and this module should not have
to trust that whoever built it also ran the check), and `short_author` (the
same collapse that turns a seven-hundred-name collaboration credit into one
usable line — see tools/tests/test_credits.py). A fourth and fifth name,
`api` and `clean`, are used only to REVALIDATE a credit already in the cache
(see `_revalidate` below) — `api` is the same MediaWiki call `search` makes
internally, addressed at one exact title instead of a full-text query, and
`clean` is the exact HTML-tag-stripping `search` itself uses to normalise
Commons' `Artist`/`LicenseShortName`/`LicenseUrl` fields (it STRIPS a tag;
`common.clean_text`, used for feed prose elsewhere in this package,
SUBSTITUTES each tag with a space instead — close enough to look right until
a field genuinely straddles a tag, like Elekhh's Commons `Artist` field
"Elekhh (<a ...>talk</a>)", which `clean_text` turns into "Elekhh ( talk )";
using anything but `search`'s own `clean` here would silently degrade a
credit that was correct at first lookup). No new licence rule is written
anywhere here: `_revalidate` still judges acceptability with the identical
`licence_ok`, it just asks Commons again rather than trusting a first answer
forever.

City, not venue: the query is always the conference's *city* — "Shanghai",
never "Sede Afundación" — because Commons has a good photograph of the
former and essentially never of the latter. It is also always the city
*and its country*: "Cambridge" alone is dominated by Cambridge, UK on
Commons, so a bare city name would make Cambridge, US either miss entirely
or resolve to the wrong city's photograph. Cities repeat between
conferences (two workshops in Trieste in the same year, say — or, across
countries, two different Cambridges), so a result is cached by
(city, country_code) at every granularity that matters: the in-memory/disk
cache key (_key), the on-disk filename (_slug), AND the Commons query
itself (_country_name) — all three, not just the cache, because a
same-named different city sharing just one of those would still either
collide on disk or be handed the wrong search results. The same city is
looked up on Commons at most once per process (PHOTO_CACHE below is loaded
lazily and updated in memory), AND, once written to disk, never looked up
again on a later run either — the same idea as venue.py's VENUE_CACHE, and
for the same two reasons: politeness to somebody else's API, and a daily
job that should not re-download an unchanging photograph every morning. A
negative result (no usable candidate) is cached too, exactly like venue.py's
cache of a page that answered but carried nothing — a cache that only
remembered successes would re-query every unphotographed city every
morning.

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

import datetime as _dt
import io
import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

from tools.fetch_commons_images import (
    UA, api as commons_api, clean as commons_clean, licence_ok, search, short_author,
)

from . import worldmap as wm
from .common import write_json

ROOT = Path(__file__).resolve().parents[2]
IMAGES_SRC = ROOT / "site-src" / "images-src"
SITE_IMAGES = ROOT / "site" / "images"
PHOTO_CACHE = ROOT / "var" / "news" / "photocache.json"

# 640, not site.yaml's 1600: see the module docstring.
MAX_SIDE = 640
JPEG_QUALITY = 78
CANDIDATES_PER_CITY = 5

# A cached credit is frozen author/licence/links, read from Commons once and
# never checked again by default — see `_revalidate` below. Re-checking every
# entry every run would mean one extra Commons request per city on top of the
# search-cache's own steady-state promise of zero; instead an entry is only
# due once it is this old, and even then only REVALIDATE_PER_RUN of the due
# entries are actually re-checked in one run — the same shape as
# geocode.MAX_NEW_PER_RUN, and for the same reason: bound the damage (here,
# the request count) of however many entries happen to come due on one
# morning, at the cost of the rest waiting one more run.
REVALIDATE_AFTER_DAYS = 180
REVALIDATE_PER_RUN = 5
_revalidated_this_run = 0

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


# worldmap.COUNTRY_BY_NAME maps many aliases (ISO2, ISO3, full and partial
# names) onto one code each — inverted here once, at import time, keeping
# the SHORTEST alias over 3 characters per code: "united kingdom" (14) over
# "united kingdom of great britain and northern ireland" (54), while the
# 2/3-letter code entries themselves (len <= 3) are excluded so GB does not
# just map back to "gb". Used only to make the Commons *query* readable
# ("Cambridge, United Kingdom" vs "Cambridge, United States") — the cache
# key and the on-disk filename are both built from the raw code, which is
# what actually has to be unambiguous; see _slug and _key below.
_COUNTRY_NAME_BY_CODE: dict[str, str] = {}
for _name, _code in wm.COUNTRY_BY_NAME.items():
    if len(_name) <= 3:
        continue
    if _code not in _COUNTRY_NAME_BY_CODE or len(_name) < len(_COUNTRY_NAME_BY_CODE[_code]):
        _COUNTRY_NAME_BY_CODE[_code] = _name
del _name, _code


def _country_name(code: str) -> str:
    name = _COUNTRY_NAME_BY_CODE.get((code or "").strip().upper())
    return name.title() if name else code


_cache: dict[str, dict | None] | None = None


def _key(city: str, country_code: str) -> str:
    return f"{city.strip().lower()}|{(country_code or '').strip().upper()}"


def _slug(city: str, country_code: str) -> str:
    """The on-disk filename stem — same (city, country_code) granularity as
    _key, not city alone. Two same-named cities in different countries
    (Cambridge GB / Cambridge US, Santiago CL / Santiago de Compostela ES)
    must never share a path: a real bug found by review, not by a test —
    city-only slugging let a later-processed Cambridge silently overwrite an
    earlier one's file on disk, so the first city's cached author/licence
    ended up captioning the second city's photograph. See
    tools/tests/test_photos.py for the RED-proven regression check.

    The 60-char limit is applied to the CITY portion alone, before the
    country code is appended — not to the joined "city country_code" string
    afterwards. Truncating after joining can cut the code off the end of a
    long city name (anything past ~53 characters), silently re-creating the
    same disambiguator-loss collision the fix above exists to prevent; no
    real city name reaches that length today, but nothing here should depend
    on that staying true.
    """
    code = re.sub(r"[^a-z0-9]+", "-", (country_code or "").lower()).strip("-")
    suffix = f"-{code}" if code else ""
    prefix = "conf-"
    budget = max(60 - len(prefix) - len(suffix), 1)
    city_text = re.sub(r"[^a-z0-9]+", "-", (city or "").lower()).strip("-")[:budget].strip("-")
    return f"{prefix}{city_text or 'city'}{suffix}"


def _cache_load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(PHOTO_CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _cache_save() -> None:
    # write_json writes a .tmp file and renames it into place, so a run
    # interrupted mid-write leaves the last good cache intact rather than a
    # truncated file that _cache_load's except clause would read back as {}.
    write_json(PHOTO_CACHE, _cache)


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
# revalidation — a cached credit is not permission forever
# --------------------------------------------------------------------------- #
# Relicensing is deliberately NOT what this guards against: a CC BY/BY-SA/CC0
# grant is irrevocable, so permission obtained the day this was first cached
# survives even if the uploader changes their mind later. Two things a first
# lookup cannot see coming are what this exists for: a TAKEDOWN of a file that
# was never the uploader's to license in the first place (Commons deletes it;
# this project, never checking again, would keep serving it under a retracted
# claim, with a Commons link that now 404s), and a CORRECTED Artist field —
# the site printing a credit that no longer matches what the source says,
# which is the founding rule's own territory ("a photograph without its
# credit is a licence violation, not a cosmetic slip" applies just as much to
# a WRONG credit as to a missing one).
def _commons_title_of(page_url: str) -> str:
    """The exact Commons page title ("File:Whatever.jpg") a stored `page` URL
    points at, so revalidation can ask about that one file specifically
    rather than repeating the original full-text search (whose top result can
    drift for reasons that have nothing to do with the file's own status)."""
    tail = (page_url or "").rstrip("/").rsplit("/", 1)[-1]
    return urllib.parse.unquote(tail).replace("_", " ")


def _revalidate(entry: dict, city: str, log: logging.Logger) -> dict | None:
    """Re-check one cached credit against Commons, by exact title.

    Returns the entry with a fresh `cached_at` (and updated author/licence/
    licence_url if Commons now reports different ones — a corrected Artist
    field must reach the page, not stay frozen at whatever it said the day
    this was first cached), or None if the photograph must STOP being
    served — but only on an AFFIRMATIVE signal that it should: Commons
    itself reports the title `"missing"`, or a genuinely-returned licence no
    longer passes `licence_ok` — the same rule `search`'s own results are
    judged by, not a new one. `for_city` writes that None straight to the
    on-disk cache, and a cached None short-circuits before ever calling
    `search()` again — so a city that lands here by mistake can never regain
    a photograph without a hand edit to photocache.json. Consequently
    anything short of an affirmative answer is treated as TRANSIENT, exactly
    like a request that fails outright (network down, Commons unreachable,
    caught below): a response that doesn't parse into the expected shape at
    all (an error envelope, an empty `pages` dict, an "invalid title"
    response — none of these carry `"missing"`, and none of them say
    anything about whether the file is actually still there), or a page that
    IS present but comes back with no `extmetadata` whatsoever, or one whose
    `Artist` field is empty despite the rest of the metadata being there
    (Commons vandalism blanking a field is not the same event as a curator
    deleting the file). In every one of those cases the entry is returned
    UNCHANGED, still with its old `cached_at`, so it comes up for
    revalidation again next run rather than being dropped over a response
    that says nothing conclusive about the file's actual status.
    """
    title = _commons_title_of(entry.get("page", ""))
    if not title:
        return entry
    try:
        data = commons_api({"action": "query", "titles": title,
                            "prop": "imageinfo", "iiprop": "extmetadata"})
        pages = ((data.get("query") or {}).get("pages") or {})
        page = next(iter(pages.values()), None)
    except Exception as exc:                              # noqa: BLE001
        log.warning("photos: revalidation fetch failed for %r (%s) — keeping "
                    "the cached credit for now, will retry", title, exc.__class__.__name__)
        return entry

    if page is None:
        # No page at all in the response — an error envelope, an "invalid"
        # title, or a `pages` dict that came back empty. None of these is
        # Commons saying the file is gone; see the docstring above.
        log.warning("photos: revalidation got an unrecognised response for "
                    "%r — keeping the cached credit for now, will retry",
                    title)
        return entry
    if "missing" in page:
        log.warning("photos: %s is gone from Commons — no longer served for %r",
                    title, city)
        return None

    meta = (page.get("imageinfo") or [{}])[0].get("extmetadata") or {}
    if not meta:
        log.warning("photos: revalidation for %s came back with no metadata "
                    "at all — keeping the cached credit for now, will retry",
                    title)
        return entry
    # commons_clean (fetch_commons_images.clean), not common.clean_text:
    # clean_text SUBSTITUTES each HTML tag with a space, which mangles a
    # credit that straddles a tag ("Elekhh (<a ...>talk</a>)" -> "Elekhh
    # ( talk )") instead of stripping it the way `search`'s own first
    # lookup does — see the module docstring.
    licence = commons_clean((meta.get("LicenseShortName") or {}).get("value", ""))
    ok, why = licence_ok(licence, title)
    if not ok:
        log.warning("photos: %s no longer qualifies for reuse (%s) — no "
                    "longer served for %r", title, why, city)
        return None
    author = short_author(commons_clean((meta.get("Artist") or {}).get("value", "")))
    if not author:
        log.warning("photos: %s's Artist field came back empty on Commons — "
                    "keeping the cached credit for now, will retry", title)
        return entry

    updated = dict(entry)
    updated["author"] = author
    updated["licence"] = licence
    updated["licence_url"] = commons_clean((meta.get("LicenseUrl") or {}).get("value", ""))
    updated["cached_at"] = _dt.date.today().isoformat()
    if updated["author"] != entry.get("author") or updated["licence"] != entry.get("licence"):
        log.info("photos: %s's credit changed on Commons — updated for %r",
                 title, city)
    return updated


def _delete_local_copies(cached: dict, city: str, log: logging.Logger) -> None:
    """Remove a taken-down photograph's bytes from both trees a build can
    serve them from, not just from the cache's *pointer* to them.

    Without this, `for_city` stops linking the file (the cache entry is
    None) but the JPEG itself stays sitting in site-src/images-src AND in
    site/images — and pipeline.PHOTO_GLOBS matches both by glob and keeps
    committing/deploying whatever it finds there, so a taken-down file's
    bytes would stay served at their old URL indefinitely, just unlinked
    from any card. Deleting here, at the one place a takedown is actually
    decided, needs no general pruning machinery: the file this call removes
    is *exactly* the one the takedown was just decided for.
    """
    name = Path(cached.get("file", "")).name
    if not name:
        return
    for base in (IMAGES_SRC, SITE_IMAGES):
        path = base / name
        try:
            if path.exists():
                path.unlink()
                log.info("photos: removed the taken-down file %s for %r", path, city)
        except OSError as exc:
            log.warning("photos: could not remove %s (%s)", path, exc.__class__.__name__)


def _due_for_revalidation(entry: dict) -> bool:
    stamp = entry.get("cached_at")
    if not stamp:
        return True                  # written before this field existed
    try:
        age = (_dt.date.today() - _dt.date.fromisoformat(stamp)).days
    except ValueError:
        return True
    return age >= REVALIDATE_AFTER_DAYS


# --------------------------------------------------------------------------- #
def for_city(city: str, country_code: str, log: logging.Logger) -> dict | None:
    """A credited photograph of `city`, or None.

    Looks up Commons at most once per (city, country_code): a cache hit,
    positive or negative, returns immediately without calling `search` —
    unless the cached credit is old enough to be due for revalidation (see
    `_revalidate` above) and this run still has budget left for it, in which
    case Commons is asked again about that one exact file before the cached
    answer is trusted further. A cache entry naming a file that is no longer
    on disk is treated as a miss and re-fetched — the manifest must never
    point at a picture that is not actually there to serve.
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
            global _revalidated_this_run
            if (_due_for_revalidation(cached)
                    and _revalidated_this_run < REVALIDATE_PER_RUN):
                _revalidated_this_run += 1
                fresh = _revalidate(cached, city, log)
                if fresh is None:
                    _delete_local_copies(cached, city, log)
                cache[key] = fresh
                _cache_save()
                return fresh
            return cached
        # else: the manifest remembers a file no longer on disk — fall
        # through and fetch again rather than emit a dangling <img src>.

    # Disambiguated by country, not just city: "Cambridge" alone is
    # dominated by Cambridge, UK on Commons, and two cities of the same name
    # must not even be LIKELY to resolve to the same candidate — see _slug's
    # docstring for what happens on disk when they collide.
    query = f"{city}, {_country_name(country_code)}" if country_code else city
    try:
        candidates = search(city, query, limit=CANDIDATES_PER_CITY)
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
        dest = IMAGES_SRC / f"{_slug(city, country_code)}.jpg"
        if not _save_thumb(cand["thumb"], dest, log):
            continue
        result = {
            "file": f"images/{dest.name}",
            "page": page,
            "author": author,
            "licence": licence,
            "licence_url": cand.get("licence_url") or "",
            "cached_at": _dt.date.today().isoformat(),
        }
        break

    if result is None:
        log.info("photos: no usable, fully-credited candidate for %r — no photo", city)

    cache[key] = result
    _cache_save()
    return result
