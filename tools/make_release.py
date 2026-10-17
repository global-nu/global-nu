#!/usr/bin/env python3
"""Generate everything that states a current or released value.

    ./.venv/bin/python3 tools/make_release.py            # public build inputs
    ./.venv/bin/python3 tools/make_release.py --drafts   # draft build inputs

One source, site-src/data/releases.yaml (plus, with --drafts, the unpublished
overlay drafts/data/releases.yaml), and from it:

  page fragments   release-panel, release-changes, results-current,
                   table-<id>, files-<id>, data-current, data-releases,
                   current-ranges.svg
                   -> site-src/data/figures/   (public)
                   -> drafts/figures/          (--drafts; overrides the public
                                                ones in the draft build only)
  data files       current/parameters.{csv,json}, citation.bib, schema.json
                   and global-nu-current.zip
                   -> data-exports/current/    (public)
                   releases/<version>/ packages, latest/, <version>.zip
                   -> drafts/data/releases/    (--drafts)

build.py runs this before it renders the pages, so a page, its CSV and its
JSON cannot come from different inputs; tools/tests/test_release_files.py
checks the built pages against the built files.

Values stay strings from the YAML to the page: the generator never re-rounds a
published number. The only arithmetic is the display sign of Δm² in inverted
ordering, the conversion of mixing angles to plain decimals on the home panel
(an exact power-of-ten shift), and the 1σ accuracy where a release does
not print it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import shutil
import sys
import zipfile
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import accuracy as acc_rule   # noqa: E402
# The public build knows only published releases: their papers' definition.
# run(drafts=True) switches to the note that also states release 2026.a's.
ACC_NOTE = "1σ accuracy: " + acc_rule.NOTE_PAPERS + "."
from tools.make_figures import _rel_axis, _rel_range_row  # noqa: E402

SRC = ROOT / "site-src" / "data" / "releases.yaml"
DRAFT_SRC = ROOT / "drafts" / "data" / "releases.yaml"
FIG_PUBLIC = ROOT / "site-src" / "data" / "figures"
FIG_DRAFT = ROOT / "drafts" / "figures"
EXPORT_PUBLIC = ROOT / "data-exports" / "current"
DRAFT_RELEASES = ROOT / "drafts" / "data" / "releases"

LICENSE = "CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/"
SCHEMA_VERSION = 1
LEVELS = (("s1", "1σ"), ("s2", "2σ"), ("s3", "3σ"))
# Δm² is exported as its magnitude, the quantity the papers print.
CSV_NAME = {"Dm2": "absDm2"}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def _put(path: Path, data: bytes | str) -> None:
    """Write only when the content changes. Every build regenerates these
    files; rewriting identical bytes bumps the mtime, which makes build.py
    copy them again and makes a synced folder (this one sits on an
    iCloud-synced Desktop) upload them again — rapid rewrites there left
    conflict copies named "parameters 2.csv" in the built tree."""
    b = data.encode("utf-8") if isinstance(data, str) else data
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == b:
        return
    path.write_bytes(b)


def _sync_dir(dst: Path, files: dict[str, bytes]) -> None:
    """Make `dst` hold exactly `files` (relative path -> bytes), touching only
    what differs and removing what is no longer part of the set."""
    for rel, b in files.items():
        _put(dst / rel, b)
    if dst.exists():
        for p in sorted(dst.rglob("*"), reverse=True):
            rel = p.relative_to(dst).as_posix()
            if p.is_file() and rel not in files:
                p.unlink()
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()


def load(drafts: bool) -> dict:
    doc = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    rels = {r["id"]: r for r in doc["releases"]}
    order = [r["id"] for r in doc["releases"]]
    current = doc["current"]
    if drafts and DRAFT_SRC.exists():
        d = yaml.safe_load(DRAFT_SRC.read_text(encoding="utf-8"))
        for r in d["releases"]:
            rels[r["id"]] = r
            order.append(r["id"])
        public_current = current
        current = dict(d["current"], previous=public_current)
    return {"params": doc["parameters"], "rels": rels, "order": order,
            "current": current, "drafts": drafts}


def entry(rel: dict, p: str, o: str) -> dict | None:
    by = (rel.get("values") or {}).get(p) or {}
    return by.get(o) or by.get("any")


def same_both(rel: dict, p: str) -> bool:
    return "any" in ((rel.get("values") or {}).get(p) or {})


def acc_of(rel: dict, e: dict) -> str:
    return e["acc"]


def acc_is_computed(rel: dict) -> bool:
    return bool(rel.get("acc_computed"))


def sources_of(D: dict) -> list[str]:
    seen = []
    for p in D["params"]:
        rid = D["current"]["from"][p]
        if rid not in seen:
            seen.append(rid)
    return seen


def cur_anchor(D: dict) -> str:
    """Where "the current values" live on results.html: the generated section
    on the public page, the release's own best-fit section on the draft page."""
    srcs = [D["rels"][r] for r in sources_of(D)]
    if D["drafts"] and len(srcs) == 1 and srcs[0].get("draft"):
        # earlier releases live on their own page in the draft build
        return "results.html#risultati-sezione"
    return "#current-results-section"


def mixed(D: dict) -> bool:
    return len(sources_of(D)) > 1


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #
def neg(s: str) -> str:
    return "−" + s


def show(D: dict, p: str, o: str, v: str) -> str:
    return neg(v) if D["params"][p]["signed"] and o == "IO" else v


def show_range(D: dict, p: str, o: str, r: list[str]) -> str:
    lo, hi = r
    if D["params"][p]["signed"] and o == "IO":
        return f"{neg(hi)} – {neg(lo)}"
    return f"{lo} – {hi}"


def plain(D: dict, p: str, v: str) -> str:
    """Mixing angles as plain decimals for the home panel (exact shift)."""
    meta = D["params"][p]
    if p.startswith("sin2"):
        return str(Decimal(v) * Decimal(str(meta["scale"])))
    return v


def plain_unit(D: dict, p: str) -> str:
    return "" if p.startswith("sin2") else D["params"][p]["unit"]


