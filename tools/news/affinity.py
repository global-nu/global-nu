"""How close a conference's subject is to this site's own field.

Every meeting on the Conferences page gets one of five tiers, and the page
paints it: the listing chips and the timeline bars are coloured by the answer
this module returns.

Ported from ~/Documents/My Home Page - Claude/tools/news/affinity.py. Two
things are different here and both are deliberate: that project builds two
editions from per-edition YAML and imports `edition` to know which one is
running, where this site has ONE `tools/news/config.yaml` and no edition
module at all; and the palette is this site's, not that one's — see THE
COLOURS below.

WHAT THE SCHEME IS
------------------
Four named tiers plus an explicit unknown, from "the meeting is about our
subject" down to "our subject is incidental to it":

    core      the meeting is ABOUT the field (Neutrino, NuFact, NOW, Neutel,
              NuPhys, INSS, NuInt, NNN, NBI, ARENA, CEvNS, 0vbb …)
    related   the field is a major but not exclusive theme (TAUP, ICRC,
              dark-matter-and-neutrino meetings, multimessenger, underground)
    broad     the field is one session of a general meeting (ICHEP, Moriond,
              Lepton-Photon, EPS-HEP, LHCP, SUSY, PANIC, Pheno, Blois, PIC)
    adjacent  the field is incidental (QCD and heavy ions, colliders and the
              Higgs, accelerators, targetry, instrumentation, cosmology- or
              gravity-only meetings)
    unknown   nothing in the record supports a judgement

WHAT IT IS ANCHORED ON
----------------------
Two published vocabularies, not a private taste.

  * the arXiv subject taxonomy (https://arxiv.org/category_taxonomy) supplies
    the axis the tiers run along: hep-ex/hep-ph at the centre of a particle
    meeting, nucl-ex/nucl-th, gr-qc and astro-ph.CO/HE one step out,
    physics.ins-det and physics.acc-ph out again;
  * INSPIRE's own `inspire_categories` vocabulary (Experiment-HEP,
    Phenomenology-HEP, Theory-HEP, Astrophysics, Gravitation and Cosmology,
    Theory-Nucl, Experiment-Nucl, Instrumentation, Accelerators, …) supplies
    the machine-readable corroboration: INSPIRE stamps it on the conference
    record itself, so it costs no guessing to read.

WHAT IT DOES **NOT** CLAIM
--------------------------
It is a reading aid, nothing more. A tier is this pipeline's reading of a
title, an acronym and INSPIRE's own categories — it is NOT a statement by the
organisers, not a judgement of a meeting's quality or importance, and not a
claim about how much of its programme is actually devoted to the subject. A
general conference tiered `broad` may well hold the year's most important
neutrino talk. The colour says "expect the subject to be one session here",
not "this meeting matters less".

SIGNALS, IN PRIORITY ORDER
--------------------------
The first one that fires decides; the rest are never consulted. The order is
the order of how much the signal actually knows:

  (a) the conference SERIES or ACRONYM, matched against explicit lists. A
      series name is the organisers' own statement of what the meeting is, and
      it is the only signal that can tell NOW (Neutrino Oscillation Workshop)
      from the English word "now" — which is why series terms are matched
      against `extra.acronym` and `extra.series` ONLY, never against prose.
  (b) SUBJECT TERMS, in the title AND in the acronym/series text. Word-bounded,
      always: "neutron" is not "neutrino", and a Higgs workshop that mentions
      neutrino masses in one line of its blurb is not a neutrino conference.
      Never the abstract or the keyword soup, for that same reason.

      THE ASYMMETRY WITH (a) IS DELIBERATE, and it comes from the data.
      Neutrino Unbound routinely puts the meeting's real name in the ACRONYM
      field and a bare fragment in the title: acronym "Neutrinos in Cosmology,
      in Astro-, Particle- and Nuclear Physics" against title "47th Course of
      the International School/Workshop of Nuclear Physics"; acronym "New
      Physics from Galaxy Clustering 2026" against title "5th Workshop";
      acronym "XIX Tonale Winter School on Cosmology 2026" against title
      "Theory for Observers & Observations for Theorists". Reading terms in
      the title alone leaves those unclassifiable even though the record says
      plainly what they are about. Subject WORDS ("neutrino", "gravity",
      "bayesian") are unambiguous wherever they appear, so they may be read
      everywhere; SERIES NAMES ("NOW", "PIC", "DIS", "DISCRETE") are ordinary
      words in prose and stay confined to the acronym field. That is the whole
      of the asymmetry: it is about how ambiguous the token is, not about
      which field it was found in.
  (c) INSPIRE's `inspire_categories`, as corroboration — consulted only when
      (a) and (b) both said nothing. Categories are coarse (half the neutrino
      calendar is stamped "Experiment-HEP"), so they can place a record in a
      tier but must never override a name that says something sharper.
  (d) PROVENANCE, last, and EMPTY here — see DEFAULT_PROVENANCE below for the
      measurement that emptied it. The machinery stays for a future calendar
      that is genuinely subject-specific; where it is used it may only LIFT an
      `unknown`, never outrank an explicit series or title match.

THE COLOURS
-----------
This site has no `--gold/--cyan/--violet/--coral`. It has `--dec-1` … `--dec-5`,
a categorical set, and the assignment below is chosen for THIS page rather
than copied by hue from the other site:

    core      --dec-2   the same blue the conference map on this very page
                        already uses for a neutrino-scope dot (`--no`, which
                        is --dec-2's hex in both themes). One blue, one
                        meaning — "this meeting is about neutrinos" — in both
                        of the page's colour systems instead of two.
    related   --dec-5   green, the one --dec- token nothing else on this page
                        uses, so "astroparticle & underground" cannot be read
                        as one of the map's two categories.
    broad     --dec-1   gold. `--io` (the inverted-ordering amber) is a near
                        neighbour of it, but --io leaves this page entirely
                        with this change: "under way" moved from a fill to an
                        outline, see figures.py.
    adjacent  --dec-3   coral — the far ring, and the same hue the other
                        site's `adjacent` wears, which costs nothing and helps
                        a reader who knows both.
    unknown   --text-mute  a refusal to judge must not look like a judgement.

`--dec-4` (violet) is deliberately NOT used, for a measured reason rather than
a taste: on the dark theme it reaches 4.33:1 on --bg and 3.97:1 on --surface,
under the 4.5:1 a chip's text needs, and in the LIGHT theme its hex (#6d28d9)
is exactly `--accent-2`, which is the conference map's "general particle
physics" marker on this same page. Every pair above is measured in both themes
by PAIRS in tools/tests/test_theme.js.

The tokens' own comment in site.css used to say they "never encode a value".
It no longer says that: these five do, on this page, and the comment records
it, because a token whose meaning changed silently is how a later edit breaks
something nothing tests.

ONE SITE, ONE VOCABULARY
------------------------
The other project keeps its vocabulary in per-edition YAML because it builds a
Cosmos page where a neutrino-proximity scale would be meaningless. This site
has one page and one field, so the lists below ARE the vocabulary, and
`scheme_from(cfg)` still reads an optional `affinity:` block from
tools/news/config.yaml — the hook stays, unused, so the vocabulary can be
tuned without editing code.
"""

