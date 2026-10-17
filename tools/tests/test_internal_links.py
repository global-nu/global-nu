#!/usr/bin/env python3
"""Every internal link resolves — the file, and the #anchor inside it.

    ./.venv/bin/python3 tools/tests/test_internal_links.py

build.py reports internal references to missing files but does not fail on
them, and it does not look at fragments. A redesign moves sections around
(history.html#compare became #method for the conversion treatment), and a
link that lands at the top of the wrong page is broken in every way that
matters to a reader. Checks site/ and, when present, site-draft/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HREF = re.compile(r'href="([^"]+)"')
ID = re.compile(r'\sid="([^"]+)"')
COMMENT = re.compile(r"<!--.*?-->", re.S)
TEMPLATE = re.compile(r"<template\b.*?</template>", re.S)


def check_tree(tree: Path) -> list[str]:
    problems = []
    ids: dict[Path, set[str]] = {}

    def ids_of(p: Path) -> set[str]:
        if p not in ids:
            ids[p] = set(ID.findall(p.read_text(encoding="utf-8", errors="ignore")))
        return ids[p]

    for page in sorted(tree.rglob("*.html")):
        text = TEMPLATE.sub("", COMMENT.sub("", page.read_text(encoding="utf-8", errors="ignore")))
        for href in set(HREF.findall(text)):
            if href.startswith(("http://", "https://", "mailto:", "data:", "//", "javascript:")):
                continue
            path, _, frag = href.partition("#")
            path = path.split("?")[0]
            target = (page.parent / path).resolve() if path else page
            if path.endswith("/"):
                target = target / "index.html" if (target / "index.html").exists() else target
            if not target.exists():
                problems.append(f"{page.relative_to(tree)} -> {href}: no such file")
                continue
            if frag and target.suffix == ".html" and frag not in ids_of(target):
                problems.append(f"{page.relative_to(tree)} -> {href}: no id=\"{frag}\"")
    return problems


def main() -> None:
    trees = [ROOT / "site"] + ([ROOT / "site-draft"] if (ROOT / "site-draft" / "index.html").exists() else [])
    problems = []
    for t in trees:
        problems += [f"{t.name}: {p}" for p in check_tree(t)]
    if problems:
        print("  ! broken internal links:")
        for p in sorted(problems)[:60]:
            print("      " + p)
        print(f"  ({len(problems)} in all)")
        sys.exit(1)
    print(f"all internal links and anchors resolve in {', '.join(t.name for t in trees)}")


if __name__ == "__main__":
    main()
