/* global-nu — the conference map's card.
 *
 * Deliberately small next to map.js: that script owns pan, zoom, a legend
 * and fan-out over forty-odd experiments; this one only ever answers one
 * click with one card — which conference, when, where, and a link out —
 * because tools/news/figures.py draws a flat `<g class="conf-pin">` per
 * marker with no cluster wrapper to reveal. Same conventions as site.js: an
 * IIFE, "use strict", var, no build step, no dependency, and every
 * enhancement guarded so a missing API disables the one thing that needs it
 * rather than taking the rest down. It touches exactly one figure —
 * `.confmap-figure` — and does nothing at all if the page has none, because
 * this file is loaded only by conferences.md but must survive being loaded
 * anywhere else too.
 *
 * The SVG itself (figures.conference_map) is content: every marker carries a
 * <title>, and with this script never running the map still draws and still
 * reads on hover. What follows only adds the card on top of that.
 *
 * The Google Maps link is built from the marker's own data-lat/data-lon, not
 * from data-place: a text search for "Old Trafford" lands in Manchester, not
 * at the stadium's actual coordinates, and the whole point of this map is
 * that every dot on it came from a real (lon, lat) via venue.locate_record —
 * throwing that away for a text query would make the link less precise than
 * the data already on the marker.
 *
 * A marker whose city has a licence-clean, fully-credited photograph
 * (tools/news/photos.py) carries five extra data-photo* attributes; the card
 * renders the image AND its full credit — author, licence, a link to the
 * file's own page on Commons — because a photograph without its credit is a
 * licence violation, not a cosmetic slip. A marker with no such photograph
 * (most conferences: Commons rarely has one, or the record's city could not
 * be established cleanly — see figures.py's _photo_city) simply carries none
 * of the five attributes, and the card renders exactly as it did before this
 * feature existed. Two conferences that share a city (the common case for a
 * fanned, merged marker) carry the identical photo, because photos.for_city
 * caches by city — nothing here needs to special-case a cluster.
 */