from __future__ import annotations

import re
import unicodedata

# Tier ids, strongest first. `unknown` is last and is not a degree of anything
# — it is the refusal to guess, and it is deliberately spelled out rather than
# folded into `adjacent`, so a record the pipeline could not read looks
# different from one it read and placed at the far end.
TIERS: tuple[str, ...] = ("core", "related", "broad", "adjacent", "unknown")

# tier -> the CSS custom property the chip and the timeline bar are painted
# with. Read by BOTH render.py (the listing chips and the legend) and
# figures.py (the timeline bars), so the two can never advertise different
# colours for the same tier. See "THE COLOURS" above for why this assignment
# and why --dec-4 is absent from it.
TIER_COLOUR: dict[str, str] = {
    "core": "var(--dec-2)",
    "related": "var(--dec-5)",
    "broad": "var(--dec-1)",
    "adjacent": "var(--dec-3)",
    "unknown": "var(--text-mute)",
}

# The default labels. An `affinity:` block in config.yaml replaces them
# wholesale (see `scheme_from`).
DEFAULT_LABELS: dict[str, str] = {
    "core": "Neutrino physics",
    "related": "Astroparticle & underground",
    "broad": "Particle physics at large",
    "adjacent": "Adjacent fields",
    "unknown": "Not classified",
}

