"""arXiv fetcher for the compact digest section.

Deliberately not AI: the page's compact digest is a ranked list of what the
arXiv API returned in the last few days, scored by keyword. The curated,
reasoned digest is the separate Neutrino-Highlights page produced by the
/arxiv skill; this section exists so the news page is never stale when that
skill has not run, and it links across for the long version.

Scoring is intentionally crude — a title hit counts three, an abstract hit
one. It is a relevance sort, not a judgement, and pretending otherwise by
inventing a cleverer formula would only make the ordering harder to explain.

Two routes to the same papers. The API (/api/query) is the one that answers
"everything in the last 168 hours", and it is tried first. When it refuses —
it answered HTTP 429 "Rate exceeded" on five days between August and
September 2026, three of them consecutive, and the digest page sat on
12 September's preprints for two days — the per-category RSS feeds are read
instead. They live on a different host with a different limiter, and on every
one of those days they answered normally.

The feeds are a narrower thing and the code does not pretend otherwise: one
day's announcements rather than a rolling week, so `window_hours` cannot be
applied and is not claimed. Both routes score identically, build the same
record, and mark it with `extra.route`, which the digest page reads to say
where the day's list came from. Only "new" and "cross" announcements are
taken: a "replace" is a revision of an older paper, and listing it as today's
preprint would be the one thing this section must never do.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET

from . import cache
from .common import clean_text, http_get, load_config, truncate

API = "https://export.arxiv.org/api/query"
# One feed per category, on a host that is rate-limited separately from the
# API — which is the entire reason this fallback can work at all.
RSS = "https://rss.arxiv.org/rss/{category}"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"

# What the feed calls an announcement that is genuinely appearing today.
# "replace" and "replace-cross" are new versions of papers announced days or
# years ago; the digest is a list of what is new.
ANNOUNCE_KINDS = ("new", "cross")

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


# How the last word of a term is allowed to end. A digest keyword is a noun
# phrase, and the papers write it either way: "Eclectic flavour symmetries
# without flavons" carries the config's `flavour symmetry` in the plural, and
# matching only the singular cost that title three points and dropped it to
# 61st of 66 on 16 September 2026. The suffix is always followed by \b, so
# widening it does not license an arbitrary ending: `reactor` still does not
# match "reactorless".
_PLURAL = (
    (("ch", "sh", "s", "x", "z"), "(?:es)?"),   # searches, fluxes
    (("a",), "(?:e|s)?"),                       # supernova -> supernovae
)


def _plural(word: str) -> str:
    """The word, as a pattern that also matches its plural."""
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        return re.escape(word[:-1]) + "(?:y|ies)"   # hierarchy -> hierarchies
    for endings, suffix in _PLURAL:
        if word.endswith(endings):
            return re.escape(word) + suffix
    return re.escape(word) + "s?"


def _compile(terms: list[str]) -> list[tuple[str, re.Pattern]]:
    """Word-boundary patterns, so 'nova' does not match 'innovation', with the
    last word of each term also matching its plural.

    A term whose plural is another term in the same list is dropped: with the
    plural folded into the pattern, a config that still spells out both forms
    would fire twice on one word and quietly double that paper's score."""
    out: list[tuple[str, re.Pattern]] = []
    for t in terms:
        if not t:
            continue
        words = t.lower().split()
        if not words:
            continue
        pat = re.compile(r"\b" + r"\s+".join(
            [re.escape(w) for w in words[:-1]] + [_plural(words[-1])]) + r"\b")
        if any(kept.fullmatch(t.lower()) for _, kept in out):
            continue
        out.append((t, pat))
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
def _make(aid: str, title: str, summary: str, authors: str, day: str,
          cats: list[str], pts: int, hits: list[str], route: str,
          doi: str = "") -> dict:
    """The one record shape the digest reads, whichever route found it."""
    return cache.make_record(
        id=f"arxiv:{aid}",
        source="arxiv",
        title=title,
        url=f"https://arxiv.org/abs/{aid}",
        links={
            "arxiv": f"https://arxiv.org/abs/{aid}",
            "pdf": f"https://arxiv.org/pdf/{aid}",
            "doi": f"https://doi.org/{doi}" if doi else "",
        },
        authors=authors,
        date=day,
        summary=truncate(summary, 1200),
        extra={"categories": cats[:4], "score": pts, "hits": hits[:8],
               "route": route},
    )


# The feed's own preamble to every abstract: "arXiv:2609.12610v1 Announce
# Type: new \nAbstract: ...". It is metadata the item already carries in its
# own elements, and leaving it in would put it in the scored text and on the
# page.
_RSS_PREFIX = re.compile(r"^\s*arXiv:\S+\s+Announce Type:\s*[\w-]+\s*",
                         re.IGNORECASE)
_RSS_ABSTRACT = re.compile(r"^\s*Abstract:\s*", re.IGNORECASE)


# The feeds hand back author names as their submitters typed them, which for
# anyone with an accent means LaTeX: "H. Almaz\\'an", "Rita de C\\'assia".
# The API route returns the same names already resolved to Unicode, so without
# this the page would spell a person's name one way on a good day and another
# on a fallback day — and "Almaz\\'an" on any day is simply wrong.
#
# Deliberately a small table of the accents that actually occur in author
# lists, not a LaTeX parser: an unknown command is left alone rather than
# mangled into a guess, which keeps the failure visible instead of plausible.
_ACCENTS = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
    "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
    "c": "\u0327", "k": "\u0328", "r": "\u030a", "d": "\u0323", "b": "\u0331",
}
# \l, \o and friends are whole letters, not marks on one.
_LETTERS = {"l": "ł", "L": "Ł", "o": "ø", "O": "Ø", "ss": "ß",
            "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å"}

