#!/usr/bin/env python3
"""Build the photograph gallery from site-src/data/photos.yaml.

    ./.venv/bin/python3 tools/make_gallery.py
        -> site-src/data/figures/gallery.html

Only entries marked `keep` are rendered, and each one is rendered *with* its
credit: author, licence and a link to the file page on Commons. The credit is
not decoration — it is the condition under which the picture may be here at
all, so the generator refuses to emit an image whose licence or file page is
missing rather than publish it bare.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site-src" / "data" / "photos.yaml"
CANDIDATES = ROOT / "var" / "photo-candidates"
IMAGES = ROOT / "site-src" / "images-src"
OUT = ROOT / "site-src" / "data" / "figures" / "gallery.html"


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def main() -> None:
    doc = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    kept = [p for p in doc["photos"] if p.get("status") == "keep"]
    if not kept:
        sys.exit("nothing marked keep in photos.yaml")

    cards, problems = [], []
    for p in kept:
        for field in ("file", "page", "licence"):
            if not p.get(field):
                problems.append(f'{p.get("title", "?")}: no {field}')
        src = CANDIDATES / (p.get("file") or "")
        if not src.exists():
            problems.append(f'{p.get("title","?")}: file missing from the candidate folder')
        else:
            IMAGES.mkdir(parents=True, exist_ok=True)
            dest = IMAGES / src.name
            if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                dest.write_bytes(src.read_bytes())
        if problems and problems[-1].startswith(p.get("title", "?")):
            continue

        # images-src/x.png is published as images/x.png by build.py's pipeline
        name = Path(p["file"]).stem + (".png" if p["file"].lower().endswith(".png") else ".jpg")
        author = p.get("author_short") or p.get("author") or "unknown author"
        lic, lic_url = p["licence"], p.get("licence_url")
        lic_html = (f'<a href="{esc(lic_url)}">{esc(lic)}</a>' if lic_url else esc(lic))
        cards.append(
            '<figure class="shot">'
            f'<img src="images/{esc(name)}" alt="{esc(p.get("caption") or p["subject"])}" '
            'loading="lazy">'
            f'<figcaption><b>{esc(p["subject"])}</b>{esc(p.get("caption") or "")}'
            f'<span class="shot__credit">{esc(author)} · {lic_html} · '
            f'<a href="{esc(p["page"])}">Wikimedia Commons</a></span></figcaption>'
            '</figure>')

    if problems:
        print("  ! not rendered, because a credit cannot be built:")
        for pr in problems:
            print("      " + pr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('<div class="shots">' + "".join(cards) + "</div>", encoding="utf-8")
    print(f"gallery: {len(cards)} photograph(s) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
