"""arXiv fetcher for the compact digest section.

Deliberately not AI: the page's compact digest is a ranked list of what the
arXiv API returned in the last few days, scored by keyword. The curated,
reasoned digest is the separate Neutrino-Highlights page produced by the
/arxiv skill; this section exists so the news page is never stale when that
skill has not run, and it links across for the long version.

Scoring is intentionally crude — a title hit counts three, an abstract hit
one. It is a relevance sort, not a judgement, and pretending otherwise by
inventing a cleverer formula would only make the ordering harder to explain.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import xml.etree.ElementTree as ET

from . import cache
from .common import clean_text, http_get, load_config, truncate

API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

TITLE_WEIGHT = 3
ABSTRACT_WEIGHT = 1


def _authors(entry: ET.Element, limit: int = 3) -> str:
    names = [clean_text(a.findtext(f"{ATOM}name"))
             for a in entry.findall(f"{ATOM}author")]
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + " et al."


def _arxiv_id(entry: ET.Element) -> str:
    """'http://arxiv.org/abs/2608.01890v2' -> '2608.01890'.

    The version is dropped on purpose: a paper that gets a v2 tomorrow must
    keep the same id, or the run-on-run comparison would report it as new.
    """
    raw = entry.findtext(f"{ATOM}id") or ""
    m = re.search(r"abs/([^v\s]+?)(?:v\d+)?$", raw.strip())
    return m.group(1) if m else raw.strip()


def _published(entry: ET.Element) -> _dt.datetime | None:
    for tag in (f"{ATOM}published", f"{ATOM}updated"):
        raw = entry.findtext(tag)
        if not raw:
            continue
        try:
            return _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _compile(terms: list[str]) -> list[tuple[str, re.Pattern]]:
    """Word-boundary patterns, so 'nova' does not match 'innovation' and
    'reactor' does not match 'reactors' only by luck — \\b handles the plural
    separately because the config lists the forms it wants."""
    out = []
    for t in terms:
        if not t:
            continue
        out.append((t, re.compile(r"\b" + re.escape(t.lower()) + r"\b")))
    return out


def score(title: str, summary: str, high: list, low: list) -> tuple[int, list[str]]:
    """Total score and the terms that fired, for the record's `extra`."""
    t, s = title.lower(), summary.lower()
    total = 0
    hits: list[str] = []
    for terms, weight in ((high, 2), (low, 1)):
        for term, pat in terms:
            in_t = bool(pat.search(t))
            in_s = bool(pat.search(s))
            if not (in_t or in_s):
                continue
            total += weight * (TITLE_WEIGHT if in_t else 0)
            total += weight * (ABSTRACT_WEIGHT if in_s else 0)
            hits.append(term)
    return total, hits


# --------------------------------------------------------------------------- #
def fetch(cfg: dict, log: logging.Logger) -> list[dict]:
    conf = cfg.get("arxiv", {})
    errors: list[str] = []
    if not conf.get("enabled", True):
        log.info("arxiv: disabled in config")
        cache.store("arxiv", [], ["disabled"])
        return []

    cats = conf.get("categories") or ["hep-ph"]
    query = " OR ".join(f"cat:{c}" for c in cats)
    max_fetch = int(conf.get("max_fetch", 300))

    r = http_get(API, params={
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max_fetch,
    }, timeout=60, log=log)
    if r is None:
        errors.append("arXiv API unreachable")
        log.warning("arxiv: API unreachable — section will fall back to cache")
        cache.store("arxiv", [], errors)
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        errors.append(f"unparseable Atom response: {exc}")
        log.warning("arxiv: response did not parse (%s)", exc)
        cache.store("arxiv", [], errors)
        return []

    window = _dt.timedelta(hours=int(conf.get("window_hours", 72)))
    cutoff = _dt.datetime.now(_dt.timezone.utc) - window
    high = _compile(conf.get("keywords", {}).get("high", []))
    low = _compile(conf.get("keywords", {}).get("low", []))

    scored: list[tuple[int, _dt.datetime, dict]] = []
    seen = 0
    for entry in root.findall(f"{ATOM}entry"):
        seen += 1
        published = _published(entry)
        if published is None or published < cutoff:
            continue
        aid = _arxiv_id(entry)
        if not aid:
            continue
        title = clean_text(entry.findtext(f"{ATOM}title"))
        summary = clean_text(entry.findtext(f"{ATOM}summary"))
        pts, hits = score(title, summary, high, low)
        if pts <= 0:
            continue

        cats_e = [c.get("term") for c in entry.findall(f"{ATOM}category")
                  if c.get("term")]
        doi = entry.findtext(f"{ARXIV_NS}doi")
        rec = cache.make_record(
            id=f"arxiv:{aid}",
            source="arxiv",
            title=title,
            url=f"https://arxiv.org/abs/{aid}",
            links={
                "arxiv": f"https://arxiv.org/abs/{aid}",
                "pdf": f"https://arxiv.org/pdf/{aid}",
                "doi": f"https://doi.org/{doi}" if doi else "",
            },
            authors=_authors(entry),
            date=published.date().isoformat(),
            summary=truncate(summary, 1200),
            extra={"categories": cats_e[:4], "score": pts, "hits": hits[:8]},
        )
        scored.append((pts, published, rec))

    scored.sort(key=lambda x: (-x[0], -x[1].timestamp()))
    records = [rec for _, _, rec in scored]

    log.info("arxiv: %d entries scanned, %d in the %dh window and on topic",
             seen, len(records), int(conf.get("window_hours", 72)))
    if seen and not records:
        errors.append("no entry matched the keywords inside the window")

    cache.store("arxiv", records, errors)
    return records


def top(records: list[dict], n: int) -> list[dict]:
    """The n highest-scoring records — what the page actually shows."""
    return records[:max(0, n)]


if __name__ == "__main__":  # pragma: no cover
    from .common import get_logger
    cfg = load_config()
    log = get_logger("news.arxiv")
    recs = fetch(cfg, log)
    for rec in top(recs, int(cfg["arxiv"].get("max_items", 6))):
        print(f'{rec["extra"]["score"]:>3}  {rec["date"]}  {rec["title"][:78]}')
        print(f"     {rec['url']}")
