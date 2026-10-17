#!/usr/bin/env python3
"""Every "1σ accuracy" on the site follows tools/accuracy.py.

    ./.venv/bin/python3 tools/tests/test_accuracy.py

Two definitions (Antonio, 2026-10-17): published releases keep their papers'
one, one sixth of the 3σ range over the best fit; Bari Release 2026.a uses the
1σ error over the best fit (δ/π included) and, for sin²θ₂₃ only, one sixth of
the 3σ range. The release page once printed the 1σ error for sin²θ₂₃ too
(6.93% against 4.4%), and fixes lived in one of two diverging copies of
drafts/. This test reads the built pages, so it holds whatever generator writes
them: every percentage printed as a "1σ accuracy" (or "known to", "tightens it
from … to …") must be what the rule gives for a release's ranges: the papers'
rule for published releases and the history, release 2026.a's for its data.
"""

from __future__ import annotations

import html
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import accuracy as acc_rule  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RELEASE_JSON = (Path.home() / "Desktop/JUNO_2026/JUNO_2026_second_release/"
                "Bari_Group_Release_2026.a/pubblicazione/json/bestfit_ranges_FIT.json")
PAGES = ("index.html", "results.html", "earlier-releases.html", "data.html")


def allowed() -> set[str]:
    out: set[str] = set()
    pub = yaml.safe_load((ROOT / "site-src/data/releases.yaml").read_text(encoding="utf-8"))
    for rel in pub["releases"]:
        for p, by in (rel.get("values") or {}).items():
            for e in by.values():
                if e.get("acc"):
                    out.add(str(e["acc"]))          # as the paper printed it
                add(out, p, e.get("best"), e.get("s1"), e.get("s3"), "papers")
    draft = ROOT / "drafts/data/releases.yaml"
    if draft.exists():
        for rel in yaml.safe_load(draft.read_text(encoding="utf-8"))["releases"]:
            for p, by in (rel.get("values") or {}).items():
                for e in by.values():
                    add(out, p, e.get("best"), e.get("s1"), e.get("s3"), "2026a")
    # The home page's precision chart: every release of the parameter history.
    for src in (ROOT / "site-src/data/history.yaml", ROOT / "drafts/data/history-with-2026a.yaml"):
        if not src.exists():
            continue
        for rel in yaml.safe_load(src.read_text(encoding="utf-8"))["releases"]:
            for p, by in (rel.get("values") or {}).items():
                for e in by.values():
                    add(out, p, e.get("best"), e.get("s1"), e.get("s3"),
                        rel.get("accuracy_rule", "papers"))
    # The release's other data sets (the key-number cards quote the one
    # without JUNO), when the release itself is on this machine.
    if RELEASE_JSON.exists():
        import json
        for ds in json.loads(RELEASE_JSON.read_text(encoding="utf-8"))["params"].values():
            for k, e in ds.items():
                add(out, k.split("|")[0], e["bf"], [e["1s"][0][0], e["1s"][-1][1]],
                    [e["3s"][0][0], e["3s"][-1][1]], "2026a")
    return out


def add(out: set[str], p: str, best, s1, s3, rule: str) -> None:
    a = acc_rule.accuracy(p, best, s1, s3, rule)
    if a is None:
        return
    acc = Decimal(str(a))
    for q in ("1", "0.1", "0.01"):
        for how in (ROUND_HALF_UP, ROUND_HALF_EVEN):    # the chart uses Python's %g
            out.add(str(acc.quantize(Decimal(q), how)))


def printed(page: str) -> list[str]:
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    t = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())
    got = []
    for m in re.finditer(r"1σ accuracy\s+([\d.]+)\s*%(?:\s*→\s*([\d.]+)\s*%)?", t):
        got += [g for g in m.groups() if g]
    got += re.findall(r"known to\s+([\d.]+)\s*%", t)
    for m in re.finditer(r"tightens it from\s+([\d.]+)\s*%\s+to\s+([\d.]+)\s*%", t):
        got += list(m.groups())
    return got


def main() -> None:
    ok = allowed()
    bad, n = [], 0
    for tree in (ROOT / "site", ROOT / "site-draft"):
        for name in PAGES:
            f = tree / name
            if not f.exists():
                continue
            for v in printed(f.read_text(encoding="utf-8")):
                n += 1
                if v not in ok:
                    bad.append(f"{tree.name}/{name}: {v}%")
    if n == 0:
        sys.exit("no '1σ accuracy' found on the pages — has the wording changed?")
    if bad:
        print("  ! printed as 1σ accuracy but not the site's definition (tools/accuracy.py):")
        for b in bad:
            print("      " + b)
        sys.exit(1)
    print(f"all {n} '1σ accuracy' values follow tools/accuracy.py")


if __name__ == "__main__":
    main()
