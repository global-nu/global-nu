# Pre-publication audit — factual and numerical content

Auditor pass: prose numbers, derived quantities, conversion arithmetic, experiment
statuses, methodological callouts, bibliographic identities.
Date: 14 August 2026. Scope: `site/` (the about-to-be-public build), with
`site-src/` and `var/history-sources/` as the upstream sources.

Deliberately **not** re-run: the register-value tests (555 values vs cited tables),
the 80 numbers of Table I on `results.html`. Everything below is in territory those
tests do not cover.

**Verdict: NOT publishable as-is.** Three Critical findings, six Important, four
Minor. Details and evidence follow.

---

## CRITICAL

### C1. Wrong journal article number for the 2026 Bari paper

**Location:** `site/history.html:892`, visible text in "The releases" table, row 2026:

> Updated bounds on the (1,2) neutrino oscillation parameters after first JUNO results
> **Phys. Rev. D 114, 013003 (2026)**

Also in the two published machine-readable exports: `site/data/history.csv:141`
and `:142`, and `site/data/history.json` — both carry
`"Phys. Rev. D 114, 013003 (2026)"`. Upstream source: `site-src/data/history.yaml`,
the `bari 2026` release, field `journal`.

**What the source actually says.** INSPIRE record for arXiv:2511.21650, raw API
(`https://inspirehep.net/api/arxiv/2511.21650`):

```json
"publication_info": [{"year": 2026, "artid": "016026", "journal_issue": "1",
                      "journal_title": "Phys.Rev.D", "journal_volume": "114"}]
"dois": ["10.1103/cxqw-1bty"]
"texkeys": ["Capozzi:2025ovi"]
```

The correct citation is **Phys. Rev. D 114, 016026 (2026)**, DOI
`10.1103/cxqw-1bty` (resolves to `https://link.aps.org/doi/10.1103/cxqw-1bty`).

**Why this is Critical, not a typo.** `Phys. Rev. D 114, 013003 (2026)` is a real
article, and it is a different paper entirely. INSPIRE query
`publication_info.journal_title:"Phys.Rev.D" and journal_volume:114 and artid:013003`
returns exactly one hit:

> "Complete two-loop unrenormalized electroweak corrections to e+e- → HZ"
> (arXiv:2209.14953), Phys.Rev.D 114 013003 (2026)

A reader following the group's own citation lands on an unrelated electroweak
two-loop calculation. The wrong string is also in the JSON and CSV that the site
advertises as citable at stable URLs, so anything scripted against them inherits it.

Note the arXiv abstract page for 2511.21650 still shows no journal reference — the
authors have not updated it — so INSPIRE is the authority here, and it is
unambiguous.

### C2. Wrong INSPIRE/BibTeX key in the "How to cite" block

**Location:** `site/about.html:101`, inside the `#cite` callout:

> `@article{Capozzi:2025wgt,`

**What the source actually says.** INSPIRE's texkey for arXiv:2503.07752 is
**`Capozzi:2025wyn`** (raw API, `texkeys` field). A direct INSPIRE query for
`texkeys:Capozzi:2025wgt` returns **0 hits** — the key on the site matches no
record in INSPIRE at all.

**Aggravating context.** The very next sentence in the same callout says:

> "The INSPIRE record carries the authoritative key and an always-current BibTeX
> entry: look it up on INSPIRE."

which invites the reader to assume the block above already matches it. Anyone who
copies this block and later pulls the same paper from INSPIRE gets two entries with
different keys for one paper — a silent duplicate-citation bug in their bibliography.
Everything else in the block is correct: volume 111, number 9, pages 093006, year
2025, DOI `10.1103/PhysRevD.111.093006`, and the six-author list all match INSPIRE.

### C3. T2K published as "taking data" — cited source does not support it, and it is not true today

**Location:** `site/resources.html`, experiments tile list and map marker:
`T2K — Tokai, JP · ... · taking data` (`data-status="taking data"`). Upstream:
`site-src/data/experiments.yaml`, `status: running`, `source: https://t2k-experiment.org/`.

**What the cited source actually says.** The T2K homepage carries no 2026
operational statement. Its most recent status-bearing sentence is a news item from
August 2024: *"The T2K Collaboration has started data taking using the enhanced
neutrino beam and new neutrino near-detectors from December 2023."* The newest item
on the page is dated 23 October 2025. Nothing on the cited page speaks to the
present.

**What is actually the case as of 14 August 2026.** T2K's beam is off:

