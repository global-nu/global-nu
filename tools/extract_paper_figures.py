#!/usr/bin/env python3
"""Extract figures from a published paper into site-src/images-src/.

    ./.venv/bin/python3 tools/extract_paper_figures.py

Only run against papers whose licence allows redistribution. The 2025 release
is published by the American Physical Society under CC BY 4.0, which permits
further distribution provided attribution to the authors, the article title,
the journal citation and the DOI is maintained — the results page carries all
four beside every figure. This script prints the licence line it found, so the
permission is checked on every run rather than remembered.

A figure's extent is measured, not guessed: the vector drawings that sit above
the caption are unioned into a bounding box and that box is rendered. Nothing
is cropped by hand-typed coordinates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:                                        # pragma: no cover
    sys.exit("Missing dependency: pymupdf  ->  ./setup-venv.sh")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-src" / "images-src"
PDF = Path.home() / "Desktop/JUNO_2026/Reference/PhysRevD.111.093006.pdf"

# figure number -> output basename
WANTED = {
    3: "prd111-093006-fig3-global-projections",
    4: "prd111-093006-fig4-th23-th13",
    7: "prd111-093006-fig7-dm2ee-dm2sol",
}

LICENCE = re.compile(r"Creative Commons Attribution 4\.0 International", re.I)
DPI = 260


def licence_of(doc) -> str | None:
    text = doc[0].get_text("text")
    m = LICENCE.search(text)
    if not m:
        return None
    i = text.find("Published by the American Physical Society")
    return " ".join(text[i:i + 300].split()) if i >= 0 else m.group(0)


def figure_box(page, caption_rect) -> pymupdf.Rect | None:
    """Union of the vector drawings that belong to this figure.

    The figure is whatever is drawn above the caption and below whatever text
    precedes it, so both edges come from the page itself.
    """
    # Only running prose bounds the figure from above. Axis labels and tick
    # numbers are text blocks too, and treating them as prose put the top edge
    # in the middle of the plot — the first attempt cropped every figure away.
    top_limit = 0.0
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, txt = block[:5]
        words = len(txt.split())
        if y1 <= caption_rect.y0 - 4 and words >= 12 and (x1 - x0) > 180:
            top_limit = max(top_limit, y1)

    box = None
    for d in page.get_drawings():
        r = d["rect"]
        if r.y1 <= caption_rect.y0 - 2 and r.y0 >= top_limit - 2 and r.height > 2:
            box = r if box is None else box | r
    if box is None or box.height < 40:
        return None

    # Axis labels and tick numbers are text, not drawings, so the union of the
    # drawings stops just inside them and the first crop sliced the bottom row
    # of numbers in half. Take in every text block that sits within the plot's
    # own band, and let the caption set the lower edge.
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, txt = block[:5]
        if not txt.strip():
            continue
        if y0 >= box.y0 - 14 and y1 <= caption_rect.y0 - 2 and \
           x1 >= box.x0 - 30 and x0 <= box.x1 + 30:
            box = box | pymupdf.Rect(x0, y0, x1, y1)
    box.y1 = caption_rect.y0 - 3
    # No padding at the bottom: the caption starts there, and 6pt of it was
    # showing up as a sliver of prose under the axes.
    return box + (-6, -6, 6, 0)


def main() -> None:
    if not PDF.exists():
        sys.exit(f"source PDF not found: {PDF}")
    doc = pymupdf.open(PDF)

    lic = licence_of(doc)
    if not lic:
        sys.exit("no CC BY licence line found on page 1 — refusing to extract "
                 "figures from a paper whose terms are not stated")
    print("licence:", lic[:160], "\n")

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for page in doc:
        for rect in page.search_for("FIG. "):
            line = page.get_text("text", clip=pymupdf.Rect(
                rect.x0, rect.y0 - 1, page.rect.x1, rect.y1 + 3))
            m = re.match(r"FIG\.\s*(\d+)\.", " ".join(line.split()))
            if not m:
                continue
            num = int(m.group(1))
            if num not in WANTED:
                continue
            box = figure_box(page, rect)
            if box is None:
                print(f"  ! FIG. {num}: could not measure its extent — skipped")
                continue
            pix = page.get_pixmap(clip=box, dpi=DPI)
            dest = OUT / f"{WANTED[num]}.png"
            pix.save(dest)
            print(f"  ok  FIG. {num}  page {page.number + 1}  "
                  f"{pix.width}×{pix.height}px  -> {dest.name}")
            written += 1

    print(f"\n{written} figure(s) written to {OUT.relative_to(ROOT)}")
    print("Attribution is required wherever these appear: authors, title, "
          "journal citation and DOI.")


if __name__ == "__main__":
    main()
