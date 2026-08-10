"""INSPIRE-HEP fetchers: published literature, and conferences.

Two endpoints, two jobs.

`literature` feeds Theory highlights. The brief asks for *published* papers
carrying arXiv + INSPIRE + DOI, so a record without a DOI and a journal
reference is dropped here rather than patched up later: those three links are
the entry's reason to exist, and one of them missing means we would be
guessing.

`conferences` feeds the Conferences section, entirely deterministically — no
model involved in dates or places. INSPIRE's conference search does not accept
a date predicate in the query (`opening_date > …` silently returns nothing),
so the window is applied here, after sorting the API result by date descending.
That is worth knowing before someone "fixes" the query.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re

from . import cache
from .common import clean_text, http_get, load_config, truncate

LIT_API = "https://inspirehep.net/api/literature"
CONF_API = "https://inspirehep.net/api/conferences"

LIT_FIELDS = ",".join([
    "titles", "authors", "arxiv_eprints", "dois", "publication_info",
    "earliest_date", "abstracts", "control_number", "document_type",
])
CONF_FIELDS = ",".join([
    "titles", "acronyms", "addresses", "opening_date", "closing_date",
    "cnum", "urls", "series", "control_number",
])

# Journal tiers, used only to order the candidate pool handed to the model.
# Not a quality judgement on a paper — a way to put the venues a neutrino
# physicist reads first at the top of a list that has to be cut somewhere.
JOURNAL_TIERS: list[tuple[int, tuple[str, ...]]] = [
    (4, ("Nature", "Nature Phys.", "Nature Astron.", "Science",
         "Phys.Rev.Lett.", "Phys.Rept.", "Rev.Mod.Phys.")),
    (3, ("Phys.Rev.D", "JHEP", "Phys.Lett.B", "Eur.Phys.J.C",
         "JCAP", "Phys.Rev.C")),
    (2, ("Astrophys.J.", "Nucl.Phys.B", "Prog.Part.Nucl.Phys.",
         "Ann.Rev.Nucl.Part.Sci.", "Universe", "Symmetry")),
]

# Document types that are not "a recent published paper" in the sense meant
# here. Proceedings repeat talks; instrumentation notes belong to Experiments.
SKIP_TYPES = {"conference paper", "proceedings", "thesis", "book",
              "book chapter", "activity report", "note"}


def _journal_rank(journal: str) -> int:
    for rank, names in JOURNAL_TIERS:
        if journal in names:
            return rank
    return 1


def _authors(meta: dict, limit: int = 3) -> str:
    names = [clean_text(a.get("full_name", "")) for a in meta.get("authors", [])]
    names = [n for n in names if n]
    if not names:
        return ""
    # INSPIRE stores "Fogli, G.L."; the page reads better as "G.L. Fogli".
    flipped = []
    for n in names[:limit]:
        if "," in n:
            last, first = [p.strip() for p in n.split(",", 1)]
            flipped.append(f"{first} {last}".strip())
        else:
            flipped.append(n)
    out = ", ".join(flipped)
    if len(names) > limit:
        out += " et al."
    return out


def _abstract(meta: dict) -> str:
    for a in meta.get("abstracts") or []:
        if a.get("value"):
            return clean_text(a["value"])
    return ""


# --------------------------------------------------------------------------- #
# literature
# --------------------------------------------------------------------------- #
def fetch_literature(cfg: dict, log: logging.Logger) -> list[dict]:
    conf = cfg.get("inspire", {}).get("literature", {})
    errors: list[str] = []
    if not cfg.get("inspire", {}).get("enabled", True):
        log.info("inspire: disabled in config")
        cache.store("inspire", [], ["disabled"])
        return []

    window_days = int(conf.get("window_days", 120))
    cutoff = _dt.date.today() - _dt.timedelta(days=window_days)
    query = conf.get("query", "t neutrino and tc p")
    # The date predicate goes in the query for literature — unlike conferences,
    # here INSPIRE honours it, and it keeps the response small.
    q = f"{query} and de > {cutoff.isoformat()}"

    r = http_get(LIT_API, params={
        "q": q, "sort": "mostrecent",
        "size": int(conf.get("max_fetch", 120)), "fields": LIT_FIELDS,
    }, timeout=60, log=log)
    if r is None:
        errors.append("INSPIRE literature API unreachable")
        cache.store("inspire", [], errors)
        return []

    try:
        hits = r.json()["hits"]["hits"]
    except (ValueError, KeyError) as exc:
        errors.append(f"unexpected INSPIRE payload: {exc}")
        log.warning("inspire: unexpected payload (%s)", exc)
        cache.store("inspire", [], errors)
        return []

    records: list[dict] = []
    skipped_unpublished = skipped_type = 0
    for hit in hits:
        meta = hit.get("metadata", {})
        recid = meta.get("control_number")
        if not recid:
            continue

        doc_types = {t.lower() for t in (meta.get("document_type") or [])}
        if doc_types & SKIP_TYPES:
            skipped_type += 1
            continue

        pub = (meta.get("publication_info") or [{}])[0]
        journal = pub.get("journal_title") or ""
        dois = [d.get("value") for d in (meta.get("dois") or []) if d.get("value")]
        # The three-link promise: no DOI or no journal means we cannot keep it.
        if not dois or not journal:
            skipped_unpublished += 1
            continue

        eprint = ""
        for e in meta.get("arxiv_eprints") or []:
            if e.get("value"):
                eprint = e["value"]
                break

        title = clean_text((meta.get("titles") or [{}])[0].get("title", ""))
        if not title:
            continue

        vol = pub.get("journal_volume", "")
        page = pub.get("page_start") or pub.get("artid") or ""
        year = pub.get("year", "")
        ref = " ".join(x for x in [journal, vol, f"({year})" if year else "",
                                   page] if x).strip()

        records.append(cache.make_record(
            id=f"inspire:{recid}",
            source="inspire",
            title=title,
            url=f"https://inspirehep.net/literature/{recid}",
            links={
                "inspire": f"https://inspirehep.net/literature/{recid}",
                "doi": f"https://doi.org/{dois[0]}",
                "arxiv": f"https://arxiv.org/abs/{eprint}" if eprint else "",
            },
            authors=_authors(meta),
            date=meta.get("earliest_date", "") or "",
            summary=truncate(_abstract(meta), 1400),
            extra={
                "journal": journal,
                "reference": ref,
                "year": year,
                "eprint": eprint,
                "rank": _journal_rank(journal),
            },
        ))

    # Ordering of the candidate pool: journal tier first, recency inside a
    # tier. Two passes rather than one composite key because the two criteria
    # sort in opposite directions; Python's sort is stable, so the second pass
    # keeps the first pass's order within equal ranks.
    records.sort(key=lambda r: r["date"] or "", reverse=True)
    records.sort(key=lambda r: r["extra"]["rank"], reverse=True)

    # max_items caps the candidate pool handed on. It was being ignored, so
    # the dashboard exposed a knob that changed nothing.
    cap = int(conf.get("max_items", 0) or 0)
    if cap > 0:
        records = records[:max(cap * 3, cap)]   # a pool to choose from, not the final list

    log.info("inspire literature: %d published candidates "
             "(%d dropped: no DOI/journal, %d dropped: document type)",
             len(records), skipped_unpublished, skipped_type)
    if not records:
        errors.append("no published paper matched inside the window")

    cache.store("inspire", records, errors)
    return records


# --------------------------------------------------------------------------- #
# conferences
# --------------------------------------------------------------------------- #
_ACRONYM_RE = re.compile(r"[A-Za-z]")


def _place(meta: dict) -> str:
    addr = (meta.get("addresses") or [{}])[0]
    cities = addr.get("cities") or []
    country = addr.get("country") or ""
    parts = [c for c in cities[:1] if c] + ([country] if country else [])
    return ", ".join(parts)


def _conf_url(meta: dict, recid: int) -> str:
    """Prefer the conference's own site; fall back to its INSPIRE page, which
    always exists."""
    for u in meta.get("urls") or []:
        val = u.get("value", "")
        if val.startswith("http"):
            return val
    return f"https://inspirehep.net/conferences/{recid}"


def _span(opening: str, closing: str) -> str:
    """'2026-10-28' + '2026-10-31' -> '28–31 October 2026'."""
    try:
        o = _dt.date.fromisoformat(opening)
    except (ValueError, TypeError):
        return ""
    try:
        c = _dt.date.fromisoformat(closing)
    except (ValueError, TypeError):
        return o.strftime("%-d %B %Y")
    if o == c:
        return o.strftime("%-d %B %Y")
    if (o.year, o.month) == (c.year, c.month):
        return f"{o.day}–{c.day} {o.strftime('%B %Y')}"
    if o.year == c.year:
        return f"{o.day} {o.strftime('%B')} – {c.day} {c.strftime('%B %Y')}"
    return f"{o.strftime('%-d %B %Y')} – {c.strftime('%-d %B %Y')}"


def fetch_conferences(cfg: dict, log: logging.Logger, *,
                      scope: str = "neutrino") -> list[dict]:
    """Conferences for one scope.

    scope="neutrino"  the field's own meetings, upcoming and just concluded
    scope="general"   the flagship particle-physics series (ICHEP, Moriond,
                      LHCP, DIS, SUSY, Quark Matter …), from the `general`
                      block of the config

    One code path for both: the only differences are the query, the window and
    which cache file the result lands in.
    """
    root = cfg.get("inspire", {}).get("conferences", {})
    conf = root if scope == "neutrino" else (root.get("general") or {})
    source = "inspire-conf" if scope == "neutrino" else "inspire-conf-general"
    errors: list[str] = []
    if not cfg.get("inspire", {}).get("enabled", True) \
            or not conf.get("enabled", True):
        cache.store(source, [], ["disabled"])
        return []

    today = _dt.date.today()
    ahead = today + _dt.timedelta(days=int(conf.get("upcoming_months", 12)) * 30)
    behind = today - _dt.timedelta(days=int(conf.get("recent_months", 4)) * 30)

    # Fetched date-descending and filtered here: the API ignores a date
    # predicate in `q` and answers with an empty set instead of an error.
    #
    # Note for whoever edits the query: INSPIRE wants OR in CAPITALS. Written
    # `a or b` it does not complain — it returns zero hits, which reads like
    # "nothing matched" rather than "your query is malformed".
    r = http_get(CONF_API, params={
        "q": conf.get("query", "neutrino"),
        "sort": "datedesc", "size": int(conf.get("max_fetch", 250)),
        "fields": CONF_FIELDS,
    }, timeout=60, log=log)
    if r is None:
        errors.append("INSPIRE conferences API unreachable")
        cache.store(source, [], errors)
        return []

    try:
        hits = r.json()["hits"]["hits"]
    except (ValueError, KeyError) as exc:
        errors.append(f"unexpected INSPIRE payload: {exc}")
        cache.store(source, [], errors)
        return []

    hints = [h.lower() for h in (conf.get("series_hints") or [])]
    records: list[dict] = []
    for hit in hits:
        meta = hit.get("metadata", {})
        recid = meta.get("control_number")
        opening = meta.get("opening_date") or ""
        if not recid or not opening:
            continue
        try:
            o = _dt.date.fromisoformat(opening)
        except ValueError:
            continue
        if not (behind <= o <= ahead):
            continue

        # "Upcoming" must mean "not finished", not "not started": a conference
        # in its third day was being filed under Recently concluded, which is
        # simply wrong to a reader deciding whether to go.
        closing = meta.get("closing_date") or ""
        try:
            end = _dt.date.fromisoformat(closing)
        except ValueError:
            end = o
        upcoming = end >= today

        title = clean_text((meta.get("titles") or [{}])[0].get("title", ""))
        if not title:
            continue
        acronym = ""
        for a in meta.get("acronyms") or []:
            if a:
                acronym = a
                break

        hay = f"{title} {acronym}".lower()
        flagship = any(h in hay for h in hints)
        # The general scope casts a wide net on purpose, then keeps only the
        # named series: without this, "particle physics" returns every local
        # workshop and the section stops meaning anything.
        if scope == "general" and hints and not flagship:
            continue

        address = (meta.get("addresses") or [{}])[0]
        records.append(cache.make_record(
            id=f"conf:{recid}",
            source="inspire-conf",
            title=title,
            url=_conf_url(meta, recid),
            links={"inspire": f"https://inspirehep.net/conferences/{recid}"},
            date=opening,
            summary="",
            extra={
                "acronym": acronym,
                "place": _place(meta),
                # Kept separately from `place` because the map plots by
                # country: INSPIRE gives a city name but no coordinates.
                "country_code": (address.get("country_code") or "").upper(),
                "city": (address.get("cities") or [""])[0],
                "scope": scope,
                "opening": opening,
                "closing": closing,
                "span": _span(opening, closing),
                "upcoming": upcoming,
                "in_progress": upcoming and o <= today,
                "flagship": flagship,
                "cnum": meta.get("cnum", ""),
            },
        ))

    # INSPIRE holds genuine duplicates — the 17th Neutrino Summer School is in
    # there twice, under two record ids, with the city spelled two ways. Same
    # dates plus a similar title is enough to call it one event; the record
    # with a real conference URL (not the INSPIRE fallback) is the keeper.
    # Keyed on the CLOSING date, not the opening one: the two summer-school
    # records differ by a day at the start (28 vs 29 June) and agree at the
    # end, so an opening-date key merged nothing at all.
    deduped: dict[tuple, dict] = {}
    for r in records:
        key = (r["extra"]["closing"] or r["extra"]["opening"],
               re.sub(r"[^a-z0-9]", "", r["title"].lower())[:26])
        best = deduped.get(key)
        if best is None:
            deduped[key] = r
            continue
        def has_own_site(rec: dict) -> bool:
            return "inspirehep.net/conferences" not in rec["url"]
        if has_own_site(r) and not has_own_site(best):
            deduped[key] = r
    if len(deduped) != len(records):
        log.info("inspire conferences: %d duplicate record(s) merged",
                 len(records) - len(deduped))
    records = list(deduped.values())

    # Upcoming first (soonest at the top), then the recently concluded ones
    # (most recent first). Flagship series win ties.
    upcoming = sorted([r for r in records if r["extra"]["upcoming"]],
                      key=lambda r: (r["date"], not r["extra"]["flagship"]))
    recent = sorted([r for r in records if not r["extra"]["upcoming"]],
                    key=lambda r: (r["date"], r["extra"]["flagship"]),
                    reverse=True)
    ordered = upcoming + recent

    log.info("inspire conferences (%s): %d in window (%d upcoming, %d recent)",
             scope, len(ordered), len(upcoming), len(recent))
    if not ordered:
        errors.append("no conference in the configured window")

    cache.store(source, ordered, errors)
    return ordered


def split(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """(upcoming, recently concluded) — what the renderer wants."""
    return ([r for r in records if r["extra"].get("upcoming")],
            [r for r in records if not r["extra"].get("upcoming")])


if __name__ == "__main__":  # pragma: no cover
    from .common import get_logger
    cfg = load_config()
    log = get_logger("news.inspire")
    lit = fetch_literature(cfg, log)
    print(f"\n--- literature ({len(lit)}) ---")
    for rec in lit[:10]:
        print(f'  [{rec["extra"]["rank"]}] {rec["extra"]["reference"]:34}'
              f' {rec["title"][:60]}')
    conf = fetch_conferences(cfg, log)
    up, rec = split(conf)
    print(f"\n--- conferences: {len(up)} upcoming, {len(rec)} recent ---")
    for c in (up[:6] + rec[:4]):
        flag = "→" if c["extra"]["upcoming"] else "·"
        print(f'  {flag} {c["extra"]["span"]:32} {c["extra"]["place"][:22]:24}'
              f' {c["title"][:52]}')
