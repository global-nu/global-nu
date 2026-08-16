# Digest Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep every edition of the arXiv digest, filed by the day each paper was announced, as one page per day plus one per calendar month, indexed from the digest page.

**Architecture:** A new `tools/news/archive.py` owns a JSON store at `var/news/archive.json` mapping announcement date → the records that reached the page, merged by arXiv identifier. Pages are regenerated from that store every run, never appended to, so they can always be rebuilt and cannot drift. The step runs inside the pipeline's existing `_safe` wrapper, after the digest renders, so an archive failure can never take down the run that publishes the site.

**Tech Stack:** Python 3 (stdlib + PyYAML, already in `.venv`), no new dependencies. Tests are standalone scripts run as `./.venv/bin/python3 tools/tests/test_X.py` — there is no pytest in this project.

**Spec:** `docs/superpowers/specs/2026-08-16-digest-archive-design.md`

## Global Constraints

- **File papers by their own `date`, never by the run date.** `window_hours` is 168, so the page shows the best of the last seven days and consecutive editions overlap by six sevenths — 92 of 100 cached identifiers appear on more than one day. Filing by run date would repeat almost everything.
- **Merge by arXiv identifier** (`record["id"]`, e.g. `"arxiv:2608.10062"`). Re-running a day must change nothing; a record whose fields improved replaces the older copy.
- **Archive what was published, not everything fetched** — the records handed to `render.digest`, which are `fetch_arxiv.top(arxiv, max_items)`.
- **Nothing is ever deleted.** No retention, and day pages persist rather than dissolving into the month page: a URL that starts returning 404 is information lost. This is why the publish step needs only `git add`, never `git add -A`.
- **No model is involved.** The digest's own banner says so and the archive must be able to say the same: no generated summaries.
- **The archive step must never break the run.** It goes inside `_safe`, like every other step.
- Tests are standalone scripts; the build is `./.venv/bin/python3 build.py`.
- Comments explain *why*, not *what*.

**Record shape**, verified from `var/news/cache/2026-08-15/arxiv.json`:

```python
{"id": "arxiv:2608.10062", "source": "arxiv",
 "title": "Archimedean Seesaw: …", "url": "https://arxiv.org/abs/2608.10062",
 "links": {"arxiv": "https://arxiv.org/abs/2608.10062", "pdf": "…"},
 "authors": "Tao Han, Alejandro Ibarra, Subhojit Roy et al.",
 "date": "2026-08-10", "summary": "…",
 "extra": {"categories": ["hep-ph", "hep-ex"], "score": 20, "hits": [...]}}
```

---

### Task 1: The store

**Files:**
- Create: `tools/news/archive.py`
- Test: `tools/tests/test_digest_archive.py`

