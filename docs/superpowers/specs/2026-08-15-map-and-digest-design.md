# The conference map, remade on the model of the home page — and the digest entry

Date: 2026-08-15 · Status: awaiting review

## The problem, stated plainly

Antonio's own site at `home.ba.infn.it/~marrone` has a better conference map
than global-nu's, and a digest entry he prefers. He said so; the screenshots
say why.

Both maps are drawn from the *same* geometry — `tools/news/worldmap.py` is
byte-for-byte identical in the two repositories, 2434 lines of Natural Earth
outline. Everything that separates them is in the drawing:

| | global-nu | home page |
|---|---|---|
| Projection | squashed north–south (`MAP_SCALE_Y = 0.5`), Antarctic smear along the bottom | cropped 82°N–58°S, natural shapes |
| Frame | a card labelled `MAP` with a caption below | full width, no frame |
| Markers | all the same blue, all the same size, each with a halo | two colours with a legend; radius grows with the count; a numbered badge where meetings coincide |
| Zoom | none | +/−/reset, with city names revealed on zoom |

The squash is the worst of it. It exists to keep the figure short, and the
caption apologises for it in prose — *"The map is compressed north-to-south, so
distances and shapes read flatter here"*. The home page achieves the same height
by **cropping** the empty Arctic and the Antarctic band instead of compressing
what is between them. There is no trade-off to arbitrate: cropping gives the same
height on screen *and* the right shapes.

The digest entry is a smaller matter. global-nu prints
`authors · categories · date` as one monospace line with an ISO date and a
separate `arXiv` link row underneath. The home page gives the title the link,
puts the authors and a human date in a proportional face, and shows the arXiv
categories as monospace pills.

## Decisions taken

Antonio decided, on 2026-08-15:

1. **Take the look, keep the behaviour.** The click card built on 2026-08-14 —
   the city photograph, its full credit, the Google Maps link built from the
   marker's real coordinates — stays exactly as it is. Only the drawing changes.
   Adopting the home page's map wholesale would have thrown that away, because
   its map has no per-marker information at all: a DOM query found **one**
   `<title>` on the entire SVG.
2. **Hover is light, click is complete.** Hovering a marker shows a small panel:
   the place, then one line per conference with its name and dates — the three
   fields Antonio asked for, no image, nothing to load. Clicking still opens the
   full card. On touch devices, where hover does not exist, the tap opens the
   full card as it does today, so nothing is lost.
3. **A numbered badge, not a fan.** Where several conferences share a city,
   global-nu currently fans them into separate dots; the home page draws one dot
   with the count on it. The badge wins — it is what makes the home page's map
   legible across a crowded Europe.
4. **The digest changes form, not structure.** Pills, a human date, a linked
   title, more air. The Experimental / Theory split stays: the page's own lede
   promises the reader that experimental and theoretical work are kept apart, and
   that is an editorial choice, not decoration.

## Approaches considered and rejected

**A shared drawing module across the two repositories.** Tempting, since
`worldmap.py` is already identical in both. Rejected: they are two separate git
repositories with no package relationship. That file is identical because it was
copied by hand, and a "shared module" that nothing links is a fiction that comes
apart at the first divergent change.

**Copying the home page's `conference_map` wholesale and re-attaching
global-nu's features.** Same end state as the chosen approach, reached by first
destroying `geocluster.py`'s clustering and the photograph plumbing and then
rebuilding them. Churn with nothing to show for it.

## The map

### Geometry

`MAP_SCALE_Y` and `_map_xy` are deleted. Projection is `worldmap.project`,
unaltered. The crop moves from 84°N/−78°S to **82°N/−58°S**, the home page's
numbers: no conference has ever been held north or south of that, and the
Antarctic band in an equirectangular projection is a smear the width of the world.

The caption's sentence about compression goes with the compression. A caption
that explains a distortion the figure no longer has is worse than no caption.
The rest of the caption — how many of the upcoming meetings are placed, and that
the unplaced ones stay in the list below without a dot rather than getting a
guessed one — is unaffected and stays.

### One marker per venue

`geocluster.cluster_by_distance` stays, and keeps the `MAP_MERGE_DIST` rule, but
now buckets in undistorted pixel space. A cluster draws **one** circle of radius
`3.2 + 1.5 × min(n − 1, 4)`, with the count centred on it when `n > 1`.
`MAP_FAN_R` and the fan-out are removed.

A pin therefore represents N conferences, and the DOM has to carry them. This
codebase already has the pattern: `map.js` reads `.map-exp` children inside a
single experiment pin. So:

```html
<g class="conf-pin" data-fixed="x y" transform="translate(x y)"
   data-place="…" data-lat="…" data-lon="…" data-photo…>
  <title>…every conference at this venue…</title>
  <circle r="…"/>
  <text>3</text>                       <!-- only when n > 1 -->
  <text class="map-name">Naples</text>
  <g class="conf-item" data-name="…" data-dates="…" data-url="…"></g>
  <g class="conf-item" data-name="…" data-dates="…" data-url="…"></g>
</g>
```

