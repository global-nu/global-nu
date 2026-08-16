# Pre-publication fixes — what was changed, and on what evidence

Worked from `main` at 484f51b. Every Critical and Important finding of
`audit-numbers.md` and `audit-prose.md` is addressed below, plus the Minors
whose fix was cheap and unambiguous. Findings deliberately left alone are
listed at the end with the reason.

Nothing under `site/`, `data-exports/`, `site-src/content/history.md` or the
three daily pages was hand-edited: the sources were changed and the generators
re-run. All tests pass (see the end).

---

## Critical

### numbers C1 / prose C1 — wrong article number for the 2026 paper

`site-src/data/history.yaml`, release `bari 2026`:

- `journal:` `Phys. Rev. D 114, 013003 (2026)` → **`Phys. Rev. D 114, 016026 (2026)`**
- `title:` `…the (1,2) neutrino…` → **`…the (1, 2) neutrino…`** (published form)

**Evidence.** `https://inspirehep.net/api/arxiv/2511.21650` —
`publication_info`: `[{"year": 2026, "artid": "016026", "material":
"publication", "journal_issue": "1", "journal_title": "Phys.Rev.D",
"journal_volume": "114"}]`; `dois`: `[{"value": "10.1103/cxqw-1bty", "source":
"APS"}]`. INSPIRE's own BibTeX for the same record:

```bibtex
@article{Capozzi:2025ovi,
    title = "{Updated bounds on the (1, 2) neutrino oscillation parameters after first JUNO results}",
    doi = "10.1103/cxqw-1bty", journal = "Phys. Rev. D",
    volume = "114", number = "1", pages = "016026", year = "2026"
}
```

Note the DOI is APS's new opaque form, `10.1103/cxqw-1bty`, not a
`PhysRevD.114.016026` string — verified twice, in the JSON and in the BibTeX.
Regenerated: `site/history.html`, `site/data/history.{json,csv}`,
`data-exports/history.{json,csv}`. `grep -r 013003 site/ data-exports/` now
returns nothing; `016026` appears in all five places.

### numbers C2 — wrong BibTeX key

`site-src/content/about.md`: `@article{Capozzi:2025wgt` → **`@article{Capozzi:2025wyn`**.

**Evidence.** `https://inspirehep.net/api/arxiv/2503.07752`, `texkeys`:
`['Capozzi:2025wyn']`.

**Every other field of that block was checked against the same record and
INSPIRE's generated BibTeX, and every one is correct**: the six authors in
order (Capozzi, Francesco / Giarè, William / Lisi, Eligio / Marrone, Antonio /
Melchiorri, Alessandro / Palazzo, Antonio), the title
`Neutrino masses and mixing: Entering the era of subpercent precision`,
`journal = {Phys. Rev. D}`, `volume = {111}`, `number = {9}`,
`pages = {093006}`, `year = {2025}`, `doi = {10.1103/PhysRevD.111.093006}`,
`eprint = {2503.07752}`, `primaryClass = {hep-ph}`. The only difference from
INSPIRE's output is that the site escapes the accent as `Giar\`e` where INSPIRE
emits raw UTF-8 `Giarè`; both are correct BibTeX and the escaped form is safer
in a legacy toolchain, so it was left as it was.

### prose C2 — the "no CDN" claim and GoatCounter

`count.js` is now **self-hosted**: fetched from `https://gc.zgo.at/count.js`
(HTTP 200, `content-length: 9213`, ISC licence header) into
`site-src/assets/vendor/goatcounter/count.js`, sha256
`792b7abd26c1fb6ae62906833e09a301251e2641816e69e4f95aba518f3fe3f0`. `build.py`
now emits
`src="{base}assets/vendor/goatcounter/count.js"` (cache-busted like every other
asset). Verified: the script reads its endpoint from the `data-goatcounter`
attribute and from nothing else (`get_endpoint()`, line 84 of the vendored
file), so self-hosting cannot break counting. `grep -r gc.zgo.at site/` is
empty.

Claims made precise rather than dropped:

- `README.md`: "No framework, no CDN, no third-party script … One request does
  leave it: GoatCounter's counter sends a single cookieless pageview to
  `global-nu.goatcounter.com`. That is the analytics, and it is the only
  outbound request a page makes."
