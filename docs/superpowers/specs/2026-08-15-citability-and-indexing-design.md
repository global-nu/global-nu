# Citability and indexing: a DOI for the register, and metadata a machine can read

Date: 2026-08-15 · Status: awaiting review

## The problem, stated plainly

The parameter register is the most original thing this site publishes. It puts
Bari, NuFit and Valencia on the same axes across 141 rows and a quarter century,
each value traced to the table of the paper that printed it, with the convention
conversions documented and tested. Nothing else we know of does this.

It is also, today, citable only as a URL. A URL is not an identifier: it dies
with a domain, a hosting decision, or a change of group. Somebody who builds on
the register in 2029 has nothing durable to point at, and somebody looking for
exactly this dataset has no way to find it — Google Dataset Search cannot see it,
because the page never says, in a form a machine reads, that a dataset is here.

The same silence covers the crawlers. `robots.txt` is three lines that allow
everything by omission. That happens to permit the AI crawlers, which is the
outcome we want, but it is an accident of a wildcard rather than a position the
site has taken — and there is nowhere the site asks to be attributed.

## Decisions taken

Antonio decided, on 2026-08-15:

1. **The DOI goes to the register alone**, as a Zenodo *Dataset* deposit — not to
   the repository as software, and not to both. The register is the reusable
   scientific object; the code is the means. Zenodo gives a concept DOI that
   always resolves to the newest version, plus one DOI per version.
2. **The crawler policy is open and explicit.** The main AI crawlers are named in
   `robots.txt` and allowed one by one, rather than left covered by the wildcard.
   This is coherent with the CC BY 4.0 the data already carries: declining by
   `robots.txt` what the licence grants would be incoherent. Attribution is asked
   for in `llms.txt`, where a model actually reads it.
3. **Antonio deposits alone, on the group's behalf** — creator: Antonio Marrone,
   ORCID `0000-0001-6096-1880` (confirmed by him, and cross-checked against the
   INSPIRE author record, the author block of the 2025 paper, and `orcid.org`),
   affiliation Università di Bari and INFN Bari. The register compiles values
   published by three groups; depositing it under the six names of the 2025 paper
   would commit colleagues to an object they did not build. Names can be added in
   a later version if they want in.
4. **Structured metadata stays targeted.** `Dataset` JSON-LD on `history.html`,
   `Organization` + `WebSite` on `index.html`, `citation_*` on `history.html`
   only, `llms.txt` at the root. Nothing on `results.html`.
5. **The dataset title is the technical one**, generated with the register's real
   year span: *"Published global-fit values of the three-flavour neutrino
   oscillation parameters, with provenance and convention conversions
   (2001–2026)"*. The span is computed, never typed — the register already
   reaches 2026, and a hand-written year is a value that rots.
6. **The real deposit is made by Antonio, from the web interface**, after the
   whole run has been rehearsed against `sandbox.zenodo.org`. A permanent DOI is
   minted by a person, not by a process.

## Why `citation_*` does not go on `results.html`

The `citation_*` tags are Google Scholar's interface, and Scholar reads them as
"the full text of a scholarly work is at this URL". `results.html` presents the
numbers of Phys. Rev. D 111, 093006; it is not that paper. Tagging it would
invite Scholar to index a second, spurious record of the group's own article,
carrying the group's own names. On `history.html` the tags describe an object
that exists in its own right and has its own DOI, so they are honest there.

This was put to Antonio explicitly. He chose the targeted option.

## Architecture

### One placeholder, opt-in per page

`site-src/templates/base.html` gains a single placeholder, `{{head_extra}}`,
immediately before `{{katex_head}}`. It is empty on eight of the ten pages.

Pages opt in from their own front matter — the mechanism the build already uses
for `katex` and `sitemap`:

```yaml
jsonld: dataset   # history.md
jsonld: site      # index.md
```

An unknown value is a build error, not a silent empty string. A typo that
silently removes the site's structured metadata is exactly the failure this
project keeps catching in audits rather than in tests.

### `head_extra(fm, cfg, url)` in `build.py`

A new module-level function, deliberately outside `build_pages`, which is already
long. It returns the `<script type="application/ld+json">` block and, for the
dataset page, the `citation_*` meta tags.

The `Dataset` object on `history.html` carries:

| Field | Source |
|---|---|
| `name`, `description` | the page's front matter |
| `url` | canonical URL, as the existing `<link rel=canonical>` |
| `license` | `https://creativecommons.org/licenses/by/4.0/` |
| `creator` | `Person`, name + `identifier` (ORCID) + `affiliation` |
| `distribution` | two `DataDownload`: `history.json` (`application/json`), `history.csv` (`text/csv`) |
| `temporalCoverage` | **computed** from the register's min and max `year` |
| `variableMeasured` | **computed** from the parameters present in the register |
| `dateModified` | **the last commit date of `site-src/data/history.yaml`**, not the build date |
| `identifier`, `citation_doi` | emitted **only** when `zenodo_doi` is set |

The `citation_*` tags on the same page are `citation_title`, `citation_author`,
`citation_publication_date`, `citation_public_url`, and `citation_doi` — the last
only when a DOI exists.

Three of these deserve their reasons in writing:

