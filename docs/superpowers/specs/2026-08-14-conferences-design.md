# Conferences: the sources the page was missing, and a map worth clicking

Date: 2026-08-14 · Status: awaiting review

## The problem, stated plainly

Antonio's own personal site has a better conferences page than global-nu's, and
the reason is not presentation. It is sources.

`tools/news/pipeline.py` fetches arXiv, feeds, INSPIRE **literature** and Indico.
It does not fetch Neutrino Unbound, and it never asks INSPIRE for conferences at
all. So Indico is the only conference source, and Indico's generic categories are
what the page ends up showing: on the day this was written the published page led
with *CZ+SK HEP Workshop 2026* and *Probing new physics beyond the standard model
at the HL-LHC and future lepton colliders* — neither about neutrinos — while
NuFact, the Erice school and the joint IceCube–KM3NeT–JUNO workshop were absent.

Two things make this cheap to fix:

- **`tools/news/conferences.py` already merges and deduplicates three providers.**
  It knows the string `nu-unbound`, it decides which record leads when two
  sources describe one conference, and it records which sources listed it. The
  merge layer was ported; only the fetchers that feed it were not.
- **`conferences_nu_unbound` already exists in `tools/news/config.yaml`**, fully
  documented, and nothing reads it.

There is also a loose end this closes: `tools/news/geocode.py`'s docstring names
`figures.conference_map` as a consumer. That function has never existed. A
pre-launch audit found the reference and flagged it.

## Decisions taken

Antonio decided, on 2026-08-14:

1. **Timeline and map, both.** He was told the risk — two large figures can push
   the list, which is the part people actually consult, below the fold — and
   chose both anyway. The design contains that risk rather than ignoring it.
2. **Neutrino conferences first, general particle physics below**, in two
   sections, as his personal site does by querying INSPIRE with both scopes.
3. **Work harder to place each point**, reading the conference's own page when
   the structured sources do not yield a location.
4. **A city photograph in the card**, freely licensed.
5. **A "open in Google Maps" link in the card**, opening in a new tab.

## The work

### 1. Three sources instead of one

`fetch_nu_unbound.py` is ported **unchanged** from the personal site. It carries
nothing specific to that site, and it is carefully built: the start date is read
from the `id` attribute (`20260831__NuFact_2026`) rather than parsed from prose,
a record whose end date cannot be established is **dropped rather than guessed**,
and the 800 kB page is fetched conditionally with ETag and `If-Modified-Since`,
so the ordinary morning answer is a 304 with no body.

`fetch_inspire.fetch_conferences(cfg, log, scope=...)` is ported with both
scopes, `neutrino` and `general`.

Both are wired into `pipeline.py` beside the existing Indico fetch, each inside
the existing `_safe()` wrapper so one failing source cannot take the run down.
Neutrino Unbound is a university web page, not an API with an uptime guarantee;
the page must build when it is unreachable.

`tools/news/conferences.py` is **not modified**. If merging three sources
reveals a defect in it, that is a finding to report, not a licence to redesign
the merge during this work.

### 2. Placing the point: a cascade, not a scrape

For each conference, in order, stopping at the first that yields a location:

1. **Neutrino Unbound's `place`** — already clean, e.g. `Shanghai, China`.
2. **INSPIRE's structured address fields** on the conference record.
3. **Indico's `address` field.** We already fetch it and throw it away: a
   pre-launch audit judged it too verbose to *print* under a title
   (`Sede Afundación, Cantón Grande 8, A Coruña, 15003, Spain`). Verbose for a
   title is precise for a geocoder.
4. **The conference's own page**, parsed for a structured address
   (schema.org `Event`/`Place` first, a postal address pattern second).
5. **Nothing.** The conference keeps its place in the list and gets no dot.

Step 4 is last for a reason: it is thirty requests a day to other people's
servers, and every conference site is built differently. **The outcome of every
attempt is cached — success and failure alike** — so an unresolvable venue is
tried once, not every morning. Coordinates continue to go through
`tools/news/geocode.py` and its existing cache.

The standing rule holds: **a dot in roughly the right country is worse than no
dot.** A location that cannot be established leaves the conference off the map
and in the list.

