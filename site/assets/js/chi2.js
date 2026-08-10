/* Interactive Δχ² explorer.
 *
 * Reads the JSON written by tools/make_chi2_data.py and draws the profiles the
 * way the papers do: Nσ = √Δχ² against the parameter, one curve per mass
 * ordering, with 1σ/2σ/3σ guides.
 *
 * Three things it deliberately does NOT do:
 *   * it never interpolates between grid nodes — the release states that its
 *     own figures are PCHIP-interpolated, and a straight segment between two
 *     published nodes is an honest drawing where an invented spline is not;
 *   * it never rescales one ordering onto the other silently. The two curves
 *     are each referred to their own minimum, exactly as released; the
 *     "common scale" switch applies the offset from the same file and says so;
 *   * it draws nothing at all if the data file is missing, and says why.
 *
 * Colours come from CSS variables, so the plot follows the theme.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-chi2]");
  if (!root) return;

  var W = 760, H = 380, L = 62, R = 18, T = 18, B = 46;
  var NSIGMA_MAX = 4;

  var state = { data: null, set: null, param: null, joint: false, hover: null };

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function el(tag, attrs, text) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }
  function nsigma(dchi2) { return dchi2 > 0 ? Math.sqrt(dchi2) : 0; }

  /* ---------------------------------------------------------------- data -- */
  function load() {
    var url = root.getAttribute("data-chi2");
    fetch(url, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (doc) {
        state.data = doc;
        state.set = Object.keys(doc.datasets)[0];
        state.param = Object.keys(doc.datasets[state.set].params)[0];
        build();
      })
      .catch(function (e) {
        root.innerHTML =
          '<p class="small muted">The Δχ² data could not be loaded (' +
          String(e.message) + "). Nothing is drawn rather than something " +
          "approximate.</p>";
      });
  }

  /* --------------------------------------------------------------- chrome -- */
  function build() {
    root.innerHTML = "";

    var bar = document.createElement("div");
    bar.className = "chi2__bar";

    var sets = document.createElement("div");
    sets.className = "chi2__group";
    sets.setAttribute("role", "group");
    sets.setAttribute("aria-label", "Data set");
    Object.keys(state.data.datasets).forEach(function (k) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chi2__chip";
      b.textContent = state.data.datasets[k].label || k;
      b.setAttribute("aria-pressed", String(k === state.set));
      b.addEventListener("click", function () {
        state.set = k;
        if (!state.data.datasets[k].params[state.param]) {
          state.param = Object.keys(state.data.datasets[k].params)[0];
        }
        build();
      });
      sets.appendChild(b);
    });

    var params = document.createElement("div");
    params.className = "chi2__group";
    params.setAttribute("role", "group");
    params.setAttribute("aria-label", "Parameter");
    var ps = state.data.datasets[state.set].params;
    Object.keys(ps).forEach(function (k) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chi2__chip";
      b.textContent = ps[k].label || k;
      b.setAttribute("aria-pressed", String(k === state.param));
      b.addEventListener("click", function () { state.param = k; build(); });
      params.appendChild(b);
    });

    var joint = document.createElement("label");
    joint.className = "chi2__switch";
    var cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = state.joint;
    cb.addEventListener("change", function () { state.joint = cb.checked; build(); });
    joint.appendChild(cb);
    joint.appendChild(document.createTextNode(" put both orderings on a common scale"));

    bar.appendChild(params);
    bar.appendChild(sets);
    bar.appendChild(joint);
    root.appendChild(bar);
    root.appendChild(plot());

    var read = document.createElement("p");
    read.className = "chi2__readout";
    read.id = "chi2-readout";
    read.setAttribute("aria-live", "polite");
    read.textContent = "Move along the curve to read values.";
    root.appendChild(read);

    var note = document.createElement("p");
    note.className = "cap";
    var d = state.data.datasets[state.set];
    note.innerHTML =
      "Δχ² profiles as released, one degree of freedom; each ordering is " +
      "referred to its own free minimum. Offset (IO − NO) = " +
      d.offset_io_minus_no.toFixed(3) +
      (state.joint
        ? ", applied here so the two are directly comparable."
        : ", not applied: as drawn, the two curves are <strong>not</strong> " +
          "directly comparable.") +
      " Segments join published grid nodes; nothing is interpolated.";
    root.appendChild(note);
  }

  /* ----------------------------------------------------------------- plot -- */
  function plot() {
    var d = state.data.datasets[state.set];
    var p = d.params[state.param];
    var off = d.offset_io_minus_no;
    var addNO = state.joint ? Math.max(0, -off) : 0;
    var addIO = state.joint ? Math.max(0, off) : 0;

    var x0 = Math.min.apply(null, p.v), x1 = Math.max.apply(null, p.v);
    var sx = function (v) { return L + (v - x0) / (x1 - x0) * (W - L - R); };
    var sy = function (n) { return H - B - (n / NSIGMA_MAX) * (H - T - B); };

    var svg = el("svg", {
      viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Delta chi squared profile for " + (p.label || state.param) +
        ", both mass orderings",
      class: "chi2__svg"
    });

    svg.appendChild(el("line", { x1: L, y1: H - B, x2: W - R, y2: H - B,
      stroke: "currentColor", "stroke-width": 1, opacity: ".35" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: H - B,
      stroke: "currentColor", "stroke-width": 1, opacity: ".35" }));

    [1, 2, 3].forEach(function (n) {
      svg.appendChild(el("line", { x1: L, y1: sy(n), x2: W - R, y2: sy(n),
        stroke: "currentColor", "stroke-width": 1, "stroke-dasharray": "3 5",
        opacity: ".22" }));
      svg.appendChild(el("text", { x: L - 9, y: sy(n) + 4, "text-anchor": "end",
        "font-size": 11, fill: "currentColor", opacity: ".62" }, n + "σ"));
    });
    for (var t = 0; t <= 4; t++) {
      var v = x0 + (x1 - x0) * t / 4;
      svg.appendChild(el("text", { x: sx(v), y: H - B + 20, "text-anchor": "middle",
        "font-size": 11, fill: "currentColor", opacity: ".62" },
        Number(v.toPrecision(4)).toString()));
    }
    svg.appendChild(el("text", { x: (L + W - R) / 2, y: H - 8,
      "text-anchor": "middle", "font-size": 12, fill: "currentColor",
      opacity: ".75" },
      (p.label || state.param) + (p.unit_label ? " / " + p.unit_label : "")));
    svg.appendChild(el("text", { x: 14, y: (T + H - B) / 2,
      "text-anchor": "middle", "font-size": 12, fill: "currentColor",
      opacity: ".75", transform: "rotate(-90 14 " + ((T + H - B) / 2) + ")" }, "Nσ"));

    function curve(vals, add, colour, dash) {
      var d2 = "", started = false;
      for (var i = 0; i < p.v.length; i++) {
        var n = nsigma(vals[i] + add);
        if (n > NSIGMA_MAX) { started = false; continue; }   // clipped, not squashed
        d2 += (started ? "L" : "M") + sx(p.v[i]).toFixed(1) + " " + sy(n).toFixed(1);
        started = true;
      }
      var path = el("path", { d: d2, fill: "none", stroke: colour,
        "stroke-width": 2.4, "stroke-linejoin": "round", "stroke-linecap": "round" });
      if (dash) path.setAttribute("stroke-dasharray", "7 5");
      return path;
    }
    svg.appendChild(curve(p.no, addNO, "var(--no)", false));
    svg.appendChild(curve(p.io, addIO, "var(--io)", true));

    var cross = el("line", { x1: 0, y1: T, x2: 0, y2: H - B, stroke: "currentColor",
      "stroke-width": 1, opacity: "0" });
    svg.appendChild(cross);

    var hit = el("rect", { x: L, y: T, width: W - L - R, height: H - T - B,
      fill: "transparent", style: "cursor:crosshair" });
    svg.appendChild(hit);

    function at(clientX) {
      var box = svg.getBoundingClientRect();
      var vx = (clientX - box.left) / box.width * W;
      var value = x0 + (vx - L) / (W - L - R) * (x1 - x0);
      var best = 0, bd = Infinity;
      for (var i = 0; i < p.v.length; i++) {
        var dd = Math.abs(p.v[i] - value);
        if (dd < bd) { bd = dd; best = i; }
      }
      cross.setAttribute("x1", sx(p.v[best]));
      cross.setAttribute("x2", sx(p.v[best]));
      cross.setAttribute("opacity", ".45");
      var out = document.getElementById("chi2-readout");
      if (out) {
        out.textContent = (p.label || state.param) + " = " +
          Number(p.v[best].toPrecision(5)) + (p.unit_label ? " " + p.unit_label : "") +
          " · NO " + nsigma(p.no[best] + addNO).toFixed(2) + "σ" +
          " · IO " + nsigma(p.io[best] + addIO).toFixed(2) + "σ";
      }
    }
    hit.addEventListener("mousemove", function (e) { at(e.clientX); });
    hit.addEventListener("touchmove", function (e) {
      if (e.touches[0]) at(e.touches[0].clientX);
    }, { passive: true });
    hit.addEventListener("mouseleave", function () {
      cross.setAttribute("opacity", "0");
      var out = document.getElementById("chi2-readout");
      if (out) out.textContent = "Move along the curve to read values.";
    });

    var wrap = document.createElement("div");
    wrap.className = "chi2__plot";
    wrap.appendChild(svg);

    var legend = document.createElement("div");
    legend.className = "legend legend--chart";
    legend.innerHTML =
      '<span><i class="k-no"></i>Normal ordering</span>' +
      '<span><i class="k-io"></i>Inverted ordering (dashed)</span>';
    wrap.appendChild(legend);
    return wrap;
  }

  load();
})();
