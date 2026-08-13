# Parameter History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three-group comparison the spine of the Parameter history page, teach the register to hold upper limits as well as measurements, add five sourced releases, and publish the whole record as citable JSON and CSV.

**Architecture:** A new `tools/history.py` becomes the single loader and validator for `site-src/data/history.yaml` — the same shape that `tools/experiments.py` took for the experiment roster, and for the same reason: three consumers (the page generator, the new exporter, the tests) must not each parse the file their own way. Rendering stays in `tools/make_history.py`; export goes in a new `tools/make_history_data.py`.

**Tech Stack:** Python 3 (stdlib + PyYAML + pymupdf for the PDF checks), SVG generated as text, no JavaScript, the project's own `.venv`.

## Global Constraints

Copied from the spec and `PROMPT_GLOBAL_NU.md`; every task implicitly includes these.

- **No physical value from memory.** Every number comes from the table named in the record, in the cached PDF. A value that cannot be found in its source is a failure, not a rounding difference.
- **A limit whose confidence level cannot be established from the paper is omitted**, like any other unsourceable value.
- **Prose answers to the same rule as numbers.** The page title must not claim a span the register does not cover.
- No CDN, no external runtime request; no hard-coded colours — CSS custom properties only, and any new pair goes into `PAIRS` in `tools/tests/test_theme.js`.
- `site-src/content/history.md` is **generated** — edit `tools/make_history.py` or the YAML, never the Markdown. Its header says so.
- `site/` is build output, never hand-edited.
- Python is `./.venv/bin/python3`, never bare `python3`.
- Commit messages are prose in the register of the existing `git log` (read `git log -5`). No `feat:`/`fix:` prefixes. Keep the `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` trailer.
- Do not commit anything under `var/`, `drafts/`, `site-draft/` or `preview/`.
- `node tools/tests/test_mockup_contrast.js` fails on `mockups/index.html`. That is **pre-existing and unrelated** — confirmed by running it on a clean checkout of the merge base. Do not fix it, and do not let it stop you.

## File Structure

| File | Responsibility |
|---|---|
| `tools/history.py` | **new** — load, validate and normalise `history.yaml`; classify a value as measurement or limit. No output, no side effects. |
| `tools/make_history_data.py` | **new** — write `site-src/data/exports/history.json` and `history.csv`. |
| `tools/make_history.py` | modify — read through `tools/history.py`; draw limits; reorder the page; fix the title. |
| `site-src/data/history.yaml` | modify — limit entries, `excluded:` section, five new releases. |
| `site-src/content/history-schema.md` | **new** — documents every exported field. |
| `tools/tests/test_history_schema.py` | **new** — measurement-xor-limit, level vocabulary, cited table exists in the PDF. |
| `tools/tests/test_history_export.py` | **new** — JSON/CSV against the YAML, both directions; conversion column agreement. |
| `tools/tests/test_history_numbers.py` | modify — cover limit values. |
| `site-src/site.yaml` | modify — nav entry for the schema page. |

---

### Task 1: A value is a measurement or a limit

Nothing loads `history.yaml` through a validator today — `tools/make_history.py` parses it inline. Three consumers are about to need it.

**Files:**
- Create: `tools/history.py`
- Create: `tools/tests/test_history_schema.py`
- Modify: `tools/make_history.py` (replace its inline `yaml.safe_load` with `history.load()`)

**Interfaces produced** (later tasks depend on these exact names):
- `LEVELS: tuple[str, ...]` — `("3sigma", "2sigma", "90%CL", "95%CL")`
- `load() -> dict` — the whole document, validated; raises `SystemExit` naming the offending record
- `kind_of(entry: dict) -> str` — `"measurement"` or `"limit"`
- `limit_label(entry: dict) -> str` — e.g. `"< 5.0 (3σ)"`, for a marker's `<title>`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_history_schema.py`:

```python
#!/usr/bin/env python3
"""The shape of a recorded value, checked before it can reach a page.

    ./.venv/bin/python3 tools/tests/test_history_schema.py

Until now every value in history.yaml was a measurement: a best fit with
ranges. Early papers bound a parameter instead of measuring it, and a bound
without its confidence level is not a datum — "sin²θ₁₃ < 0.05" means different
things at 90% CL and at 3σ. So a value is a measurement or a limit, never both
and never neither, and a limit names its level.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import history                              # noqa: E402

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


# 1. the real file loads
doc = history.load()
check("history.yaml loads and validates", bool(doc.get("releases")))

# 2. classification
check("a best fit with ranges is a measurement",
      history.kind_of({"best": 2.23, "s3": [2.05, 2.41]}) == "measurement")
check("an upper bound with a level is a limit",
      history.kind_of({"upper": 5.0, "level": "3sigma"}) == "limit")

# 3. malformed records are rejected, built here rather than by editing the data
def rejects(entry: dict) -> bool:
    try:
        history.validate_value("sin2_th13", "no", entry)
        return False
    except SystemExit:
        return True

check("a value that is both a measurement and a limit is rejected",
      rejects({"best": 2.2, "s3": [2.0, 2.4], "upper": 5.0, "level": "3sigma"}))
check("a value that is neither is rejected", rejects({"note": "unclear"}))
check("a limit with no level is rejected", rejects({"upper": 5.0}))
check("a limit with an unknown level is rejected",
      rejects({"upper": 5.0, "level": "eyeballed"}))
check("a limit with a known level is accepted",
      not rejects({"upper": 5.0, "level": "90%CL"}))

# 4. the label a reader sees
check("a limit's label states the bound and the level",
      history.limit_label({"upper": 5.0, "level": "3sigma"}) == "< 5.0 (3σ)")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — every recorded value is a measurement or a limit")
```