- `about.html`: "Every font, stylesheet and script — including the counter's —
  is served from this domain … That is the one request a page makes off this
  domain: one counting request per pageview."

### numbers C3 — T2K published as "taking data"

`status: running`, sourced to `t2k-experiment.org`, was not supported by that
page and is not true today. Now `status: paused`, label
**"between runs, accelerator in shutdown"**, sourced to J-PARC with the
sentence quoted in the data file.

**Evidence** (fetched directly, not summarised):
`https://j-parc.jp/c/en/information/2026/06/17001832.html`, dated 2026.06.17,
signed by the Director of J-PARC Center: *"Operation of J-PARC accelerators had
been suspended following the fire on Tuesday, April 7; after safety checks, MLF
user beam resumed on Monday, June 1. Regarding the MR accelerator, another
failure occurred on Tuesday, June 2 to a piece of equipment unrelated to the
fire. We have been working to the repairs, but they are found to take time. We
have determined that we must abandon MR user operations before summer."* The
Main Ring is the machine that feeds the neutrino beamline. The FY2026 schedule
(`https://j-parc.jp/en/Operation/Operation-26_0409F.html`) shows MR in "Long
shutdown/Maintenance" through September 2026, and no later J-PARC notice
announces a restart. T2K's own newest status sentence is the December 2023 news
item, which says nothing about 2026.

**Vocabulary note, for your veto.** `tools/experiments.py` had four statuses
and none of them was true here: `running` is false, `completed` is false, and
dropping the status would have hidden something its laboratory states plainly.
I added two values — `paused` ("between runs, accelerator in shutdown") and
`construction_running` ("under construction, partial detector taking data", for
KM3NeT, I5) — each documented in the module and each carrying its
`source_quote` like every other status. If you would rather not extend the
vocabulary, deleting the two `status:` lines and keeping `source`/`source_quote`
is a one-minute change and still satisfies the rule.

---

## Important — numbers

### I1 — the 2026 (1, 2)-sector update

Pointers added, **the six stat cards left as they are**: which paper the front
page leads with is your call, not mine.

- `index.html`, under the cards: a paragraph naming the update, with
  δm² = 7.48 (1σ 7.39 – 7.58) ×10⁻⁵ eV² and sin²θ₁₂ = 0.3085 (1σ 0.3010 –
  0.3156), citing PRD 114, 016026 (2026) and arXiv:2511.21650, and stating that
  the other four parameters are unchanged.
- `results.html`, a callout at the end of the 2025 release: the same, with the
  link to the parameter history.

Both sets of values come from the register, where `test_history_numbers.py`
re-reads them out of the cached paper on every run — not from memory.

### I2 — the conventions callout

Rewritten in `tools/make_history.py` to state both shifts **on the modulus**:
−δm²/2 for NuFit (its Δm²₃ℓ = Δm²₃₂ < 0, so adding δm²/2 makes the modulus
smaller), +δm²/2 for Valencia (a modulus already, so the same addition makes it
larger). Checked against `to_our_Dm2()`: NuFit IO returns `abs(value + dm2)`
with `value < 0` → modulus shrinks; Valencia IO returns `value + dm2` with
`value = |Δm²₃₁|` → modulus grows. Normal ordering is −δm²/2 in both cases, as
the sentence still says. `test_history_conversion.py` (13 conversions) passes
unchanged.

### I3 — "status is taken from each collaboration's own pages"

Replaced on `resources.html` with what the data actually is: status comes from
a source recorded with each entry together with the sentence that states it —
"usually the collaboration's own page, and where that page states nothing, the
paper of the experiment's final dataset, a laboratory's operations notice or an
observatory page." The same paragraph also fixes prose I1 (ordering by weight).

### I4 — Hyper-Kamiokande

Source moved from the Japanese splash page to
`https://www-sk.icrr.u-tokyo.ac.jp/en/news/detail/1301` (2026.8.4), quoted
verbatim in the data file: *"The Hyper-Kamiokande project, currently under
construction underground in Kamioka, Hida City, Gifu Prefecture, reached a
major milestone on 31 July 2026, with the completion of the lining work for its
cylindrical detector tank. […] Detector components, including photosensors,
will then be installed on the structure beginning in early 2027, with
scientific operation scheduled to begin in 2028."* Status unchanged
(`construction`); it is the citation that was wrong. Confirmed independently
that `…/hk/en/` 404s and the English page is at `…/en/hk/`; the site links
neither, so nothing to fix there.

