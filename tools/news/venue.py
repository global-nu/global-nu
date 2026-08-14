"""Where a conference actually is — a cascade, not a guess.

A dot in roughly the right country is worse than no dot: someone reading the
map would trust it. So the order here always prefers data someone already
structured over anything scraped, and the last resort returns nothing rather
than something approximate.

    1. extra.place        Neutrino Unbound's own string, already clean
                           ("Shanghai, China").
    2. extra.address_structured   INSPIRE's structured address, when a record
                           carries one.
    3. extra.address       Indico's address field. A pre-launch audit judged
                           it too verbose to print under a conference title
                           ("Sede Afundación, Cantón Grande 8, A Coruña,
                           15003, Spain") — verbose for a title is precise for
                           a geocoder, which is why it is kept rather than
                           thrown away.
    4. the conference's own page, parsed for a structured address: schema.org
       Event/Place JSON-LD, walked for a node whose own @type is Event,
       Place or PostalAddress and which carries a nested address — nothing
       looser than that (see `_from_page`'s docstring for why a microdata
       fallback was tried and removed). This step is last on purpose: it is
       dozens of requests a day to other people's servers, and every
       conference site is built differently, so it is asked only once
       nothing better is available — and asked at most once ever per URL,
       because every outcome (including "found nothing") is cached in
       var/news/venuecache.json. A cache that only remembered successes
       would re-fetch every dead page every morning.
    5. nothing. The conference keeps its place in the list and gets no
       marker.

No factual value here ever comes from what this code "knows" about a city —
only from the record or the page it points at.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import geocode, worldmap
from .common import http_get

VENUE_CACHE = Path(__file__).resolve().parents[2] / "var" / "news" / "venuecache.json"

# A page fetch for step 4 is a courtesy to someone else's server, not an API
# call this project controls — keep it brisk and identify the site.
PAGE_TIMEOUT_S = 15

_cache: dict[str, str | None] | None = None


def _cache_load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(VENUE_CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _cache_save() -> None:
    VENUE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    VENUE_CACHE.write_text(
        json.dumps(_cache, indent=1, sort_keys=True, ensure_ascii=False),
        encoding="utf-8")


# --------------------------------------------------------------------------- #
# step 4: the conference's own page
# --------------------------------------------------------------------------- #
_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S)

_ADDRESS_FIELDS = (
    "streetAddress", "addressLocality", "addressRegion", "postalCode",
    "addressCountry",
)

# Indico's own JSON-LD literally emits this string when the organiser never
# set a venue — found on a real record while testing this cascade
# (indico.cern.ch/event/1677041/: `"address":"No address set"`). Treated as
# absence, not as a location, the same way an empty string would be.
_PLACEHOLDERS = {"no address set", "no location set", "n/a", "tbd", "tba"}


def _address_string(addr) -> str | None:
    """A schema.org `address` value (string, or PostalAddress object) as one
    printable string, or None if there is nothing usable in it."""
    if isinstance(addr, str):
        addr = addr.strip()
        if not addr or addr.lower() in _PLACEHOLDERS:
            return None
        return addr
    if isinstance(addr, dict):
        parts = [str(addr[f]).strip() for f in _ADDRESS_FIELDS
                 if str(addr.get(f) or "").strip()
                 and str(addr[f]).strip().lower() not in _PLACEHOLDERS]
        return ", ".join(parts) if parts else None
    return None


def _walk_jsonld(node) -> str | None:
    """Depth-first search for the first Event/Place carrying an address."""
    if isinstance(node, list):
        for item in node:
            found = _walk_jsonld(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None

    types = node.get("@type")
    types = {types} if isinstance(types, str) else set(types or [])
    if types & {"Event", "Place", "PostalAddress"} and node.get("address"):
        found = _address_string(node["address"])
        if found:
            return found

    for key in ("location", "@graph"):
        if key in node:
            found = _walk_jsonld(node[key])
            if found:
                return found
    # Fall back to any nested dict/list — some publishers bury the Place two
    # or three levels down in a wrapper object this code has no name for.
    for value in node.values():
        if isinstance(value, (dict, list)):
            found = _walk_jsonld(value)
            if found:
                return found
    return None


def _address_from_jsonld(html: str) -> str | None:
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except (ValueError, TypeError):
            continue
        found = _walk_jsonld(data)
        if found:
            return found
    return None


def _from_page(url: str, log) -> str | None:
    """The conference's own page, cached by URL — including its failures.

    JSON-LD only. An earlier version also tried a schema.org microdata
    fallback (`itemprop="streetAddress"` etc.), matched with an independent
    regex search per field across the whole page. That is unsafe: without
    itemscope/itemtype boundary tracking it will happily stitch the first
    streetAddress on the page to the first addressLocality to the first
    addressCountry, even when they come from three unrelated blocks — a
    footer Organization, a sponsor listing, a second event on an aggregator.
    A coordinate built from that blend is exactly the "dot in roughly the
    right country" this whole module exists to refuse, and this project has
    no HTML parser to scope it correctly. The JSON-LD walker above does not
    have this problem — it only reads an `address` off a node whose own
    `@type` is Event/Place/PostalAddress — so it is trusted alone; a page
    without JSON-LD simply yields nothing here rather than a guess assembled
    from unrelated parts of the page.

    Called at most once per URL, ever: a hit or a miss is written back before
    returning, so tomorrow's run finds the answer already in the cache and
    makes no request at all.
    """
    cache = _cache_load()
    if url in cache:
        return cache[url]

    address = None
    r = http_get(url, timeout=PAGE_TIMEOUT_S, log=log)
    if r is not None:
        try:
            text = r.text
        except Exception:                 # pragma: no cover — defensive only
            text = ""
        address = _address_from_jsonld(text)

    cache[url] = address
    _cache_save()
    if address:
        log.info("venue: found an address on %s", url)
    else:
        log.info("venue: no structured address on %s", url)
    return address


# --------------------------------------------------------------------------- #
# the cascade
# --------------------------------------------------------------------------- #
def address_of(record: dict, log) -> str | None:
    """The best location string this record offers, before any geocoding."""
    e = record.get("extra") or {}
    # 1. Neutrino Unbound's own place — already clean ("Shanghai, China").
    if e.get("place"):
        return e["place"]
    # 2. INSPIRE's structured address.
    if e.get("address_structured"):
        return e["address_structured"]
    # 3. Indico's address: too verbose to print under a title, exactly right
    #    for a geocoder.
    if e.get("address"):
        return e["address"]
    # 4. The conference's own page, cached by URL including its failures.
    if record.get("url"):
        return _from_page(record["url"], log)
    return None


# --------------------------------------------------------------------------- #
# turning an address into coordinates
# --------------------------------------------------------------------------- #
def _split_country(address: str) -> tuple[str, str]:
    """(remainder, ISO2 country code) parsed off the tail of an address
    string, or ("", "") if no token names a country this project recognises.

    Tokens are checked from the end backwards — the country is normally last
    ("Shanghai, China", "…, A Coruña, 15003, Spain") — and a token holding a
    digit is skipped, since that is a postal code, never a country. A
    trailing full stop is stripped before matching — real records end a
    sentence there ("Heidelberg, Germany.") without meaning it as part of
    the name.
    """
    tokens = [t.strip() for t in (address or "").split(",") if t.strip()]
    for i in range(len(tokens) - 1, -1, -1):
        tok = tokens[i]
        if any(c.isdigit() for c in tok):
            continue
        code = worldmap.COUNTRY_BY_NAME.get(tok.strip().rstrip(".").lower())
        if code:
            remainder = ", ".join(tokens[:i])
            return remainder, code
    return "", ""


def locate_record(record: dict, log) -> tuple[float, float] | None:
    """(lon, lat) for a record's best address, or None.

    None means: the address is absent, no country could be established for
    it, or the geocoder itself declined — never a guess, and never a country
    centroid (that fallback belongs to the caller, per the spec, not here).
    A network failure inside geocode.locate is swallowed there already; this
    still wraps the call, since a daily run must not go down over one venue.
    """
    address = address_of(record, log)
    if not address:
        return None

    extra = record.get("extra") or {}
    remainder, code = _split_country(address)
    if not code:
        # The address itself named no recognised country; a structured
        # country_code elsewhere on the record is still worth trying.
        code = (extra.get("country_code") or "").strip().upper()
        if len(code) != 2:
            return None
        remainder = extra.get("city") or address

    query = remainder or address
    try:
        return geocode.locate(query, code)
    except Exception as exc:              # pragma: no cover — defensive only
        log.warning("venue: geocoding failed for %r (%s)",
                    address, exc.__class__.__name__)
        return None
