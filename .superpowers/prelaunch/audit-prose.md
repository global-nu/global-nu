# Pre-publication prose audit — site/

Auditor: hostile-referee pass over the rendered text of all eleven pages under
`site/` (index, results, history, digest, news, conferences, resources, search,
about, 404 — plus the shared header/footer), and over `README.md` and `LICENSE`
at the repo root. Read-only: nothing was modified.

State audited: build of 14 August 2026, 10:13 (daily pages stamped
"14 August 2026, 07:34").

**Verdict: not publishable as-is.** Two Critical, nineteen Important, sixteen
Minor. See the verdict section at the end.

---

## Critical

### C1 — The group's own 2026 paper carries someone else's article number

**Where:** `site/history.html`, "The releases" table, 2026 row (generated from
`site-src/data/history.yaml` line 269).

> 2026 | Updated bounds on the (1,2) neutrino oscillation parameters after
> first JUNO results | **Phys. Rev. D 114, 013003 (2026)** | arXiv:2511.21650

**What is wrong:** the journal reference is wrong. Verified against
`https://inspirehep.net/api/arxiv/2511.21650`:

- title: "Updated bounds on the (1, 2) neutrino oscillation parameters after first JUNO results"
- authors: Capozzi, Lisi, **Marcone**, Marrone, Palazzo (five, not six)
- publication_info: Phys.Rev.D **114**, artid **016026**, 2026
- DOI: `10.1103/cxqw-1bty`

`Phys. Rev. D 114, 013003 (2026)` is a real but entirely unrelated article
("Complete two-loop unrenormalized electroweak corrections to e⁺e⁻ → HZ", Chen
et al., DOI 10.1103/5ssz-gr6j). The site therefore points a reader who wants
the Bari group's own JUNO update at a Higgs-physics paper — on the one page
whose stated purpose is that every value is traceable to its source.

This is the site's worst failure of its own rule, because the rule is loudest
exactly here: "every value in the register is found in the cited table of the
cited paper". `test_history_numbers.py` reads the *cached PDF* keyed on
`group-year-arxiv`, so it verifies the numbers but never the `journal:` string —
the one field nothing checks is the one that is wrong.

**Suggested wording:** `journal: "Phys. Rev. D 114, 016026 (2026)"`. Also fix
the title to the published form "(1, 2)" (space after the comma) and consider a
`doi:` field, checked by the test suite, so a citation string cannot drift again.

### C2 — README claims the site makes no runtime request; every page loads a third-party script

**Where:** `README.md`, lines 6–8.

> A static site: HTML, CSS and a little JavaScript, built by `build.py` from
> `site-src/`. **No framework, no CDN, no runtime request to anything. Fonts,
> KaTeX and every script are served from the site itself.**

**What is wrong:** false, on all ten pages. Every built page ends with

```html
<script data-goatcounter="https://global-nu.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
```

That is a script fetched at runtime from a third-party CDN (`gc.zgo.at`) and a
beacon sent to a third-party host on every pageview. The site's own
`about.html` discloses it honestly — "Visits are counted with GoatCounter" —
so the README contradicts the site as well as the facts. A reader who checked
the claim (and a referee-minded reader will) finds it wrong in one view of the
network tab.

**Suggested wording:** "No framework, no build-time CDN. Fonts, KaTeX and the
site's own scripts are served from the site itself; the only third-party
request is GoatCounter's counter (`gc.zgo.at`), which records a pageview
without cookies and without tracking individuals."

---

## Important

### I1 — "Ordered by weight in the current global fit" is not true of most of the list

**Where:** `site/resources.html`, note under the experiment tiles.

> Grouped by what each experiment constrains, and **ordered within a group by
> its weight in the current global fit.**

Four of the seven groups — "Short baseline and sterile searches", "Absolute
mass", "Neutrinoless double-beta decay", and the decommissioned entries inside
the others (Kamiokande, ANTARES, K2K, MINOS+) — contribute nothing to the
global oscillation fit, so they cannot be ordered by a weight in it.

