#!/usr/bin/env python3
"""Every "1σ accuracy" on the site is the papers' one.

    ./.venv/bin/python3 tools/tests/test_accuracy.py

The papers' tables define the formal "1σ parameter accuracy" as one sixth of
the 3σ range divided by the best fit, in percent (Phys. Rev. D 111, 093006,
Table I caption). The 2026.a release page computed its own bars and key-number
cards as the ±1σ error over the best fit instead — sin²θ₂₃ 6.93% next to 4.4%
under the same name — and the fix lived in one of two diverging copies of
drafts/. This test reads the built pages, so it holds whatever generator
writes them: every percentage printed as a "1σ accuracy" (or "known to",
"tightens it from … to …") must be one of the releases' own values, computed
from their 3σ ranges, in releases.yaml (public and draft).
"""

from __future__ import annotations

import html
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RELEASE_JSON = (Path.home() / "Desktop/JUNO_2026/JUNO_2026_second_release/"
                "Bari_Group_Release_2026.a/pubblicazione/json/bestfit_ranges_FIT.json")
PAGES = ("index.html", "results.html", "earlier-releases.html", "data.html")


def allowed() -> set[str]:
    out: set[str] = set()
    for src in (ROOT / "site-src/data/releases.yaml", ROOT / "drafts/data/releases.yaml"):
        if not src.exists():
            continue
        for rel in yaml.safe_load(src.read_text(encoding="utf-8"))["releases"]:
            for by in (rel.get("values") or {}).values():
                for e in by.values():
                    if e.get("acc"):
                        out.add(str(e["acc"]))
                    add(out, e.get("best"), e.get("s3"))
    # The home page's precision chart: every release of the parameter history.
    hist = yaml.safe_load((ROOT / "site-src/data/history.yaml").read_text(encoding="utf-8"))
    for rel in hist["releases"]:
        for by in (rel.get("values") or {}).values():
            for e in by.values():
                add(out, e.get("best"), e.get("s3"))
    # The release's other data sets (the key-number cards quote the one
    # without JUNO), when the release itself is on this machine.
    if RELEASE_JSON.exists():
        import json
        for ds in json.loads(RELEASE_JSON.read_text(encoding="utf-8"))["params"].values():
            for e in ds.values():
                add(out, e["bf"], [e["3s"][0][0], e["3s"][-1][1]])
    return out


def add(out: set[str], best, s3) -> None:
    if not s3 or best is None or not float(best):
        return
    acc = Decimal(str((float(s3[1]) - float(s3[0])) / 6 / abs(float(best)) * 100))
    for q in ("1", "0.1", "0.01"):
        out.add(str(acc.quantize(Decimal(q), ROUND_HALF_UP)))


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
        print("  ! printed as 1σ accuracy but not one sixth of a 3σ range over the best fit:")
        for b in bad:
            print("      " + b)
        sys.exit(1)
    print(f"all {n} '1σ accuracy' values are the papers' definition")


if __name__ == "__main__":
    main()
