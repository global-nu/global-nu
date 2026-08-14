/* global-nu — open a figure at full size.
 *
 * The comparison panels are drawn at 520x250 and sit two to a row: on a laptop
 * a marker is a few pixels across and the year labels are at the limit of
 * legibility. They are vector, so nothing is lost by showing them large — the
 * only thing missing was a way to ask.
 *
 * Same conventions as site.js: an IIFE, "use strict", var, no build step, no
 * dependency, and every enhancement guarded so a missing API disables it rather
 * than taking the page down with it. With this script never running, every
 * figure still draws exactly as before; this only adds a way to enlarge one.
 *
 * The world map, and the conference map beside it, are deliberately excluded.
 * Each already answers a click by opening its own card, and two meanings for
 * one click means one of them loses.
 *
 * On the zoom arithmetic being similar to map.js's: that is deliberate, not an
 * oversight. Sharing it would mean refactoring the map's working, tested
 * interaction to serve a simpler case — this one has no markers to counter-
 * scale, no kinds to filter and no sites to fan out. The duplication is one
 * clamp and one transform string, and it is cheaper than the coupling.
 */
(function () {
  "use strict";

  var MIN = 1, MAX = 8, STEP = 1.5;

  /* A figure worth opening holds a drawing. A caption on its own does not. */
  function drawingIn(fig) {
    return fig.querySelector("svg, img");
  }

  /* What a screen reader hears before activating it. */
  function nameOf(fig) {
    var head = fig.querySelector("h3, h4");
    var svg = fig.querySelector("svg");
    var text = (head && head.textContent) ||
               (svg && svg.getAttribute("aria-label")) ||
               (fig.querySelector(".cap") || {}).textContent || "figure";
    return "Enlarge: " + text.replace(/\s+/g, " ").trim();
  }

  function open(fig) {
    var opener = fig;
    var scale = 1, tx = 0, ty = 0;

    var box = document.createElement("div");
    box.className = "figbox";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", nameOf(fig).replace(/^Enlarge: /, ""));

    var bar = document.createElement("div");
    bar.className = "figbox__bar";
    ["in", "out", "reset"].forEach(function (kind) {
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-zoom", kind);
      b.textContent = kind === "in" ? "+" : kind === "out" ? "−" : "⟲";
      b.setAttribute("aria-label",
        kind === "in" ? "Zoom in" : kind === "out" ? "Zoom out" : "Reset the view");
      bar.appendChild(b);
    });
    var close = document.createElement("button");
    close.type = "button";
    close.className = "figbox__close";
    close.textContent = "✕";
    close.setAttribute("aria-label", "Close");
    bar.appendChild(close);

    var frame = document.createElement("div");
    frame.className = "figbox__frame";
    var stage = document.createElement("div");
    stage.className = "figbox__stage";

    /* A copy, so closing cannot disturb the figure on the page. */
    var art = drawingIn(fig).cloneNode(true);
    art.removeAttribute("width");
    art.removeAttribute("height");
    stage.appendChild(art);
    frame.appendChild(stage);

    box.appendChild(bar);
    box.appendChild(frame);

    var cap = fig.querySelector(".cap");
    var head = fig.querySelector("h3, h4");
    if (head || cap) {
      var foot = document.createElement("div");
      foot.className = "figbox__cap";
      if (head) {
        var h = document.createElement("b");
        h.textContent = head.textContent.replace(/\s+/g, " ").trim();
        foot.appendChild(h);
      }
      if (cap) {
        var p = document.createElement("p");
        p.textContent = cap.textContent.replace(/\s+/g, " ").trim();
        foot.appendChild(p);
      }
      box.appendChild(foot);
    }

    function apply() {
      stage.style.transform = "translate(" + tx.toFixed(1) + "px," +
                              ty.toFixed(1) + "px) scale(" + scale.toFixed(3) + ")";
    }
    function zoom(factor) {
      var next = Math.min(MAX, Math.max(MIN, scale * factor));
      if (next === scale) return;
      scale = next;
      if (scale === MIN) { tx = 0; ty = 0; }
      apply();
    }
    apply();

    bar.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-zoom]");
      if (!b) return;
      var kind = b.getAttribute("data-zoom");
      if (kind === "in") zoom(STEP);
      else if (kind === "out") zoom(1 / STEP);
      else { scale = MIN; tx = 0; ty = 0; apply(); }
    });

    /* Wheel zoom, guarded: a browser without it simply keeps the buttons. */
    frame.addEventListener("wheel", function (e) {
      e.preventDefault();
      zoom(e.deltaY < 0 ? 1.12 : 1 / 1.12);
    }, { passive: false });

    /* Drag to pan. Pointer events are checked for rather than assumed. */
    if (window.PointerEvent) {
      var dragging = false, lastX = 0, lastY = 0;
      frame.addEventListener("pointerdown", function (e) {
        if (scale <= MIN) return;
        dragging = true; lastX = e.clientX; lastY = e.clientY;
      });
      document.addEventListener("pointermove", function (e) {
        if (!dragging) return;
        tx += e.clientX - lastX; ty += e.clientY - lastY;
        lastX = e.clientX; lastY = e.clientY;
        apply();
      });
      document.addEventListener("pointerup", function () { dragging = false; });
      document.addEventListener("pointercancel", function () { dragging = false; });
    }

    function shut() {
      document.removeEventListener("keydown", onKey);
      if (box.parentNode) box.parentNode.removeChild(box);
      document.documentElement.classList.remove("figbox-open");
      if (opener && opener.focus) opener.focus();
    }
    function onKey(e) {
      if (e.key === "Escape") { shut(); return; }
      if (e.key === "+" || e.key === "=") zoom(STEP);
      else if (e.key === "-") zoom(1 / STEP);
      else if (e.key === "Tab") {
        /* Keep the keyboard inside the dialog while it is open. */
        var stops = box.querySelectorAll("button");
        if (!stops.length) return;
        var first = stops[0], last = stops[stops.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); first.focus();
        }
      }
    }

    close.addEventListener("click", shut);
    box.addEventListener("click", function (e) { if (e.target === box) shut(); });
    document.addEventListener("keydown", onKey);

    document.body.appendChild(box);
    document.documentElement.classList.add("figbox-open");
    close.focus();
  }

  function wire() {
    var figs = document.querySelectorAll("figure.figure");
    if (!figs.length) return;
    Array.prototype.forEach.call(figs, function (fig) {
      if (fig.classList.contains("map-figure")) return;   /* has its own click */
      if (fig.classList.contains("confmap-figure")) return; /* ditto — confmap.js */
      if (!drawingIn(fig)) return;                        /* nothing to enlarge */
      fig.setAttribute("tabindex", "0");
      fig.setAttribute("role", "button");
      fig.setAttribute("aria-label", nameOf(fig));
      fig.classList.add("figure--openable");
      fig.addEventListener("click", function () { open(fig); });
      fig.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
          e.preventDefault();
          open(fig);
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
