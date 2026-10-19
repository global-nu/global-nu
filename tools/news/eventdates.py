"""A conference's dates, checked against the organisers' own page.

On 19 October 2026 the page listed DISCRETE 2026 as 13–17 October, a month
early, and as already over. Neutrino Unbound had it that way; the event page
it links to said 13–17 November. Nothing compared the two, because nothing
here ever read a date from the page a record points at. This does, for every
record about to be published.

The organisers' page is the authority, but only what it says in a form a
program can read without guessing: a schema.org Event in JSON-LD, which every
Indico event page carries (agenda.infn.it included, whose export API answers
HTML instead) and many other conference sites too. Its startDate/endDate are
written in the event's own timezone — unlike Indico's export API, which
answers in the server's: LHCP 2027 in Vancouver comes back from indico.cern.ch
as 31 May – 5 June, Zurich time, for a meeting that ends on 4 June.

A page whose interval lies more than OTHER_EDITION_DAYS away is probably about
another edition, not a wrong date: the link for the 6th Astro-COLIBRI workshop
(October 2027) redirects to the 5th edition's site. That is mailed as
SUSPECT and the record left alone.

Agreement is not equality. The list usually gives the scientific days and the
page the whole event: NNN26 is 28–30 October in the list and 26–30 on Indico,
Patras 2026 is 9–13 November in the list and 8–13 on the page, because of a
welcome reception on the 8th. Listed dates INSIDE the page's interval are
kept. Anything else (no overlap, or listed days the organisers do not
announce) is replaced by the page's dates, logged, and mailed once.

A page with no Event, or with several (a series page, an institute's
calendar), or with an interval longer than MAX_SPAN_DAYS, gives no dates: the
record keeps its listed dates. It is still read for a weaker signal: the
months it names with a year ("13-17 November 2026", "novembre 2026",
"13.11.2026"). If it names months of the event's year but never the month we
publish, the record is mailed as SUSPECT and left unchanged — prose is not
read well enough here to replace a date with it, only to doubt one. A page
that names no month of that year (a site still about last year's edition, or
one drawn by JavaScript) raises nothing. Neither does a page that cannot be
fetched.
Every answer, found or not, is cached in var/news/datecache.json for
RECHECK_DAYS, so most mornings cost a dozen requests, not a hundred.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from .common import VAR, http_get, read_json, write_json
from .fetch_nu_unbound import _span_text

DATE_CACHE = VAR / "datecache.json"
RECHECK_DAYS = 7
MAX_SPAN_DAYS = 60
OTHER_EDITION_DAYS = 180
# Prose is doubted only for meetings not long over. Pages of past meetings
# tend to name just their deadlines ("Abstract submission: 6 March 2026"), and
# a wrong date that matters makes a meeting look recently over, as DISCRETE's.
SUSPECT_PAST_DAYS = 30
PAGE_TIMEOUT_S = 15
WORKERS = 6

_MONTHS = {}
for _i, (_en, _it) in enumerate(zip(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"],
        ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
         "agosto", "settembre", "ottobre", "novembre", "dicembre"]), 1):
    for _n in (_en, _en[:3], _it):
        _MONTHS[_n] = _i
_MONTHS["sept"] = 9
# "November 2026", "Nov 13-17, 2026", "13 novembre 2026"; and "13.11.2026".
# "September 21 to 26, 2026" too: school.lomcon.ru writes it so.
_MONTH_YEAR_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?\b"
    r"(?:[^0-9a-z]{0,6}(?:(?:to|and|until|till)\b[^0-9a-z]{0,6})?"
    r"\d{1,2}(?:st|nd|rd|th)?){0,3}[^0-9a-z]{0,12}(20\d\d)\b",
    re.I)
_NUMERIC_RE = re.compile(r"\b\d{1,2}[./](\d{1,2})[./](20\d\d)\b")

# A bot check answers 200 with its own page, which has no dates and must not
# be cached as "this conference's page has none": agenda.infn.it runs Anubis
# and let the first dozen requests of 19 October 2026 through, then sent this.
_CHALLENGE_RE = re.compile(
    r"/\.within\.website/|not a bot|<title>Just a moment|cf-chl-|challenge-platform",
    re.I)

_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S)


def _events_in(node, out: list[dict]) -> list[dict]:
    if isinstance(node, list):
        for n in node:
            _events_in(n, out)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and t.endswith("Event") for t in types) \
                and node.get("startDate"):
            out.append(node)
        for k, v in node.items():
            if k != "subEvent" and isinstance(v, (dict, list)):
                _events_in(v, out)
    return out


def _local_date(stamp: str) -> tuple[_dt.date, bool] | None:
    """The calendar date as written, and whether it is exactly midnight."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:T(\d{2}):(\d{2}))?", str(stamp).strip())
    if not m:
        return None
    try:
        day = _dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return day, m.group(2) == "00" and m.group(3) == "00"


