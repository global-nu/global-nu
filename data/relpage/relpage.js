(function(){
/* gallery built from a list, so adding a figure is one line */
const F2=[["s23_s13","sin&sup2;&theta;<sub>23</sub> &ndash; sin&sup2;&theta;<sub>13</sub>"],
          ["s23_dm2atm","sin&sup2;&theta;<sub>23</sub> &ndash; |&Delta;m&sup2;|"],
          ["s23_delta","sin&sup2;&theta;<sub>23</sub> &ndash; &delta;/&pi;"],
          ["dm2ee_dm2sol","&Delta;m&sup2;<sub>ee</sub> &ndash; &delta;m&sup2;"],
          ["s12_dm2sol","sin&sup2;&theta;<sub>12</sub> &ndash; &delta;m&sup2;"]];
const card=(src,tit,pdf)=>`<figure><a href="${src}" target="_blank" rel="noopener">
  <img src="${src}" width="2524" height="1670" alt="${tit.replace(/<[^>]*>/g,'')}" loading="lazy"></a>
  <figcaption><b>${tit}</b></figcaption></figure>`;
document.getElementById('gal2').innerHTML = F2.map(([k,t])=>
  card(`release-2026a/figures/2D/bari2026_2D_${k}.png`,t,`release-2026a/figures/2D/bari2026_2D_${k}.pdf`)).join('');

/* The "run online" buttons only make sense if the page is served from a
   reachable host: from file:// there is nothing for Binder or Colab to fetch,
   and a dead link is worse than an absent one. */
(function(){
  /* ------------------------------------------------------------------
     PUBLIC_REPO — the only line to touch.

     Empty  -> the Binder and Colab buttons DO NOT appear. This is the current
               state: these results sit behind authentication (.htaccess), and
               Binder and Colab only work by fetching notebook and data from a
               PUBLIC repository. Making them work would put the same data in
               the clear on GitHub, i.e. undo the protection. That is not an
               implementation choice: it is a choice about who may see the
               results, and it belongs upstream.

     Set to "user/repo" -> the two buttons appear on their own, with nothing
               else to change. Do this when the results become public
               (typically when the paper comes out) -- and at that point the
               .htaccess should be revisited too, because keeping the site
               protected while the data sit on GitHub is protection in
               appearance only.

     NOTEBOOK_IN_REPO: path of the .ipynb inside that repository.
     ------------------------------------------------------------------ */
  const PUBLIC_REPO = "";
  const NOTEBOOK_IN_REPO = "Bari_Group_Results/notebook/bari2026_figures.ipynb";

  const el = document.getElementById('online');
  if (!el) return;
  const host = location.hostname;
  const servita = location.protocol === 'http:' || location.protocol === 'https:';
  const pubblica = servita && host && host !== 'localhost' && host !== '127.0.0.1';

  /* JupyterLite is STATIC: any server will do, even a local one, and from there
     it already works -- notebook and data are inside the build. Binder and Colab
     instead must FETCH from a reachable host. The conditions are distinct. */
  let html = servita
    ? `<a class="file" target="_blank" rel="noopener"
        href="release-2026a/lite/lab/index.html?path=bari2026_figures.ipynb">
        <span class="ext">LITE</span><span><span class="n">JupyterLite</span>
        <span class="d">opens in a new tab; runs in this browser, nothing installed, no account</span></span></a>`
    : `<div class="file" style="opacity:.55;cursor:default"><span class="ext">&mdash;</span>
        <span><span class="n">Open this page through a web server</span>
        <span class="d">from file:// the in-browser notebook cannot load</span></span></div>`;

  if (PUBLIC_REPO && pubblica) {
    const nb = encodeURIComponent(NOTEBOOK_IN_REPO);
    html += `<a class="file" href="https://mybinder.org/v2/gh/${PUBLIC_REPO}/HEAD?labpath=${nb}" target="_blank" rel="noopener noreferrer">
        <span class="ext">BINDER</span><span><span class="n">Binder</span>
        <span class="d">full environment, a minute to start</span></span></a>
       <a class="file" href="https://colab.research.google.com/github/${PUBLIC_REPO}/blob/main/${NOTEBOOK_IN_REPO}" target="_blank" rel="noopener noreferrer">
        <span class="ext">COLAB</span><span><span class="n">Google Colab</span>
        <span class="d">needs a Google account</span></span></a>`;
  }
  /* If PUBLIC_REPO is empty nothing is added: no greyed-out buttons, no
     promises. JupyterLite already covers online execution in full, and
     announcing two routes that do not exist only confuses. */
  el.innerHTML = html;
})();

})();

