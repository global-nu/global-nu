"""Conferences from Indico, through its documented HTTP export API.

Indico is where the field's meetings actually live, and its export endpoint
returns exact ISO start AND end dates with a timezone — the best dates of any
source here, better than INSPIRE's and better than the prose spans parsed out
of Neutrino Unbound.

    GET https://indico.cern.ch/export/categ/6741.json?from=…&to=…&pretty=no

Three things learned the hard way, all worth keeping:

  * The window must be given as ISO dates. Indico's relative forms are not
    universally supported: `to=today+30d` answers HTTP 400 with
    "Impossible to parse" on CERN, IN2P3, DESY and indico.global.
  * Root categories are noisy. They carry seminars and standing series, and
    one entry ran from 2024 to 2030 — a monthly seminar, not a conference. So:
    only `conference` and `meeting`, only spans under `max_span_days`, and only
    if a keyword matches.
  * `location` and `address` are free text and mostly empty (39% filled on the
    CERN category). Neither is turned into a country_code here: an event with
    no country is listed but simply does not appear on the map, which is the
    honest outcome. Guessing "CERN" means Switzerland would be right often and
    wrong sometimes, and there is no way to tell which from the record.
    `address` — often more precise than `location` ("Manchester" vs. "Old
    Trafford", or a full street address) — is still kept, as extra.address,
    for `venue.py`'s geocoding cascade to try before it ever fetches the
    event's own page.

ON robots.txt. Indico's own robots.txt, served by CERN, disallows /export/.
That directive is aimed at search-engine crawlers rather than at clients of a
documented API — but it is a real directive, so this fetcher behaves like a
guest: one request per host per run, a User-Agent naming the site and a contact
address, and no retry storm. If that reading is ever judged wrong, set
`enabled: false` in the config and the section falls back to its other sources.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re

from . import cache
from .common import USER_AGENT, clean_text, http_get

KEEP_TYPES = {"conference", "meeting"}


def _date(node: dict | None) -> _dt.date | None:
    if not isinstance(node, dict):
        return None
    try:
        return _dt.date.fromisoformat(str(node.get("date", ""))[:10])
    except ValueError:
        return None


def _matches(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(re.search(r"\b" + re.escape(k.lower()) + r"\b", low) for k in keywords)


def fetch(cfg: dict, log: logging.Logger) -> list[dict]:
    conf = cfg.get("conferences_indico") or {}
    errors: list[str] = []
    if not conf.get("enabled", True):
        log.info("indico: disabled in config")
        cache.store("indico-conf", [], ["disabled"])
        return []

    today = _dt.date.today()
    ahead = today + _dt.timedelta(days=int(conf.get("upcoming_months", 18)) * 30)
    behind = today - _dt.timedelta(days=int(conf.get("recent_months", 5)) * 30)
    keywords = conf.get("keywords") or ["neutrino"]
    max_span = int(conf.get("max_span_days", 60))

    records: list[dict] = []
    seen: set[str] = set()

    for src in (conf.get("sources") or []):
        if not src.get("enabled", True):
            continue
        host, cat = src.get("host", ""), str(src.get("category", "0"))
        if not host:
            continue
        url = f"https://{host}/export/categ/{cat}.json"
        r = http_get(url, params={"from": today.isoformat(), "to": ahead.isoformat(),
                                  "pretty": "no"},
                     headers={"User-Agent": USER_AGENT},
                     timeout=int(conf.get("timeout", 60)), log=log)
        if r is None:
            errors.append(f"{host}: unreachable")
            continue
        try:
            results = r.json().get("results", [])
        except ValueError:
            errors.append(f"{host}: unparseable JSON")
            continue

        kept = 0
        for ev in results:
            if str(ev.get("type", "")).lower() not in KEEP_TYPES:
                continue
            start, end = _date(ev.get("startDate")), _date(ev.get("endDate"))
            if start is None:
                continue
            if end is None or end < start:
                end = start
            if (end - start).days > max_span:
                continue                      # a standing series, not a meeting
            if not (behind <= start <= ahead):
                continue

            title = clean_text(ev.get("title", ""))
            if not title:
                continue
            hay = f"{title} {clean_text(ev.get('description', ''))[:400]}"
            if not _matches(hay, keywords):
                continue

            link = str(ev.get("url", "")).strip()
            if not link.startswith("http"):
                continue
            if link in seen:
                continue
            seen.add(link)

            upcoming = end >= today
            place = clean_text(ev.get("location", "")) or ""
            address = clean_text(ev.get("address", "")) or ""
            records.append(cache.make_record(
                id=f"indico:{host.split('.')[1] if host.count('.') > 1 else host}"
                   f":{ev.get('id', '')}",
                source="inspire-conf",
                title=title,
                url=link,
                links={},
                date=start.isoformat(),
                summary="",
                extra={
                    "acronym": "",
                    "place": place,
                    "address": address,
                    # Left blank on purpose: see the module docstring.
                    "country_code": "",
                    "city": "",
                    "scope": src.get("scope", "neutrino"),
                    "provider": "indico",
                    "opening": start.isoformat(),
                    "closing": end.isoformat(),
                    "span": _span_text(start, end),
                    "upcoming": upcoming,
                    "in_progress": upcoming and start <= today,
                    "flagship": False,
                    "cnum": "",
                },
            ))
            kept += 1
        log.info("indico %s cat %s: %d events, %d kept", host, cat, len(results), kept)

    log.info("indico: %d records in window", len(records))
    if not records and not errors:
        errors.append("no event matched the keywords in the window")
    cache.store("indico-conf", records, errors)
    return records


def _span_text(start: _dt.date, end: _dt.date) -> str:
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
    log = get_logger("news.indico")
    for r in fetch(cfg, log)[:25]:
        e = r["extra"]
        print(f'  {e["span"][:30]:32} {e["scope"]:9} {r["title"][:52]}')
