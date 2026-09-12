#!/usr/bin/env python3
"""The conference subject classifier, on this project's own real records.

    ./.venv/bin/python3 tools/tests/test_conf_affinity.py

A classifier is tested on the data it has to classify, not on examples written
to make it pass. This reads real INSPIRE, Indico and Neutrino Unbound records
— 92 of them in tools/tests/data/conf/, copied out of var/news/cache/ — and
demands the right tier on a named subset, meeting by meeting.

COPIED, NOT READ FROM THE LIVE CACHE, and that is the point of the directory.
`var/` is in .gitignore and every pipeline run rewrites it: a test pointed at
it cannot run on another machine, and it changes under its own feet the moment
the INSPIRE sweep adds records. A fixture has to be immutable or it is testing
the weather. The files are the cache of 2026-09-12 for INSPIRE and Indico, and
of 2026-09-08 for Neutrino Unbound — the last complete snapshot before
nu.to.infn.it started answering ConnectTimeout.

The expectations are not the author's opinion. They come from the table at the
top of tools/news/affinity.py, which is anchored on the arXiv subject taxonomy
and on INSPIRE's own `inspire_categories` vocabulary.

Four things a syntax check would not see:

1. THE RIGHT TIER on the real records. In particular that no general meeting
   (ICHEP, LHCP, SUSY, Pheno, Blois, Physics in Collision) is read as a
   neutrino one, and that nothing from QCD / hadrons / Higgs / targetry gets
   there by contact.
2. NO FALSE POSITIVE FROM A SINGLE WORD. "neutron" is not "neutrino", and a
   Higgs workshop that lists neutrino masses among its keywords stays
   `adjacent`. The boundaries are LETTERS, not `\\b`: acronyms arrive glued to
   their year (ARENA2026, NNN26, DIS2026) and `\\b` would not match them.
3. DETERMINISM. Same record, same answer, always: the page is rebuilt every
   morning, and a tier that wobbles would change a meeting's colour with
   nothing having changed.
4. THE REFUSAL TO GUESS. A record with no title, no acronym and no categories
   is `unknown`, never a plausible tier — the same rule this site applies to
   every number it prints.

Plus the parts that hold the rest of the chain together: the signal priority,
the colour tokens, and the fact that the classes the renderer emits are ones
site.css actually defines.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.news import affinity                                  # noqa: E402

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


# --------------------------------------------------------------------------- #
# the real records
# --------------------------------------------------------------------------- #
CACHE = ROOT / "tools/tests/data/conf"
TODAY_FILES = ("inspire-conf.json", "inspire-conf-general.json",
               "indico-conf.json")
SNAPSHOT = CACHE / "nu-unbound.json"


def load(name: str) -> list[dict]:
    path = CACHE / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["records"]


RECORDS = [r for name in TODAY_FILES for r in load(name)]


def find(fragment: str, pool: list[dict] | None = None) -> dict | None:
    """The record whose title or acronym contains this fragment.

    By text, not by index: the cache keeps INSPIRE's own order and that
    changes from one day to the next. A test pinned to a position would be
    testing INSPIRE, not the classifier.
    """
    low = fragment.lower()
    for rec in (RECORDS if pool is None else pool):
        hay = (rec.get("title", "") + " "
               + (rec.get("extra", {}).get("acronym") or "")).lower()
        # The non-breaking space is real: INSPIRE stores "NEUTRINO 2026".
        if low in hay.replace(" ", " "):
            return rec
    return None


# A fragment of the title or acronym -> the expected tier. A fragment and not
# a whole title: INSPIRE changes punctuation without notice, and this test must
# fail when the CLASSIFICATION changes, not when a comma does.
EXPECTED: list[tuple[str, str, str]] = [
    # --- core: the meeting IS about neutrinos ------------------------------
    ("NEUTRINO 2026", "core", "the field's parent conference"),
    ("NOW 2026", "core", "Neutrino Oscillation Workshop, an explicit series"),
    ("Neutel 27", "core", "Neutrino Telescopes, an explicit series"),
    ("INSS 2026", "core", "the International Neutrino Summer School"),
    ("NNN26", "core", "Next Generation Nucleon Decay and Neutrino Detectors"),
    ("NBI/RaDIATE", "core", "Neutrino Beams and Instrumentation"),
    ("ARENA2026", "core", "an acronym glued to its year"),
    ("MagCEvNS2026", "core", "CEvNS: coherent neutrino-nucleus scattering"),
    ("New Physics Opportunities at Neutrino Faci", "core", "NPN 2026"),
    ("Neutrino Geoscience 2026", "core", "geoneutrinos"),
    ("Neutrino Physics and Machine Learning", "core", "NPML"),
    ("Neutrinoless double beta", "core",
     "0νββ: no beam of neutrinos, but it is neutrino physics"),
    # --- broad: neutrinos are ONE session ----------------------------------
    ("ICHEP 2026", "broad", "ICHEP"),
    ("LHCP2026", "broad", "LHCP 2026, by acronym"),
    ("Large Hadron Collider Physics Conference", "broad",
     "LHCP 2027, by title"),
    ("Supersymmetry and Unification", "broad", "SUSY"),
    ("Phenomenology 2026 Symposium", "broad", "PHENO"),
    ("Blois 2026", "broad", "Rencontres de Blois"),
    ("PIC 2026", "broad", "Physics in Collision"),
    # --- adjacent: neutrinos are incidental --------------------------------
    ("Quark Matter 2027", "adjacent", "heavy ions"),
    ("DIS2026", "adjacent", "Deep Inelastic Scattering"),
    ("QCHS26", "adjacent", "Quark Confinement and the Hadron Spectrum"),
    ("HH2026", "adjacent", "Higgs Hunting"),
    ("High Power Targetry", "adjacent",
     "targets for neutrino beams: technology, not neutrino physics"),
]


print("the fixture")
check("the committed fixture holds its 29 INSPIRE and Indico records",
      len(RECORDS) == 29, f"{len(RECORDS)} read from {CACHE}")
check("and the 63-record Neutrino Unbound snapshot of 2026-09-08",
      SNAPSHOT.exists() and len(load("nu-unbound.json")) == 63,
      f"{len(load('nu-unbound.json'))} records")

if not RECORDS:
    print(f"\n  the fixture at {CACHE} is missing: the test cannot run")
    sys.exit(1)

print("\nthe tier each real record gets")
missing, wrong = [], []
for fragment, expected, why in EXPECTED:
    rec = find(fragment)
    if rec is None:
        missing.append(fragment)
        continue
    got = affinity.classify(rec)
    if got["tier"] != expected:
        wrong.append(f"{fragment!r}: expected {expected}, got {got['tier']} "
                     f"({got['why']}) — {why}")
check(f"all {len(EXPECTED)} expected meetings are in the fixture",
      not missing, "; ".join(missing))
check("every expected meeting gets its own tier", not wrong,
      "\n         ".join(wrong))

tiers = [affinity.classify(r)["tier"] for r in RECORDS]
check("every tier is one of the five declared",
      all(t in affinity.TIERS for t in tiers), str(sorted(set(tiers))))

# THE CHECK THAT MATTERS MOST: nothing in the general block may be read as
# `core`. An ICHEP painted as a neutrino conference would tell the reader
# something false about that meeting's programme — the same species of error
# (attributing to someone what they did not say) this whole site is built to
# avoid.
general = load("inspire-conf-general.json")
core_in_general = [r["title"] for r in general
                   if affinity.classify(r)["tier"] == "core"]
check("no meeting from the general block is read as `core`",
      not core_in_general, str(core_in_general))

print("\nno false positive from one word")
neutron = {"title": "Workshop on neutron scattering and neutron stars",
           "extra": {}}
check("«neutron» is not read as «neutrino»",
      affinity.classify(neutron)["tier"] != "core",
      affinity.classify(neutron)["why"])

higgs = {"title": "Higgs Hunting 2026",
         "extra": {"acronym": "HH2026",
                   "keywords": ["Higgs boson; neutrino masses; BSM"]}}
check("a Higgs workshop with «neutrino» among its keywords stays `adjacent`",
      affinity.classify(higgs)["tier"] == "adjacent",
      affinity.classify(higgs)["why"])

for acr in ("ARENA2026", "NNN26", "DIS2026", "LHCP2026"):
    got = affinity.classify({"title": "", "extra": {"acronym": acr}})
    check(f"an acronym glued to its year is still recognised: {acr}",
          got["tier"] != "unknown", f'{got["tier"]} — {got["why"]}')

got = affinity.classify({"title": "", "extra": {"acronym": "SUSYNOW"}})
check("a substring inside another word does not count (SUSYNOW)",
      got["tier"] == "unknown", f'{got["tier"]} — {got["why"]}')

print("\nsignal priority")
rec = {"title": "17th International Conference on Particle Physics",
       "extra": {"acronym": "NuFact 2027"}}
got = affinity.classify(rec)
check("the series beats the words of the title",
      got["tier"] == "core" and "series" in got["why"],
      f'{got["tier"]} — {got["why"]}')

rec = {"title": "47th Course of the International School/Workshop of "
                "Nuclear Physics",
       "extra": {"acronym": "Neutrinos in Cosmology, in Astro-, Particle- "
                            "and Nuclear Physics"}}
got = affinity.classify(rec)
check("a subject term counts even when only the acronym carries it",
      got["tier"] == "core" and got["why"].startswith("name"),
      f'{got["tier"]} — {got["why"]}')

got = affinity.classify({"title": "Workshop on what happens now", "extra": {}})
check("a SERIES NAME is never looked for in prose: «now» is not NOW 2026",
      got["tier"] != "core", f'{got["tier"]} — {got["why"]}')

# Provenance (signal d) is empty here, deliberately — see DEFAULT_PROVENANCE.
rec = {"title": "Workshop", "extra": {"provider": "nu-unbound"}}
got = affinity.classify(rec)
check("nothing is lifted by provenance alone", got["tier"] == "unknown",
      f'{got["tier"]} — {got["why"]}')
fake = affinity.scheme_from({"affinity": {"provenance": {"only-nu": "core"}}})
got = affinity.classify({"title": "Workshop",
                         "extra": {"provider": "only-nu"}}, fake)
check("the provenance mechanism is still alive for a single-subject calendar",
      got["tier"] == "core", f'{got["tier"]} — {got["why"]}')
got = affinity.classify(
    {"title": "43rd International Conference on High Energy Physics",
     "extra": {"acronym": "ICHEP 2026", "provider": "only-nu"}}, fake)
check("and it never overrides an explicit series (ICHEP)",
      got["tier"] == "broad", f'{got["tier"]} — {got["why"]}')

rec = {"title": "Workshop on something",
       "extra": {"categories": ["Experiment-HEP", "Astrophysics"]}}
got = affinity.classify(rec)
check("INSPIRE's categories decide when the names say nothing",
      got["tier"] == "broad" and "INSPIRE" in got["why"],
      f'{got["tier"]} — {got["why"]}')

print("\nthe refusal to guess")
for rec in ({"title": "", "extra": {}},
            {"title": "", "extra": {"acronym": "", "categories": []}},
            {}):
    got = affinity.classify(rec)
    check(f"a record with nothing to read stays `unknown` ({rec})",
          got["tier"] == "unknown" and got["label"] == "Not classified",
          f'{got["tier"]} — {got["why"]}')

for rec in RECORDS:
    got = affinity.classify(rec)
    if not got["why"] or got["why"] == got["tier"]:
        check("every decision carries a readable `why`", False,
              f'{rec["title"][:40]}: {got["why"]!r}')
        break
else:
    check("every decision carries a readable `why`", True)

print("\ndeterminism")
once = [affinity.classify(r) for r in RECORDS]
check("the same records give the same answers twice running",
      once == [affinity.classify(r) for r in RECORDS])
check("and a scheme rebuilt from scratch gives the same answers",
      once == [affinity.classify(r, affinity.scheme_from({})) for r in RECORDS])

print("\ntag() writes into the record")
copies = [dict(r, extra=dict(r["extra"])) for r in RECORDS[:5]]
affinity.tag(copies)
check("tag() writes extra['affinity'] on every record",
      all(r["extra"]["affinity"]["tier"] in affinity.TIERS for r in copies))
before = [r["extra"]["affinity"] for r in copies]
affinity.tag(copies)
check("tag() is idempotent: running it twice changes nothing",
      [r["extra"]["affinity"] for r in copies] == before)
bare = {"title": "X", "url": "u", "id": "i"}
affinity.tag([bare])
check("tag() creates `extra` when the record has none", "affinity" in bare["extra"])

# --------------------------------------------------------------------------- #
# the colours, and the markup that wears them
# --------------------------------------------------------------------------- #
print("\nthe colours")
CSS = (ROOT / "site-src/assets/css/site.css").read_text(encoding="utf-8")
for tier in affinity.TIERS:
    colour = affinity.TIER_COLOUR.get(tier, "")
    check(f"tier `{tier}` is painted with a token, not a literal colour",
          colour.startswith("var(--") and colour.endswith(")"), colour)
    check(f"site.css defines the chip for tier `{tier}`",
          f".conf-aff--{tier}{{" in CSS)
for rule in ("span.conf-aff{", ".conf-legend{", ".conf-legend__lead{"):
    check(f"site.css defines {rule[:-1]}", rule in CSS)

# --dec-4 is the one token of the decorative set the chips must NOT use: it
# measures 4.33:1 on --bg and 3.97:1 on --surface in the dark theme (under the
# 4.5 a chip's text needs) and in the light theme it is byte-for-byte
# --accent-2, the conference map's own "general" marker on this same page.
check("no tier uses --dec-4, which fails the dark theme and collides with "
      "--accent-2 in the light one",
      "var(--dec-4)" not in affinity.TIER_COLOUR.values(),
      str(affinity.TIER_COLOUR))

# No literal colour anywhere in the chip and legend rules: everything goes
# through the tokens, which is what makes both themes work.
start = CSS.find("/* ---------- conference affinity ----------")
block = CSS[start:CSS.find("/* ====", start + 10)] if start > 0 else ""
check("the `conference affinity` block of site.css is found whole",
      start > 0 and ".conf-legend__lead" in block)
literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", block)
check("the chip and legend rules fix no literal colour", not literals,
      str(literals))

# Every token the chips use must be defined in BOTH theme blocks. A tier
# painted with a token only the dark block declares would be invisible — or
# inherited — for a reader on the light one.
for tier, colour in affinity.TIER_COLOUR.items():
    token = colour[len("var("):-1]
    for selector in (':root[data-theme="dark"]', ':root[data-theme="light"]'):
        i = CSS.index(selector)
        theme_block = CSS[CSS.index("{", i):CSS.index("}", i)]
        check(f"{token} ({tier}) is defined in {selector}",
              f"{token}:" in theme_block)

print("\nthe markup the renderer emits")
from tools.news import fetch_inspire, render                     # noqa: E402

tagged = [dict(r, extra=dict(r["extra"])) for r in RECORDS]
affinity.tag(tagged)
up, done = fetch_inspire.split(tagged)
markup = (render.affinity_legend(tagged)
          + render._scope_block(tagged, "Test", "nothing"))
used: set[str] = set()
for m in re.finditer(r'class="([^"]+)"', markup):
    used.update(m.group(1).split())
absent = sorted(c for c in used if f".{c}" not in CSS)
check("every class the chips and the legend emit exists in site.css",
      not absent, str(absent))

rows = markup.count("<li>")
n_legend = len(affinity.tiers_present(tagged))
check("every row carries its own chip, plus one per tier in the legend",
      rows > 0 and markup.count('class="conf-aff conf-aff--') == rows + n_legend,
      f'{rows} rows + {n_legend} legend entries, '
      f'{markup.count(chr(34) + "conf-aff conf-aff--")} chips')
check("the listing chip carries its `why` in a tooltip",
      bool(re.search(r'class="conf-aff conf-aff--\w+" title="[^"]+"', markup)))

# A legend of one colour is not a scale, and would only be noise.
one_tier = [r for r in tagged if r["extra"]["affinity"]["tier"] == "core"]
check("a page with only one tier on it prints no legend at all",
      render.affinity_legend(one_tier) == "",
      render.affinity_legend(one_tier)[:60])
check("an untagged record gets no chip rather than an unearned grey one",
      render._affinity_chip({"extra": {}}) == "")

# --------------------------------------------------------------------------- #
# the timeline bars carry the same scale, and the tense moved off the fill
# --------------------------------------------------------------------------- #
# The fill used to say three things at once (ahead / running / concluded) and
# now says one. The other two had to land somewhere a hue cannot argue with:
# "concluded" on the opacity, "under way" on the outline. Built here rather
# than taken from the cache because no meeting is running on most days, so the
# outline would otherwise be untested on every day but a handful.
print("\nthe timeline bars")
from tools.news import figures                                   # noqa: E402

TODAY = _dt.date.today()


def _bar(days_from_today: int, length: int, title: str, acronym: str) -> dict:
    start = TODAY + _dt.timedelta(days=days_from_today)
    end = start + _dt.timedelta(days=length)
    return {"id": f"t:{days_from_today}", "title": title,
            "url": "https://example.org/", "links": {}, "authors": "",
            "date": start.isoformat(), "summary": "",
            "extra": {"acronym": acronym, "place": "Bari, Italy",
                      "opening": start.isoformat(), "closing": end.isoformat(),
                      "upcoming": end >= TODAY,
                      "in_progress": start <= TODAY <= end,
                      "flagship": False}}


bars = [_bar(20, 4, "32nd Conference on Neutrino Physics", "NEUTRINO 2027"),
        _bar(-1, 3, "Workshop on Deep Inelastic Scattering", "DIS2026"),
        _bar(-40, 3, "43rd Conference on High Energy Physics", "ICHEP 2026")]
affinity.tag(bars)
ahead = [b for b in bars if b["extra"]["upcoming"]]
over = [b for b in bars if not b["extra"]["upcoming"]]
svg = figures.conference_timeline(ahead, over, log=logging.getLogger("t"))
rects = re.findall(r'<rect[^>]*style="fill:(var\(--[\w-]+\));opacity:([\d.]+)([^"]*)"', svg)
fills = {f for f, _, _ in rects}
check("every bar is painted with a tier token from affinity.TIER_COLOUR",
      fills and fills <= set(affinity.TIER_COLOUR.values()), str(fills))
check("a `core` meeting's bar is the core colour",
      affinity.TIER_COLOUR["core"] in fills, str(fills))
check("a meeting under way is drawn with an OUTLINE, not a third fill colour",
      sum(1 for _, _, x in rects if "stroke:var(--text)" in x) == 1,
      str([x for _, _, x in rects]))
check("and a concluded meeting is still faded, as it always was",
      any(o != "1" for _, o, _ in rects), str([o for _, o, _ in rects]))
check("the bar's tooltip names the tier and the signal that decided it",
      "Adjacent fields" in svg and "series “DIS”" in svg)
check("an untagged record falls back to the `unknown` grey rather than a tier "
      "it did not earn",
      affinity.TIER_COLOUR["unknown"] in figures.conference_timeline(
          [dict(b, extra={k: v for k, v in b["extra"].items()
                          if k != "affinity"}) for b in ahead], [],
          log=logging.getLogger("t")))

# --------------------------------------------------------------------------- #
# the normal day: the real merge, with Neutrino Unbound back up
# --------------------------------------------------------------------------- #
# The live cache for Neutrino Unbound is empty — nu.to.infn.it has answered
# ConnectTimeout since 9 September 2026 — and on that alone the listing looks
# 29 records long. The realistic case is built from the last complete snapshot
# merged with today's INSPIRE and Indico: this is exactly what the pipeline
# will see on the day nu.to.infn.it comes back, and what _recover_conferences
# in pipeline.py already feeds it in the meantime.
print("\nthe normal day (fixture + the Neutrino Unbound snapshot)")
from tools.news import conferences as cm                         # noqa: E402
from tools.news.common import load_config                        # noqa: E402

_log = logging.getLogger("news.test.affinity")
_log.addHandler(logging.NullHandler())
_log.propagate = False

cfg = load_config()
nu = load("nu-unbound.json")
indico = load("indico-conf.json")
own = cm.sort_for_page(cm.merge(
    [load("inspire-conf.json"), cm.split_scope(nu, "neutrino"),
     cm.split_scope(indico, "neutrino")], _log))
gen = cm.sort_for_page(cm.merge(
    [load("inspire-conf-general.json"), cm.split_scope(nu, "general"),
     cm.split_scope(indico, "general")], _log))
affinity.tag(own, cfg)
affinity.tag(gen, cfg)
everything = own + gen

check("the merged listing is 69 neutrino records and 16 general ones",
      len(own) == 69 and len(gen) == 16, f"{len(own)} / {len(gen)}")

# Deliberately no assertion on how many are UPCOMING: sort_for_page re-derives
# the tense from each record's own dates against today (conferences.
# _refresh_tense), so that number falls by itself as the fixture ages. A test
# that pinned it would fail on a calendar, not on a bug.

SNAPSHOT_EXPECTED: list[tuple[str, str, str]] = [
    ("Gravity@Prague", "adjacent", "pure gravity: no neutrinos"),
    ("AIPHY2", "adjacent", "a school of method, not of neutrino physics"),
    ("NuSym26", "adjacent",
     "nuclear symmetry energy: «NuSym» must NOT read as a neutrino series"),
    ("RPMBT23", "adjacent", "many-body theory"),
    ("ESC26", "adjacent", "scientific computing"),
    ("LIDINE", "related",
     "light detection in noble elements: shared between ν and dark matter"),
    ("SoUP 2026", "related", "a school of underground physics"),
    ("ICPPA-2026", "broad", "particle physics and astrophysics at large"),
    ("Neutrinos in Cosmology", "core",
     "the name is in the acronym, not in the title"),
    ("NuINT 2027", "core", "the NuInt series"),
    ("DISCRETE 2026", "broad", "symmetries at large, caught by acronym"),
    ("Patras 2026", "related", "axions, WIMPs and WISPs"),
    ("UNDARK 2026", "adjacent", "cosmological tensions"),
    ("HEPNP 2027", "broad", "high energy, particles and nuclear physics"),
    ("Neutel 27", "core", "inside the 18-month window, and it must be shown"),
]
missing, wrong = [], []
for fragment, expected, why in SNAPSHOT_EXPECTED:
    c = find(fragment, everything)
    if c is None:
        missing.append(fragment)
        continue
    got = c["extra"]["affinity"]
    if got["tier"] != expected:
        wrong.append(f"{fragment!r}: expected {expected}, got {got['tier']} "
                     f"({got['why']}) — {why}")
check("every meeting the snapshot is expected to carry is in it", not missing,
      "; ".join(missing))
check("and each of them gets its own tier", not wrong,
      "\n         ".join(wrong))

# The check that motivated emptying DEFAULT_PROVENANCE: no chip coloured by
# where the record came from.
lifted = [c for c in everything
          if "listed on" in c["extra"]["affinity"]["why"]
          or "listed by" in c["extra"]["affinity"]["why"]]
check("no record is classified by its provenance alone", not lifted,
      str([c["extra"].get("acronym") for c in lifted]))

unknown = [c for c in own if c["extra"]["affinity"]["tier"] == "unknown"]
check("only a handful of the real records stay `unknown`", len(unknown) <= 8,
      f"{len(unknown)} of {len(own)}: "
      + str([c["extra"].get("acronym") or c["title"][:24] for c in unknown]))

# --------------------------------------------------------------------------- #
# the cap on the concluded tail
# --------------------------------------------------------------------------- #
print("\nthe caps")
up = [c for c in own if c["extra"].get("upcoming")]
done = [c for c in own if not c["extra"].get("upcoming")]
cap = int(((cfg.get("inspire") or {}).get("conferences") or {})
          .get("max_recent", render.MAX_RECENT))
html = render._scope_block(own, "Neutrino conferences", "nothing", cap)
shown_up = html.split("<h3>Recent</h3>")[0].count("<li>")
shown_done = html.count("<li>") - shown_up
check(f"the concluded tail stops at max_recent={cap}", shown_done <= cap,
      f"{shown_done} shown of {len(done)}")
check("UPCOMING is never cut: every meeting inside the window reaches the page",
      shown_up == len(up), f"{shown_up} of {len(up)}")
check("and the heading says how many were left out rather than just how many "
      "are shown",
      (f"{shown_done} of {len(done)}" in html) or shown_done == len(done))

print("\n  --- the fixture's 29 records, as the classifier reads them ---")
for rec in RECORDS:
    got = affinity.classify(rec)
    name = (rec["extra"].get("acronym") or rec["title"])[:40]
    print(f"  {got['tier']:9} {name:42} {got['why']}")

print("\n  --- the 63 Neutrino Unbound records of 2026-09-08 ---")
for rec in nu:
    got = affinity.classify(rec)
    name = (rec["extra"].get("acronym") or rec["title"])[:40]
    print(f"  {got['tier']:9} {rec['extra'].get('opening', '')}  {name:42} "
          f"{got['why']}")

print()
if problems:
    print(f"  ! {len(problems)} of {checks} checks failed")
    for p in problems:
        print("    - " + p)
    sys.exit(1)
print(f"all {checks} checks pass — five tiers, on 92 real conference records")
