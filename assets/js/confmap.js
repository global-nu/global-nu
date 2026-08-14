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

    function open(pin) {
      remove();
      lastFocus = document.activeElement;

      var name = pin.getAttribute("data-name") || "";
      var place = pin.getAttribute("data-place") || "";
      var dates = pin.getAttribute("data-dates") || "";
      var url = pin.getAttribute("data-url") || "";
      var lat = pin.getAttribute("data-lat") || "";
      var lon = pin.getAttribute("data-lon") || "";

      var card = document.createElement("div");
      card.className = "conf-card";
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-label", name);

      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "conf-card__close";
      closeBtn.setAttribute("aria-label", "Close");
      closeBtn.textContent = "×";
      closeBtn.addEventListener("click", close);
      card.appendChild(closeBtn);

      var h = document.createElement("h4");
      h.className = "conf-card__title";
      if (url) {
        var titleLink = document.createElement("a");
        titleLink.href = url;
        titleLink.target = "_blank";
        titleLink.rel = "noopener noreferrer";
        titleLink.textContent = name;
        h.appendChild(titleLink);
      } else {
        h.textContent = name;
      }
      card.appendChild(h);

      var bits = [];
      if (dates) bits.push(dates);
      if (place) bits.push(place);
      if (bits.length) {
        var meta = document.createElement("p");
        meta.className = "conf-card__meta";
        meta.textContent = bits.join(" · ");
        card.appendChild(meta);
      }

      var actions = document.createElement("div");
      actions.className = "conf-card__actions";
      if (lat && lon) {
        actions.appendChild(link(gmapsUrl(lat, lon), "Open in Google Maps",
          "conf-card__gmaps"));
      }
      if (url) {
        actions.appendChild(link(url, "Conference site", "conf-card__site"));
      }
      if (actions.childNodes.length) card.appendChild(actions);

      fig.appendChild(card);
      current = card;
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
        var pinName = pinEl.getAttribute("data-name");
        if (pinName) pinEl.setAttribute("aria-label", pinName);
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
