"""Laboratory and experiment news, from plain RSS 2.0 and Atom feeds.

Why hand-rolled parsing instead of feedparser: the venv is deliberately four
packages wide (yaml, requests, markdown, pillow) and every addition is one
more thing that can break a Sunday-morning unattended run. RSS and Atom are
small enough that xml.etree covers them — the only real work is that the two
formats disagree on element names, on where the link lives, and on how a date
is written. Everything below is that disagreement, handled once.

Two rules from CLAUDE.md shape the control flow:

  * A feed that fails is skipped, logged and recorded in `errors`; it never
    degrades into a guess. common.http_get returns None on failure precisely
    so that there is nothing here to improvise from.
  * A date that cannot be parsed is not a date. An undated entry is dropped,
    because a feed that dates its other entries has simply omitted this one —
    keeping it would silently promote unknown-age news into today's page. The
    single exception is a feed that dates *nothing*: there the omission is a
    property of the publisher, not of the entry, and the fetch timestamp is
    the honest best estimate.

Run standalone to probe the configured URLs and see what survives filtering:

    python3 -m tools.news.fetch_feeds
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from . import cache
from .common import clean_text, get_logger, http_get, load_config, today, truncate

SUMMARY_CHARS = 600

# Namespaces are stripped rather than declared: feeds in the wild bind the
# same vocabulary to a dozen prefixes, and RSS 2.0 uses none at all.
_NS_RE = re.compile(r"^\{[^}]*\}")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _local(tag: object) -> str:
    """'{http://www.w3.org/2005/Atom}entry' -> 'entry'."""
    return _NS_RE.sub("", tag) if isinstance(tag, str) else ""


def _slug(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "feed"


# --------------------------------------------------------------------------- #
# element access
# --------------------------------------------------------------------------- #
def _child_text(el: ET.Element, *names: str) -> str:
    """Text of the first child matching one of `names`, in that priority.

    itertext() rather than .text: Atom allows type="xhtml" content, whose text
    sits in nested elements and would otherwise come back empty.
    """
    for name in names:
        for child in el:
            if _local(child.tag) == name:
                text = "".join(child.itertext())
                if text.strip():
                    return text
    return ""


def _is_url(candidate: str) -> bool:
    """Absolute http(s) URL with a plausible host.

    Not pedantry: news.fnal.gov ships items whose <link> is
    'http://South%20Dakota%20Public%20Broadcasting' — a source name typed into
    the URL box. The cache is the authority for every link the page prints, so
    a string that cannot be a URL must never reach it.
    """
    m = re.match(r"https?://([^/\s?#]+)", candidate)
    return bool(m) and "." in m[1] and " " not in m[1] and "%20" not in m[1]


def _entry_link(el: ET.Element) -> str:
    """The entry's primary URL, or "" if the entry offers no usable one.

    RSS puts it in <link>text</link>; Atom in <link href=… rel=…/>, where
    rel="self" / "replies" / "enclosure" are emphatically not the article.
    The guid is the last resort — WordPress feeds with a broken or empty
    <link> still carry a resolvable '?p=' permalink there, whatever
    isPermaLink claims.
    """
    candidates: list[str] = []
    alternates: list[str] = []
    for child in el:
        if _local(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        if href:
            rel = (child.get("rel") or "alternate").strip()
            (candidates if rel == "alternate" else alternates).append(href)
        elif (child.text or "").strip():
            candidates.append(child.text.strip())
    for child in el:
        if _local(child.tag) == "guid" and (child.text or "").strip():
            alternates.append(child.text.strip())
    for candidate in candidates + alternates:
        if _is_url(candidate):
            return candidate
    return ""


def _entry_author(el: ET.Element) -> str:
    """dc:creator, or Atom <author><name>. RSS <author> is an email address by
    spec, so it is ignored rather than printed on a public page."""
    for child in el:
        if _local(child.tag) == "creator" and (child.text or "").strip():
            return child.text.strip()
    for child in el:
        if _local(child.tag) == "author":
            for sub in child:
                if _local(sub.tag) == "name" and (sub.text or "").strip():
                    return sub.text.strip()
    return ""


# --------------------------------------------------------------------------- #
# dates
# --------------------------------------------------------------------------- #
def parse_date(raw: str | None) -> _dt.date | None:
    """RFC 822 (RSS) or ISO 8601 (Atom) -> date. None when neither applies.

    Both forms turn up in feeds that claim to be one or the other, and SLAC
    writes two-digit years ('Wed, 05 Aug 26 …'), which email.utils resolves
    per RFC 2822. Returning None is a real answer here — see the module
    docstring for what the caller does with it.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt is not None:
            return dt.date()
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return _dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    return None


