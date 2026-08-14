"""Conferences from Neutrino Unbound (nu.to.infn.it), INFN Torino.

Why this source. INSPIRE knows about three upcoming neutrino conferences at
the time of writing; this list knows about thirty, including NuFact, the Erice
school, LIDINE and the joint IceCube–KM3NeT–JUNO workshop. It is the curated
list for exactly this field, maintained at INFN Torino by Gariazzo, Giunti and
Laveder, and it is kept current — the copy fetched while this was written had
been modified that same morning.

It is HTML, not an API, which normally means guessing. Here it does not: the
start date is in the `id` attribute as YYYYMMDD, so the one date that must be
right is read, never parsed from prose:

    <div class='el_cont' id='20260831__NuFact_2026'>
    <dd><b class='red_150'><a href='…'>NuFact 2026</a></b>,
        <b class='navy'>27th International Workshop on Neutrinos…</b>,
        <b class='red'>31 August - 5 September 2026</b>,
        <b class='green'>Shanghai, China</b></dd></div>

Only the end date has to come from the span text. Three forms cover every
entry in the list; anything else makes the record be DROPPED rather than
guessed at, because a conference with an invented end date is worse than a
conference nobody listed.

Politeness. The page is 800 kB and this runs daily, so the fetch is
conditional: the ETag and Last-Modified of the last copy are kept in var/ and
sent back, and the usual answer is 304 with no body. There is no robots.txt on
the host (404, so nothing is disallowed) and no stated licence, so the page
credits the list by name — it is a colleague's resource, not a public API.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re

from . import cache
from .common import USER_AGENT, VAR, clean_text, read_json, write_json

URL = "https://www.nu.to.infn.it/conf/"
STATE = VAR / "nu_unbound.json"

# Section headings, in the order they appear. Each entry belongs to the last
# heading before it, which is what tells us the scope and whether it is past.
SECTIONS = [
    ("Past Neutrino, Astroparticle, and Weak Interaction Conferences",
     "neutrino", True),
    ("Neutrino, Astroparticle, and Weak Interaction Conferences",
     "neutrino", False),
    ("Past Other Interesting Conferences", "general", True),
    ("Other Interesting Conferences", "general", False),
    ("Past Italian Conferences", "general", True),
]

ENTRY_RE = re.compile(
    r"<div class='el_cont' id='(?P<start>\d{8})__(?P<slug>[^']*)'>(?P<body>.*?)</div>",
    re.S)
LINK_RE = re.compile(r"<b class='red_150'>\s*<a href='([^']+)'>(.*?)</a>", re.S)
NAME_ONLY_RE = re.compile(r"<b class='red_150'>(.*?)</b>", re.S)
TITLE_RE = re.compile(r"<b class='navy'>(.*?)</b>", re.S)
SPAN_RE = re.compile(r"<b class='red'>(.*?)</b>", re.S)
PLACE_RE = re.compile(r"<b class='green'>(.*?)</b>", re.S)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}

# "23 August - 1 September 2026" | "10-14 August 2026" | "5 October 2026"
SPAN_FULL = re.compile(
    r"(\d{1,2})\s+([A-Za-z]+)\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
SPAN_SAME_MONTH = re.compile(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
SPAN_ONE_DAY = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


def _end_date(span: str, start: _dt.date) -> _dt.date | None:
    """End date from the span text, or None if it cannot be read.

    None means the record is dropped. There is deliberately no `end = start`
    fallback: that would silently turn a week-long school into a one-day
    meeting, and the reader would have no way of knowing.
    """
    text = clean_text(span)

    m = SPAN_FULL.search(text)
    if m:
        d2, mon2, year = int(m.group(3)), MONTHS.get(m.group(4).lower()), int(m.group(5))
        if mon2:
            try:
                return _dt.date(year, mon2, d2)
            except ValueError:
                return None

    m = SPAN_SAME_MONTH.search(text)
    if m:
        d2, mon, year = int(m.group(2)), MONTHS.get(m.group(3).lower()), int(m.group(4))
        if mon:
            try:
                return _dt.date(year, mon, d2)
            except ValueError:
                return None

    m = SPAN_ONE_DAY.search(text)
    if m:
        d, mon, year = int(m.group(1)), MONTHS.get(m.group(2).lower()), int(m.group(3))
        if mon:
            try:
                return _dt.date(year, mon, d)
            except ValueError:
                return None
    return None


def _country(place: str) -> str:
    """ISO2 for the last comma-separated token of a free-text place.

    Unmapped places are left blank on purpose: an event with no country simply
    does not appear on the map, rather than appearing in the wrong place.
    """
    from . import worldmap as wm
    tail = (place or "").split(",")[-1].strip().lower()
    return wm.COUNTRY_BY_NAME.get(tail, "")


INTERMEDIATE = VAR / "nu_intermediate.pem"
CA_BUNDLE = VAR / "nu_ca_bundle.pem"
# From the server certificate's Authority Information Access field. INFN
# Torino's host sends only its leaf certificate and omits this intermediate,
# so OpenSSL cannot close the chain and `requests` fails with
# "unable to get local issuer certificate" — while curl succeeds, because
# macOS fetches the missing link itself. This does the same thing explicitly.
AIA_URL = "http://crt.harica.gr/HARICA-GEANT-TLS-R1.cer"


def _ca_bundle(log: logging.Logger) -> str | None:
    """Path to certifi's roots plus the missing intermediate, or None.

    Note what is NOT happening here: verification is never switched off. The
    downloaded intermediate is only useful if it chains to a root already
    trusted in certifi — a tampered one would simply fail to verify, exactly
    as it should. The alternative, verify=False, would accept anything at all.
    """
    import certifi
    try:
        if not INTERMEDIATE.exists():
            import requests
            r = requests.get(AIA_URL, timeout=30, headers={"User-Agent": USER_AGENT})
            if r.status_code != 200 or not r.content:
                log.warning("nu-unbound: could not fetch the CA intermediate "
                            "(HTTP %s)", r.status_code)
                return None
            blob = r.content
            if b"-----BEGIN CERTIFICATE-----" not in blob:
                # Served as DER; convert without shelling out to openssl.
                import base64
                b64 = base64.encodebytes(blob).decode("ascii")
                blob = ("-----BEGIN CERTIFICATE-----\n" + b64 +
                        "-----END CERTIFICATE-----\n").encode("ascii")
            INTERMEDIATE.parent.mkdir(parents=True, exist_ok=True)
            INTERMEDIATE.write_bytes(blob)
            log.info("nu-unbound: fetched and cached the missing CA intermediate")

        roots = certifi.where()
        if (not CA_BUNDLE.exists()
                or CA_BUNDLE.stat().st_mtime < INTERMEDIATE.stat().st_mtime
                or CA_BUNDLE.stat().st_mtime < _mtime(roots)):
            CA_BUNDLE.write_text(
                open(roots, encoding="utf-8").read() + "\n"
                + INTERMEDIATE.read_text(encoding="utf-8"), encoding="utf-8")
        return str(CA_BUNDLE)
    except Exception as exc:                     # never fatal: fall back to certifi
        log.warning("nu-unbound: CA bundle setup failed (%s)", exc.__class__.__name__)
        return None


def _mtime(path: str) -> float:
    import os
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _section_of(pos: int, marks: list[tuple[int, str, bool]]) -> tuple[str, bool]:
    scope, past = "neutrino", False
    for at, s, p in marks:
        if at <= pos:
            scope, past = s, p
        else:
            break
    return scope, past


def fetch(cfg: dict, log: logging.Logger) -> list[dict]:
    conf = (cfg.get("conferences_nu_unbound") or {})
    errors: list[str] = []
    if not conf.get("enabled", True):
        log.info("nu-unbound: disabled in config")
        cache.store("nu-unbound", [], ["disabled"])
        return []

    import requests
    prev = read_json(STATE, {}) or {}
    headers = {"User-Agent": USER_AGENT}
    if prev.get("etag"):
        headers["If-None-Match"] = prev["etag"]
    if prev.get("last_modified"):
        headers["If-Modified-Since"] = prev["last_modified"]

    verify = _ca_bundle(log) or True
    try:
        r = requests.get(URL, headers=headers, verify=verify,
                         timeout=int(conf.get("timeout", 60)))
    except requests.RequestException as exc:
        errors.append(f"unreachable: {exc.__class__.__name__}")
        log.warning("nu-unbound: unreachable (%s)", exc.__class__.__name__)
        cache.store("nu-unbound", [], errors)
        return []

    if r.status_code == 304:
        # Unchanged since the last run: reuse what we parsed then, without
        # re-downloading 800 kB to reach the same answer.
        cached = cache.latest_day_with("nu-unbound")
        if cached:
            records = cache.load_records("nu-unbound", cached)
            log.info("nu-unbound: unchanged (304), reusing %d records from %s",
                     len(records), cached)
            cache.store("nu-unbound", records, [])
            return records
        log.info("nu-unbound: 304 but nothing cached — refetching in full")
        headers.pop("If-None-Match", None)
        headers.pop("If-Modified-Since", None)
        r = requests.get(URL, headers=headers, verify=verify,
                         timeout=int(conf.get("timeout", 60)))

    if r.status_code != 200:
        errors.append(f"HTTP {r.status_code}")
        log.warning("nu-unbound: HTTP %s", r.status_code)
        cache.store("nu-unbound", [], errors)
        return []

    html = r.text
    write_json(STATE, {"etag": r.headers.get("ETag", ""),
                       "last_modified": r.headers.get("Last-Modified", "")})

    marks = []
    for label, scope, past in SECTIONS:
        at = html.find(label)
        if at >= 0:
            marks.append((at, scope, past))
    marks.sort()

    today = _dt.date.today()
    ahead = today + _dt.timedelta(days=int(conf.get("upcoming_months", 18)) * 30)
    behind = today - _dt.timedelta(days=int(conf.get("recent_months", 5)) * 30)

    records: list[dict] = []
    seen_ids: set[str] = set()
    dropped_dates = out_of_window = 0

    for m in ENTRY_RE.finditer(html):
        try:
            start = _dt.datetime.strptime(m.group("start"), "%Y%m%d").date()
        except ValueError:
            dropped_dates += 1
            continue
        if not (behind <= start <= ahead):
            out_of_window += 1
            continue

        body = m.group("body")
        span = SPAN_RE.search(body)
        end = _end_date(span.group(1), start) if span else None
        if end is None or end < start:
            dropped_dates += 1
            continue

        link = LINK_RE.search(body)
        if link:
            url, acronym = link.group(1).strip(), clean_text(link.group(2))
        else:
            plain = NAME_ONLY_RE.search(body)
            url, acronym = "", clean_text(plain.group(1)) if plain else ""
        if not url:
            # No link, nothing to point the reader at. INSPIRE has a fallback
            # page for its own records; this list does not.
            continue

        title_m = TITLE_RE.search(body)
        title = clean_text(title_m.group(1)) if title_m else ""
        if not title:
            title = acronym
        if not title:
            continue

        place = clean_text(PLACE_RE.search(body).group(1)) if PLACE_RE.search(body) else ""
        scope, _past = _section_of(m.start(), marks)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", m.group("slug")).strip("-").lower()
        rid = f"nu:{m.group('start')}-{slug}"[:80]
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        upcoming = end >= today
        records.append(cache.make_record(
            id=rid,
            source="inspire-conf",          # same shape as the INSPIRE records
            title=title,
            url=url,
            links={},
            date=start.isoformat(),
            summary="",
            extra={
                "acronym": acronym,
                "place": place,
                "country_code": _country(place),
                "city": (place.split(",")[0].strip() if place else ""),
                "scope": scope,
                "provider": "nu-unbound",
                "opening": start.isoformat(),
                "closing": end.isoformat(),
                "span": _span_text(start, end),
                "upcoming": upcoming,
                "in_progress": upcoming and start <= today,
                "flagship": True,
                "cnum": "",
            },
        ))

    log.info("nu-unbound: %d records in window (%d outside, %d dropped for an "
             "unreadable date)", len(records), out_of_window, dropped_dates)
    if not records:
        errors.append("no conference parsed — the page layout may have changed")
        log.warning("nu-unbound: parsed nothing; leaving the section to INSPIRE")

    cache.store("nu-unbound", records, errors)
    return records


def _span_text(start: _dt.date, end: _dt.date) -> str:
    """Same wording as fetch_inspire._span, so the two sources read alike."""
    if start == end:
        return start.strftime("%-d %B %Y")
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {start.strftime('%B %Y')}"
    if start.year == end.year:
        return (f"{start.day} {start.strftime('%B')} – "
                f"{end.day} {end.strftime('%B %Y')}")
    return f"{start.strftime('%-d %B %Y')} – {end.strftime('%-d %B %Y')}"


if __name__ == "__main__":  # pragma: no cover
    from .common import get_logger, load_config
    cfg = load_config()
    log = get_logger("news.nu")
    recs = fetch(cfg, log)
    up = [r for r in recs if r["extra"]["upcoming"]]
    print(f"\n{len(recs)} records, {len(up)} upcoming")
    for r in up[:20]:
        e = r["extra"]
        print(f'  {e["scope"]:9} {e["span"][:30]:32} {e["country_code"] or "--":3} '
              f'{(e["acronym"] or r["title"])[:44]}')