- J-PARC, 7 April 2026 (`https://j-parc.jp/c/en/information/2026/04/07001779.html`):
  *"At approximately 7:00 a.m. on April 7, a fire broke out from a high-voltage
  switchboard inside the J-PARC 50 GeV substation."*
- J-PARC Director, 17 June 2026 (`https://j-parc.jp/c/en/information/2026/06/17001832.html`):
  *"another failure occurred on Tuesday, June 2 to a piece of equipment unrelated to
  the fire… We have determined that we must abandon MR user operations before
  summer."* The Main Ring is the machine that feeds the neutrino beamline.
- FY2026 accelerator schedule
  (`https://j-parc.jp/c/en/uploads/2026/Op_plan_202604-09e_output_r.jpg`): July,
  August and September 2026 are colour-coded **"Long shutdown/Maintenance"** for MR.

T2K is an active experiment between runs, not a running one. Per the brief's own
rule — a status whose source page no longer supports it is Critical — this qualifies
twice over: the page never supported it, and the substance is now wrong. Suggested
wording: "active, currently in accelerator shutdown", cited to a dated J-PARC source.

---

## IMPORTANT

### I1. The home page presents (1,2)-sector values the site's own register has superseded

**Location:** `site/index.html`, "Best fits" stat cards:

> `δm² / 10⁻⁵ eV²` **7.37** · `sin²θ₁₂` **0.303** — "1σ accuracy 4.5%"

and the prose below: *"All values from Table I of Phys. Rev. D 111, 093006 (2025)."*

**What the site's own data says.** `site-src/data/history.yaml`, `bari 2026`
(arXiv:2511.21650), a partial update flagged in the file itself as *"a (1,2)-sector
update … it adds the latest SNO+ data and the first JUNO results to the 2025
analysis"*: **δm² = 7.48** (1σ 7.39–7.58) and **sin²θ₁₂ = 3.085** (1σ 3.01–3.156).

The values on the cards are correctly attributed to the 2025 paper, so this is not a
misquotation. It is an omission with teeth: the same page's precision figure
**already plots the 2026 points** —
`<title>δm², 2026: 1σ accuracy 1.3%</title>` and
`<title>sin²θ₁₂, 2026: 1σ accuracy 2.4%</title>` — so `index.html` simultaneously
tells a reader that δm² is 7.37 at 2.3% and that the group reached 1.3% on δm² in
2026. `results.html` never mentions the 2026 paper at all (`grep 2026 site/results.html`
matches only the footer). A visitor in August 2026 has no way to learn from the
front page or the results page that the group has a newer number for two of the six
parameters.

Recommend a one-line pointer on both pages. (The 2026 register values are
internally consistent: recomputing the paper's own accuracies from them gives
(7.78−7.21)/6/7.48 = 1.27% → 1.3% and (3.303−2.866)/6/3.085 = 2.36% → 2.4%, matching
the abstract.)

### I2. The conventions callout contradicts itself on the inverted-ordering sign

**Location:** `site/history.html`, "Reading a comparison across conventions":

> "From the identity Δm² = Δm²₃₁ − δm²/2, the correction is −δm²/2 for normal
> ordering in every case, but in inverted ordering it is **+δm²/2 for NuFit** and
> **+δm²/2 applied to the modulus for Valencia** — **the sign of the shift is not
> the same for the two groups**."

**The algebra, worked from the definitions.** With δm² = m₂²−m₁² > 0 and
Δm² = m₃² − (m₁²+m₂²)/2:

- Δm² = Δm²₃₁ − δm²/2 = Δm²₃₂ + δm²/2. (Identity as quoted — correct.)
- **NuFit NO**: publishes Δm²₃ℓ = Δm²₃₁ > 0 → |Δm²| = published − δm²/2. Shift **−δm²/2**.
- **NuFit IO**: publishes Δm²₃ℓ = Δm²₃₂ < 0 → Δm² = published + δm²/2, still negative,
  so **|Δm²| = |published| − δm²/2**. Shift on the modulus **−δm²/2**.
- **Valencia NO**: publishes |Δm²₃₁| → |Δm²| = published − δm²/2. Shift **−δm²/2**.
- **Valencia IO**: publishes |Δm²₃₁| = −Δm²₃₁ → |Δm²| = published + δm²/2. Shift **+δm²/2**.