`data-lat` / `data-lon` remain the venue's real coordinates, as today — the
Google Maps link is only as honest as the numbers behind it. The five
`data-photo*` attributes stay on the pin, where they already belong: they are
per city, and `photos.for_city` caches by city, so a shared marker needs no
special case.

### Colour

Colour follows the split the page already makes — neutrino conferences and
general particle physics — with a legend, because two unexplained colours are a
puzzle.

**Amber is not available.** On this page amber already means *in progress right
now*, and giving it a second meaning as a category would collide with a state
the reader is being asked to read off the same figure. That state colour was the
subject of a bug fixed on 2026-08-14 and must not be muddied now.

So: neutrino keeps `--no` (the blue the pins already are) and general particle
physics takes the purple `--dec-4`, which is defined in both themes — `#8c63c9`
dark, `#6d28d9` light.

The count inside the badge is the pair most at risk here, because it is text on
a saturated fill. It takes `--on-accent`, which already flips between the themes
(`#06121c` dark, `#ffffff` light) — but that token was chosen to sit on
`--accent`, not on these two, so the four resulting combinations are measured
rather than assumed. All of it goes through `tools/tests/test_theme.js`, which
already checks every colour pair on the site for WCAG contrast in both themes.
No colour here is chosen by eye.

### Zoom, and the city names

`svgzoom.js` is ported from the home page unchanged. It is already generic: it
drives any `svg[data-zoomable]` by its viewBox alone and counter-scales every
`[data-fixed]` group, which is exactly the marker structure above.

It is **not** `map.js` generalised. `figure.js` already argues the case in its
own header — duplicating one clamp and one transform string costs less than
coupling a working, tested interaction to a second caller — and that reasoning
applies here unchanged. `figure.js` also deliberately excludes both maps from
its lightbox, because each already answers a click with its own card; that
exclusion stays.

Every marker carries its city name, hidden by CSS until the map is zoomed. At
rest, thirty-odd labels collide; the CSS-only default means that with JavaScript
disabled the labels simply stay visible, which is the right fallback.

### The hover panel

New in `confmap.js`. `mouseenter` on a `.conf-pin` opens a small panel — the
place, then one line per `.conf-item` with its name and dates. `mouseleave`
closes it. It opens on **keyboard focus** as well: the pins are already
clickable, and a control reachable by mouse but not by keyboard is a defect, not
a limitation.

No image goes in it, so hovering loads nothing. The full card, with the
photograph, stays on click.

## The digest entry

`render._digest_list` produces, today:

```html
<li><b>title</b><span>authors · cats · date</span><span class="cites">arXiv</span></li>
```

It becomes: the **title carries the arXiv link**; below it `authors · 13 Aug 2026`
in the proportional face; below that the arXiv categories as monospace pills, one
`<span class="tag">` each.

Two things are deliberately left alone:

- **The `.cites` row is not blindly deleted.** `_links_row` does not emit only
  arXiv — for a preprint already published it can carry a DOI and a journal. The
  row disappears **only when the sole link it held was the arXiv one**, now in
  the title, and survives when it still has something to say.
- **The three-category cap stays.** How many categories a reader sees is content,
  not form, and this change is about form.

## Files

| File | Change |
|---|---|
| `tools/news/figures.py` | `conference_map`, `_conf_pin`, the map constants |
| `tools/news/render.py` | `_digest_list`, and the map caption |
| `site-src/assets/js/svgzoom.js` | new, ported from the home page |
| `site-src/assets/js/confmap.js` | the hover panel; the card lists N conferences |
| `site-src/assets/css/site.css` | pills, entry spacing, `.map-name` hidden until zoom, the hover panel |

## Testing

`tools/tests/test_confmap.js` and `tools/tests/test_confcard_credit.py` already
exist and are extended: the card now lists several conferences under one
photograph, and the credit must still sit inside the card's lower edge — the
thing that was fixed on 2026-08-14 and is the easiest to break here.

New checks:

- one marker per venue, not per conference
- the number in the badge equals the count of `.conf-item` children
- every `.conf-item` carries a name, dates and a URL
- a digest entry's title is a link, and its categories are pills
- the two category colours clear WCAG contrast in both themes (`test_theme.js`)

And then the built page is **looked at**, with Playwright, at 375, 700 and
1280 px in both themes. On this project, opening the page in a browser keeps
finding things that green tests do not.

## Out of scope

- The experiments world map and `map.js`. Untouched.
- `figure.js`'s exclusion of both maps from the lightbox. Unchanged.
- The conference list, the timeline, and the sources feeding them.
- The Experimental / Theory split on the digest, and the ranking behind it.
