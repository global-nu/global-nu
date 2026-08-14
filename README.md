# global-nu

The site of the Bari global analysis of neutrino oscillation data —
[global-nu.org](https://global-nu.org).

A static site: HTML, CSS and a little JavaScript, built by `build.py` from
`site-src/`. No framework, no CDN, no runtime request to anything. Fonts, KaTeX
and every script are served from the site itself.

## What is here

**Results** — the published releases of the global analysis: best fits and
allowed ranges for the six oscillation parameters in our conventions, with the
tables, the figures and the downloadable files.

**Parameter history** — how the parameters moved across twenty years of
published global fits, and the only place we know of that puts Bari, NuFit and
Valencia on the same axes. The three groups do not report the same quantity:
we use Δm² = m₃² − ½(m₁²+m₂²), NuFit reports Δm²₃ℓ, Valencia reports |Δm²₃₁|
for both orderings. Every comparison passes through a conversion that is
documented in the code and on the page, and the register records what each
paper printed, unconverted, alongside it.

**arXiv digest, News, Conferences** — regenerated every morning by a local job.
Each is marked as automatically generated, with the timestamp of its last
successful update.

**Search** — natural-language search across INSPIRE-HEP, arXiv, Crossref,
OpenAlex and Semantic Scholar, running entirely in the reader's browser. What
you type goes from you to those databases and never to this site.

## The rule this project is built on

**No value with a source is written from memory.** Every physical number and
every factual claim is checked against its primary source — the table in the
paper, the collaboration's own page — before it is written, and a value that
cannot be established is left out rather than guessed. A page that prints
nothing where a number is unknown is doing the right thing.

That rule is enforced by tests, not by intention:

| Test | What it checks |
|---|---|
| `test_history_numbers.py` | every value in the register is found in the cited table of the cited paper |
| `test_history_schema.py` | a value is a measurement or a limit, never both; a limit names its confidence level; the cited table exists in the cited PDF |
| `test_history_conversion.py` | every cross-group conversion agrees with the identity it claims |
| `test_release_numbers.py` | the numbers on the results and home pages match the paper's table |
| `test_experiments.py` | the experiment list and the map cannot disagree |
| `test_history_export.py` | the published JSON and CSV are what the register currently says |
| `test_built_pages.py` | no page ships unconverted Markdown |
| `test_no_draft_leak.py` | nothing embargoed has reached the published tree |
| `test_theme.js` | every colour pair clears WCAG contrast in both themes |

## Building it

```sh
./setup-venv.sh                  # once
./.venv/bin/python3 build.py     # site-src/ -> site/
./serve.sh                       # preview at http://localhost:8000
```

`site/` is build output and is never edited by hand. `site-src/content/*.md`
holds the pages; `site-src/data/*.yaml` holds the data; `tools/` holds the
generators and the tests.

Some pages are themselves generated — `history.md` by `tools/make_history.py`,
the daily pages by `tools/news/` — and say so in a comment at the top. Edit the
generator or the data, never the Markdown.

## Licensing

Not one licence for everything. The data is CC BY 4.0; the code and the prose
are all rights reserved; third-party figures and photographs carry their own
terms, credited beside each one. See [LICENSE](LICENSE).

## The group

Capozzi, Giarè, Lisi, Marrone, Melchiorri, Palazzo. See the
[About](https://global-nu.org/about.html) page for the series of papers and how
to cite them.
