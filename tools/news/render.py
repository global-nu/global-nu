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
        cats = ", ".join((rec.get("extra") or {}).get("categories", [])[:3])
        meta = " · ".join(x for x in (rec.get("authors"), cats, rec.get("date")) if x)
        out.append(f'<li><b>{_title(rec)}</b>'
                   f'<span>{_esc(meta)}</span>'
                   f'<span class="cites">{_links_row(rec)}</span></li>\n')
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
    <h1>Conferences and workshops</h1>
    <p class="lede">Conferences, workshops and schools in neutrino physics:
    what is coming, and what has just happened.</p>
  </div>
</section>

::: section

{AUTOGEN_SCRIPT.format(sources="conference indexers' APIs", stamp=stamp or _stamp())}

<div class="section-head"><h2>Upcoming</h2>
<p>{len(upcoming)} meeting{"" if len(upcoming) == 1 else "s"}</p></div>

{_conf_list(upcoming, "Nothing announced in this window.")}

:::

::: section alt

<div class="section-head"><h2>Recent</h2>
<p>{len(recent)} meeting{"" if len(recent) == 1 else "s"}</p></div>

{_conf_list(recent, "No meeting in this window has ended yet.")}

<p class="small muted">The list is rebuilt each day from the conference
indexers rather than maintained by hand. Where a date cannot be confirmed from
the source, the entry is dropped rather than guessed; a venue is shown when the
source publishes one, and left blank when it does not. A meeting stays under
“Upcoming” until its last day is over.</p>

:::
"""
    _page(CONFERENCES_PAGE, CONF_FRONTMATTER, body)
    log.info("render: conferences.md — %d upcoming, %d recent",
             len(upcoming), len(recent))
    return True