### I5 — KM3NeT

Now `construction_running` → "under construction, partial detector taking
data", sourced to the ORCA physics page (fetched):
*"At the end of the current construction phase KM3NeT 2.0, the full ORCA
detector will comprise a detector block of 115 detection units. […] Currently,
ORCA is operated with 28 detection units (ORCA28). […] KM3NeT scientists have
already published compelling results from studies with only a few detection
units."* (That page's unit count is itself stale — the collaboration's news of
8 July 2026 puts ORCA at 42 — which is why the count is not printed on our
page, only the compound status.)

### I6 / prose I18 — the 2001 and 2004 papers under "Nufit"

Three changes. `history.yaml` flags both with `predecessor: true`;
`make_history.py` prints them as **"NuFit (predecessor)"**; and a paragraph
above the table now says it in words, naming the authors of each
(Gonzalez-Garcia, Maltoni, Peña-Garay, Valle in 2001; Maltoni, Schwetz,
Tórtola, Valle in 2004 — both from INSPIRE) and stating that two of them also
appear on the Valencia papers below, so the three series are less separate
before 2012 than three columns suggest.

---

## Important — prose

| # | What was changed |
|---|---|
| I1 | Ordering sentence on `resources.html` rewritten (with I3 above): experiments in the current fit come first, in descending weight, then the rest. |
| I2 | Two notices instead of one, in `tools/news/render.py`. Digest and conferences: "generated automatically by a script from the arXiv API / conference indexers' APIs … **No model is involved.**" News: "The summaries on this page are written automatically with AI from fetched records." Footer and `about.html` rewritten to match; README too. |
| I3 | "files you can compute with" and "the downloadable files" dropped from the index hero, hero caption, results lede, 404 tile and README. The home-page card now points at `history.html#data`, labelled "The parameter register, as JSON and CSV". The `#data` section on `results.html` keeps its honest "nothing is linked yet" and now points readers to the register that *does* exist. |
| I4 | Results lede is now "The most recent full release in detail … Every earlier release is traced parameter by parameter on the parameter history", and the page carries the 2026 pointer (I1). |
| I5 | The two tiles whose sparkline ran to 2026 while the number was 2025 are now explained by the paragraph directly beneath them, which gives the 2026 values and says which release the cards are. The sparklines still show the register's full span, which is their purpose. (See also the sparkline bug below, which affected the δm² card.) |
| I6 | "BibTeX for this release and the ones before it" → "BibTeX for the current release". |
| I7 | The keyword list is now **printed on the digest page**, in a `<details>` generated from `config.yaml` itself, with the weighting rule read out of `fetch_arxiv.TITLE_WEIGHT`/`ABSTRACT_WEIGHT` so the description cannot drift from the code. The index card says "a keyword score whose word list is printed at the foot of that page". |
| I8 | The model-written overview no longer sits above the notice as the page's lede: `news.md` now has a fixed lede, and the overview appears below the banner, labelled "**In summary.** … This paragraph summarises the items below; the sources are on the items themselves." The index card says "every **item** … carries the link it came from". (This also fixes M5.) |
| I9 | Footer licence sentence replaced with the three-way split from `LICENSE`, linking to a new **Licensing** section on `about.html` (`#licence`) that states it on the site itself — `LICENSE` is a repo file and is not published, so the footer had nowhere honest to point. |
| I10 | Same fix as numbers I2. |
| I11 | `.capitalize()` replaced by a `GROUP_DISPLAY` map; an unknown group key now fails the build instead of being silently mangled. "Nufit" appears nowhere in `site/`. |
| I12 | `tools/news/common.detex()` renders the TeX that arrives in titles (`\bar\nu` → ν̄ with a combining macron, `NO$\nu$A` → NOνA, `^{40}` → ⁴⁰, unknown commands lose the command and keep the argument), and citation titles are cut with `truncate()` — word boundary, ellipsis — instead of `title[:90]`. |
| I13 | `astro-ph.HE` dropped from `render.EXPERIMENTAL_CATS`. The pipeline's wider pool for the AI narrative is now a separate constant, `EXPERIMENT_POOL_CATS`, so the two cannot be changed by accident together. The digest footnote now states the rule: "The split between the two streams is by the preprint's primary arXiv category". Today's rebuild moves from 6/10 to 2/14. |
| I14 | The conferences note now describes what the page does: dates confirmed or dropped, "a venue is shown when the source publishes one, and left blank when it does not", and "A meeting stays under 'Upcoming' until its last day is over". The frontmatter description and the index card were softened the same way. I did **not** teach the fetcher to read Indico's `address` field — see the list of things not done. |
| I15 | "twenty years" → "a quarter century" in README and `404.html`; the home-page chart is retitled "How the precision improved", with no span claim over a 2006–2026 chart. |
| I16 | The heading now reads "11 releases · 393 values, **381 of them checked against the source they name**", and the caption explains the 12 derived endpoints and the release whose source is equations rather than a table. Both counts are computed from the data in `make_history.py`, not typed: 393 − 12 = 381, and `test_history_numbers.py` independently reports "12 declared as derived, not searched". |
| I17 | "Google Scholar has no public search API, and NASA ADS's requires a personal token"; the later paragraph now opens "Its search API is public and documented, but it requires a personal token". |
| I18 | See numbers I6. |
| I19 | **Not fixed** — see below. |

