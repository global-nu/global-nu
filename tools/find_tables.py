#!/usr/bin/env python3
"""Locate the page carrying the oscillation-parameter table in a paper.

Scores each page by how many of the six parameter row labels it shows next to
range markers. Prints the best page so a human can read the table off it —
the transcription itself is never automatic.

    python3 tools/find_tables.py var/history-sources/<file>.pdf [n_chars]
"""
import re, sys
from pypdf import PdfReader

LABELS = [r"δm\s*2|δm2|dm2", r"Δm\s*2|∆m\s*2|Δm2|∆m2", r"sin\s*2\s*θ\s*12|sin2θ12",
          r"sin\s*2\s*θ\s*13|sin2θ13", r"sin\s*2\s*θ\s*23|sin2θ23", r"δ/π|δ\s*/\s*π|δCP"]
RANGE = r"1σ|2σ|3σ|1\s*σ|3\s*σ|best.?fit|Best ﬁt|Best fit"

def main():
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2600
    r = PdfReader(path)
    best, best_score = None, 0
    for i, pg in enumerate(r.pages):
        t = pg.extract_text() or ""
        score = sum(1 for L in LABELS if re.search(L, t)) + (2 if re.search(RANGE, t) else 0)
        if score > best_score:
            best, best_score = i, score
    if best is None:
        print("no candidate page"); return
    print(f"### {path.split('/')[-1]} — page {best+1} (score {best_score}) ###")
    print((r.pages[best].extract_text() or "")[:n])

main()