**Interfaces:**
- Consumes: `tools.news.common.VAR` (the `var/news` path)
- Produces:
  - `archive.STORE: Path` — `var/news/archive.json`
  - `archive.load() -> dict[str, list[dict]]`
  - `archive.save(store: dict) -> None`
  - `archive.merge(store: dict, records: list[dict]) -> dict` — returns a new store with `records` filed under their own `date` and merged by `id`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_digest_archive.py`:

```python
#!/usr/bin/env python3
"""The digest archive files each paper once, under the day it was announced.

    ./.venv/bin/python3 tools/tests/test_digest_archive.py

The digest shows the best-scoring preprints of the last seven days, not of
today: 92 of 100 identifiers in the record cache appear on more than one day.
So an archive keyed on the run date would repeat almost everything, seven
times over. It is keyed on each record's own `date` instead, and merged by
arXiv identifier, which makes re-running a day a no-op and makes a late run
harmless — a paper announced on the 12th that first enters the window on the
14th still lands under the 12th.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import archive                           # noqa: E402

checks = 0
problems = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
        return
    problems.append(label)
    print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


def rec(ident: str, date: str, title: str = "A paper") -> dict:
    return {"id": ident, "date": date, "title": title,
            "url": f"https://arxiv.org/abs/{ident.split(':')[1]}",
            "links": {"arxiv": f"https://arxiv.org/abs/{ident.split(':')[1]}"},
            "authors": "A. Author", "summary": "…",
            "extra": {"categories": ["hep-ph"]}}


# --- filed by the record's own date, not by when it was seen -------------
store = archive.merge({}, [rec("arxiv:1", "2026-08-12"),
                           rec("arxiv:2", "2026-08-13")])
check("each paper lands under its own announcement date",
      sorted(store) == ["2026-08-12", "2026-08-13"], str(sorted(store)))
check("and one paper per day here", all(len(v) == 1 for v in store.values()))

# --- the seven-day window must not multiply anything ---------------------
for _ in range(3):
    store = archive.merge(store, [rec("arxiv:1", "2026-08-12")])
check("a paper seen on three later runs is still stored once",
      len(store["2026-08-12"]) == 1,
      f"{len(store['2026-08-12'])} copies — the window is leaking into the store")

# --- an improved record replaces the older copy --------------------------
store = archive.merge(store, [rec("arxiv:1", "2026-08-12", title="A better title")])
check("a record whose fields improved is updated in place",
      store["2026-08-12"][0]["title"] == "A better title",
      store["2026-08-12"][0]["title"])
check("and still only once", len(store["2026-08-12"]) == 1)

# --- a record with no usable date is refused, not guessed ----------------
before = dict(store)
store = archive.merge(store, [{"id": "arxiv:9", "title": "No date"}])
check("a record with no date is dropped rather than filed under today",
      store == before,
      "guessing a date would put a paper in a day it was not announced in")

# --- days keep a stable order inside themselves --------------------------
many = archive.merge({}, [rec("arxiv:b", "2026-08-12"), rec("arxiv:a", "2026-08-12")])
again = archive.merge({}, [rec("arxiv:a", "2026-08-12"), rec("arxiv:b", "2026-08-12")])
check("a day's records are ordered deterministically",
      [r["id"] for r in many["2026-08-12"]] == [r["id"] for r in again["2026-08-12"]],
      "an unstable order would rewrite the archive pages every single run")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the store files each paper once, by its own date")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: FAIL with `ImportError: cannot import name 'archive' from 'tools.news'`

- [ ] **Step 3: Write the implementation**

Create `tools/news/archive.py`:

```python
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

import json
from pathlib import Path

from .common import VAR

STORE = VAR / "archive.json"


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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: PASS, all checks ok.

- [ ] **Step 5: Commit**

```bash
git add tools/news/archive.py tools/tests/test_digest_archive.py
git commit -m "Keep the digest's papers, filed by the day each was announced"
```

---

### Task 2: The day and month pages

**Files:**
- Modify: `tools/news/archive.py`
- Modify: `tools/tests/test_digest_archive.py`

**Interfaces:**
- Consumes: `archive.load/save/merge` from Task 1; `tools.news.render._digest_list(records) -> str`; `tools.news.render.AUTOGEN_SCRIPT`
- Produces:
  - `archive.CONTENT_DIR: Path` — `site-src/content/digest`
  - `archive.day_markdown(day: str, records: list[dict], stamp: str) -> str`
  - `archive.month_markdown(month: str, days: dict[str, list[dict]], stamp: str) -> str`
  - `archive.write_pages(store: dict, stamp: str) -> list[str]` — returns the urls written

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_digest_archive.py`, before the final `print()`:

```python
# --- the pages ------------------------------------------------------------
import re                                                # noqa: E402

STAMP = "16 August 2026, 07:32 CEST"
day_md = archive.day_markdown("2026-08-12",
                              [rec("arxiv:1", "2026-08-12", "First"),
                               rec("arxiv:2", "2026-08-12", "Second")], STAMP)

check("the day page declares its own url",
      "url: digest/2026-08-12.html" in day_md, day_md[:200])
check("the day page's title names the day in words",
      "12 August 2026" in day_md, day_md[:200])
check("the day page lists both papers",
      "First" in day_md and "Second" in day_md)
check("the day page says it was generated by a script, with no model",
      "No model is involved" in day_md,
      "the main digest says this; an archive of it must be able to say it too")
check("the day page carries its own count",
      "2 preprints" in day_md, day_md[:400])

month_md = archive.month_markdown(
    "2026-08",
    {"2026-08-13": [rec("arxiv:3", "2026-08-13", "Later")],
     "2026-08-12": [rec("arxiv:1", "2026-08-12", "Earlier")]}, STAMP)

check("the month page declares its own url",
      "url: digest/2026-08.html" in month_md)
check("the month page names the month",
      "August 2026" in month_md, month_md[:200])
check("the month page keeps the days visible as sections",
      "13 August" in month_md and "12 August" in month_md,
      "a flat month loses which day a paper belongs to")
check("the month page runs most recent first",
      month_md.index("13 August") < month_md.index("12 August"))
check("the month page contains every paper of its days",
      "Later" in month_md and "Earlier" in month_md)

# A month page must never reach outside its own month: a paper filed in
# September appearing on the August page would be a silent factual error.
check("month_markdown is given only its own days",
      "2026-09" not in month_md)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: FAIL with `AttributeError: module 'tools.news.archive' has no attribute 'day_markdown'`

- [ ] **Step 3: Write the implementation**

Add to `tools/news/archive.py`:

```python
import datetime as _dt

from .common import ROOT

CONTENT_DIR = ROOT / "site-src" / "content" / "digest"


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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/news/archive.py tools/tests/test_digest_archive.py
git commit -m "Render an archive page per day and per calendar month"
```

---

### Task 3: The Archive block on the digest page

**Files:**
- Modify: `tools/news/render.py` (the `digest()` template)
- Modify: `tools/news/archive.py`
- Modify: `tools/tests/test_digest_archive.py`

**Interfaces:**
- Consumes: `archive.write_pages` from Task 2
- Produces: `archive.update_index(store: dict) -> bool` — rewrites the block between the markers in `site-src/content/digest.md`, returns whether the file changed

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_digest_archive.py`, before the final `print()`:

```python
# --- the index block on the digest page -----------------------------------
block = archive.index_block({
    f"2026-08-{d:02d}": [rec(f"arxiv:{d}", f"2026-08-{d:02d}")]
    for d in range(1, 15)})

check("the index lists the ten most recent days by name",
      block.count('href="digest/2026-08-') >= 10, block[:300])
check("the newest day comes first",
      block.index("2026-08-14") < block.index("2026-08-13"))
check("older days are reached through their month, not listed one by one",
      'href="digest/2026-08.html"' in block,
      "fourteen days with no month link would grow without bound")
check("each listed day shows how many papers it holds",
      "1 paper" in block, block[:400])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: FAIL — `module 'tools.news.archive' has no attribute 'index_block'`

- [ ] **Step 3: Add the markers to the digest template**

In `tools/news/render.py`, inside `digest()`'s body string, immediately before the final closing `:::` of the last section, insert:

```
<div class="section-head"><h2>Archive</h2>
<p>Every edition, by the day each paper was announced.</p></div>

<!-- ARCHIVE:BEGIN -->
<!-- ARCHIVE:END -->
```

The markers are emitted by `render.digest` and filled by `archive.update_index`
because two different steps write this one file; without an explicit seam the
second writer would have to parse the first one's output.

- [ ] **Step 4: Write the implementation**

Add to `tools/news/archive.py`:

```python
import re

DIGEST_MD = ROOT / "site-src" / "content" / "digest.md"
BEGIN, END = "<!-- ARCHIVE:BEGIN -->", "<!-- ARCHIVE:END -->"
RECENT_DAYS = 10


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
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/news/render.py tools/news/archive.py tools/tests/test_digest_archive.py
git commit -m "Index the archive from the digest page, between explicit markers"
```

---

### Task 4: Run it in the pipeline, and let the job commit it

**Files:**
- Modify: `tools/news/pipeline.py` (the render block around line 170; `PUBLISHED_BY_JOB` around line 214)
- Modify: `tools/tests/test_digest_archive.py`

**Interfaces:**
- Consumes: `archive.load/merge/save/write_pages/update_index`

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_digest_archive.py`, before the final `print()`:

```python
# --- the daily job must be able to commit what it just wrote --------------
from tools.news import pipeline                          # noqa: E402

paths = " ".join(pipeline.PUBLISHED_BY_JOB)
check("the publish list covers the archive's source pages",
      "site-src/content/digest" in paths and "digest.md" in paths,
      "a page the job writes but cannot commit leaves the tree dirty, and the "
      "next git pull --rebase refuses — the site then stops updating silently")
check("and their built output",
      "site/digest" in paths, paths)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: FAIL on the archive source pages — the list has `site-src/content/digest.md` but not the directory.

- [ ] **Step 3: Extend the publish list**

In `tools/news/pipeline.py`, add two entries to `PUBLISHED_BY_JOB`:

```python
    "site-src/content/digest", "site/digest",
```

and extend the comment above it to say why a directory appears in a list of
files: the archive writes a page per day, so the names cannot be enumerated in
advance. Note also that the archive never deletes, so a plain `git add` of the
directory is sufficient and `git add -A` — which would also stage anything else
that happened to be removed — is deliberately not used.

- [ ] **Step 4: Run the archive after the digest renders**

In `tools/news/pipeline.py`, the digest is rendered by

```python
    if _safe("render digest",
            lambda: render.digest(
                fetch_arxiv.top(arxiv, int(cfg["arxiv"].get("max_items", 12))), log),
            log, False):
        wrote.append("digest")
```

Hoist the published selection into a variable so the archive files exactly what
the page showed, then add the archive step immediately after the three render
calls and before the build:

```python
    published = fetch_arxiv.top(arxiv, int(cfg["arxiv"].get("max_items", 12)))
    if _safe("render digest", lambda: render.digest(published, log), log, False):
        wrote.append("digest")
```

and, after `render news`:

```python
    # The archive keeps what the digest published, filed by each paper's own
    # announcement date. Inside _safe like every other step: an archive that
    # fails must cost the archive, not the day's digest.
    def _archive() -> bool:
        store = archive.merge(archive.load(), published)
        archive.save(store)
        archive.write_pages(store, render._stamp())
        archive.update_index(store)
        return True

    _safe("archive digest", _archive, log, False)
```

Add `archive` to the `from . import …` line at the top of the module, beside
`render`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_digest_archive.py`
Expected: PASS.

- [ ] **Step 6: Run it for real, from cache, and look at what appeared**

```bash
./update-daily --from-cache --no-ai
ls site-src/content/digest/ | head
./.venv/bin/python3 build.py
ls site/digest/ | head
```

Expected: one `.md` per archived day plus one per month, and the same as
`.html` under `site/digest/`. Confirm `git status --short` shows them as
untracked or added — not as a dirty tree the job could not commit.

- [ ] **Step 7: Commit**

```bash
git add tools/news/pipeline.py tools/tests/test_digest_archive.py \
        site-src/content/digest site/digest site-src/content/digest.md \
        var/news/archive.json
git commit -m "Archive the digest on every run, and let the job publish it"
```

Note: `var/` is gitignored, so `var/news/archive.json` will simply not be
added — that is correct and expected; the store is local state, and the pages
regenerated from it are what ships.

---

### Task 5: Look at it

**Files:**
- Modify: whatever the screenshots show is wrong

- [ ] **Step 1: Shoot the new pages**

```bash
mkdir -p /tmp/arch && ./.venv/bin/python3 - <<'PY'
from playwright.sync_api import sync_playwright
import pathlib, glob, os
root = pathlib.Path("site").resolve()
day = sorted(glob.glob("site/digest/2026-*-*.html"))[-1]
month = sorted(glob.glob("site/digest/2026-??.html"))[-1]
with sync_playwright() as p:
    b = p.chromium.launch()
    for theme in ("light", "dark"):
        for w in (375, 1280):
            pg = b.new_page(viewport={"width": w, "height": 1000})
            for path in (day, month, "site/digest.html"):
                pg.goto("file://" + str(pathlib.Path(path).resolve()))
                pg.evaluate(f"localStorage.setItem('gnu-theme','{theme}')")
                pg.reload(); pg.wait_for_timeout(400)
                name = os.path.basename(path).replace(".html", "")
                pg.screenshot(path=f"/tmp/arch/{name}-{theme}-{w}.png",
                              full_page=True)
            pg.close()
    b.close()
print("screenshots in /tmp/arch")
PY
```

- [ ] **Step 2: Read every screenshot**

Look at all twelve. The things most likely to be wrong:

1. The archive list on `digest.html` unstyled, because `.archive` has no rules in this site's CSS (it is Antonio's other site that has them).
2. A day page's "Back to the current digest" link resolving to the wrong place from a sub-directory.
3. The month page enormous at 375 px, with no way to reach a single day.
4. The `<h3>` day headings inside the month page rendering at the same weight as the `<h2>`s.
5. Assets or the theme toggle broken on a sub-directory page — the `base` prefix.

- [ ] **Step 3: Style `.archive`, fix what else the screenshots show, and re-shoot**

Do not declare this done on a screenshot taken before the last edit.

- [ ] **Step 4: Run the whole suite**

```bash
for t in tools/tests/test_*.py; do echo "--- $t"; ./.venv/bin/python3 "$t" || echo "FAILED $t"; done
for t in tools/tests/test_*.js; do echo "--- $t"; node "$t" || echo "FAILED $t"; done
```

Expected: every one passes. `test_built_pages.py` matters here — it catches
unconverted Markdown, which a new generated page is exactly the sort of thing
to ship.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "The digest archive, seen in a browser before shipping"
```

Do not push and do not run `git subtree`.

---

## Self-review

**Spec coverage.** Store and merge-by-identifier → Task 1; day and month pages,
with days kept visible inside the month → Task 2; the Archive block between
markers → Task 3; the `_safe` placement and `PUBLISHED_BY_JOB` → Task 4; the
browser pass → Task 5. The spec's out-of-scope list is respected: nothing
changes `window_hours` or the main digest's contents, no model writes anything,
no archive search, no retention.

**Placeholders.** None. Every code step carries its code; every test step
carries its assertions and the command that runs it.

**Type consistency.** `merge(store, records) -> dict` is defined in Task 1 and
called in Task 4. `day_markdown(day, records, stamp)`,
`month_markdown(month, days, stamp)` and `write_pages(store, stamp)` are
defined in Task 2 and only `write_pages` is called later. `index_block(store)`
and `update_index(store)` are defined in Task 3, and Task 3's test calls
`index_block` directly. `_human_day` and `_human_month` are defined in Task 2
and reused in Task 3.

**One thing to watch.** Task 2 imports `render._digest_list` and
`render.AUTOGEN_SCRIPT`, both private-by-convention. That is deliberate — an
archive entry must look exactly like a digest entry, and a second copy of that
markup would drift the first time one of them changed. The import is inside the
functions rather than at module scope because `render` imports from `common`
and a module-level cycle is easy to create here by accident.
