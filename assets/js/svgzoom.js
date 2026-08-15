/* global-nu — pan & zoom for inline SVGs marked data-zoomable, by viewBox
 * alone.
 *
 * Ported unchanged from Antonio's home page, which is where this behaviour
 * was written and proven. Not map.js generalised: figure.js already argues
 * the case in its own header — duplicating one clamp and one transform
 * string costs less than coupling a working, tested interaction to a second
 * caller — and that reasoning applies here without modification. map.js
 * still owns the experiments map, and figure.js still excludes both maps
 * from its lightbox, because each already answers a click with its own card.
 *
 * No transforms, no dependencies. Wheel zoom requires Ctrl (or a trackpad
 * pinch, which macOS reports as ctrl+wheel) so plain scrolling over the
 * figure keeps scrolling the page; on touch, one finger scrolls the page
 * until the figure is actually zoomed in, then it pans.
 */
(function () {
  "use strict";

  var MAX = 8;                       // maximum magnification
  var STEP = 1.5;                    // per button press / dblclick

  function attach(svg) {
    var vb = (svg.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(isNaN)) return;
    var x0 = vb[0], y0 = vb[1], w0 = vb[2], h0 = vb[3];
    var x = x0, y = y0, w = w0, h = h0;

    var wrap = document.createElement("div");
    wrap.className = "svgzoom";
    svg.parentNode.insertBefore(wrap, svg);
    wrap.appendChild(svg);

    var bar = document.createElement("div");
    bar.className = "svgzoom__bar";
    var bIn = btn("+", "Zoom in"), bOut = btn("−", "Zoom out"),
        bRst = btn("↺", "Reset zoom");
    bar.appendChild(bIn); bar.appendChild(bOut); bar.appendChild(bRst);
    wrap.appendChild(bar);

    function btn(label, title) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "svgzoom__btn";
      b.textContent = label;
      b.setAttribute("aria-label", title);
      b.title = title;
      return b;
    }

    var fixed = svg.querySelectorAll("[data-fixed]");

    function apply() {
      svg.setAttribute("viewBox", x + " " + y + " " + w + " " + h);
      // Counter-scale the marker groups so they keep their on-screen size:
      // zooming the map in would otherwise blow clustered dots up into one
      // blob. data-fixed holds the group's anchor as "x y".
      var f = w / w0;
      for (var i = 0; i < fixed.length; i++) {
        fixed[i].setAttribute("transform", "translate(" +
          fixed[i].getAttribute("data-fixed") + ") scale(" + f + ")");
      }
      var zoomed = w < w0 - 0.5;
      wrap.classList.toggle("svgzoom--zoomed", zoomed);
      // While zoomed a single touch finger pans the map, so the browser must
      // not claim it for page scrolling; at rest give the finger back.
      svg.style.touchAction = zoomed ? "none" : "pan-y";
      bRst.disabled = bOut.disabled = !zoomed;
      bIn.disabled = w0 / w >= MAX - 0.01;
    }

    function clamp() {
      w = Math.min(w0, Math.max(w0 / MAX, w));
      h = w * h0 / w0;
      x = Math.min(x0 + w0 - w, Math.max(x0, x));
      y = Math.min(y0 + h0 - h, Math.max(y0, y));
    }

    // (px,py) is the zoom anchor in current SVG units.
    function zoomAt(factor, px, py) {
      var nw = w / factor;
      x += (px - x) * (1 - nw / w);
      y += (py - y) * (1 - nw / w);
      w = nw;
      clamp(); apply();
    }

    function svgPoint(ev) {
      var r = svg.getBoundingClientRect();
      return { px: x + (ev.clientX - r.left) / r.width * w,
               py: y + (ev.clientY - r.top) / r.height * h };
    }

    function center() { return { px: x + w / 2, py: y + h / 2 }; }

    bIn.addEventListener("click", function () {
      var c = center(); zoomAt(STEP, c.px, c.py);
    });
    bOut.addEventListener("click", function () {
      var c = center(); zoomAt(1 / STEP, c.px, c.py);
    });
    bRst.addEventListener("click", function () {
      x = x0; y = y0; w = w0; h = h0; apply();
    });

    svg.addEventListener("dblclick", function (ev) {
      ev.preventDefault();
      if (w < w0 - 0.5) { x = x0; y = y0; w = w0; h = h0; apply(); }
      else { var p = svgPoint(ev); zoomAt(STEP * STEP, p.px, p.py); }
    });

    svg.addEventListener("wheel", function (ev) {
      if (!ev.ctrlKey) return;           // plain wheel keeps scrolling the page
      ev.preventDefault();
      var p = svgPoint(ev);
      zoomAt(Math.pow(1.0015, -ev.deltaY), p.px, p.py);
    }, { passive: false });

    // One pointer pans (when zoomed); two pointers pinch. Pointer events
    // cover mouse and touch alike.
    //
    // This block is not the unmodified port: the home page's original
    // called svg.setPointerCapture(ev.pointerId) here, which is harmless on
    // that page (nothing else listens for a click on that SVG) but breaks
    // this one. confmap.js answers a click on this very SVG with its own
    // card, and capturing the pointer redirects the browser's own mouseup
    // target away from wherever the finger actually lifts — which stops
    // mousedown and mouseup from agreeing on a target, and a plain,
    // undragged click never synthesizes a `click` event without that
    // agreement. Verified in a real browser (Playwright/Chromium): with
    // setPointerCapture in place, clicking a marker never opened its card,
    // not even without a drag. map.js hit the identical bug on the
    // experiments map and its own wireInteractions documents the fix at
    // length: don't capture, listen for move/up on `document` instead of
    // the SVG so a drag is still tracked once the pointer leaves it, and
    // track how far each pointer actually travelled so a real pan can
    // suppress the click it would otherwise also deliver.
    var pointers = {};                   // id -> {cx, cy, moved}
    var pinch0 = 0;                      // finger distance when pinch began
    var DRAG_PX = 6;                     // real clicks jitter a pixel or two
    var justPanned = false;              // set by a real pan, consumed once below

    function dist() {
      var ids = Object.keys(pointers);
      var a = pointers[ids[0]], b = pointers[ids[1]];
      return Math.hypot(a.cx - b.cx, a.cy - b.cy) || 1;
    }

    svg.addEventListener("pointerdown", function (ev) {
      pointers[ev.pointerId] = { cx: ev.clientX, cy: ev.clientY, moved: 0 };
      if (Object.keys(pointers).length === 2) pinch0 = dist();
    });

    document.addEventListener("pointermove", function (ev) {
      var p = pointers[ev.pointerId];
      if (!p) return;
      var ids = Object.keys(pointers);
      if (ids.length === 1 && w < w0 - 0.5) {
        var r = svg.getBoundingClientRect();
        var dx = ev.clientX - p.cx, dy = ev.clientY - p.cy;
        x -= dx / r.width * w;
        y -= dy / r.height * h;
        p.moved += Math.hypot(dx, dy);
        clamp(); apply();
        ev.preventDefault();
      }
      p.cx = ev.clientX; p.cy = ev.clientY;
      if (ids.length === 2) {
        var d = dist();
        var a = pointers[ids[0]], b = pointers[ids[1]];
        var mid = { clientX: (a.cx + b.cx) / 2, clientY: (a.cy + b.cy) / 2 };
        var m = svgPoint(mid);
        zoomAt(d / pinch0, m.px, m.py);
        pinch0 = d;
        ev.preventDefault();
      }
    });

    function lift(ev) {
      var p = pointers[ev.pointerId];
      if (p && p.moved > DRAG_PX) justPanned = true;
      delete pointers[ev.pointerId];
      if (Object.keys(pointers).length === 2) pinch0 = dist();
    }
    document.addEventListener("pointerup", lift);
    document.addEventListener("pointercancel", lift);

    // Capture phase, so this runs before the event ever reaches a marker —
    // and before confmap.js's own (bubble-phase) click listener on this same
    // svg, wherever it sits in script-load order. A drag that ends over a
    // marker still fires a native click at release; without this, panning
    // across a marker would pop its card open as an unwanted side effect of
    // the gesture, the same hazard map.js's wireCard guards against with its
    // drag.justDragged flag.
    svg.addEventListener("click", function (ev) {
      if (justPanned) { justPanned = false; ev.stopPropagation(); }
    }, true);

    apply();
  }

  function init() {
    var list = document.querySelectorAll("svg[data-zoomable]");
    for (var i = 0; i < list.length; i++) attach(list[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