def label_unit(D: dict, p: str) -> str:
    meta = D["params"][p]
    return f'{meta["label"]} / {meta["unit"]}' if meta["unit"] else meta["label"]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def rel_link(rel: dict) -> str:
    if rel.get("doi"):
        return f'<a href="https://doi.org/{rel["doi"]}">{esc(rel["journal"])}</a>'
    return esc(rel.get("date_note") or rel["label"])


def year_of(rel: dict) -> str:
    return str(rel.get("date", ""))[:4]


def badge(rel: dict) -> str:
    """The provenance badge; a link to the paper when there is one."""
    cls = "src--new" if rel.get("kind") == "partial" or rel.get("draft") else "src--old"
    if rel.get("doi"):
        return (f'<a class="srcbadge {cls}" href="https://doi.org/{rel["doi"]}" '
                f'title="{esc(rel["journal"])}">{esc(rel["badge"])}</a>')
    return f'<span class="srcbadge {cls}">{esc(rel["badge"])}</span>'


def orderings(rel: dict, p: str) -> list[str]:
    return ["any"] if same_both(rel, p) else ["NO", "IO"]


# --------------------------------------------------------------------------- #
# home: the release panel and the four actions
# --------------------------------------------------------------------------- #
def panel(D: dict) -> str:
    cur = D["current"]
    rels = D["rels"]
    srcs = [rels[r] for r in sources_of(D)]
    ordrel = rels[cur["ordering_from"]]
    kind = "full release" if not mixed(D) and srcs[0]["kind"] == "full" else "partial update"
    if mixed(D):
        newest = max(srcs, key=lambda r: str(r.get("date")))
        ident = f'{esc(cur["label"])} · {esc(newest["label"])} on the {esc(rels[newest["base"]]["label"])}'
        date = esc("published " + " and ".join(
            f'{year_of(r)} ({"full release" if r["kind"] == "full" else "update"})'
            for r in sorted(srcs, key=lambda r: str(r.get("date")))))
    else:
        r = srcs[0]
        ident = esc(r["label"])
        date = esc(r.get("date_note") or r.get("date", ""))

    glance = {}
    gpath = ROOT / "drafts" / "data" / "glance.json"
    if D["drafts"] and not mixed(D) and srcs[0].get("draft") and gpath.exists():
        glance = json.loads(gpath.read_text(encoding="utf-8"))
    cells = []
    for p, meta in D["params"].items():
        rel = rels[cur["from"][p]]
        no = entry(rel, p, "NO")
        io_e = entry(rel, p, "IO")
        u = plain_unit(D, p)
        io_txt = ("same in IO" if same_both(rel, p)
                  else f'IO {show(D, p, "IO", plain(D, p, io_e["best"]))}')
        src_dd = f'<dd class="relcell__src">{badge(rel)}</dd>' if mixed(D) else ""
        cells.append(
            f'<div class="relcell" data-param="{p}">'
            f'<dt>{esc(meta["label"])}{f" <span class=u>/ {esc(u)}</span>" if u else ""}</dt>'
            f'<dd class="relcell__v">{esc(plain(D, p, no["best"]))}'
            + (f'<span class="relcell__err">{glance[p]["err"]}</span>' if p in glance else "")
            + '</dd>'
            + (f'<dd class="relcell__curve">{glance[p]["svg"]}</dd>' if p in glance else "")
            + f'<dd class="relcell__io">{esc(io_txt)}</dd>{src_dd}</div>')

    banner = ""
    if mixed(D):
        parts = []
        for r in srcs:
            ps = [D["params"][p]["label"] for p in D["params"] if cur["from"][p] == r["id"]]
            parts.append(f'{", ".join(ps)} from {rel_link(r)}')
        banner = ('<p class="relpanel__banner" role="note"><strong>Current snapshot: '
                  'values from two publications, not a single fit.</strong> '
                  + "; ".join(parts) + ".</p>")
    draft = ""
    if any(r.get("draft") for r in srcs):
        draft = ('<p class="relpanel__draft" role="note"><strong>Draft — not published.</strong> '
                 'Bari Release 2026.a is shown here for local review only; its paper is in preparation.</p>')

    order_txt = (f'{esc(ordrel["ordering_preference"])} · Δχ²(IO−NO) = '
                 f'{esc(ordrel["chi2_io_minus_no"])}')
    order_src = f' <span class="relpanel__from">from {rel_link(ordrel)}</span>' if mixed(D) else ""

    dl = download_target(D)
    if D["drafts"] and not mixed(D) and srcs[0].get("draft"):
        # the draft release has its own full page (drafts/tools/
        # make_release_page_draft.py): point at what physicists use there
        actions = ('<a class="btn" href="results.html">Full results</a>\n'
                   '  <a class="btn btn--ghost" href="results.html#sinossi-sezione">Figures: 1D and 2D</a>\n'
                   '  <a class="btn btn--ghost" href="results.html#chi2-6d-sezione">Δχ² explorer, 6D</a>\n'
                   '  <a class="btn btn--ghost" href="results.html#data">Download the Δχ² tables</a>')
    else:
        actions = (f'<a class="btn" href="results.html">Full results</a>\n'
                   f'  <a class="btn btn--ghost" href="{dl}" download>Download current release</a>\n'
                   '  <a class="btn btn--ghost" href="about.html#cite" data-copy-cite="current">Copy citation</a>\n'
                   '  <a class="btn btn--ghost" href="history.html">Parameter history</a>')
    return f'''<section class="relpanel" id="current-results" aria-labelledby="cr-h">
<div class="relpanel__head">
  <p class="kicker">Current results</p>
  <h2 id="cr-h">{ident}</h2>
  <p class="relpanel__meta"><span class="tag tag--kind">{kind}</span><span>{date}</span></p>
</div>
{draft}{banner}
<p class="relpanel__note">Best fit, normal ordering (NO); the inverted-ordering (IO) value below each.</p>
<dl class="relgrid{" relgrid--curves" if glance else ""}">
{chr(10).join(cells)}
</dl>
{'<p class="relpanel__legend"><i class="lno"></i>NO <i class="lio"></i>IO · Nσ = √Δχ² up to 5σ, both orderings on the common scale (guides at 1σ and 3σ); shaded: the 1σ range (NO). Profiles of the final combination.</p>' if glance else ""}
<p class="relpanel__order">{order_txt}{order_src}</p>
<div class="relpanel__actions">
  {actions}
</div>
<template id="cite-current">{esc(citation_text(D))}</template>
</section>'''


