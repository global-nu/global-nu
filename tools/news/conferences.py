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


def _editions_apart(a: dict, b: dict) -> bool:
    """True when two records sharing a key are different editions.

    A series often keeps one domain for every edition: the 5th and 6th
    Astro-COLIBRI workshops (October 2026 and 2027) both link to
    multimessenger-astrophysics.com, and merging on that URL made the 5th
    disappear into the 6th.
    """
    try:
        da = _dt.date.fromisoformat(str(a.get("extra", {}).get("opening") or a.get("date", ""))[:10])
        db = _dt.date.fromisoformat(str(b.get("extra", {}).get("opening") or b.get("date", ""))[:10])
    except ValueError:
        return False
    return abs((da - db).days) > 180


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
            if hit is not None and _editions_apart(out[hit], rec):
                hit = None
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
        except (ValueError, TypeError):
            continue
        upcoming = end >= today
        in_progress = upcoming
        opening = extra.get("opening")
        if opening:
            try:
                in_progress = upcoming and _dt.date.fromisoformat(opening) <= today
            except (ValueError, TypeError):
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


# --------------------------------------------------------------------------- #
# Facets for the page's filters (kind, continent) and grouping of satellites.
# --------------------------------------------------------------------------- #
# The kind is read from the title, because no source states it; the filter
# says so on the page. Order matters: "Summer School and Workshop" is a school.
_KINDS = (
    ("school", re.compile(r"\b(school|lectures?|summer institute|winter institute|training)\b", re.I)),
    ("workshop", re.compile(r"\b(workshop|meeting|forum|days|week)\b", re.I)),
    ("conference", re.compile(r"\b(conference|symposium|congress|convention|colloquium)\b", re.I)),
)


def kind_of(record: dict) -> str:
    """"school", "workshop", "conference", or "other" — from the title."""
    title = record.get("title") or ""
    for kind, rx in _KINDS:
        if rx.search(title):
            return kind
    return "other"


# ISO 3166-1 alpha-2 -> continent, for the countries conference sources use.
_CONTINENT = {}
for _cont, _codes in {
    "Europe": "AD AL AM AT BA BE BG BY CH CY CZ DE DK EE ES FI FR GB GE GR HR HU IE IS IT "
              "LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SK SM UA VA XK FX",
    "Asia": "AE AF AZ BD BH BN BT CN HK ID IL IN IQ IR JO JP KG KH KR KW KZ LA LB LK MM MN "
            "MO MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE",
    "North America": "AG BB BS BZ CA CR CU DM DO GD GT HN HT JM KN LC MX NI PA PR SV TT US VC",
    "South America": "AR BO BR CL CO EC GY PE PY SR UY VE",
    "Africa": "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG ER ET GA GH GM GN GQ GW KE KM LR LS "
              "LY MA MG ML MR MU MW MZ NA NE NG RW SC SD SL SN SO SS ST SZ TD TG TN TZ UG ZA ZM ZW",
    "Oceania": "AU FJ KI MH FM NR NZ PG PW SB TO TV VU WS",
}.items():
    for _c in _codes.split():
        _CONTINENT[_c] = _cont


def continent_of(record: dict) -> str:
    cc = ((record.get("extra") or {}).get("country_code") or "").upper()
    return _CONTINENT.get(cc, "")


def status_of(record: dict) -> str:
    x = record.get("extra") or {}
    if x.get("in_progress"):
        return "ongoing"
    return "upcoming" if x.get("upcoming") else "recent"


def _span(record: dict) -> tuple[_dt.date, _dt.date] | None:
    x = record.get("extra") or {}
    try:
        a = _dt.date.fromisoformat(x.get("opening") or record.get("date") or "")
        b = _dt.date.fromisoformat(x.get("closing") or x.get("opening") or record.get("date") or "")
    except ValueError:
        return None
    return a, b


_SATELLITE = re.compile(r"\b(satellite|pre-?conference|post-?conference)\b", re.I)


def group_related(records: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Fold schools, workshops and satellite events into the conference they
    belong to, so one meeting with three side events reads as one entry.

    Deliberately conservative — a wrong grouping hides a meeting under
    another's name, which is worse than a duplicate-looking list. A record is
    folded under a conference only if it is not itself a conference, its dates
    lie within 7 days of the conference's, both are in the same country, and
    either they share a city or the side event names the conference (by its
    acronym, by a number-and-name like "Neutrino 2026", or by calling itself
    a satellite). Returns the top-level records, in their original order, and
    the side events of each conference by id.
    """
    mains = [r for r in records if kind_of(r) == "conference"]
    children: dict[str, list[dict]] = {}
    folded: set[str] = set()
    for r in records:
        if kind_of(r) == "conference":
            continue
        sr = _span(r)
        if sr is None:
            continue
        xr = r.get("extra") or {}
        for m in mains:
            sm = _span(m)
            xm = m.get("extra") or {}
            if sm is None or not xr.get("country_code") or xr.get("country_code") != xm.get("country_code"):
                continue
            near = (sr[0] <= sm[1] + _dt.timedelta(days=7)) and (sr[1] >= sm[0] - _dt.timedelta(days=7))
            if not near:
                continue
            same_city = bool(xr.get("city")) and _norm(xr.get("city", "")) == _norm(xm.get("city", ""))
            title = r.get("title") or ""
            names = [xm.get("acronym") or ""]
            mt = re.search(r"\b([A-Z][A-Za-z]+)\s+(20\d\d)\b", title)
            named = any(n and len(n) >= 3 and re.search(r"\b" + re.escape(n) + r"\b", title, re.I) for n in names)
            if mt and re.search(r"\b" + re.escape(mt.group(1)) + r"\b.*\b" + mt.group(2) + r"\b",
                                (m.get("title") or "") + " " + " ".join(names), re.I):
                named = True
            close = (sr[0] <= sm[1] + _dt.timedelta(days=3)) and (sr[1] >= sm[0] - _dt.timedelta(days=3))
            if named or (same_city and close and (_SATELLITE.search(title)
                                                  or kind_of(r) in ("school", "workshop"))):
                children.setdefault(m["id"], []).append(r)
                folded.add(r["id"])
                break
    return [r for r in records if r["id"] not in folded], children


def to_ics(records: list[dict], stamp: _dt.datetime | None = None) -> str:
    """An iCalendar file of the meetings, all-day events from opening to
    closing (DTEND is exclusive, hence the day after closing)."""
    now = (stamp or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")

    def esc(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def fold(line: str) -> str:
        out, b = [], line.encode("utf-8")
        while len(b) > 74:
            cut = 74
            while (b[cut] & 0xC0) == 0x80:
                cut -= 1
            out.append(b[:cut].decode("utf-8"))
            b = b" " + b[cut:]
        out.append(b.decode("utf-8"))
        return "\r\n".join(out)

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//global-nu.org//conferences//EN",
             "CALSCALE:GREGORIAN", "X-WR-CALNAME:global-nu — neutrino conferences"]
    for r in records:
        sp = _span(r)
        if sp is None:
            continue
        x = r.get("extra") or {}
        lines += ["BEGIN:VEVENT",
                  f"UID:{esc(r['id'])}@global-nu.org",
                  f"DTSTAMP:{now}",
                  f"DTSTART;VALUE=DATE:{sp[0].strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(sp[1] + _dt.timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{esc(r.get('title', ''))}",
                  *( [f"LOCATION:{esc(x['place'])}"] if x.get("place") else [] ),
                  *( [f"URL:{r['url']}"] if r.get("url") else [] ),
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"
