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

TWO WAYS IN, AND THE SECOND IS THE BACKBONE
-------------------------------------------
The section used to rest on sources that go down. nu.to.infn.it (Neutrino
Unbound) has answered ConnectTimeout every morning since 9 September 2026 and
took two thirds of the calendar with it (var/news/cache/2026-09-08 holds 63 of
its records, 2026-09-12 holds none); agenda.infn.it is behind a bot check. The
one source that does not go down is INSPIRE — and it was the least used of the
three, because it was asked the wrong question.

  * the KEYWORD QUERY (`inspire.conferences.query`, historically the single
    word "neutrino") asks INSPIRE's free-text search.
  * the SWEEP (`inspire.conferences.sweep`) pages through the conference
    collection by date instead, newest first, and filters LOCALLY with
    tools/news/affinity.py. The collection holds tens of thousands of records;
    a few hundred open inside this project's window (18 months ahead, 5 months
    back). Filtering those by topic here finds meetings the keyword query
    never saw.

The two are UNIONED and deduplicated on `control_number`, never substituted:
if the sweep breaks (an API shape change, a bad page) the keyword query still
answers, and nothing that worked yesterday stops working today. See
`_sweep_hits` for the paging bound and `fetch_conferences` for the filter.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re

from . import affinity, cache
from .common import clean_text, http_get, load_config, truncate

LIT_API = "https://inspirehep.net/api/literature"
CONF_API = "https://inspirehep.net/api/conferences"

