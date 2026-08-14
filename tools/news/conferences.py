"""Merging conference records that arrive from more than one source.

INSPIRE and Neutrino Unbound overlap heavily and agree on almost nothing
textually. The same meeting is "Invisibles Workshop 2026" in one and
"invisibles 26" in the other; NOW 2026 is in "Otranto, Lecce, Italy" and in
"Otranto (Lecce), Italy". A title-similarity match would miss both.

Two keys, checked in this order:

  A. the canonical event URL, reduced to host + path with an Indico-style
     /event/<id> collapsed. This is what catches the pairs whose titles share
     no words at all.
  B. (start date, end date, first distinctive word of the place). This is what
     catches the pairs that came from different registration systems and so
     have different URLs.

Not `(start, end)` alone: in a real pool of ~110 upcoming meetings there were
fifteen date collisions and only two of them were the same event — it would
have merged NuFact in Shanghai with a conference in Mexico City.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import unicodedata
from urllib.parse import urlsplit

# Words that are not the distinctive part of a place name.
STOPWORDS = {"university", "universite", "universita", "universität", "institute",
             "institut", "centre", "center", "hotel", "auditorium", "auditorio",
             "the", "of", "de", "del", "della", "and", "campus", "college",
             "laboratory", "laboratoire", "national", "international"}

_EVENT_PATH = re.compile(r"^(.*/e(?:vent)?)/(\d+)")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def url_key(url: str) -> str:
    """host + path, Indico event ids collapsed. "" when not usable as a key."""
    if not url:
        return ""
    p = urlsplit(_norm(url))
    host = p.netloc.removeprefix("www.")
    path = p.path.rstrip("/")
    m = _EVENT_PATH.match(path)
    if m:
        path = m.group(0)
    # INSPIRE's fallback URL is per-record, so it is unique by construction and
    # would merge nothing while looking like a key.
    if "inspirehep.net" in host and "/conferences" in path:
        return ""
    return (host + path) if host else ""


def place_key(record: dict) -> str:
    extra = record.get("extra", {})
    place = extra.get("city") or extra.get("place") or ""
    for token in re.split(r"[^A-Za-zÀ-ɏ]+", _norm(place)):
        if len(token) > 3 and token not in STOPWORDS:
            return token
    return ""


def date_place_key(record: dict) -> str:
    extra = record.get("extra", {})
    start, end = extra.get("opening", ""), extra.get("closing", "")
    town = place_key(record)
    return f"{start}|{end}|{town}" if (start and town) else ""


def _better(a: dict, b: dict) -> dict:
    """Which record leads the merged entry.

    A real conference site beats INSPIRE's fallback page — that is the link the
    reader wants. Otherwise Neutrino Unbound leads, because it is the source
    that reliably carries an acronym and a "City, Country" place.
    """
    a_own = "inspirehep.net" not in a.get("url", "")
    b_own = "inspirehep.net" not in b.get("url", "")
    if a_own != b_own:
        return a if a_own else b
    a_nu = a.get("extra", {}).get("provider") == "nu-unbound"
    b_nu = b.get("extra", {}).get("provider") == "nu-unbound"
    if a_nu != b_nu:
        return a if a_nu else b
    return a


def _absorb(lead: dict, other: dict) -> dict:
    """Fill the gaps in `lead` from `other`. Never overwrites what is there."""
    le, oe = lead.setdefault("extra", {}), other.get("extra", {})
    for field in ("acronym", "place", "city", "country_code", "cnum", "span"):
        if not le.get(field) and oe.get(field):
            le[field] = oe[field]
    if not le.get("closing") and oe.get("closing"):
        le["closing"] = oe["closing"]
    for k, v in (other.get("links") or {}).items():
        lead.setdefault("links", {}).setdefault(k, v)
    # Where the entry came from, for the credit line under the section. A
    # record with no `provider` came from INSPIRE, which does not set one.
    seen = set(le.get("providers") or [])
    seen.add(le.get("provider") or "inspire")
    seen.update(oe.get("providers") or [])
    seen.add(oe.get("provider") or "inspire")
    le["providers"] = sorted(seen)
    return lead


def merge(groups: list[list[dict]], log: logging.Logger) -> list[dict]:
    """Merge several sources' conference records into one list."""
    out: list[dict] = []
    by_key: dict[str, int] = {}
    merged = 0

    for records in groups:
        for rec in records:
            keys = [k for k in (url_key(rec.get("url", "")), date_place_key(rec)) if k]
            hit = None
            for k in keys:
                if k in by_key:
                    hit = by_key[k]
                    break
            if hit is None:
                out.append(rec)
                for k in keys:
                    by_key.setdefault(k, len(out) - 1)
                continue

            existing = out[hit]
            lead = _better(existing, rec)
            other = rec if lead is existing else existing
            out[hit] = _absorb(lead, other)
            merged += 1
            for k in keys:
                by_key.setdefault(k, hit)

    if merged:
        log.info("conferences: %d duplicate record(s) merged across sources", merged)
    return out