**Suggested wording:** "Grouped by what each experiment constrains; inside a
group, the experiments that enter the current global fit come first, in
descending order of their weight in it, followed by the rest."

### I2 — The AI notice on digest and conferences is false; digest.html contradicts itself in its own footnote

**Where:** `site/digest.html` and `site/conferences.html` (`AUTOGEN` banner,
`tools/news/render.py:28`); repeated in `about.html` and in the footer of every
page.

> ⚠ **This page is generated automatically with AI and may contain errors.**

Against, on the same digest page, twelve lines lower:

> Ranking is deterministic: the arXiv API is queried for the configured
> categories, and each record is scored against a stated keyword list.
> **No model is involved in choosing what appears here.**

The second sentence is the true one. `tools/news/pipeline.py` calls
`synthesize.synthesize()` — the only model call in the pipeline — solely to
build the *news* narrative; `render.digest()` and `render.conferences()` are
pure functions of the fetched records, and `tools/news/config.yaml:17` says so
in as many words ("No AI involved in this section"). Conferences likewise has
no model anywhere in its path.

So two of the three pages are labelled with a provenance they do not have, and
`about.html`'s "The arXiv digest, the news and the conference calendar are
**produced daily with AI assistance**" is wrong for two of the three named. A
false disclosure is still a false statement, and a referee will read the
self-contradiction on digest.html as carelessness about provenance generally —
which is the one thing this site cannot afford.

**Suggested wording:** two banners. Digest/conferences: "This page is generated
automatically from the arXiv and Indico APIs and may contain errors. No model
is involved." News: keep the AI wording as it stands. Footer: "Pages marked as
automatically generated may contain errors; the news page is written with AI
assistance." `about.html`: name only the news page as AI-assisted.

### I3 — Downloadable files are promised in four places and exist nowhere

**Where:** `site/index.html` hero; `site/results.html` lede and `#data`;
`README.md`.

- index hero: "best fits, allowed ranges, both mass orderings, and **files you can compute with**."
- index strip card → `results.html#data`: "**Machine-readable data** — Stable URLs and a documented schema, built to be scripted against"
- results lede: "with the paper and **the downloadable files** beside them."
- README: "with the tables, the figures and **the downloadable files**."

And then, at the destination:

> **Nothing is linked from this section yet:** the export runs when the release
> material is prepared, and a link that does not resolve is worse than no link.

The restraint in that last sentence is exactly right; the four promises pointing
at it are not. As built, the home page's "Machine-readable data" card is a link
to an empty section, while the machine-readable data that *does* exist
(`/data/history.json`, `/data/history.csv`) is reachable only from
`history.html#data`.

**Suggested wording:** point the home-page card at `history.html#data` and label
it "The parameter register, as JSON and CSV". Drop "and files you can compute
with" and "the downloadable files" from the hero, the results lede and the
README until the export ships — the `#data` section already announces them
honestly as planned.

### I4 — "One entry per release" — one release out of eleven has an entry

**Where:** `site/results.html`, lede.

> **One entry per release:** best-fit values and allowed ranges for the six
> oscillation parameters, in both mass orderings, with the paper and the
> downloadable files beside them.

The page contains exactly one release section (March 2025). `history.html`
lists eleven Bari releases, the most recent being 2026 — which the results
page does not mention at all, while the history table still tags 2025 as
"current release" and the home page badge still reads "Release March 2025".

A visitor arriving from the 2026 paper finds no trace of it on the page called
Results.

**Suggested wording:** either add the 2026 partial update as a second entry
(clearly marked as a (1,2)-sector update), or change the lede to "The most
recent release in full; earlier ones are traced parameter by parameter on the
parameter history page." Whichever, make one page the authority on "which
release is current" and have the others agree with it.

### I5 — The home page's headline numbers and their sparklines disagree

**Where:** `site/index.html`, the six stat tiles.

> sin²θ₁₂ **0.303** · 1σ accuracy 4.5% · sparkline label "**2011 → 2026**"
> (aria-label "Best fit from 2011 to 2026")
> δm² / 10⁻⁵ eV² **7.37** · sparkline label "**2011 → 2026**"