def dates_from_html(html: str) -> tuple[_dt.date, _dt.date] | None:
    """(start, end) of the one Event the page describes, or None."""
    events: list[dict] = []
    for blob in _JSONLD_RE.findall(html or ""):
        try:
            _events_in(json.loads(blob), events)
        except ValueError:
            continue
    spans = set()
    for ev in events:
        s = _local_date(ev.get("startDate", ""))
        e = _local_date(ev.get("endDate") or ev.get("startDate", ""))
        if not s or not e:
            continue
        start, (end, midnight) = s[0], e
        # An end at 00:00 closes the previous day: Dark Matter and Stars 2027
        # "ends" at 2027-07-15T00:00, after its last session on the 14th.
        if midnight and end > start:
            end -= _dt.timedelta(days=1)
        spans.add((start, end))
    if len(spans) != 1:
        return None
    start, end = spans.pop()
    if end < start or (end - start).days > MAX_SPAN_DAYS:
        return None
    return start, end


def months_named(html: str) -> list[str]:
    """Every 'YYYY-MM' the visible text of the page names, sorted."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html or "")
    text = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    found = {f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"
             for m in _MONTH_YEAR_RE.finditer(text)}
    found |= {f"{m.group(2)}-{int(m.group(1)):02d}"
              for m in _NUMERIC_RE.finditer(text) if 1 <= int(m.group(1)) <= 12}
    return sorted(found)


def _page_dates(url: str, cache: dict, today: _dt.date, offline: bool):
    """Cached or fetched answer for `url`: (start, end), a list of the months
    the page names when it has no Event, or 'unknown'."""
    hit = cache.get(url)
    if hit:
        try:
            fresh = (today - _dt.date.fromisoformat(hit["checked"])).days < RECHECK_DAYS
        except (KeyError, ValueError):
            fresh = False
        if fresh or offline:
            if hit.get("start"):
                return (_dt.date.fromisoformat(hit["start"]),
                        _dt.date.fromisoformat(hit["end"]))
            return hit.get("months") or []
    if offline:
        return "unknown"
    r = http_get(url, timeout=PAGE_TIMEOUT_S, retries=())
    if r is None or r.status_code != 200 or _CHALLENGE_RE.search(r.text[:20000]):
        return "unknown"            # not cached: try again tomorrow
    found = dates_from_html(r.text)
    months = [] if found else months_named(r.text)
    cache[url] = {"checked": today.isoformat(),
                  "start": found[0].isoformat() if found else None,
                  "end": found[1].isoformat() if found else None,
                  "months": months}
    return found or months


def check(records: list[dict], log: logging.Logger, *, offline: bool = False,
          today: _dt.date | None = None) -> list[dict]:
    """Correct, in place, records whose dates the organisers' page contradicts.

    Returns one finding per corrected record (kind "corrected") and per
    record whose page doubts its month (kind "suspect", left unchanged).
    `offline` uses only what is cached — for a re-render that must not touch
    the network.
    """
    today = today or _dt.date.today()
    cache = read_json(DATE_CACHE, {}) or {}
    urls = sorted({r.get("url", "") for r in records
                   if r.get("url", "").startswith("http")
                   and "inspirehep.net" not in r.get("url", "")})
    # Hosts in parallel, each host's pages one after the other: a burst at
    # one server is what tripped agenda.infn.it's bot check.
    by_host: dict[str, list[str]] = {}
    for u in urls:
        by_host.setdefault(urlsplit(u).netloc.lower(), []).append(u)
    answers: dict = {}

    def visit(host_urls: list[str]) -> None:
        for u in host_urls:
            answers[u] = _page_dates(u, cache, today, offline)

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(visit, by_host.values()))
    if not offline:
        write_json(DATE_CACHE, cache)

    findings = []
    read = 0
    for rec in records:
        page = answers.get(rec.get("url", ""))
        if page is None or page == "unknown":
            continue
        ex = rec.setdefault("extra", {})
        try:
            start = _dt.date.fromisoformat(ex.get("opening") or rec["date"][:10])
            end = _dt.date.fromisoformat(ex.get("closing") or ex.get("opening")
                                         or rec["date"][:10])
        except (KeyError, ValueError):
            continue
        base = {"id": rec["id"], "title": rec.get("title", ""), "url": rec["url"],
                "listed": [start.isoformat(), end.isoformat()],
                "provider": ex.get("provider") or "inspire"}
        if isinstance(page, list):
            if (today - end).days > SUSPECT_PAST_DAYS:
                continue
            same_year = [m for m in page if m.startswith(f"{start.year}-")]
            ours = {f"{start:%Y-%m}", f"{end:%Y-%m}"}
            if same_year and not ours & set(page):
                findings.append(dict(base, kind="suspect", page=same_year,
                                     why="months the page names"))
                log.warning("dates: %s listed %s – %s, but its page names only "
                            "%s of that year — check it (%s)",
                            rec.get("title", rec["id"])[:60], start, end,
                            ", ".join(same_year), rec["url"])
            continue
        read += 1
        ps, pe = page
        if ps <= start and end <= pe:
            continue
        if abs((ps - start).days) > OTHER_EDITION_DAYS:
            findings.append(dict(base, kind="suspect",
                                 page=[ps.isoformat(), pe.isoformat()],
                                 why="the page is about"))
            log.warning("dates: %s listed %s – %s, its page says %s – %s — "
                        "another edition? left as listed (%s)",
                        rec.get("title", rec["id"])[:60], start, end, ps, pe,
                        rec["url"])
            continue
        findings.append(dict(base, kind="corrected",
                             page=[ps.isoformat(), pe.isoformat()]))
        log.warning("dates: %s listed %s – %s, its page says %s – %s; using the "
                    "page (%s)", rec.get("title", rec["id"])[:60], start, end,
                    ps, pe, rec["url"])
        rec["date"] = ps.isoformat()
        ex["opening"], ex["closing"] = ps.isoformat(), pe.isoformat()
        ex["span"] = _span_text(ps, pe)
        # The tense too: not every caller's sort re-derives it (the home
        # page's does not), and DISCRETE's wrong month had made it "recent".
        ex["upcoming"] = pe >= today
        ex["in_progress"] = ps <= today <= pe
        ex["dates_from_page"] = {"listed": [start.isoformat(), end.isoformat()]}
    log.info("dates: %d of %d conferences checked against their own page, "
             "%d corrected, %d suspect", read, len(records),
             sum(f["kind"] == "corrected" for f in findings),
             sum(f["kind"] == "suspect" for f in findings))
    return findings


def compose_report(findings: list[dict]) -> tuple[str, str]:
    fixed = [f for f in findings if f["kind"] == "corrected"]
    doubt = [f for f in findings if f["kind"] == "suspect"]
    subject = (f"global-nu: conference dates — {len(fixed)} corrected, "
               f"{len(doubt)} to check")
    lines = []
    if fixed:
        lines += ["CORRECTED. These dates disagreed with the event's own page,",
                  "and the page's dates were published instead. If the page is",
                  "the one that is wrong, add an entry to date_corrections in",
                  "tools/news/config.yaml.", ""]
        for f in fixed:
            lines += [f["title"],
                      f"  listed ({f['provider']}): {f['listed'][0]} – {f['listed'][1]}",
                      f"  event page:  {f['page'][0]} – {f['page'][1]}",
                      f"  {f['url']}", ""]
    if doubt:
        lines += ["TO CHECK. Either the page gives no machine-readable dates",
                  "and its text never names the month published, or its dates",
                  "are so far off that it may be about another edition.",
                  "Nothing was changed; a wrong date goes in date_corrections",
                  "(nu-unbound), a wrong link at the source.", ""]
        for f in doubt:
            seen = (" – ".join(f["page"]) if f["why"] == "the page is about"
                    else ", ".join(f["page"]))
            lines += [f["title"],
                      f"  listed ({f['provider']}): {f['listed'][0]} – {f['listed'][1]}",
                      f"  {f['why']}: {seen}",
                      f"  {f['url']}", ""]
    return subject, "\n".join(lines)


def _key(f: dict) -> str:
    return "|".join([f["id"], f["kind"], *f["page"]])


def notify(findings: list[dict], cfg: dict, log: logging.Logger, *,
           send=None) -> list[dict]:
    """Mail the findings not mailed before. Returns those it reported.

    Remembered by (id, kind, what the page said) in the date cache, so a correction that
    holds day after day is mailed once, and a page that changes again is
    mailed again.
    """
    cache = read_json(DATE_CACHE, {}) or {}
    told = set(cache.get("_notified", []))
    new = [f for f in findings
           if _key(f) not in told]
    if not new:
        return []
    subject, body = compose_report(new)
    alerts = cfg.get("alerts") or {}
    account = alerts.get("account") or ""
    recipient = alerts.get("recipient") or account
    host, port = alerts.get("smtp_host") or "", int(alerts.get("smtp_port") or 587)
    try:
        if send is None:
            from . import mailer
            password = mailer.keychain_password(account) if account else None
            if not (account and host and password):
                log.error("dates: NOT sending mail (alerts or Keychain password "
                          "missing). The message would have been: %s", subject)
                return []
            mailer.send(mailer.build_message(subject, body, account, recipient),
                        host, port, account, password)
        else:
            send(subject, body)
    except Exception as exc:                    # noqa: BLE001 — never fatal
        log.error("dates: could not send mail (%s: %s)", type(exc).__name__, exc)
        return []
    log.info("dates: told %s about %d correction(s)", recipient, len(new))
    told.update(_key(f) for f in new)
    cache["_notified"] = sorted(told)
    write_json(DATE_CACHE, cache)
    return new