def _refresh_tense(records: list[dict]) -> None:
    """Recompute extra.upcoming/extra.in_progress from extra.opening/closing
    against date.today(), in place, for every record.

    Every fetcher computes these two fields once, on the day it runs — and
    that is fine, until the record is handed back on some LATER day without
    a fetcher having touched it again. Two real paths do exactly that:
    fetch_nu_unbound's conditional GET replays cached records verbatim on
    every 304 (see that module's docstring), carrying tense flags computed
    on whatever day the page last actually changed; and
    pipeline.run(from_cache=True) re-renders records fetched — and flagged —
    on an earlier day, on purpose, to let a wording fix be reviewed without
    touching the network. Nothing downstream ever recomputed them:
    render.conferences splits on extra.upcoming, figures.py's timeline
    colours bars from extra.upcoming/in_progress, the map is drawn from the
    same split, and _absorb above only fills gaps — it never overwrites
    `upcoming` even when a fresher source (e.g. INSPIRE) disagrees. Left
    unfixed, a conference that closed weeks ago keeps rendering as upcoming,
    coloured amber ("running right now"), sitting left of the TODAY line —
    reproduced end to end against real nu-unbound data before this function
    existed. This is the one place every source's records pass through
    before the page is built (`sort_for_page`, below), so it is the one
    place the two fields are re-derived from the dates themselves rather
    than trusted off whatever a fetcher wrote on some earlier morning — the
    same class of bug as commit c2f4162 (a fetcher-set tense field read
    uncritically at render time), re-entering through the conditional-fetch
    door instead of the one already closed.

    A record with no parseable extra.closing is left exactly as it was:
    every fetcher sets it, so that shape should not occur on a real record,
    and inventing a tense for it would be worse than leaving whatever was
    already there.
    """
    today = _dt.date.today()
    for r in records:
        extra = r.get("extra")
        if not extra:
            continue
        closing = extra.get("closing")
        if not closing:
            continue
        try:
            end = _dt.date.fromisoformat(closing)
        except ValueError:
            continue
        upcoming = end >= today
        in_progress = upcoming
        opening = extra.get("opening")
        if opening:
            try:
                in_progress = upcoming and _dt.date.fromisoformat(opening) <= today
            except ValueError:
                pass
        extra["upcoming"] = upcoming
        extra["in_progress"] = in_progress


def sort_for_page(records: list[dict]) -> list[dict]:
    """Upcoming first, soonest at the top; then the recently concluded, most
    recent first. Same order the single-source fetcher produced — merging two
    already-sorted lists by concatenation does not preserve it.

    Also the point where every record's tense (extra.upcoming/in_progress) is
    re-derived from its own dates against today — see `_refresh_tense` — since
    every record reaches the page through here, from a live fetch or from
    pipeline.run(from_cache=True) alike.
    """
    _refresh_tense(records)
    upcoming = sorted([r for r in records if r["extra"].get("upcoming")],
                      key=lambda r: (r["extra"].get("opening", ""),
                                     not r["extra"].get("flagship")))
    recent = sorted([r for r in records if not r["extra"].get("upcoming")],
                    key=lambda r: r["extra"].get("opening", ""), reverse=True)
    return upcoming + recent


def split_scope(records: list[dict], scope: str) -> list[dict]:
    """Records belonging to one scope. INSPIRE records carry the scope already;
    anything without one is treated as neutrino, which is the page's default."""
    return [r for r in records
            if (r.get("extra", {}).get("scope") or "neutrino") == scope]