---

## Minors fixed

- numbers M1 — the cards now say "**formal** 1σ accuracy", and the paragraph
  below defines it and warns that it is not half the 1σ range over the best fit.
- numbers M2 / prose M12 — NuFit 2018's title completed from INSPIRE:
  "…synergies and tensions **in the determination of θ₂₃, δCP, and the mass
  ordering**" (`titles[0].title` of `1811.05487`, with the TeX rendered as
  text); the 2026 title now has the published "(1, 2)".
- prose M1 — the second `About this site` heading is now "How this site is built".
- prose M2 — "11 releases" both times.
- prose M3 — "SNO+ is nevertheless expected to surpass the present δm² accuracy…".
- prose M4 — the authors' own caveat added: *"We underline some issues about
  systematics, that might affect this error estimate"* (abstract of
  arXiv:2503.07752, fetched).
- prose M5 — banner now precedes the generated prose (with I8).
- prose M6 — "with the links each record carries".
- prose M11 — "March 2025 — **E**ntering the era of subpercent precision".
- prose M13 — the daily stamp now carries its zone ("14 August 2026, 10:58 CEST").
- prose M15 — "No meeting in this window has ended yet."
- prose M10, partly — KamLAND and KamLAND-Zen kept `completed` but now carry
  the sentence that states it, from the collaboration's own dated news pages
  (fetched): *"On August 27, 2024, the KamLAND data acquisition drew to a close
  with 22 years of observation history. Major detector upgrades have now
  started in preparation for the upcoming KamLAND2 experiment."*
  (`…/News/2024/Completion_KamLAND_Aug_in2024-kl.html`, Aug. 29, 2024) and
  *"KamLAND-Zen 800 experiment … was completed on January 12, 2024 …"*
  (`…/News/2024/Completed_KamLAND_Zen_800_eng.html`, Feb. 05, 2024). The
  KamLAND-Zen tile now says which phase it means ("…, 800 phase"), so
  "completed" cannot be read as the end of the programme. Five records left the
  `STATUS_QUOTE_BACKLOG`, which only ever shrinks.

## A bug neither audit found, fixed here

**The δm² stat card on the home page was drawing |Δm²|'s sparkline.**
`tools/make_figures.py` wrote `spark-dm2.svg` and `spark-Dm2.svg`, which are
the same file on this machine's case-insensitive filesystem: the second
overwrote the first and both cards included the same curve. Confirmed
empirically (only five spark files existed for six cards; the δm² card's label
read "→ 2025" although δm² has a 2026 value). Fixed with a slug map —
`|Δm²|` is now `spark-Dm2-abs` — and a guard that refuses to write two spark
slugs differing only in case, so it cannot come back silently. The δm² card now
correctly runs to 2026.

While regenerating, the sparklines also picked up the 2006 release, which had
been added to the register after the committed SVGs were last built: they now
start at 2006 rather than 2011. That is the generator catching up with the
data, not a content decision.

---

## Deliberately not fixed