# --------------------------------------------------------------------------- #
# the vocabulary
# --------------------------------------------------------------------------- #
# SERIES / ACRONYMS. Matched against `extra.acronym` and `extra.series` only,
# never against a title: "NOW", "NBI" and "PIC" are ordinary words or other
# people's initials in prose, and only the organisers' own acronym field makes
# them unambiguous.
DEFAULT_SERIES: dict[str, list[str]] = {
    "core": [
        "Neutrino", "NuFact", "NOW", "Neutel", "NuPhys", "INSS", "NuInt",
        "NNN", "NBI", "ARENA", "CEvNS", "MagCEvNS", "NuMass", "NPML", "NPN",
        "Neutrino Telescopes", "Neutrino Oscillation Workshop",
        "Neutrino Geoscience", "Magellan", "WIN", "NuTel",
    ],
    "related": [
        "TAUP", "ICRC", "IDM", "COSMO", "RICAP", "VLVnT", "UHECR",
        "Identification of Dark Matter", "Multimessenger", "Vulcano",
    ],
    "broad": [
        "ICHEP", "Moriond", "Lepton Photon", "Lepton-Photon", "EPS-HEP",
        "LHCP", "Large Hadron Collider Physics", "SUSY", "Supersymmetry",
        "PANIC", "Pheno", "Phenomenology", "Blois", "Rencontres de Blois",
        "PIC", "Physics in Collision", "Lomonosov", "EPS",
        # DISCRETE (Symmetries in Particle, Nuclear and Astroparticle Physics)
        # is a general symmetries conference with a neutrino session, not a
        # neutrino meeting. Only ever an ACRONYM match: "discrete" is an
        # ordinary English adjective and would fire on half the titles in
        # mathematical physics if it were a subject term.
        "DISCRETE",
    ],
    "adjacent": [
        "Quark Matter", "DIS", "Deep Inelastic Scattering", "QCHS",
        "Confinement", "Strangeness in Quark Matter", "SQM", "Hard Probes",
        # "HH" (Higgs Hunting's own acronym) is deliberately NOT here: two
        # letters are too little to be sure of, and the meeting's title says
        # "Higgs Hunting" in full, which the term list below reads instead —
        # and which makes a far better `why` for the reader.
        "Higgs Hunting", "LCWS", "Linear Collider", "IPAC", "HPTW",
        "Lattice", "Hadron", "ECT",
    ],
}

# SUBJECT TERMS. Matched against the TITLE and the acronym/series text.
# Multi-word terms are matched as written, with punctuation treated as a
# space, so "neutrino-nucleus" matches "neutrino" and "Deep-Inelastic
# Scattering" matches "deep inelastic scattering".
DEFAULT_TERMS: dict[str, list[str]] = {
    "core": [
        "neutrino", "neutrinos", "neutrinoless", "double beta", "0νββ", "νββ",
        "geoneutrino", "geoneutrinos", "leptogenesis", "seesaw",
        "sterile", "cevns", "coherent elastic",
    ],
    "related": [
        "astroparticle", "particle astrophysics", "underground physics",
        "multimessenger", "multi-messenger", "cosmic ray", "cosmic rays",
        "dark matter", "direct detection", "axion", "axions",
        "high energy astrophysics",
        # WIMPs and WISPs are dark matter under other names, and the
        # noble-liquid detection workshops (LIDINE) serve the neutrino and the
        # dark-matter experiments about equally — which is exactly what
        # `related` means. Singular AND plural: the boundary is a letter, so
        # "noble element" does not match "Noble Elements".
        "wimp", "wimps", "wisp", "wisps",
        "noble element", "noble elements", "light detection",
    ],
    "broad": [
        # "high energy physics" first, so it supplies the `why` when both
        # match; the bare "high energy" is what reads "High Energy, Particles
        # and Nuclear Physics in the LHC Era", which the longer phrase misses.
        # Safe below `related`, which is tested first and owns "high energy
        # astrophysics".
        "high energy physics", "high energy", "particle physics",
        "lepton photon", "large hadron collider physics", "supersymmetry",
        "phenomenology", "physics in collision", "rencontres de blois",
        "electroweak", "flavour physics", "flavor physics", "unification",
    ],
    "adjacent": [
        "quark matter", "heavy ion", "heavy-ion", "deep inelastic",
        "quark confinement", "hadron spectrum", "hadron spectroscopy",
        # More specific first: the list is scanned in order inside a tier, and
        # "higgs hunting" makes a `why` a reader can act on where the bare
        # "higgs" does not. Same reason "high power targetry" precedes
        # "targetry" — the phrase names the meeting, the word only a topic.
        "quantum chromodynamics", "qcd", "higgs hunting", "higgs",
        "collider", "colliders", "accelerator", "accelerators",
        "high power targetry", "targetry",
        "target station", "beam dump", "instrumentation",
        "detector", "detectors",
        # Cosmology, gravity and pure astronomy: real subjects, and on a
        # NEUTRINO page they are the far ring. "cosmic" sits here and not in
        # `related` because `related` is tested first and already owns "cosmic
        # ray(s)" — so "Illuminating Cosmic Discord" lands adjacent while the
        # cosmic-ray schools stay related.
        "cosmology", "cosmological", "cosmic", "dark energy",
        "gravity", "gravitational", "gravitational wave",
        "gravitational waves", "general relativity",
        "galactic", "galaxy",
        # Nuclear structure, many-body theory, statistics and computing: the
        # schools and symposia a neutrino physicist's calendar carries but
        # whose subject is not neutrinos. "nuclear symmetry"/"symmetry energy"
        # is what reads NuSym — whose ACRONYM must never be mistaken for a
        # neutrino series, which is why "Nu…" is not and never will be a
        # prefix rule anywhere in this module.
        "nuclear physics", "nuclear symmetry", "symmetry energy",
        "many-body", "many body", "scientific computing", "bayesian",
        "statistics", "lattice",
    ],
}

