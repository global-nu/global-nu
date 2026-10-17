/* global-nu — history explorer.
 *
 * One parameter at a time, from the Bari, NuFit and Valencia global fits, by
 * publication year: a range line and a marker for each published row, with the
 * source of whichever point is selected written out below the chart.
 *
 * Same conventions as site.js: an IIFE, "use strict", var, no build step, no
 * dependency, nothing fetched but the site's own data file. The container is
 * <div class="explorer" data-src="data/history.json"></div>; with this script
 * never running it stays empty and the static panels around it carry the same
 * points. If the data cannot be loaded the container says so in one sentence.
 *
 * Rows quoted without a normal/inverted split (ordering "any") appear in both
 * ordering views, drawn hollow and marked with a diamond in the readout.
 * Selecting a point does not redraw the chart, so keyboard focus stays where it
 * was; only the toggles redraw.
 */
(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var FAIL = "The interactive chart could not load its data; the static panels below show the same points.";
  var GROUPS = [["bari", "Bari"], ["nufit", "NuFit"], ["valencia", "Valencia"]];
  var GLYPH = { bari: "●", nufit: "■", valencia: "◆" };
  var PARAMS = [
    ["Dm2", "|Δm²|"],
    ["dm2", "δm²"],
    ["sin2_th12", "sin²θ₁₂"],
    ["sin2_th13", "sin²θ₁₃"],
    ["sin2_th23", "sin²θ₂₃"],
    ["delta_pi", "δ/π"]
  ];
  var NOTE_PUB = "As published: the three groups quote different quantities (Bari Δm², NuFit Δm²₃ℓ, Valencia |Δm²₃₁|); these points are not comparable with each other.";
  var NOTE_OURS = "Converted to Δm² = m₃² − (m₁²+m₂²)/2; intervals include the uncertainty of δm², not the δm²–Δm² correlation (see the full treatment below). ";
  var uid = 0;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs.hasOwnProperty(k)) e.setAttribute(k, attrs[k]);
    return e;
  }
  function num(v) { return String(+v.toFixed(5)); }
  function groupName(g) { for (var i = 0; i < GROUPS.length; i++) if (GROUPS[i][0] === g) return GROUPS[i][1]; return g; }
  function levelText(l) { return l ? String(l).replace("sigma", "σ") : ""; }

  /* ---- one explorer ---- */
  function build(box, rows) {
    var id = "explorer" + (++uid);
    var st = { param: "Dm2", ord: "no", groups: { bari: true, nufit: true, valencia: true },
               sig: 3, mode: "ours", sel: null };
    var units = {};
    rows.forEach(function (r) { units[r.parameter] = r.unit; });
    function pLabel(p, withUnit) {
      var l = "";
      PARAMS.forEach(function (x) { if (x[0] === p) l = x[1]; });
      var u = units[p];
      return withUnit && u && u !== "1" ? l + " / " + u : l;
    }

    box.textContent = "";
    var controls = el("div", "explorer__controls");
    var btns = {};

    function segment(label, key, items, multi, onPick) {
      var wrap = el("div", "explorer__ctl");
      var lid = id + "-" + key;
      var lab = el("span", "explorer__label", label);
      lab.id = lid;
      var grp = el("div", "explorer__seg");
      grp.setAttribute("role", "group");
      grp.setAttribute("aria-labelledby", lid);
      btns[key] = {};
      items.forEach(function (it) {
        var b = el("button", "explorer__btn");
        b.type = "button";
        b.setAttribute("data-v", it[0]);
        if (it[2]) {
          var g = el("span", "explorer__glyph explorer__glyph--" + it[0], it[2]);
          g.setAttribute("aria-hidden", "true");
          b.appendChild(g);
        }
        b.appendChild(document.createTextNode(it[1]));
        b.addEventListener("click", function () { onPick(it[0]); });
        btns[key][it[0]] = b;
        grp.appendChild(b);
      });
      wrap.appendChild(lab);
      wrap.appendChild(grp);
      controls.appendChild(wrap);
    }

    segment("Parameter", "param", PARAMS.map(function (p) { return [p[0], pLabel(p[0], true)]; }), false,
            function (v) { st.param = v; st.sel = null; draw(); });
    segment("Ordering", "ord", [["no", "NO"], ["io", "IO"]], false,
            function (v) { st.ord = v; st.sel = null; draw(); });
    segment("Groups", "groups", GROUPS.map(function (g) { return [g[0], g[1], GLYPH[g[0]]]; }), true,
            function (v) {
              var on = 0; for (var k in st.groups) if (st.groups[k]) on++;
              if (st.groups[v] && on === 1) { hint.textContent = "At least one group must stay on."; return; }
              st.groups[v] = !st.groups[v]; st.sel = null; draw();
            });
    segment("Range", "sig", [["1", "1σ"], ["3", "3σ"]], false,
            function (v) { st.sig = +v; draw(); });
    segment("Values", "mode", [["ours", "GLOBAL-NU convention"], ["pub", "As published"]], false,
            function (v) { st.mode = v; draw(); });

    var hint = el("p", "explorer__hint");
    var summary = el("p", "explorer__summary");
    summary.setAttribute("aria-live", "polite");
    var chart = el("div", "explorer__chart");
    var note = el("p", "explorer__note");
    var key = el("p", "explorer__key", "Hollow marker: quoted for both orderings. Arrow: upper limit.");
    var readout = el("div", "explorer__readout");
    readout.setAttribute("aria-live", "polite");
    var tgl = el("button", "explorer__btn explorer__toggle", "Show as table");
    tgl.type = "button";
    tgl.setAttribute("aria-expanded", "false");
    var tableWrap = el("div", "table-scroll");
    tableWrap.hidden = true;
    tgl.addEventListener("click", function () {
      var open = tableWrap.hidden;
      tableWrap.hidden = !open;
      tgl.setAttribute("aria-expanded", open ? "true" : "false");
      tgl.textContent = open ? "Hide table" : "Show as table";
    });

    /* ---- downloads: what is on screen, as a figure or as a table ---- */
    var dl = el("div", "explorer__dl");
    dl.appendChild(el("span", "explorer__dl-label", "Download what is shown:"));
    [["svg", "Figure (SVG)"], ["png", "Figure (PNG)"], ["csv", "Table (CSV)"]].forEach(function (d) {
      var b = el("button", "explorer__btn", d[1]);
      b.type = "button";
      b.addEventListener("click", function () { download(d[0]); });
      dl.appendChild(b);
    });

    function baseName() {
      return "global-nu_" + st.param + "_" + st.ord.toUpperCase() + "_" + st.sig + "sigma_" +
        (st.mode === "pub" ? "as-published" : "global-nu-convention");
    }
    function save(blob, name) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    }
    /* A standalone copy of the chart: the page's colours are CSS variables
       that mean nothing outside it, so every element gets its computed
       colours written in; a background, a title saying what is plotted, and
       a source line are added. */
    function standaloneSvg() {
      /* Always the light theme: a downloaded figure goes into a paper or a
         slide. The page's theme is switched for the time of the read and
         put back at once. */
      var root = document.documentElement, was = root.getAttribute("data-theme");
      root.setAttribute("data-theme", "light");
      try { return standaloneSvgNow(); }
      finally { if (was === null) root.removeAttribute("data-theme"); else root.setAttribute("data-theme", was); }
    }
    function standaloneSvgNow() {
      var src = chart.querySelector("svg");
      if (!src) return null;
      var clone = src.cloneNode(true);
      var a = src.querySelectorAll("*"), b = clone.querySelectorAll("*");
      var PROPS = ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "fill-opacity",
                   "stroke-opacity", "font-family", "font-size", "font-weight", "text-anchor"];
      for (var i = 0; i < a.length; i++) {
        var cs = window.getComputedStyle(a[i]), style = "";
        PROPS.forEach(function (k) { var v = cs.getPropertyValue(k); if (v) style += k + ":" + v + ";"; });
        Array.prototype.slice.call(b[i].attributes).forEach(function (at) {
          if (at.value.indexOf("var(") >= 0) b[i].removeAttribute(at.name);
        });
        b[i].setAttribute("style", style);
        b[i].removeAttribute("class");
        b[i].removeAttribute("tabindex");
      }
      var vb = (src.getAttribute("viewBox") || "0 0 720 380").split(/\s+/).map(Number);
      var W = vb[2], H = vb[3], top = 34, foot = 22;
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      clone.setAttribute("viewBox", "0 " + (-top) + " " + W + " " + (H + top + foot));
      clone.setAttribute("width", W);
      clone.setAttribute("height", H + top + foot);
      clone.removeAttribute("class");
      var bg = "#ffffff";
      var ink = window.getComputedStyle(document.body).color;
      var ns = "http://www.w3.org/2000/svg";
      var rect = document.createElementNS(ns, "rect");
      rect.setAttribute("x", 0); rect.setAttribute("y", -top);
      rect.setAttribute("width", W); rect.setAttribute("height", H + top + foot);
      rect.setAttribute("style", "fill:" + bg);
      clone.insertBefore(rect, clone.firstChild);
      function text(y, str, size, op) {
        var t = document.createElementNS(ns, "text");
        t.setAttribute("x", 12); t.setAttribute("y", y);
        t.setAttribute("style", "fill:" + ink + ";font-family:Inter,Helvetica,Arial,sans-serif;font-size:" + size + "px;opacity:" + op);
        t.textContent = str;
        clone.appendChild(t);
      }
      text(-12, summary.textContent, 13, 1);
      /* the group key, top right, in the groups' own colours */
      var probe = document.createElement("span");
      chart.appendChild(probe);
      var kx = W - 12;
      GROUPS.slice().reverse().forEach(function (g) {
        if (!st.groups[g[0]]) return;
        probe.style.color = "var(--grp-" + g[0] + ")";
        var t = document.createElementNS(ns, "text");
        t.setAttribute("x", kx); t.setAttribute("y", -12); t.setAttribute("text-anchor", "end");
        t.setAttribute("style", "fill:" + window.getComputedStyle(probe).color +
                       ";font-family:Inter,Helvetica,Arial,sans-serif;font-size:12px;font-weight:600");
        t.textContent = GLYPH[g[0]] + " " + g[1];
        clone.appendChild(t);
        kx -= 12 + 8 * (g[1].length + 2);
      });
      probe.remove();
      text(H + 15, "global-nu.org — every point from the table of its paper; " +
           (st.mode === "pub" ? "values as published." : "converted to Δm² = m₃² − (m₁²+m₂²)/2 where needed."), 10, .7);
      return new XMLSerializer().serializeToString(clone);
    }
    function csvTable() {
      var q = function (v) { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
      var head = ["parameter", "ordering_shown", "values", "range_level", "group", "year", "journal", "arxiv",
                  "table", "ordering_of_row", "kind", "value", "range_low", "range_high", "unit", "interval_method"];
      var lines = ["# global-nu.org parameter history — the points of the chart as shown; " +
                   "values " + (st.mode === "pub" ? "as published" : "in the GLOBAL-NU convention") +
                   "; CC BY 4.0", head.join(",")];
      points().forEach(function (p) {
        var r = p.row;
        lines.push([st.param, st.ord.toUpperCase(), st.mode === "pub" ? "as_published" : "global_nu_convention",
          st.sig + "sigma", groupName(r.group), r.year, r.journal, r.arxiv, r.table, r.ordering, r.kind,
          p.raw, p.rawLo, p.rawHi, r.unit, r.interval_method].map(q).join(","));
      });
      return lines.join("\n") + "\n";
    }
    function download(kind) {
      if (kind === "csv") {
        save(new Blob([csvTable()], { type: "text/csv" }), baseName() + ".csv");
        return;
      }
      var svgText = standaloneSvg();
      if (!svgText) return;
      if (kind === "svg") {
        save(new Blob([svgText], { type: "image/svg+xml" }), baseName() + ".svg");
        return;
      }
      var img = new Image();
      img.onload = function () {
        var scale = 2, c = document.createElement("canvas");
        c.width = img.width * scale; c.height = img.height * scale;
        var ctx = c.getContext("2d");
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);
        c.toBlob(function (blob) { if (blob) save(blob, baseName() + ".png"); }, "image/png");
      };
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgText);
    }
    box.__explorer = { standaloneSvg: standaloneSvg, csvTable: csvTable };   /* for tests */

    [controls, hint, summary, chart, note, key, readout, dl, tgl, tableWrap].forEach(function (n) { box.appendChild(n); });

    /* ---- data for the current state ---- */
    function sfx() { return st.mode === "pub" ? "_as_published" : "_our_convention"; }
    function absMode() { return st.param === "Dm2" && st.mode === "pub"; }

    function pointOf(r, i) {
      var v = r["value" + sfx()];
      if (v == null) return null;
      var p = { row: r, idx: i, raw: v, v: absMode() ? Math.abs(v) : v, lo: null, hi: null, rawLo: null, rawHi: null };
      var lo = r["s" + st.sig + "_lo" + sfx()], hi = r["s" + st.sig + "_hi" + sfx()];
      if (lo != null && hi != null) {
        p.rawLo = lo; p.rawHi = hi;
        if (absMode()) { lo = Math.abs(lo); hi = Math.abs(hi); }
        p.lo = Math.min(lo, hi); p.hi = Math.max(lo, hi);
      }
      return p;
    }
    function points() {
      var out = [];
      rows.forEach(function (r, i) {
        if (r.parameter !== st.param || !st.groups[r.group]) return;
        if (r.ordering !== "any" && r.ordering !== st.ord) return;
        var p = pointOf(r, i);
        if (p) out.push(p);
      });
      out.sort(function (a, b) {
        return a.row.year - b.row.year || (a.row.group < b.row.group ? -1 : a.row.group > b.row.group ? 1 : 0) || a.idx - b.idx;
      });
      return out;
    }

    function fmtVal(p) {
      var u = units[p.row.parameter] && units[p.row.parameter] !== "1" ? " " + units[p.row.parameter] : "";
      if (p.row.kind === "limit") return "< " + num(p.raw) + u + " (" + levelText(p.row.level) + ")";
      return num(p.raw) + u;
    }
    function fmtRange(p) {
      if (p.row.kind === "limit") return "upper limit, " + levelText(p.row.level);
      if (p.lo == null) return "no " + st.sig + "σ range published";
      return st.sig + "σ: " + num(p.rawLo) + " to " + num(p.rawHi);
    }

    /* ---- axes ---- */
    function niceStep(raw) {
      var e = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / e;
      return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e;
    }
    function yTicks(lo, hi) {
      if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
      var step = niceStep((hi - lo) / 4);
      var a = Math.floor(lo / step + 1e-9) * step, b = Math.ceil(hi / step - 1e-9) * step, t = [];
      for (var v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(8));
      return t;
    }

    /* ---- drawing ---- */
    function markerShape(g, grp, hollow) {
      var col = "var(--grp-" + grp + ")";
      var fill = hollow ? "var(--bg)" : col;
      var s;
      if (grp === "bari") s = sv("circle", { r: 5 });
      else if (grp === "nufit") s = sv("rect", { x: -4.5, y: -4.5, width: 9, height: 9 });
      else s = sv("path", { d: "M0,-6 L6,0 L0,6 L-6,0 Z" });   /* diamond, as on the static panels */
      s.setAttribute("style", "fill:" + fill + ";stroke:" + col + ";stroke-width:2");
      s.setAttribute("class", "explorer__mark");
      g.appendChild(s);
    }

    function draw() {
      var pts = points();
      var W = Math.max(300, Math.round(chart.clientWidth || 720));
      var H = Math.max(260, Math.round(W * 0.52));
      var m = { l: 58, r: 18, t: 14, b: 42 };
      var pw = W - m.l - m.r, ph = H - m.t - m.b;

      /* button state */
      for (var k in btns.param) btns.param[k].setAttribute("aria-pressed", String(k === st.param));
      for (k in btns.ord) btns.ord[k].setAttribute("aria-pressed", String(k === st.ord));
      for (k in btns.groups) btns.groups[k].setAttribute("aria-pressed", String(!!st.groups[k]));
      btns.sig["1"].setAttribute("aria-pressed", String(st.sig === 1));
      btns.sig["3"].setAttribute("aria-pressed", String(st.sig === 3));
      btns.mode.ours.setAttribute("aria-pressed", String(st.mode === "ours"));
      btns.mode.pub.setAttribute("aria-pressed", String(st.mode === "pub"));
      hint.textContent = "";

      /* notes */
      note.textContent = "";
      if (st.param === "Dm2") {
        if (st.mode === "pub") note.textContent = NOTE_PUB;
        else {
          note.appendChild(document.createTextNode(NOTE_OURS));
          var a = el("a", null, "Method");
          a.href = "#method";
          note.appendChild(a);
        }
      }
      note.hidden = st.param !== "Dm2";

      /* summary */
      var names = GROUPS.filter(function (g) { return st.groups[g[0]]; }).map(function (g) { return g[1]; });
      summary.textContent = pLabel(st.param, false) + ", " + (st.ord === "no" ? "normal" : "inverted") + " ordering, " +
        st.sig + "σ, " + (st.mode === "ours" ? "GLOBAL-NU convention" : "as published") + ": " +
        pts.length + (pts.length === 1 ? " point" : " points") + " from " + names.join(", ");

      /* domain */
      var y0 = Infinity, y1 = -Infinity, x0 = Infinity, x1 = -Infinity;
      pts.forEach(function (p) {
        [p.v, p.lo, p.hi].forEach(function (v) { if (v != null) { y0 = Math.min(y0, v); y1 = Math.max(y1, v); } });
        x0 = Math.min(x0, p.row.year); x1 = Math.max(x1, p.row.year);
      });
      chart.textContent = "";
      var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, "class": "explorer__svg", role: "group",
                            "aria-label": pLabel(st.param, true) + " by publication year" });
      chart.appendChild(svg);
      if (!pts.length) {
        var t0 = sv("text", { x: W / 2, y: H / 2, "text-anchor": "middle", "class": "explorer__tick" });
        t0.textContent = "No points for this selection.";
        svg.appendChild(t0);
        renderTable(pts); showSel(pts);
        return;
      }
      x0 -= 1; x1 += 1;
      var ticks = yTicks(y0, y1);
      var ya = ticks[0], yb = ticks[ticks.length - 1];
      function X(v) { return m.l + (v - x0) / (x1 - x0) * pw; }
      function Y(v) { return m.t + (1 - (v - ya) / (yb - ya)) * ph; }

      ticks.forEach(function (v) {
        svg.appendChild(sv("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), "class": "explorer__grid" }));
        var t = sv("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", "class": "explorer__tick" });
        t.textContent = num(v);
        svg.appendChild(t);
      });
      var span = x1 - x0, xs = span > 20 ? 5 : span > 10 ? 2 : 1;
      for (var yr = Math.ceil(x0 / xs) * xs; yr <= x1; yr += xs) {
        svg.appendChild(sv("line", { x1: X(yr), x2: X(yr), y1: m.t + ph, y2: m.t + ph + 4, "class": "explorer__axis" }));
        var xt = sv("text", { x: X(yr), y: m.t + ph + 18, "text-anchor": "middle", "class": "explorer__tick" });
        xt.textContent = yr;
        svg.appendChild(xt);
      }
      svg.appendChild(sv("line", { x1: m.l, x2: W - m.r, y1: m.t + ph, y2: m.t + ph, "class": "explorer__axis" }));
      svg.appendChild(sv("line", { x1: m.l, x2: m.l, y1: m.t, y2: m.t + ph, "class": "explorer__axis" }));
      var xl = sv("text", { x: m.l + pw / 2, y: H - 6, "text-anchor": "middle", "class": "explorer__title" });
      xl.textContent = "Publication year";
      svg.appendChild(xl);
      var yl = sv("text", { x: 0, y: 0, "text-anchor": "middle", "class": "explorer__title",
                            transform: "translate(13," + (m.t + ph / 2) + ") rotate(-90)" });
      yl.textContent = pLabel(st.param, true);
      svg.appendChild(yl);

      /* offsets so rows of one year do not overlap */
      var byYear = {};
      pts.forEach(function (p) { (byYear[p.row.year] = byYear[p.row.year] || []).push(p); });
      for (var yk in byYear) {
        var list = byYear[yk];
        list.forEach(function (p, i) { p.dx = (i - (list.length - 1) / 2) * 7; });
      }

      pts.forEach(function (p) {
        var r = p.row, hollow = r.ordering === "any", limit = r.kind === "limit";
        var cx = X(r.year) + p.dx, cy = Y(p.v), col = "var(--grp-" + r.group + ")";
        var g = sv("g", { "class": "explorer__pt", tabindex: "0", role: "button",
                          transform: "translate(" + cx + "," + cy + ")", "data-idx": p.idx,
                          "aria-label": groupName(r.group) + " " + r.year + ", " + fmtVal(p) + (limit ? "" : ", " + fmtRange(p)) });
        if (limit) {
          var ly = Y(ya) - cy;
          g.appendChild(sv("line", { x1: 0, x2: 0, y1: 0, y2: ly, style: "stroke:" + col + ";stroke-width:2" }));
          g.appendChild(sv("path", { d: "M-5," + (ly - 7) + " L0," + ly + " L5," + (ly - 7), style: "fill:none;stroke:" + col + ";stroke-width:2" }));
          var lt = sv("text", { x: cx > W - 90 ? -8 : 8, y: -8, "text-anchor": cx > W - 90 ? "end" : "start", "class": "explorer__tick explorer__lbl" });
          lt.textContent = "<" + num(p.raw) + " (" + levelText(r.level) + ")";
          g.appendChild(lt);
        } else if (p.lo != null) {
          g.appendChild(sv("line", { x1: 0, x2: 0, y1: Y(p.hi) - cy, y2: Y(p.lo) - cy, style: "stroke:" + col + ";stroke-width:2" }));
          g.appendChild(sv("line", { x1: -3.5, x2: 3.5, y1: Y(p.hi) - cy, y2: Y(p.hi) - cy, style: "stroke:" + col + ";stroke-width:2" }));
          g.appendChild(sv("line", { x1: -3.5, x2: 3.5, y1: Y(p.lo) - cy, y2: Y(p.lo) - cy, style: "stroke:" + col + ";stroke-width:2" }));
        }
        g.appendChild(sv("circle", { r: 11, "class": "explorer__ring" }));
        g.appendChild(sv("circle", { r: 14, "class": "explorer__hit" }));
        markerShape(g, r.group, hollow);
        g.addEventListener("click", function () { select(p.idx, pts); });
        g.addEventListener("focus", function () { select(p.idx, pts); });
        g.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.idx, pts); }
        });
        svg.appendChild(g);
      });
      renderTable(pts);
      showSel(pts);
    }

    /* ---- selection and readout ---- */
    function select(idx, pts) { st.sel = idx; showSel(pts || points()); }

    function showSel(pts) {
      var cur = null;
      pts.forEach(function (p) { if (p.idx === st.sel) cur = p; });
      var nodes = chart.querySelectorAll(".explorer__pt");
      for (var i = 0; i < nodes.length; i++) {
        var on = cur && +nodes[i].getAttribute("data-idx") === cur.idx;
        nodes[i].setAttribute("class", "explorer__pt" + (on ? " is-sel" : ""));
        if (on) nodes[i].setAttribute("aria-pressed", "true"); else nodes[i].removeAttribute("aria-pressed");
      }
      readout.textContent = "";
      if (!cur) {
        st.sel = null;
        readout.appendChild(el("p", "explorer__empty", "Select a point to see its source."));
        return;
      }
      var r = cur.row;
      var head = el("p", "explorer__who");
      head.appendChild(el("strong", null, groupName(r.group) + " " + r.year));
      if (r.ordering === "any") head.appendChild(document.createTextNode(" (quoted for both orderings)"));
      readout.appendChild(head);
      var dl = el("dl", "explorer__facts");
      function row(k, v) {
        dl.appendChild(el("dt", null, k));
        var dd = el("dd");
        if (typeof v === "string") dd.textContent = v; else dd.appendChild(v);
        dl.appendChild(dd);
      }
      row("Value", fmtVal(cur) + (absMode() ? " (plotted as |value|)" : ""));
      row("Range", fmtRange(cur));
      row("Journal", r.journal);
      var ax = el("a", null, r.arxiv);
      ax.href = "https://arxiv.org/abs/" + r.arxiv;
      row("arXiv", ax);
      row("Table", r.table);
      if (r.interval_method) row("Interval method", r.interval_method);
      readout.appendChild(dl);
    }

    function renderTable(pts) {
      tableWrap.textContent = "";
      var tb = el("table", "data");
      var hd = el("tr");
      ["Year", "Group", "Value", "Range (" + st.sig + "σ)", "Source"].forEach(function (h) { hd.appendChild(el("th", null, h)); });
      tb.appendChild(el("thead")).appendChild(hd);
      var body = el("tbody");
      pts.forEach(function (p) {
        var tr = el("tr");
        tr.appendChild(el("th", null, String(p.row.year)));
        tr.appendChild(el("td", null, groupName(p.row.group) + (p.row.ordering === "any" ? " (both orderings)" : "")));
        tr.appendChild(el("td", null, fmtVal(p)));
        tr.appendChild(el("td", null, p.row.kind === "limit" ? "—" : p.lo == null ? "none published" : num(p.rawLo) + " to " + num(p.rawHi)));
        tr.appendChild(el("td", null, p.row.journal));
        body.appendChild(tr);
      });
      tb.appendChild(body);
      tableWrap.appendChild(tb);
    }

    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && st.sel != null) { st.sel = null; showSel(points()); }
    });

    /* redraw when the container width changes, so the text keeps its size */
    var lastW = chart.clientWidth;
    if (window.addEventListener) {
      window.addEventListener("resize", function () {
        if (chart.clientWidth && Math.abs(chart.clientWidth - lastW) > 8) { lastW = chart.clientWidth; draw(); }
      });
    }
    draw();
  }

  function failed(box) {
    box.textContent = "";
    box.appendChild(el("p", "explorer__fail", FAIL));
  }

  function init() {
    var boxes = document.querySelectorAll(".explorer[data-src]");
    Array.prototype.forEach.call(boxes, function (box) {
      try {
        if (!window.fetch) { failed(box); return; }
        window.fetch(box.getAttribute("data-src"))
          .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
          })
          .then(function (data) {
            if (!data || !data.rows || !data.rows.length) throw new Error("no rows");
            build(box, data.rows);
          })
          .catch(function () { failed(box); });
      } catch (e) { failed(box); }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