| Finding | Why |
|---|---|
| **prose I19 — the postcode** | I could not verify 70125 for *Via Amendola 173* from any primary source. UniBa's site serves robots a 708-byte stub; INFN Bari publishes "Via E. Orabona 4 - 70125", a different street; OpenStreetMap returns 70121 and 74126 for Via Amendola. 70126 is what the group's own papers print. Changing a factual string to one I cannot source would break the project's first rule, so it stands. **Worth your ten seconds**: if 70125 is right for the department building, say so and I will change it. |
| numbers M3 — AMoRE's 26-month-old source | The stored quote is verbatim and states installation in terms; the newer paper (arXiv:2607.08039, 9 July 2026) says only *"An improved sensitivity is expected for the upcoming AMoRE-II experiment"*, which supports "not yet running" but not "under construction" as directly. The file's comment already records the 2026 paper. Swapping to a weaker sentence would be a downgrade. |
| numbers M4 — the empty "Recent" section | The project's stated preference is that "an honest empty section beats an invented full one"; suppressing sections when empty is a design choice, not a correction. The wrong verb in it was fixed (M15). "invisibles 26" appearing under Upcoming on its final day is the intended rule, now stated on the page. |
| prose I14, the fetcher half | Reading Indico's `address` field would put "Sede Afundación, Cantón Grande 8, A Coruña, 15003, Spain" under a conference title. Whether that is an improvement is a taste question, and the prose now describes what the page does. |
| prose M7 — the dropped condition in the decoherence summary | That sentence is model-written. Rewriting it by hand would make a page labelled "written automatically" partly hand-written, which is a worse lie than the one it fixes. It will be regenerated tomorrow. |
| prose M8 — "Old Trafford" | Same class: the string is what the source published, and shortening venue strings is presentation taste. |
| prose M9 — two `http://` links | Both hosts answer only on http; rewriting them to https would break two working links. |
| prose M10, the rest | Seven experiments carry no status (Homestake, NOvA, MicroBooNE, PROSPECT, CUORE, DUNE, Project 8). Printing nothing where nothing is sourced is exactly what the rule asks for; adding seven statuses means seven sourced sentences, which is a work item, not a correction. |
| prose M14 — affiliation order | Cosmetic, and the affiliations are correct. |
| prose M16 — `chi2.js` ships unreferenced | It is referenced by `drafts/content/release-2026.md`, i.e. it is there for the embargoed release. Deleting it would break the draft build. |
| rendering audit's two Minors | Both are "correct behaviour, could be prettier" (SVG letterboxing on phones, Semantic Scholar's rate limit). Nothing touched them. |

---

## Verification

```
./.venv/bin/python3 build.py                      → 10 pages, all internal references resolve
test_built_pages.py      all 10 checks pass
test_credits.py          all 7 checks pass
test_experiments.py      all 10 checks pass — 44 experiments
test_history_conversion  all 13 conversions agree with the identity
test_history_export.py   all 7 checks pass — 141 rows, both directions
test_history_numbers.py  all 555 values verified (12 declared as derived)
test_history_schema.py   all 35 checks pass
test_no_draft_leak.py    all 4 checks pass
test_release_numbers.py  80 numbers of Table I + index cards match the paper
test_theme.js / test_map.js / test_figure.js / test_mockup_contrast.js  all pass
```

Strings confirmed gone from `site/` **and** `data-exports/`: `013003`,
`Capozzi:2025wgt`, `Nufit`, `gc.zgo.at`, `twenty years`,
`generated automatically with AI`, `no runtime request`, `One entry per
release`, `stated keyword`. Confirmed present: `016026 (2026)` in
`site/history.html`, `site/data/history.{json,csv}` and
`data-exports/history.{json,csv}`; `Capozzi:2025wyn` in `site/about.html`;
`NuFit (predecessor)` twice in `site/history.html`.

## Needs your decision

1. **Which release the front page leads with.** The six stat cards are still
   the 2025 release, with the 2026 update stated beneath them. Replacing two of
   six with values from a different paper is an editorial call.
2. **The two new status words** (`paused`, `construction_running`). Reasoned
   above; trivially reversible.
3. **The postcode.** 70125 or 70126 for Via Amendola 173 — you know, and I
   could not source it.
