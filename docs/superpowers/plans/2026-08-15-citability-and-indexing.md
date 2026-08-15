# Citability and Indexing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the parameter register a Zenodo DOI and describe it, on the page, in a form machines read — plus an explicit crawler policy and an `llms.txt`.

**Architecture:** One new placeholder (`{{head_extra}}`) in the single page template, filled by a new `head_extra()` in `build.py` for pages that opt in from their own front matter. The facts the metadata states (year span, parameters, last-changed date) are computed by a new shared module, `tools/register_meta.py`, which both `build.py` and the Zenodo deposit tool import so they cannot disagree. `robots.txt` and `llms.txt` become source files under `site-src/`. The DOI is one line of `site.yaml`, absent until the deposit is made — and while it is absent, nothing claims it.

**Tech Stack:** Python 3 (stdlib + PyYAML, already vendored in `.venv`), no new dependencies. Tests are standalone scripts run as `./.venv/bin/python3 tools/tests/test_X.py`, following the existing suite — there is no pytest in this project.

**Spec:** `docs/superpowers/specs/2026-08-15-citability-and-indexing-design.md`

## Global Constraints

- **No value with a source is written from memory.** Every fact in the metadata is computed from the register or read from `site.yaml`. Nothing is typed twice.
- **A page prints nothing where a value is unknown.** With no DOI configured, the build emits no `identifier`, no `citation_doi`, and no DOI line in `llms.txt` — not an empty string, not a placeholder: the field is absent.
- **No third-party host.** Nothing added here loads or fetches from another origin at page-render time. The only network access anywhere in this plan is in `tools/make_zenodo_deposit.py`, opt-in behind a flag.
- **The build stays deterministic and offline.** No task may add a network call to `build.py`. The 07:30 job must not be able to fail because a remote service is down.
- **Creator identity, fixed and confirmed by Antonio on 2026-08-15:** name `Antonio Marrone`, ORCID `0000-0001-6096-1880`, affiliation `Università di Bari and INFN Bari`.
- **Related identifiers, verified against INSPIRE-HEP:** paper DOI `10.1103/PhysRevD.111.093006`, arXiv `2503.07752`.
- **Licence:** `https://creativecommons.org/licenses/by/4.0/` for the register and everything under `/data/`.
- **Run the build as** `./.venv/bin/python3 build.py`, from the repository root.

---

### Task 1: The facts the metadata has to state

Two consumers need the same three facts about the register — the year span, the parameters it measures, and when it last changed — and must not compute them differently. This task builds the one module both import.

**Files:**
- Create: `tools/register_meta.py`
- Test: `tools/tests/test_register_meta.py`

**Interfaces:**
- Consumes: `tools/history.py::load()` (returns the whole register document: keys `meta`, `releases`, `excluded`); `data-exports/history.json` (keys `note`, `rows`; each row has `year`, `parameter`, …)
- Produces:
  - `register_facts() -> dict` with keys `temporal_coverage: str` (e.g. `"2001/2026"`), `variables: list[dict]` (each `{"name": str, "label": str, "unit": str}`), `date_modified: str | None` (ISO-8601 date, or `None` when git cannot say), `n_rows: int`, `years: tuple[int, int]`
  - `REGISTER: Path` and `EXPORT: Path`, the two source files

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_register_meta.py`:

```python
#!/usr/bin/env python3
"""Check that the facts the metadata states are computed, not typed.

    ./.venv/bin/python3 tools/tests/test_register_meta.py

Every one of these values appears in published metadata — the
schema.org/Dataset block on history.html and the Zenodo deposit. A
hand-written year span or parameter list is a value that rots the first time
a release is added, and nothing on the page would show it had.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import register_meta                          # noqa: E402

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


facts = register_meta.register_facts()
rows = json.loads(register_meta.EXPORT.read_text(encoding="utf-8"))["rows"]

lo, hi = min(r["year"] for r in rows), max(r["year"] for r in rows)
check("temporalCoverage spans the register's real years",
      facts["temporal_coverage"] == f"{lo}/{hi}",
      f"got {facts['temporal_coverage']!r}, export says {lo}/{hi}")

check("years agrees with temporal_coverage", facts["years"] == (lo, hi))

check("n_rows counts every exported row",
      facts["n_rows"] == len(rows), f"got {facts['n_rows']}, export has {len(rows)}")

named = {v["name"] for v in facts["variables"]}
exported = {r["parameter"] for r in rows}
check("variableMeasured lists exactly the exported parameters",
      named == exported, f"metadata {sorted(named)} vs export {sorted(exported)}")

check("every variable carries a label and a unit",
      all(v.get("label") and v.get("unit") for v in facts["variables"]),
      str([v for v in facts["variables"] if not (v.get("label") and v.get("unit"))]))

# date_modified may legitimately be None (no git, or the file untracked), but
# it must never be today's build date dressed up as the register's date.
import datetime as _dt                                    # noqa: E402
dm = facts["date_modified"]
check("date_modified is an ISO date or None",
      dm is None or len(dm) == 10 and dm[4] == dm[7] == "-", f"got {dm!r}")
check("date_modified is not simply today (that would be the build date)",
      dm is None or dm != _dt.date.today().isoformat(),
      "the register did not change today; if it did, re-run this test tomorrow")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the register's facts are computed from the register")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_register_meta.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.register_meta'`

- [ ] **Step 3: Write the implementation**

Create `tools/register_meta.py`:

```python
#!/usr/bin/env python3
"""The facts about the parameter register that published metadata states.

    ./.venv/bin/python3 tools/register_meta.py

Two consumers need the same three facts and must not compute them
differently: build.py, which writes the schema.org/Dataset block on
history.html, and tools/make_zenodo_deposit.py, which writes the Zenodo
metadata. Both import from here, so a new release changes one number in one
place and every published statement about the register follows.

The year span and the parameter list are read from data-exports/history.json
— the very file the Dataset says it distributes — rather than from the YAML.
Describing the file that is actually published is the honest choice: the
export canonicalises NuFit's Dm2_3l and Valencia's |Dm2_31| into the single
parameter Dm2, and it is that column a downloader gets.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "site-src" / "data" / "history.yaml"
EXPORT = ROOT / "data-exports" / "history.json"


