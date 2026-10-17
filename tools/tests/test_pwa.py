#!/usr/bin/env python3
"""The site is installable as an app, in both builds.

    ./.venv/bin/python3 tools/tests/test_pwa.py

  1. manifest.webmanifest is valid JSON with name, start_url, display and
     icons, and every icon exists with the pixel size it declares;
  2. every page links the manifest;
  3. sw.js exists, and every URL it precaches exists in the tree, with the
     ?v= hash the pages use;
  4. the worker never caches the data downloads (the app is for reading).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

problems: list[str] = []


def check(label: str, ok: bool) -> None:
    if not ok:
        problems.append(label)


def tree(t: Path) -> None:
    tag = t.name
    m = json.loads((t / "manifest.webmanifest").read_text(encoding="utf-8"))
    for k in ("name", "short_name", "start_url", "display", "icons"):
        check(f"{tag}: manifest has {k}", bool(m.get(k)))
    for ic in m["icons"]:
        f = t / ic["src"]
        check(f"{tag}: icon {ic['src']} exists", f.is_file())
        if f.is_file():
            w, h = Image.open(f).size
            check(f"{tag}: icon {ic['src']} is {ic['sizes']}", f"{w}x{h}" == ic["sizes"])
    for page in t.rglob("*.html"):
        if {"lite", "release-2026a", "data"} & set(page.relative_to(t).parts):
            continue
        check(f"{tag}: {page.relative_to(t)} links the manifest",
              'rel="manifest"' in page.read_text(encoding="utf-8", errors="replace"))
    sw = (t / "sw.js").read_text(encoding="utf-8")
    pre = json.loads(re.search(r"var PRECACHE = (\[.*?\]);", sw, re.S).group(1))
    versions = build.asset_versions()
    for u in pre:
        path, _, v = u.partition("?v=")
        f = t / ("index.html" if path == "./" else path)
        check(f"{tag}: precached {u} exists", f.is_file())
        if v:
            check(f"{tag}: precached {u} has the current hash", versions.get(path) == v)
    check(f"{tag}: sw.js has a version", "{{version}}" not in sw)
    never = re.search(r"var NEVER = (/.*?/i);", sw).group(1)
    for ext in ("csv", "json", "gz", "zip", "txt"):
        check(f"{tag}: .{ext} is never cached", f"{ext}|" in never or f"|{ext}" in never)
    check(f"{tag}: data/ is never cached", "data|" in never)


def main() -> None:
    for t in (ROOT / "site", ROOT / "site-draft"):
        if (t / "index.html").exists():
            tree(t)
    if problems:
        print("  ! app files are wrong:")
        for p in problems[:30]:
            print("      " + p)
        sys.exit(1)
    print("app: manifest, icons, links and service worker are consistent in both builds")


if __name__ == "__main__":
    main()