LIT_FIELDS = ",".join([
    "titles", "authors", "arxiv_eprints", "dois", "publication_info",
    "earliest_date", "abstracts", "control_number", "document_type",
])
# `inspire_categories` and `keywords` are asked for so tools/news/affinity.py
# has real metadata to classify a meeting with instead of only a title.
# Verified against the live API on 2026-09-12, which is where the shapes the
# parsing below expects come from: `inspire_categories` is a list of
# {"term": "Experiment-HEP"} (a closed vocabulary — Experiment-HEP,
# Phenomenology-HEP, Astrophysics, Instrumentation, Other, …), `series` a list
# of {"name": "Neutrino Geoscience", "number": 3}, and `keywords` a list of
# {"value": "neutrino; multimessenger; astrophysics"} — one free-text blob per
# entry, not one keyword per entry. The keywords are carried but NOT used to
# decide a tier: they are uncontrolled author-supplied prose, and matching
# subject words against them is exactly how a Higgs workshop that lists
# "neutrino mass" among fifteen keywords would be called a neutrino
# conference.
CONF_FIELDS = ",".join([
    "titles", "acronyms", "addresses", "opening_date", "closing_date",
    "cnum", "urls", "series", "control_number", "inspire_categories",
    "keywords",
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


# The sweep's result, memoised for the life of the process and keyed by the
# window it covers. `fetch_conferences` is called twice per run (the neutrino
# block and the `general` one) and both want the SAME raw records — the
# filtering that makes them differ happens afterwards. Without this the run
# would page INSPIRE twice for identical bytes. The key carries the dates, so
# a long-lived process re-sweeps when the day turns.
_SWEEP_CACHE: dict[tuple, list[dict]] = {}

# INSPIRE's hard ceiling on `size`, verified against the live API on
# 2026-09-12: size=1000 answers 200, size=1001 answers
# HTTP 400 "Maximum search page size of `1000` results exceeded". 500 is used
# instead of the maximum because two pages of 500 already reach past the
# 5-month lookback, and a ~344 kB response is a kinder thing to ask for twice
# than a ~700 kB one once.
INSPIRE_MAX_SIZE = 1000


def _sweep_hits(root: dict, log: logging.Logger, behind: _dt.date) -> list[dict]:
    """Page the conference collection by date until it reaches past `behind`.

    A calendar sweep, not a search: INSPIRE is asked for everything, newest
    first, and the topic filter is applied locally by the caller. That is the
    whole point — the database knows about these meetings, its free-text index
    does not connect them to the word "neutrino".

    BOUNDED, deliberately and in two independent ways. The collection holds
    tens of thousands of records; an unbounded loop over it is how a morning
    job becomes a morning outage, and it would be INSPIRE paying for the
    mistake. So: `max_pages` is a hard stop whatever the dates say, and the
    loop also exits as soon as the oldest record in hand is older than the
    window's own start. Measured 2026-09-12: the second condition fires after
    2 pages, so the cap of 6 is three times the observed need rather than a
    guess.

    Returns [] on any failure, which is what keeps the keyword query
    authoritative — see the module docstring.
    """
    sweep = root.get("sweep") or {}
    if not sweep.get("enabled", True):
        return []
    size = min(int(sweep.get("size", 500)), INSPIRE_MAX_SIZE)
    max_pages = max(1, int(sweep.get("max_pages", 6)))

    key = (size, max_pages, behind.isoformat())
    if key in _SWEEP_CACHE:
        return _SWEEP_CACHE[key]

    hits: list[dict] = []
    pages = 0
    for page in range(1, max_pages + 1):
        r = http_get(CONF_API, params={
            "sort": "datedesc", "size": size, "page": page,
            "fields": CONF_FIELDS,
        }, timeout=90, log=log)
        if r is None:
            log.warning("inspire sweep: page %d unreachable — stopping with "
                        "%d record(s); the keyword query still answers",
                        page, len(hits))
            break
        try:
            batch = r.json()["hits"]["hits"]
        except (ValueError, KeyError) as exc:
            log.warning("inspire sweep: unexpected payload on page %d (%s) — "
                        "stopping; the keyword query still answers", page, exc)
            break
        if not batch:
            break
        hits.extend(batch)
        pages = page
        oldest = min((h.get("metadata", {}).get("opening_date") or "9999")
                     for h in batch)
        if oldest < behind.isoformat():
            break
    else:
        # Ran out of pages before running out of window. Not an error — the
        # sweep still returns what it has — but it means the lookback is
        # incomplete, and silence here would hide that permanently.
        log.warning("inspire sweep: hit the %d-page cap before reaching %s; "
                    "the recent-conference lookback may be short",
                    max_pages, behind)

    log.info("inspire sweep: %d record(s) over %d page(s)", len(hits), pages)
    _SWEEP_CACHE[key] = hits
    return hits


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
    keyword_hits: list[dict] = []
    if r is None:
        errors.append("INSPIRE conferences API unreachable")
    else:
        try:
            keyword_hits = r.json()["hits"]["hits"]
        except (ValueError, KeyError) as exc:
            errors.append(f"unexpected INSPIRE payload: {exc}")

    # --- the union ------------------------------------------------------- #
    # The keyword query FIRST, so its records own their id in `from_keyword`
    # and are exempt from the topic filter below; then the sweep, which only
    # adds ids the query did not already return. Deduplicated on
    # `control_number`, INSPIRE's own primary key — not on title or dates,
    # which the same meeting spells differently from one source to the next.
    #
    # If BOTH come back empty the section is empty and says so; if only the
    # sweep is empty the page is exactly what it was before the sweep existed.
    # That is the whole safety property, and it is why this is a union and not
    # a replacement.
    from_keyword: set = set()
    ordered_hits: list[dict] = []
    seen_recid: set = set()
    for hit in keyword_hits:
        recid = hit.get("metadata", {}).get("control_number")
        if recid is None or recid in seen_recid:
            continue
        seen_recid.add(recid)
        from_keyword.add(recid)
        ordered_hits.append(hit)
    n_keyword = len(ordered_hits)

    swept = _sweep_hits(root, log, behind)
    for hit in swept:
        recid = hit.get("metadata", {}).get("control_number")
        if recid is None or recid in seen_recid:
            continue
        seen_recid.add(recid)
        ordered_hits.append(hit)
    if not ordered_hits:
        cache.store(source, [], errors or ["no conference returned at all"])
        return []

    # The topic filter for swept records, and the scheme it uses. Built once.
    scheme = affinity.scheme_from(cfg)
    KEEP_TIERS = {"core", "related"}

    hints = [h.lower() for h in (conf.get("series_hints") or [])]
    records: list[dict] = []
    dropped_offtopic = 0
    for hit in ordered_hits:
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
        # INSPIRE's own metadata about what the meeting IS, kept as flat
        # lists of strings so the record survives a JSON round-trip through
        # the cache unchanged and affinity.py never has to know INSPIRE's
        # nesting. Empty lists where INSPIRE says nothing — never a guessed
        # category, which would be a claim INSPIRE did not make.
        categories = [c.get("term", "") for c in (meta.get("inspire_categories") or [])
                      if c.get("term")]
        series_names = [s.get("name", "") for s in (meta.get("series") or [])
                        if s.get("name")]
        keywords = [k.get("value", "") for k in (meta.get("keywords") or [])
                    if k.get("value")]

        # --- the topic filter, and what it now costs --------------------- #
        # A NEW COUPLING, and the most important thing on this page for the
        # next reader to know. Until the sweep existed, tools/news/affinity.py
        # only chose a COLOUR: every record that reached here was published,
        # and a meeting the classifier could not read simply wore a grey "Not
        # classified" chip. From here on, for SWEPT records only, affinity
        # also decides what APPEARS — and `unknown` means dropped, not grey.
        #
        # That makes the vocabulary in affinity.py load-bearing. A genuinely
        # relevant meeting whose title and acronym say nothing readable now
        # vanishes instead of being shown and left to the reader. It is the
        # right trade at this scale — the sweep offers hundreds of upcoming
        # meetings, nearly all of them noise to this page — but it IS a trade,
        # and someone editing DEFAULT_TERMS is now editing the calendar, not
        # the palette.
        #
        # It applies to SWEPT RECORDS ONLY. Records from the keyword query
        # (`from_keyword`), from Neutrino Unbound and from Indico are NOT
        # subject to it and never have been: those sources were asked a
        # question that already encodes relevance, and re-judging their
        # answers here would silently narrow three working sources to fix a
        # problem only the fourth has. The `general` block is untouched too —
        # its `series_hints` filter above is the one that applies there.
        if scope != "general" and recid not in from_keyword:
            tier = affinity.classify({"title": title, "extra": {
                "acronym": acronym, "series": series_names,
                "categories": categories}}, scheme)["tier"]
            if tier not in KEEP_TIERS:
                dropped_offtopic += 1
                continue

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
                # For affinity.classify: the series name is the organisers'
                # own statement of what the meeting is, and the categories
                # are INSPIRE's.
                "series": series_names,
                "categories": categories,
                "keywords": keywords,
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

    log.info("inspire conferences (%s): %d in window (%d upcoming, %d recent) "
             "— %d from the keyword query, %d swept records considered, "
             "%d dropped as off-topic",
             scope, len(ordered), len(upcoming), len(recent),
             n_keyword, len(swept), dropped_offtopic)
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