def _last_commit_date() -> str | None:
    """The register's last commit date, as YYYY-MM-DD, or None.

    Not the build date. The site is rebuilt every morning by the 07:30 job;
    a dateModified of "today" would rewrite history.html on every run and
    fill the daily refresh commit with a diff whose only content is a date.

    The register carries no date field of its own, and the two alternatives
    are worse: a hand-maintained meta.updated: is a value somebody must
    remember to change, and a file mtime means nothing after a fresh clone.
    A commit date cannot rot and needs nobody to maintain it.

    None when git is unavailable or the file is untracked — the caller then
    omits the field rather than guessing one.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(REGISTER)],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    date = out.stdout.strip()
    # %cs is the committer date as YYYY-MM-DD. An empty result means the file
    # has no commits — a fresh working copy, or a rename not yet recorded.
    return date if len(date) == 10 and date[4] == date[7] == "-" else None


def register_facts() -> dict:
    """Year span, measured parameters, row count and last-changed date."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools import history

    doc = history.load()
    meta = (doc.get("meta") or {}).get("parameters") or {}

    rows = json.loads(EXPORT.read_text(encoding="utf-8"))["rows"]
    if not rows:
        raise SystemExit(f"{EXPORT} holds no rows — run tools/make_history_data.py")

    years = (min(r["year"] for r in rows), max(r["year"] for r in rows))

    # Sorted for a stable build: an unordered set would reshuffle the JSON-LD
    # from run to run and the daily commit would carry a phantom diff.
    variables = [
        {"name": name,
         "label": (meta.get(name) or {}).get("label", name),
         "unit": (meta.get(name) or {}).get("unit", "1")}
        for name in sorted({r["parameter"] for r in rows})
    ]

    return {
        "temporal_coverage": f"{years[0]}/{years[1]}",
        "years": years,
        "variables": variables,
        "date_modified": _last_commit_date(),
        "n_rows": len(rows),
    }


