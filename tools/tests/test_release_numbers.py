#!/usr/bin/env python3
"""Check the published numbers against the paper they claim to come from.

This is the test this project exists for. The failure mode it guards against
is not a typo: it is a table that looks right, reads plausibly, and belongs to
a different analysis. Attributing someone else's numbers to an author on their
own site is the worst error possible here, and it has happened before.

So the values are not compared against a list kept in this file — that list
could drift with the page. They are re-extracted from the PDF of the published
paper on every run, and every one of them must appear in the built HTML.

    python3 tools/tests/test_release_numbers.py [path/to/PhysRevD.111.093006.pdf]

Default source: ~/Desktop/JUNO_2026/Reference/PhysRevD.111.093006.pdf
Requires: pypdf (installed by ./setup-venv.sh)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF = Path.home() / "Desktop/JUNO_2026/Reference/PhysRevD.111.093006.pdf"
PAGE = ROOT / "site" / "results.html"

# The (1,2)-sector update. Two of the six cards on the home page come from
# this paper, not from the 2025 release, so they must be checked against it —
# checking them against Table I of the full release would have been checking
# them against numbers they deliberately supersede.
PDF_2026 = ROOT / "var" / "history-sources" / "bari-2026-2511.21650.pdf"

# Row label in the paper -> label as written on the page. Keeping both here
# makes the mapping explicit rather than implied by ordering.
ROWS = {
    "δm2=10−5 eV2": "δm² / 10⁻⁵ eV²",
    "sin2 θ12=10−1": "sin²θ₁₂ / 10⁻¹",
    "jΔm2j=10−3 eV2": "|Δm²| / 10⁻³ eV²",
    "sin2 θ13=10−2": "sin²θ₁₃ / 10⁻²",
    "sin2 θ23=10−1": "sin²θ₂₃ / 10⁻¹",
    "δ=π": "δ/π",
}


def table_numbers(pdf: Path) -> dict[str, list[str]]:
    """Every number of Table I, row by row, straight out of the PDF."""
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Missing dependency: pypdf  ->  ./setup-venv.sh")

    text = ""
    for page in PdfReader(str(pdf)).pages:
        t = page.extract_text() or ""
        if "TABLE I." in t and "Best fit" in t:
            text = t
            break
    if not text:
        sys.exit(f"Table I not found in {pdf}")

    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        for key in ROWS:
            if line.startswith(key) or line.lstrip().startswith(key):
                nums = re.findall(r"\d+\.\d+|\b\d+\b", line[len(key):])
                out.setdefault(ROWS[key], []).extend(nums)
        # continuation rows carry only an ordering and its numbers
        m = re.match(r"^(NO|IO)\s+(.*)$", line.strip())
        if m and out:
            last = list(out)[-1]
            out[last].extend(re.findall(r"\d+\.\d+|\b\d+\b", m.group(2)))
    return out


# The home page shows the NO best fits as plain decimals rather than in the
# paper's ×10^n normalisation. That conversion is done by hand in the Markdown,
# so it is checked here: paper value, exponent, and what the page must read.
# Cards taken from the 2025 full release.
HOME_CONVERSIONS = [
    ("sin²θ₁₃", "sin2 θ13=10−2", -2, "0.0223"),
    ("sin²θ₂₃", "sin2 θ23=10−1", -1, "0.473"),
]

# Cards taken from the 2026 (1,2)-sector update, Table I, final block
# ("w/ SNO+ & JUNO 2025"). Label -> (exponent, value shown on the card).
HOME_2026 = [
    ("δm²", "dm2", 0, "7.48"),
    ("sin²θ₁₂", "sin2_th12", -1, "0.3085"),
]


# The hero figure on index.html (ranges-hero.svg) draws one row per
# parameter, normal ordering only, with its best fit printed exactly as
# tools/make_figures.py formats it (Python's "%g", so "1.20" prints as
# "1.2"). No unit conversion — these are the paper's own values, the same
# ones that appear as the first number of each Table I row.
HERO_ROWS = [
    ("δm²", "δm2=10−5 eV2"),
    ("|Δm²|", "jΔm2j=10−3 eV2"),
    ("sin²θ₁₂", "sin2 θ12=10−1"),
    ("sin²θ₁₃", "sin2 θ13=10−2"),
    ("sin²θ₂₃", "sin2 θ23=10−1"),
    ("δ/π", "δ=π"),
]


def check_hero(rows: dict[str, list[str]]) -> list[str]:
    """The best-fit values drawn in the home page's hero figure must be the
    paper's own normal-ordering best fits, present on index.html as drawn."""
    home = ROOT / "site" / "index.html"
    if not home.exists():
        return ["site/index.html not found — run build.py first"]
    html = home.read_text(encoding="utf-8")
    haystack = set(re.findall(r"\d+\.\d+|\b\d+\b", html))
    problems = []
    for name, key in HERO_ROWS:
        best = float(rows[ROWS[key]][0])          # first number = NO / only row
        shown = f"{best:g}"
        if shown not in haystack:
            problems.append(
                f"{name} (ranges-hero best fit): {shown} not present on index.html")
    return problems