So the bolded conclusion is right — in IO the signs genuinely differ — but the clause
that is supposed to establish it says "+δm²/2" for *both* groups and then asserts they
are not the same. The "+" for NuFit is true only of the signed quantity Δm²₃₂; every
number the site actually displays for NuFit IO is a magnitude, and on the magnitude
the shift is **−δm²/2**. The sentence changes convention mid-clause without saying so,
in the one callout whose entire job is to state the conversion precisely.

The code gets it right — `tools/make_history.py:157` `to_our_Dm2()` returns
`abs(value + dm2)` for NuFit IO (magnitude shrinks) and `value + dm2` for Valencia IO
(magnitude grows), and its docstring states this correctly. Only the public prose is
muddled. Suggested fix: state both in terms of the modulus, i.e. "−δm²/2 for NuFit,
+δm²/2 for Valencia".

*The rest of the callout is correct*, including "Valencia reports |Δm²₃₁| for both
orderings" — verified verbatim against the source tables (see Clean §3).

### I3. "Status is taken from each collaboration's own pages" is false for 14 of 34

**Location:** `site/resources.html`, note under the experiment tiles:

> "Status is taken from each collaboration's own pages; where it could not be
> established, none is shown."

**What the data says.** 33 rendered statuses (19 completed, 9 taking data, 3 under
construction, 2 proposed) across 44 entries. Of the 34 entries carrying a `status` in
`site-src/data/experiments.yaml`, **14 are sourced to an arXiv abstract or a journal
DOI, not to a collaboration page**: RENO, Double Chooz, MINOS+, K2K, OPERA,
GALLEX/GNO, EXO-200, Majorana Demonstrator, AMoRE, Kamiokande, SBND, ICARUS
(Fermilab), STEREO, BEST.

Sourcing a status to a paper is perfectly respectable — several of those quotes are
the best evidence available. The problem is the sentence claiming otherwise. This is
the same genre as the three false sourcing justifications caught in earlier waves.
Compounding it, two of the statuses that *are* sourced to collaboration pages are not
actually stated there (I4, I5).

### I4. Hyper-Kamiokande status cited to a page that states no status

**Location:** `site/resources.html`, `Hyper-Kamiokande … under construction`.
Source: `https://www-sk.icrr.u-tokyo.ac.jp/hk/`.

**What the cited source actually says.** A Japanese splash page with a tagline and a
news list. It contains no statement of operational status; the closest is a headline,
「ハイパーカミオカンデ　水槽ライニング工事が完了」(4 Aug 2026), from which
construction must be inferred. Separately, `https://www-sk.icrr.u-tokyo.ac.jp/hk/en/`
returns 404 (the English page is at `/en/hk/`).

**The status itself is correct.** The collaboration says so in terms, at
`https://www-sk.icrr.u-tokyo.ac.jp/en/news/detail/1301` (4 Aug 2026):

> "The Hyper-Kamiokande project, currently under construction underground in Kamioka…
> reached a major milestone on 31 July 2026, with the completion of the lining work…
> Detector components, including photosensors, will then be installed beginning in
> early 2027, with scientific operation scheduled to begin in 2028."

Fix is the citation, not the fact.

### I5. KM3NeT: cited page never says "under construction", and the bare label misleads

**Location:** `site/resources.html`, `KM3NeT … under construction`. Source:
`https://www.km3net.org/`.

**What the cited source actually says.** The words "under construction" do not appear
on the page. The only relevant sentence is:

> "KM3NeT is a research infrastructure housing the next generation neutrino
> telescopes. **Once completed**, the telescopes will have detector volumes between
> megaton and several cubic kilometres of clear sea water."

which implies incompleteness without stating it.

**The substantive issue.** Construction is genuinely ongoing — `Welcome, ORCA-42!`
(8 July 2026) puts ORCA at 42 detection units against a 115 target — but KM3NeT has
been taking data and publishing physics from partial detectors for years, including
the KM3-230213A ultra-high-energy event that has its own section and public data
release on the cited homepage. A reader scanning the tiles sees "under construction"
next to Hyper-K (no data until 2028) and concludes KM3NeT has produced nothing. A
compound label ("under construction; partial detectors taking data") would be
accurate.

### I6. The 2001 and 2004 papers are attributed to "Nufit", which did not yet exist

**Location:** `site/history.html`, "Compared with the other groups" reference table,
rows 2001 and 2004, both labelled `Nufit —`. The page frames the comparison as
"three independent global analyses".

**What the records say.** Author lists from INSPIRE:

- `hep-ph/0009350` (2001): Gonzalez-Garcia, Maltoni, **Peña-Garay, Valle**
- `hep-ph/0405172` (2004): Maltoni, Schwetz, **Tórtola, Valle**
- `1209.3023` (2012, the first paper the site's own convention column treats as
  modern NuFit): Gonzalez-Garcia, Maltoni, Salvado, Schwetz
- `1708.01186` (2018, filed by the site under **Valencia**): de Salas, Forero,
  Ternes, **Tórtola, Valle**

Both pre-2012 entries are co-authored by J.W.F. Valle, and the 2004 one by Tórtola as
well — the same two authors whose 2018 paper the site places in the *Valencia* column.
Assigning those papers to the NuFit series while the Valencia series is made to begin
only in 2018 is a lineage judgement, and a contestable one, presented in a citation
table as plain fact with no note. The three columns are not as "independent" before
2012 as the framing implies. Either add a note on the shared ancestry or relabel the
two early rows.

(I could not reach `nu-fit.org` to check how the project itself lists its history —
the site's certificate has expired, which is also worth knowing since
`site/resources.html` links to it.)

---

## MINOR

### M1. "1σ accuracy" on the stat cards drops the paper's own hedging

**Location:** `site/index.html`, stat cards: `1σ accuracy 4.5%` / `2.4%` / `5.1%`.

The numbers are right — they are Table I's last column exactly (4.5, 2.4, 5.1 for
sin²θ₁₂, sin²θ₁₃ NO, sin²θ₂₃ NO). But the paper writes that column as
**"1σ" (%)** and calls it *the formal "1σ parameter accuracy," defined as 1/6 of the
3σ range, divided by the best-fit value*. The cards drop both the quotation marks and
the word "formal", and carry no definition; the definition appears only much further
down the page, in the caption of the precision figure ("a sixth of its 3σ range over
its best fit" — correct there).

A reader who reads "1σ accuracy 4.5%" as the ordinary 1σ fractional uncertainty and
checks it against the 1σ range on `results.html` gets a different number:
(3.17−2.91)/2/3.03 = **4.3%**, not 4.5%. The name is defensible — it is the paper's —
but on the cards it is unqualified where the paper is careful.

### M2. NuFit 2018 title silently truncated

**Location:** `site/history.html`, other-groups table, row 2018 NuFit:
"Global analysis of three-flavour neutrino oscillations: synergies and tensions".
INSPIRE title continues: *"…in the determination of θ23, δCP, and the mass ordering"*.
Truncation without an ellipsis, in a table of citations. All other 18 titles match
their INSPIRE records.

### M3. AMoRE status rests on a 26-month-old paper whose schedule has since slipped

**Location:** `site/resources.html`, `AMoRE … under construction`, sourced to
arXiv:2406.09698 with the stored quote *"AMoRE-II is the main phase of AMoRE and is
currently being installed at the Yemi Underground Laboratory (Yemilab)…"*.

The quote is verbatim and appears in the paper's Introduction (confirmed against the
PDF text; note the abstract carries slightly different wording, so a spot-check
against the abstract alone would wrongly flag it). The status is correct. But a
present-tense claim about August 2026 is being carried by a June 2024 paper, and the
schedule has moved — the AMoRE input to the European Strategy update states *"The
AMoRE-II experiment is under construction and will start data-taking at Yemilab in
2027."* Worth a fresher citation.

### M4. Two presentational blemishes on the auto-generated pages

- `site/conferences.html:96` publishes an empty section: heading "Recent" with
  "0 meetings" and no items beneath it.
- `site/conferences.html:84` lists "invisibles 26", 10–14 August 2026, under
  **Upcoming** on 14 August 2026 — its final day.

Neither is a wrong fact. Both pages are labelled as automatically generated on
`about.html`, which is honest.

---

## CLEAN — what was checked, and how

**1. Prose that states numbers — all verified against the paper's own text.**
Extracted PRD 111, 093006 from the reference PDF with pymupdf and compared
sentence by sentence:

