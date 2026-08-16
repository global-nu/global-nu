# An archive for the arXiv digest

Date: 2026-08-16 · Status: awaiting review

## The problem, stated plainly

The digest is ephemeral. Every morning the job overwrites
`site-src/content/digest.md` and the previous day ceases to exist — not moved,
not superseded, gone. A reader who saw a preprint on the page yesterday and
wants it today has no way back, and the site keeps no record of what it said.

Antonio's own site solved this long ago: one page per day under
`highlights/YYYY-MM-DD.html`, and an "Archive" block on the digest page listing
every previous edition, most recent first. Half of this work is a port of that.

The other half is a problem his site does not have, and it is the reason this
needed a design rather than a patch.

## The finding that shaped everything

`tools/news/config.yaml` sets `window_hours: 168`. The digest does not show
"today's preprints"; it shows the best-scoring preprints of the **last seven
days**. Two consecutive editions therefore overlap by six sevenths.

Measured on the cached records: **92 of 100 arXiv identifiers appear on more
than one day.**

Taken literally, "an archive day by day" would produce ten pages repeating
roughly 86% of one another, and a monthly rollup in which the same paper
appears up to seven times. The obvious implementation produces a useless
artefact. Everything below follows from avoiding that.

## Decisions taken

Antonio decided, on 2026-08-16:

1. **Archive by arXiv announcement date**, not by the day the page happened to
   show it. Every record already carries its own `date`, so each paper is filed
   once, under one day, and the seven-day window stops mattering to the
   archive. It also makes the archive self-healing: a paper announced on the
   12th that first enters the window on the 14th still files under the 12th.
2. **Keep what was published, not everything fetched.** Roughly fifty preprints
   pass the keyword filter each run and sixteen reach the page. The archive of
   the digest is the digest — anything else turns it into a second, worse copy
   of arXiv, which already exists.
3. **Nothing is discarded.** The first sketch dropped days older than a month;
   Antonio rejected that. The archive accumulates.
4. **The ten most recent days are listed by name; everything older is reached
   through a page per calendar month.** Note what this is: a rule about the
   *index*, not about what exists. Every day keeps its own page (see the next
   section); the ten are simply the ones the reader sees without going through
   a month. A monthly page whose contents shift daily would not be a monthly
   page, so the rollup follows the calendar, not a sliding window — and the
   page for the month in progress exists from its first day and grows, rather
   than appearing only once the month has ended.

## One decision I took, and why

Decision 4 leaves a gap Antonio's answer implies but does not state: when a day
passes out of the most-recent ten, does its own page disappear into the monthly
one?

**No. Day pages persist.** A URL that existed and then returns 404 is
information lost, which contradicts decision 3 directly — and any link a reader
made to `digest/2026-08-12.html` would break. The monthly page is therefore an
additional view of a month, not a replacement for its days.

This also removes every deletion from the design, which matters more than it
sounds: see the publish constraint below.

The cost, stated rather than hidden: roughly 250 new pages a year, all of them
in the sitemap. Antonio's own site already carries the same cost for the same
reason.

## The constraint that makes this architectural

`tools/news/pipeline.py` publishes by handing `git add` a **literal list of
seven paths** — the three generated pages, their built output, and the sitemap —
with the comment that "anything else in the tree is someone's work in progress
and is not this job's to commit". Archive pages are generated daily and are not
in that list. Left as it is, every night's run would leave new files
uncommitted, `git pull --rebase` would refuse a dirty tree, and publication
would stop.

That failure has now occurred twice in one day for unrelated reasons, and both
times it was silent. The design must extend `GENERATED_PATHS` to cover the
archive directories.

Because day pages persist, the job only ever **adds** files, never removes
them, so a plain `git add` of the two directories is enough and the more
dangerous `git add -A` is not needed. That is the practical dividend of the
decision above.

## Architecture

### `var/news/archive.json` — the store

A single JSON object mapping an announcement date to the records published on
that date:

```json
{"2026-08-12": [ {record}, {record} ], "2026-08-13": [ … ]}
```

Written by a new `tools/news/archive.py` after the digest renders. Each run
takes the records that reached the page, groups them by their own `date`, and
merges into the store **by arXiv identifier**, so:

- re-running a day changes nothing;
- a paper seen again on a later run is not duplicated;
- a paper whose record improved (a DOI appeared, a title was corrected) is
  updated in place rather than appended.

The store is the single source of truth for every archive page. Pages are
regenerated from it, never appended to, so a page can always be rebuilt from
scratch and cannot drift.

### The pages

Generated by `tools/news/archive.py` from the store:

| Path | Contents |
|---|---|
| `site-src/content/digest/YYYY-MM-DD.md` | one day, every paper filed under it |
| `site-src/content/digest/YYYY-MM.md` | one calendar month, days as sections, most recent first |
| the `Archive` block inside `digest.md` | the ten most recent days by name, then the months |

`build.py` already walks `CONTENT` with `rglob("*.md")` and already sets
`base = "../" * url.count("/")`, so pages in a sub-directory build, resolve
their assets and appear in the sitemap with no change to the generator. This
was verified, not assumed.

Each day page states its own provenance in the same words the main page uses —
generated automatically, from the arXiv API, no model involved — and carries
the count of papers, so the Archive list can show it without recomputing.

### The Archive block

Rewritten in place between `<!-- ARCHIVE:BEGIN -->` and `<!-- ARCHIVE:END -->`
markers inside the digest page, the same mechanism Antonio's site uses. Markers
rather than regeneration of the whole page because `digest.md` is written by
`render.digest()` and this block is written by a different step; two writers on
one file need an explicit seam.

### Where it runs

After the digest renders and before the build, inside the existing `_safe`
wrapper so a failure in the archive can never take down the run that publishes
the site. An archive that breaks must cost the archive, not the day's digest.

## Testing

| Check | The failure it prevents |
|---|---|
| A paper appearing in three consecutive runs is stored once | the seven-day window quietly multiplying every entry |
| It is filed under its own `date`, not the run date | the archive drifting one day at a time when a run is late |
| A record whose fields improved replaces the older copy | a stale title or a missing DOI frozen forever |
| Day pages exist for every day in the store | a day silently absent from its own archive |
| The monthly page contains exactly the days of that calendar month | a paper filed under the wrong month at a boundary |
| No day page is ever deleted | the 404 this design exists to avoid |
| `GENERATED_PATHS` covers both archive directories | the silent publication stall described above |
| The store round-trips: pages regenerated from it are byte-identical | a page that can no longer be rebuilt from its source |

And the built pages are looked at in a browser, at three widths and both
themes, before this ships.

## Out of scope

- Changing `window_hours`, or what the main digest page shows. The archive is
  built from what the page published; the page itself is unchanged.
- Any AI-written summary of a day or a month. The digest's own lede states that
  it is built by script with no model involved, and the archive must be able to
  say the same.
- Search across the archive. The site's search already covers INSPIRE, arXiv
  and three more databases; a second search over a subset of arXiv would be
  worse than the one that exists.
- Retention. Decided against; the archive accumulates.