if __name__ == "__main__":
    facts = register_facts()
    print(json.dumps(facts, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_register_meta.py`
Expected: PASS, all checks ok. Also run `./.venv/bin/python3 tools/register_meta.py` and confirm by eye that it prints `"temporal_coverage": "2001/2026"`, six variables, and a `date_modified` that is not today.

- [ ] **Step 5: Commit**

```bash
git add tools/register_meta.py tools/tests/test_register_meta.py
git commit -m "The register's own facts, computed once for every consumer"
```

---

### Task 2: The Dataset block on the history page

**Files:**
- Modify: `site-src/templates/base.html` (add `{{head_extra}}` before `{{katex_head}}`, line 29)
- Modify: `build.py` (new `head_extra()` near `render_template`, around line 210; new ctx key in `build_pages`, around line 505)
- Modify: `site-src/site.yaml` (new `dataset:` block)
- Modify: `site-src/content/history.md` (front matter gains `jsonld: dataset`)
- Test: `tools/tests/test_metadata.py`

**Interfaces:**
- Consumes: `tools.register_meta.register_facts()` from Task 1
- Produces:
  - `build.py::head_extra(fm: dict, cfg: dict, url: str) -> str` — returns the `<script type="application/ld+json">` block and `citation_*` meta tags for a page, or `""`
  - `build.py::_json_ld(obj: dict) -> str` — serialises one JSON-LD object into a script element, safe to embed
  - `site.yaml` key `dataset` with sub-keys `doi`, `creator.name`, `creator.orcid`, `creator.affiliation`, `license`, `related.paper_doi`, `related.arxiv`

- [ ] **Step 1: Add the configuration block**

In `site-src/site.yaml`, after the `goatcounter:` block, add:

```yaml
# The citable parameter register: what the schema.org/Dataset block on
# history.html and the Zenodo deposit both say about it.
#
# doi is the Zenodo CONCEPT DOI — the one that always resolves to the newest
# version, not a per-version DOI. While it is empty the build emits no
# identifier, no citation_doi and no DOI line in llms.txt. That is deliberate
# and it is tested: a page states nothing it cannot support.
dataset:
  doi: ""
  creator:
    name: "Antonio Marrone"
    orcid: "0000-0001-6096-1880"
    affiliation: "Università di Bari and INFN Bari"
  license: "https://creativecommons.org/licenses/by/4.0/"
  related:
    paper_doi: "10.1103/PhysRevD.111.093006"
    arxiv: "2503.07752"
```

- [ ] **Step 2: Add the placeholder to the template**

In `site-src/templates/base.html`, change line 29 from:

```html
{{katex_head}}
```

to:

```html
{{head_extra}}
{{katex_head}}
```

- [ ] **Step 3: Opt the history page in**

In `site-src/content/history.md`, add one line to the front matter, after `katex: false`:

```yaml
jsonld: dataset
```

- [ ] **Step 4: Write the failing test**

Create `tools/tests/test_metadata.py`:

```python
#!/usr/bin/env python3
"""Check the structured metadata the site publishes about itself.

    ./.venv/bin/python3 tools/tests/test_metadata.py

A malformed JSON-LD block is invisible to the eye and mute to a crawler: the
page renders, the build succeeds, and the dataset simply never appears in
Google Dataset Search. Everything here is a guard against a silent failure.

Run build.py first — this reads the built tree, not the sources.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT))

from tools import register_meta                          # noqa: E402

CFG = yaml.safe_load((ROOT / "site-src" / "site.yaml").read_text(encoding="utf-8"))
DOI = (CFG.get("dataset") or {}).get("doi") or ""

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


LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def blocks(page: str) -> list[dict]:
    text = (SITE / page).read_text(encoding="utf-8")
    out = []
    for raw in LD.findall(text):
        out.append(json.loads(raw))
    return out


if not (SITE / "history.html").exists():
    check("site/ holds built pages", False,
          "run ./.venv/bin/python3 build.py first")
else:
    # --- history.html: the Dataset ---------------------------------------
    try:
        found = blocks("history.html")
        parsed = True
    except json.JSONDecodeError as exc:
        found, parsed = [], False
        check("history.html JSON-LD parses", False, str(exc))
    if parsed:
        check("history.html JSON-LD parses", True)

    ds = next((b for b in found if b.get("@type") == "Dataset"), None)
    check("history.html carries a Dataset block", ds is not None,
          f"found types {[b.get('@type') for b in found]}")

    if ds:
        for field in ("@context", "name", "description", "url", "license",
                      "creator", "distribution", "temporalCoverage",
                      "variableMeasured"):
            check(f"Dataset has {field}", field in ds)

        check("Dataset licence is CC BY 4.0",
              ds.get("license") == "https://creativecommons.org/licenses/by/4.0/",
              str(ds.get("license")))

        # Every distributed file must actually be there. This is the case
        # where an export is renamed and the metadata quietly points at
        # nothing — a 404 that only a machine ever sees.
        for dist in ds.get("distribution", []):
            url = dist.get("contentUrl", "")
            rel = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
            check(f"distribution exists: {rel}", (SITE / rel).exists(), url)

        facts = register_meta.register_facts()
        check("temporalCoverage is the register's, not a typed one",
              ds.get("temporalCoverage") == facts["temporal_coverage"],
              f"page {ds.get('temporalCoverage')!r} vs register "
              f"{facts['temporal_coverage']!r}")

        page_vars = {v.get("name") for v in ds.get("variableMeasured", [])}
        reg_vars = {v["name"] for v in facts["variables"]}
        check("variableMeasured is the register's parameter list",
              page_vars == reg_vars, f"page {sorted(page_vars)} vs register "
                                     f"{sorted(reg_vars)}")

        if facts["date_modified"]:
            check("dateModified is the register's commit date, not the build date",
                  ds.get("dateModified") == facts["date_modified"],
                  f"page {ds.get('dateModified')!r} vs git "
                  f"{facts['date_modified']!r}")

    # --- the DOI, present or absent, must be consistent everywhere -------
    hist = (SITE / "history.html").read_text(encoding="utf-8")
    if DOI:
        check("configured DOI has the shape 10.xxxx/...",
              re.fullmatch(r"10\.\d{4,9}/\S+", DOI) is not None, DOI)
        check("history.html declares citation_doi",
              f'name="citation_doi" content="{DOI}"' in hist)
        check("Dataset carries the DOI as identifier",
              bool(ds) and DOI in json.dumps(ds))
    else:
        check("with no DOI configured, no citation_doi is emitted",
              "citation_doi" not in hist,
              "the page is claiming an identifier that does not exist")
        check("with no DOI configured, the Dataset has no identifier",
              not bool(ds) or "identifier" not in ds)

    # --- citation_* belongs on the dataset page and nowhere else ---------
    for page in sorted(SITE.glob("*.html")):
        has = "citation_title" in page.read_text(encoding="utf-8")
        if page.name == "history.html":
            check("history.html carries citation_* tags", has)
        else:
            check(f"{page.name} carries no citation_* tags", not has,
                  "Google Scholar would index it as a separate scholarly work")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the published metadata says what the data says")
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `./.venv/bin/python3 build.py && ./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: FAIL — `history.html carries a Dataset block` fails, because nothing emits one yet.

- [ ] **Step 6: Write the implementation**

In `build.py`, immediately after `render_template` (line 209), add:

```python
def _json_ld(obj: dict) -> str:
    """One JSON-LD object, as a script element that cannot break the page.

    A literal "</script>" inside any string would end the element early and
    spill JSON into the document as text. Escaping "<" as \\u003c is valid
    JSON, changes no value, and removes the whole class of problem. The same
    reasoning as the html.escape() on title and description below.
    """
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("<", "\\u003c")
    return f'<script type="application/ld+json">{body}</script>'


def head_extra(fm: dict, cfg: dict, url: str) -> str:
    """Structured metadata for the pages that ask for it in their front matter.

    Opt-in per page (`jsonld: dataset` / `jsonld: site`), because these blocks
    describe a specific object and a block that describes the wrong thing is
    worse than none. An unrecognised value is a build error rather than a
    silent empty string: a typo that removes the site's structured metadata
    would otherwise be found by an audit months later, if at all.
    """
    kind = fm.get("jsonld")
    if not kind:
        return ""
    if kind not in ("dataset", "site"):
        sys.exit(f"{url}: unknown 'jsonld: {kind}' — expected 'dataset' or 'site'")
    if kind == "dataset":
        return _dataset_head(fm, cfg, url)
    return _site_head(cfg)


def _dataset_head(fm: dict, cfg: dict, url: str) -> str:
    from tools import register_meta

    facts = register_meta.register_facts()
    ds_cfg = cfg.get("dataset") or {}
    creator = ds_cfg.get("creator") or {}
    base = cfg["site_url"]
    doi = (ds_cfg.get("doi") or "").strip()

    person = {"@type": "Person", "name": creator.get("name", "")}
    if creator.get("orcid"):
        person["identifier"] = f"https://orcid.org/{creator['orcid']}"
        person["sameAs"] = f"https://orcid.org/{creator['orcid']}"
    if creator.get("affiliation"):
        person["affiliation"] = {"@type": "Organization",
                                 "name": creator["affiliation"]}

    obj = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": fm.get("title", ""),
        "description": " ".join((fm.get("description") or "").split()),
        "url": f"{base}/{url}",
        "license": ds_cfg.get("license", ""),
        "isAccessibleForFree": True,
        "creator": person,
        "temporalCoverage": facts["temporal_coverage"],
        "variableMeasured": [
            {"@type": "PropertyValue", "name": v["name"],
             "alternateName": v["label"], "unitText": v["unit"]}
            for v in facts["variables"]
        ],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": f"{base}/data/history.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "contentUrl": f"{base}/data/history.csv"},
        ],
    }
    # Absent, not empty: with no deposit there is no identifier to state.
    if facts["date_modified"]:
        obj["dateModified"] = facts["date_modified"]
    if doi:
        obj["identifier"] = f"https://doi.org/{doi}"

    tags = [
        ("citation_title", fm.get("title", "")),
        ("citation_author", creator.get("name", "")),
        ("citation_public_url", f"{base}/{url}"),
    ]
    if facts["date_modified"]:
        tags.append(("citation_publication_date",
                     facts["date_modified"].replace("-", "/")))
    if doi:
        tags.append(("citation_doi", doi))

    meta = "\n".join(
        f'<meta name="{n}" content="{html.escape(str(v), quote=True)}">'
        for n, v in tags if v)
    return _json_ld(obj) + "\n" + meta


def _site_head(cfg: dict) -> str:
    base = cfg["site_url"]
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Bari neutrino global analysis group",
        "url": base,
        "parentOrganization": [
            {"@type": "Organization", "name": "Università degli Studi di Bari Aldo Moro"},
            {"@type": "Organization", "name": "INFN, Sezione di Bari"},
        ],
    }
    site = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": cfg["site_name"],
        "url": base,
        "description": cfg.get("tagline", ""),
        "publisher": {"@type": "Organization",
                      "name": "Bari neutrino global analysis group"},
    }
    return _json_ld(org) + "\n" + _json_ld(site)
```

Confirm `import json`, `import html` and `import sys` are already at the top of `build.py` (they are — `json` is used by the asset-version hashing, `html` by the front-matter escaping, `sys` by the argument handling). Add `from pathlib import Path`-style imports only if a check shows one missing.

Then, in `build_pages`, add one key to the `render_template` context dict (around line 505, beside `"katex_head"`):

```python
            "head_extra": head_extra(fm, cfg, url),
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `./.venv/bin/python3 build.py && ./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: PASS. The `_site_head` checks are not exercised yet — Task 3 opts `index.md` in.

- [ ] **Step 8: Verify the block by eye**

Run:

```bash
./.venv/bin/python3 - <<'PY'
import json, re, pathlib
m = re.search(r'<script type="application/ld\+json">(.*?)</script>',
              pathlib.Path("site/history.html").read_text(), re.S)
print(json.dumps(json.loads(m.group(1)), indent=2, ensure_ascii=False))
PY
```

Expected: a `Dataset` with `temporalCoverage: "2001/2026"`, six `variableMeasured` entries, two `distribution` entries, **no** `identifier`.

- [ ] **Step 9: Commit**

```bash
git add build.py site-src/templates/base.html site-src/site.yaml \
        site-src/content/history.md tools/tests/test_metadata.py site/
git commit -m "Say, in a form a machine reads, that the register is a dataset"
```

---

### Task 3: Who publishes the site

**Files:**
- Modify: `site-src/content/index.md` (front matter gains `jsonld: site`)
- Modify: `tools/tests/test_metadata.py` (checks for the home page blocks)

**Interfaces:**
- Consumes: `build.py::_site_head(cfg)` from Task 2 — already written, not yet reached by any page

- [ ] **Step 1: Write the failing test**

In `tools/tests/test_metadata.py`, immediately before the `# --- citation_* belongs on the dataset page` section, insert:

```python
    # --- index.html: who publishes this -----------------------------------
    home = blocks("index.html")
    types = {b.get("@type") for b in home}
    check("index.html carries an Organization block", "Organization" in types,
          f"found {sorted(t for t in types if t)}")
    check("index.html carries a WebSite block", "WebSite" in types,
          f"found {sorted(t for t in types if t)}")
    for b in home:
        check(f"{b.get('@type')} on index.html names its url",
              b.get("url") == CFG["site_url"], str(b.get("url")))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: FAIL — `index.html carries an Organization block`, found `[]`.

- [ ] **Step 3: Opt the home page in**

In `site-src/content/index.md`, add one line to the front matter after `katex: false`:

```yaml
jsonld: site
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 build.py && ./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add site-src/content/index.md tools/tests/test_metadata.py site/
git commit -m "Name the group that publishes the site, on the home page"
```

---

### Task 4: The crawler policy, as reviewable text

**Files:**
- Create: `site-src/robots.txt`
- Modify: `build.py:619-621` (write the source file instead of an f-string)
- Modify: `tools/tests/test_metadata.py`

**Interfaces:**
- Produces: `site/robots.txt` — the source file verbatim, with a trailing `Sitemap:` line derived from `site_url`

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_metadata.py`, before the final `print()` block:

```python
# --- robots.txt: the policy is a position, not an omission ----------------
AI_AGENTS = [
    # Training crawlers — allowed, because CC BY 4.0 already grants this and
    # declining it here would contradict the licence the data carries.
    "GPTBot", "ClaudeBot", "anthropic-ai", "Google-Extended", "CCBot",
    "Bytespider", "Applebot-Extended", "Meta-ExternalAgent", "Amazonbot",
    "cohere-ai",
    # Retrieval agents — fetch a page to answer a question, and cite it.
    "OAI-SearchBot", "ChatGPT-User", "Claude-User", "Claude-SearchBot",
    "PerplexityBot", "Perplexity-User", "Meta-ExternalFetcher",
    # Ordinary search engines.
    "Googlebot", "Bingbot", "DuckDuckBot", "Applebot",
]

robots = (SITE / "robots.txt").read_text(encoding="utf-8")
for agent in AI_AGENTS:
    check(f"robots.txt names {agent}",
          re.search(rf"^User-agent: {re.escape(agent)}$", robots, re.M) is not None,
          "the declared policy allows it, so it must be named explicitly")

denies = [ln for ln in robots.splitlines()
          if ln.strip().lower().startswith("disallow:") and ln.split(":", 1)[1].strip()]
check("robots.txt blocks nobody", not denies,
      f"the site's stated policy is open; found {denies}")

check("robots.txt points at the sitemap",
      f"Sitemap: {CFG['site_url']}/sitemap.xml" in robots)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: FAIL — `robots.txt names GPTBot` and every other agent, because the built file is still the three-line wildcard.

- [ ] **Step 3: Write the source file**

Create `site-src/robots.txt`:

```
# global-nu.org — crawler policy.
#
# Everything here is public. The parameter register and the files under /data/
# are CC BY 4.0: reuse them, including for training a model, and attribute
# them. Declining by robots.txt what the licence already grants would be
# incoherent, so the AI crawlers are named and allowed one by one instead of
# being left covered by the wildcard. This is a position the site has taken,
# not an omission it has fallen into.
#
# What we ask in return is attribution, and robots.txt has no field for it.
# It is stated in /llms.txt and on /about.html#licence.
#
# tools/tests/test_metadata.py fails if a name below goes missing, or if any
# rule in this file is anything other than Allow.

User-agent: *
Allow: /

# --- search engines ------------------------------------------------------
User-agent: Googlebot
Allow: /

User-agent: Bingbot
Allow: /

User-agent: DuckDuckBot
Allow: /

User-agent: Applebot
Allow: /

# --- AI crawlers gathering training corpora ------------------------------
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: Bytespider
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Meta-ExternalAgent
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: cohere-ai
Allow: /

# --- AI agents that fetch a page to answer a question, and cite it -------
User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: Claude-User
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Perplexity-User
Allow: /

User-agent: Meta-ExternalFetcher
Allow: /
```

- [ ] **Step 4: Write the implementation**

In `build.py`, replace lines 619-621:

```python
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {cfg['site_url']}/sitemap.xml\n",
        encoding="utf-8")
```

with:

```python
    # The crawler policy is data, not a string in the middle of code: the list
    # of named agents is a public position of this site and has to be
    # reviewable in a diff. Only the Sitemap line is derived, so the domain
    # stays defined in exactly one place (site_url).
    robots = (SRC / "robots.txt").read_text(encoding="utf-8").rstrip("\n")
    (OUT / "robots.txt").write_text(
        f"{robots}\n\nSitemap: {cfg['site_url']}/sitemap.xml\n", encoding="utf-8")
```

`SRC` is the `site-src/` path constant already defined near the top of `build.py`. If it is named differently there, use the existing name — do not add a second constant for the same directory.

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 build.py && ./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: PASS. Confirm `site/robots.txt` ends with the `Sitemap:` line and that `site-src/robots.txt` does not contain it.

- [ ] **Step 6: Commit**

```bash
git add site-src/robots.txt build.py tools/tests/test_metadata.py site/robots.txt
git commit -m "Name the crawlers and allow them, instead of allowing by omission"
```

---

### Task 5: `llms.txt`

**Files:**
- Create: `site-src/llms.txt`
- Modify: `build.py` (write it beside `robots.txt` in `main()`)
- Modify: `tools/tests/test_metadata.py`

**Interfaces:**
- Consumes: `build.py::render_template(tpl, ctx)` — the same `{{key}}` substitution the pages use
- Produces: `site/llms.txt`

- [ ] **Step 1: Write the failing test**

Append to `tools/tests/test_metadata.py`, before the final `print()` block:

```python
# --- llms.txt -------------------------------------------------------------
llms_path = SITE / "llms.txt"
check("llms.txt is published", llms_path.exists())
if llms_path.exists():
    llms = llms_path.read_text(encoding="utf-8")
    check("llms.txt has no unsubstituted placeholder", "{{" not in llms,
          "a template placeholder reached the published root")
    check("llms.txt states the licence",
          "creativecommons.org/licenses/by/4.0" in llms)
    check("llms.txt points at both data files",
          "/data/history.json" in llms and "/data/history.csv" in llms)
    if DOI:
        check("llms.txt states the DOI", DOI in llms)
    else:
        check("with no DOI configured, llms.txt claims none",
              "doi.org" not in llms.lower())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: FAIL — `llms.txt is published`.

- [ ] **Step 3: Write the source file**

Create `site-src/llms.txt`:

```
# global-nu

> {{tagline}}

The site of the Bari group's global analyses of neutrino oscillation data.
{{site_url}}

## What is here

- Results: the most recent full release of the global analysis — best fits and
  allowed ranges for the six three-flavour oscillation parameters.
- Parameter history: how those parameters moved across a quarter century of
  published global fits by three independent groups — Bari, NuFit and Valencia
  — with every value traced to the table of the paper that printed it, and the
  conversions between the groups' conventions documented and tested.
- arXiv digest, News and Conferences: regenerated every morning by a local job,
  each marked as automatically generated with the time of its last update.

## The data

The parameter register is published in full, in two formats:

- {{site_url}}/data/history.json
- {{site_url}}/data/history.csv

Both are licensed CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/
{{dataset_doi_line}}

## What we ask

Use it. Quote it. Train on it. The licence asks one thing in return, and this
file is the only place a model reads it: attribute the parameter register to
{{creator_name}} and the Bari group, and cite it by the identifier above where
there is one, by {{site_url}}/history.html where there is not.

If you state one of these numbers, state also which paper and which table it
came from — every row carries both. A value repeated without its provenance is
how a transcription error becomes a fact.

## What is not ours to license

The photographs on the conferences page belong to their authors and carry
their own credits and licences, shown on each card. The figures reproduced
from published papers carry the licence of the paper. See
{{site_url}}/about.html#licence
```

- [ ] **Step 4: Write the implementation**

In `build.py`'s `main()`, immediately after the `robots.txt` write added in Task 4, add:

```python
    # llms.txt: not a standard, and no vendor has committed to honouring it.
    # It costs one small file, and it is the only place where the attribution
    # the CC BY licence requires is stated in a form a model reads. The DOI
    # line is absent, not empty, until there is a deposit to point at.
    ds_cfg = cfg.get("dataset") or {}
    doi = (ds_cfg.get("doi") or "").strip()
    (OUT / "llms.txt").write_text(render_template(
        (SRC / "llms.txt").read_text(encoding="utf-8"), {
            "site_url": cfg["site_url"],
            "tagline": cfg.get("tagline", ""),
            "creator_name": (ds_cfg.get("creator") or {}).get("name", ""),
            "dataset_doi_line":
                f"\nPermanent identifier: https://doi.org/{doi}\n" if doi else "",
        }), encoding="utf-8")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/python3 build.py && ./.venv/bin/python3 tools/tests/test_metadata.py`
Expected: PASS. Read `site/llms.txt` and confirm it reads as prose, with no blank gap where the DOI line will go.

- [ ] **Step 6: Commit**

```bash
git add site-src/llms.txt build.py tools/tests/test_metadata.py site/llms.txt
git commit -m "Ask, where a model will read it, for the attribution the licence requires"
```

---

### Task 6: Prove the site is correct with a DOI, before there is one

The DOI arrives last, but the code that handles it must be tested now — after the deposit is the worst moment to discover that a DOI breaks the build. This task exercises both states without minting anything.

**Files:**
- Create: `tools/tests/test_metadata_with_doi.py`

**Interfaces:**
- Consumes: everything from Tasks 2–5

- [ ] **Step 1: Write the test**

Create `tools/tests/test_metadata_with_doi.py`:

```python
#!/usr/bin/env python3
"""Build the site with a DOI configured, and check every claim it enables.

    ./.venv/bin/python3 tools/tests/test_metadata_with_doi.py

The real DOI arrives only after the Zenodo deposit, and the moment after a
permanent identifier is minted is the worst moment to discover that the build
mishandles it. This builds into a throwaway tree with a placeholder DOI in
site.yaml, so both states — with and without — are covered before the deposit
is made. It never touches site/ and never writes a DOI into the real config.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FAKE_DOI = "10.5281/zenodo.9999999"

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


cfg_path = ROOT / "site-src" / "site.yaml"
original = cfg_path.read_text(encoding="utf-8")
work = Path(tempfile.mkdtemp(prefix="gnu-doi-"))

try:
    doc = yaml.safe_load(original)
    doc.setdefault("dataset", {})["doi"] = FAKE_DOI
    cfg_path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")

    run = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python3"), "build.py",
         "--out", str(work), "--no-images"],
        cwd=ROOT, capture_output=True, text=True)
    check("the build succeeds with a DOI configured", run.returncode == 0,
          (run.stderr or run.stdout)[-800:])

    if run.returncode == 0:
        hist = (work / "history.html").read_text(encoding="utf-8")
        check("citation_doi is emitted",
              f'name="citation_doi" content="{FAKE_DOI}"' in hist)

        block = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', hist, re.S)
        ds = json.loads(block.group(1)) if block else {}
        check("the Dataset identifier is the DOI URL",
              ds.get("identifier") == f"https://doi.org/{FAKE_DOI}",
              str(ds.get("identifier")))

        llms = (work / "llms.txt").read_text(encoding="utf-8")
        check("llms.txt states the DOI", FAKE_DOI in llms)
        check("llms.txt has no unsubstituted placeholder", "{{" not in llms)