| Claim on the site | Paper |
|---|---|
| `index.html`: "Normal ordering is favoured at 2.2σ" | Abstract: "a relatively weak preference for NO versus IO (at 2.2σ)"; Fig. 3 caption: "NO is favored at 2.2σ" |
| `index.html`, `results.html`: "Δχ²(IO−NO) = +5.0" | Table I last row: `Δχ² IO-NO … +5.0` |
| `results.html`: "0.8% level … first oscillation parameter to enter the subpercent precision era" | Abstract: "the first 3ν parameter to enter the domain of subpercent precision (0.8% at 1σ)" |
| `results.html`: "against 1.1% in the previous update" | §II B: "constrained at the 0.8% level at present (it was 1.1% in [14])" |
| `results.html`: "sin²θ₁₃ falls to 2.4%, from about 3%" | "The uncertainty of sin²θ₁₃ is reduced to 2.4% (from ∼3% in [14])" |
| `results.html`: "two quasi-degenerate minima … roughly 15% against about 25%" | "differing by only ∼15% (∼25% in [14])" |
| `results.html`: "Nσ = √5.0 = 2.2, down from 2.5σ" | √5.0 = 2.236 → 2.2 ✓; 2021 paper (2107.00532) states "an indication for normal ordering at the level of 2.5σ" on pp. 1, 2 and 5 ✓ |
| `results.html` "Not included" callout on SNO+ | §II B: "an error larger than in Table I by a factor of ∼6 and only by assuming a prior on θ12" ✓ |
| Author list, received/accepted/published dates on `results.html` | PDF title page: "(Received 12 March 2025; accepted 21 April 2025; published 19 May 2025)" ✓ |

**2. Derived quantities — recomputed from Table I.** The three stat-card percentages
equal Table I's last column exactly. Recomputing that column's definition
(1/6 of the 3σ range ÷ best fit) reproduces it: sin²θ₁₂ (3.45−2.64)/6/3.03 = 4.46% →
4.5; sin²θ₁₃ NO (2.38−2.06)/6/2.23 = 2.39% → 2.4; sin²θ₂₃ NO (5.81−4.37)/6/4.73 =
5.07% → 5.1. The alternative reading ((hi−lo)/2/best from the 1σ range) does *not*
reproduce them — hence M1, which is about the label, not the arithmetic. Every point
in the precision figure was checked the same way; e.g. |Δm²| 2025 renders 0.84%
((2.558−2.433)/6/2.495 = 0.835%) where the paper rounds to 0.8% — a finer rendering,
not a discrepancy, and |Δm²| 2021 renders 1.1%, matching the paper's statement.

**3. Conversion arithmetic — done by hand, three rows, against the cached PDFs.**

- *NuFit 2020* (`var/history-sources/nufit-2020-2007.14792.pdf`, Table 3 lower block,
  "with SK atmospheric data"): printed Δm²₃ℓ = **+2.517** (NO), **−2.498** (IO),
  Δm²₂₁ = **7.42**; caption confirms *"Δm²₃ℓ ≡ Δm²₃₁ > 0 for NO and Δm²₃ℓ ≡ Δm²₃₂ < 0
  for IO"*. δm²/2 = 0.0371 (in 10⁻³ eV²). NO: 2.517 − 0.0371 = **2.4799** = exported
  value ✓. IO: |−2.498 + 0.0371| = **2.4609** = exported value ✓. 3σ endpoints shift
  by the same constant: 2.435 → 2.3979 and 2.598 → 2.5609, both matching the rendered
  tooltips ✓.
- *Valencia 2020* (`valencia-2020-2006.11237.pdf`, Table III): printed
  |Δm²₃₁| = **2.55** (NO), **2.45** (IO), Δm²₂₁ = **7.50**; the table literally reads
  "|Δm²₃₁|[10⁻³eV²] (NO)" and "(IO)", confirming the stated convention.
  δm²/2 = 0.0375. NO: 2.55 − 0.0375 = **2.5125** ✓. IO: 2.45 + 0.0375 = **2.4875** ✓.
  3σ 2.47–2.63 → 2.4325–2.5925 ✓.
- *Valencia 2018* (`valencia-2018-1708.01186.pdf`, Table I): printed 2.50 (NO),
  2.42 (IO), Δm²₂₁ = 7.55, δm²/2 = 0.03775. NO: **2.46225** ✓. IO: **2.45775** ✓.

The exported numbers are right on their own terms, not merely equal to what the code
emits. The sign handling in IO is opposite between the two groups, exactly as the code
intends — and that is what the prose in I2 fumbles.

**4. Counts in headings and subtitles — all recomputed from the data.**

- "8 releases from NuFit and Valencia" — the reference table has exactly 8 rows
  (NuFit 2001, 2004, 2012, 2018, 2020, 2024; Valencia 2018, 2020) ✓
