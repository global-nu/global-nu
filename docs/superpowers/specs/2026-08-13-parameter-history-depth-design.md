# Parameter history: the record the field does not keep

Date: 2026-08-13 · Status: awaiting review

## Why this page, and not another

NuFit publishes its current numbers. So does Valencia. So do we. Nobody publishes
**how those numbers moved** — and nobody puts the three groups on the same axes,
because doing so honestly requires converting between three different definitions
of the larger mass splitting and saying so out loud.

This site already does that, in a section at the bottom of the Parameter history
page, with a methodological note that gets the hard part right: it states that
the correction to Δm² is −δm²/2 for normal ordering in every case, but that in
inverted ordering **the sign of the shift is not the same** for NuFit and for
Valencia. Twelve conversions are checked by `tools/tests/test_history_conversion.py`.

The section is good and almost nobody will find it. It sits below ten panels of
our own history, and it is fed by four NuFit points and two Valencia points
against our ten. This design makes that comparison the reason the page exists,
and gives it enough data to carry the weight.

## Decisions taken

Antonio decided, on 2026-08-13:

1. **Upper limits are shown**, drawn distinctly from measurements. A parameter
   that a paper only bounded is part of the record, because θ₁₃ going from
   "consistent with zero" to 2.4% precision is the field's best story and the
   page currently cannot tell it.
2. **Only published papers count as a release.** Not the numbered tables on
   nu-fit.org: a web table changes without a version, so a citation to one stops
   being checkable. Fewer points, every one of them permanent.
3. **Only complete global analyses count.** Sector papers — solar-only,
   atmospheric-only — are out, which keeps the three groups comparable, since
   NuFit and Valencia publish only global analyses.
4. **The register becomes citable data**, exported at stable URLs with a
   documented schema. Per-point permalinks were considered and rejected as more
   discipline than they are worth today.
5. **The three-group comparison becomes the page's spine**, with the Bari series
   kept as a secondary view rather than removed.
6. Two specific papers were adjudicated: `hep-ph/0206162` is excluded as
   methodological, and `hep-ph/0208026` is excluded on inspection — its abstract
   describes "an updated analysis of the current solar neutrino data" with
   terrestrial searches entering as constraints, and its only table is a 2ν solar
   fit without CHOOZ. There is no global three-flavour table in it to extract.

## What this costs the page's own headline

The Bari series has no complete published global analysis before
`hep-ph/0506083`, posted in 2005 and published as Prog. Part. Nucl. Phys. 57 742
(2006). The genuinely global analyses of 2001–2004 exist, but as conference
proceedings, which decision 2 excludes for want of a citable table.

**Which year a record carries**: `history.yaml` keys a release by its *journal*
year, not the year the preprint appeared — the existing 2026 Bari entry cites
arXiv:2511.21650, posted in 2025 and published in 2026, and is filed under 2026.
So `hep-ph/0506083` is a 2006 record, and the register spans 2006–2026 for Bari
and 2000–2024 across all three groups.

So the register starts in 2006, and the page's title — *"A quarter century of
global fits"* — is an unsupported claim. It becomes twenty years, or a phrase
carrying no number. On this site prose is held to the rule that binds the
numbers: no assertion without something behind it.

## The work

### 1. A value is a measurement or a limit, never both

Today every value in `site-src/data/history.yaml` is a measurement: `best`, with
`s1` and `s3` ranges. It gains a second shape:

```yaml
sin2_th13:
  "no": {best: 2.23, s1: [2.17, 2.29], s3: [2.05, 2.41]}   # a measurement
  "io": {upper: 5.0, level: s3}                             # an upper limit at 3σ
```

A limit carries the confidence level it was quoted at, because a bound without
one is not a datum. `tools/experiments.py`'s validation is the model: the loader
raises rather than letting a malformed record reach a page, naming what is wrong
with which entry.

**Levels are heterogeneous and the schema must not pretend otherwise.** Older
papers quote bounds at whatever level suited them — 90% CL, 95% CL, 2σ, 3σ. How
mixed that landscape actually is will only be known once the five papers are
read, so `level` is a string drawn from a documented set (`3sigma`, `2sigma`,
`90%CL`, `95%CL`), extended when a paper demands it rather than decided in
advance, and validated against that set. **The page prints the level beside every
limit**, so two arrows at different levels are never silently compared. A limit
whose level cannot be established from the paper is omitted, like any other
value that cannot be sourced.