finally:
    cfg_path.write_text(original, encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)

check("site.yaml is restored unchanged",
      cfg_path.read_text(encoding="utf-8") == original,
      "the real config was left modified — fix this before committing")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the site is correct with a DOI and without one")
```

- [ ] **Step 2: Check the build accepts `--out`**

Run: `./.venv/bin/python3 build.py --help`

If there is no `--out` flag, add one next to the existing `--drafts` / `--clean` / `--no-images` arguments, defaulting to `site/`, and assign it to the module-level `OUT` in `main()` exactly as `--drafts` already reassigns `OUT` to `OUT_DRAFT` (see `build.py:594`). Do not restructure the argument handling for this.

- [ ] **Step 3: Run the test**

Run: `./.venv/bin/python3 tools/tests/test_metadata_with_doi.py`
Expected: PASS, and `git status` must show `site-src/site.yaml` unmodified afterwards.

- [ ] **Step 4: Confirm the real tree is untouched**

Run: `git status --short`
Expected: no modification to `site-src/site.yaml`, nothing new under `site/`.

- [ ] **Step 5: Commit**

```bash
git add tools/tests/test_metadata_with_doi.py build.py
git commit -m "Test the site with a DOI before minting one, not after"
```

---

### Task 7: The deposit package

**Files:**
- Create: `tools/make_zenodo_deposit.py`
- Test: `tools/tests/test_zenodo_deposit.py`

**Interfaces:**
- Consumes: `tools.register_meta.register_facts()`; `tools/make_history_data.py::FIELD_DOCS` (list of `(name, html_description)` pairs, asserted in that module to match `FIELDS`); `site-src/site.yaml` key `dataset`
- Produces:
  - `build_package(out_dir: Path) -> dict` — writes the package and returns the Zenodo metadata dict
  - a directory containing `history.json`, `history.csv`, `README.md`, `LICENSE.txt`, `zenodo.json`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_zenodo_deposit.py`:

```python
#!/usr/bin/env python3
"""Check the Zenodo package before anything permanent is minted.

    ./.venv/bin/python3 tools/tests/test_zenodo_deposit.py

A DOI cannot be withdrawn. Everything a deposit will assert is checked here,
against the register itself, while it is still only a directory on disk.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import register_meta                          # noqa: E402
import make_zenodo_deposit                                # noqa: E402
import make_history_data                                  # noqa: E402

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


work = Path(tempfile.mkdtemp(prefix="gnu-zenodo-"))
try:
    meta = make_zenodo_deposit.build_package(work)
    facts = register_meta.register_facts()

    for name in ("history.json", "history.csv", "README.md", "LICENSE.txt",
                 "zenodo.json"):
        check(f"package contains {name}", (work / name).exists())

    check("upload_type is dataset", meta["upload_type"] == "dataset")
    check("the title carries the register's real year span",
          f"({facts['years'][0]}–{facts['years'][1]})" in meta["title"],
          meta["title"])

    creators = meta.get("creators") or []
    check("one creator, with an ORCID", len(creators) == 1 and creators[0].get("orcid"),
          str(creators))
    check("the ORCID is Antonio's",
          creators and creators[0].get("orcid") == "0000-0001-6096-1880",
          str(creators))

    check("licence is CC BY 4.0", meta.get("license") == "cc-by-4.0",
          str(meta.get("license")))

    rel = {r["identifier"] for r in meta.get("related_identifiers", [])}
    check("the deposit is bound to the 2025 paper",
          "10.1103/PhysRevD.111.093006" in rel, str(sorted(rel)))
    check("the deposit is bound to the site",
          any("global-nu.org" in r for r in rel), str(sorted(rel)))

    # The README must describe exactly the columns the files actually carry,
    # and it is generated from FIELD_DOCS so it cannot drift. Check that the
    # generation really happened rather than trusting it.
    readme = (work / "README.md").read_text(encoding="utf-8")
    for field, _ in make_history_data.FIELD_DOCS:
        check(f"README documents the column {field}", f"`{field}`" in readme)
    check("README carries no HTML tags from the page version",
          "<code>" not in readme and "<a " not in readme,
          "FIELD_DOCS is HTML for the web page; it must be converted for a text README")

    check("the deposited JSON is the published export",
          (work / "history.json").read_bytes() == register_meta.EXPORT.read_bytes())

    payload = json.loads((work / "zenodo.json").read_text(encoding="utf-8"))
    check("zenodo.json holds the same metadata that was returned",
          payload.get("metadata", payload) == meta)
finally:
    shutil.rmtree(work, ignore_errors=True)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — the package says what the register says")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python3 tools/tests/test_zenodo_deposit.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'make_zenodo_deposit'`