- "11 releases" and "11 updates" (Bari series) — `history.yaml` holds 11 Bari releases
  (2006, 2008, 2011, 2012, 2013, 2016, 2017, 2018, 2021, 2025, 2026) ✓
- "**393 values**, each verified against its source table" — summing best fits plus
  every s1/s2/s3 endpoint over the Bari releases gives exactly **393** ✓ (all groups
  together: 564; 141 entries, matching the 141 rows of `history.json`/`.csv`)
- `digest.html` "6 preprints" / "10 preprints" — 6 and 10 list items ✓
- `conferences.html` "7 meetings" — 7 items ✓ (the "0 meetings" section is M4)

**5. Bibliographic identities — all 19 releases cross-checked against INSPIRE**
by script (`/api/arxiv/<id>`, comparing journal title/volume/artid/year and paper
title). **18 of 19 match exactly.** The nineteenth is C1. Titles match their INSPIRE
records in all cases but M2. The 2025 paper's identity is correct everywhere it
appears — `index.html` hero, `results.html` (table caption, figure credits, buttons),
`about.html`, `history.html` — as Phys. Rev. D 111, 093006 (2025),
DOI 10.1103/PhysRevD.111.093006, arXiv:2503.07752, issue 9.

**6. Experiment statuses — eight spot-checked by fetching the cited page first,
then corroborating independently.** Clean and supported: **JUNO** (cited page
headlines "JUNO Completed Liquid Filling and Begins Data Taking"; first physics
results published June 2026), **SBND** (cited paper: "began operation in July 2024,
and started collecting stable neutrino beam data in December 2024"; Fermilab, July
2026: "SBND and ICARUS are still active today"), **SNO+** (cited page: "SNO+ takes
data 24/7/365"), **LEGEND** (cited page describes LEGEND-200 continuing data taking;
LBNL, March 2026: "returned to taking production data"), **NEXT** (cited page:
NEXT-100 "now fully operational at the Laboratorio Subterráneo de Canfranc since May
2024"), **RENO** (cited abstract: "As of March 2023, the data acquisition was
completed after a total of 3800 live days"). Problems found: T2K (C3), Hyper-K (I4),
KM3NeT (I5), AMoRE (M3).

**7. The ICARUS double entry is correct, not a contradiction.** `resources.html`
lists ICARUS twice with opposite statuses, which looks like an error and is not: the
two entries are disambiguated by place and run period —
`Assergi, IT · CNGS beam from CERN, at Gran Sasso, 2010-2013 run · completed` and
`Batavia, US · far detector of the Short-Baseline Neutrino programme, at Fermilab ·
taking data`. Both are true, and the cited page supports the first in terms: *"The
ICARUS collaboration studied neutrinos at Gran Sasso National Laboratory in Italy …
from 2010 to 2013"* (past tense, explicit dates). The Fermilab phase is confirmed
running by the ICARUS European Strategy submission (*"ICARUS is currently taking data
in FY25 (RUN4)"*) and Fermilab news of 15 April 2026. Super-Kamiokande also appears
twice, both "running", consistently. Recorded here so a later reviewer does not
re-raise it.

---

## Verdict

**Not publishable as-is.**

Two of the three Critical findings are citation errors in the group's own
bibliography — a wrong article number that points readers at an unrelated
electroweak paper (C1, and it is in the JSON and CSV exports as well as the visible
page), and a BibTeX key that exists nowhere in INSPIRE sitting directly above a
sentence telling readers INSPIRE has the authoritative key (C2). Both are cheap to
fix and exactly the kind of error the audience notices. The third (C3) publishes T2K
as taking data while its beam is in a J-PARC long shutdown.

Beyond those, the Important findings cluster around claims about provenance rather
than the numbers themselves: a sourcing sentence that is wrong for 14 of 34 statuses
(I3), two statuses whose cited pages state nothing (I4, I5), a conventions callout
that contradicts itself in the one place precision matters most (I2), and a front
page that shows 2025 values for two parameters the group has since updated, on a page
whose own figure already plots the update (I1).

The measured numbers themselves are in good shape. Table I is transcribed faithfully,
the derived accuracies are the paper's own column and reproduce from its definition,
the register counts are all exactly right, and the convention conversion — the most
error-prone thing on the site — is correct in all three rows I recomputed by hand from
the source PDFs, including the sign flip between NuFit and Valencia in inverted
ordering. What fails is the connective tissue: citations, sourcing claims, and one
methodological sentence. Fix C1–C3 and I1–I5 and this is publishable.
