"""Keep every edition of the arXiv digest, filed by announcement date.

The digest page is overwritten every morning, so without this the previous
day simply ceases to exist. This module keeps the records that reached the
page and regenerates a page per day and per calendar month from them.

Why announcement date and not the day the page showed it: `window_hours` is
168, so each edition draws on the last seven days and consecutive editions
overlap almost entirely — 92 of 100 identifiers in the record cache appear on
more than one day. Keyed on the run, the archive would repeat itself seven
times over. Keyed on the record's own `date`, every paper is filed once, and a
late run is harmless: a paper announced on the 12th that first enters the
window on the 14th still lands under the 12th.

Nothing here ever deletes. Pages are regenerated from the store rather than
appended to, so any page can be rebuilt from scratch and cannot drift.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .common import ROOT, VAR

STORE = VAR / "archive.json"
CONTENT_DIR = ROOT / "site-src" / "content" / "digest"
DIGEST_MD = ROOT / "site-src" / "content" / "digest.md"
BEGIN, END = "<!-- ARCHIVE:BEGIN -->", "<!-- ARCHIVE:END -->"
RECENT_DAYS = 10


def load() -> dict[str, list[dict]]:
    """The store, or an empty one. A missing or unreadable file is empty.

    Never fatal: the archive is a record of the digest, and losing it must
    not stop the digest from being published today.
    """
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(store: dict[str, list[dict]]) -> None:
    """Write the store, sorted, so a run that changes nothing writes nothing."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    ordered = {day: store[day] for day in sorted(store)}
    STORE.write_text(json.dumps(ordered, indent=1, ensure_ascii=False,
                                sort_keys=False) + "\n", encoding="utf-8")


def merge(store: dict[str, list[dict]],
          records: list[dict]) -> dict[str, list[dict]]:
    """File records under their own dates, merging by arXiv identifier.

    Returns a new store; the argument is not modified, so a caller can
    compare before and after to see whether anything actually changed.

    A record without a usable `date` or `id` is dropped. Filing it under today
    would place a paper in a day it was not announced in, and this project
    leaves out what it cannot establish rather than guessing it.
    """
    out = {day: list(items) for day, items in store.items()}
    for record in records:
        day = str(record.get("date") or "")
        ident = record.get("id")
        if not day or not ident:
            continue
        bucket = out.setdefault(day, [])
        for i, existing in enumerate(bucket):
            if existing.get("id") == ident:
                bucket[i] = record        # improved fields replace the old copy
                break
        else:
            bucket.append(record)
    # Sorted by identifier so a day's page is byte-identical between runs that
    # saw the same papers in a different order — otherwise every run would
    # rewrite every page and the daily commit would be noise.
    for day in out:
        out[day] = sorted(out[day], key=lambda r: str(r.get("id")))
    return out


def _human_day(day: str) -> str:
    """"2026-08-12" -> "12 August 2026"."""
    return _dt.date.fromisoformat(day).strftime("%-d %B %Y")


def _human_month(month: str) -> str:
    """"2026-08" -> "August 2026"."""
    return _dt.date.fromisoformat(month + "-01").strftime("%B %Y")


def _front_matter(title: str, url: str, description: str) -> str:
    # The description is one line: build.py escapes it into a meta tag, and a
    # newline there would end the attribute early.
    return (f'---\ntitle: "{title}"\nurl: {url}\ndescription: >-\n'
            f'  {" ".join(description.split())}\nkatex: false\n---\n')


def day_markdown(day: str, records: list[dict], stamp: str) -> str:
    """One archived day, in the same markup the digest page itself uses."""
    from . import render

    n = len(records)
    human = _human_day(day)
    return (
        _front_matter(
            f"arXiv digest — {human}", f"digest/{day}.html",
            f"The neutrino preprints the arXiv digest carried for {human}: "
            f"{n} paper{'' if n == 1 else 's'}, announced that day.")
        + f"""
<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">arXiv digest · archive</p>
    <h1>{human}</h1>
    <p class="lede">The preprints announced on this day that reached the
    digest, kept as they were published.</p>
  </div>
</section>

::: section

{render.AUTOGEN_SCRIPT.format(sources="arXiv API", stamp=stamp)}

<div class="section-head"><h2>Preprints</h2>
<p>{n} preprint{'' if n == 1 else 's'}</p></div>

{render._digest_list(records)}

<p class="small muted"><a href="../digest.html">Back to the current
digest</a></p>

:::
"""
    )