- [ ] **Step 3: Write the implementation**

Create `tools/make_zenodo_deposit.py`:

```python
#!/usr/bin/env python3
"""Assemble the Zenodo deposit for the parameter register.

    ./.venv/bin/python3 tools/make_zenodo_deposit.py            # build only
    ./.venv/bin/python3 tools/make_zenodo_deposit.py --sandbox --token TOKEN

By default this touches no network at all: it writes the package into
var/zenodo/ and prints what to upload. --sandbox rehearses the whole round
trip against sandbox.zenodo.org, which mints throwaway DOIs and can be got
wrong as many times as needed.

The real deposit is made by hand, from Antonio's account, and this script has
no flag that makes one. A DOI cannot be withdrawn: minting one is a decision
a person takes, not a side effect of running a tool.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import register_meta                          # noqa: E402
import make_history_data                                  # noqa: E402

OUT_DIR = ROOT / "var" / "zenodo"
CFG = ROOT / "site-src" / "site.yaml"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode.txt"

TITLE = ("Published global-fit values of the three-flavour neutrino "
         "oscillation parameters, with provenance and convention "
         "conversions ({lo}–{hi})")

DESCRIPTION = """\
<p>A register of the three-flavour neutrino oscillation parameters as
published by three independent global analyses &mdash; Bari, NuFit and
Valencia &mdash; across {span}. It holds {n} values covering {nvars}
parameters.</p>

<p>Every value is transcribed by hand from the table of the paper that
printed it, and each row names that paper and that table. No value is
interpolated, averaged, read off a figure, or carried over from another
release. Each row carries the number twice: <code>value_as_published</code>,
exactly as the paper printed it in its own convention and normalisation, and
<code>value_our_convention</code>, the same quantity in the Bari convention
&delta;m&sup2; = m&#8322;&sup2; &minus; m&#8321;&sup2; and
&Delta;m&sup2; = m&#8323;&sup2; &minus; (m&#8321;&sup2; + m&#8322;&sup2;)/2.
Only &Delta;m&sup2; is ever converted, because it is the only quantity the
three groups report differently.</p>

<p>The register is the source of the parameter-history page at
<a href="{url}/history.html">{url}/history.html</a>, where every field is
documented. See README.md in this deposit for the same documentation.</p>
"""


def _cfg() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


def _plain(html_text: str) -> str:
    """FIELD_DOCS is written as HTML for the web page. Make it text.

    The README must describe exactly the columns the exports carry, so it is
    generated from the same FIELD_DOCS the page uses rather than written
    again here — a second copy would start out identical and end up wrong.
    """
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", html_text, flags=re.S)
    text = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", text,
                  flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _readme(facts: dict, cfg: dict, meta: dict) -> str:
    lines = [
        f"# {meta['title']}",
        "",
        f"{facts['n_rows']} values, {facts['years'][0]}–{facts['years'][1]}, "
        f"from the Bari, NuFit and Valencia global analyses.",
        "",
        "Published, with the page that documents it, at "
        f"{cfg['site_url']}/history.html",
        "",
        "## Files",
        "",
        "- `history.json` — the register, as an object with a `note` and a "
        "`rows` array.",
        "- `history.csv` — the same rows, one per line, same column names.",
        "",
        "## Columns",
        "",
    ]
    for name, doc in make_history_data.FIELD_DOCS:
        lines.append(f"- `{name}` — {_plain(doc)}")
    lines += [
        "",
        "## Parameters",
        "",
    ]
    for v in facts["variables"]:
        lines.append(f"- `{v['name']}` — {v['label']}, in units of {v['unit']}")
    lines += [
        "",
        "## Licence",
        "",
        "CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
        "",
        "Attribute the register to "
        f"{(cfg.get('dataset') or {}).get('creator', {}).get('name', '')} and the "
        "Bari group. If you state one of these numbers, state also the paper "
        "and the table it came from — every row carries both.",
        "",
    ]
    return "\n".join(lines)


def build_package(out_dir: Path) -> dict:
    """Write the deposit package into out_dir and return its metadata."""
    facts = register_meta.register_facts()
    cfg = _cfg()
    ds = cfg.get("dataset") or {}
    creator = ds.get("creator") or {}
    related = ds.get("related") or {}
    lo, hi = facts["years"]

    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "upload_type": "dataset",
        "title": TITLE.format(lo=lo, hi=hi),
        "version": "1.0.0",
        "language": "eng",
        "creators": [{
            "name": "Marrone, Antonio",
            "orcid": creator.get("orcid", ""),
            "affiliation": creator.get("affiliation", ""),
        }],
        "description": DESCRIPTION.format(
            span=f"{lo}–{hi}", n=facts["n_rows"],
            nvars=len(facts["variables"]), url=cfg["site_url"]),
        "license": "cc-by-4.0",
        "access_right": "open",
        "keywords": [
            "neutrino oscillations", "global fit", "neutrino mass ordering",
            "mixing angles", "CP violation phase", "three-flavour oscillations",
        ],
        "related_identifiers": [
            {"identifier": f"{cfg['site_url']}/history.html",
             "relation": "isDocumentedBy", "resource_type": "publication-webpage",
             "scheme": "url"},
            {"identifier": related.get("paper_doi", ""),
             "relation": "isSupplementTo", "resource_type": "publication-article",
             "scheme": "doi"},
            {"identifier": f"arXiv:{related.get('arxiv', '')}",
             "relation": "isSupplementTo", "resource_type": "publication-preprint",
             "scheme": "arxiv"},
        ],
    }
    if facts["date_modified"]:
        meta["publication_date"] = facts["date_modified"]

    shutil.copyfile(register_meta.EXPORT, out_dir / "history.json")
    shutil.copyfile(register_meta.EXPORT.with_suffix(".csv"), out_dir / "history.csv")
    (out_dir / "README.md").write_text(_readme(facts, cfg, meta), encoding="utf-8")
    (out_dir / "LICENSE.txt").write_text(
        "This dataset is licensed CC BY 4.0.\n"
        f"Full text: {LICENCE_URL}\n\n"
        "Attribute the parameter register to Antonio Marrone and the Bari "
        "group, and cite it by its DOI.\n", encoding="utf-8")
    (out_dir / "zenodo.json").write_text(
        json.dumps({"metadata": meta}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return meta


def rehearse(pkg: Path, token: str) -> None:
    """Run the whole deposit against sandbox.zenodo.org. Never the real one."""
    import urllib.request

    base = "https://sandbox.zenodo.org/api/deposit/depositions"

    def call(url: str, data: bytes | None, method: str, ctype: str) -> dict:
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        if ctype:
            req.add_header("Content-Type", ctype)
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        return json.loads(body) if body else {}

    dep = call(base, b"{}", "POST", "application/json")
    print(f"  sandbox deposition {dep['id']} created")
    bucket = dep["links"]["bucket"]
    for name in ("history.json", "history.csv", "README.md", "LICENSE.txt"):
        call(f"{bucket}/{name}", (pkg / name).read_bytes(), "PUT",
             "application/octet-stream")
        print(f"  uploaded {name}")
    payload = json.loads((pkg / "zenodo.json").read_text(encoding="utf-8"))
    call(f"{base}/{dep['id']}", json.dumps(payload).encode(), "PUT",
         "application/json")
    print(f"  metadata accepted — review it at {dep['links']['html']}")
    print("  NOT published: publishing is done by hand, on the real Zenodo.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--sandbox", action="store_true",
                    help="rehearse against sandbox.zenodo.org (needs --token)")
    ap.add_argument("--token", default="", help="a sandbox.zenodo.org API token")
    args = ap.parse_args()

    meta = build_package(args.out)
    print(f"package written to {args.out}")
    print(f"  title:   {meta['title']}")
    print(f"  version: {meta['version']}")
    print(f"  files:   history.json, history.csv, README.md, LICENSE.txt")
    print(f"  metadata: {args.out / 'zenodo.json'}")

    if args.sandbox:
        if not args.token:
            sys.exit("--sandbox needs --token (make one at sandbox.zenodo.org)")
        rehearse(args.out, args.token)
    else:
        print("\nNo network was touched. To rehearse:  --sandbox --token TOKEN")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python3 tools/tests/test_zenodo_deposit.py`
