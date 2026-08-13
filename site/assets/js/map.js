/* global-nu — the world map: zoom, pan, filter, a card on click.
 *
 * Deliberately small and dependency-free, like site.js. It touches exactly
 * one figure — `.map-figure` — and does nothing at all if the page has none,
 * because this script is loaded only by Resources but must survive being
 * loaded anywhere else too.
 *
 * The SVG itself (tools/make_map.py) is content: every marker carries a
 * <title>, and with this script never running the map still draws and still
 * reads on hover. What follows only adds interaction on top of that, and
 * every enhancement is feature-detected so a missing API disables the one
 * thing that needs it rather than throwing and taking the rest down.
 *
 * Zoom lives on `.map-layer`, a <g> wrapping everything the SVG drew
 * (wrapped here if make_map.py did not already provide one, which lets this
 * file also run against a hand-written test fixture). Each `.map-pin` then
 * counter-scales by 1/s around its OWN anchor point — the centre of its
 * first <circle> — so panning and zooming still carries a marker to the
 * right place on the map while its drawn size never changes on screen; a
 * bare `scale(1/s)` with no such anchor would cancel the marker's motion
 * along with its growth, leaving every dot pinned to the pan offset instead
 * of following the coastline under it.
 */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var MIN_S = 1;
  var MAX_S = 8;
  var ZOOM_STEP = 1.4;

  function init() {
    var fig = document.querySelector(".map-figure");
    if (!fig) return;
    var svg = fig.querySelector("svg");
    if (!svg) return;

    // The toolbar and the card overlay the SVG itself, not the whole
    // figure — which also carries a heading above it and the legend below.
    // Anchoring them to the figure would float them over that text instead
    // of the map, so the SVG is wrapped in its own positioning box first.
    var stage = ensureStage(svg);

    var box = parseViewBox(svg);
    var layer = ensureLayer(svg);
    var pins = collectPins(layer);

    var s = 1, tx = 0, ty = 0;

    function clampPan() {
      // Content overflows by (s-1)*half-extent around the centre as it
      // zooms; allow a little further so the frame's own edges can be
      // dragged into view, but not so far the map can be lost entirely.
      var maxX = (s - 1) * box.w / 2 + box.w * 0.4;
      var maxY = (s - 1) * box.h / 2 + box.h * 0.4;
      tx = Math.max(-maxX, Math.min(maxX, tx));
      ty = Math.max(-maxY, Math.min(maxY, ty));
    }

    function render() {
      layer.setAttribute("transform",
        "translate(" + tx + "," + ty + ") scale(" + s + ")");
      var inv = 1 / s;
      for (var i = 0; i < pins.length; i++) {
        var p = pins[i];
        var pre = p.base ? p.base + " " : "";
        p.el.setAttribute("transform",
          pre + "translate(" + p.px + "," + p.py + ") scale(" + inv + ") " +
          "translate(" + (-p.px) + "," + (-p.py) + ")");
      }
    }

    function zoomAt(factor, fx, fy) {
      var next = Math.max(MIN_S, Math.min(MAX_S, s * factor));
      if (next === s) return;
      // Keep the SVG-space point (fx,fy) fixed on screen: solve tx,ty so the
      // point maps to the same place under the new scale as under the old.
      tx += fx * (s - next);
      ty += fy * (s - next);
      s = next;
      clampPan();
      render();
    }

    function centre() { return [box.x + box.w / 2, box.y + box.h / 2]; }

    function reset() { s = 1; tx = 0; ty = 0; render(); }

    render();
    buildControls(stage, zoomAt, centre, reset);
    wireLegend(fig, pins);
    var drag = { justDragged: false };
    wireInteractions(svg, zoomAt, centre, function (dx, dy) {
      tx += dx; ty += dy; clampPan(); render();
    }, drag);
    wireCard(stage, svg, pins, drag);
  }

  /* -------------------------------------------------------------- setup -- */

  function parseViewBox(svg) {
    var raw = (svg.getAttribute("viewBox") || "0 0 100 100").split(/\s+/);
    var x = parseFloat(raw[0]), y = parseFloat(raw[1]);
    var w = parseFloat(raw[2]), h = parseFloat(raw[3]);
    if (!isFinite(w) || !w) w = 100;
    if (!isFinite(h) || !h) h = 100;
    return { x: x || 0, y: y || 0, w: w, h: h };
  }

  function directChild(el, cls) {
    for (var i = 0; i < el.children.length; i++) {
      if (el.children[i].classList.contains(cls)) return el.children[i];
    }
    return null;
  }

  /* A div sized to exactly the SVG's own rendered box, wrapped around it so
     the toolbar and the card can be positioned against the map and nothing
     else on the page. Idempotent, like ensureLayer. */
  function ensureStage(svg) {
    var parent = svg.parentElement;
    if (parent && parent.classList.contains("map-stage")) return parent;
    var stage = document.createElement("div");
    stage.className = "map-stage";
    parent.insertBefore(stage, svg);
    stage.appendChild(svg);
    return stage;
  }

  /* Everything the SVG already drew — land, pins, the polar inset — moves
     into one <g class="map-layer">, so a single transform zooms and pans
     all of it together. Idempotent: a fixture (or a re-run) that already
     provides the wrapper is left alone. */
  function ensureLayer(svg) {
    var existing = directChild(svg, "map-layer");
    if (existing) return existing;
    var layer = document.createElementNS(SVGNS, "g");
    layer.setAttribute("class", "map-layer");
    var kids = [];
    for (var i = 0; i < svg.children.length; i++) {
      if (svg.children[i].tagName.toLowerCase() !== "title") kids.push(svg.children[i]);
    }
    for (var j = 0; j < kids.length; j++) layer.appendChild(kids[j]);
    svg.appendChild(layer);
    return layer;
  }

  /* One record per marker: its element, whatever transform it already
     carried (a fixture may supply one; make_map.py's own output does not),
     and the anchor point every later zoom pivots around — the centre of its
     first <circle>, which for a single marker is the dot itself and for a
     fanned one is the cluster badge, wherever no circle exists at all
     (an empty test fixture) the anchor simply falls back to the origin. */
  function collectPins(layer) {
    var els = layer.querySelectorAll(".map-pin");
    var out = [];
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var c = el.querySelector("circle");
      var px = c ? parseFloat(c.getAttribute("cx")) : 0;
      var py = c ? parseFloat(c.getAttribute("cy")) : 0;
      out.push({
        el: el,
        base: el.getAttribute("transform") || "",
        px: isFinite(px) ? px : 0,
        py: isFinite(py) ? py : 0
      });
    }
    return out;
  }

  /* ---------------------------------------------------------- controls -- */

  function buildControls(fig, zoomAt, centre, reset) {
    var ctl = document.createElement("div");
    ctl.className = "map-ctl";

    function button(label, title, action) {
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-zoom", label);
      b.setAttribute("aria-label", title);
      b.textContent = label === "in" ? "+" : label === "out" ? "−" : "↻";
      b.addEventListener("click", action);
      ctl.appendChild(b);
      return b;
    }

    button("in", "Zoom in", function () {
      var c = centre();
      zoomAt(ZOOM_STEP, c[0], c[1]);
    });
    button("out", "Zoom out", function () {
      var c = centre();
      zoomAt(1 / ZOOM_STEP, c[0], c[1]);
    });
    button("reset", "Reset view", reset);

    fig.appendChild(ctl);
  }

  /* -------------------------------------------------------------- pan/zoom -- */

  function wireInteractions(svg, zoomAt, centre, pan, drag) {
    svg.setAttribute("tabindex", "0");

    svg.addEventListener("wheel", function (e) {
      e.preventDefault();
      var pt = screenToSvg(svg, e.clientX, e.clientY) || centre();
      var factor = Math.pow(1.0015, -e.deltaY);
      zoomAt(factor, pt[0], pt[1]);
    }, { passive: false });

    svg.addEventListener("keydown", function (e) {
      var step = 24; // viewBox units per key press, independent of zoom
      switch (e.key) {
        case "ArrowLeft": pan(step, 0); break;
        case "ArrowRight": pan(-step, 0); break;
        case "ArrowUp": pan(0, step); break;
        case "ArrowDown": pan(0, -step); break;
        case "+": case "=": zoomAt(ZOOM_STEP, centre()[0], centre()[1]); break;
        case "-": case "_": zoomAt(1 / ZOOM_STEP, centre()[0], centre()[1]); break;
        default: return;
      }
      e.preventDefault();
    });

    // Pointer drag to pan, and pinch (two pointers) to zoom. Guarded behind
    // PointerEvent: without it the map is still fully usable via wheel,
    // keyboard and the toolbar, just not draggable with a finger or mouse.
    if (!window.PointerEvent) return;

    // move/up listen on `document`, not `svg`, and neither ever calls
    // setPointerCapture: capturing the pointer on the SVG redirects the
    // browser's own mouseup target to the capturing element, which is
    // exactly what stops mousedown and mouseup from agreeing on a target —
    // and a plain, undragged click never synthesizes a `click` event
    // without that agreement. A version of this file that called
    // setPointerCapture here shipped a map where no marker could be opened
    // by a real click, only by a synthetic one, which is how a jsdom test
    // dispatching `new Event('click')` passed while every real click failed.
    var active = {};
    var lastDist = null;
    var DRAG_PX = 6; // real clicks jitter a pixel or two; a drag moves further

    function ids() { return Object.keys(active); }

    function midAndDist() {
      var pts = ids().map(function (k) { return active[k]; });
      if (pts.length < 2) return null;
      var mx = (pts[0].x + pts[1].x) / 2, my = (pts[0].y + pts[1].y) / 2;
      var d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      return { mx: mx, my: my, d: d };
    }

    svg.addEventListener("pointerdown", function (e) {
      active[e.pointerId] = { x: e.clientX, y: e.clientY, moved: 0 };
      drag.justDragged = false;
      svg.style.cursor = "grabbing";
      var md = midAndDist();
      if (md) lastDist = md.d;
    });

    document.addEventListener("pointermove", function (e) {
      if (!active[e.pointerId]) return;
      var prev = active[e.pointerId];
      var dxCss = e.clientX - prev.x, dyCss = e.clientY - prev.y;
      active[e.pointerId] = { x: e.clientX, y: e.clientY, moved: prev.moved + Math.hypot(dxCss, dyCss) };

      if (ids().length >= 2) {
        var md = midAndDist();
        if (md && lastDist && md.d > 0) {
          var pt = screenToSvg(svg, md.mx, md.my) || centre();
          zoomAt(md.d / lastDist, pt[0], pt[1]);
        }
        lastDist = md ? md.d : lastDist;
        return;
      }

      var rect = svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
      if (!rect || !rect.width || !rect.height) return;
      var box = parseViewBox(svg);
      var k = box.w / rect.width; // viewBox units per CSS pixel
      pan(dxCss * k, dyCss * k);
    });

    function endPointer(e) {
      var p = active[e.pointerId];
      if (p && p.moved > DRAG_PX) drag.justDragged = true;
      delete active[e.pointerId];
      if (ids().length < 2) lastDist = null;
      if (!ids().length) svg.style.cursor = "";
    }
    document.addEventListener("pointerup", endPointer);
    document.addEventListener("pointercancel", endPointer);
  }

  function screenToSvg(svg, clientX, clientY) {
    try {
      if (!svg.createSVGPoint || !svg.getScreenCTM) return null;
      var ctm = svg.getScreenCTM();
      if (!ctm) return null;
      var pt = svg.createSVGPoint();
      pt.x = clientX; pt.y = clientY;
      var p = pt.matrixTransform(ctm.inverse());
      return [p.x, p.y];
    } catch (e) {
      return null;
    }
  }

  /* ---------------------------------------------------------------- filter -- */

  function wireLegend(fig, pins) {
    var entries = fig.querySelectorAll("[data-filter]");
    if (!entries.length) return;
    var enabled = {};

    function apply() {
      for (var i = 0; i < pins.length; i++) {
        var kinds = (pins[i].el.getAttribute("data-kinds") || "").split(/\s+/);
        var show = false;
        for (var k = 0; k < kinds.length; k++) {
          if (enabled[kinds[k]] !== false) { show = true; break; }
        }
        if (show) pins[i].el.removeAttribute("hidden");
        else pins[i].el.setAttribute("hidden", "");
      }
    }

    function toggle(entry) {
      var kind = entry.getAttribute("data-filter");
      enabled[kind] = enabled[kind] === false;
      entry.setAttribute("aria-pressed", enabled[kind] ? "true" : "false");
      apply();
    }

    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      enabled[entry.getAttribute("data-filter")] = true;
      entry.setAttribute("role", "button");
      if (!entry.hasAttribute("tabindex")) entry.tabIndex = 0;
      entry.setAttribute("aria-pressed", "true");
      entry.addEventListener("click", function () { toggle(this); });
      entry.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(this); }
      });
    }
  }

  /* ------------------------------------------------------------------ card -- */

  function wireCard(fig, svg, pins, drag) {
    var current = null;
    // The element focus returns to when the card closes: whatever was
    // focused at the moment THIS card opened, normally the marker itself —
    // reached either by a mouse click (which focuses a tabindex'd element by
    // default) or, for a keyboard user, by Tab landing on it beforehand.
    var lastFocus = null;

    // Removes the DOM without touching focus, so open() can clear a
    // previously-open card before showing a new one without a focus flicker
    // back to whatever opened the old one.
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

    function reveal(pin) {
      var kids = pin.querySelectorAll(".map-exp");
      for (var i = 0; i < kids.length; i++) kids[i].removeAttribute("hidden");
    }

    function expBlock(exp) {
      var wrap = document.createElement("div");
      wrap.className = "map-card__exp";

      var name = document.createElement("p");
      name.className = "map-card__name";
      var url = exp.getAttribute("data-url");
      var label = exp.getAttribute("data-experiment") || "";
      if (url) {
        var a = document.createElement("a");
        a.href = url; a.target = "_blank"; a.rel = "noopener";
        a.textContent = label;
        name.appendChild(a);
      } else {
        name.textContent = label;
      }
      wrap.appendChild(name);

      var bits = [];
      var place = exp.getAttribute("data-place");
      var kindLabel = exp.getAttribute("data-kind-label");
      var status = exp.getAttribute("data-status");
      if (place) bits.push(place);
      if (kindLabel) bits.push(kindLabel);
      if (status) bits.push(status);
      if (bits.length) {
        var meta = document.createElement("p");
        meta.className = "map-card__meta";
        meta.textContent = bits.join(" · ");
        wrap.appendChild(meta);
      }

      var note = exp.getAttribute("data-note");
      if (note) {
        var noteP = document.createElement("p");
        noteP.className = "map-card__note";
        noteP.textContent = note;
        wrap.appendChild(noteP);
      }

      var photo = exp.getAttribute("data-photo");
      if (photo) wrap.appendChild(photoBlock(exp, photo));

      return wrap;
    }

    function photoBlock(exp, photo) {
      var figure = document.createElement("figure");
      figure.className = "map-card__photo";

      var img = document.createElement("img");
      img.src = photo;
      img.loading = "lazy";
      img.alt = exp.getAttribute("data-photo-alt") || "";
      figure.appendChild(img);

      // The credit is not decoration: author, licence and a link to the
      // file's own page on Commons are the terms under which the picture
      // may be here at all, so they move to the card with it rather than
      // being left behind with the gallery that used to hold them.
      var credit = document.createElement("figcaption");
      credit.className = "map-card__credit";
      var author = exp.getAttribute("data-photo-author");
      if (author) credit.appendChild(document.createTextNode(author + " · "));
      var lic = exp.getAttribute("data-photo-licence");
      if (lic) {
        var licUrl = exp.getAttribute("data-photo-licence-url");
        if (licUrl) {
          var la = document.createElement("a");
          la.href = licUrl; la.textContent = lic;
          credit.appendChild(la);
        } else {
          credit.appendChild(document.createTextNode(lic));
        }
      }
      var page = exp.getAttribute("data-photo-page");
      if (page) {
        credit.appendChild(document.createTextNode(" · "));
        var pa = document.createElement("a");
        pa.href = page; pa.textContent = "Wikimedia Commons";
        credit.appendChild(pa);
      }
      figure.appendChild(credit);
      return figure;
    }

    function open(pin) {
      remove();
      lastFocus = document.activeElement;
      var names = (pin.getAttribute("data-names") || "").split("|");
      var exps = pin.querySelectorAll(".map-exp");

      var card = document.createElement("div");
      card.className = "map-card";
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-label", names.join(", "));

      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "map-card__close";
      closeBtn.setAttribute("aria-label", "Close");
      closeBtn.textContent = "×";
      closeBtn.addEventListener("click", close);
      card.appendChild(closeBtn);

      var h = document.createElement("h4");
      h.className = "map-card__title";
      h.textContent = names.length > 1 ?
        (names.length + " experiments here") : (names[0] || "");
      card.appendChild(h);

      for (var i = 0; i < exps.length; i++) card.appendChild(expBlock(exps[i]));

      fig.appendChild(card);
      current = card;
      // A role="dialog" that never receives focus is announced as a dialog
      // but does not behave like one; move focus onto its close button so a
      // keyboard or screen-reader user lands inside it immediately, the same
      // place Escape or the button itself will send an activation back out
      // through close()'s focus restoration above.
      closeBtn.focus();
    }

    function activate(pin) {
      if (pin.hasAttribute("data-fan")) reveal(pin);
      open(pin);
    }

    // Every marker becomes a keyboard target, mirroring the pattern
    // wireLegend already uses for the legend entries: a marker is
    // informational without JS (readable via its <title> on hover) and only
    // becomes an operable control once this script actually runs, so the
    // role/tabindex/keydown wiring belongs here rather than in make_map.py's
    // static markup.
    for (var pi = 0; pi < pins.length; pi++) {
      var pinEl = pins[pi].el;
      pinEl.setAttribute("role", "button");
      if (!pinEl.hasAttribute("tabindex")) pinEl.setAttribute("tabindex", "0");
      if (!pinEl.hasAttribute("aria-label")) {
        var pinNames = (pinEl.getAttribute("data-names") || "").split("|").join(", ");
        if (pinNames) pinEl.setAttribute("aria-label", pinNames);
      }
      pinEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
          // "Spacebar" is IE11's legacy key name; harmless to keep alongside
          // " ", the modern one, since browsers only ever send one of them.
          e.preventDefault();
          activate(this);
        }
      });
    }

    svg.addEventListener("click", function (e) {
      // A drag that ends over a marker still fires a native click at
      // release; without this check, panning across a marker would pop its
      // card open as an unwanted side effect of the gesture.
      if (drag && drag.justDragged) { drag.justDragged = false; return; }
      if (!e.target.closest) return;
      var pin = e.target.closest(".map-pin");
      if (!pin) return;
      e.stopPropagation();
      activate(pin);
    });

    document.addEventListener("click", function (e) {
      if (current && !current.contains(e.target)) close();
    });

    // A minimal Tab trap: while the card is open, Tab and Shift+Tab cycle
    // among its own focusable elements (the close button, and any
    // experiment-name or credit links) instead of walking out into the rest
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