def download_target(D: dict) -> str:
    cur = D["current"]
    if D["drafts"] and not mixed(D):
        rel = D["rels"][cur["from"]["dm2"]]
        if rel.get("package"):
            return f'data/releases/{rel["version"]}.zip'
    return "data/current/global-nu-current.zip"


def citation_text(D: dict) -> str:
    """What "Copy citation" puts on the clipboard: BibTeX of every source."""
    out = []
    for rid in sources_of(D):
        out.append(bibtex_of(D["rels"][rid]).strip())
    return "\n\n".join(out) + "\n"


def bibtex_of(rel: dict) -> str:
    if rel.get("bibtex"):
        return rel["bibtex"]
    # Unpublished release: no paper to cite yet. A dataset entry that says so,
    # with nothing in it that would need a source (no authors, no journal).
    return (f'% {rel["label"]}: paper in preparation — replace with its record once out.\n'
            f'@misc{{globalnu:{rel["version"]},\n'
            f'    title = "{{Bari global analysis of neutrino oscillation data, release {rel["version"]}}}",\n'
            f'    howpublished = "\\url{{https://global-nu.org/{rel["package"]}}}",\n'
            f'    note = "Draft, not published; values as of {rel["date"]}",\n'
            f'    year = "{year_of(rel)}"\n}}\n')


# --------------------------------------------------------------------------- #
# home: what changed
# --------------------------------------------------------------------------- #
def changes(D: dict) -> str:
    rels, cur = D["rels"], D["current"]
    items = []
    computed = False
    if "previous" in cur:                                  # draft: vs public snapshot
        prev = cur["previous"]
        for p, meta in D["params"].items():
            old_rel, new_rel = rels[prev["from"][p]], rels[cur["from"][p]]
            o, n = entry(old_rel, p, "NO"), entry(new_rel, p, "NO")
            mark = "*" if acc_is_computed(new_rel) else ""
            computed |= bool(mark)
            items.append(f'<li><b>{esc(meta["label"])}</b> 1σ accuracy '
                         f'{esc(o["acc"])}% → {esc(n["acc"])}%{mark}</li>')
        po, pn = rels[prev["ordering_from"]], rels[cur["ordering_from"]]
        items.append(f'<li><b>Ordering</b> {esc(po["ordering_preference"].replace("Normal ordering favoured at ", "NO at "))}'
                     f' → {esc(pn["ordering_preference"].replace("Normal ordering favoured at ", "NO at "))}'
                     f' (Δχ² {esc(po["chi2_io_minus_no"])} → {esc(pn["chi2_io_minus_no"])})</li>')
        against = "against the published values (2025 release with the 2026 (1, 2)-sector update)"
    else:
        for rid in sources_of(D):
            rel = rels[rid]
            if rel.get("kind") != "partial":
                continue
            base = rels[rel["base"]]
            for p in rel["updates"]:
                o, n = entry(base, p, "NO"), entry(rel, p, "NO")
                items.append(f'<li><b>{esc(D["params"][p]["label"])}</b> 1σ accuracy '
                             f'{esc(o["acc"])}% → {esc(n["acc"])}%</li>')
            items.append('<li><b>Ordering preference</b> unchanged — the update does not '
                         'refit it</li>')
            against = f'{esc(rel["label"])} against the {esc(base["label"])}'
    foot = ('<p class="small muted">* computed from the release ranges, with the '
            'definition of our papers\' tables.</p>') if computed else ""
    return (f'<div class="changes" aria-labelledby="ch-h"><h3 id="ch-h">What changed</h3>'
            f'<p class="changes__ctx">{against}</p><ul>{"".join(items)}</ul>'
            f'<p class="changes__def">{esc(ACC_NOTE)}</p>{foot}</div>')


# --------------------------------------------------------------------------- #
# home: the six parameters chart
# --------------------------------------------------------------------------- #
def ranges_svg(D: dict) -> str:
    W, ROW, TOP = 520, 34, 36
    params = list(D["params"])
    H = TOP + ROW * len(params) + 39
    L, R = 124, 58
    out = _rel_axis(L, R, W, TOP - 12, TOP + ROW * len(params))
    credits = []
    for i, p in enumerate(params):
        rel = D["rels"][D["current"]["from"][p]]
        e = entry(rel, p, "NO")
        f = {"best": float(e["best"]), "s1": [float(x) for x in e["s1"]],
             "s3": [float(x) for x in e["s3"]]}
        y = TOP + i * ROW + ROW / 2
        label = "Δm²" if p == "Dm2" else D["params"][p]["label"]
        out.extend(_rel_range_row(p, "no" if not same_both(rel, p) else "any", label, "",
                                  unit_for_fig(D, p), f, y, "var(--no)", L, R, W,
                                  font=11.5, value_font=11, source=rel.get("arxiv") or rel["id"]))
        if rel["id"] not in credits:
            credits.append(rel["id"])
    out.append(f'<text x="{L}" y="{H-19:.0f}" font-size="9.5" fill="currentColor" '
               f'opacity=".82">width = 3σ range as a percentage of the best fit</text>')
    credit = " · ".join(
        (f'arXiv:{D["rels"][c]["arxiv"]}' if D["rels"][c].get("arxiv") else D["rels"][c]["label"])
        for c in credits)
    out.append(f'<text x="{W-R}" y="{H-6:.0f}" text-anchor="end" font-size="9.5" '
               f'font-family="var(--mono)" fill="currentColor" opacity=".75">{esc(credit)}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Best fit with 1σ and 3σ ranges '
            'for each oscillation parameter, normal ordering, current values, on one scale in '
            "percent of each parameter's own best fit\">\n" + "\n".join(out) + "\n</svg>")


def unit_for_fig(D: dict, p: str) -> str | None:
    # make_figures.unit_suffix expects the register's notation ("1e-5 eV²")
    u = D["params"][p]["unit_csv"]
    return None if u == "1" else u.replace("^2", "²")


