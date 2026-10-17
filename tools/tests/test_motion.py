#!/usr/bin/env python3
"""No content waits for an animation, and motion honours the reader's setting.

    ./.venv/bin/python3 tools/tests/test_motion.py

The scroll reveal used to start at opacity 0: a figure below the fold was an
empty box until it scrolled in, and stayed empty in a screenshot or a print.
Two rules, read from the stylesheets themselves:
  1. no .reveal rule sets opacity 0 or visibility hidden;
  2. every element given an `animation:` in a stylesheet has it switched off
     inside a prefers-reduced-motion block of the same stylesheet.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = sorted((ROOT / "site-src" / "assets" / "css").glob("*.css"))
bad = []
for path in CSS:
    css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    for m in re.finditer(r"([^{}]*\.reveal[^{}]*)\{([^}]*)\}", css):
        if re.search(r"opacity\s*:\s*0(?![.\d])|visibility\s*:\s*hidden", m.group(2)):
            bad.append(f"{path.name}: '{m.group(1).strip()}' hides content until it animates")
    reduced = " ".join(b.group(0) for b in re.finditer(
        r"@media[^{]*prefers-reduced-motion\s*:\s*reduce[^{]*\{(?:[^{}]*\{[^}]*\})*[^{}]*\}", css))
    # innermost rules only: a selector inside an @media block is read as the
    # selector, not the at-rule's header
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if not re.search(r"\banimation\s*:(?!\s*none)", m.group(2)):
            continue
        sel = m.group(1).strip().split(",")[0].strip()
        if sel and sel not in reduced:
            bad.append(f"{path.name}: '{sel}' animates with no reduced-motion override")
for b in bad:
    print("  FAIL " + b)
if bad:
    sys.exit(1)
print(f"all motion checks pass ({len(CSS)} stylesheets)")