The printed value, the printed accuracy and the caption ("from Table I of Phys.
Rev. D 111, 093006 (2025)") are all 2025. The sparkline beside them runs one
point further: its final dot is the 2026 value, 3.085 for sin²θ₁₂ (accuracy
2.4%, not 4.5%) and 7.48 for δm². The tile therefore shows a number, an
accuracy and a curve that end in different years, with a label announcing the
later one.

**Suggested wording:** either truncate the sparklines at the release the tile
quotes (label "2011 → 2025"), or quote the 2026 values in the two tiles that
have them and say so in the caption. The current mixture is the one option
that is wrong either way.

### I6 — "BibTeX for this release and the ones before it" — there is one BibTeX entry

**Where:** `site/results.html`, strip card → `about.html#cite`.

> How to cite — **BibTeX for this release and the ones before it**

`about.html#cite` contains a single `@article{Capozzi:2025wgt, …}` and the
sentence "If you use the numbers or the files from the 2025 release, please
cite the paper". No earlier release's BibTeX appears anywhere on the site.

**Suggested wording:** "BibTeX for the current release" — or add the entries and
keep the promise.

### I7 — "A stated keyword score" — the keyword list is stated nowhere on the site

**Where:** `site/digest.html` footnote and `site/index.html` digest card.

> each record is **scored against a stated keyword list**
> ranked by **a stated keyword score** — no model decides what appears there

The list lives in `tools/news/config.yaml`, which is not published on the site.
"Stated" is doing load-bearing work here — it is the reason the reader is
supposed to trust the ranking — and nothing on any page states it.

**Suggested wording:** "scored against a fixed keyword list, published in the
repository (`tools/news/config.yaml`)" — with the link — or publish the list in
a `<details>` on the digest page and keep the word "stated".

### I8 — "Every claim on that page carries the link it came from" — the news summary carries none

**Where:** `site/index.html`, News card.

> Experiments, results and milestones, written from fetched sources: **every
> claim on that page carries the link it came from**, and an item whose citation
> cannot be resolved is dropped before publication.

The first thing on `news.html` is an unsourced 60-word summary paragraph
("This week's neutrino news is dominated by detector engineering and
machine-learning efforts at DUNE…") with no link at all. The claim is true of
the item tiles below it and false of the paragraph above them.

**Suggested wording:** "every item on that page carries the link it came from"
— and either attach sources to the opening summary or mark it plainly as a
summary of the items below.

### I9 — The footer's licence sentence does not match LICENSE

**Where:** footer of all ten pages.

> © 2026 the Bari group · **Content is published under the terms stated on each
> release page.**

`LICENSE` says something quite different and much more specific: data (and
`history.yaml`) CC BY 4.0; code and prose **all rights reserved**; third-party
figures and photographs under their own terms. No "release page" states general
terms — `results.html` states terms only for the two reproduced APS figures.
So the footer both invents a location for the licence and, by implication,
licenses prose that LICENSE explicitly reserves.

**Suggested wording:** "© 2026 the Bari group · The data is CC BY 4.0; the text
and code are all rights reserved; reproduced figures and photographs carry the
terms credited beside them. See the licence." — linking to `LICENSE`.

### I10 — The conversion paragraph states the same sign twice and then says the signs differ

**Where:** `site/history.html`, "Reading a comparison across conventions".

> From the identity Δm² = Δm²₃₁ − δm²/2, the correction is −δm²/2 for normal
> ordering in every case, but in inverted ordering it is **+δm²/2 for NuFit and
> +δm²/2 applied to the modulus for Valencia — the sign of the shift is not the
> same for the two groups.**

As written the sentence gives the same sign for both groups and then asserts
they differ. The arithmetic (correct in `to_our_Dm2`, `tools/make_history.py`
:157–176) is that NuFit's IO value is *negative* — Δm²₃ℓ = Δm²₃₂ < 0 — so
adding δm²/2 makes the modulus *smaller*, whereas Valencia's is a modulus, so
adding δm²/2 makes it *larger*. The reader has to reconstruct that from a
sentence three lines earlier. This is the only piece of physics reasoning the
site spells out in prose, and it is the one a competitor will read hardest.

**Suggested wording:** "…but in inverted ordering the two differ. NuFit's
Δm²₃ℓ is negative there, so Δm² = Δm²₃ℓ + δm²/2 makes the modulus *smaller* by
δm²/2; Valencia publishes a modulus, so |Δm²| = |Δm²₃₁| + δm²/2 makes it
*larger* by the same amount. Same identity, opposite effect on the plotted
number."

### I11 — "Nufit" — another group's name misspelled six times, in the citation table

**Where:** `site/history.html`, "Compared with the other groups" table, all six
NuFit rows.

> **Nufit** — Global three-neutrino oscillation analysis of neutrino data

The rest of the site spells it NuFit (43 occurrences against these 6). Cause:
`tools/make_history.py:432` renders the group key with `.capitalize()`, which
lowercases everything after the first letter. It is a one-line bug, but it
lands in the table whose whole point is that the citation metadata is exact.

**Suggested wording:** a display-name map (`{"bari": "Bari", "nufit": "NuFit",
"valencia": "Valencia"}`) instead of `.capitalize()`.

### I12 — News citation titles are truncated mid-word, with raw LaTeX showing

**Where:** `site/news.html`, "Theory highlights" and the NOvA tile.

> Measurement of the **$\bar ν_μ-$**Hydrogen Charged-Current Quasi-Elastic Cross Section **using t** — arXiv
> Benchmarking state-of-the-art theory and empirical models of pionless neutrino-argon **scatt** — arXiv · INSPIRE · DOI
> Impact of different neutrino decoherence formalisms at the future long-baseline **experiment** — arXiv · INSPIRE · DOI
> Constraining invisible neutrino decay at **NO$\nu $A** and DUNE — INSPIRE · DOI

Two faults, both systematic rather than today's luck. Titles are cut at a fixed
character count with no ellipsis, so they end mid-word ("using t", "scatt") or —
worse — in a word that is still spelled correctly but now says something else
("…long-baseline **experiment**" for "experiments"). And TeX in the source title
is printed verbatim: `$\bar ν_μ-$`, `NO$\nu $A`. On a page that is the group's
public face, four of five citations are visibly broken.

**Suggested wording:** truncate on a word boundary and append "…", or do not
truncate at all (these titles are one line at most); and strip/convert the
common TeX forms (`$…$`, `\bar`, `\nu`) before rendering, since the digest page
already receives the same titles.

### I13 — The digest's "Experimental" stream is mostly theory papers

**Where:** `site/digest.html`, "Experimental — 6 preprints".

Four of today's six "experimental" entries are astrophysics phenomenology:
"Impact of Neutrino Flavour Conversion on the Diffuse Neutrino Background from
Neutrino-dominated Accretion Flows", "Neutrino quantum kinetics for fast flavor
conversion in a time-dependent environment", "An Evolving Leptonic Jet Model for
Delayed Radio Flares in Neutrino Blazars", "The Galactic Neutrino Sky:
Predictions from Gamma-ray Source Populations".

Cause: `EXPERIMENTAL_CATS = ("hep-ex", "nucl-ex", "physics.ins-det",
"astro-ph.HE")` in `tools/news/render.py:26`. Every astro-ph.HE preprint,
theoretical or not, is filed as experimental. This is not a wording nit that
regenerates away — it mislabels the same class of paper every day, and the page
promises "experimental and theoretical work kept apart".

A related visible artefact: two near-identical software papers land in opposite
streams (MANGO → Experimental, Newtrinos.jl → Theory) purely because of primary
category, and the page never tells the reader that the split is by primary arXiv
category.

**Suggested wording:** drop `astro-ph.HE` from `EXPERIMENTAL_CATS` (or add a
third stream, "Astrophysical"), and add one line to the footnote: "The split is
by the preprint's primary arXiv category."

### I14 — The conferences page states a rule it does not follow

**Where:** `site/conferences.html`, closing note and "Upcoming" list.

> **Where a date or a venue cannot be confirmed from the source, the entry is
> dropped rather than guessed.**

Two of seven upcoming entries display no venue at all:

> invisibles 26 — 10–14 August 2026 — Details
> Probing new physics beyond the standard model at the HL-LHC and future lepton colliders — 21–24 September 2026 — Details

The venue *is* confirmable for at least the first: the linked Indico page
(`indico.cern.ch/event/1561367/`) gives "Sede Afundación, Cantón Grande 8, A
Coruña, 15003, Spain". So the entry was neither dropped nor given its venue —
the third outcome the sentence rules out. The hero and the `<meta
name="description">` both promise "dates, venues and links".

**Suggested wording:** either read the venue from the Indico location field
before falling back, or soften to "Where a date cannot be confirmed from the
source, the entry is dropped rather than guessed; a venue is shown when the
source publishes one."

### I15 — "Twenty years" and "a quarter century" describe the same page

**Where:** four places, two answers.

- `README.md`: "across **twenty years** of published global fits"
- `site/404.html`: "across **twenty years** of published global fits"
- `site/index.html` strip: "**A quarter century** of global fits — Bari, Valencia, NuFit"
- `site/results.html` strip: "over **a quarter century**"

The register runs 2001 (NuFit) to 2026, so a quarter century is the defensible
figure and "twenty years" understates the site's own reach. Separately,
`index.html`'s chart heading

> **A quarter century of sharpening** — formal 1σ accuracy · logarithmic scale

sits over a chart whose points run 2011–2026 (θ₁₃ from 2008): fifteen years of
data under a twenty-five-year headline. That one is an overclaim, not just an
inconsistency.

**Suggested wording:** standardise on "a quarter century" for the parameter
history everywhere, and retitle the home-page chart to what it shows — e.g.
"Fifteen years of sharpening", or "How the precision improved" with no span at
all.

### I16 — "Every value … verified against its source table" — twelve are not, and one release has no table

**Where:** `site/history.html`, "The releases".

> 11 updates · **393 values, each verified against its source table**
> **Every value on this page is transcribed from the table named here** and
> checked against the paper by `tools/tests/test_history_numbers.py`, which
> re-reads each source on every run.

`test_history_numbers.py:210–213` skips any non-`best` value on a release
flagged `derived: true` ("A value the paper states as central ± error is
computed, not printed: the entry declares it and it is not searched"). Two
releases carry that flag — 2006 (ten range endpoints) and 2008 (two) — so
twelve of the 393 values are computed and never looked for in the source. The
test itself prints "(N declared as derived, not searched)".

The 2006 entry also has no table: its own note says "No numbered table: the
paper gives all five parameters only as text equations (Eqs. 53-57)", and the
`table` field reads "Eq. (53)-(57)".

The register handles both cases honestly in the data; only the sentence on the
page overstates. Given the project's rule that prose answers to the same
standard as numbers, this one should be exact.

**Suggested wording:** "393 values. Every best fit, and every range endpoint the
paper prints, is checked against the source it names; twelve range endpoints
that the paper states only as a central value ± error are computed from it, and
the register marks them as derived." And "from the table or equations named
here" in the paragraph below.

### I17 — The search page says ADS has no public API, then explains ADS's public API

**Where:** `site/search.html`, two paragraphs apart.

> **Google Scholar and NASA ADS have no public search API** — use the buttons
> below to open the same query there.

> **Why not NASA ADS.** It requires a personal token, which would have to be
> published in the page source to work — so for ADS the parsed query is turned
> into a correct search URL and offered as a button instead.

ADS does have a public, documented search API; it is token-gated, which is the
real (and good) reason it cannot be called from a static page. The first
sentence is wrong and the second corrects it, on the same page.

**Suggested wording:** "Google Scholar has no public search API, and NASA ADS's
requires a personal token — use the buttons below to open the same query
there."

### I18 — Two IFIC-Valencia papers are attributed to NuFit

**Where:** `site/history.html`, "Compared with the other groups" table.

> **Nufit** — Global three-neutrino oscillation analysis of neutrino data · Phys. Rev. D 63, 033005 (2001)
> **Nufit** — Status of global fits to neutrino oscillations · New J. Phys. 6, 122 (2004)

Both are IFIC-Valencia global fits (Gonzalez-Garcia, Maltoni, Peña-Garay,
Valle); "NuFit" as a name and a collaboration dates from ~2012. The register
knows this — `history.yaml` comments "The two predecessor entries below (2001,
2004) are earlier IFIC-Valencia global fits by the same lineage of authors,
recorded as 'nufit' per this file's existing convention for predecessors" — but
nothing of that reaches the page. Worse, the same table carries a separate
"Valencia" group for a *different* lineage (de Salas, Forero, Tórtola, Valle),
so a reader is invited to conclude the 2001 paper is not a Valencia paper. Both
groups' authors will notice.

**Suggested wording:** label them "NuFit (predecessor)" with a footnote, or
introduce a third series label; and add one sentence above the table: "The 2001
and 2004 entries predate the NuFit name; they are earlier fits by the same
lineage of authors, grouped here for continuity."

### I19 — The contact postcode is not the one the institutions publish

**Where:** `site/about.html` Contact, and the footer of all ten pages.

> Dipartimento Interateneo di Fisica "Michelangelo Merlin", Via Amendola 173,
> **70126** Bari, Italy

UniBa's own page publishes "via Amendola 173 - **70125** Bari"
(`uniba.it/it/ricerca/dipartimenti/fisica/dipartimento/dove-siamo`); INFN Bari
publishes 70125 as well. 70126 is what the group's papers print, so it is
faithful *as an affiliation line* — but the site presents it as a contact
address, next to a "Write to" line, where the institution's own postcode is
what a reader needs.

**Suggested wording:** 70125 in the footer and the Contact block. (Street
number 173 is confirmed correct.) Note also that UniBa now names the department
"Dipartimento Interuniversitario di Fisica (DIF)"; "Interateneo … Michelangelo
Merlin" is still used on the department's own location page and in the papers,
so it is defensible, but it is no longer the primary official form.

---

## Minor

| # | Where | What |
|---|---|---|
| M1 | `about.html` | `<h1>About this site</h1>` and, further down, `<h2>About this site</h2>` — the same heading twice on one page. Rename the h2 to "How this site is built" or "Privacy and technology". |
| M2 | `history.html` | "The Bari series — **11 releases**", then the table below is headed "The releases" with the subtitle "**11 updates**". Pick one word. |
| M3 | `results.html` | "SNO+ **expectations** on (δm², θ₁₂) are nevertheless very promising and **are expected to** surpass the current δm² accuracy within a few years." Repetition, and an expectation cannot surpass an accuracy. Suggest: "SNO+ is nevertheless expected to surpass the present δm² accuracy within a few years." |
| M4 | `results.html`, "What changed" | Repeats the paper's headline ("the first oscillation parameter to enter the subpercent precision era") without the authors' own caveat — the abstract reads "We underline some issues about systematics, that might affect this error estimate." Add half a sentence. |
| M5 | `news.html` | The AI-generated summary paragraph is printed *above* the "generated automatically with AI" banner. Move the banner up so the warning precedes the generated prose. |
| M6 | `news.html` | "Theory highlights — recently published, **with preprint, record and journal**", but two of the five items have no preprint link (TAMBO; invisible decay). Suggest "with the links the record carries". |
| M7 | `news.html` | The decoherence summary states flatly that the two formalisms "give different oscillation probabilities and sensitivities"; the abstract (arXiv:2604.20977) says they agree for small Γ and in vacuum, and differ only when Γ is large or matter effects are strong. Not a contradiction, but a dropped condition. |
| M8 | `conferences.html` | "…in Xe - next-generation experiment · **Old Trafford**" — the source gives "Old Trafford, Manchester, United Kingdom". A district name alone reads as a joke. Show city and country. Also "invisibles 26" is carried in the source's lowercase form; consider title-casing known series names. |
| M9 | `resources.html` | Two `http://` links (`dayabay.ihep.ac.cn`, `www.nu-fit.org`) on an otherwise all-https page. Both answer on http only, so a note or an https attempt first. |
| M10 | `resources.html` | "Status is taken from each collaboration's own pages; where it could not be established, none is shown" — yet KamLAND and KamLAND-Zen are marked "completed" (both are in operation/upgrade), and Homestake, NOvA, MicroBooNE, PROSPECT, CUORE, DUNE and Project 8 carry no status at all although each publishes one. |
| M11 | `results.html` | `<h2>March 2025 — entering the era of subpercent precision</h2>` lowercases the paper's own "Entering". |
| M12 | `history.html` | Title rendered "(1,2)"; the published title is "(1, 2)". |
| M13 | digest / news / conferences | "Last successful update: 14 August 2026, 07:34" gives no time zone. Add "CEST" or use ISO with an offset. |
| M14 | `about.html` | Melchiorri's affiliations are listed "Roma 'La Sapienza' and INFN Roma I"; the paper prints INFN Roma I first. Cosmetic — the affiliations themselves are correct, including "Roma I". |
| M15 | `conferences.html` | "Recent — 0 meetings — **Nothing announced in this window.**" Wrong verb for past meetings; suggest "No meetings ended in this window." |
| M16 | build | `site/assets/js/chi2.js` ships but no published page references it. Not prose, noted so it is not forgotten. |

---

## What was checked and found clean

**People, names, affiliations (the category with the highest stakes) — clean.**
All six names on `about.html` were verified against `inspirehep.net/api/arxiv/
2503.07752` (raw affiliation strings as printed in the paper) and cross-checked
against Crossref for DOI 10.1103/PhysRevD.111.093006. Spelling, accents
(Giarè), author order and every affiliation match the paper: Capozzi (L'Aquila
+ INFN LNGS), Giarè (Sheffield, his only affiliation on this paper), Lisi (INFN
Bari), Marrone (Bari + INFN Bari), Melchiorri (La Sapienza + INFN **Roma I** —
"Roma I" is the correct form, not "Sezione di Roma"), Palazzo (Bari + INFN
Bari). The same six surnames in `README.md` and the LICENSE citation are
correct and correctly ordered. Only the postcode (I19) and the ordering nit
(M14) attach here.

**Publication metadata of the 2025 release — clean.** "Received 12 March 2025;
accepted 21 April 2025; published 19 May 2025" matches APS and Crossref
exactly. Journal reference, volume, article number, DOI and eprint number in
the BibTeX all check out.

**The numbers on `results.html` — clean.** All ten "1σ (%)" entries recomputed
from the printed 3σ ranges and best fits under the page's own stated definition
(3σ range / 6 / best fit): 2.3, 4.5, 0.8, 0.8, 2.4, 2.4, 5.1, 4.3, 18, 8 — every
one reproduces. "Nσ = √5.0 = 2.2" is right. The headline claims match the
abstract verbatim: "|Δm²| is the first 3ν parameter to enter the domain of
subpercent precision (0.8% at 1σ)" and "a relatively weak preference for NO
versus IO (at 2.2σ)".

**Figure licensing — clean.** Crossref confirms PRD 111, 093006 carries
`https://creativecommons.org/licenses/by/4.0/` for the version of record, so
`results.html`'s "Published by the American Physical Society under the terms of
the Creative Commons Attribution 4.0 International license" and the
corresponding paragraph in `LICENSE` are both accurate. LICENSE's three-way
split (data CC BY 4.0 / code and prose reserved / third-party as credited) is
internally consistent and consistent with README; the only page that departs
from it is the footer (I9).

**AI-generated page marking — structurally correct.** The notice with a
timestamp appears on exactly `digest.html`, `conferences.html` and `news.html`,
and on no other page (checked by grep across all ten). Its *wording* is the
problem, not its placement — see I2 and M5.

**Links on `resources.html` — clean.** All 53 distinct external links were
requested with a browser user-agent: 52 return 200. The single non-200 is
`doi.org/10.1103/PhysRevLett.77.1683` returning 403 from APS to a robot, which
resolves normally in a browser — exactly the case `tools/news/linkcheck.py`
documents. So the link *targets* are sound; the claim "Every link here was
checked before publication" (resources hero) is true today, though nothing in
the test suite re-checks it, so it will decay silently.

**Search page privacy claims — clean.** "Everything happens in your browser…
nothing you type is sent to, logged by, or stored on global-nu.org" holds:
`site/assets/js/search.js` reads `?q=` if present (line 1033) and never writes
the query to the URL, and posts nothing to the site's own origin. "No cookies"
on `about.html` holds too — the theme uses `localStorage`, and GoatCounter is
cookieless. (The GoatCounter script is a third-party *request*, which is why
C2 is a README problem and not an about.html one.)

**Data files — clean.** `site/data/history.json` is an object with `note` and
`rows` (141 rows), and `history.csv` has the same 141 rows and a 13-field
header, exactly as `history.html#data` documents field by field. The two files
agree with each other and with the page's description.

**English mechanics — clean.** No doubled words, no stray double spaces, no
unconverted Markdown, no broken entity in the rendered text of any page.
Headings are consistently sentence case throughout. Terminology is consistent
apart from M2 and I15. The register's number formatting, en dashes and Greek
glyphs are uniform.

**Spot-checked AI content against its own sources — accurate.** Three of the
linked sources were fetched and compared with the summary that cites them:
NOvA (arXiv:2608.12293 — 1.2×10²¹ POT, 35,509 signal events, "highest
statistics of (anti)neutrino–hydrogen interactions measured to date",
backgrounds constrained with data control samples: all four match); the
decoherence paper (arXiv:2604.20977 — formalisms, experiments and conclusion
match, with the caveat at M7); TAMBO (INSPIRE 3185371 — Nature Astronomy 10,
2026, DOI 10.1038/s41550-026-02916-4: the "Nature Astronomy article"
attribution is correct). No result is attributed to the wrong paper. The
failures on these pages are in presentation (I12, I13) and provenance labelling
(I2), not in the summaries themselves.

---

## Verdict

**Not publishable as-is.**

Two findings must be fixed before the site goes public, and both are cheap:

1. **C1** — the group's own 2026 paper is cited with another group's article
   number. This is a wrong citation, on the page whose entire argument is that
   every number is traceable, pointing at a Higgs paper. Nothing else on the
   site would embarrass the group as directly, and a colleague looking up the
   JUNO update is exactly the reader who will hit it first. One line in
   `history.yaml`, plus a test that checks `journal:` and a `doi:` field the way
   the numbers are already checked.
2. **C2** — the README's "no runtime request to anything" is refuted by a
   `<script src="https://gc.zgo.at/count.js">` on every page. One sentence.

Beyond those, the pattern in the Important list is worth naming, because it is
one pattern and not nineteen: **the prose promises more than the build
delivers.** Downloadable files that do not exist (I3), a release list with one
release (I4), BibTeX "and the ones before it" (I6), a "stated" keyword list that
is stated nowhere (I7), "every claim carries its link" beside an unsourced
paragraph (I8), a drop-rather-than-guess rule that neither drops nor fills
(I14), "every value verified" with twelve exceptions (I16), "ordered by weight
in the global fit" for experiments that are not in it (I1). Each is small. Their
sum is the one impression this site cannot afford to give — that its claims are
aspirational rather than checked — and it undercuts the genuinely excellent
restraint shown elsewhere on the same pages ("a link that does not resolve is
worse than no link", "a page that prints nothing where a number is unknown is
doing the right thing").

The remedy for almost all of them is to weaken the sentence rather than
strengthen the build: the site is already better than its prose admits in the
places that matter (the numbers are right, the conversions are right, the
citations are right apart from C1, the names and affiliations are right). Fix
the two Criticals, sweep the Importants for overclaim — most are a word or two
— and this is a site a referee would respect.

The Minors are polish and can follow publication, with the exception of M5
(warning placement on a page of AI-written prose), which is cheap enough to do
in the same pass.