def stats_block(html: str) -> str:
    """Just the six stat cards.

    A bare `shown in html` would be satisfied by the same digits appearing
    anywhere on the page — and they do: every sparkline's <title> carries the
    historical values, so a card could be changed to a wrong number and still
    "be present". The check is scoped to the block the cards live in.
    """
    i = html.find('<div class="stats')
    if i < 0:
        return ""
    return html[i:html.find("</div>", html.rfind('<!--include:spark-delta_pi'))]


def check_home(rows: dict[str, list[str]]) -> list[str]:
    """The decimals on index.html must equal each card's own source paper.

    Four cards come from the 2025 full release, checked against Table I of the
    PDF re-read above. Two — dm2 and sin2 th12 — were superseded by the 2026
    (1,2)-sector update and are checked against the register entry for that
    paper, which tools/tests/test_history_numbers.py re-extracts from its own
    cached PDF on every run. Checking them against the 2025 table would have
    been checking them against numbers they deliberately replace.
    """
    home = ROOT / "site" / "index.html"
    if not home.exists():
        return ["site/index.html not found — run build.py first"]
    html = home.read_text(encoding="utf-8")
    cards = stats_block(html)
    if not cards:
        return ["the stat-card block was not found on index.html"]
    problems = []

    for name, key, exponent, shown in HOME_CONVERSIONS:
        best = float(rows[ROWS[key]][0])          # first number of the row
        expected = best * (10 ** exponent)
        if abs(float(shown) - expected) > 1e-12:
            problems.append(
                f"{name}: page says {shown}, paper gives {best}×10^{exponent} = {expected}")
        elif shown not in cards:
            problems.append(f"{name}: {shown} is not on a stat card")

    sys.path.insert(0, str(ROOT))
    from tools import history                                  # noqa: E402
    rel = next((r for r in history.load()["releases"]
                if r["group"] == "bari" and r["arxiv"] == "2511.21650"), None)
    if rel is None:
        problems.append("the 2026 (1,2)-sector release is not in the register")
        return problems
    for name, pname, exponent, shown in HOME_2026:
        entry = ((rel.get("values") or {}).get(pname) or {}).get("any")
        if not entry:
            problems.append(f"{name}: the 2026 release records no value for {pname}")
            continue
        expected = entry["best"] * (10 ** exponent)
        if abs(float(shown) - expected) > 1e-12:
            problems.append(
                f"{name}: card says {shown}, the 2026 paper gives "
                f"{entry['best']}×10^{exponent} = {expected}")
        elif shown not in cards:
            problems.append(f"{name}: {shown} is not on a stat card")
    return problems


def main() -> None:
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PDF
    if not pdf.exists():
        sys.exit(f"source PDF not found: {pdf}\n"
                 "Pass the path as an argument, or place the published paper there.")
    if not PAGE.exists():
        sys.exit(f"{PAGE} not found — run build.py first")

    html = PAGE.read_text(encoding="utf-8")
    # The page writes ranges as "7.21 – 7.52"; compare bare numbers only.
    haystack = set(re.findall(r"\d+\.\d+|\b\d+\b", html))

    rows = table_numbers(pdf)
    if len(rows) != len(ROWS):
        sys.exit(f"parsed {len(rows)} of {len(ROWS)} rows from the PDF — parser needs fixing")

    missing, checked = [], 0
    for label, nums in rows.items():
        for n in nums:
            checked += 1
            if n not in haystack:
                missing.append(f"{label}: {n}")

    for label, nums in rows.items():
        print(f"  {label:<20} {len(nums):>2} values from Table I")

    missing += check_home(rows)
    missing += check_hero(rows)

    if missing:
        print("\n  ! a value in the paper table is missing from the page,\n"
              "    or a home-page conversion does not match the paper:")
        for m in missing:
            print("      " + m)
        sys.exit(1)

    print(f"\nall {checked} numbers of Table I appear on results.html")
    print(f"the {len(HOME_CONVERSIONS)} stat cards from the 2025 release and the "
          f"{len(HOME_2026)} from the 2026 (1,2)-sector update match their own papers")
    print(f"the {len(HERO_ROWS)} hero-figure best fits on index.html match the paper")


if __name__ == "__main__":
    main()