### 2. The exclusions are recorded, not remembered

A new `excluded:` section in `history.yaml` lists every paper considered and
rejected, with its reason: `hep-ph/0206162` methodological; `hep-ph/0208026`
solar with terrestrial constraints, no global table; the 2001–2004 conference
proceedings for want of a citable table.

A physicist reading this page will ask why a paper they know is missing. Today
that answer exists only in one conversation. This puts it in the file, next to
the data it explains.

### 3. Five extractions, all from PDFs already cached

| group | arXiv | year | why it belongs |
|---|---|---|---|
| Bari | hep-ph/0506083 | 2006 | the first complete global analysis published as an article |
| NuFit | hep-ph/0009350 | 2000 | predecessor; a global analysis, and it bounds θ₁₃ |
| NuFit | hep-ph/0405172 | 2004 | as above |
| NuFit | 1001.4524 | 2010 | as above |
| Valencia | 1806.11051 | 2018 | a global analysis, downloaded and never extracted |

Sixteen points become twenty-one, and the comparison goes from ten of ours
against six of theirs to eleven against ten. The three NuFit predecessors are
what let the page show a limit on θ₁₃ becoming a measurement — a story our own
papers cannot tell alone, which is the argument for the comparison being the
spine rather than an appendix.

Every value is verified by `tools/tests/test_history_numbers.py`, which
re-extracts the cited table from the cached PDF and checks each number against
it. That test is why this compilation is safe in a way the experiment roster was
not: a mistranscribed value fails the build.

**What the test cannot check is the choice of table.** It verifies that a value
appears in the table named, not that the right table was named. Each extraction
records the table it came from, and a limit records the sentence or table entry
stating the confidence level — the `source_quote` discipline adopted for the
experiment roster, applied here from the start rather than retrofitted.

### 4. The page, reorganised

The comparison moves to the top: one panel per parameter, all three groups on the
same axes, 2000 to today, with limits drawn as arrows distinct from the markers
used for measurements. The methodological note on conventions rises with it,
because it stops being a caveat and becomes the page's key.

The Bari series survives below as a secondary view. The point of this page is not
to be modest about our own record; it is that our record is more interesting
inside the field's than beside it.

### 5. The register as data

`data/history.json` and `data/history.csv` at stable URLs, with a page
documenting every field. Each row carries group, year, arXiv identifier, source
table, parameter, and the original convention.

**Every row carries the value twice, under names that cannot be confused:**
`value_as_published` — exactly what the paper printed, in the paper's own
convention and normalisation — and `value_our_convention`, the same quantity
converted by the rule in `tools/make_history.py`. Publishing only the first
serves fidelity and fails anyone who downloads the file to compare groups;
publishing only the second passes our arithmetic off as the paper's number.
Publishing both, named for what they are, does neither. The conversion rule is
documented in the schema page and the original convention is named in every row,
so a reader can redo the arithmetic or reject it.

Only Δm² is ever converted — the groups agree on δm², on the three mixing angles
and on δ/π. For every other parameter the two columns hold the same number, and
that is the correct output, not a redundancy to optimise away: a consumer reading
`value_our_convention` gets a comparable column for all six parameters without
having to know which one needed work.

## Verification

- `tools/tests/test_history_numbers.py` covers the new values automatically.
- A new check: every value is a measurement or a limit, never both and never
  neither.
- A new check: every limit declares its confidence level, and that level is one
  of the documented set.
- A new check: **the table each record cites actually exists in the PDF it cites
  it from.** This does not prove the right table was chosen — nothing mechanical
  can — but it catches a record pointing at Table III of a paper with two tables,
  which is the cheapest way to aim at the wrong target.
- A new check: `value_our_convention` equals what the conversion rule produces
  from `value_as_published`, so the two exported columns cannot drift apart.
- A new check: the exported JSON and CSV contain exactly the points in the YAML,
  compared in both directions — one direction catches a point that failed to
  export, the other catches a row with no counterpart in the source.
- `tools/tests/test_history_conversion.py` must keep passing; any new group entry
  with its own convention gets a conversion case there.
- The page is looked at in a browser, both themes, at full width and at 700px:
  limit arrows must be distinguishable from measurement markers at a glance, and
  the panels must stay legible with three groups and twenty-one points on them.

## Not in this spec

The other two sub-projects identified with Antonio: the daily pipeline behind the
arXiv digest, News and Conferences; and a Methodology page. Each gets its own
design.
