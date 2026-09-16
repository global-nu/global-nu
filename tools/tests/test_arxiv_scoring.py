#!/usr/bin/env python3
"""fetch_arxiv's keyword scorer, and the plural forms it used to miss.

    ./.venv/bin/python3 tools/tests/test_arxiv_scoring.py

Why this file exists. On 16 September 2026 the digest ranked "Eclectic
flavour symmetries without flavons" (arXiv:2609.16118) 61st of 66 with a
score of 1, and the top-16 cut dropped it. The title carries the config's
`flavour symmetry` term — in the plural. `_compile` wrapped each term in
\\b…\\b against the singular alone, so the title hit, worth three points
against an abstract hit's one, was never counted. The paper was not the only
casualty: `oscillations` missed `oscillation` the same day.

The old config compensated by hand, and only for one word: `neutrino` and
`neutrinos` were both listed. That patch is what this scorer should not need,
and the last check here is the trap it sets — once a term matches its own
plural, a config that still lists both forms scores the same paper twice and
silently inflates half the page's ranking.

Scoring stays deterministic and keyword-only: no model is on this path, and
the digest page says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import fetch_arxiv                              # noqa: E402

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


def score(title: str, summary: str, high=(), low=()) -> tuple[int, list[str]]:
    return fetch_arxiv.score(title, summary,
                             fetch_arxiv._compile(list(high)),
                             fetch_arxiv._compile(list(low)))


T, A = fetch_arxiv.TITLE_WEIGHT, fetch_arxiv.ABSTRACT_WEIGHT
# score() weights a `high` term twice a `low` one. Spelled out here so a check
# that expects "one title hit" says which list it came from.
HIGH, LOW = 2, 1

# --------------------------------------------------------------------- #
# the plural in the title
# --------------------------------------------------------------------- #
print("\nplurals")

pts, hits = score("Eclectic flavour symmetries without flavons",
                  "the traditional flavour symmetry of the model",
                  low=["flavour symmetry"])
check("a title in the plural scores as a title hit, not as nothing "
      "(arXiv:2609.16118, the paper that prompted this file)",
      pts == LOW * (T + A) and hits == ["flavour symmetry"], f"{pts} {hits}")

pts, _ = score("Neutrino oscillations in matter", "", high=["oscillation"])
check("'oscillations' matches the configured 'oscillation'", pts == HIGH * T, pts)

pts, _ = score("Neutrino mass hierarchies", "", high=["mass hierarchy"])
check("a -y term matches its -ies plural", pts == HIGH * T, pts)

pts, _ = score("Searches for sterile neutrinos", "", high=["sterile"])
check("a term already ending in -e pluralises", pts == HIGH * T, pts)

# --------------------------------------------------------------------- #
# what must NOT start matching
# --------------------------------------------------------------------- #
print("\nboundaries hold")

pts, _ = score("An innovation in detector design", "", low=["nova"])
check("'nova' still does not match 'innovation'", pts == 0, pts)

pts, _ = score("Supernovae and their remnants", "", low=["supernova"])
check("'supernova' matches 'supernovae'", pts == LOW * T, pts)

pts, _ = score("Reactorless neutrino sources", "", low=["reactor"])
check("a plural suffix does not license an arbitrary suffix "
      "('reactorless' is not 'reactors')", pts == 0, pts)

pts, _ = score("", "the modulus of the amplitude", low=["modular"])
check("'modular' does not match unrelated words sharing a stem", pts == 0, pts)

# --------------------------------------------------------------------- #
# the trap: a config that still lists both forms
# --------------------------------------------------------------------- #
print("\nno double counting")

pts, hits = score("Neutrinos from supernovae", "", high=["neutrino", "neutrinos"])
check("a term and its own plural, both listed, score once — not twice",
      pts == HIGH * T and hits == ["neutrino"], f"{pts} {hits}")

from tools.news.common import load_config                       # noqa: E402
kw = load_config()["arxiv"]["keywords"]
stems = kw["high"] + kw["low"]
# Containment, not just the plural: `modular` fires inside `modular
# invariance` too, so listing both scores one phrase twice — the same
# inflation the plural rule was about, wearing a different hat.
dupes = [t for t in stems
         if any(o != t and fetch_arxiv._compile([o])[0][1].search(t.lower())
                for o in stems)]
check("no shipped term is already matched by another, by plural or by "
      "containment — either would score one phrase twice",
      not dupes, f"redundant: {dupes}")

# --------------------------------------------------------------------- #
# the gate: naming the field is not the same as scoring well
# --------------------------------------------------------------------- #
print("\nthe on-topic gate")

REQ = ["neutrino", "lepton", "seesaw", "flavon"]
gate = lambda t, a="": fetch_arxiv.on_topic(t, a, fetch_arxiv._compile_stem(REQ))

check("a paper that never names the field is out, however it scores — "
      "the X-ray binary whose 'quasi-periodic oscillations' scored 8 and "
      "reached the page on 16 September 2026",
      not gate("Compelling evidence of a link between the lags of the "
               "quasi-periodic oscillations and the radio jet in the "
               "black-hole X-ray binary GRS 1915+105"), "")

check("...and so is an axion paper that borrows the same word",
      not gate("(Re)constructing Accurate Axion Oscillations"), "")

check("a supernova paper about supernovae, not about their neutrinos, is out",
      not gate("Which Type Ia supernova observables best indicate the ages "
               "of their progenitors?"), "")

check("a supernova paper that IS about the neutrinos stays",
      gate("Supernova cooling from neutrinophilic dark matter"), "")

check("the field's word in the abstract alone is enough — the gate reads "
      "both, unlike the title/abstract weighting",
      gate("Eclectic flavour symmetries without flavons",
           "a realistic model of lepton masses"), "")

check("an empty requirement list disables the gate rather than emptying "
      "the page", fetch_arxiv.on_topic("anything at all", "", []), "")

cfg_req = load_config()["arxiv"]["keywords"].get("require_any")
check("the shipped config actually sets the gate", bool(cfg_req), cfg_req)

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    sys.exit(1)
print(f"all {checks} checks pass — a plural in the title is worth what a "
      f"title is worth, and is worth it exactly once")