# --------------------------------------------------------------------------- #
# results: level 1 (summary), level 2 (full table), level 3 (files)
# --------------------------------------------------------------------------- #
def summary(D: dict, rid_for: dict, table_id: str, caption: str) -> str:
    """Desktop table + mobile cards for a set of parameters (p -> release id)."""
    rels = D["rels"]
    rows, cards = [], []
    for p, meta in D["params"].items():
        if p not in rid_for:
            continue
        rel = rels[rid_for[p]]
        ords = orderings(rel, p)
        star = "*" if acc_is_computed(rel) else ""
        for k, o in enumerate(ords):
            e = entry(rel, p, o)
            oo = "NO" if o == "any" else o
            head = (f'<th scope="row" rowspan="{len(ords)}">{esc(label_unit(D, p))}</th>'
                    if k == 0 else "")
            rows.append(
                f'<tr data-param="{p}" data-ordering="{o}">{head}'
                f'<td class="ord{"" if o == "any" else " ord--" + o.lower()}">{"NO, IO" if o == "any" else o}</td>'
                f'<td class="num bf">{esc(show(D, p, oo, e["best"]))}</td>'
                f'<td class="num">{esc(show_range(D, p, oo, e["s1"]))}</td>'
                f'<td class="num col-more">{esc(show_range(D, p, oo, e["s2"]))}</td>'
                f'<td class="num">{esc(show_range(D, p, oo, e["s3"]))}</td>'
                f'<td class="num col-more" title="{esc(ACC_NOTE)}">{esc(e["acc"])}{star}</td>'
                f'<td class="srccell">{badge(rel)}</td></tr>')
        # mobile card
        name = f"lv-{table_id}-{p}"
        radios = "".join(
            f'<input type="radio" name="{name}" id="{name}-{k}" value="{k}"{" checked" if k == "s1" else ""}>'
            f'<label for="{name}-{k}">{lab}</label>' for k, lab in LEVELS)
        lines = []
        for o in ords:
            e = entry(rel, p, o)
            oo = "NO" if o == "any" else o
            rng = "".join(f'<span class="pc__r pc__r--{k}">{esc(show_range(D, p, oo, e[k]))}</span>'
                          for k, _ in LEVELS)
            copy = (f'{meta["label"]} ({"NO, IO" if o == "any" else o}) = {show(D, p, oo, e["best"])}'
                    f'{" × " + meta["unit"] if meta["unit"] else ""}; '
                    f'1σ {show_range(D, p, oo, e["s1"])}, 3σ {show_range(D, p, oo, e["s3"])}; '
                    f'{rel.get("journal") or rel["label"]}')
            lines.append(
                f'<div class="pc__row"><span class="pc__o">{"NO, IO" if o == "any" else o}</span>'
                f'<span class="pc__bf">{esc(show(D, p, oo, e["best"]))}</span>{rng}'
                f'<button class="pc__copy" type="button" data-copy="{esc(copy)}" '
                f'aria-label="Copy {esc(meta["label"])} {o} value">Copy</button></div>')
        e0 = entry(rel, p, ords[0])
        unit_html = f' <span class="u">/ {esc(meta["unit"])}</span>' if meta["unit"] else ""
        cards.append(
            f'<article class="pc" data-param="{p}"><h3 class="pc__h">{esc(meta["label"])}'
            f'{unit_html}</h3>'
            f'<div class="pc__lv" role="radiogroup" aria-label="Range shown">{radios}'
            f'{"".join(lines)}</div>'
            f'<p class="pc__meta">1σ accuracy {esc(e0["acc"])}%{star} · {badge(rel)}</p></article>')
    return f'''<div class="lvl1" data-table="{table_id}">
<div class="table-scroll lvl1__table">
<table class="data data--summary" id="{table_id}-summary">
<caption>{caption}</caption>
<thead><tr><th scope="col">Parameter</th><th scope="col">Ordering</th><th scope="col">Best fit</th><th scope="col"><span class="sym">1σ</span> range</th><th scope="col" class="col-more"><span class="sym">2σ</span> range</th><th scope="col"><span class="sym">3σ</span> range</th><th scope="col" class="col-more"><abbr title="{esc(ACC_NOTE)}"><span class="sym">1σ</span> accuracy</abbr> (%)</th><th scope="col">Source</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>
<button class="btn btn--sm btn--ghost more-toggle" type="button" aria-expanded="false" hidden>More details: 2σ and accuracy</button>
<div class="pcards">
{chr(10).join(cards)}
</div>
<p class="accnote small"><span aria-hidden="true">ⓘ</span> {esc(ACC_NOTE)}</p>
</div>'''


def full_table(D: dict, rid_for: dict, table_id: str, caption: str, from_col: bool,
               superseded: set[str] = frozenset()) -> str:
    rels = D["rels"]
    rows = []
    alt = False
    for p in D["params"]:
        if p not in rid_for:
            continue
        rel = rels[rid_for[p]]
        ords = orderings(rel, p)
        alt = not alt
        star = "*" if acc_is_computed(rel) else ""
        for k, o in enumerate(ords):
            e = entry(rel, p, o)
            oo = "NO" if o == "any" else o
            sup = (f' <sup><a href="{cur_anchor(D)}" title="superseded by a later release">†</a></sup>'
                   if p in superseded and k == 0 else "")
            # the ordering again inside the sticky first column: on a phone the
            # Ordering column scrolls away, and the row must still say which it is
            otag = "" if o == "any" else f' <span class="ordtag ord--{o.lower()}">{o}</span>'
            th = f'<th scope="row">{(esc(label_unit(D, p)) + sup) if k == 0 else ""}{otag}</th>'
            ocls = "ord" if o == "any" else f"ord ord--{o.lower()}"
            src = ""
            if from_col:
                href = f"https://doi.org/{rel['doi']}" if rel.get("doi") else cur_anchor(D)
                cls = "src--new" if rel.get("kind") == "partial" or rel.get("draft") else "src--old"
                src = f'<td class="ord {cls}"><a href="{href}">{esc(year_of(rel)) if not rel.get("draft") else esc(rel["version"])}</a></td>'
            rows.append(
                f'<tr{" class=\"row-alt\"" if alt else ""}>{th}<td class="{ocls}">{"NO, IO" if o == "any" else o}</td>'
                f'<td>{esc(show(D, p, oo, e["best"]))}</td>'
                + "".join(f'<td>{esc(show_range(D, p, oo, e[k2]))}</td>' for k2, _ in LEVELS)
                + f'<td>{esc(e["acc"])}{star}</td>{src}</tr>')
    head_from = '<th scope="col">From</th>' if from_col else ""
    return f'''<div class="ts-wrap"><div class="table-scroll table-scroll--sticky" tabindex="0" role="region" aria-label="{esc(table_id)} table, scrolls horizontally">
<table class="data" id="{table_id}">
<caption>{caption}</caption>
<thead>
<tr><th scope="col">Parameter</th><th scope="col">Ordering</th><th scope="col">Best fit</th><th scope="col"><span class="sym">1σ</span> range</th><th scope="col"><span class="sym">2σ</span> range</th><th scope="col"><span class="sym">3σ</span> range</th><th scope="col"><abbr title="{esc(ACC_NOTE)}">“<span class="sym">1σ</span>” (%)</abbr></th>{head_from}</tr>
</thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div></div>
<p class="scroll-cue small" aria-hidden="true">Swipe the table sideways for all columns →</p>'''