**`dateModified` must not be the build date.** The site is rebuilt every morning
by the 07:30 job. A `dateModified` of "today" would rewrite `history.html` on
every run, and the daily refresh commit would carry a diff whose only content is
a date — noise that hides the real changes underneath it.

The register carries no date field of its own, so the date comes from
`git log -1 --format=%cI -- site-src/data/history.yaml`. That was chosen over the
two alternatives on purpose. A hand-maintained `meta.updated:` field is a value
somebody must remember to change, and this project has already learned what
happens to values that depend on discipline. The file's mtime is meaningless
after a fresh clone. The commit date cannot rot and needs nobody to maintain it,
and because the register changes only when a new global fit is published — not
daily — it is stable between releases. If `git` is unavailable or the file is
untracked, the field is omitted rather than guessed.

**`temporalCoverage` and `variableMeasured` are computed.** Written by hand they
become two more values that quietly disagree with the data, which is the class of
error this project's tests exist to prevent.

**No DOI means no claim.** With `zenodo_doi` unset in `site.yaml`, the build emits
neither `identifier` nor `citation_doi` nor a DOI line in `llms.txt`. The page is
correct and publishable without them. This is the project's founding rule applied
to metadata: a page that prints nothing where a value is unknown is doing the
right thing.

### `robots.txt` becomes data

It stops being an f-string at `build.py:619` and becomes `site-src/robots.txt`,
where the list of crawlers is reviewable text rather than a string inside code.
`build.py` appends the `Sitemap:` line derived from `site_url`, so the domain
stays defined in exactly one place.

The file names and allows, one by one, the crawlers the policy covers: the search
engines, the AI training crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot,
Bytespider, Applebot-Extended, Meta-ExternalAgent), and the AI retrieval agents
that fetch a page to answer a question and cite it (OAI-SearchBot, ChatGPT-User,
Claude-User, PerplexityBot). A short comment block states the position and points
at the licence.

### `llms.txt`

`site-src/llms.txt`, passed through `render_template` — it needs `site_url` and
the DOI — and copied to the published root. Short prose: what the site is, what
is under CC BY 4.0 and what is not, how attribution is asked for, where the two
data files are, and the DOI when there is one.

It is not a standard and no vendor has committed to honouring it. It costs one
small file, and it is the only place where the attribution the licence requires is
stated in a form a model reads.

## The deposit

`tools/make_zenodo_deposit.py` assembles a working directory:

- `history.json` and `history.csv`, copied from the published exports
- `README.md`, documenting the fields one by one, **generated from the same source
  that documents them on `history.html#data`**, so the two cannot drift apart
- the CC BY 4.0 licence text

and writes `zenodo.json` beside it: `upload_type: dataset`, the computed title,
`creators` with ORCID and affiliation, description, `license: cc-by-4.0`,
keywords, and `related_identifiers` binding the deposit to the site URL and to
the 2025 paper — DOI `10.1103/PhysRevD.111.093006`, arXiv `2503.07752`. Version
`1.0.0`.

**By default it touches no network.** It prints what to upload and stops. With
`--sandbox` and a token it rehearses the whole round trip against
`sandbox.zenodo.org`, which mints throwaway DOIs and can be got wrong as many
times as needed. Only when that run is clean does the real deposit happen, by
hand, from Antonio's account.

## Testing

A new `tools/tests/test_metadata.py`:

| Check | The failure it prevents |
|---|---|
| The JSON-LD on `history.html` parses, and has the required fields | a malformed block is invisible to the eye and mute to a crawler |
| Every `distribution.contentUrl` exists in `site/` | an export is renamed and the metadata points at nothing |
| `temporalCoverage` and `variableMeasured` agree with the register | they degrade into hand-written values that rot |
| With no `zenodo_doi`, no `citation_doi` or `identifier` anywhere | the project's rule: no claim that cannot be supported |
| With a `zenodo_doi`, it has the shape `10.xxxx/...` | a truncated or mistyped DOI ships silently |
| `dateModified` matches the register's commit date, and is not the build date | the daily job starts churning `history.html` with a date-only diff |
| `robots.txt` names every crawler in the declared list, and every rule is `Allow` | a later edit blocks somebody by accident, against the stated policy |
| `llms.txt` contains no unsubstituted `{{` | a placeholder reaches the published root |

Whether the DOI actually *resolves* is a network check, marked skippable: the
07:30 job must not fail because Zenodo is down.

## Order of work

The order is the part that protects us, because it puts the irreversible step
last.

1. **The metadata machinery and its tests, with the DOI absent.** Build, verify,
   publish. The site is already correct in this state.
2. **The deposit package, rehearsed on the Zenodo sandbox** until the round trip
   is clean.
3. **The real deposit**, made by Antonio from the web interface. The concept DOI
   comes back.
4. **One line in `site.yaml`**, rebuild, verify on the live page — not only
   locally — and commit.

## Out of scope

- Any change to `results.html`, its metadata, or the way the paper is cited.
- A software DOI for the repository, and the GitHub↔Zenodo release integration.
- Automating the deposit from the daily job. An unattended process that mints
  permanent public identifiers cannot take back a mistake; this was considered
  and rejected.
- `Dataset` metadata for the conferences and digest exports. They are derived,
  regenerated daily, and not the object anybody would cite.