# INSPIRE CATEGORIES. Corroboration only (signal (c)): consulted when neither
# the series nor the title said anything. The values are INSPIRE's own
# vocabulary, verified live against the conferences API on 2026-09-12 —
# records there carry terms such as Experiment-HEP, Phenomenology-HEP,
# Astrophysics, Instrumentation, Other. Deliberately coarse in the tier it
# assigns: no category means "about neutrinos", so nothing here maps to core.
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "broad": ["Experiment-HEP", "Phenomenology-HEP", "Theory-HEP",
              "Lattice", "General Physics"],
    "adjacent": ["Astrophysics", "Gravitation and Cosmology", "Theory-Nucl",
                 "Experiment-Nucl", "Instrumentation", "Accelerators",
                 "Math and Math Physics", "Computing",
                 "Data Analysis and Statistics", "Other"],
}

# Providers whose mere presence says something about the subject (signal (d)),
# and the tier they lift an `unknown` record TO.
#
# EMPTY, AND IT WAS NOT ALWAYS. The first version of this module lifted every
# unreadable Neutrino Unbound record to `related`, on the reasoning that a
# curated neutrino calendar would not list something irrelevant. Measured on
# the last complete snapshot of that calendar (63 records,
# var/news/cache/2026-09-08/nu-unbound.json — nu.to.infn.it has been answering
# ConnectTimeout since 9 September, so the current day's file is empty and hid
# this entirely): nearly half the listing would have been claiming "neutrinos
# are a major theme here" about gravity, cosmology and statistics meetings,
# which is precisely what the legend promises the colour means.
#
# So the rule is: the colour states what the RECORD says, never what the
# source is. A grey "Not classified" chip on a meeting we could not read is
# worth more than a green one that makes a claim on the reader's behalf — the
# same rule this whole site is built on, where a value that cannot be
# established is left out rather than guessed.
#
# The machinery below stays, unused, for a future calendar that really is
# single-subject — one whose mere presence would be evidence. Neutrino Unbound
# is not that: it also lists ICHEP, Moriond and DIS.
DEFAULT_PROVENANCE: dict[str, str] = {}

# The human phrase that goes with a provenance lift. Keyed by provider so a
# second curated calendar can name itself correctly.
_PROVENANCE_WHY: dict[str, str] = {
    "nu-unbound": "listed on the Neutrino Unbound calendar",
}