def files_row(D: dict, rel: dict | None, current: bool = False, bib_link: bool = True) -> str:
    """Level 3: the scientific files of a release (or of the current snapshot)."""
    links = []
    if current and mixed(D):
        base = "data/current/"
        links = [(f"{base}parameters.csv", "Download CSV"), (f"{base}parameters.json", "Download JSON"),
                 (f"{base}schema.json", "Schema"), (f"{base}citation.bib", "BibTeX"),
                 (f"{base}global-nu-current.zip", "All files (.zip)")]
        note = ('<p class="files__note small">These files carry the current snapshot exactly as '
                'shown above. Δχ² profiles and release notes are not available: neither paper '
                'published a machine-readable package.</p>')
    elif rel is not None and rel.get("package") and D["drafts"]:
        base = rel["package"]
        links = [(f"{base}parameters.csv", "Download CSV"), (f"{base}parameters.json", "Download JSON"),
                 (f"{base}profiles/", "Δχ² profiles"), (f"{base}schema.json", "Schema"),
                 (f"{base}citation.bib", "BibTeX"), (f"{base}release-notes.md", "Release notes"),
                 (f"{base}manifest.json", "Manifest"), (f"data/releases/{rel['version']}.zip", "All files (.zip)")]
        note = (f'<p class="files__note small">Permanent, versioned directory: <code>{esc(base)}</code> · '
                f'convenience alias <code>data/releases/latest/</code>. '
                f'<a href="data.html#package">What a release package contains</a>.</p>')
    else:
        note = ('<p class="files__note small">Machine-readable release package not available '
                'for this historical release.</p>')
        if bib_link and rel is not None and rel.get("bibtex"):
            links = [(f"https://inspirehep.net/api/literature?q=arxiv:{rel['arxiv']}&format=bibtex", "BibTeX (INSPIRE)")]
    btns = "".join(
        f'<a class="btn btn--sm btn--ghost" href="{href}"{" download" if "." in href.rsplit("/", 1)[-1] and not href.endswith(".html") and "#" not in href else ""}>{esc(t)}</a>'
        for href, t in links)
    return f'<div class="files"><div class="btn-row">{btns}</div>{note}</div>'


def results_current(D: dict) -> str:
    cur, rels = D["current"], D["rels"]
    srcs = [rels[r] for r in sources_of(D)]
    if mixed(D):
        title = "Current values — newest published value per parameter"
        sub = " · ".join(f'{esc(r["badge"])}: {rel_link(r)}' for r in srcs)
        cap = ("<strong>The newest published value for each parameter — not a single fit.</strong> "
               + "; ".join(
                   f'{", ".join(D["params"][p]["label"] for p in D["params"] if cur["from"][p] == r["id"])}'
                   f' from {esc(r["table"])} of {rel_link(r)}' for r in srcs)
               + ". Ranges at Nσ = 1, 2, 3. δ/π is cyclic (mod 2). Δm² is <strong>signed</strong>: "
                 "the papers print |Δm²| and the minus sign in IO is the convention stated "
                 '<a href="#conventions">below</a>.')
    else:
        r = srcs[0]
        title = f'{esc(r["label"])} — {"full release" if r["kind"] == "full" else "partial update"}'
        sub = esc(r.get("date_note") or r.get("date", ""))
        cap = (f'<strong>{esc(r["label"])}</strong>: best fit and ranges at Nσ = 1, 2, 3, both '
               f'orderings, from {esc(r["table"])}. δ/π is cyclic (mod 2). Δm² is <strong>signed</strong>, '
               'negative in IO (see <a href="#conventions">conventions</a>).'
               + (" * accuracy computed by this site from the unrounded ranges." if acc_is_computed(r) else ""))
    draft = ""
    if any(r.get("draft") for r in srcs):
        draft = ('<div class="autogen autogen--draft"><span aria-hidden="true">⚠</span><div><b>Draft — not '
                 'published.</b> <span class="stamp">Bari Release 2026.a is shown for local review only. '
                 'Its paper is in preparation; authors, title and BibTeX will be filled in from it.'
                 '</span></div></div>')
    banner = ('<p class="relpanel__banner" role="note"><strong>Current snapshot: values from two '
              'publications, not a single fit.</strong></p>') if mixed(D) else ""
    rid_for = dict(cur["from"])
    return f'''<div class="release" id="current-results-section">
<div class="section-head">
  <h2>{title}</h2>
  <p>{sub}</p>
</div>
{draft}{banner}
{summary(D, rid_for, "current", cap)}
<details class="fulltable">
<summary>Show full table</summary>
{full_table(D, rid_for, "current", cap, from_col=True)}
</details>
<h3 class="files__h">Files</h3>
{files_row(D, srcs[0], current=True)}
<p class="small cite-line"><a href="about.html#cite" data-copy-cite="current">Copy citation</a> · <a href="data.html">All data</a></p>
<template id="cite-current">{esc(citation_text(D))}</template>
</div>'''


