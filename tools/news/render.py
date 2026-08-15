"""Write the three automated pages of global-nu from fetched records.

    news.md          the narrative: experiments, then theory
    digest.md        the day's arXiv preprints, experimental and theoretical
    conferences.md   upcoming and recent meetings

Presentation only. Nothing here decides what is true: it renders records that
were fetched, and narrative text whose every citation has already been checked
against those records by synthesize.validate(). If a section has no material,
it says so — an honest empty section beats an invented full one.

Each page is rewritten whole, between the frontmatter and the closing fence,
so a partial failure can never leave half of yesterday's page glued to half of
today's.
"""

from __future__ import annotations

import datetime as _dt
import html
import logging
from pathlib import Path

from . import conferences as conf_mod, fetch_inspire, figures, venue
from .common import (CONFERENCES_PAGE, DIGEST_PAGE, NEWS_PAGE, detex,
                     load_config, truncate)

# What counts as an experimental preprint for the digest's two streams. This
# is the *primary* arXiv category, and astro-ph.HE is deliberately not in it:
# it is the list a phenomenologist files a neutrino-astrophysics calculation
# under, so including it filed four theory papers out of six as experimental
# every day, on a page that promises the two are kept apart. A genuinely
# experimental astro-ph.HE paper is cross-listed to hep-ex or nucl-ex and is
# caught by those.
EXPERIMENTAL_CATS = ("hep-ex", "nucl-ex", "physics.ins-det")

# Two notices, because the three pages do not have the same provenance and one
# sentence for all three was false on two of them. The digest and the
# conference calendar are pure functions of fetched records — no model is
# called anywhere on their path — while the news narrative is written by one.
# Both still say, loudly, that the page was generated without a human writing
# it, because that is what a reader needs to know.
AUTOGEN_SCRIPT = """<div class="autogen">
<span aria-hidden="true">⚠</span>
<div><b>This page is generated automatically by a script from the {sources},
and may contain errors. No model is involved.</b>
<span class="stamp">Last successful update: {stamp}</span></div>
</div>"""

AUTOGEN_AI = """<div class="autogen">
<span aria-hidden="true">⚠</span>
<div><b>The summaries on this page are written automatically with AI from
fetched records, and may contain errors.</b>
<span class="stamp">Last successful update: {stamp}</span></div>
</div>"""


def _esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def _title(rec: dict, limit: int | None = None) -> str:
    """A record's title as a page can print it: TeX rendered as text, and cut
    on a word boundary with an ellipsis if it has to be cut at all."""
    text = detex(rec.get("title"))
    return _esc(truncate(text, limit) if limit else text)


def _stamp(when: _dt.datetime | None = None) -> str:
    """Local time, with the zone named: "07:34" alone is not a time anyone
    can check a daily job against without knowing where the job runs."""
    return (when or _dt.datetime.now()).astimezone().strftime("%d %B %Y, %H:%M %Z")


def _human_date(iso: str) -> str:
    """"2026-08-13" -> "13 Aug 2026".

    Returned unchanged if it does not parse: the records come from an API,
    and a date this function cannot read is still better shown as it arrived
    than swallowed.
    """
    try:
        return _dt.date.fromisoformat(str(iso)).strftime("%-d %b %Y")
    except (ValueError, TypeError):
        return str(iso)


def _links_row(rec: dict, skip: set[str] | None = None) -> str:
    """arXiv / INSPIRE / DOI, whichever the record actually carries.

    Only links that came with the record are emitted: a DOI is never
    constructed from an arXiv id, because a paper that is not published yet
    would get a link that 404s.

    `skip` leaves out link keys the caller has already shown elsewhere. The
    digest passes {"arxiv"} because the entry's title now carries that link;
    the row still appears for a record that also has a DOI or a journal, and
    disappears only when arXiv was all it had.
    """
    order = [("arxiv", "arXiv"), ("inspire", "INSPIRE"), ("doi", "DOI"),
             ("journal", "Journal"), ("source", "Source")]
    skip = skip or set()
    seen, out = set(), []
    for key, label in order:
        if key in skip:
            continue
        url = (rec.get("links") or {}).get(key)
        if url and url not in seen:
            seen.add(url)
            out.append(f'<a href="{_esc(url)}">{label}</a>')
    if not out and rec.get("url") and "url" not in skip:
        out.append(f'<a href="{_esc(rec["url"])}">Read it</a>')
    return " · ".join(out)


