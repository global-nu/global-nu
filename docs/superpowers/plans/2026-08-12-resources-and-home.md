# Resources and Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `site-src/data/experiments.yaml` the only place an experiment is named, grow it from 13 entries to roughly 45 verified ones, turn the world map into something that can be navigated, collapse seven-hundred-name credits, and replace the home page's invented hero figure with the measured parameter ranges.

**Architecture:** A new library module `tools/experiments.py` owns loading, validating and ordering the experiment records. Both the map writer and a new tiles writer import it, so the two renderings cannot disagree about what exists or in what order. The map gains a companion `map.js` that operates on `data-` attributes the SVG writer emits; without JavaScript the SVG still renders and reads. Figures stay generated Python-side into `site-src/data/figures/`, picked up by build.py's existing `<!--include:name-->` mechanism.

**Tech Stack:** Python 3 (stdlib + PyYAML), vanilla ES5-flavoured JavaScript with no dependencies, SVG generated as text, jsdom for JS tests, the project's own `.venv`.

## Global Constraints

Copied from the spec and from `PROMPT_GLOBAL_NU.md`; every task's requirements implicitly include this section.

- **No physical or factual value from memory.** Every `status`, date and URL is taken from a primary source (the collaboration's own site, or the paper of its final dataset) and the source is recorded in the entry. Unverifiable ⇒ the field is omitted and the page prints nothing.
- **No CDN, no external runtime request.** Everything self-hosted.
- **No hard-coded colours.** CSS custom properties only, and any new colour must be added to `PAIRS` in `tools/tests/test_theme.js` or it is untested.
- **`site/` is never edited by hand.** It is build output; `python3 build.py` regenerates it.
- **Nothing embargoed leaves `drafts/`.** `tools/tests/test_no_draft_leak.py` must keep passing after every commit.
- **No working notes on public pages.** No "TODO", no "scaffold", no `site-src/` paths.
- Python is run as `./.venv/bin/python3`, never bare `python3`.
- Commit messages: prose that says what changed and why, in the register of the existing log. No `feat:`/`fix:` prefixes — this repository does not use them.

## Deviation from the spec, to be confirmed

The spec says IceCube returns to the map because "the projection is extended south". Implementing it that way means extending an equirectangular frame to −90°, where the South Pole is stretched into a line as wide as the world and Antarctica becomes an empty band about a sixth of the map's height. Task 4 instead adds a **small azimuthal south-polar inset** in the map's corner, which puts IceCube on the map properly rather than at the bottom edge of a band of white. Same goal, better cartography. Flag this to Antonio when Task 4 is reviewed.

## File Structure

| File | Responsibility |
|---|---|
| `tools/experiments.py` | **new** — load, validate, group and order experiment records. No output, no side effects. |
| `tools/make_experiments.py` | **new** — render the Resources tiles to `site-src/data/figures/experiments-tiles.html`. |
| `tools/make_map.py` | modify — import ordering from `tools/experiments.py`; group co-located sites; emit `data-` attributes; add the polar inset. |
| `tools/make_figures.py` | modify — add `hero_ranges_svg()`, write `ranges-hero.svg`. |
| `tools/fetch_commons_images.py` | modify — collapse author fields. |
| `site-src/data/experiments.yaml` | modify — new fields, ~45 entries. |
| `site-src/content/resources.md` | modify — hand-written tiles and the gallery figure removed, replaced by includes. |
| `site-src/content/index.md` | modify — invented SVG replaced by `<!--include:ranges-hero-->`. |
| `site-src/assets/js/map.js` | **new** — zoom, pan, filter, marker card. |
| `site-src/assets/css/site.css` | modify — map controls and card; `.shots`/`.shot` rules retargeted to the card. |
| `tools/tests/test_experiments.py` | **new** — schema, ordering, and the bidirectional drift check. |
| `tools/tests/test_map.js` | **new** — jsdom coverage of `map.js`. |
| `tools/tests/test_release_numbers.py` | modify — cover the hero figure's values. |

---

### Task 1: Credits that read like credits

The JUNO photograph's credit is Commons' `Artist` field verbatim: the collaboration's entire author list, some seven hundred names, printed under the picture.

**Files:**
- Modify: `tools/fetch_commons_images.py` (add `short_author()`, call it where `author` is stored, line ~108)
- Test: `tools/tests/test_experiments.py` — no; this one gets its own check inside `tools/fetch_commons_images.py`'s module test below
- Create: `tools/tests/test_credits.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `short_author(value: str) -> str` in `tools.fetch_commons_images`, importable by tests and by Task 5's card renderer.

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_credits.py`:

```python
#!/usr/bin/env python3
"""A credit line must credit, not enumerate.

    ./.venv/bin/python3 tools/tests/test_credits.py

Commons stores whatever the uploader put in the Artist field. For
File:JUNO Detector with labels.jpg that is the collaboration's entire author
list, and it was printed under the photograph. The licence asks for
attribution in a reasonable manner; seven hundred names in a caption is not
reasonable, and the full field stays in photos.yaml with a link to the file's
page on Commons, which is where attribution is properly discharged.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.fetch_commons_images import short_author   # noqa: E402

fail: list[str] = []


def check(label: str, got: str, want: str) -> None:
    if got == want:
        print(f"  ok   {label}")
    else:
        fail.append(label)
        print(f"  FAIL {label}\n         got:  {got!r}\n         want: {want!r}")


check("a collaboration keeps its name and drops its roster",
      short_author("JUNO Collaboration: Angel Abusleme, Thomas Adam, "
                   "Shakeel Ahmad, Rizwan Ahmed, Sebastiano Aiello"),
      "JUNO Collaboration")

check("a collaboration named without a colon is kept whole",
      short_author("Borexino Collaboration"),
      "Borexino Collaboration")

check("one photographer is left alone",
      short_author("Christopher Michel"),
      "Christopher Michel")

check("two names are left alone",
      short_author("Fermilab, Reidar Hahn"),
      "Fermilab, Reidar Hahn")

check("more than three names collapse to the first",
      short_author("Ann Alpha, Ben Beta, Carl Gamma, Dana Delta"),
      "Ann Alpha et al.")

check("an empty field stays empty",
      short_author(""),
      "")

print()
if fail:
    print(f"{len(fail)} check(s) failed")
    sys.exit(1)
print(f"all {6} checks pass — credits name a source, not a roster")
```

- [ ] **Step 2: Run it and watch it fail**

```
./.venv/bin/python3 tools/tests/test_credits.py
```

Expected: `ImportError: cannot import name 'short_author'`.

- [ ] **Step 3: Implement `short_author`**

In `tools/fetch_commons_images.py`, beside `clean()`:

```python
def short_author(value: str) -> str:
    """Credit the source, not the roster.

    Commons' Artist field is free text. For a collaboration upload it is
    routinely the paper's entire author list — seven hundred names for JUNO,
    which is what shipped under the photograph. CC BY asks for attribution
    "in a reasonable manner for the medium"; naming the collaboration and
    linking the file's page on Commons is the reasonable manner for a caption,
    and photos.yaml keeps the field intact.
    """
    text = (value or "").strip()
    if not text:
        return ""
    head = text.split(":", 1)[0].strip()
    if head.lower().endswith(("collaboration", "collaborations")):
        return head
    names = [n.strip() for n in text.split(",") if n.strip()]
    if len(names) > 3:
        return f"{names[0]} et al."
    return text
```

- [ ] **Step 4: Run it and watch it pass**

```
./.venv/bin/python3 tools/tests/test_credits.py
```

Expected: `all 6 checks pass`.

- [ ] **Step 5: Apply it where the credit is built**

In the `search()` function, change the manifest line so the shortened form is stored beside the full one — the full field must survive for the Commons link to remain honest:

```python
            "author": clean((meta.get("Artist") or {}).get("value", "")),
            "author_short": short_author(clean((meta.get("Artist") or {}).get("value", ""))),
```

Then regenerate the manifest and the rendered credits:

```
./.venv/bin/python3 tools/fetch_commons_images.py
```

If the network is unavailable, edit `site-src/data/photos.yaml` by hand to add `author_short` to each of the five entries, computed by running `short_author` on the stored `author`. Do not invent a value.

- [ ] **Step 6: Commit**

```bash
git add tools/fetch_commons_images.py tools/tests/test_credits.py site-src/data/photos.yaml
git commit -m "$(cat <<'EOF'
A credit line should credit, not enumerate

Commons' Artist field is free text, and for File:JUNO Detector with labels.jpg
the uploader put the collaboration's entire author list in it. All seven
hundred names were printed under the photograph, because the fetcher copied
the field verbatim.

An author field naming a collaboration now collapses to the collaboration;
one naming more than three people collapses to the first of them. The full
field stays in photos.yaml and the link to the file's page on Commons stays
under every photograph, which is where CC BY attribution is properly
discharged.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: One source for the experiments

The tiles on `resources.md` are hand-written HTML duplicating `experiments.yaml`. Prove the machinery with today's 13 entries before entering forty more.

**Files:**
- Create: `tools/experiments.py`
- Create: `tools/make_experiments.py`
- Create: `tools/tests/test_experiments.py`
- Modify: `tools/make_map.py` (import loading from the library instead of reading the YAML itself)
- Modify: `site-src/data/experiments.yaml` (add `role`, `status`, `rank`, `source` to the 13 existing entries)
- Modify: `site-src/content/resources.md:50-94` (delete the four `<article class="tile">` blocks, insert the include)

**Interfaces:**
- Consumes: nothing.
- Produces, in `tools.experiments`:
  - `ROLES: list[tuple[str, str]]` — `(role_key, heading)` in display order
  - `STATUSES: tuple[str, ...]` — `("running", "completed", "construction", "proposed")`
  - `load() -> list[dict]` — every record, validated, raising `SystemExit` on a schema breach
  - `ordered() -> list[tuple[str, str, list[dict]]]` — `(role_key, heading, records)` grouped and sorted by `rank`
  - `label(record) -> str` — the one-line description the tile and the map card both print

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_experiments.py`:

```python
#!/usr/bin/env python3
"""The experiment list must exist once, and the pages must agree with it.

    ./.venv/bin/python3 tools/tests/test_experiments.py

Resources used to carry the list twice: once in experiments.yaml for the map,
once as hand-written tiles in resources.md. The YAML's header asked the two to
agree; nothing made them, and they drifted into thirteen entries with Daya Bay
and RENO missing while Double Chooz was present.

Four checks:
  1. every record satisfies the schema
  2. rank is unique within a role, so the order is total and not accidental
  3. every name in the YAML reaches the built resources.html
  4. every experiment name on the built page comes from the YAML
Checks 3 and 4 are the same check in both directions on purpose: one catches a
name that was never rendered, the other catches a name hand-typed onto the
page.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import experiments                        # noqa: E402

PAGE = ROOT / "site" / "resources.html"

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


records = experiments.load()

# 1. schema
roles = {k for k, _ in experiments.ROLES}
bad = [f'{r.get("name", "?")}: {why}'
       for r in records
       for why in [
           None if r.get("role") in roles else f'unknown role {r.get("role")!r}',
           None if r.get("status") in experiments.STATUSES
           else f'unknown status {r.get("status")!r}',
           None if isinstance(r.get("rank"), int) else "rank is not an integer",
           None if r.get("url") else "no url",
           None if r.get("source") else "no source recorded for its status",
       ] if why]
check("every record satisfies the schema", not bad, "; ".join(bad[:5]))

# 2. rank unique within a role
dupes = []
for key, _heading, group in experiments.ordered():
    seen: dict[int, str] = {}
    for r in group:
        if r["rank"] in seen:
            dupes.append(f'{key}: {seen[r["rank"]]} and {r["name"]} share rank {r["rank"]}')
        seen[r["rank"]] = r["name"]
check("rank is unique within each role", not dupes, "; ".join(dupes[:5]))

# 3 & 4. the page and the YAML agree, both ways
if not PAGE.exists():
    check("resources.html exists", False, "run ./.venv/bin/python3 build.py first")
else:
    html = PAGE.read_text(encoding="utf-8")
    tiles = re.findall(r'data-experiment="([^"]+)"', html)
    from_yaml = {r["name"] for r in records}
    on_page = set(tiles)

    missing = sorted(from_yaml - on_page)
    check("every experiment in the YAML reaches the page", not missing,
          f"absent from resources.html: {', '.join(missing[:8])}")

    extra = sorted(on_page - from_yaml)
    check("every experiment on the page comes from the YAML", not extra,
          f"on the page but not in the YAML: {', '.join(extra[:8])}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — {len(records)} experiments, named once")
```

- [ ] **Step 2: Run it and watch it fail**

```
./.venv/bin/python3 tools/tests/test_experiments.py
```

Expected: `ModuleNotFoundError: No module named 'tools.experiments'`.

- [ ] **Step 3: Write the library**

Create `tools/experiments.py`:

```python
#!/usr/bin/env python3
"""The experiment list, loaded once and ordered once.

Both the world map and the tiles on the Resources page are drawn from this
module, so the two cannot name different experiments or put them in different
orders. Before it existed the list lived twice — in experiments.yaml and as
hand-written HTML — and every addition cost two edits, which is why the list
stayed at thirteen entries with Daya Bay absent.

The ordering is a claim, not a preference: within a role, experiments are
ranked by their weight in the current global fit, and `rank` records where
each one sits. The claim is written down so it can be argued with.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "experiments.yaml"

# Display order of the groups, and the heading each one gets.
ROLES: list[tuple[str, str]] = [
    ("theta13",     "Reactor · θ₁₃"),
    ("theta12_dm2", "Reactor · θ₁₂ and δm²"),
    ("solar",       "Solar neutrinos"),
    ("lbl",         "Long-baseline accelerator"),
    ("atmospheric", "Atmospheric neutrinos"),
    ("sterile",     "Short baseline and sterile searches"),
    ("mass",        "Absolute mass"),
    ("0nubb",       "Neutrinoless double-beta decay"),
]

STATUSES: tuple[str, ...] = ("running", "completed", "construction", "proposed")

# How a status is written on the page. Absent status prints nothing at all,
# which is the honest outcome when it could not be established.
STATUS_LABEL = {
    "running":      "taking data",
    "completed":    "completed",
    "construction": "under construction",
    "proposed":     "proposed",
}


def load() -> list[dict]:
    """Every record in the file. Raises SystemExit on a malformed file."""
    raw = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    records = (raw or {}).get("experiments")
    if not records:
        sys.exit(f"{DATA} holds no experiments")
    for r in records:
        if not r.get("name"):
            sys.exit(f"{DATA}: a record has no name")
    return records


def ordered() -> list[tuple[str, str, list[dict]]]:
    """(role, heading, records) — grouped in ROLES order, ranked within each."""
    out = []
    records = load()
    for key, heading in ROLES:
        group = sorted((r for r in records if r.get("role") == key),
                       key=lambda r: (r.get("rank", 10_000), r["name"]))
        if group:
            out.append((key, heading, group))
    return out


def label(record: dict) -> str:
    """The one line printed under a name, on the tile and in the map card."""
    bits = [b for b in (record.get("place") or
                        f'{record.get("city", "")}, {record.get("country", "")}',
                        record.get("note"),
                        STATUS_LABEL.get(record.get("status", ""))) if b]
    return " · ".join(bits)
```

- [ ] **Step 4: Write the tiles renderer**

Create `tools/make_experiments.py`:

```python
#!/usr/bin/env python3
"""Render the Resources tiles from site-src/data/experiments.yaml.

    ./.venv/bin/python3 tools/make_experiments.py

Output is an include, picked up by build.py's <!--include:experiments-tiles-->.
Nothing here decides what exists or in what order — that is tools/experiments.py,
which the map reads too.
"""
from __future__ import annotations

import html
from pathlib import Path

from tools import experiments

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-src" / "data" / "figures" / "experiments-tiles.html"


def tiles_html() -> str:
    parts = ['<div class="tiles reveal">']
    for _key, heading, group in experiments.ordered():
        parts.append('<article class="tile">')
        parts.append(f'<h3>{html.escape(heading)}</h3>')
        parts.append('<ul class="list">')
        for r in group:
            name = html.escape(r["name"])
            parts.append(
                f'<li data-experiment="{name}">'
                f'<b><a href="{html.escape(r["url"])}">{name}</a></b>'
                f'<span>{html.escape(experiments.label(r))}</span></li>')
        parts.append("</ul></article>")
    parts.append("</div>")
    return "\n".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tiles_html(), encoding="utf-8")
    total = sum(len(g) for _k, _h, g in experiments.ordered())
    print(f"tiles: {total} experiments -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
```

Note the `data-experiment="…"` attribute: it is what the drift test in Step 1 counts, and what Task 5's card lookup keys on.

- [ ] **Step 5: Give the 13 existing records their new fields**

Edit `site-src/data/experiments.yaml`. Extend the header comment to state the ordering criterion, then add `role`, `status`, `rank` and `source` to each existing entry. Add to the header:

```yaml
# Ordering. Entries are grouped by `role` — what the experiment constrains in
# a global fit — and ranked within a group by its weight in the current fit:
# the datasets that dominate a constraint come first. `rank` records that
# position so the order is a claim on the page rather than a preference in
# somebody's head.
#
# `status` is a statement of fact about a real collaboration and follows the
# project's first rule: it is taken from the source named in `source` — the
# collaboration's own page, or the paper of its final dataset — and never from
# recollection. An experiment whose status cannot be established carries no
# `status` field, and the page then prints nothing rather than a guess.
```

Do **not** invent statuses in this step. For each of the 13, open its `url`, read what the collaboration says, and record it. If the site does not say, leave `status` out and put the URL you checked in `source` anyway.

- [ ] **Step 6: Teach build.py nothing, and resources.md everything**

`build.py` already resolves `<!--include:experiments-tiles-->` because `_include` looks for `<name>.html` in `site-src/data/figures/`. No change to `build.py` is needed — verify this rather than assuming it.

In `site-src/content/resources.md`, delete lines 50–94 (the `<div class="tiles reveal">` block and its four `<article>` children) and put in their place:

```markdown
<!--include:experiments-tiles-->

<p class="small muted" style="margin-top:1.4rem">Grouped by what each
experiment constrains, and ordered within a group by its weight in the
current global fit. Status is taken from each collaboration's own pages;
where it could not be established, none is shown.</p>
```

- [ ] **Step 7: Build and run the test**

```
./.venv/bin/python3 tools/make_experiments.py
./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_experiments.py
```

Expected: `all 4 checks pass — 13 experiments, named once`.

- [ ] **Step 8: Point make_map.py at the library**

In `tools/make_map.py`, replace the direct YAML read

```python
    entries = yaml.safe_load(DATA.read_text(encoding="utf-8"))["experiments"]
```

with

```python
    entries = experiments.load()
```

adding `from tools import experiments` to the imports and removing the now-unused `yaml` import and `DATA` constant. Then:

```
./.venv/bin/python3 tools/make_map.py
./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_experiments.py
```

Expected: the map still reports `map: 13 experiments placed`, and the test still passes.

- [ ] **Step 9: Commit**

```bash
git add tools/experiments.py tools/make_experiments.py tools/make_map.py \
        tools/tests/test_experiments.py site-src/data/experiments.yaml \
        site-src/content/resources.md site-src/data/figures/experiments-tiles.html site/
git commit -m "$(cat <<'EOF'
The experiment list stops existing twice

Resources named its experiments in two places: experiments.yaml, which the map
reads, and hand-written tiles in resources.md. The YAML's own header asked the
two to agree so they "cannot drift"; nothing made them, and the cost of every
addition being two edits is why the list stayed at thirteen entries with
Double Chooz present and Daya Bay and RENO absent.

tools/experiments.py now owns loading and ordering, the map and a new tiles
renderer both read it, and the tiles in resources.md are generated. The
records gain role, status, rank and source: what the experiment constrains,
what state it is in, where it sits in its group, and where that was checked.

The new test compares the YAML and the built page in both directions — one
direction catches a record that never rendered, the other catches a name typed
onto the page by hand.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Forty-five experiments, each one checked

Pure compilation. No code changes. The machinery from Task 2 is already proven, so a mistake here is a wrong fact, not a broken page.

**Files:**
- Modify: `site-src/data/experiments.yaml`

**Interfaces:**
- Consumes: `tools.experiments.ROLES`, `STATUSES` from Task 2.
- Produces: the populated data every later task renders.

**Method for every single entry, without exception:**

1. Open the collaboration's own page. Record the URL in `source`.
2. Read `status` off it. Taking data? Finished? Under construction? Proposed?
3. If the site is dead or silent, find the paper of its final dataset on INSPIRE and use its DOI as both `url` and `source`.
4. If neither exists, **leave the entry out**. An experiment we cannot source does not go on the page.
5. `city` and `country` must be resolvable by `tools/news/geocode.py`, or the map drops the entry — run the map after each batch to find out.

**The roster, by role, in rank order.** Ranks are the weight in the current global fit; where two are equivalent, alphabetical.

- [ ] **Step 1: `theta13` — Daya Bay, RENO, Double Chooz**

Three entries. `kind: reactor`. Daya Bay and RENO rank 1 and 2: they are the measurements that fix θ₁₃. Check each collaboration's page for whether data-taking has ended and record it.

- [ ] **Step 2: `theta12_dm2` — KamLAND, JUNO**

`kind: reactor`. JUNO's status is `running` only if its own site says so; check, do not assume from our own release.

- [ ] **Step 3: `solar` — SNO, Super-Kamiokande, Borexino, Homestake, GALLEX/GNO, SAGE**

`kind: natural`. Homestake, GALLEX/GNO and SAGE have no live collaboration site: use the INSPIRE record or final-paper DOI for both `url` and `source`, and `status: completed`. Super-Kamiokande appears here **and** under `atmospheric` — that is correct, it constrains both; give it two records with distinct `role`, the same `name`, and note in the YAML header that a name may appear under more than one role. **Adjust the drift test if it treats names as unique** — it compares sets, so duplicates are fine, but confirm rather than assume.

- [ ] **Step 4: `lbl` — T2K, NOvA, MINOS+, K2K, OPERA, ICARUS, then DUNE, Hyper-Kamiokande, ESSnuSB**

`kind: accelerator`. The last three are `construction` or `proposed` — check which; DUNE and Hyper-K are not in the same state and must not be given the same one.

- [ ] **Step 5: `atmospheric` — Super-Kamiokande, IceCube/DeepCore, KM3NeT/ORCA, ANTARES, Kamiokande**

`kind: natural`. ANTARES and Kamiokande are completed; source both.

- [ ] **Step 6: `sterile` — MicroBooNE, SBND, ICARUS, PROSPECT, STEREO, BEST**

`kind: accelerator` for the beam ones, `reactor` for PROSPECT and STEREO, `natural` for BEST (a source experiment — if none of the four kinds fits, add a fifth kind and give it a colour, which then also goes into `test_theme.js`'s `PAIRS`).

- [ ] **Step 7: `mass` — KATRIN, Project 8**

`kind: mass`.

- [ ] **Step 8: `0nubb` — LEGEND, GERDA, KamLAND-Zen, CUORE, CUPID, nEXO, EXO-200, Majorana Demonstrator, NEXT, AMoRE, SNO+**

`kind: mass`. GERDA and EXO-200 are completed and their successors are not; do not collapse a pair into one entry.

- [ ] **Step 9: Regenerate, check, and look at it**

```
./.venv/bin/python3 tools/make_experiments.py
./.venv/bin/python3 tools/make_map.py
./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_experiments.py
./.venv/bin/python3 tools/news/linkcheck.py
```

Expected: the test reports roughly 45 experiments; the map reports how many it placed and names any it could not locate; linkcheck reports zero broken links. **A `! not located` line is a failure to fix, not a note to skip** — either the place name is wrong or it needs a more specific `city`.

- [ ] **Step 10: Commit, once per role batch**

Commit after each of steps 1–8 rather than at the end, so a wrong fact is easy to find later. Message pattern:

```bash
git add site-src/data/experiments.yaml site-src/data/figures/ site/
git commit -m "$(cat <<'EOF'
Experiments: the reactor θ₁₃ measurements, sourced

Daya Bay and RENO were missing from a list that had Double Chooz on it, on a
site published by a group whose analyses are dominated by exactly those two
measurements. Each entry's status is read off the collaboration's own page and
the page is recorded beside it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: A map that can carry forty-five markers

**Files:**
- Modify: `tools/make_map.py`
- Test: `tools/tests/test_experiments.py` (extend with a marker-count check)

**Interfaces:**
- Consumes: `tools.experiments.load()`, `label()`.
- Produces: an SVG in which every marker group is
  `<g class="map-pin" data-site="<slug>" data-kinds="reactor natural" data-names="SNO+|Borexino">`,
  and each experiment within it is `<g class="map-exp" data-experiment="SNO+" data-kind="reactor" …>`.
  `map.js` (Task 5) depends on these exact attribute names.

- [ ] **Step 1: Group co-located experiments**

Kamioka will hold Super-Kamiokande, KamLAND, T2K's far detector and Hyper-Kamiokande; Gran Sasso will hold Borexino, LEGEND, CUORE and OPERA. Four coincident dots are one dot. In `main()`, after projecting, bucket by rounded position:

```python
    sites: dict[tuple[float, float], list[dict]] = {}
    for e, x, y in placed:
        key = (round(x, 1), round(y, 1))
        sites.setdefault(key, []).append(e)
```

Emit one `<g class="map-pin">` per bucket. A bucket holding more than one experiment gets `data-fan="1"` and a count badge; the individual `<g class="map-exp">` children carry the per-experiment data and start hidden, positioned on a small circle around the parent — `map.js` reveals them on click.

- [ ] **Step 2: Add the south-polar inset**

IceCube sits at the South Pole. Today the frame stops at 78°S and the caption apologises. Draw a small azimuthal-equidistant inset in the lower-left corner: a circle spanning 60°S to the pole, the Antarctic coastline from `tools/news/worldmap.py` reprojected into it, and IceCube's marker inside — same `map-pin` markup, so filtering and the card work there without a special case. Label it `South Pole`.

Then **remove the apology from the caption** in `site-src/content/resources.md:31-35`, replacing it with a sentence about the inset.

- [ ] **Step 3: Emit the data attributes**

Every marker group gets the attributes named in **Interfaces** above. Keep the existing `<title>` on each: it is what makes the map readable with JavaScript off, and Task 5 must not remove it.

- [ ] **Step 4: Regenerate and look**

```
./.venv/bin/python3 tools/make_map.py
./.venv/bin/python3 build.py
```

Open `site/resources.html` in a browser. Expected: every experiment placed, no overlapping dots, IceCube visible in the inset, tooltips working with JavaScript not yet written.

- [ ] **Step 5: Commit**

```bash
git add tools/make_map.py site-src/content/resources.md site-src/data/figures/ site/
git commit -m "$(cat <<'EOF'
The map learns to hold forty-five experiments

Kamioka hosts Super-Kamiokande, KamLAND, T2K's far detector and Hyper-
Kamiokande; Gran Sasso hosts four more. At thirteen entries that was a
curiosity, at forty-five it is a blot. Coincident sites now draw as one marker
that fans out.

IceCube is on the map instead of being explained away. The frame stopped at
78°S and the caption apologised for it; a south-polar inset puts the marker
where the detector is, with the same markup as every other marker so filtering
and the card need no special case.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Zoom, pan, filter, card

**Files:**
- Create: `site-src/assets/js/map.js`
- Create: `tools/tests/test_map.js`
- Modify: `site-src/assets/css/site.css`
- Modify: `site-src/content/resources.md` (frontmatter `scripts:` gains `assets/js/map.js`)
- Modify: `tools/tests/test_theme.js` (any new colour into `PAIRS`)

**Interfaces:**
- Consumes: the SVG attributes from Task 4 — `data-site`, `data-kinds`, `data-names`, `data-experiment`, `data-kind`.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_map.js`, modelled on `test_theme.js`'s structure (build a jsdom document holding a miniature of the generated SVG, load `map.js` into it, drive it):

```js
/* The map's behaviour, tested rather than assumed.
 *
 * Six things, each of which can break on its own:
 *   zoom stays inside its limits; panning moves the group; a legend toggle
 *   hides one kind and only that kind; clicking a marker opens its card with
 *   the right name; a shared site fans out into one child per experiment;
 *   and every control is reachable from the keyboard.
 *
 *   node tools/tests/test_map.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..', '..');
const js = fs.readFileSync(path.join(ROOT, 'site-src/assets/js/map.js'), 'utf8');

const fail = [];
const ok = m => console.log('  ok   ' + m);
const bad = m => { fail.push(m); console.log('  FAIL ' + m); };

const SVG = `
<figure class="figure map-figure">
  <svg id="m" viewBox="0 0 720 324">
    <g class="map-layer">
      <g class="map-pin" data-site="kamioka" data-kinds="natural accelerator"
         data-names="Super-Kamiokande|T2K" data-fan="1" transform="translate(600,120)">
        <title>Kamioka</title>
        <g class="map-exp" data-experiment="Super-Kamiokande" data-kind="natural"></g>
        <g class="map-exp" data-experiment="T2K" data-kind="accelerator"></g>
      </g>
      <g class="map-pin" data-site="chooz" data-kinds="reactor"
         data-names="Double Chooz" transform="translate(350,90)">
        <title>Double Chooz</title>
        <g class="map-exp" data-experiment="Double Chooz" data-kind="reactor"></g>
      </g>
    </g>
  </svg>
  <div class="legend legend--chart">
    <span data-filter="reactor"><i></i>Reactor</span>
    <span data-filter="natural"><i></i>Natural</span>
  </div>
</figure>`;

function boot() {
  const dom = new JSDOM(`<!doctype html><body>${SVG}</body>`,
                        { runScripts: 'outside-only', pretendToBeVisual: true });
  dom.window.eval(js);
  dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
  return dom.window.document;
}

/* 1. controls are injected and reachable */
let d = boot();
const zoomIn = d.querySelector('.map-ctl [data-zoom="in"]');
zoomIn ? ok('a zoom-in control is provided') : bad('no zoom-in control');
if (zoomIn && zoomIn.tagName === 'BUTTON') ok('the control is a button, so it is focusable');
else bad('the zoom control is not a button');

/* 2. zoom is bounded */
d = boot();
for (let i = 0; i < 40; i++) d.querySelector('[data-zoom="in"]').click();
let t = d.querySelector('.map-layer').getAttribute('transform') || '';
let scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale <= 8.001 ? ok('zooming in stops at the limit') : bad('zoom ran past its limit: ' + scale);

d = boot();
for (let i = 0; i < 40; i++) d.querySelector('[data-zoom="out"]').click();
t = d.querySelector('.map-layer').getAttribute('transform') || '';
scale = parseFloat((t.match(/scale\(([\d.]+)/) || [])[1] || '1');
scale >= 0.999 ? ok('zooming out stops at the original scale') : bad('zoomed out past 1: ' + scale);

/* 3. markers keep their screen size */
d = boot();
d.querySelector('[data-zoom="in"]').click();
const pin = d.querySelector('.map-pin');
pin.getAttribute('transform').indexOf('scale') > -1
  ? ok('markers counter-scale so they stay the same size on screen')
  : bad('markers do not counter-scale and will grow into blobs');

/* 4. a legend entry filters its kind and only its kind */
d = boot();
d.querySelector('[data-filter="reactor"]').click();
const chooz = d.querySelector('[data-site="chooz"]');
const kamioka = d.querySelector('[data-site="kamioka"]');
chooz.hasAttribute('hidden') ? ok('turning off a kind hides its markers')
                             : bad('the filter did not hide the reactor marker');
!kamioka.hasAttribute('hidden') ? ok('a marker of another kind is untouched')
                                : bad('the filter hid an unrelated marker');

/* 5. clicking a marker opens a card naming it */
d = boot();
d.querySelector('[data-site="chooz"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const card = d.querySelector('.map-card');
card && /Double Chooz/.test(card.textContent)
  ? ok('clicking a marker opens a card naming the experiment')
  : bad('no card, or the card does not name the experiment');

/* 6. a shared site fans out */
d = boot();
d.querySelector('[data-site="kamioka"]').dispatchEvent(new d.defaultView.Event('click', {bubbles: true}));
const shown = [...d.querySelectorAll('[data-site="kamioka"] .map-exp')]
  .filter(g => !g.hasAttribute('hidden'));
shown.length === 2 ? ok('a shared site fans out into one child per experiment')
                   : bad('the fan-out revealed ' + shown.length + ' of 2');

/* 7. the SVG stays readable with the script never running */
const plain = new JSDOM(`<!doctype html><body>${SVG}</body>`).window.document;
plain.querySelectorAll('.map-pin title').length === 2
  ? ok('every marker keeps its <title>, so the map reads with JS off')
  : bad('a marker lost its <title>');

console.log();
if (fail.length) { console.log(fail.length + ' check(s) failed'); process.exit(1); }
console.log('all checks pass');
```

- [ ] **Step 2: Run it and watch it fail**

```
node tools/tests/test_map.js
```

Expected: `ENOENT … site-src/assets/js/map.js`.

- [ ] **Step 3: Write `map.js`**

Follow `site.js`'s conventions exactly: an IIFE, `"use strict"`, `var`, no build step, no dependency, and guarded feature detection so a missing API disables an enhancement rather than throwing. It must:

- find `.map-figure svg`, wrap the markers in `<g class="map-layer">` if the SVG did not already provide one, and inject a `.map-ctl` toolbar of three `<button>`s (`data-zoom="in"`, `"out"`, `"reset"`);
- keep `scale` between `1` and `8`; apply `translate(tx,ty) scale(s)` to `.map-layer`;
- counter-scale every `.map-pin` by `scale(1/s)` so markers keep their screen size;
- pan on pointer drag, zoom on wheel with `preventDefault` only when the pointer is over the map, and support pinch via two-pointer distance;
- respond to arrow keys for panning and `+`/`-` for zoom when the SVG has focus, with `tabindex="0"` and a visible focus ring;
- toggle a kind when a `[data-filter]` legend entry is clicked, setting `hidden` on markers whose `data-kinds` no longer intersects the enabled set, and reflecting state in `aria-pressed`;
- on marker click, build `.map-card` from `data-names` plus the child `data-experiment` groups, and reveal the `.map-exp` children when `data-fan` is set;
- close the card on `Escape` and on a click outside it;
- do nothing at all — silently — when no `.map-figure` is on the page, because `map.js` will be loaded only by Resources but must not throw if that changes.

- [ ] **Step 4: Run it and watch it pass**

```
npm install jsdom   # already present; run only if node reports it missing
node tools/tests/test_map.js
```

Expected: `all checks pass`.

- [ ] **Step 5: Style the controls and the card**

In `site-src/assets/css/site.css`, add `.map-figure`, `.map-ctl`, `.map-card` and `.map-exp` rules using existing tokens only. The `.shots`/`.shot` rules at lines 652–661 no longer have a gallery to style: retarget the photograph rules to `.map-card img` rather than deleting and rewriting them. Add every new foreground/background pair to `PAIRS` in `tools/tests/test_theme.js`, then:

```
node tools/tests/test_theme.js
```

Expected: `all checks pass`, including the new pairs.

- [ ] **Step 6: Load the script on the page**

In `site-src/content/resources.md`'s frontmatter:

```yaml
scripts:
  - assets/js/map.js
```

- [ ] **Step 7: Build and look at it in a browser**

```
./.venv/bin/python3 build.py
./serve.sh
```

In both themes and at a 700px width: zoom, pan, filter, open a card, fan out Kamioka, reach every control by keyboard, press Escape. **Looking is a step, not a formality** — the last audit found a missing sparkline that every test had passed over.

- [ ] **Step 8: Commit**

```bash
git add site-src/assets/js/map.js site-src/assets/css/site.css \
        site-src/content/resources.md tools/tests/test_map.js tools/tests/test_theme.js site/
git commit -m "$(cat <<'EOF'
The map becomes something you can use

Zoom, pan, filter by what an experiment constrains, and a card on click
carrying the place, the role, the status and the photograph. Markers
counter-scale so they stay the size of markers instead of growing into blobs,
and a site hosting several experiments fans out.

With JavaScript off the SVG still draws and every marker keeps its <title>,
which the test checks: the map is content, not an application.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: A hero figure that is a result

**Files:**
- Modify: `tools/make_figures.py` (add `hero_ranges_svg()`, write it in `main()`)
- Modify: `site-src/content/index.md:25-44`
- Modify: `tools/tests/test_release_numbers.py`

**Interfaces:**
- Consumes: `load()`, `entry()`, `PARAMS` already in `tools/make_figures.py`.
- Produces: `site-src/data/figures/ranges-hero.svg`, resolved by `<!--include:ranges-hero-->`.

- [ ] **Step 1: Extend the numbers test first**

In `tools/tests/test_release_numbers.py`, add a check that every best-fit value drawn in `ranges-hero.svg` appears in Table I of the paper — the same treatment the rest of the home page's numbers already get. Run it and watch it fail because the file does not exist:

```
./.venv/bin/python3 tools/tests/test_release_numbers.py
```

- [ ] **Step 2: Write `hero_ranges_svg`**

In `tools/make_figures.py`, beside `ranges_svg`. It must share its geometry with `ranges_svg` rather than copy it — extract the per-row drawing into a helper both call, so the two figures cannot disagree about a number or a scale. Proportions for the hero column: one row per parameter, normal ordering only, roughly `W = 520`, and a caption line carrying `arXiv:2503.07752`.

Then in `main()`:

```python
    (OUT / "ranges-hero.svg").write_text(hero_ranges_svg(meta, bari), encoding="utf-8")
    written.append("ranges-hero")
```

- [ ] **Step 3: Replace the invented figure**

In `site-src/content/index.md`, delete lines 25–44 — the whole `<figure>` with the hand-drawn `<path>`s, the legend, and the caption beginning "Illustrative." — and put in their place:

```markdown
    <figure class="figure">
      <h4>The six parameters, as measured</h4>
      <!--include:ranges-hero-->
      <p class="cap">Best fit with 1σ and 3σ ranges, normal ordering, from
      Table I of <a href="https://doi.org/10.1103/PhysRevD.111.093006">Phys.
      Rev. D 111, 093006 (2025)</a>. Full tables, both orderings and the
      downloadable files are on the <a href="results.html">results page</a>.</p>
    </figure>
```

The words "Illustrative", "schematic" and "not a fit" must not survive anywhere on the page. Grep for them.

- [ ] **Step 4: Regenerate and verify**

```
./.venv/bin/python3 tools/make_figures.py
./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_release_numbers.py
grep -ri "illustrative\|schematic" site/ site-src/content/
```

Expected: the numbers test passes including the new check; the grep returns nothing.

- [ ] **Step 5: Commit**

```bash
git add tools/make_figures.py tools/tests/test_release_numbers.py \
        site-src/content/index.md site-src/data/figures/ranges-hero.svg site/
git commit -m "$(cat <<'EOF'
The home page opens with a measurement, not a drawing

The hero figure was two hand-drawn curves labelled "Illustrative" and
"schematic, not a fit" — on a site whose first rule is that no number appears
without a source. It is now the six parameters with their 1σ and 3σ ranges,
from the same Table I values as the figure on the results page, drawn by the
same code so the two cannot disagree, and checked against the paper by
test_release_numbers.py like every other number on the page.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: The whole suite, and a real browser

**Files:** none changed unless something fails.

- [ ] **Step 1: Everything, in order**

```
./.venv/bin/python3 build.py
for t in tools/tests/test_*.py; do echo "== $t"; ./.venv/bin/python3 "$t" || echo "FAILED"; done
node tools/tests/test_theme.js
node tools/tests/test_map.js
node tools/tests/test_mockup_contrast.js
./.venv/bin/python3 tools/news/linkcheck.py
```

Expected: every test passes, linkcheck reports zero broken links.

- [ ] **Step 2: Confirm the daily job still runs**

The launchd job rebuilds the site every morning. Run its manual equivalent and confirm it completes:

```
./update-daily
tail -20 var/news/logs/news.log
```

Expected: `build ok` and `run finished`.

- [ ] **Step 3: Look at the pages**

Home and Resources, in both themes, at full width and at 700px. Check the hero figure reads at a glance, the map zooms and filters, a card opens, the tiles group sensibly, and no experiment name is orphaned.

- [ ] **Step 4: Add `.idea/` to `.gitignore`**

It has been untracked since the project began.

- [ ] **Step 5: Final commit**

```bash
git add .gitignore
git commit -m "$(cat <<'EOF'
Ignore .idea/, and record the verification of this branch of work

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage.** Section 1 of the spec → Tasks 2 and 3. Section 2 → Tasks 4 and 5. Section 3 → Task 1 (collapsing) and Task 5 Step 5 (photographs moving into the card). Section 4 → Task 6. The spec's verification list → Task 7, plus the per-task checks. The spec's "sourcing rule" is the method block at the head of Task 3.

**One divergence, flagged above and repeated here so it is not missed:** the spec says the projection is extended south; Task 4 uses a polar inset instead, for the reason given. Confirm with Antonio at Task 4's review.

**Type consistency.** `tools.experiments` exports `ROLES`, `STATUSES`, `STATUS_LABEL`, `load()`, `ordered()`, `label()`; Task 2's test imports exactly those, Task 2's tiles renderer calls exactly those, Task 4's map calls `load()` and `label()`. The SVG attribute names in Task 4's Interfaces (`data-site`, `data-kinds`, `data-names`, `data-fan`, `data-experiment`, `data-kind`) are the ones Task 5's test drives and Task 5's implementation reads. `data-experiment` is also what Task 2's drift test counts on the built page, so the tiles renderer and the map both emit it.

**Placeholders.** None. Task 3 deliberately carries no code — it is compilation, and its steps are the method by which each fact is established rather than instructions to invent one.