# --------------------------------------------------------------------------- #
# matching
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    """Fold to a comparable form: no accents, lower case, punctuation -> space.

    The NBSP is the reason this is not a one-liner: INSPIRE really does store
    "NEUTRINO 2026" with a non-breaking space in the acronym, and a naive
    `.split()` leaves it glued to the year. NFKD turns it into a plain space;
    everything else that is not a letter or a digit becomes one too, so
    "neutrino-nucleus", "EPS-HEP" and "Xe/136" all tokenise the way a reader
    would expect.
    """
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    out = [c.lower() if (c.isalnum()) else " " for c in folded]
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _compile(term: str) -> re.Pattern:
    """A word-bounded matcher for one term, digits allowed on either side.

    The boundary is LETTERS, not \\b: acronyms arrive glued to their year —
    "ARENA2026", "NNN26", "DIS2026", "LHCP2026" — and `\\bARENA\\b` does not
    match "arena2026", because a digit is a word character. A letter-only
    boundary matches all of those and still refuses the false positives that
    matter: "neutron" never matches "neutrino" (different letters), and
    "neutrinoless" does not match the term "neutrino" (a letter follows).
    """
    letter = r"[^\W\d_]"          # a unicode letter, and nothing else
    return re.compile(rf"(?<!{letter}){re.escape(_norm(term))}(?!{letter})")


class Scheme:
    """One vocabulary, compiled once.

    Holds the four ordered tier lists for each signal plus the labels. Built by
    `scheme_from(cfg)`; `DEFAULT_SCHEME` is this site's.
    """

    __slots__ = ("labels", "series", "terms", "categories", "provenance")

    def __init__(self, labels: dict, series: dict, terms: dict,
                 categories: dict, provenance: dict):
        self.labels = labels
        # tier -> [(compiled, term as written)], so the `why` can quote the
        # vocabulary the way a human wrote it rather than the folded form.
        self.series = {t: [(_compile(x), x) for x in series.get(t, [])]
                       for t in TIERS if t != "unknown"}
        self.terms = {t: [(_compile(x), x) for x in terms.get(t, [])]
                      for t in TIERS if t != "unknown"}
        # Categories are compared as whole strings, case-folded: they are a
        # closed vocabulary, not free text, so no word matching is wanted.
        self.categories = {t: {c.strip().lower() for c in categories.get(t, [])}
                           for t in TIERS if t != "unknown"}
        self.provenance = dict(provenance)

    def label(self, tier: str) -> str:
        return self.labels.get(tier, DEFAULT_LABELS.get(tier, tier))


DEFAULT_SCHEME = Scheme(DEFAULT_LABELS, DEFAULT_SERIES, DEFAULT_TERMS,
                        DEFAULT_CATEGORIES, DEFAULT_PROVENANCE)


def scheme_from(cfg: dict | None) -> Scheme:
    """The configured scheme: config.yaml's `affinity:` block, or the default.

    Every sub-block is independent — a config may override only the labels, or
    only the series lists, and inherit the rest. That is not laziness: tuning
    five labels should not mean copying four lists that would then drift.
    """
    block = ((cfg or {}).get("affinity") or {})
    if not block:
        return DEFAULT_SCHEME

    # `in`, not `or`: a config that writes `provenance: {}` MEANS "no curated
    # calendar feeds this page" and must get an empty table, not the default
    # one. `x or default` cannot tell an explicit empty mapping from an absent
    # key.
    def pick(key: str, default: dict) -> dict:
        return block[key] if key in block and block[key] is not None else default

    return Scheme(
        {**DEFAULT_LABELS, **(block.get("labels") or {})},
        pick("series", DEFAULT_SERIES),
        pick("terms", DEFAULT_TERMS),
        pick("categories", DEFAULT_CATEGORIES),
        pick("provenance", DEFAULT_PROVENANCE),
    )


# --------------------------------------------------------------------------- #
# the classifier
# --------------------------------------------------------------------------- #
def _series_text(record: dict) -> str:
    """Acronym plus series names — the organisers' own naming, nothing else.

    INSPIRE's `series` is a list of {"name": …, "number": …}; fetch_inspire
    flattens the names into `extra.series`. A record from another source
    simply has no series, which is a miss, not an error.
    """
    extra = record.get("extra") or {}
    parts = [str(extra.get("acronym") or "")]
    series = extra.get("series")
    if isinstance(series, str):
        parts.append(series)
    elif isinstance(series, (list, tuple)):
        parts.extend(str(s) for s in series)
    return _norm(" ; ".join(p for p in parts if p))