def month_markdown(month: str, days: dict[str, list[dict]], stamp: str) -> str:
    """One calendar month, its days kept as sections, most recent first.

    Days stay visible rather than being flattened into one list: without them
    a reader cannot tell which day a paper belongs to, which is the one fact
    the archive exists to preserve.
    """
    from . import render

    human = _human_month(month)
    total = sum(len(v) for v in days.values())
    blocks = []
    for day in sorted(days, reverse=True):
        blocks.append(
            f'<div class="section-head"><h3>{_human_day(day)}</h3>'
            f'<p><a href="{day}.html">that day on its own page</a></p></div>\n\n'
            + render._digest_list(days[day]))

    return (
        _front_matter(
            f"arXiv digest — {human}", f"digest/{month}.html",
            f"Every neutrino preprint the arXiv digest carried in {human}: "
            f"{total} papers across {len(days)} days.")
        + f"""
<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">arXiv digest · archive</p>
    <h1>{human}</h1>
    <p class="lede">Every preprint the digest carried this month, by the day
    it was announced.</p>
  </div>
</section>

::: section

{render.AUTOGEN_SCRIPT.format(sources="arXiv API", stamp=stamp)}

{"".join(blocks)}

<p class="small muted"><a href="../digest.html">Back to the current
digest</a></p>

:::
"""
    )


def write_pages(store: dict[str, list[dict]], stamp: str) -> list[str]:
    """Regenerate every archive page from the store. Writes nothing else.

    Regenerated rather than appended to: a page that can only be extended can
    drift from its source and can never be rebuilt. Nothing is deleted — a URL
    that starts returning 404 is information lost.
    """
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    written = []

    for day, records in store.items():
        (CONTENT_DIR / f"{day}.md").write_text(
            day_markdown(day, records, stamp), encoding="utf-8")
        written.append(f"digest/{day}.html")

    months: dict[str, dict[str, list[dict]]] = {}
    for day, records in store.items():
        months.setdefault(day[:7], {})[day] = records
    for month, days in months.items():
        (CONTENT_DIR / f"{month}.md").write_text(
            month_markdown(month, days, stamp), encoding="utf-8")
        written.append(f"digest/{month}.html")

    return sorted(written)


def index_block(store: dict[str, list[dict]]) -> str:
    """The archive index: the most recent days by name, then the months.

    Ten days, not all of them: a list that grows without bound stops being an
    index. Everything older stays one click away through its month, and every
    day keeps its own page regardless — the ten is a rule about this list, not
    about what exists.
    """
    days = sorted(store, reverse=True)
    recent, older = days[:RECENT_DAYS], days[RECENT_DAYS:]

    rows = []
    for day in recent:
        n = len(store[day])
        rows.append(
            f'  <li><time datetime="{day}">{_human_day(day)}</time>'
            f'<a href="digest/{day}.html">Digest of {day}</a>'
            f'<span class="count">{n} paper{"" if n == 1 else "s"}</span></li>')

    months = sorted({day[:7] for day in older}, reverse=True)
    for month in months:
        n = sum(len(store[d]) for d in store if d.startswith(month))
        rows.append(
            f'  <li><time datetime="{month}">{_human_month(month)}</time>'
            f'<a href="digest/{month}.html">All of {_human_month(month)}</a>'
            f'<span class="count">{n} paper{"" if n == 1 else "s"}</span></li>')

    return '<ul class="archive">\n' + "\n".join(rows) + "\n</ul>"


def update_index(store: dict[str, list[dict]]) -> bool:
    """Rewrite the block between the markers in digest.md. True if it changed."""
    text = DIGEST_MD.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise RuntimeError(
            f"{DIGEST_MD} has no ARCHIVE markers — render.digest must emit them")
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END),
                 f"{BEGIN}\n{index_block(store)}\n{END}", text, flags=re.S)
    if new == text:
        return False
    DIGEST_MD.write_text(new, encoding="utf-8")
    return True