def release_table(D: dict, rid: str) -> str:
    rel = D["rels"][rid]
    rid_for = {p: rid for p in rel["values"]}
    later = set()
    for p in rel["values"]:
        if D["current"]["from"][p] != rid:
            later.add(p)
    cap = (f'{esc(rel["table"])} of {rel_link(rel)}: best-fit values and allowed ranges at '
           'N&#8202;σ = 1, 2, 3, for either NO or IO. The last column is the “1σ parameter '
           'accuracy”, 1/6 of the 3σ range divided by the best fit, in percent. δ/π is cyclic '
           '(mod 2). Values are transcribed from the published table; nothing is estimated or '
           'rounded further. Δm² is <strong>signed</strong>, so the inverted-ordering rows read '
           'negative: the paper prints |Δm²|.')
    if later:
        cap += (' <strong>†</strong> superseded by a later release: see '
                f'<a href="{cur_anchor(D)}">current values</a> at the top of this page.')
    tid = {"bari-2025": "release-2025"}.get(rid, f"release-{rid.removeprefix('bari-')}")
    return full_table(D, rid_for, tid, cap, from_col=False, superseded=later)


# --------------------------------------------------------------------------- #
# data files
# --------------------------------------------------------------------------- #
def records(D: dict, rid_for: dict) -> list[dict]:
    out = []
    for p, meta in D["params"].items():
        if p not in rid_for:
            continue
        rel = D["rels"][rid_for[p]]
        for o in ("NO", "IO"):
            e = entry(rel, p, o)
            out.append({
                "parameter": CSV_NAME.get(p, p),
                "ordering": o,
                "unit": meta["unit_csv"],
                "best_fit": e["best"],
                "range_1sigma_low": e["s1"][0], "range_1sigma_high": e["s1"][1],
                "range_2sigma_low": e["s2"][0], "range_2sigma_high": e["s2"][1],
                "range_3sigma_low": e["s3"][0], "range_3sigma_high": e["s3"][1],
                "accuracy_1sigma_percent": e["acc"],
                "accuracy_source": "computed" if acc_is_computed(rel) else "paper",
                "same_in_both_orderings": "true" if same_both(rel, p) else "false",
                "source_release": rel.get("version") or rel["id"],
                "source_doi": rel.get("doi") or "",
                "source_arxiv": rel.get("arxiv") or "",
                "source_table": rel.get("table") or "",
            })
    return out


CSV_HEAD = ["parameter", "ordering", "unit", "best_fit",
            "range_1sigma_low", "range_1sigma_high", "range_2sigma_low", "range_2sigma_high",
            "range_3sigma_low", "range_3sigma_high", "accuracy_1sigma_percent", "accuracy_source",
            "same_in_both_orderings", "source_release", "source_doi", "source_arxiv", "source_table"]

CONVENTIONS = {
    "dm2": "δm² = m₂² − m₁² > 0",
    "absDm2": "|Δm²| with Δm² = m₃² − (m₁² + m₂²)/2 = (Δm²₃₁ + Δm²₃₂)/2; Δm² > 0 in NO, < 0 in IO",
    "delta_pi": "δ/π, cyclic mod 2",
    "ranges": "1, 2, 3σ ranges for one degree of freedom: Δχ² = 1, 4, 9 from the minimum of the same ordering",
    "units": "each value is in the unit of its row, e.g. best_fit 3.085 with unit 1e-1 means 0.3085",
    "accuracy_1sigma_percent": acc_rule.NOTE_PAPERS,
}


def to_csv(recs: list[dict], header_lines: list[str]) -> str:
    buf = io.StringIO()
    for line in header_lines:
        buf.write(f"# {line}\n")
    w = csv.DictWriter(buf, fieldnames=CSV_HEAD, lineterminator="\n")
    w.writeheader()
    w.writerows(recs)
    return buf.getvalue()


def to_json(recs: list[dict], about: dict) -> str:
    num = lambda s: float(s) if s not in ("", None) else None   # noqa: E731
    rows = []
    for r in recs:
        rows.append({
            "parameter": r["parameter"], "ordering": r["ordering"], "unit": r["unit"],
            "best_fit": num(r["best_fit"]),
            "range_1sigma": [num(r["range_1sigma_low"]), num(r["range_1sigma_high"])],
            "range_2sigma": [num(r["range_2sigma_low"]), num(r["range_2sigma_high"])],
            "range_3sigma": [num(r["range_3sigma_low"]), num(r["range_3sigma_high"])],
            "accuracy_1sigma_percent": num(r["accuracy_1sigma_percent"]),
            "accuracy_source": r["accuracy_source"],
            "same_in_both_orderings": r["same_in_both_orderings"] == "true",
            "source": {"release": r["source_release"], "doi": r["source_doi"] or None,
                       "arxiv": r["source_arxiv"] or None, "table": r["source_table"]},
        })
    return json.dumps({**about, "parameters": rows}, ensure_ascii=False, indent=1) + "\n"