def _subject_text(record: dict) -> str:
    """Everything a subject TERM may be read in: the title and the names.

    Deliberately wider than `_series_text` — see the "(b)" paragraph of the
    module docstring. Neutrino Unbound puts the meeting's real name in the
    acronym and a fragment in the title, so a classifier that reads only the
    title cannot see what half that calendar is about.
    """
    return _norm(record.get("title") or "") + " ; " + _series_text(record)


def _first_hit(haystack: str, table: dict) -> tuple[str, str, re.Pattern] | None:
    """(tier, the term as written, its matcher) for the strongest tier that hits.

    TIER order first, term order second: a `core` term anywhere in the
    haystack beats a `broad` term anywhere in it. That is what lets the
    combined title+acronym text of signal (b) be searched in one pass without
    the field a word happens to sit in deciding the tier.
    """
    if not haystack:
        return None
    for tier in TIERS:
        if tier == "unknown":
            continue
        for rx, written in table.get(tier, []):
            if rx.search(haystack):
                return tier, written, rx
    return None


def classify(record: dict, scheme: Scheme | None = None) -> dict:
    """{"tier", "label", "why"} for one conference record.

    Pure and deterministic: it reads the record and the scheme, touches no
    clock, no network and no global state, and returns the same answer for the
    same input every time. Signals are consulted in the documented order and
    the first hit decides.
    """
    sch = scheme or DEFAULT_SCHEME
    extra = record.get("extra") or {}

    # (a) the series / acronym — the organisers' own statement.
    hit = _first_hit(_series_text(record), sch.series)
    if hit:
        return _out(sch, hit[0], f"series “{hit[1]}”")

    # (b) subject terms, in the title or in the acronym/series name. The `why`
    # names the field the word was actually found in, so a reader hovering a
    # chip whose title says nothing ("5th Workshop") is told the judgement came
    # from the acronym rather than left to wonder.
    hit = _first_hit(_subject_text(record), sch.terms)
    if hit:
        tier, written, rx = hit
        where = "title" if rx.search(_norm(record.get("title") or "")) else "name"
        return _out(sch, tier, f"{where} names “{written}”")

    # (c) INSPIRE's own categories, as corroboration. Only reached when the
    # names said nothing at all.
    cats = extra.get("categories") or []
    if isinstance(cats, str):
        cats = [cats]
    folded = [(str(c).strip(), str(c).strip().lower()) for c in cats]
    for tier in TIERS:
        if tier == "unknown":
            continue
        for written, low in folded:
            if low in sch.categories.get(tier, set()):
                return _out(sch, tier, f"INSPIRE category “{written}”")

    # (d) provenance, last, and only ever as a lift out of `unknown`.
    provider = str(extra.get("provider") or "")
    providers = [provider] + [str(p) for p in (extra.get("providers") or [])]
    for p in providers:
        tier = sch.provenance.get(p)
        if tier:
            return _out(sch, tier,
                        _PROVENANCE_WHY.get(p, f"listed by {p}"))

    return _out(sch, "unknown", "nothing in the record to judge by")


def _out(scheme: Scheme, tier: str, why: str) -> dict:
    return {"tier": tier, "label": scheme.label(tier), "why": why}


def tag(records: list[dict], cfg: dict | None = None) -> list[dict]:
    """Write `classify(...)` into every record's `extra["affinity"]`.

    Mutates in place and returns the same list, so a caller can write either
    `affinity.tag(recs)` or `recs = affinity.tag(recs)`. Idempotent: running it
    twice writes the same dict twice, which is what makes it safe to call late
    in the pipeline without knowing whether an earlier stage already did.
    """
    scheme = scheme_from(cfg)
    for rec in records or []:
        rec.setdefault("extra", {})["affinity"] = classify(rec, scheme)
    return records


def tiers_present(*groups: list[dict]) -> list[str]:
    """The tiers that actually occur in these record lists, strongest first.

    The legend names only what the reader can see: a five-entry key under a
    list with two colours in it is noise, and worse, it invites the reader to
    hunt for a colour that is not there.
    """
    seen = {(r.get("extra") or {}).get("affinity", {}).get("tier")
            for group in groups for r in (group or [])}
    return [t for t in TIERS if t in seen]
