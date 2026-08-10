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

from .common import CONFERENCES_PAGE, DIGEST_PAGE, NEWS_PAGE

EXPERIMENTAL_CATS = ("hep-ex", "nucl-ex", "physics.ins-det", "astro-ph.HE")

AUTOGEN = """<div class="autogen">
<span aria-hidden="true">⚠</span>
<div><b>This page is generated automatically with AI and may contain errors.</b>
<span class="stamp">Last successful update: {stamp}</span></div>
</div>"""


def _esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def _stamp(when: _dt.datetime | None = None) -> str:
    return (when or _dt.datetime.now()).strftime("%d %B %Y, %H:%M")


def _links_row(rec: dict) -> str:
    """arXiv / INSPIRE / DOI, whichever the record actually carries.

    Only links that came with the record are emitted: a DOI is never
    constructed from an arXiv id, because a paper that is not published yet
    would get a link that 404s.
    """
    order = [("arxiv", "arXiv"), ("inspire", "INSPIRE"), ("doi", "DOI"),
             ("journal", "Journal"), ("source", "Source")]
    seen, out = set(), []
    for key, label in order:
        url = (rec.get("links") or {}).get(key)
        if url and url not in seen:
            seen.add(url)
            out.append(f'<a href="{_esc(url)}">{label}</a>')
    if not out and rec.get("url"):
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
            parts.append(f'<span class="cite">{_esc(rec["title"][:90])} — {row}</span>')
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

    body = [f"""<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Neutrino news</p>
    <h1>What is happening in <i class="grad">neutrino physics</i></h1>
    <p class="lede">{_esc(narrative.get("overview") or
      "Experiments, results and recently published work from across the field.")}</p>
  </div>
</section>

::: section

""" + AUTOGEN.format(stamp=stamp or _stamp())]

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
                    '<p>recently published, with preprint, record and journal</p></div>\n')
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
        cats = ", ".join((rec.get("extra") or {}).get("categories", [])[:3])
        meta = " · ".join(x for x in (rec.get("authors"), cats, rec.get("date")) if x)
        out.append(f'<li><b>{_esc(rec["title"])}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="cites">{_links_row(rec)}</span></li>\n')
    out.append('</ul>\n')
    return "".join(out)


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
    <h1>Today on <i class="grad">arXiv</i></h1>
    <p class="lede">Neutrino preprints ranked by relevance to the field, with
    experimental and theoretical work kept apart.</p>
  </div>
</section>

::: section

{AUTOGEN.format(stamp=stamp or _stamp())}

<div class="section-head"><h2>Experimental</h2>
<p>{len(exp)} preprint{"" if len(exp) == 1 else "s"}</p></div>

{_digest_list(exp)}

:::

::: section alt

<div class="section-head"><h2>Theory</h2>
<p>{len(thy)} preprint{"" if len(thy) == 1 else "s"}</p></div>

{_digest_list(thy)}

<p class="small muted">Ranking is deterministic: the arXiv API is queried for
the configured categories, and each record is scored against a stated keyword
list. No model is involved in choosing what appears here.</p>

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
  venues and links — refreshed daily.
katex: false
---"""


def _conf_list(records: list[dict]) -> str:
    if not records:
        return '<p class="small muted">Nothing announced in this window.</p>\n'
    out = ['<ul class="list list--news">\n']
    for rec in records:
        extra = rec.get("extra") or {}
        meta = " · ".join(x for x in (extra.get("span"), extra.get("place")) if x)
        out.append(f'<li><b>{_esc(rec["title"])}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="cites"><a href="{_esc(rec["url"])}">Details</a></span></li>\n')
    out.append('</ul>\n')
    return "".join(out)


def conferences(records: list[dict], log: logging.Logger,
                stamp: str | None = None) -> bool:
    """Rewrite conferences.md, split into what is coming and what just ran."""
    if not records:
        log.warning("render: no conference records — conferences.md left untouched")
        return False

    upcoming = [r for r in records if (r.get("extra") or {}).get("scope") != "past"]
    recent = [r for r in records if (r.get("extra") or {}).get("scope") == "past"]

    body = f"""<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Refreshed daily</p>
    <h1>Where the field <i class="grad">meets</i></h1>
    <p class="lede">Conferences, workshops and schools in neutrino physics:
    what is coming, and what has just happened.</p>
  </div>
</section>

::: section

{AUTOGEN.format(stamp=stamp or _stamp())}

<div class="section-head"><h2>Upcoming</h2>
<p>{len(upcoming)} meeting{"" if len(upcoming) == 1 else "s"}</p></div>

{_conf_list(upcoming)}

:::

::: section alt

<div class="section-head"><h2>Recent</h2>
<p>{len(recent)} meeting{"" if len(recent) == 1 else "s"}</p></div>

{_conf_list(recent)}

<p class="small muted">The list is rebuilt each day from the conference
indexers rather than maintained by hand. Where a date or a venue cannot be
confirmed from the source, the entry is dropped rather than guessed.</p>

:::
"""
    _page(CONFERENCES_PAGE, CONF_FRONTMATTER, body)
    log.info("render: conferences.md — %d upcoming, %d recent",
             len(upcoming), len(recent))
    return True
