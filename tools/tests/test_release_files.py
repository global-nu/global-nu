#!/usr/bin/env python3
"""The pages, the CSV and the JSON of a release must say the same thing.

    ./.venv/bin/python3 tools/tests/test_release_files.py

For each built tree — site/ always, site-draft/ when it exists — and from the
same source the build used (releases.yaml, plus the draft overlay for
site-draft/):

  1. data/current/parameters.csv and .json carry exactly the source values,
     row by row, at the printed precision (CSV) and as numbers (JSON);
  2. the current-values table on results.html and the summary table above it
     show every one of those values, with Δm² signed in IO as the page says;
  3. the home panel shows each parameter's NO best fit;
  4. every release package (data/releases/<version>/) has a manifest whose
     sizes and SHA-256 match the files, a checksums.txt that matches too, the
     same rows as the source, and a latest/ identical to the newest version.

This is the "validated from one source" promise made on data.html.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import make_release as mr  # noqa: E402

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not ok:
        problems.append(f"{label}{': ' + detail if detail else ''}")


def read_csv(path: Path) -> list[dict]:
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    return list(csv.DictReader(lines))


def block(html: str, start: str, end: str) -> str:
    i = html.find(start)
    return "" if i < 0 else html[i:html.find(end, i)]


def tokens(s: str) -> set[str]:
    return set(re.findall(r"−?\d+\.\d+|−?\b\d+\b", s))


def check_tree(tree: Path, drafts: bool, pages_drafts: bool | None = None) -> None:
    """`pages_drafts` differs from `drafts` only when a release is published
    as preliminary: its pages show it, its data files still hold the last
    published release."""
    D = mr.load(drafts)
    tag = tree.name
    want = mr.records(D, dict(D["current"]["from"]))

    # 1. files
    got_csv = read_csv(tree / "data/current/parameters.csv")
    check(f"{tag}: current CSV equals the source", got_csv == want,
          f"{len(got_csv)} rows vs {len(want)}")
    doc = json.loads((tree / "data/current/parameters.json").read_text(encoding="utf-8"))
    for w, j in zip(want, doc["parameters"]):
        ok = (j["parameter"] == w["parameter"] and j["ordering"] == w["ordering"]
              and Decimal(str(j["best_fit"])) == Decimal(w["best_fit"])
              and [Decimal(str(x)) for x in j["range_3sigma"]]
              == [Decimal(w["range_3sigma_low"]), Decimal(w["range_3sigma_high"])])
        check(f"{tag}: JSON row {w['parameter']} {w['ordering']}", ok)
    check(f"{tag}: JSON has as many rows as the source", len(doc["parameters"]) == len(want))

    if pages_drafts is not None and pages_drafts != drafts:
        D = mr.load(pages_drafts)
    # 2. results page
    res = (tree / "results.html").read_text(encoding="utf-8")
    if 'id="risultati-sezione"' in res:
        # The draft Results page is the release's own page: its best-fit
        # section prints mixing angles as plain decimals and |Δm²| with its
        # sign in words, so compare unsigned values, in either normalisation.
        sec = res[res.index('id="risultati-sezione"'):]
        sec = sec[:sec.index("</section>")]
        here = {t.lstrip("−") for t in tokens(sec)}
        for p in D["params"]:
            rel = D["rels"][D["current"]["from"][p]]
            for o in ("NO", "IO"):
                e = mr.entry(rel, p, o)
                for v in [e["best"], *e["s1"], *e["s2"], *e["s3"]]:
                    ok = v in here or mr.plain(D, p, v) in here
                    check(f"{tag}: {p} {o} {v} in the release page's best-fit section", ok)
    else:
        check_summary_tables(D, tag, res)

    check_rest(D, tag, tree)


def check_summary_tables(D: dict, tag: str, res: str) -> None:
    full = tokens(block(res, '<table class="data" id="current">', "</table>"))
    summ = tokens(block(res, '<table class="data data--summary" id="current-summary">', "</table>"))
    for p in D["params"]:
        rel = D["rels"][D["current"]["from"][p]]
        for o in ("NO", "IO"):
            e = mr.entry(rel, p, o)
            for v in [e["best"], *e["s1"], *e["s2"], *e["s3"]]:
                shown = mr.show(D, p, o, v)
                check(f"{tag}: {p} {o} {shown} in the full table", shown in full)
            for v in [e["best"], *e["s1"], *e["s3"]]:
                shown = mr.show(D, p, o, v)
                check(f"{tag}: {p} {o} {shown} in the summary table", shown in summ)


def check_rest(D: dict, tag: str, tree: Path) -> None:
    # 3. home panel
    home = (tree / "index.html").read_text(encoding="utf-8")
    grid = tokens(block(home, '<dl class="relgrid', "</dl>"))
    for p in D["params"]:
        e = mr.entry(D["rels"][D["current"]["from"][p]], p, "NO")
        check(f"{tag}: home panel shows {p} = {mr.plain(D, p, e['best'])}",
              mr.plain(D, p, e["best"]) in grid)

    # 4. packages
    rels_dir = tree / "data/releases"
    if not rels_dir.is_dir():
        return
    versions = [d for d in rels_dir.iterdir() if d.is_dir() and d.name != "latest"]
    for vdir in versions:
        man = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))
        for f in man["files"]:
            b = (vdir / f["path"]).read_bytes()
            check(f"{tag}: {vdir.name}/{f['path']} size and sha256 match the manifest",
                  len(b) == f["bytes"] and hashlib.sha256(b).hexdigest() == f["sha256"])
        for line in (vdir / "checksums.txt").read_text(encoding="utf-8").splitlines():
            h, name = line.split("  ", 1)
            check(f"{tag}: checksums.txt {name}",
                  hashlib.sha256((vdir / name).read_bytes()).hexdigest() == h)
        rel = next(r for r in D["rels"].values() if r.get("version") == vdir.name)
        want_pkg = mr.records(D, {p: rel["id"] for p in rel["values"]})
        check(f"{tag}: {vdir.name}/parameters.csv equals the source",
              read_csv(vdir / "parameters.csv") == want_pkg)
    newest = max(versions, key=lambda d: d.name)
    latest = rels_dir / "latest"
    same = latest.is_dir() and all(
        (latest / p.relative_to(newest)).read_bytes() == p.read_bytes()
        for p in newest.rglob("*") if p.is_file())
    check(f"{tag}: latest/ is a copy of {newest.name}", same)



def main() -> None:
    if not (ROOT / "site").exists():
        sys.exit("site/ not found — run build.py first")
    import yaml
    cfg = yaml.safe_load((ROOT / "site-src/site.yaml").read_text(encoding="utf-8"))
    check_tree(ROOT / "site", drafts=False, pages_drafts=bool(cfg.get("preliminary")))
    if (ROOT / "site-draft" / "results.html").exists():
        check_tree(ROOT / "site-draft", drafts=True)
    if problems:
        print("  ! a page and its data files disagree:")
        for p in problems[:40]:
            print("      " + p)
        sys.exit(1)
    print(f"all {checks} checks pass — pages, CSV, JSON and packages agree with the source")


if __name__ == "__main__":
    main()