_TEX_ACCENT = re.compile(r"\\(['`^\"~=.uvHckrdb])\s*\{?([A-Za-z])\}?")
_TEX_LETTER = re.compile(r"\\(ss|ae|AE|oe|OE|aa|AA|[lLoO])(?=[^A-Za-z]|$)")
_TEX_BRACES = re.compile(r"[{}]")


def _delatex(text: str) -> str:
    """LaTeX accents in a name, resolved to the letters they stand for."""
    if "\\" not in text and "{" not in text:
        return text
    out = _TEX_ACCENT.sub(lambda m: unicodedata.normalize(
        "NFC", m.group(2) + _ACCENTS[m.group(1)]), text)
    out = _TEX_LETTER.sub(lambda m: _LETTERS[m.group(1)], out)
    return _TEX_BRACES.sub("", out).strip()


def _rss_summary(description: str) -> str:
    return _RSS_ABSTRACT.sub("", _RSS_PREFIX.sub("", clean_text(description)))


def _rss_id(item: ET.Element) -> str:
    """'https://arxiv.org/abs/2609.12610' -> '2609.12610', version dropped.

    The link is preferred over the guid ("oai:arXiv.org:2609.12610v1") for the
    same reason _arxiv_id drops the version: a paper that gets a v2 must keep
    the id it had, or every revision would read as a new paper.
    """
    raw = (item.findtext("link") or "").strip()
    m = re.search(r"abs/([^v\s/]+?)(?:v\d+)?$", raw)
    return m.group(1) if m else ""


def _rss_day(item: ET.Element, channel_day: str) -> str:
    """The item's own announcement date, or the channel's."""
    raw = (item.findtext("pubDate") or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return _dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return channel_day


def _from_rss(conf: dict, log: logging.Logger, errors: list[str]) -> list[dict]:
    """The configured categories' feeds, scored exactly as the API route is.

    Used only when the API refuses. It is a different question — "what was
    announced today" rather than "what appeared in the last 168 hours" — so
    the count that gets logged says so, and nothing here applies a window it
    cannot honour.
    """
    high = _compile(conf.get("keywords", {}).get("high", []))
    low = _compile(conf.get("keywords", {}).get("low", []))
    today = _dt.date.today().isoformat()

    by_id: dict[str, tuple[int, dict]] = {}
    seen = reached = 0
    for cat in (conf.get("categories") or ["hep-ph"]):
        r = http_get(RSS.format(category=cat), timeout=45, log=log)
        if r is None:
            errors.append(f"RSS feed unreachable: {cat}")
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as exc:
            errors.append(f"unparseable RSS for {cat}: {exc}")
            log.warning("arxiv: RSS for %s did not parse (%s)", cat, exc)
            continue
        reached += 1
        channel_day = _rss_day(root.find("channel") or ET.Element("channel"), today)

        for item in root.iter("item"):
            seen += 1
            kind = (item.findtext(f"{ARXIV_NS}announce_type") or "").strip().lower()
            if kind not in ANNOUNCE_KINDS:
                continue
            aid = _rss_id(item)
            if not aid or aid in by_id:        # a paper cross-listed in two feeds
                continue
            title = clean_text(item.findtext("title"))
            summary = _rss_summary(item.findtext("description") or "")
            pts, hits = score(title, summary, high, low)
            if pts <= 0:
                continue
            cats = [c.text.strip() for c in item.findall("category") if c.text]
            authors = _delatex(clean_text(item.findtext(f"{DC_NS}creator")))
            names = [n.strip() for n in authors.split(",") if n.strip()]
            if len(names) > 3:
                authors = ", ".join(names[:3]) + " et al."
            by_id[aid] = (pts, _make(aid, title, summary, authors,
                                     _rss_day(item, channel_day), cats, pts,
                                     hits, "rss"))

    if not reached:
        return []
    records = [rec for _, rec in sorted(by_id.values(), key=lambda kv: -kv[0])]
    log.warning("arxiv: fell back to the RSS feeds — %d announcement(s) across "
                "%d of %d feed(s), %d new or cross-listed and on topic. This is "
                "the day's announcements, not the %dh window the API answers.",
                seen, reached, len(conf.get("categories") or []), len(records),
                int(conf.get("window_hours", 72)))
    return records


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
        # The feeds, not the cache. Re-rendering yesterday's cached records
        # would re-stamp the page with today's date while showing yesterday's
        # papers, which is the one outcome worse than not updating; the feeds
        # are today's actual announcements, from a host with its own limiter.
        errors.append("arXiv API unreachable")
        log.warning("arxiv: the API refused (HTTP error or timeout) — trying "
                    "the per-category RSS feeds instead")
        records = _from_rss(conf, log, errors)
        if not records:
            # Both routes gone. render.digest sees an empty list, leaves
            # digest.md untouched, and the page keeps BOTH its papers and its
            # "Last successful update" stamp — the honest outcome, and the
            # log has to describe it rather than promise a fallback that has
            # already been tried.
            log.warning("arxiv: the feeds gave nothing either — no records "
                        "today, so the digest page keeps its previous content "
                        "and its previous timestamp")
        cache.store("arxiv", records, errors)
        return records

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
        rec = _make(aid, title, summary, _authors(entry),
                    published.date().isoformat(), cats_e, pts, hits, "api",
                    doi=entry.findtext(f"{ARXIV_NS}doi") or "")
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