/* Indice della pagina (v2): riquadri "Contents" sotto l'intestazione + barra fissa che
   compare dopo. Voci dalle <section> con un <h2>, anche quelle aggiunte dal sito. */
(function () {
  var ICON = {
    download: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    key: '<path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/>',
    sets: '<rect x="3" y="4" width="18" height="5" rx="1.5"/><rect x="3" y="10.5" width="18" height="5" rx="1.5"/><rect x="3" y="17" width="18" height="3" rx="1.5"/>',
    best: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    read: '<path d="M4 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H4z"/><path d="M20 5h-5a3 3 0 0 0-3 3"/>',
    nota: '<path d="M5 7h14M5 12h10M5 17h6"/><path d="m17 15 3 3-3 3"/>',
    run: '<path d="M8 5v14l11-7z"/>',
    fig: '<path d="M3 20 9 9l5 7 3-4 4 8z"/><circle cx="17" cy="6" r="2"/>',
    plane: '<ellipse cx="12" cy="12" rx="9" ry="5" transform="rotate(-25 12 12)"/><ellipse cx="12" cy="12" rx="4.5" ry="2.3" transform="rotate(-25 12 12)"/>',
    code: '<path d="m9 8-5 4 5 4"/><path d="m15 8 5 4-5 4"/>',
    news: '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
    six: '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M12 12 20 7.5M12 12v9M12 12 4 7.5"/>'
  };
  /* parola chiave nel titolo -> [etichetta, descrizione, icona, gruppo] */
  var MAPPA = [
    [/key numbers/i, "Key numbers", "Mass ordering, octant, CP: the headline answers", "key", 0],
    [/best fits/i, "Best fits & ranges", "Every parameter, 1, 2, 3σ, both orderings", "best", 0],
    [/three data sets/i, "The three data sets", "What each combination contains, and its verdict", "sets", 0],
    [/synopsis/i, "Synopsis figures", "The 1D profiles of all six parameters", "fig", 1],
    [/two-dimensional/i, "2D planes", "Allowed regions, both orderings overlaid", "plane", 1],
    [/get the data/i, "Download the tables", "1D, 2D and the full 6D Δχ², plain text", "download", 1],
    [/6d/i, "6D explorer", "Δχ² at any point; export your own table", "six", 1],
    [/run it/i, "Notebook in the browser", "Redraw every figure, nothing to install", "run", 2],
    [/quick start/i, "Quick start", "Three lines of Python to read a file", "code", 2],
    [/how to read/i, "How to read the tables", "Baselines, offsets, degrees of freedom", "read", 2],
    [/notation/i, "Notation & comparison", "|Δm²| vs Δm²₃₁; NuFIT and Valencia", "nota", 0],
    [/what.s new/i, "What’s new & how to cite", "New data, BibTeX, contact", "news", 2]];
  var GRUPPI = ["Results", "Figures & data", "Use & cite"];
  /* un dato VERO, letto dalla pagina stessa: se non si trova, nessuna etichetta */
  function etichetta(v) {
    var s = v.sec, x;
    try {
      if (/key numbers/i.test(v.titolo)) {
        x = s.querySelector("tbody td");
        var t = x && x.textContent.match(/(NO|IO) at ([\d.]+)\u03c3/);
        return t ? t[1] + " " + t[2] + "\u03c3" : "";
      }
      if (/get the data/i.test(v.titolo)) { x = s.querySelectorAll("a.gd-f").length; return x ? x + " files" : ""; }
      if (/synopsis|two-dimensional/i.test(v.titolo)) { x = s.querySelectorAll("figure").length; return x ? x + " figures" : ""; }
      if (/best fits/i.test(v.titolo)) return "6 parameters";
      if (/three data sets/i.test(v.titolo)) return "a \u00b7 b \u00b7 c";
      if (/6d/i.test(v.titolo)) return "interactive";
      if (/run it/i.test(v.titolo)) return "no install";
      if (/quick start/i.test(v.titolo)) return "Python \u00b7 pandas";
      if (/how to read/i.test(v.titolo)) return "read first";
      if (/what.s new/i.test(v.titolo)) {
        x = [].map.call(s.querySelectorAll(".nv-d"), function (e) { return e.textContent.trim(); });
        return x.join(" \u00b7 ");
      }
    } catch (e) {}
    return "";
  }
  function slug(t) { return t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
  function riquadro(v, k, anima) {
    var a = document.createElement("a");
    a.className = "toc-a"; a.href = "#" + v.sec.id; a.dataset.k = k;
    if (anima) a.style.animationDelay = (40 * k) + "ms";
    a.innerHTML = '<span class="toc-i"><svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[v.ic] +
      '</svg></span><span class="toc-x"><b>' + v.lab + "</b><small>" + v.desc + "</small>" +
      '<span class="toc-tag">' + (v.tag || "") + '</span></span><span class="toc-bar"></span>' +
      '<span class="toc-n">' + String(v.num).padStart(2, "0") + "</span>";
    a.style.setProperty("--gc", "var(--g" + v.g + ")");
    return a;
  }
  function avvia() {
    var voci = [];
    document.querySelectorAll("section").forEach(function (sec) {
      var h = sec.querySelector("h2"); if (!h) return;
      var t = h.textContent.trim(), m = null;
      for (var i = 0; i < MAPPA.length; i++) if (MAPPA[i][0].test(t)) { m = MAPPA[i]; break; }
      var ord = m ? MAPPA.indexOf(m) : 99;
      if (!m) m = [null, t, "", "nota", 2];
      if (!sec.id) sec.id = "s-" + slug(t);
      voci.push({ sec: sec, lab: m[1], desc: m[2], ic: m[3], g: m[4], titolo: t, ord: ord });
    });
    voci.forEach(function (v, i) { v.num = i + 1; v.tag = etichetta(v); });            // numerazione = ordine nella pagina
    function riempi(dove, anima) {
      var g = document.getElementById(dove); if (!g) return [];
      var col = GRUPPI.map(function (n) {
        var d = document.createElement("div");
        var nn = voci.filter(function (v) { return v.g === GRUPPI.indexOf(n); }).length;
        d.innerHTML = '<div class="toc-gt">' + n + ' <b>' + nn + '</b></div><div class="toc-c"></div>';
        g.appendChild(d); return d.querySelector(".toc-c");
      });
      var k = 0, link = [];
      [0, 1, 2].forEach(function (gr) {
        voci.filter(function (v) { return v.g === gr; })
            .sort(function (a, b) { return a.ord - b.ord; })        // per importanza, non per pagina
            .forEach(function (v) { var a = riquadro(v, k++, anima); col[gr].appendChild(a); link.push(a); });
      });
      return link;
    }
    riempi("toc-g", true);
    var tutti = riempi("tb-g", false);
    var tb = document.getElementById("tb"), toc = document.getElementById("contents");
    var tn = document.getElementById("tb-n"), tt = document.getElementById("tb-t");
    var bar = document.getElementById("tb-bar"), bt = document.getElementById("tb-b");
    var cur = -1, seg = document.createElement("div");
    seg.className = "tb-seg";
    voci.forEach(function (v, i) {
      var b = document.createElement("i");
      b.title = v.titolo; b.style.setProperty("--sc", "var(--g" + v.g + ")");
      b.addEventListener("click", function () { vai(i); });
      seg.appendChild(b);
    });
    tb.insertBefore(seg, document.getElementById("tb-d"));
    var segs = seg.querySelectorAll("i");
    function vai(i) {
      if (i < 0 || i >= voci.length) return;
      tb.classList.remove("tb--open"); bt.setAttribute("aria-expanded", "false");
      var lento = !matchMedia("(prefers-reduced-motion: reduce)").matches;
      voci[i].sec.scrollIntoView({ block: "start", behavior: lento ? "smooth" : "auto" });
      history.replaceState(null, "", "#" + voci[i].sec.id);
    }
    function aggiorna() {
      var fuori = toc.getBoundingClientRect().bottom < 0;
      tb.classList.toggle("tb--su", fuori);
      if (!fuori) tb.classList.remove("tb--open");
      var y = window.scrollY + (parseFloat(getComputedStyle(voci[0].sec).scrollMarginTop) || 90) + 20, c = -1;
      voci.forEach(function (v, i) { if (v.sec.offsetTop <= y) c = i; });
      if (c !== cur) {
        cur = c;
        tn.textContent = c >= 0 ? String(voci[c].num).padStart(2, "0") + " / " + String(voci.length).padStart(2, "0") : "";
        tt.textContent = c >= 0 ? voci[c].titolo : "";
        tutti.forEach(function (a) { a.classList.toggle("on", c >= 0 && a.getAttribute("href") === "#" + voci[c].sec.id); });
        segs.forEach(function (b, i) { b.classList.toggle("on", i === c); b.classList.toggle("fatto", i < c); });
        tn.style.setProperty("--sc", c >= 0 ? "var(--g" + voci[c].g + ")" : "var(--accent)");
      }
      var h = document.documentElement;
      bar.style.width = (100 * h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight)) + "%";
    }
    document.addEventListener("click", function (e) {
      var a = e.target.closest("a.toc-a"); if (!a) return;
      var i = voci.findIndex(function (v) { return "#" + v.sec.id === a.getAttribute("href"); });
      if (i >= 0) { e.preventDefault(); vai(i); }
    });
    bt.addEventListener("click", function () {
      var o = tb.classList.toggle("tb--open"); bt.setAttribute("aria-expanded", o ? "true" : "false");
    });
    document.getElementById("tb-p").addEventListener("click", function () { vai(Math.max(0, cur - 1)); });
    document.getElementById("tb-x").addEventListener("click", function () { vai(Math.min(voci.length - 1, cur + 1)); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") tb.classList.remove("tb--open"); });
    window.addEventListener("scroll", aggiorna, { passive: true });
    window.addEventListener("resize", aggiorna);
    aggiorna();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia);
  else avvia();
})();


(function(){
  var boxes = document.querySelectorAll(".relpage .tw, .relpage .table-scroll, .relpage .c6-scorre");
  function edge(b){ b.classList.toggle("at-end", b.scrollLeft + b.clientWidth >= b.scrollWidth - 4); }
  function check(){
    boxes.forEach(function(b){
      var over = b.scrollWidth > b.clientWidth + 4;
      b.classList.toggle("is-scrollable", over);
      var h = b.previousElementSibling;
      var has = h && h.classList.contains("swipe-hint");
      if (over && !has) {
        h = document.createElement("p");
        h.className = "swipe-hint";
        h.textContent = "Swipe to see all columns \u2192";
        b.parentNode.insertBefore(h, b);
      } else if (!over && has) {
        h.remove();
      }
      edge(b);
    });
  }
  boxes.forEach(function(b){ b.addEventListener("scroll", function(){ edge(b); }, {passive:true}); });
  check();
  addEventListener("load", check);
  addEventListener("resize", check);
})();

(function(){
  /* A link to a section (results.html#chi2-6d-sezione) must land on it even
     though the page above keeps growing after the jump: figures, the tables'
     scripts and the fonts add some 2000 px. Keep the target in place on every
     resize until the page is settled -- loaded, fonts ready, every image above
     the target decoded, and one second without a resize -- or until the reader
     scrolls; at most 15 s. Again on hashchange and on pageshow (back/forward). */
  var timer = null, ro = null, moved = false, t0 = 0;
  function stop(){ moved = true; }
  ["wheel","touchstart","keydown","mousedown"].forEach(function(e){
    addEventListener(e, stop, {passive:true});
  });
  function target(){
    var id = decodeURIComponent(location.hash.slice(1));
    return id ? document.getElementById(id) : null;
  }
  function settled(t){
    if (document.readyState !== "complete") return false;
    if (document.fonts && document.fonts.status !== "loaded") return false;
    var y = t.getBoundingClientRect().top;
    return [].every.call(document.images, function(im){
      return im.complete || im.getBoundingClientRect().top > y;
    });
  }
  function finish(){
    if (ro) ro.disconnect(); ro = null; clearTimeout(timer);
    dispatchEvent(new Event("scroll"));
  }
  function go(){
    var t = target();
    if (!t || moved) return finish();
    t.scrollIntoView({block:"start"});
    clearTimeout(timer);
    timer = setTimeout(function(){
      if (settled(t) || Date.now() - t0 > 15000) { t.scrollIntoView({block:"start"}); finish(); }
      else go();
    }, 1000);
  }
  function start(){
    if (!target() || !window.ResizeObserver) return;
    moved = false; t0 = Date.now();
    /* images above the target: load them now, so they take their height
       before the reader arrives, not while reading */
    var y = target().getBoundingClientRect().top;
    [].forEach.call(document.images, function(im){
      if (im.getBoundingClientRect().top < y) im.loading = "eager";
    });
    if (ro) ro.disconnect();
    ro = new ResizeObserver(go); ro.observe(document.body);
    go();
  }
  start();
  addEventListener("hashchange", start);
  addEventListener("pageshow", function(e){ if (e.persisted) start(); });
})();
