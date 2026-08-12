# Resources and home: one source for the experiments, a map worth using, a real hero figure

Date: 2026-08-12 · Status: awaiting review

## What is wrong today

Four faults, reported by Antonio after looking at the built pages.

**The experiment list is thin and arbitrarily ordered.** Resources shows 13
experiments. Double Chooz is there; Daya Bay and RENO — the two measurements
that actually fix θ₁₃ — are not. For a group that publishes global analyses,
that list is not defensible.

**The list exists twice.** `site-src/data/experiments.yaml` feeds the map;
the tiles under it are hand-written HTML in `site-src/content/resources.md`
holding the same names and URLs again. The YAML's own header says the `url`
must match the resources page "so the two cannot drift" — but nothing enforces
it, and every addition has to be made twice. This is the root cause of the
first fault: a list that costs double to extend does not get extended.

**A photograph's credit runs to some seven hundred names.** `tools/fetch_commons_images.py`
copies Commons' `Artist` field verbatim; for `JUNO Detector with labels.jpg`
that field is the collaboration's entire author list. It is printed under the
photograph.

**The home page's hero figure is invented.** It is a hand-drawn SVG of two
oscillation curves labelled "schematic, not a fit" and "Illustrative". A site
whose first rule is that no number appears without a source should not open
with a drawing that has none.

## Decisions taken

Antonio chose, on 2026-08-12:

- The photographs **leave the Resources page** and reappear inside the map:
  clicking an experiment opens a card that may carry its photograph. There is
  no gallery section any more.
- The hero figure becomes **the six parameters with their 1σ and 3σ ranges**,
  from the verified Table I numbers — a compact variant of the figure on
  Results, not a copy of it.

## The work

### 1. One source for the experiments

`site-src/data/experiments.yaml` becomes the only place an experiment is
named. `build.py` gains an include that renders the tiles from it, the way
`map-experiments` is already rendered. The hand-written `<article class="tile">`
blocks in `resources.md` are deleted.

Each entry grows four fields beyond today's `name`/`kind`/`city`/`country`/`note`/`url`:

| field | meaning |
|---|---|
| `role` | what it constrains: `theta13`, `theta12_dm2`, `solar`, `lbl`, `atmospheric`, `mass`, `0nubb`, `sterile` |
| `status` | `running`, `completed`, `construction`, `proposed` |
| `rank` | integer, position within its group |
| `photo` | optional key into `photos.yaml` |

`kind` stays as it is: it picks the marker colour and must keep working.

**The ordering criterion, stated once and applied everywhere:** experiments are
grouped by `role` and ordered within a group by their weight in the current
global fit — the datasets that dominate a constraint come first. The criterion
goes in the YAML header and in a note on the page, so the order is a claim the
reader can check rather than a preference.

Target coverage, roughly 45 entries: reactor θ₁₃ (Daya Bay, RENO, Double Chooz),
reactor θ₁₂/δm² (KamLAND, JUNO), solar (SNO, Super-Kamiokande, Borexino,
Homestake, GALLEX/GNO, SAGE), long-baseline accelerator (T2K, NOvA, MINOS+,
K2K, OPERA, ICARUS), atmospheric (Super-Kamiokande, IceCube/DeepCore,
KM3NeT/ORCA, ANTARES, Kamiokande), absolute mass (KATRIN, Project 8),
0νββ (LEGEND/GERDA, KamLAND-Zen, CUORE/CUPID, nEXO/EXO-200, Majorana
Demonstrator, NEXT, AMoRE, SNO+), short-baseline (MicroBooNE, SBND, ICARUS,
PROSPECT, STEREO, BEST), and the ones still to come (DUNE, Hyper-Kamiokande,
JUNO-TAO, ESSnuSB), each marked by `status` rather than by prose.

**Sourcing rule.** `status` is a factual claim about a real collaboration and
is therefore subject to the project's first rule: every value is taken from a
primary source — the collaboration's own page, or the final-dataset paper —
and the source is recorded in the entry. An experiment whose status cannot be
established is entered as `running` only if its site says so; otherwise the
field is left out and the page prints nothing rather than a guess. Historic
experiments with no live site link their INSPIRE record or the DOI of their
final paper; no URL is invented, and `tools/news/linkcheck.py` sees every one
of them.

### 2. A map that can be navigated

The map stays a self-hosted SVG — no tile server, no external runtime request.
A new `site-src/assets/js/map.js` adds:

- wheel and pinch zoom, drag to pan, `+` / `−` / reset buttons, keyboard
  panning and zooming, and a visible focus ring;
- markers that keep a constant size on screen as the zoom grows, by
  counter-scaling radius and stroke;
- a card on click: name, place, role in the fit, status, link, and the
  photograph when the entry has one;
- legend entries that act as filters by `kind`;
- direct labels for the major sites, appearing as the zoom grows and
  de-overlapped greedily — the same treatment already applied to the curve
  labels in `precision.svg`.

Two substantive fixes to the drawing itself:

- **IceCube goes back on the map.** Today's caption apologises that the South
  Pole falls outside the frame. The projection is extended south instead.
- **Sites hosting several experiments** — Kamioka (Super-Kamiokande, KamLAND,
  T2K far detector, Hyper-Kamiokande), Gran Sasso (Borexino, LEGEND, CUORE,
  OPERA), SNOLAB, Fermilab — collapse to a single marker that fans out on
  click. Without this, a 45-entry map is a pile of overlapping dots.

Degradation without JavaScript: the SVG renders and is readable, with markers
and their `<title>` tooltips; only zoom, filtering and the card are lost.

### 3. Credits that read like credits

In `tools/fetch_commons_images.py`, an author field that names a collaboration
collapses to the collaboration's name; any other field naming more than three
people collapses to the first of them followed by *et al.* The full
field stays in `photos.yaml`, and the link to the file's page on Commons stays
under every photograph, so the attribution the licence requires remains
reachable. The photographs themselves move into the map cards; the
`What they look like` figure and the `gallery` include are removed from
`resources.md`.

### 4. A hero figure that is a result

`tools/make_figures.py` gains a compact `ranges-hero` variant: the six
parameters, best fit with 1σ and 3σ bands, drawn from the same verified Table I
values as `ranges.svg` but proportioned for the hero column and carrying its
own caption with the arXiv identifier. The invented SVG and the words
"Illustrative" and "schematic, not a fit" leave `index.md`. Both figures are
generated from one function so they cannot disagree.

## Verification

Nothing here is declared done by reading it.

- `python3 build.py` runs clean, and the built `resources.html` contains every
  experiment in `experiments.yaml` — a new check in the test suite compares the
  two lists in both directions, so a name can never again exist in one and not
  the other.
- Every `url` in `experiments.yaml` passes `tools/news/linkcheck.py`.
- Every `status` is checked against the source recorded beside it.
- `map.js` is tested under jsdom: zoom limits, pan, filter toggles, card
  opening, fan-out of a shared site, and keyboard reach.
- `tools/tests/test_theme.js` passes on any new colour, in both themes.
- The map and the hero figure are looked at in a real browser, in both themes
  and at a narrow width, before the work is called finished.
- `test_release_numbers.py` is extended to cover the hero figure's values, so
  the home page's figure is verified against the paper like everything else.

## Not in this spec

The wider "better than NuFit" question — what Parameter history, the arXiv
digest, News, Conferences and a possible Methodology page should become — is
its own design. The downloadable Δχ² tables and the JupyterLite notebook are
already published as part of the Bari group release and are not in scope here.