Expected: PASS.

- [ ] **Step 5: Build the package and read it**

Run: `./.venv/bin/python3 tools/make_zenodo_deposit.py`

Then read `var/zenodo/README.md` end to end and confirm every column description reads as English prose with no HTML left in it, and `var/zenodo/zenodo.json` for the title and the related identifiers.

- [ ] **Step 6: Keep the package out of git**

Confirm `var/` is already ignored (`.gitignore` covers it — check with `git check-ignore -v var/zenodo/zenodo.json`). If it is not, add `var/` to `.gitignore` in this commit.

- [ ] **Step 7: Commit**

```bash
git add tools/make_zenodo_deposit.py tools/tests/test_zenodo_deposit.py
git commit -m "Assemble the Zenodo deposit, and mint nothing"
```

---

### Task 8: Rehearse, deposit, and wire the DOI in

This task has a manual gate in the middle. **Do not attempt the real deposit** — it is made by Antonio, from his own account.

**Files:**
- Modify: `site-src/site.yaml` (the `dataset.doi` line, once)
- Modify: `README.md` (a line about the DOI in the data section)

- [ ] **Step 1: Rehearse against the sandbox**

Ask Antonio for a token from `sandbox.zenodo.org` (Applications → Personal access tokens, scopes `deposit:write` and `deposit:actions`). Then:

```bash
./.venv/bin/python3 tools/make_zenodo_deposit.py --sandbox --token "$TOKEN"
```

Expected: a deposition is created, four files upload, the metadata is accepted, and a review URL is printed. Open it and check the title, the creator with the ORCID, the licence, and the three related identifiers. Repeat until clean.

- [ ] **Step 2: Hand the package to Antonio — STOP HERE**

Report: the sandbox run is clean, the package is at `var/zenodo/`, and the metadata to paste is in `var/zenodo/zenodo.json`. He makes the real deposit at `zenodo.org` from his own account and sends back the **concept DOI** — the one Zenodo labels "Cite all versions", not the version DOI.

Do not proceed past this step without that DOI.

- [ ] **Step 3: Wire it in**

In `site-src/site.yaml`, set the one line:

```yaml
  doi: "10.5281/zenodo.XXXXXXX"    # the concept DOI Antonio sends back
```

- [ ] **Step 4: Rebuild and run every metadata test**

```bash
./.venv/bin/python3 build.py
./.venv/bin/python3 tools/tests/test_register_meta.py
./.venv/bin/python3 tools/tests/test_metadata.py
./.venv/bin/python3 tools/tests/test_zenodo_deposit.py
```

Expected: all pass, and `test_metadata.py` now takes the `if DOI:` branch — confirm by eye that it printed `configured DOI has the shape 10.xxxx/...` rather than the two "with no DOI configured" lines.

- [ ] **Step 5: Check the DOI resolves**

```bash
curl -sI "https://doi.org/$(./.venv/bin/python3 -c "import yaml,pathlib;print(yaml.safe_load(pathlib.Path('site-src/site.yaml').read_text())['dataset']['doi'])")" | head -3
```

Expected: `301` or `302` to a `zenodo.org/records/...` URL. A `404` means the DOI is wrong or not yet registered — DataCite registration can lag the deposit by a few minutes.

- [ ] **Step 6: Update the README**

In `README.md`, in the paragraph describing the parameter history, add a sentence naming the DOI and that the register is citable independently of the domain.

- [ ] **Step 7: Commit and publish**

```bash
git add site-src/site.yaml README.md site/
git commit -m "The register has a DOI, and every page that can say so does"
```

Then publish as the project always does — `git push`, then
`git subtree push --prefix site origin gh-pages`.

- [ ] **Step 8: Verify on the live page, not only locally**

```bash
curl -s https://global-nu.org/history.html | grep -o 'application/ld+json' | head -1
curl -s https://global-nu.org/llms.txt | head -20
curl -s https://global-nu.org/robots.txt | grep -c '^User-agent:'
```

Expected: the JSON-LD script is present on the live page, `llms.txt` carries the DOI line, and `robots.txt` names 22 user agents. Paste the live `history.html` into Google's Rich Results Test and confirm it reports a Dataset with no errors.

---

## Self-review

**Spec coverage.** Every section of the design maps to a task: the Dataset JSON-LD and `citation_*` to Task 2; `Organization`/`WebSite` to Task 3; `robots.txt` to Task 4; `llms.txt` to Task 5; the computed facts and the `dateModified` reasoning to Task 1; the deposit tool, the generated README and the sandbox rehearsal to Tasks 7 and 8; the "no DOI means no claim" rule to Tasks 2, 5 and 6. The spec's out-of-scope list is respected: no task touches `results.html`, none adds a software DOI, and none puts a deposit in the daily job.

**Placeholders.** None. Every code step carries the code; every test step carries the assertions and the command that runs them.

**Type consistency.** `register_facts()` returns the same five keys wherever it is consumed (`temporal_coverage`, `years`, `variables`, `date_modified`, `n_rows`); `build_package(out_dir) -> dict` is called with a `Path` and its return is compared against `zenodo.json` in the test; `head_extra(fm, cfg, url)` is defined and called with exactly those three arguments.

**One thing Task 6 may have to add.** `build.py` may not accept `--out`. Step 2 of that task checks, and adds it in the existing argument-handling style if missing, rather than assuming either way.