(function () {
  "use strict";

  function init() {
    var fig = document.querySelector(".confmap-figure");
    if (!fig) return;
    var svg = fig.querySelector("svg");
    if (!svg) return;
    var pins = svg.querySelectorAll(".conf-pin");
    if (!pins.length) return;

    // The card is positioned against the map, not the whole figure (which
    // also carries a heading above it and a caption below) — so the SVG is
    // wrapped in its own positioning box first, the same idea as map.js's
    // ensureStage, just without anything to zoom or pan.
    var stage = ensureStage(svg);

    wireCard(stage, svg, pins);
    wireTip(fig, stage, pins);
  }

  function ensureStage(svg) {
    var parent = svg.parentElement;
    if (parent && parent.classList.contains("confmap-stage")) return parent;
    var stage = document.createElement("div");
    stage.className = "confmap-stage";
    parent.insertBefore(stage, svg);
    stage.appendChild(svg);
    return stage;
  }

  function gmapsUrl(lat, lon) {
    return "https://www.google.com/maps/search/?api=1&query=" + lat + "," + lon;
  }

  // One entry per <g class="conf-item"> inside a marker — a marker now holds
  // every conference at that venue, not just one (figures.py's _conf_marker).
  // Top-level, not nested in wireCard: the hover panel a later task adds is a
  // sibling function that needs this same reading, and a helper buried inside
  // wireCard would be invisible to it.
  function items(pin) {
    var out = [], els = pin.querySelectorAll(".conf-item"), i;
    for (i = 0; i < els.length; i++) {
      out.push({
        name: els[i].getAttribute("data-name") || "",
        dates: els[i].getAttribute("data-dates") || "",
        url: els[i].getAttribute("data-url") || ""
      });
    }
    return out;
  }

  function wireCard(fig, svg, pins) {
    var current = null;
    // Whatever was focused at the moment the open card was opened — normally
    // the marker itself, reached either by a click (which focuses a
    // tabindex'd element by default) or, for a keyboard user, by Tab landing
    // on it beforehand. Escape and the close button both return focus here.
    var lastFocus = null;

    function remove() {
      if (current && current.parentNode) current.parentNode.removeChild(current);
      current = null;
    }

    function close() {
      if (!current) return;
      remove();
      if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
      lastFocus = null;
    }

    function link(href, text, className) {
      var a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = text;
      if (className) a.className = className;
      return a;
    }

    function photoBlock(pin, photo, name, place) {
      var figure = document.createElement("figure");
      figure.className = "conf-card__photo";

      var img = document.createElement("img");
      img.src = photo;
      img.loading = "lazy";
      img.alt = "Photograph of " + (place || name);
      figure.appendChild(img);

      var credit = document.createElement("figcaption");
      credit.className = "conf-card__credit";
      var author = pin.getAttribute("data-photo-author") || "";
      if (author) credit.appendChild(document.createTextNode(author));
      var lic = pin.getAttribute("data-photo-licence") || "";
      if (lic) {
        if (author) credit.appendChild(document.createTextNode(" · "));
        var licUrl = pin.getAttribute("data-photo-licence-url") || "";
        credit.appendChild(licUrl ? link(licUrl, lic) : document.createTextNode(lic));
      }
      var page = pin.getAttribute("data-photo-page") || "";
      if (page) {
        if (author || lic) credit.appendChild(document.createTextNode(" · "));
        credit.appendChild(link(page, "Wikimedia Commons"));
      }
      figure.appendChild(credit);
      return figure;
    }

    function open(pin) {
      remove();
      lastFocus = document.activeElement;

      // data-place/data-lat/data-lon and the five data-photo* attributes are
      // per VENUE, not per conference — they stay on the pin exactly as
      // before. Only the name, dates and URL moved: they now live one per
      // <g class="conf-item"> child, because a marker can hold several
      // conferences at the same venue (figures.py's _conf_marker).
      var confs = items(pin);
      var place = pin.getAttribute("data-place") || "";
      var lat = pin.getAttribute("data-lat") || "";
      var lon = pin.getAttribute("data-lon") || "";
      var photo = pin.getAttribute("data-photo") || "";

      var names = [], ci;
      for (ci = 0; ci < confs.length; ci++) {
        if (confs[ci].name) names.push(confs[ci].name);
      }

      var card = document.createElement("div");
      card.className = "conf-card";
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-label", names.join("; ") || place);

      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "conf-card__close";
      closeBtn.setAttribute("aria-label", "Close");
      closeBtn.textContent = "×";
      closeBtn.addEventListener("click", close);
      card.appendChild(closeBtn);

      // The place line is shared by every conference on this marker, so it
      // is shown once, ahead of the list rather than repeated per entry —
      // alongside a count ("5 conferences"), because a card capped at
      // 20rem/60vh (see .conf-card in site.css) can scroll past two or
      // three headings of a five-conference marker with nothing else on
      // screen saying there are more. The count is the reader's first
      // signal of that before they ever need to notice the scrollbar.
      var placeBits = [];
      if (place) placeBits.push(place);
      if (confs.length) {
        placeBits.push(confs.length + " conference" + (confs.length === 1 ? "" : "s"));
      }
      if (placeBits.length) {
        var placeMeta = document.createElement("p");
        placeMeta.className = "conf-card__meta";
        placeMeta.textContent = placeBits.join(" · ");
        card.appendChild(placeMeta);
      }

      // A photograph of the host city, when photos.for_city found one — and
      // its credit, which is not decoration: author, licence and a link to
      // the file's own page on Commons are the terms under which the
      // picture may be here at all (see tools/news/photos.py). It is
      // rendered once, here, ABOVE the list built below: this is a
      // photograph of the CITY (photos.for_city caches by city), so every
      // conference on this marker shares the identical image — repeating it
      // per conference would be wrong and would multiply the card's height.
      // Keeping it (and its credit) this close to the top also keeps the
      // credit inside .conf-card's max-height/overflow-y:auto box even when
      // the list below grows long, instead of being pushed past the card's
      // visible bottom edge the way Task 4/the 2026-08-14 fix found it —
      // see tools/tests/test_confcard_credit.py.
      if (photo) card.appendChild(photoBlock(pin, photo, names.join("; ") || place, place));

      // One heading block per conference at this venue — a link when the
      // conference has a URL, plain text when it does not — followed by its
      // own dates. All links here go through link() above, which always
      // sets target="_blank" rel="noopener noreferrer": this whole card is
      // built in script, so build.py's own externalize_links() never gets a
      // chance to add them itself.
      for (ci = 0; ci < confs.length; ci++) {
        var c = confs[ci];
        var h = document.createElement("h4");
        h.className = "conf-card__title";
        if (c.url) {
          h.appendChild(link(c.url, c.name));
        } else {
          h.textContent = c.name;
        }
        card.appendChild(h);

        if (c.dates) {
          var meta = document.createElement("p");
          meta.className = "conf-card__meta";
          meta.textContent = c.dates;
          card.appendChild(meta);
        }
      }

      var actions = document.createElement("div");
      actions.className = "conf-card__actions";
      if (lat && lon) {
        actions.appendChild(link(gmapsUrl(lat, lon), "Open in Google Maps",
          "conf-card__gmaps"));
      }
      if (actions.childNodes.length) card.appendChild(actions);

      fig.appendChild(card);
      current = card;

      // .conf-card--scrollable turns on the fade site.css paints at the
      // bottom of the card (see the rule there) — only when this card's own
      // content actually overflows its box, so a short, single-conference
      // card (still the common case) never shows a "there is more" cue that
      // would be a lie. scrollHeight/clientHeight only report real numbers
      // once the card is in the document with layout run, which is why this
      // reads them here rather than before the appendChild above; jsdom (no
      // layout engine) reports 0 for both, so this is a no-op there, not a
      // false positive.
      if (card.scrollHeight > card.clientHeight) {
        card.classList.add("conf-card--scrollable");
      }

      // A role="dialog" that never receives focus is announced as a dialog
      // but does not behave like one; move focus onto its close button so a
      // keyboard or screen-reader user lands inside it immediately.
      closeBtn.focus();
    }

    // Every marker becomes a keyboard target: informational without JS
    // (readable via its <title> on hover) and only becomes an operable
    // control once this script actually runs.
    for (var pi = 0; pi < pins.length; pi++) {
      var pinEl = pins[pi];
      pinEl.setAttribute("role", "button");
      if (!pinEl.hasAttribute("tabindex")) pinEl.setAttribute("tabindex", "0");
      if (!pinEl.hasAttribute("aria-label")) {
        // data-name lived on the pin itself before a marker could hold more
        // than one conference; now it is only on the .conf-item children,
        // so this reads all of them and joins them "; " — the same
        // separator figures.py already uses for the pin's own <title>.
        var pinConfs = items(pinEl), pinNames = [], pj;
        for (pj = 0; pj < pinConfs.length; pj++) {
          if (pinConfs[pj].name) pinNames.push(pinConfs[pj].name);
        }
        if (pinNames.length) pinEl.setAttribute("aria-label", pinNames.join("; "));
      }
      pinEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
          // "Spacebar" is IE11's legacy key name; harmless to keep alongside
          // " ", the modern one, since browsers only ever send one of them.
          e.preventDefault();
          open(this);
        }
      });
    }

    // Click delegation on the SVG, not one listener per marker: markers never
    // move or get replaced, but this mirrors map.js's own pattern and stays
    // correct if a future revision redraws the SVG in place. No pointer/drag
    // handling here at all — there is nothing to pan, so a plain `click`
    // never needs the setPointerCapture-avoidance map.js's wireInteractions
    // documents at length; that hazard is specific to a draggable surface.
    svg.addEventListener("click", function (e) {
      if (!e.target.closest) return;
      var pin = e.target.closest(".conf-pin");
      if (!pin) return;
      e.stopPropagation();
      open(pin);
    });

    document.addEventListener("click", function (e) {
      if (current && !current.contains(e.target)) close();
    });

    // A minimal Tab trap: while the card is open, Tab and Shift+Tab cycle
    // among its own focusable elements instead of walking out into the rest
    // of the page behind it.
    function trapFocus(e) {
      var focusable = current.querySelectorAll(
        'button, a[href], [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", function (e) {
      if (!current) return;
      if (e.key === "Escape") { close(); return; }
      if (e.key === "Tab") trapFocus(e);
    });
  }

  /* A light panel: the place, then one line per conference with its name
   * and dates. No image, so crossing a crowded Europe loads nothing. The
   * full card, with the photograph, stays on click — two weights of
   * answer for two weights of gesture.
   *
   * `fig` (the .confmap-figure element itself, same as init()'s own `fig`)
   * is what the sizing check below measures room against — see there for
   * why the stage alone is not enough. */
  function wireTip(fig, stage, pins) {
    var tip = document.createElement("div");
    tip.className = "conf-tip";
    tip.hidden = true;
    stage.appendChild(tip);

    function show(pin) {
      var place = pin.getAttribute("data-place") || "";
      var confs = items(pin), i;
      tip.textContent = "";
      tip.style.maxHeight = "";           // drop any earlier marker's clamp
      if (place) {
        var head = document.createElement("b");
        head.textContent = place;
        tip.appendChild(head);
      }
      for (i = 0; i < confs.length; i++) {
        var line = document.createElement("p");
        line.textContent = confs[i].dates
          ? confs[i].name + " · " + confs[i].dates
          : confs[i].name;
        tip.appendChild(line);
      }
      // Default corner first, then check: this map's markers are not
      // uniformly spread (Vancouver, near the map's own top-left, sits
      // right under the panel's default top:.6rem/left:.6rem spot — found
      // by hovering it in a real browser, not by the jsdom suite, which
      // has no layout engine to catch it). getBoundingClientRect is all
      // zero in jsdom, so `overlap` is always false there and this is a
      // no-op for test_confmap.js, same treatment as .conf-card--scrollable
      // above gives its own post-layout measurement.
      tip.hidden = false;
      tip.classList.remove("conf-tip--br");
      var tr = tip.getBoundingClientRect(), pr = pin.getBoundingClientRect();
      var overlap = !(tr.right < pr.left || tr.left > pr.right ||
                       tr.bottom < pr.top || tr.top > pr.bottom);
      if (overlap) tip.classList.add("conf-tip--br");

      // The CSS max-height (min(60vh,20rem), .conf-card's own cap) assumes
      // a figure tall enough to hold it; .confmap-stage is only as tall as
      // the SVG itself (a wide, short map — ~85px at 375px wide), so a
      // crowded marker (Milano: five conferences) can still overflow past
      // the FIGURE's bottom edge even with that cap, because a panel
      // anchored to the stage's top corner isn't limited by the stage's
      // own short height. Verified in a real browser at 375x700, not
      // assumed: the figure includes the caption below the map, so this
      // measures room against `fig`, not `stage`, and only ever tightens
      // the CSS cap, never loosens it — a tall desktop figure leaves this
      // a no-op. fr is all-zero in jsdom, so `room` is 0 there too, and
      // this stays a no-op for test_confmap.js.
      tr = tip.getBoundingClientRect();     // re-measure: the flip may have moved it
      var fr = fig.getBoundingClientRect();
      var room = tip.classList.contains("conf-tip--br")
        ? tr.bottom - fr.top
        : fr.bottom - tr.top;
      if (room > 0) tip.style.maxHeight = Math.max(60, room - 8) + "px";
    }

    function hide() { tip.hidden = true; }

    for (var i = 0; i < pins.length; i++) {
      pins[i].addEventListener("mouseenter", (function (p) {
        // svgzoom.js pans this very SVG by tracking pointermove on the
        // whole document without ever calling setPointerCapture (its own
        // header explains why: capture broke confmap.js's click). Without
        // capture, the browser keeps hit-testing normally during a mouse
        // drag, so panning across the map fires real mouseenter/mouseleave
        // on every marker the pointer sweeps over. Left unguarded, that
        // pops this panel open and shut under the pointer for the whole
        // drag — a nuisance, not a feature. e.buttons is nonzero exactly
        // while a mouse button is held (i.e. mid-drag); it is 0 for an
        // actual, button-up hover, so this only suppresses the drag case.
        // Touch panning is not a concern here: sliding a finger does not
        // synthesize mouseenter on the elements it crosses, only a single
        // pointer/touchmove stream, so there is nothing to sweep-trigger.
        return function (e) { if (!e.buttons) show(p); };
      })(pins[i]));
      pins[i].addEventListener("mouseleave", hide);
      pins[i].addEventListener("focus", (function (p) {
        return function () { show(p); };
      })(pins[i]));
      pins[i].addEventListener("blur", hide);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