### 3. The page

Four blocks: **timeline**, **map**, **neutrino conferences**, **general particle
physics**.

`figures.conference_timeline()` is ported from the personal site and restyled in
global-nu's tokens. `figures.conference_map()` is new and reuses
`tools/news/worldmap.py` and `geocode.py` — the same machinery as the experiments
map.

**An architectural difference that matters:** the experiments map is generated at
build time from static data by `tools/make_map.py`. This one is generated every
morning from data fetched that morning, so it is written by the daily renderer,
not by `make_map.py`. The two must not be merged into one generator.

**Containing the risk Antonio accepted:** both figures are compact, the map is
about half the height of the experiments map's 720×324 frame — it exists to show
where the field gathers, not to be explored — and the list begins above the fold
on an ordinary screen. If it reads badly when opened, cutting a figure is one
line.

**The map shows upcoming conferences only.** Past ones stay in the "recently
held" list and get no dot: a map is a picture of where to go, and mixing the two
would need a second visual language to tell them apart, on a figure whose whole
job is to be read at a glance. This also matches the photographs, which are
fetched for upcoming conferences alone, so every dot on the map can carry one.

### 4. The card

Clicking a marker opens a card carrying: the conference name and its acronym,
the dates, the place, a link to the conference, a **city photograph with its
credit**, and a **"Open in Google Maps" link that opens in a new tab**
(`target="_blank"` with `rel="noopener noreferrer"`; the card is built in
JavaScript, so `build.py`'s `externalize_links` does not reach it and the
attributes must be set in the card code).

The Google Maps URL is built from the geocoded coordinates —
`https://www.google.com/maps/search/?api=1&query=<lat>,<lon>` — not from the
venue string, so it lands where the dot is rather than wherever a text search
drifts to.

### 5. The photographs

`tools/fetch_commons_images.py` does this already and its rules are the design:
it fetches from Wikimedia Commons, **refuses any licence that does not permit
reuse**, and records the author and the licence. It is the same code whose
`short_author` collapsed JUNO's seven hundred authors to "JUNO Collaboration".
No generic web image search — on the open web "free" routinely means "nobody
checked".

Three bounds:

- **City, not venue.** Commons has a good photograph of Shanghai or Corfu; of
  "Sede Afundación" it almost certainly does not. Cities also repeat between
  conferences, so each is fetched once.
- **Upcoming conferences only**, which bounds the count and the weight.
- **The credit travels with the photograph** — author, licence, and a link to
  its Commons file page — exactly as in the experiments map's cards. That is the
  licence, not a courtesy.

The site is 2.6 MB today and roughly twenty-five cities would be involved. The
existing image pipeline already resizes and compresses (`site.yaml`:
`max_side: 1600`, `quality: 82`), but 1600 px is for a figure on a results page,
not for a photograph inside a card: **these are generated at 640 px on the long
side**, which is ample for a card at any screen density this site targets.
**If the built site grows past roughly twice its current size, stop and report
it** rather than shipping it silently — the number of cities is not known until
the sources are merged for the first time.

## Verification

- The page builds when **any one source is unreachable**, and when **all three**
  are: unreachable sources are skipped with a warning and the page keeps
  yesterday's content with yesterday's timestamp.
- Merging the three sources produces no duplicate conference. NuFact listed by
  both Neutrino Unbound and INSPIRE must appear once, with both providers
  recorded.
- A conference whose location cannot be established appears in the list and not
  on the map — asserted by a test with a synthetic record, not by inspection.
- Every photograph rendered carries author, licence and Commons link. A record
  whose licence could not be established has no photograph rather than an
  uncredited one.
- The daily run does not slow measurably: geocoding and photographs come from
  caches after the first run, and every network attempt caches its outcome
  including failure.
- The page is looked at in a browser, both themes, at 1280 and 375 px, before it
  is called done — and the judgement Antonio was warned about is checked there:
  does the list still read, with two figures above it?

## Not in this spec

`tools/news/conferences.py`'s merge logic is used, not revised. The other
"better than NuFit" work for the daily pipeline — RSS/Atom feeds, a browsable
archive rather than only the current day, a defensible ranking — remains its own
design, as does the Methodology page.