# --------------------------------------------------------------------------- #
# keyword filter
# --------------------------------------------------------------------------- #
def _keyword_patterns(keywords: list[str]) -> list[re.Pattern]:
    """Word-ish matching: 'nova' must not fire on 'supernova', while 'hyper-k'
    still matches 'Hyper-K' and 'Hyper K', and 'double beta' matches
    'double-beta'. Feeds are inconsistent about that separator, the keyword
    list should not have to be."""
    pats = []
    for kw in keywords:
        parts = [re.escape(p) for p in re.split(r"[\s\-]+", str(kw)) if p]
        if not parts:
            continue
        body = r"[\s\-]+".join(parts)
        pats.append(re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE))
    return pats


def _matches(text: str, pats: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in pats)


# --------------------------------------------------------------------------- #
# feed parsing
# --------------------------------------------------------------------------- #
def parse_feed(payload: bytes) -> list[ET.Element]:
    """Every <item> (RSS 2.0, RSS 1.0/RDF) and <entry> (Atom) in the document.

    Raises ET.ParseError on malformed XML; callers turn that into a skip.
    Parsing bytes, not text: the XML declaration carries the encoding and
    requests' charset guess is wrong often enough to matter.
    """
    root = ET.fromstring(payload.lstrip())
    return [el for el in root.iter() if _local(el.tag) in ("item", "entry")]


def _entry_record(el: ET.Element, *, name: str, weight: int) -> dict | None:
    """One feed entry -> (record, date) material, or None if unusable."""
    url = _entry_link(el)
    title = clean_text(_child_text(el, "title"))
    if not url or not title:
        return None
    summary = truncate(
        clean_text(_child_text(el, "description", "summary", "encoded",
                               "content", "subtitle")),
        SUMMARY_CHARS)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    rec = cache.make_record(
        id=f"feed:{_slug(name)}:{digest}",
        source="feed",
        title=title,
        url=url,
        authors=_entry_author(el) or name,
        date="",
        summary=summary,
        extra={"feed": name, "weight": weight},
    )
    rec["_date"] = parse_date(_child_text(el, "pubDate", "published",
                                          "updated", "date", "modified"))
    return rec