def _cited(ids: list[str], known: dict[str, dict]) -> str:
    """The links for the records an item cites, in the order cited."""
    parts = []
    for rid in ids:
        rec = known.get(rid)
        if not rec:
            continue
        row = _links_row(rec)
        if row:
            # 90 characters, but cut at a word boundary and marked with an
            # ellipsis: a fixed slice used to end citations mid-word ("using
            # t", "scatt") and, worse, on a word that was still spelled
            # correctly while saying something else ("experiment" for
            # "experiments").
            parts.append(f'<span class="cite">{_title(rec, 90)} — {row}</span>')
    return "".join(parts)


def _page(path: Path, frontmatter: str, body: str) -> None:
    path.write_text(frontmatter.rstrip() + "\n\n" + body.strip() + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# news
# --------------------------------------------------------------------------- #
NEWS_FRONTMATTER = """---
title: News
url: news.html
description: >-
  What is happening in neutrino physics: experiments and their results, recently
  published theory papers, milestones and new projects.
katex: false
---"""


def news(narrative: dict | None, known: dict[str, dict], log: logging.Logger,
         stamp: str | None = None) -> bool:
    """Rewrite news.md. Returns False when there is nothing to publish, in
    which case the page on disk is left exactly as it was."""
    if not narrative or not (narrative.get("experiments") or narrative.get("theory")):
        log.warning("render: no narrative — news.md left untouched")
        return False

    # The overview is model-written prose and carries no citation of its own,
    # so it sits BELOW the notice, labelled as a summary of the items under
    # it — not above the notice as the page's lede, where it read as the
    # site's own words.
    body = [f"""<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Neutrino news</p>
    <h1>News from the field</h1>
    <p class="lede">Experiments, results and recently published work from
    across the field.</p>
  </div>
</section>

::: section

""" + AUTOGEN_AI.format(stamp=stamp or _stamp())]

    if narrative.get("overview"):
        body.append(
            '\n<p class="small muted"><b>In summary.</b> '
            f'{_esc(narrative["overview"])} This paragraph summarises the items '
            'below; the sources are on the items themselves.</p>\n')

    if narrative.get("experiments"):
        body.append('\n<div class="section-head"><h2>Experiments and results</h2></div>\n')
        body.append('<div class="tiles">\n')
        for item in narrative["experiments"]:
            body.append(
                '<article class="tile">\n'
                f'<div class="stamp stamp--no">{_esc(item.get("heading", "Experiment"))}</div>\n'
                f'<p>{_esc(item["text"])}</p>\n'
                f'<div class="cites">{_cited(item["ids"], known)}</div>\n'
                '</article>\n')
        body.append('</div>\n')

    body.append(":::\n")

    if narrative.get("theory"):
        body.append('\n::: section alt\n')
        body.append('<div class="section-head"><h2>Theory highlights</h2>'
                    '<p>recently published, with the links each record '
                    'carries</p></div>\n')
        body.append('<ul class="list list--news">\n')
        for item in narrative["theory"]:
            body.append(f'<li><p>{_esc(item["text"])}</p>'
                        f'<span class="cites">{_cited(item["ids"], known)}</span></li>\n')
        body.append('</ul>\n')
        body.append('\n<div class="btn-row"><a class="btn btn--sm btn--ghost" '
                    'href="digest.html">The full arXiv digest →</a></div>\n')
        body.append(':::\n')

    _page(NEWS_PAGE, NEWS_FRONTMATTER, "".join(body))
    log.info("render: news.md — %d experiment items, %d theory items",
             len(narrative.get("experiments") or []), len(narrative.get("theory") or []))
    return True


# --------------------------------------------------------------------------- #
# digest
# --------------------------------------------------------------------------- #
DIGEST_FRONTMATTER = """---
title: arXiv digest
url: digest.html
description: >-
  The day's neutrino preprints on arXiv, experimental and theoretical, ranked by
  relevance — updated automatically every day.
katex: false
---"""


def _digest_list(records: list[dict]) -> str:
    if not records:
        return ('<p class="small muted">Nothing matched today. arXiv does not '
                'announce at weekends, so an empty section here is usually a '
                'quiet Sunday rather than a failure.</p>\n')
    out = ['<ul class="list list--news">\n']
    for rec in records:
        title = _title(rec)
        arxiv = (rec.get("links") or {}).get("arxiv")
        # The title carries the arXiv link, so the links row below drops it.
        # A record with no arXiv link keeps a plain title and an untouched
        # row — nothing is lost for the records this does not apply to.
        head = f'<a href="{_esc(arxiv)}">{title}</a>' if arxiv else title
        meta = " · ".join(x for x in (rec.get("authors"),
                                      _human_date(rec.get("date", ""))) if x)
        tags = "".join(
            f'<span class="tag">{_esc(c)}</span>'
            for c in (rec.get("extra") or {}).get("categories", [])[:3])
        # `url` is skipped alongside `arxiv`: every fetched record carries a
        # `url` (cache.py's contract), and for an arXiv-sourced record it IS
        # the arXiv link — so leaving it in would print a second "Read it"
        # link to the same address the title already points to.
        rest = _links_row(rec, skip={"arxiv", "url"} if arxiv else None)
        row = f'<span class="cites">{rest}</span>' if rest else ""
        out.append(f'<li><b>{head}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="tags">{tags}</span>{row}</li>\n')
    out.append('</ul>\n')
    return "".join(out)


def _keyword_note() -> str:
    """The keyword list itself, on the page that says it is scored against one.

    The page used to call the list "stated" while it lived only in
    tools/news/config.yaml, which is not published here. Either the word goes
    or the list does; the list is more use to a reader.
    """
    from .fetch_arxiv import ABSTRACT_WEIGHT, TITLE_WEIGHT

    kw = ((load_config().get("arxiv") or {}).get("keywords") or {})
    high, low = kw.get("high") or [], kw.get("low") or []
    if not (high or low):
        return ""
    rows = "".join(
        f"<p class=\"small\"><b>{label}</b> — {_esc(', '.join(words))}</p>"
        for label, words in (("Strong terms, counted double", high),
                             ("Supporting terms", low)) if words)
    rule = (f'<p class="small muted">A term found in the title counts '
            f'{TITLE_WEIGHT} to the {ABSTRACT_WEIGHT} it counts in the '
            'abstract, a strong term counts double a supporting one, and the '
            'scores add.</p>')
    return ('<details style="margin-top:.6rem"><summary class="small muted">'
            f'The {len(high) + len(low)} words the score is computed from'
            f'</summary>{rows}{rule}</details>\n')


def digest(records: list[dict], log: logging.Logger, stamp: str | None = None) -> bool:
    """Rewrite digest.md, keeping experiment and theory streams apart."""
    if not records:
        log.warning("render: no arXiv records — digest.md left untouched")
        return False

    def is_exp(rec: dict) -> bool:
        cats = (rec.get("extra") or {}).get("categories", [])
        return bool(cats) and cats[0].startswith(EXPERIMENTAL_CATS)

    exp = [r for r in records if is_exp(r)]
    thy = [r for r in records if not is_exp(r)]

    body = f"""<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Updated daily</p>
    <h1>The day's preprints on arXiv</h1>
    <p class="lede">Neutrino preprints ranked by relevance to the field, with
    experimental and theoretical work kept apart.</p>
  </div>
</section>

::: section

{AUTOGEN_SCRIPT.format(sources="arXiv API", stamp=stamp or _stamp())}

<div class="section-head"><h2>Experimental</h2>
<p>{len(exp)} preprint{"" if len(exp) == 1 else "s"}</p></div>

{_digest_list(exp)}

:::

::: section alt

<div class="section-head"><h2>Theory</h2>
<p>{len(thy)} preprint{"" if len(thy) == 1 else "s"}</p></div>

{_digest_list(thy)}

<p class="small muted">Ranking is deterministic: the arXiv API is queried for
the configured categories, and each record is scored against the fixed keyword
list below. No model is involved in choosing what appears here. The split
between the two streams is by the preprint's primary arXiv category:
{", ".join(EXPERIMENTAL_CATS)} are read as experimental, everything else as
theory, so a phenomenology paper cross-listed to an experimental category
still appears under theory.</p>

{_keyword_note()}

:::
"""
    _page(DIGEST_PAGE, DIGEST_FRONTMATTER, body)
    log.info("render: digest.md — %d experimental, %d theory", len(exp), len(thy))
    return True


# --------------------------------------------------------------------------- #
# conferences
# --------------------------------------------------------------------------- #
CONF_FRONTMATTER = """---
title: Conferences
url: conferences.html
description: >-
  Upcoming and recent neutrino conferences, workshops and schools, with dates,
  links, and venues where the source publishes one — refreshed daily.
katex: false
scripts:
  - assets/js/confmap.js
---"""


def _conf_list(records: list[dict], empty: str) -> str:
    if not records:
        return f'<p class="small muted">{empty}</p>\n'
    out = ['<ul class="list list--news">\n']
    for rec in records:
        extra = rec.get("extra") or {}
        meta = " · ".join(x for x in (extra.get("span"), extra.get("place")) if x)
        out.append(f'<li><b>{_title(rec)}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="cites"><a href="{_esc(rec["url"])}">Details</a></span></li>\n')
    out.append('</ul>\n')
    return "".join(out)


def _scope_block(records: list[dict], title: str, empty_upcoming: str) -> str:
    """One physics domain's meetings — `records` already narrowed by
    `conferences.split_scope()` — split the way the page has always split
    meetings within a domain: upcoming first, then recently concluded.

    This is one of the two blocks Antonio asked for (neutrino conferences,
    general particle physics); the split between the two domains is the new
    axis this function exists for, and the upcoming/recent split inside it is
    the one Task 1 already fixed a real bug on (`extra.scope` is the DOMAIN,
    never the tense — see `fetch_inspire.split`).
    """
    upcoming, recent = fetch_inspire.split(records)
    out = [f'<div class="section-head"><h2>{_esc(title)}</h2>'
          f'<p>{len(records)} meeting{"" if len(records) == 1 else "s"}</p></div>\n']
    out.append('<div class="section-head section-head--sub"><h3>Upcoming</h3>'
               f'<p>{len(upcoming)} meeting{"" if len(upcoming) == 1 else "s"}</p></div>\n')
    out.append(_conf_list(upcoming, empty_upcoming))
    out.append('<div class="section-head section-head--sub"><h3>Recent</h3>'
               f'<p>{len(recent)} meeting{"" if len(recent) == 1 else "s"}</p></div>\n')
    out.append(_conf_list(recent, "No meeting in this window has ended yet."))
    return "".join(out)


def conferences(records: list[dict], log: logging.Logger,
                stamp: str | None = None) -> bool:
    """Rewrite conferences.md, split into what is coming and what just ran."""
    if not records:
        log.warning("render: no conference records — conferences.md left untouched")
        return False

    # `extra.scope` is the field DOMAIN ("neutrino" vs "general" — what
    # conferences.split_scope() uses for the two sections below), not the
    # TENSE. It is never "past"; the field that says whether a conference is
    # still ahead is `extra.upcoming`, set by every fetcher. Indico alone
    # never produced a concluded record, so reading `scope` here happened to
    # give the right answer and nothing noticed until a second source did.
    upcoming, recent = fetch_inspire.split(records)

    # Drawn fresh from this morning's records, same as the lists below — never
    # cached from a previous run, so the two can never show different dates.
    # Rows fill from `upcoming` first (soonest at the top); `recent` only gets
    # whatever room is left, which is usually none — see conference_timeline's
    # docstring for why that is the right trade rather than an accident.
    max_rows = 14
    timeline = figures.conference_timeline(upcoming, recent, max_rows=max_rows, log=log)
    timeline_block = ""
    if timeline:
        n_up = min(len(upcoming), max_rows)
        n_rec = max(0, max_rows - len(upcoming))
        n_rec = min(n_rec, len(recent))
        # n_up can be 0 on a morning every fetcher fails but stale `recent`
        # records still remain — "The soonest 0 upcoming meetings" would be
        # the sentence a reader saw on a page like that, so the two clauses
        # are built to stand on their own rather than assuming n_up > 0.
        if n_up:
            caption = (f"The soonest {n_up} upcoming meeting{'' if n_up == 1 else 's'} "
                      f"(blue, amber if running right now)")
            if n_rec:
                caption += (f" and the {n_rec} most recently concluded "
                           f"(grey), filling the rows the upcoming ones leave")
        else:
            caption = (f"The {n_rec} most recently concluded "
                      f"meeting{'' if n_rec == 1 else 's'} (grey)")
        caption += (f". {len(upcoming)} upcoming and {len(recent)} recent "
                   f"meeting{'' if len(upcoming) + len(recent) == 1 else 's'} "
                   f"are tracked in full below.")
        timeline_block = f"""
<figure class="figure">
<h4>Timeline</h4>
<div class="timeline-scroll">
{timeline}
</div>
<p class="cap">{caption}</p>
</figure>
"""

    # Located fresh from this morning's `upcoming` records, same as the
    # timeline above — never cached, so the map can never show a conference
    # the lists no longer do. venue.locate_record runs the cascade (place
    # string, INSPIRE's structured address, Indico's address, the
    # conference's own page — see venue.py) and is asked here for the first
    # time on this site; a record it cannot place keeps its row in the
    # "Upcoming" list below and simply gets no dot, per the spec.
    located: list[tuple[dict, float, float]] = []
    for rec in upcoming:
        spot = venue.locate_record(rec, log)
        if spot is not None:
            lon, lat = spot
            located.append((rec, lon, lat))

    conf_map = figures.conference_map(located)
    map_block = ""
    if conf_map:
        n_located = len(located)
        n_missing = len(upcoming) - n_located
        map_caption = (f"{n_located} of {len(upcoming)} upcoming "
                       f"meeting{'' if len(upcoming) == 1 else 's'} placed "
                       f"on the map from a venue the source published")
        if n_missing:
            map_caption += (f"; the other {n_missing} stay in the list "
                            f"below without a dot rather than a guess.")
        else:
            map_caption += "."
        map_block = f"""
<figure class="figure confmap-figure">
<h4>Map</h4>
{conf_map}
<p class="cap">{map_caption}</p>
</figure>
"""

    # The two list blocks below split on physics DOMAIN, not tense — Antonio's
    # decision to follow his personal site's INSPIRE query rather than mix
    # ICHEP and Moriond into a "neutrino conferences" list. The timeline and
    # map above are drawn from `upcoming`/`located`, i.e. across both domains
    # at once: they exist to show the field's whole calendar and map at a
    # glance, and splitting THEM by domain too would mean two timelines and
    # two maps above a list already asked to make room for one of each.
    neutrino_records = conf_mod.split_scope(records, "neutrino")
    general_records = conf_mod.split_scope(records, "general")

    body = f"""<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Refreshed daily</p>
    <h1>Conferences and workshops</h1>
    <p class="lede">Conferences, workshops and schools in neutrino physics:
    what is coming, and what has just happened.</p>
  </div>
</section>

::: section

{AUTOGEN_SCRIPT.format(sources="conference indexers' APIs", stamp=stamp or _stamp())}

{timeline_block}
{map_block}
{_scope_block(neutrino_records, "Neutrino conferences",
             "Nothing announced in this window.")}

:::

::: section alt

{_scope_block(general_records, "General particle physics",
             "No flagship meeting is listed ahead in the window; the next "
             "editions may not be registered with INSPIRE yet.")}

<p class="small muted">The list is rebuilt each day from the conference
indexers rather than maintained by hand. Where a date cannot be confirmed from
the source, the entry is dropped rather than guessed; a venue is shown when the
source publishes one, and left blank when it does not. A meeting stays under
“Upcoming” until its last day is over. <b>Neutrino conferences</b> is the
field's own meetings; <b>General particle physics</b> is the flagship series
the field plans around — ICHEP, Moriond, LHCP and their neighbours — queried
from INSPIRE the same way.</p>

:::
"""
    _page(CONFERENCES_PAGE, CONF_FRONTMATTER, body)
    log.info("render: conferences.md — %d upcoming, %d recent "
             "(%d neutrino, %d general)",
             len(upcoming), len(recent), len(neutrino_records), len(general_records))
    return True