def schema_json() -> str:
    rng = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
    return json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://global-nu.org/data/schema/parameters-v1.json",
        "title": "global-nu parameters file, schema version 1",
        "type": "object",
        "required": ["schema_version", "release", "conventions", "license", "parameters"],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "release": {"type": "object"},
            "conventions": {"type": "object", "additionalProperties": {"type": "string"}},
            "license": {"type": "string"},
            "parameters": {"type": "array", "items": {
                "type": "object",
                "required": ["parameter", "ordering", "unit", "best_fit", "range_1sigma",
                             "range_2sigma", "range_3sigma", "accuracy_1sigma_percent", "source"],
                "properties": {
                    "parameter": {"enum": ["dm2", "sin2_th12", "absDm2", "sin2_th13", "sin2_th23", "delta_pi"]},
                    "ordering": {"enum": ["NO", "IO"]},
                    "unit": {"type": "string"},
                    "best_fit": {"type": "number"},
                    "range_1sigma": rng, "range_2sigma": rng, "range_3sigma": rng,
                    "accuracy_1sigma_percent": {"type": "number"},
                    "accuracy_source": {"enum": ["paper", "computed"]},
                    "same_in_both_orderings": {"type": "boolean"},
                    "source": {"type": "object"},
                }}},
        },
    }, ensure_ascii=False, indent=1) + "\n"


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    """Deterministic zip: fixed timestamps, sorted names — same bytes for the
    same content, so a rebuild does not look like a new release."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    _put(path, buf.getvalue())


def write_current(D: dict, out: Path) -> None:
    rid_for = dict(D["current"]["from"])
    recs = records(D, rid_for)
    srcs = [D["rels"][r] for r in sources_of(D)]
    about = {
        "schema_version": SCHEMA_VERSION,
        "release": {
            "id": D["current"]["id"],
            "kind": "snapshot" if mixed(D) else srcs[0]["kind"],
            "note": ("Newest published value per parameter — values from two publications, "
                     "not a single fit." if mixed(D) else srcs[0]["label"]),
            "sources": [{"release": r.get("version") or r["id"], "label": r["label"],
                         "doi": r.get("doi"), "arxiv": r.get("arxiv"), "journal": r.get("journal")}
                        for r in srcs],
            "ordering": {"preference": D["rels"][D["current"]["ordering_from"]]["ordering_preference"],
                         "chi2_io_minus_no": D["rels"][D["current"]["ordering_from"]]["chi2_io_minus_no"]},
        },
        "conventions": CONVENTIONS,
        "license": LICENSE,
    }
    head = [f"global-nu current values — {about['release']['note']}",
            *[f"source: {s['label']} — {s['journal'] or s['release']}" for s in about["release"]["sources"]],
            "conventions: " + "; ".join(f"{k}: {v}" for k, v in CONVENTIONS.items()),
            f"licence: {LICENSE}",
            "pandas.read_csv(path, comment='#', dtype=str) keeps the printed digits"]
    files = {
        "parameters.csv": to_csv(recs, head).encode(),
        "parameters.json": to_json(recs, about).encode(),
        "schema.json": schema_json().encode(),
        "citation.bib": citation_text(D).encode(),
    }
    for n, b in files.items():
        _put(out / n, b)
    write_zip(out / "global-nu-current.zip", {f"global-nu-current/{n}": b for n, b in files.items()})


def write_package(D: dict, rel: dict, root: Path) -> None:
    """A versioned, immutable release package (drafts only, for now)."""
    ver = rel["version"]
    out = root / ver
    rid_for = {p: rel["id"] for p in rel["values"]}
    recs = records(D, rid_for)
    about = {
        "schema_version": SCHEMA_VERSION,
        "release": {"id": rel["id"], "version": ver, "kind": rel["kind"], "label": rel["label"]},
        "conventions": CONVENTIONS, "license": LICENSE,
    }
    head = [f"Bari global analysis — {rel['label']} ({rel['kind']} release)",
            f"source: {rel['table']}", f"licence: {LICENSE}",
            "pandas.read_csv(path, comment='#', dtype=str) keeps the printed digits"]
    files = {
        "parameters.csv": to_csv(recs, head).encode(),
        "parameters.json": to_json(recs, about).encode(),
        "schema.json": schema_json().encode(),
        "citation.bib": bibtex_of(rel).encode(),
        "release-notes.md": release_notes(D, rel).encode(),
    }
    prof = rel.get("profiles") or {}
    for f in prof.get("files", []):
        files[f"profiles/{f}"] = (Path(prof["dir"]) / f).read_bytes()
    sums = {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}
    manifest = {
        "release_id": rel["id"], "version": ver, "date": rel["date"],
        "kind": rel["kind"], "draft": bool(rel.get("draft")),
        "paper": {"title": rel.get("title"), "authors": rel.get("authors"), "journal": rel.get("journal"),
                  "doi": rel.get("doi"), "arxiv": rel.get("arxiv")},
        "updated_parameters": [CSV_NAME.get(p, p) for p in rel["values"]],
        "orderings": ["NO", "IO"],
        "units": {CSV_NAME.get(p, p): m["unit_csv"] for p, m in D["params"].items()},
        "conventions": CONVENTIONS,
        "ordering_preference": {"text": rel["ordering_preference"], "chi2_io_minus_no": rel["chi2_io_minus_no"]},
        "license": LICENSE, "schema_version": SCHEMA_VERSION,
        "files": [{"path": n, "bytes": len(b), "sha256": sums[n]} for n, b in sorted(files.items())],
    }
    mbytes = (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode()
    files["manifest.json"] = mbytes
    sums["manifest.json"] = hashlib.sha256(mbytes).hexdigest()
    chk = "".join(f"{sums[n]}  {n}\n" for n in sorted(sums)).encode()
    files["checksums.txt"] = chk
    # the profiles directory gets an index so the link from the page resolves;
    # a convenience page, outside the checksummed set
    idx = "".join(f'<li><a href="{f}">{f}</a></li>' for f in prof.get("files", []))
    on_disk = dict(files)
    on_disk["profiles/index.html"] = (
        f'<!doctype html><meta charset="utf-8"><title>{ver} Δχ² profiles</title>'
        f'<h1>{ver} — Δχ² profiles, one degree of freedom</h1><ul>{idx}</ul>'
        '<p>Each file carries its own documentation in its header.</p>').encode()
    _sync_dir(out, on_disk)
    _sync_dir(root / "latest", on_disk)
    write_zip(root / f"{ver}.zip", {f"{ver}/{n}": b for n, b in files.items()})


def release_notes(D: dict, rel: dict) -> str:
    lines = [f"# {rel['label']}", "",
             f"Kind: {rel['kind']} release. Date: {rel['date']} ({rel.get('date_note', '')}).", "",
             f"Source of the numbers: {rel['table']}.", "",
             f"Mass ordering: {rel['ordering_preference']}; Δχ²(IO−NO) = {rel['chi2_io_minus_no']}.", ""]
    if rel.get("acc_computed"):
        lines += ["The 1σ accuracy is computed from the unrounded ranges: the 1σ error "
                  "divided by the best fit, δ/π included; for sin²θ23 one sixth of the 3σ "
                  "range divided by the best fit (tools/accuracy.py).", ""]
    if rel.get("draft"):
        lines += ["DRAFT — not published. Authors, title and citation will be completed from "
                  "the paper.", ""]
    lines += ["Corrections are published as a new version of the package, never by "
              "replacing these files.", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# data page fragments
# --------------------------------------------------------------------------- #
def data_current(D: dict) -> str:
    return (f'<div class="datablock" id="current">{files_row(D, D["rels"][sources_of(D)[0]], current=True)}'
            f'</div>')


def data_preview(D: dict) -> str:
    """The first rows of parameters.csv, as the file has them — a reader sees
    the format before downloading it. Generated from the same records."""
    recs = records(D, dict(D["current"]["from"]))
    lines = to_csv(recs, []).splitlines()
    cols = ["parameter", "ordering", "unit", "best_fit", "range_1sigma_low", "range_1sigma_high",
            "source_release"]
    idx = [lines[0].split(",").index(c) for c in cols]
    import csv as _csv
    rows = list(_csv.reader(lines))
    shown = [",".join(r[i] for i in idx) for r in rows[:5]]
    return ('<figure class="datapreview"><figcaption class="small">parameters.csv — first rows, '
            f'7 of its {len(CSV_HEAD)} columns</figcaption><pre><code>'
            + esc("\n".join(shown) + "\n…") + "</code></pre></figure>")


def data_main(D: dict) -> str:
    """Data page, current release. Draft build: the release's Δχ² tables, as
    drafts/tools/make_release_page_draft.py lays them out. Public build: the
    current values as files (the published papers released no Δχ² tables)."""
    cards = ROOT / "drafts" / "build" / "data-release-cards.html"
    srcs = [D["rels"][r] for r in sources_of(D)]
    if D["drafts"] and len(srcs) == 1 and srcs[0].get("draft") and cards.exists():
        return cards.read_text(encoding="utf-8")
    base = "data/current/"
    f = [(f"{base}parameters.csv", "Current values", "csv"),
         (f"{base}parameters.json", "Current values", "json")]
    btns = "".join(f'<a class="dfile" href="{h}" download><span class="dfile__l">{l}</span>'
                   f'<span class="dfile__m">.{e}</span></a>' for h, l, e in f)
    return ('<div class="dsets"><article class="dset"><header><h3>Best fits and ranges, both orderings</h3>'
            '<p class="dset__note">δm² and sin²θ₁₂ from the 2026 (1, 2)-sector update; the other four '
            'from the March 2025 full release — two papers, not one fit</p></header>'
            f'<div class="dset__files">{btns}</div></article></div>')


def data_releases(D: dict) -> str:
    items = []
    for rid in reversed(D["order"]):
        rel = D["rels"][rid]
        if rel.get("draft"):
            continue
        items.append(f'<li><b>{esc(rel["label"])}</b> — {rel_link(rel)}'
                     f'{" · <a href=https://arxiv.org/abs/" + esc(rel["arxiv"]) + ">arXiv:" + esc(rel["arxiv"]) + "</a>" if rel.get("arxiv") else ""}</li>')
    return f'<ul class="rellist-plain">{"".join(items)}</ul>'


# --------------------------------------------------------------------------- #
def write_fragments(D: dict, out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    frags = {
        "release-panel.html": panel(D),
        "release-changes.html": changes(D),
        "current-ranges.svg": ranges_svg(D),
        "results-current.html": results_current(D),
        "data-current.html": data_current(D),
        "data-releases.html": data_releases(D),
        "cite-current.html": f'<pre class="cite-block"><code>{esc(citation_text(D))}</code></pre>',
        "data-preview.html": data_preview(D),
        "data-main.html": data_main(D),
    }
    for rid in D["order"]:
        if not D["rels"][rid].get("draft"):
            frags[f"table-{rid}.html"] = release_table(D, rid)
            frags[f"files-{rid}.html"] = files_row(D, D["rels"][rid])
    for n, s in frags.items():
        _put(out / n, s + "\n")
    return sorted(frags)


def write_feed(D: dict, path: Path) -> None:
    """releases.atom: one entry per release, newest first."""
    from tools import atom
    entries = []
    for rid in reversed(D["order"]):
        rel = D["rels"][rid]
        link = (f"https://doi.org/{rel['doi']}" if rel.get("doi")
                else f"{atom.SITE}/results.html")
        kind = "full release" if rel["kind"] == "full" else "partial update"
        summary = (f"{rel['label']} ({kind}). " + (f"{rel['journal']}. " if rel.get("journal") else "")
                   + (f"Parameters: {', '.join(D['params'][p]['label'] for p in rel['values'])}. ")
                   + (rel.get("ordering_preference") or "") )
        if rel.get("draft"):
            summary = "DRAFT, not published. " + summary
        entries.append({"id": f"{atom.SITE}/releases/{rel.get('version') or rid}",
                        "title": rel["label"] + (f" — {rel['title']}" if rel.get("journal") else ""),
                        "link": link, "updated": str(rel.get("date") or ""),
                        "authors": rel.get("authors") or [], "summary": summary.strip()})
    _put(path, atom.feed("data/feeds/releases.atom", "global-nu — Bari global-analysis releases",
                              "results.html", "data/feeds/releases.atom",
                              "Each release of the Bari global analysis of neutrino oscillation data.",
                              entries))


def run(drafts: bool = False, verbose: bool = True) -> None:
    global ACC_NOTE
    ACC_NOTE = (acc_rule.NOTE if drafts else "1σ accuracy: " + acc_rule.NOTE_PAPERS + ".")
    CONVENTIONS["accuracy_1sigma_percent"] = (
        acc_rule.NOTE.removeprefix("1σ accuracy, in percent. ") if drafts else acc_rule.NOTE_PAPERS)
    D = load(drafts)
    if drafts:
        names = write_fragments(D, FIG_DRAFT)
        for rid in D["order"]:
            rel = D["rels"][rid]
            if rel.get("draft") and rel.get("package"):
                write_package(D, rel, DRAFT_RELEASES)
        write_current(D, ROOT / "drafts" / "data" / "current")
        write_feed(D, ROOT / "drafts" / "data" / "feeds" / "releases.atom")
    else:
        names = write_fragments(D, FIG_PUBLIC)
        write_current(D, EXPORT_PUBLIC)
        write_feed(D, EXPORT_PUBLIC.parent / "feeds" / "releases.atom")
    if verbose:
        print(f"  release: {len(names)} fragments ({'drafts' if drafts else 'public'})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--drafts", action="store_true")
    run(ap.parse_args().drafts)


if __name__ == "__main__":
    main()