def _fetch_source(src: dict, *, pats: list[re.Pattern], window_days: int,
                  per_feed_max: int, timeout: int, log: logging.Logger,
                  errors: list[str]) -> list[dict]:
    """Fetch and filter one source. Never raises: a bad feed costs its own
    records and nothing else."""
    name = str(src.get("name") or src.get("url") or "?")
    url = str(src.get("url") or "")
    weight = int(src.get("weight") or 1)
    if not url:
        errors.append(f"{name}: no url configured")
        log.warning("feed %s: no url configured", name)
        return []

    resp = http_get(url, timeout=timeout, log=log)
    if resp is None:
        errors.append(f"{name}: unreachable ({url})")
        log.warning("feed %s: skipped, unreachable", name)
        return []
    try:
        entries = parse_feed(resp.content)
    except ET.ParseError as exc:
        errors.append(f"{name}: malformed XML ({url}) — {exc}")
        log.warning("feed %s: skipped, malformed XML (%s)", name, exc)
        return []
    if not entries:
        errors.append(f"{name}: no <item>/<entry> elements ({url})")
        log.warning("feed %s: skipped, response is not an RSS/Atom feed", name)
        return []

    parsed = [r for r in (_entry_record(e, name=name, weight=weight)
                          for e in entries) if r]
    # An undated entry is only trusted when the whole feed is undated; see the
    # module docstring. This has to be decided per feed, hence the second pass.
    feed_has_dates = any(r["_date"] for r in parsed)
    stamp = today()
    cutoff = stamp - _dt.timedelta(days=max(window_days, 0))

    kept: list[dict] = []
    seen: set[str] = set()
    n_undated = n_offtopic = n_old = n_dup = 0
    for rec in parsed:
        date = rec.pop("_date")
        if date is None:
            if feed_has_dates:
                n_undated += 1
                continue
            date = stamp
        if date < cutoff:
            n_old += 1
            continue
        if not _matches(f"{rec['title']} {rec['summary']}", pats):
            n_offtopic += 1
            continue
        if rec["url"] in seen:
            n_dup += 1
            continue
        seen.add(rec["url"])
        rec["date"] = date.isoformat()
        kept.append(rec)

    kept.sort(key=lambda r: r["date"], reverse=True)
    trimmed = kept[:max(per_feed_max, 0)]
    log.info("feed %s: %d entries -> %d kept (dropped %d off-topic, "
             "%d older than %dd, %d undated, %d duplicate%s)",
             name, len(entries), len(trimmed), n_offtopic, n_old, window_days,
             n_undated, n_dup,
             f", {len(kept) - len(trimmed)} over per-feed cap"
             if len(kept) > len(trimmed) else "")
    return trimmed


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def fetch(cfg: dict, log: logging.Logger) -> list[dict]:
    """Fetch every enabled feed, filter, cap, and write today's cache.

    Returns the records it stored. When the section is disabled the cache is
    left untouched — overwriting a good cache with an empty one would delete
    the fallback the renderer relies on.
    """
    fcfg = dict(cfg.get("feeds") or {})
    if not fcfg.get("enabled", True):
        log.info("feeds: disabled in config, nothing fetched")
        return []

    sources = [s for s in (fcfg.get("sources") or []) if isinstance(s, dict)]
    pats = _keyword_patterns(list(fcfg.get("keywords") or []))
    window_days = int(fcfg.get("window_days", 45))
    per_feed_max = int(fcfg.get("per_feed_max", 6))
    max_items = int(fcfg.get("max_items", 10))
    timeout = int(fcfg.get("timeout", 20))

    records: list[dict] = []
    errors: list[str] = []
    for src in sources:
        if not src.get("enabled", False):
            continue
        records.extend(_fetch_source(
            src, pats=pats, window_days=window_days, per_feed_max=per_feed_max,
            timeout=timeout, log=log, errors=errors))

    # Recency first, weight only to break ties — which is what config.yaml has
    # always said. Sorting by weight first meant a six-week-old item from a
    # weight-3 feed outranked this morning's from a weight-1 one, and the
    # weight-1 sources could never appear at all. `per_feed_max` already stops
    # one chatty feed from filling the page, so recency is safe to lead with.
    records.sort(key=lambda r: (r["date"], int(r["extra"].get("weight", 1))),
                 reverse=True)

    # Sources overlap on purpose — "DUNE / LBNF" is a tag view of the same
    # WordPress site as "Fermilab News" — so the same story arrives twice with
    # two ids. Deduplicate on the URL after sorting: the copy that survives is
    # the one from the heavier feed, which is also the one worth crediting.
    unique: list[dict] = []
    seen: set[str] = set()
    for rec in records:
        if rec["url"] in seen:
            continue
        seen.add(rec["url"])
        unique.append(rec)
    if len(unique) < len(records):
        log.info("feeds: %d cross-feed duplicate(s) dropped",
                 len(records) - len(unique))
    records = unique

    if len(records) > max_items:
        log.info("feeds: %d records -> %d after the overall cap",
                 len(records), max_items)
        records = records[:max_items]

    cache.store("feeds", records, errors)
    log.info("feeds: %d records from %d source(s), %d error(s)",
             len(records), len({r["extra"].get("feed") for r in records}),
             len(errors))
    return records


def verify_sources(cfg: dict, log: logging.Logger) -> list[dict]:
    """Probe every configured URL, enabled or not, and report what answered.

    Used by the dashboard's source table and by __main__. Disabled sources are
    probed too: that is the point — it is how a source that was turned off
    because it broke gets noticed once it works again.
    """
    fcfg = dict(cfg.get("feeds") or {})
    timeout = int(fcfg.get("timeout", 20))
    rows: list[dict] = []
    for src in (fcfg.get("sources") or []):
        if not isinstance(src, dict):
            continue
        name = str(src.get("name") or "?")
        url = str(src.get("url") or "")
        row = {"name": name, "url": url,
               "enabled": bool(src.get("enabled", False)),
               "status": "no url", "items": 0}
        if url:
            resp = http_get(url, timeout=timeout, log=log)
            if resp is None:
                row["status"] = "unreachable"
            else:
                try:
                    entries = parse_feed(resp.content)
                except ET.ParseError:
                    row["status"] = "malformed XML"
                else:
                    row["items"] = len(entries)
                    row["status"] = "ok" if entries else "not a feed"
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    _cfg = load_config()
    _log = get_logger("news", verbose=False)   # the table below is the output

    _rows = verify_sources(_cfg, _log)
    _w = max([len(r["name"]) for r in _rows] + [6])
    print(f"{'source'.ljust(_w)}  on   status         items  url")
    print("-" * (_w + 60))
    for _r in _rows:
        print(f"{_r['name'].ljust(_w)}  {'y' if _r['enabled'] else 'n'}    "
              f"{_r['status']:<13}  {_r['items']:>5}  {_r['url']}")

    _records = fetch(_cfg, _log)
    _counts: dict[str, int] = {}
    for _rec in _records:
        _feed = str(_rec["extra"].get("feed", "?"))
        _counts[_feed] = _counts.get(_feed, 0) + 1
    print(f"\nrecords kept: {len(_records)}")
    for _feed, _n in sorted(_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {_feed.ljust(_w)}  {_n}")
    if not _counts:
        print("  (none passed the keyword and window filters)")
