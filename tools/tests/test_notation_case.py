#!/usr/bin/env python3
"""Notation never passes through text-transform: uppercase.

    ./.venv/bin/python3 tools/tests/test_notation_case.py

The design sets some labels in capitals — table headers, panel titles — with
CSS. CSS applies the Unicode uppercase mapping, and that mapping does not know
that case is meaning in physics notation:

    δm²  ->  ΔM²      the solar splitting, drawn as the atmospheric one
    σ    ->  Σ        a standard deviation, drawn as a summation
    δ/π  ->  Δ/Π      the CP phase, drawn as a mass splitting
    eV   ->  EV       not a unit

Antonio caught the σ on results.html. It was not four table headers: every
panel title on history.html was going through the same rule, so both mass
splittings were printed as "ΔM²" on the page whose subject is telling them
apart. The fix is a span, .sym, that resets the transform — the same reset
.figure__unit already carried for the units beside these very labels.

This test reads the real stylesheet for the selectors that capitalise, walks
the built pages with a real parser, and fails if notation sits inside one of
them unprotected. It is written against the rule rather than against the five
labels that were wrong, because the next label added to a capitalised heading
will be wrong in exactly the same silent way.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "site-src" / "assets" / "css" / "site.css"
SITE = ROOT / "site"

# What must survive a capital: lower-case Greek, and the two Latin fragments
# whose meaning is carried by their case.
NOTATION = re.compile(r"[α-ω]|eV|m²")

# Classes whose CSS resets the transform. Read from the stylesheet below, not
# assumed, so removing a reset breaks this test rather than the pages.
protected: set[str] = set()

problems: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  ok   {label}")
    else:
        problems.append(label)
        print(f"  FAIL {label}" + (f"\n         {detail}" if detail else ""))


css = CSS.read_text(encoding="utf-8")
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
    sels, body = " ".join(m.group(1).split()), m.group(2)
    if "text-transform:none" in body.replace(" ", ""):
        protected.update(re.findall(r"\.([a-zA-Z0-9_-]+)", sels))

UPPER = []
for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
    sels, body = " ".join(m.group(1).split()), m.group(2)
    if "text-transform:uppercase" in body.replace(" ", ""):
        for sel in sels.split(","):
            UPPER.append(sel.strip())

check("the stylesheet still capitalises something, so this test has a job",
      bool(UPPER), "no text-transform:uppercase found — has the design changed?")
check("and still carries a reset for notation",
      "sym" in protected, f"protected classes: {sorted(protected)}")


def matches(sel: str, stack: list[tuple[str, set[str]]]) -> bool:
    """Does the element on top of `stack` match this descendant selector?

    Handles the shapes the stylesheet actually uses — "tag", ".class",
    "tag.class", and any of those separated by spaces — which is every
    capitalising selector in it. A selector this cannot read is reported
    rather than skipped, so the test never silently stops checking.
    """
    parts = sel.split()
    i = len(stack) - 1
    for part in reversed(parts):
        want_tag = re.match(r"^[a-z0-9]+", part)
        want_cls = set(re.findall(r"\.([a-zA-Z0-9_-]+)", part))
        found = False
        while i >= 0:
            tag, classes = stack[i]
            i -= 1
            if (not want_tag or tag == want_tag.group(0)) and want_cls <= classes:
                found = True
                break
            if part is parts[-1]:
                return False            # the subject must be the element itself
        if not found:
            return False
    return True


class Walker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.bad: list[str] = []

    def handle_starttag(self, tag, attrs):
        cls = set((dict(attrs).get("class") or "").split())
        self.stack.append((tag, cls))
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not NOTATION.search(data):
            return
        if any(protected & cls for _, cls in self.stack):
            return
        # text-transform is INHERITED, so the capitalising element may be any
        # ancestor, not the one the text sits directly inside: the panel
        # titles put their label in a <span> inside the <h4> that carries the
        # rule. Testing only the innermost element made this check pass over
        # the very markup it was written for.
        if any(matches(sel, self.stack[:k + 1])
               for k in range(len(self.stack)) for sel in UPPER):
            self.bad.append(" ".join(data.split())[:60])


pages = sorted(SITE.rglob("*.html"))
check("there are built pages to read", bool(pages), "run build.py first")

offenders: dict[str, list[str]] = {}
for page in pages:
    w = Walker()
    w.feed(page.read_text(encoding="utf-8"))
    if w.bad:
        offenders[page.relative_to(SITE).as_posix()] = w.bad

check("no notation is left inside a capitalised label",
      not offenders,
      "\n         ".join(f"{p}: {', '.join(b)} → would render "
                         f"{', '.join(x.upper() for x in b)}"
                         for p, b in offenders.items()))

# The regression itself, named: if either of these ever loses its .sym the
# check above catches it, but naming them says what was wrong and where.
results = (SITE / "results.html").read_text(encoding="utf-8")
check("the interval headers keep their lower-case sigma",
      results.count('<span class="sym">1σ</span>') >= 2
      and '<span class="sym">3σ</span>' in results,
      "results.html table headers")
history = (SITE / "history.html").read_text(encoding="utf-8")
# A panel title is an <h4> carrying a .figure__unit: that is what marks it as
# a parameter label rather than a piece of prose like "How to read these
# panels". Every one of them must open with the reset.
titles = re.findall(r"<h4>(.*?)</h4>", history, re.S)
panels = [t for t in titles if "figure__unit" in t]
unprotected = [t for t in panels if not t.startswith('<span class="sym">')]
check("every panel title protects its parameter name",
      panels and not unprotected,
      f"{len(panels)} panel titles, {len(unprotected)} unprotected: "
      f"{unprotected[:2]}")
check("and δm² is still δm² there, not ΔM²",
      '<span class="sym">δm²</span>' in history, "history.html panel title")

print(f"\n{checks - len(problems)}/{checks} checks passed")
if problems:
    print("failed: " + ", ".join(problems))
    raise SystemExit(1)
