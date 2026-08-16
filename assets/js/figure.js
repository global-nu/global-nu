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

    /* Every plotted point becomes a stop for the keyboard, and names itself
       to a screen reader through the <title> make_history.py already writes
       inside it. Done to the copy only: the figure on the page keeps its
       single tab stop, so tabbing down the page does not walk through forty
       data points before reaching the next link. */
    var points = art.querySelectorAll ? art.querySelectorAll(".pt") : [];
    Array.prototype.forEach.call(points, function (p) {
      p.setAttribute("tabindex", "0");
      p.setAttribute("role", "img");
    });

    /* The hover panel. It hangs off the frame and not off the stage, which
       is deliberate and is the whole reason this took a design: the stage is
       what carries transform: scale(), so a panel inside it would be drawn at
       eight times its size at maximum zoom and dragged out of view by any
       pan. Outside it, the panel keeps one size at every zoom. */
    var tip = document.createElement("div");
    tip.className = "figtip";
    tip.hidden = true;
    frame.appendChild(tip);

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

    /* The point under an event, or null. Walked by hand rather than with
       closest(): the target is usually an SVG child, and this file's rule is
       that a missing API disables an enhancement rather than throwing. */
    function pointAt(e) {
      var n = e.target;
      while (n && n !== frame) {
        if (n.classList && n.classList.contains("pt")) return n;
        n = n.parentNode;
      }
      return null;
    }

    /* What a point says about itself, in the order a reader needs it: who and
       when, then the number, then how well it is known. Read from data-
       attributes rather than from the <title> text, which is written for a
       human and would have to be re-parsed every time its wording changed. */
    function fill(pt) {
      var d = {}, attrs = pt.attributes, i;
      for (i = 0; i < attrs.length; i++) {
        if (attrs[i].name.indexOf("data-") === 0) {
          d[attrs[i].name.slice(5)] = attrs[i].value;
        }
      }
      if (!d.value || !d.param) return false;      /* nothing to show beats a panel of blanks */
      while (tip.firstChild) tip.removeChild(tip.firstChild);

      var head = document.createElement("b");
      head.textContent = [d.group, d.year].filter(Boolean).join(" · ");
      tip.appendChild(head);

      var val = document.createElement("p");
      val.className = "figtip__val";
      /* A limit's value already reads as "< 5.0 (3σ)" — an "=" in front of it
         would state the opposite of what the point means. */
      val.textContent = d.param + (d.kind === "limit" ? " " : " = ") + d.value +
                        (d.unit ? "  ·  " + d.unit : "");
      tip.appendChild(val);

      var lines = [];
      if (d.kind === "limit") lines.push("Upper limit — a bound, not a measurement");
      else if (d.range) lines.push(d.range);
      if (d.ordering) lines.push(d.ordering);
      if (d.note) lines.push(d.note);
      lines.forEach(function (t) {
        var p = document.createElement("p");
        p.textContent = t;
        tip.appendChild(p);
      });
      return true;
    }

    /* The panel rests in the frame's bottom-left corner, and moves to the
       bottom-right when the point being named is itself down there — the one
       placement that would hide the very thing the reader is pointing at.
       Guarded on a measurable rectangle: where layout is not computed there
       is nothing to avoid, and the default corner stands. */
    function place(p) {
      if (!p.getBoundingClientRect || !frame.getBoundingClientRect) return;
      var r = p.getBoundingClientRect(), f = frame.getBoundingClientRect();
      if (!f.width || !f.height) return;
      var low = r.top - f.top > f.height * 0.55;
      var left = r.left - f.left < f.width * 0.45;
      tip.classList.toggle("figtip--right", low && left);
    }

    function showTip(e) {
      var p = pointAt(e);
      if (!p) return;
      tip.hidden = !fill(p);
      if (!tip.hidden) place(p);
    }
    function hideTip() { tip.hidden = true; }

    frame.addEventListener("mouseover", showTip);
    frame.addEventListener("mouseout", function (e) {
      /* Moving between a point's own children — its hit disc and its ink —
         fires mouseout too. Closing on those would flicker the panel off and
         on again while the pointer never left the point. */
      var from = pointAt(e), to = e.relatedTarget;
      if (!from) return;
      while (to && to !== frame) {
        if (to === from) return;
        to = to.parentNode;
      }
      hideTip();
    });
    frame.addEventListener("focusin", showTip);
    frame.addEventListener("focusout", hideTip);

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
        /* Keep the keyboard inside the dialog while it is open. The points
           are stops too: a cycle that ended at the last button would send Tab
           straight back to the first control and no point would ever be
           reachable without a mouse. */
        var stops = box.querySelectorAll("button, .pt[tabindex]");
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