- [ ] **Step 2: Run it and watch it fail**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
```

Expected: `ModuleNotFoundError: No module named 'tools.history'`.

- [ ] **Step 3: Write the library**

Create `tools/history.py`. Note the `sys.path` insert: this repo has no `tools/__init__.py` and works as a PEP 420 namespace package, so a script run from the repo root needs the root on the path — `tools/make_map.py` sets the precedent.

```python
#!/usr/bin/env python3
"""The parameter history, loaded once and validated once.

The page generator, the data exporter and the tests all read history.yaml
through here, so none of them can disagree about what a record means.

A recorded value takes one of two shapes and never both:

    {best: 2.23, s1: [...], s3: [...]}     a measurement
    {upper: 5.0, level: "3sigma"}          a limit

The level is not decoration. Older papers bound parameters at whatever
confidence suited them, and a bound printed without its level cannot be
compared with another bound — so a limit that does not name one is refused
here rather than drawn misleadingly on a panel.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "history.yaml"

# Extended when a paper demands it, not decided in advance.
LEVELS: tuple[str, ...] = ("3sigma", "2sigma", "90%CL", "95%CL")

LEVEL_TEXT = {"3sigma": "3σ", "2sigma": "2σ", "90%CL": "90% CL", "95%CL": "95% CL"}


def kind_of(entry: dict) -> str:
    """"measurement", "limit", or "" when the entry is neither."""
    measured = "best" in entry
    bounded = "upper" in entry or "lower" in entry
    if measured and not bounded:
        return "measurement"
    if bounded and not measured:
        return "limit"
    return ""


def validate_value(pname: str, ordering: str, entry: dict) -> None:
    """Raise SystemExit naming the offender, or return quietly."""
    where = f"{pname}/{ordering}"
    kind = kind_of(entry)
    if kind == "":
        sys.exit(f"{DATA.name}: {where} is neither a measurement nor a limit: {entry!r}")
    if kind == "limit":
        level = entry.get("level")
        if not level:
            sys.exit(f"{DATA.name}: {where} is a limit with no confidence level")
        if level not in LEVELS:
            sys.exit(f"{DATA.name}: {where} has level {level!r}, "
                     f"which is not one of {', '.join(LEVELS)}")


def limit_label(entry: dict) -> str:
    """What a reader sees on the marker: the bound and the level it holds at."""
    level = LEVEL_TEXT.get(entry.get("level", ""), entry.get("level", ""))
    if "upper" in entry:
        return f"< {entry['upper']:g} ({level})"
    return f"> {entry['lower']:g} ({level})"


def load() -> dict:
    """The whole document, with every value validated."""
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    if not (doc or {}).get("releases"):
        sys.exit(f"{DATA} holds no releases")
    for rel in doc["releases"]:
        for pname, byo in (rel.get("values") or {}).items():
            for ordering, entry in byo.items():
                validate_value(pname, ordering, entry)
    return doc
```

- [ ] **Step 4: Run it and watch it pass**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
```

Expected: `all 9 checks pass`.

- [ ] **Step 5: Point the generator at the library**

In `tools/make_history.py`, replace the inline read with `history.load()`, adding the `sys.path` insert and `from tools import history` beside the existing imports. Then:

```
./.venv/bin/python3 tools/make_history.py && ./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_history_numbers.py
git diff --stat site-src/content/history.md
```

Expected: the numbers test still passes and `history.md` is **byte-identical** — this step changes how the file is read, not what is drawn. A diff here means something was altered by accident.

- [ ] **Step 6: Commit**

```bash
git add tools/history.py tools/tests/test_history_schema.py tools/make_history.py
git commit -m "$(cat <<'EOF'
A recorded value learns to be a limit instead of a measurement

Every value in history.yaml has so far been a best fit with ranges, because
every release in it measured what it reported. The early global analyses
bounded theta13 rather than measuring it, and a bound carries something a
measurement does not: the confidence level it holds at. "sin2 theta13 < 0.05"
means different things at 90% CL and at 3 sigma, so a limit that does not name
its level is refused rather than drawn on a panel where a reader would compare
it with one that does.

tools/history.py now loads and validates the file for everyone who reads it —
the generator today, the exporter and two more tests shortly. The malformed
cases are built in the test rather than by editing the real data.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: A limit is drawn as a limit

**Files:**
- Modify: `tools/make_history.py` — `marker()` (line 57), `compare_panel()` (line 109), `panel()` (line 183)
- Modify: `tools/tests/test_history_schema.py` — add rendering checks

**Interfaces:**
- Consumes: `history.kind_of`, `history.limit_label` from Task 1.
- Produces: `marker(kind, x, y, colour, label)` accepts `kind="limit-upper"`; `compare_panel` and `panel` accept limit entries.

- [ ] **Step 1: Understand what breaks**

`compare_panel` reads `e["best"]` and `e.get("s3")` when computing the vertical range and when placing a point. A limit entry has neither. `panel` does the same. Both must treat a limit as a point at the bound with a downward arrow, and must include the bound when computing the axis range — otherwise a limit can fall outside the drawn area.

- [ ] **Step 2: Write the failing checks**

Append to `tools/tests/test_history_schema.py`, before the summary block:

```python
# 5. rendering
sys.path.insert(0, str(ROOT / "tools"))
import make_history                                     # noqa: E402

svg = make_history.marker("limit-upper", 100.0, 50.0, "var(--no)", "< 5.0 (3σ)")
check("a limit renders as its own shape, not a measurement's",
      "<circle" not in svg and "<rect" not in svg,
      f"got: {svg[:80]}")
check("a limit's marker carries its label", "< 5.0 (3σ)" in svg)
```

- [ ] **Step 3: Run and watch it fail**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
```

Expected: FAIL — `marker` falls through to the diamond branch for an unknown kind, so `<path` is produced but the two checks above will still catch the shape being a diamond only if you assert it; the label check passes. Read the actual failure before implementing, and if only one check fails, say so in your report rather than assuming both did.

- [ ] **Step 4: Draw the arrow**

In `marker()`, add a branch before the fallback:

```python
    if kind == "limit-upper":
        # A downward arrow from the bound: the value lies below this line,
        # somewhere, and the drawing must not suggest a point estimate.
        return (f'<path d="M{x - 5:.1f} {y:.1f}L{x + 5:.1f} {y:.1f}M{x:.1f} {y:.1f}'
                f'L{x:.1f} {y + 11:.1f}M{x - 3.4:.1f} {y + 7:.1f}L{x:.1f} {y + 11:.1f}'
                f'L{x + 3.4:.1f} {y + 7:.1f}" fill="none" stroke="{colour}" '
                f'stroke-width="2" stroke-linecap="round">{t}</path>')
```

Then in both `compare_panel` and `panel`, where values are collected for the axis range, include a limit's bound; and where a point is placed, branch on `history.kind_of(e)` to call `marker("limit-upper", …)` with `history.limit_label(e)` instead of the measurement marker and its range bar.

- [ ] **Step 5: Run and watch it pass**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
./.venv/bin/python3 tools/make_history.py && ./.venv/bin/python3 build.py
```

Expected: checks pass; the page still builds. No limit exists in the data yet, so `history.md` should again be byte-identical — verify with `git diff --stat`.

- [ ] **Step 6: Prove it draws, before any real data depends on it**

Add a limit entry by hand to a scratch copy of the YAML (not the real one), regenerate, and **open the page in a browser** to confirm the arrow is distinguishable from a circle at panel scale, in both themes. Then discard the scratch edit. Report what you saw. Do not commit the scratch entry.

- [ ] **Step 7: Add the legend entry and commit**

The page's legend lists circle / square / diamond. Add the arrow with its meaning ("upper limit, level printed on the marker"). Check the legend colours against `PAIRS` in `tools/tests/test_theme.js` and run `node tools/tests/test_theme.js`.

```bash
git add tools/make_history.py tools/tests/test_history_schema.py site-src/content/history.md site/
git commit -m "$(cat <<'EOF'
An upper limit is drawn as an arrow, not as a point

A bound is not a measurement and must not look like one: the marker is a
downward arrow from the bound, so nothing on the panel suggests a value was
found there. The bound joins the numbers that set each panel's vertical range,
because a limit drawn outside the drawn area is worse than no limit at all.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: The cited table must exist in the cited paper

A cheap mechanical guard, added before the compilation that will lean on it.

**Files:**
- Modify: `tools/tests/test_history_schema.py`

**Interfaces:** consumes `history.load()`.

- [ ] **Step 1: Write the failing check**

Every release names its source table in `rel["table"]` — values like `"Table 1, first column"`, `"Table III"`. Add a check that the table's identifier occurs in the PDF's text. `tools/tests/test_history_numbers.py` already opens the cached PDFs; reuse its `pdf_text()` helper by importing it rather than writing a second one.

```python
# 6. the cited table exists in the cited paper
sys.path.insert(0, str(ROOT / "tools" / "tests"))
import test_history_numbers as thn                      # noqa: E402
import re                                               # noqa: E402

missing = []
for rel in doc["releases"]:
    pdf = thn.pdf_for(rel)
    if pdf is None or not pdf.exists():
        continue                       # absent cache is the numbers test's problem
    text = thn.pdf_text(pdf)
    ident = re.match(r"(Table\s+[IVXLC0-9]+)", rel.get("table", ""), re.I)
    if not ident:
        missing.append(f'{rel["group"]} {rel["year"]}: table field names no table')
        continue
    if ident.group(1).lower() not in text.lower():
        missing.append(f'{rel["group"]} {rel["year"]}: {ident.group(1)} not found in the PDF')

check("every cited table exists in the paper it is cited from", not missing,
      "; ".join(missing[:5]))
```

If `test_history_numbers.py` has no `pdf_for(rel)` helper, extract the path-building it already does inline into one, and use it from both — do not duplicate the logic.

- [ ] **Step 2: Run it**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
```

If existing records fail, that is a real finding about the current data, not a broken test. **Report it rather than loosening the check** — investigate each one and say what you found.

- [ ] **Step 3: Commit**

```bash
git add tools/tests/test_history_schema.py tools/tests/test_history_numbers.py
git commit -m "$(cat <<'EOF'
Check that a cited table exists in the paper it is cited from

The numbers test verifies that a value appears in the table named. It cannot
verify that the right table was named — and citing the wrong table is how the
experiment roster went wrong five times in a week. This does not close that
gap, but it catches the cheapest version of it: a record pointing at Table III
of a paper with two tables.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Five releases, each read from its own paper

Pure compilation, on machinery now proven. No code changes.

**Files:**
- Modify: `site-src/data/history.yaml`

**Method — the same discipline the experiment roster arrived at the hard way.** For each paper: open the cached PDF in `var/history-sources/`, find the table that quotes the oscillation parameters, and transcribe from it. Record `table` precisely enough that another person finds the same one. For any **limit**, record the sentence or table heading stating the confidence level in a `source_quote` field on that value — a level taken from context rather than from words on the page is not sourced.

If a paper's table does not quote a parameter, that parameter is simply absent from the record. Do not carry a value across from a neighbouring release, and do not convert a range into a limit or a limit into a range.

- [ ] **Step 1: Bari — `hep-ph/0506083` (2006)**

`var/history-sources/bari-2005-hep-ph_0506083.pdf`. Prog. Part. Nucl. Phys. 57 742 (2006), so the record's `year` is **2006** — this file keys a release by its journal year, as the existing 2026 entry does with a 2025 preprint. Convention is ours (`Dm2 = m3^2 - (m1^2 + m2^2)/2`); confirm that against the paper rather than assuming, and record what it actually says.

- [ ] **Step 2: NuFit predecessor — `hep-ph/0009350` (2000)**

`var/history-sources/nufit-2000-hep-ph_0009350.pdf`. Record the group as `nufit` (the file already treats the predecessors that way) and state the convention the paper uses. Expect θ₁₃ as a limit.

- [ ] **Step 3: NuFit predecessor — `hep-ph/0405172` (2004)**

`var/history-sources/nufit-2004-hep-ph_0405172.pdf`.

- [ ] **Step 4: NuFit — `1001.4524` (2010)**

`var/history-sources/nufit-2010-1001.4524.pdf`.

- [ ] **Step 5: Valencia — `1806.11051` (2018)**

`var/history-sources/valencia-2018-1806.11051.pdf`. Valencia quotes `|Dm2_31|` for both orderings; a second 2018 Valencia record already exists (`1708.01186`), so check whether these are the same analysis reported twice before adding a duplicate point — and if they are, say which one belongs and why.

- [ ] **Step 6: Record the exclusions**

Add an `excluded:` section to `history.yaml` listing what was considered and rejected, with reasons: `hep-ph/0206162` methodological; `hep-ph/0208026` a solar analysis with terrestrial constraints whose only table is a 2ν solar fit without CHOOZ; the 2001–2004 conference proceedings for want of a citable table. Include arXiv identifier and title for each.

- [ ] **Step 7: Verify after each paper, not at the end**

```
./.venv/bin/python3 tools/tests/test_history_schema.py
./.venv/bin/python3 tools/tests/test_history_numbers.py
./.venv/bin/python3 tools/tests/test_history_conversion.py
./.venv/bin/python3 tools/make_history.py && ./.venv/bin/python3 build.py
```

A new group convention needs a case in `test_history_conversion.py`. Commit per paper, not once at the end.

---

### Task 5: The comparison leads

**Files:**
- Modify: `tools/make_history.py` — `main()` (line 264) and the page's prose

- [ ] **Step 1: Reorder**

The comparison section and its panels move above the Bari-only series. The methodological note on conventions moves with it: it is the key to reading the page, not a footnote to it. The Bari series keeps its own heading and stays below.

- [ ] **Step 2: Fix the title**

`A quarter century of global fits` claims a span the register does not cover — with the earliest Bari record now 2006 and the earliest record of any group 2000, neither reading supports twenty-five years. Replace it with a phrase that is true of what the page shows. State in your report which you chose and why.

- [ ] **Step 3: Regenerate, look, commit**

```
./.venv/bin/python3 tools/make_history.py && ./.venv/bin/python3 build.py
```

Open `site/history.html` in a browser, both themes, full width and 700px. Confirm the panels stay legible with three groups and twenty-one points, that arrows are distinguishable from circles, and that no label collides — the earlier audit on this project found exactly that fault in a different figure, and only looking caught it.

---

### Task 6: The register as citable data

**Files:**
- Create: `tools/make_history_data.py`, `site-src/content/history-schema.md`, `tools/tests/test_history_export.py`
- Modify: `site-src/site.yaml` (nav)

**Interfaces:** consumes `history.load()`; and `make_history.to_our_Dm2(rel, ordering, value)` for the converted column.

- [ ] **Step 1: Write the failing test**

`tools/tests/test_history_export.py` must check, on the real exports:
1. every (group, year, parameter, ordering) point in the YAML appears in the JSON, and
2. every row in the JSON corresponds to a point in the YAML — both directions, as the experiment drift test does;
3. the CSV has the same row count as the JSON;
4. for every row, `value_our_convention` equals what `to_our_Dm2` produces from `value_as_published` for `Dm2`, and equals `value_as_published` for every other parameter.

- [ ] **Step 2: Run it and watch it fail** — the exporter does not exist.

- [ ] **Step 3: Write the exporter**

Writes `site-src/data/exports/history.json` and `history.csv`, copied into `site/data/` by the build. Every row carries: `group`, `year`, `arxiv`, `journal`, `table`, `parameter`, `ordering`, `convention`, `kind` (`measurement`/`limit`), `value_as_published`, `value_our_convention`, `unit`, and for a limit `level`. Only `Dm2` is ever converted; for the other five the two value columns hold the same number, which is correct rather than redundant.

- [ ] **Step 4: Write the schema page**

`site-src/content/history-schema.md` documents every field, states the conversion rule in words and points at `to_our_Dm2`, gives the stable URLs, and says plainly that `value_as_published` is what the paper printed and `value_our_convention` is our arithmetic.

- [ ] **Step 5: Verify, look, commit**

Run the export, the new test, the build, and check the files are reachable at their URLs in the built tree. Confirm `test_no_draft_leak.py` still passes — a new export path is a new way for embargoed material to escape, and that test is the one that would catch it.

---

## Self-review

**Spec coverage.** Spec §1 (measurement or limit) → Task 1. §1's level vocabulary → Task 1. §2 (`excluded:`) → Task 4 Step 6. §3 (five extractions, `source_quote` on limits) → Task 4. §4 (page reorganised, title) → Task 5. §5 (export, both columns, schema page) → Task 6. Verification list → the per-task steps plus Task 6 Step 5; the "cited table exists" check → Task 3.

**Placeholders.** None. Task 4 carries no code because it is compilation; its steps are the method by which each value is established.

**Type consistency.** `tools.history` exports `LEVELS`, `LEVEL_TEXT`, `kind_of`, `validate_value`, `limit_label`, `load`; Task 1's test imports exactly those, Task 2 calls `kind_of` and `limit_label`, Tasks 3 and 6 call `load`. `marker`'s new kind string is `"limit-upper"` in both the test and the implementation. The exported column names `value_as_published` and `value_our_convention` are identical in Task 6's test, exporter and schema page.

**One risk worth stating.** Task 2 Step 3 predicts a test failure whose exact shape depends on `marker`'s fallback branch. The step tells the implementer to read the real failure and report if only one of the two checks fails, rather than assuming the prediction was right.
