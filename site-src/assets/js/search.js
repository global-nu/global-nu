/* =====================================================================
   search.js — free-form literature search across INSPIRE-HEP, Crossref
   and OpenAlex, plus outbound links to arXiv, ADS and Google Scholar.

   Pure client-side: the visitor's browser talks to the APIs directly.
   Nothing is sent to global-nu.org, no key is embedded, no tracking.

   Only INSPIRE, Crossref and OpenAlex send CORS headers, so only those
   three can be rendered in-page. arXiv, ADS and Scholar are offered as
   prepared queries that open in a new tab.
   ===================================================================== */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var form = $("#lit-form");
  if (!form) return;

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  var elFree     = $("#q-free");
  var elAuthor   = $("#q-author");
  var elTitle    = $("#q-title");
  var elTopic    = $("#q-topic");
  var elFrom     = $("#q-from");
  var elTo       = $("#q-to");
  var elCollab   = $("#q-collab");
  var elSort     = $("#q-sort");
  var elResults  = $("#lit-results");
  var elStatus   = $("#lit-status");
  var elOutbound = $("#lit-outbound");
  var elChips    = $("#lit-chips");

  /* ---------------------------------------------------------------
     1. Parsing the free-form line
     --------------------------------------------------------------- */

  var MONTHS = {
    jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
    jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12
  };

  // Words that are never author surnames even when capitalised.
  var STOP = new Set((
    "a an an the of in on for with without from to by as at or not new " +
    "review lecture notes thesis paper papers preprint about search find " +
    "all any between since after before during last recent latest recently " +
    "year years month months day days week weeks and et al"
  ).split(" "));

  // Subject vocabulary. A leftover word that appears here is a topic; anything
  // else alphabetic is taken as a possible surname — REGARDLESS OF CASE,
  // because people type "lisi marrone juno" in lower case and capitalisation
  // alone is not a usable signal. Wrong guesses are visible in the chips and
  // can be corrected in the fields below.
  var PHYS = new Set((
    "neutrino neutrinos antineutrino oscillation oscillations mixing mass " +
    "masses massless splitting hierarchy ordering flavour flavor lepton " +
    "leptonic leptons quark quarks fermion fermions boson bosons " +
    "seesaw majorana dirac sterile weyl chirality helicity spinor " +
    "cp violation phase phases matrix pmns ckm unitarity " +
    "decay decays beta double neutrinoless bb 0nbb halflife " +
    "solar atmospheric reactor accelerator baseline geoneutrino supernova " +
    "cosmology cosmological cosmic relic cmb structure lensing dark matter " +
    "energy baryon asymmetry leptogenesis nucleosynthesis bbn " +
    "symmetry symmetries modular forms group groups discrete abelian " +
    "invariance invariant orbifold compactification string strings " +
    "gut unification unified proton su so pati salam " +
    "standard model beyond bsm effective field theory eft smeft operator " +
    "interaction interactions nsi coupling couplings yukawa higgs " +
    "renormalization renormalisation loop loops radiative anomaly " +
    "cross section scattering coherent cevns elastic inelastic " +
    "global analysis analyses fit fits bounds constraints limits limit " +
    "precision statistical bayesian likelihood chi2 sensitivity " +
    "detector detectors experiment experiments measurement measurements " +
    "spectrum spectra flux fluxes background signal systematics " +
    "matter msw resonance vacuum propagation coherence decoherence " +
    "physics particle nuclear astroparticle astrophysics phenomenology " +
    "theory theoretical model models mechanism mechanisms scale scales " +
    "quantum relativistic classical electroweak strong weak gauge " +
    "axion axions monopole magnetic moment dipole portal " +
    "prediction predictions correlation correlations degeneracy"
  ).split(" "));

  // Experiment names, recognised so that multi-word ones ("Daya Bay",
  // "Hyper-Kamiokande") survive as a single phrase instead of being split into
  // two capitalised words that then look like surnames.
  //
  // They are routed to the TOPIC field, not to `collaboration`. Typing "JUNO"
  // almost always means "papers about JUNO", whereas INSPIRE's `cn JUNO` means
  // "signed by the JUNO collaboration" — for a phenomenologist those are
  // disjoint sets, and the collaboration reading silently returns nothing.
  // Use the explicit c: prefix when you really want collaboration membership.
  var EXPERIMENTS = [
    "T2K", "NOvA", "DUNE", "JUNO", "Hyper-Kamiokande", "Super-Kamiokande",
    "IceCube", "KM3NeT", "KATRIN", "KamLAND", "KamLAND-Zen", "Daya Bay",
    "Double Chooz", "RENO", "Borexino", "SNO", "MINOS", "MicroBooNE",
    "SBND", "ICARUS", "LEGEND", "GERDA", "CUORE", "nEXO", "EXO-200",
    "ATLAS", "CMS", "LHCb", "ALICE", "Planck", "DESI", "Euclid", "SHiP"
  ];

  function parseFree(raw) {
    var out = { author: [], title: "", topic: [], from: "", to: "", collab: "" };
    if (!raw) return out;
    var s = " " + raw.trim() + " ";

    // --- explicit field prefixes: a:  au:  author:  t:  title:  c:  ---
    s = s.replace(/\b(?:a|au|author)\s*[:=]\s*"([^"]+)"/gi, function (_, v) {
      out.author.push(v.trim()); return " ";
    });
    s = s.replace(/\b(?:a|au|author)\s*[:=]\s*(\S+)/gi, function (_, v) {
      out.author.push(v.trim()); return " ";
    });
    s = s.replace(/\b(?:t|ti|title)\s*[:=]\s*"([^"]+)"/gi, function (_, v) {
      out.title = v.trim(); return " ";
    });
    s = s.replace(/\b(?:c|cn|collab(?:oration)?)\s*[:=]\s*(\S+)/gi, function (_, v) {
      out.collab = v.trim(); return " ";
    });

    // --- quoted phrase becomes the title if none set yet ---
    s = s.replace(/"([^"]+)"/g, function (_, v) {
      if (!out.title) out.title = v.trim(); else out.topic.push(v.trim());
      return " ";
    });

    // --- date expressions, most specific first ---
    // 2019-2023  /  2019..2023  /  2019 to 2023  /  2019->2023
    //
    // The multi-character separators come FIRST in the alternation. With a
    // bare "-" first, "2024->2026" matched "-" and then failed on ">2026", the
    // range rule gave up, and the bare-year rule below silently kept only 2024
    // — a search for 2024–2026 quietly became a search for 2024 alone, in
    // every database at once. Arrow forms are worth accepting: this page's own
    // documentation shows INSPIRE's `de 2023->2025`, so people type it.
    s = s.replace(/\b(19|20)(\d{2})\s*(?:->|→|\.\.|–|—|-|to|through)\s*((?:19|20)\d{2})\b/gi,
      function (_, c, y, y2) {
        out.from = c + y; out.to = y2; return " ";
      });
    // since 2020 / after 2020 / from 2020
    s = s.replace(/\b(?:since|after|from|newer than)\s+((?:19|20)\d{2})\b/gi,
      function (_, y) { out.from = y; return " "; });
    // before 2015 / until 2015 / up to 2015
    s = s.replace(/\b(?:before|until|till|up to|older than)\s+((?:19|20)\d{2})\b/gi,
      function (_, y) { out.to = y; return " "; });
    // last N years / months
    s = s.replace(/\blast\s+(\d{1,2})\s+(year|month)s?\b/gi, function (_, n, unit) {
      var d = new Date();
      if (/year/i.test(unit)) d.setFullYear(d.getFullYear() - parseInt(n, 10));
      else d.setMonth(d.getMonth() - parseInt(n, 10));
      out.from = d.toISOString().slice(0, 10);
      return " ";
    });
    // this year / last year
    s = s.replace(/\bthis year\b/gi, function () {
      out.from = String(new Date().getFullYear()); return " ";
    });
    s = s.replace(/\blast year\b/gi, function () {
      var y = new Date().getFullYear() - 1;
      out.from = String(y); out.to = String(y); return " ";
    });
    // month year  ->  from that month
    s = s.replace(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+((?:19|20)\d{2})\b/gi,
      function (_, mon, y) {
        var m = MONTHS[mon.toLowerCase().slice(0, 3)];
        out.from = y + "-" + String(m).padStart(2, "0");
        return " ";
      });
    // ISO dates
    s = s.replace(/\b((?:19|20)\d{2}-\d{2}(?:-\d{2})?)\b/g, function (_, d) {
      if (!out.from) out.from = d; else if (!out.to) out.to = d;
      return " ";
    });
    // a bare year
    s = s.replace(/\b((?:19|20)\d{2})\b/g, function (_, y) {
      if (!out.from) { out.from = y; out.to = y; }
      return " ";
    });

    // --- arXiv identifier: jump straight to the paper ---
    var ax = s.match(/\b(\d{4}\.\d{4,5})(v\d+)?\b/);
    if (ax) { out.arxivId = ax[1]; s = s.replace(ax[0], " "); }

    // --- experiment names -> topic (see the note on EXPERIMENTS above) ---
    EXPERIMENTS.forEach(function (c) {
      var re = new RegExp("\\b" + c.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&") + "\\b", "i");
      if (re.test(s)) { out.topic.push(c); s = s.replace(re, " "); }
    });

    // --- remaining words: subject vocabulary -> topic, the rest -> surname ---
    var words = s.split(/\s+/).filter(Boolean);
    words.forEach(function (w) {
      var clean = w.replace(/^[.,;("']+|[.,;)"']+$/g, "");
      if (!clean) return;
      var lower = clean.toLowerCase();
      if (STOP.has(lower)) return;
      if (PHYS.has(lower)) { out.topic.push(clean); return; }

      // Purely alphabetic word of decent length, not a known subject term:
      // most likely a surname. Case is deliberately ignored.
      var looksName = /^[a-zà-ÿ'’\-]{3,}$/i.test(clean) && !/\d/.test(clean);
      if (looksName && out.author.length < 4) out.author.push(capitalise(clean));
      else out.topic.push(clean);
    });

    return out;
  }

  // "lisi" -> "Lisi", "van der waals" left alone if already mixed case.
  function capitalise(s) {
    if (s !== s.toLowerCase()) return s;          // user typed some capitals
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  /* ---------------------------------------------------------------
     2. Sync parsed fields into the visible inputs
     --------------------------------------------------------------- */

  var userTouched = {};
  ["author", "title", "topic", "from", "to", "collab"].forEach(function (k) {
    var el = $("#q-" + k);
    if (el) el.addEventListener("input", function () { userTouched[k] = true; });
  });

  function applyParse() {
    var p = parseFree(elFree.value);
    if (!userTouched.author) elAuthor.value = p.author.join("; ");
    if (!userTouched.title)  elTitle.value  = p.title;
    if (!userTouched.topic)  elTopic.value  = p.topic.join(" ");
    if (!userTouched.from)   elFrom.value   = p.from;
    if (!userTouched.to)     elTo.value     = p.to;
    if (!userTouched.collab) elCollab.value = p.collab;
    renderChips(p);
    return p;
  }

  function renderChips(p) {
    var bits = [];
    if (elAuthor.value) bits.push(["Author", elAuthor.value]);
    if (elTitle.value)  bits.push(["Title", elTitle.value]);
    if (elTopic.value)  bits.push(["Topic", elTopic.value]);
    if (elCollab.value) bits.push(["Collaboration", elCollab.value]);
    if (elFrom.value || elTo.value) {
      bits.push(["Dates", (elFrom.value || "…") + " → " + (elTo.value || "…")]);
    }
    if (p && p.arxivId) bits.push(["arXiv ID", p.arxivId]);
    elChips.innerHTML = bits.length
      ? bits.map(function (b) {
          return '<span class="chip"><span class="chip__k">' + esc(b[0]) +
                 '</span>' + esc(b[1]) + "</span>";
        }).join("")
      : '<span class="muted small">Nothing recognised yet — type a query above.</span>';
  }

  elFree.addEventListener("input", function () {
    userTouched = {};
    applyParse();
  });
  ["author", "title", "topic", "from", "to", "collab"].forEach(function (k) {
    var el = $("#q-" + k);
    if (el) el.addEventListener("input", function () { renderChips(null); });
  });

  /* ---------------------------------------------------------------
     3. Query builders, one per backend
     --------------------------------------------------------------- */

  function fields() {
    return {
      author: elAuthor.value.split(";").map(function (s) { return s.trim(); }).filter(Boolean),
      title: elTitle.value.trim(),
      topic: elTopic.value.trim(),
      collab: elCollab.value.trim(),
      from: elFrom.value.trim(),
      to: elTo.value.trim(),
      sort: elSort.value
    };
  }

  function yearOf(s) { var m = /^(\d{4})/.exec(s || ""); return m ? m[1] : ""; }

  // INSPIRE's query language is strict about operators. Verified behaviour:
  //   a <name>            author            works
  //   t "<phrase>"        title phrase      works
  //   cn <name>           collaboration     works
  //   ft <words>          full text         works, forgiving — use for topics
  //   de 2019->2023 / de > 2019 / de < 2015  date ranges
  // Chaining several `t <word>` with AND is far too strict (usually 0 hits),
  // so free keywords go through `ft` instead.
  function inspireQuery(f) {
    var parts = [];
    f.author.forEach(function (a) { parts.push("a " + a); });
    if (f.title) parts.push('t "' + f.title + '"');
    if (f.collab) parts.push("cn " + f.collab);
    if (f.topic) parts.push("ft " + f.topic);
    if (f.from && f.to) parts.push("de " + yearOf(f.from) + "->" + yearOf(f.to));
    else if (f.from) parts.push("de > " + yearOf(f.from));
    else if (f.to) parts.push("de < " + yearOf(f.to));
    return parts.join(" and ");
  }

  function crossrefUrl(f) {
    var p = new URLSearchParams();
    var bib = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (bib) p.set("query.bibliographic", bib);
    if (f.author.length) p.set("query.author", f.author.join(" "));
    var filt = [];
    if (f.from) filt.push("from-pub-date:" + padDate(f.from, true));
    if (f.to) filt.push("until-pub-date:" + padDate(f.to, false));
    if (filt.length) p.set("filter", filt.join(","));
    p.set("rows", "20");
    p.set("select", "title,author,issued,container-title,DOI,URL,type");
    p.set("sort", f.sort === "date" ? "published" : "relevance");
    p.set("order", "desc");
    p.set("mailto", "antonio.marrone@ba.infn.it");
    return "https://api.crossref.org/works?" + p.toString();
  }

  function padDate(s, isStart) {
    if (/^\d{4}$/.test(s)) return s + (isStart ? "-01-01" : "-12-31");
    if (/^\d{4}-\d{2}$/.test(s)) return s + (isStart ? "-01" : "-28");
    return s;
  }

  function openalexUrl(f) {
    var p = new URLSearchParams();
    var search = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (search) p.set("search", search);
    var filt = [];
    if (f.author.length) {
      filt.push("raw_author_name.search:" + f.author.join(" "));
    }
    if (f.from) filt.push("from_publication_date:" + padDate(f.from, true));
    if (f.to) filt.push("to_publication_date:" + padDate(f.to, false));
    if (filt.length) p.set("filter", filt.join(","));
    p.set("per-page", "20");
    p.set("sort", f.sort === "date" ? "publication_date:desc" : "relevance_score:desc");
    p.set("mailto", "antonio.marrone@ba.infn.it");
    return "https://api.openalex.org/works?" + p.toString();
  }

  function arxivUrl(f) {
    var terms = [];
    f.author.forEach(function (a) { terms.push("au:" + quote(a)); });
    if (f.title) terms.push("ti:" + quote(f.title));
    if (f.topic) f.topic.split(/\s+/).forEach(function (w) { terms.push("all:" + w); });
    if (f.collab) terms.push("all:" + quote(f.collab));
    var q = terms.join(" AND ") || "all:neutrino";
    var p = new URLSearchParams({ searchtype: "all", query: q });
    if (f.from) p.set("start_date", padDate(f.from, true));
    if (f.to) p.set("end_date", padDate(f.to, false));
    return "https://arxiv.org/search/?" + p.toString();
  }

  function quote(s) { return /\s/.test(s) ? '"' + s + '"' : s; }

  /* arXiv, reached through DataCite rather than through arXiv's own API.
     Not a workaround for its own sake: export.arxiv.org sends no
     Access-Control-Allow-Origin header, so a browser refuses to read the
     response and the search would simply never return. arXiv registers a DOI
     for every preprint with DataCite (the 10.48550/arXiv.* prefix, client
     `arxiv.content`), and DataCite's API does send CORS and needs no key —
     so this is arXiv's own metadata, deposited by arXiv, fetched from where
     the browser is allowed to read it. */
  /* DataCite runs Elasticsearch query_string, where + - = && || > < ! ( ) { }
     [ ] ^ " ~ * ? : \ / all mean something. Any of them arriving from the free
     text turns a good search into zero results with a cheerful HTTP 200 — no
     error, just nothing — so they are stripped before the query is assembled. */
  function esClean(s) {
    return String(s || "").replace(/[+\-=&|!(){}\[\]^"~*?:\\\/<>]/g, " ")
                          .replace(/\s+/g, " ").trim();
  }

  function dataciteUrl(f) {
    var terms = [];
    f.author.forEach(function (a) {
      var v = esClean(a);
      if (v) terms.push("creators.name:(" + v + ")");
    });
    if (esClean(f.title)) terms.push('titles.title:("' + esClean(f.title) + '")');
    if (esClean(f.topic)) terms.push("(" + esClean(f.topic) + ")");
    if (esClean(f.collab)) terms.push('("' + esClean(f.collab) + '")');
    var q = terms.join(" AND ") || "neutrino";
    if (f.from || f.to) {
      q += " AND publicationYear:[" + (yearOf(f.from) || "1900") +
           " TO " + (yearOf(f.to) || "2100") + "]";
    }
    var p = new URLSearchParams();
    p.set("query", q);
    p.set("client-id", "arxiv.content");
    p.set("page[size]", "20");
    p.set("sort", f.sort === "date" ? "created" : "relevance");
    return "https://api.datacite.org/dois?" + p.toString();
  }

  function fromArxiv(f) {
    return getJSON(dataciteUrl(f)).then(function (d) {
      return (d.data || []).map(function (r) {
        var a = r.attributes || {};
        var doi = (a.doi || "");
        // 10.48550/arxiv.2608.01890 -> 2608.01890
        var id = (/arxiv\.(.+)$/i.exec(doi) || [])[1] || "";
        var issued = (a.dates || []).filter(function (x) {
          return x.dateType === "Issued";
        })[0];
        return {
          source: "arXiv",
          date: (issued && String(issued.date).slice(0, 10)) ||
                (a.publicationYear ? a.publicationYear + "-01-01" : ""),
          title: ((a.titles || [])[0] || {}).title || "(untitled)",
          authors: (a.creators || []).slice(0, 6).map(function (c) {
            return c.name || [c.givenName, c.familyName].filter(Boolean).join(" ");
          }),
          more: (a.creators || []).length > 6,
          year: a.publicationYear || "",
          journal: "arXiv" + (id ? ":" + id : ""),
          arxiv: id,
          links: compact([
            id && { label: "arXiv", href: "https://arxiv.org/abs/" + id },
            id && { label: "PDF", href: "https://arxiv.org/pdf/" + id },
            doi && { label: "DOI", href: "https://doi.org/" + doi }
          ])
        };
      });
    });
  }

  function adsUrl(f) {
    var parts = [];
    f.author.forEach(function (a) { parts.push('author:"' + a + '"'); });
    if (f.title) parts.push('title:"' + f.title + '"');
    if (f.topic) parts.push("abs:(" + f.topic + ")");
    if (f.collab) parts.push('abs:"' + f.collab + '"');
    if (f.from || f.to) {
      parts.push("year:[" + (yearOf(f.from) || "1900") + " TO " +
                 (yearOf(f.to) || "9999") + "]");
    }
    return "https://ui.adsabs.harvard.edu/search/q=" +
           encodeURIComponent(parts.join(" ") || "neutrino");
  }

  function scholarUrl(f) {
    var p = new URLSearchParams();
    p.set("q", [f.title, f.topic, f.collab].filter(Boolean).join(" ") || "neutrino");
    if (f.author.length) p.set("as_sauthors", f.author.join(" "));
    if (yearOf(f.from)) p.set("as_ylo", yearOf(f.from));
    if (yearOf(f.to)) p.set("as_yhi", yearOf(f.to));
    return "https://scholar.google.com/scholar?" + p.toString();
  }

  /* ---------------------------------------------------------------
     4. Fetching and normalising
     --------------------------------------------------------------- */

  function getJSON(url, opts) {
    var ctl = new AbortController();
    var t = setTimeout(function () { ctl.abort(); }, 20000);
    return fetch(url, Object.assign({ signal: ctl.signal }, opts || {}))
      .then(function (r) {
        clearTimeout(t);
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
  }

  function fromInspire(f) {
    var q = inspireQuery(f);
    if (!q) return Promise.resolve([]);
    var p = new URLSearchParams({
      q: q, size: "20", page: "1",
      sort: f.sort === "date" ? "mostrecent" : "mostcited",
      fields: "titles,authors,arxiv_eprints,publication_info,earliest_date," +
              "dois,citation_count,control_number"
    });
    return getJSON("https://inspirehep.net/api/literature?" + p.toString())
      .then(function (d) {
        return (d.hits && d.hits.hits ? d.hits.hits : []).map(function (h) {
          var m = h.metadata || {};
          var pi = (m.publication_info || [])[0] || {};
          var journal = pi.journal_title
            ? pi.journal_title + (pi.journal_volume ? " " + pi.journal_volume : "") +
              (pi.year ? " (" + pi.year + ")" : "")
            : "";
          var ep = (m.arxiv_eprints || [])[0];
          return {
            source: "INSPIRE-HEP",
            date: m.earliest_date || (pi.year ? pi.year + "-01-01" : ""),
            title: (m.titles || [{}])[0].title || "(untitled)",
            authors: (m.authors || []).slice(0, 6).map(function (a) {
              return a.full_name;
            }),
            more: (m.authors || []).length > 6,
            year: pi.year || (m.earliest_date || "").slice(0, 4),
            journal: journal,
            citations: m.citation_count,
            links: compact([
              ep && { label: "arXiv:" + ep.value, href: "https://arxiv.org/abs/" + ep.value },
              (m.dois || [])[0] && { label: "DOI", href: "https://doi.org/" + m.dois[0].value },
              { label: "INSPIRE", href: "https://inspirehep.net/literature/" + m.control_number }
            ])
          };
        });
      });
  }

  function fromCrossref(f) {
    return getJSON(crossrefUrl(f)).then(function (d) {
      return ((d.message && d.message.items) || []).map(function (it) {
        var dp = (it.issued && it.issued["date-parts"] && it.issued["date-parts"][0]) || [];
        return {
          source: "Crossref",
          date: dp.length
            ? dp[0] + "-" + String(dp[1] || 1).padStart(2, "0") +
              "-" + String(dp[2] || 1).padStart(2, "0")
            : "",
          title: (it.title || ["(untitled)"])[0],
          authors: (it.author || []).slice(0, 6).map(function (a) {
            return [a.given, a.family].filter(Boolean).join(" ");
          }),
          more: (it.author || []).length > 6,
          year: it.issued && it.issued["date-parts"] &&
                it.issued["date-parts"][0] ? it.issued["date-parts"][0][0] : "",
          journal: (it["container-title"] || [])[0] || it.type || "",
          links: compact([
            it.DOI && { label: "DOI", href: "https://doi.org/" + it.DOI }
          ])
        };
      });
    });
  }

  function fromOpenAlex(f) {
    return getJSON(openalexUrl(f)).then(function (d) {
      return (d.results || []).map(function (w) {
        var loc = w.primary_location || {};
        return {
          source: "OpenAlex",
          date: w.publication_date ||
                (w.publication_year ? w.publication_year + "-01-01" : ""),
          title: w.title || w.display_name || "(untitled)",
          authors: (w.authorships || []).slice(0, 6).map(function (a) {
            return a.author && a.author.display_name;
          }),
          more: (w.authorships || []).length > 6,
          year: w.publication_year || "",
          journal: (loc.source && loc.source.display_name) || "",
          citations: w.cited_by_count,
          links: compact([
            w.doi && { label: "DOI", href: w.doi },
            loc.landing_page_url && { label: "Publisher", href: loc.landing_page_url }
          ])
        };
      });
    });
  }

  function compact(a) { return a.filter(Boolean); }

  // Newest first. APIs are asked to sort already, but they disagree on what
  // "date" means (INSPIRE: earliest announcement, Crossref: issued, OpenAlex:
  // publication date), so re-sort locally to get one consistent order.
  function byDateDesc(rows) {
    return rows.slice().sort(function (a, b) {
      var da = a.date || (a.year ? a.year + "-01-01" : "");
      var db = b.date || (b.year ? b.year + "-01-01" : "");
      if (!da && !db) return 0;
      if (!da) return 1;
      if (!db) return -1;
      return db.localeCompare(da);
    });
  }

  /* ---------------------------------------------------------------
     Deduplication across databases
     The same paper usually comes back from all three. Merge on DOI,
     then arXiv id, then a normalised title, keeping every source and
     every link.
     --------------------------------------------------------------- */

  function normTitle(s) {
    return String(s || "").toLowerCase()
      .replace(/\$[^$]*\$/g, " ")          // strip inline maths
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function keyOf(r) {
    var doi = "";
    var arx = "";
    r.links.forEach(function (l) {
      if (/doi\.org\//i.test(l.href)) doi = l.href.replace(/^.*doi\.org\//i, "").toLowerCase();
      if (/arxiv\.org\/abs\//i.test(l.href)) arx = l.href.replace(/^.*abs\//i, "").replace(/v\d+$/, "");
    });
    return doi || (arx && "arxiv:" + arx) || "t:" + normTitle(r.title);
  }

  function mergeAll(groups) {
    var byKey = {};
    var order = [];
    groups.forEach(function (g) {
      g.rows.forEach(function (r) {
        var k = keyOf(r);
        if (!byKey[k]) {
          r.sources = [r.source];
          byKey[k] = r;
          order.push(k);
          return;
        }
        var t = byKey[k];
        if (t.sources.indexOf(r.source) === -1) t.sources.push(r.source);
        // keep the richest metadata
        if (!t.journal && r.journal) t.journal = r.journal;
        if (!t.date && r.date) t.date = r.date;
        if (typeof t.citations !== "number" && typeof r.citations === "number") {
          t.citations = r.citations;
        }
        if (r.authors.length > t.authors.length) { t.authors = r.authors; t.more = r.more; }
        r.links.forEach(function (l) {
          var seen = t.links.some(function (x) {
            return x.href.replace(/^https?:\/\//, "") === l.href.replace(/^https?:\/\//, "");
          });
          if (!seen) t.links.push(l);
        });
      });
    });
    return mergeByTitle(order.map(function (k) { return byKey[k]; }));
  }

  /* Second pass, on the title alone.
     The identifier pass above cannot catch everything: the same paper often
     carries the JOURNAL doi in one database and arXiv's own 10.48550 doi in
     another, so the two records get different keys and both survive. That is
     how "Updated bounds on the (1, 2) neutrino oscillation parameters" came
     back twice, once as "(1, 2)" and once as "(1,2)". normTitle already
     flattens punctuation, so a title pass merges them — and it runs second, so
     a matching identifier still takes precedence over a coincidence of words. */
  function mergeByTitle(rows) {
    var byTitle = {};
    var out = [];
    rows.forEach(function (r) {
      var t = normTitle(r.title);
      // Very short titles are not distinctive enough to merge on.
      if (!t || t.length < 25) { out.push(r); return; }
      var first = byTitle[t];
      if (!first) { byTitle[t] = r; out.push(r); return; }
      r.sources.forEach(function (s) {
        if (first.sources.indexOf(s) === -1) first.sources.push(s);
      });
      if (!first.journal && r.journal) first.journal = r.journal;
      if (!first.date && r.date) first.date = r.date;
      if (typeof first.citations !== "number" && typeof r.citations === "number") {
        first.citations = r.citations;
      }
      if (r.authors.length > first.authors.length) {
        first.authors = r.authors; first.more = r.more;
      }
      r.links.forEach(function (l) {
        var seen = first.links.some(function (x) {
          return x.href.replace(/^https?:\/\//, "") === l.href.replace(/^https?:\/\//, "");
        });
        if (!seen) first.links.push(l);
      });
    });
    return out;
  }

  /* ---------------------------------------------------------------
     Match classification
     Buckets, strongest first. What the reader wants to know is not
     which database answered but *why* this paper came back.
     --------------------------------------------------------------- */

  var BUCKETS = [
    { id: "exact",   label: "Exact title match",
      note: "The title you asked for." },
    { id: "authors", label: "All authors present",
      note: "Every surname you listed appears among the authors." },
    { id: "some",    label: "Some authors present",
      note: "At least one of the surnames you listed, but not all." },
    { id: "topic",   label: "Subject match only",
      note: "Matched on topic, title words or collaboration — none of your authors." }
  ];

  function surnameOf(name) {
    var n = String(name || "").trim();
    if (n.indexOf(",") > -1) return n.split(",")[0].trim().toLowerCase();
    var parts = n.split(/\s+/);
    return (parts[parts.length - 1] || "").toLowerCase();
  }

  function classify(r, f) {
    if (f.title) {
      var a = normTitle(r.title), b = normTitle(f.title);
      if (a === b || (b.length > 12 && a.indexOf(b) > -1)) return "exact";
    }
    if (!f.author.length) return "topic";

    var have = r.authors.map(surnameOf);
    var hit = 0;
    f.author.forEach(function (want) {
      var w = surnameOf(want);
      if (have.some(function (h) { return h === w || h.indexOf(w) === 0; })) hit++;
    });
    if (hit === 0) return "topic";
    return hit === f.author.length ? "authors" : "some";
  }

  /* ---------------------------------------------------------------
     Rendering
     --------------------------------------------------------------- */

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // "2025-03-10" -> "Mar 2025";  "2025" -> "2025"
  function prettyDate(s) {
    var m = /^(\d{4})(?:-(\d{2}))?/.exec(s);
    if (!m) return s;
    return m[2] ? MON[parseInt(m[2], 10) - 1] + " " + m[1] : m[1];
  }

  var SRC_CLASS = {
    "INSPIRE-HEP": "src--inspire",
    "Crossref": "src--crossref",
    "OpenAlex": "src--openalex"
  };

  function renderItem(r) {
    var authors = r.authors.filter(Boolean).join(", ") + (r.more ? ", et al." : "");
    var when = r.date || (r.year ? String(r.year) : "");
    var meta = compact([
      when && '<time class="pub__year" datetime="' + esc(when) + '">' +
              esc(prettyDate(when)) + "</time>",
      r.journal && '<span class="journal">' + esc(r.journal) + "</span>",
      typeof r.citations === "number" &&
        '<span class="muted">' + r.citations + " citations</span>"
    ]).join("");
    var links = r.links.map(function (l) {
      return '<a href="' + esc(l.href) + '" target="_blank" rel="noopener noreferrer">' +
             esc(l.label) + "</a>";
    }).join("");
    var srcs = (r.sources || [r.source]).map(function (s) {
      return '<span class="src ' + (SRC_CLASS[s] || "") + '">' + esc(s) + "</span>";
    }).join("");
    var first = r.links[0];
    var title = first
      ? '<a class="pub__title" href="' + esc(first.href) +
        '" target="_blank" rel="noopener noreferrer">' + esc(r.title) + "</a>"
      : '<span class="pub__title">' + esc(r.title) + "</span>";
    return "<li>" + title +
           '<div class="pub__authors">' + esc(authors) + "</div>" +
           '<div class="pub__ref">' + meta + links + '<span class="src-row">' +
           srcs + "</span></div></li>";
  }

  function renderBuckets(rows, f, failures) {
    var out = [];

    if (failures.length) {
      out.push('<div class="notice"><p>' +
        failures.map(function (x) {
          return esc(x.name) + " unavailable (" + esc(x.err.message) + ")";
        }).join("; ") +
        ". The outbound buttons above still work.</p></div>");
    }

    if (!rows.length) {
      out.push('<p class="muted">No results. Try loosening the query or widening the dates.</p>');
      return out.join("");
    }

    BUCKETS.forEach(function (b) {
      var group = rows.filter(function (r) { return r.bucket === b.id; });
      if (!group.length) return;
      out.push(
        '<section class="lit-bucket lit-bucket--' + b.id + '">' +
        '<h3 class="lit-group">' + esc(b.label) +
        '<span class="count">' + group.length + "</span></h3>" +
        '<p class="lit-group__note">' + esc(b.note) + "</p>" +
        '<ul class="publist">' + group.map(renderItem).join("") + "</ul></section>");
    });
    return out.join("");
  }

  function renderOutbound(f, parsed) {
    var links = [
      ["arXiv", arxivUrl(f), "btn--cyan"],
      ["NASA ADS", adsUrl(f), "btn--ghost"],
      ["Google Scholar", scholarUrl(f), "btn--ghost"],
      ["INSPIRE (site)",
       "https://inspirehep.net/search?q=" + encodeURIComponent(inspireQuery(f)),
       "btn--ghost"]
    ];
    if (parsed && parsed.arxivId) {
      links.unshift(["Open arXiv:" + parsed.arxivId,
                     "https://arxiv.org/abs/" + parsed.arxivId, ""]);
    }
    elOutbound.innerHTML = links.map(function (l) {
      return '<a class="btn btn--sm ' + l[2] + '" href="' + esc(l[1]) +
             '" target="_blank" rel="noopener noreferrer">' + esc(l[0]) + " ↗</a>";
    }).join("");
  }

  /* ---------------------------------------------------------------
     Wiring
     --------------------------------------------------------------- */

  function run(ev) {
    if (ev) ev.preventDefault();
    var parsed = applyParse();
    var f = fields();

    if (!f.author.length && !f.title && !f.topic && !f.collab) {
      elStatus.textContent = "Type something to search — an author, a title, a topic, a year.";
      elResults.innerHTML = "";
      elOutbound.innerHTML = "";
      return;
    }

    renderOutbound(f, parsed);
    elStatus.innerHTML = '<span class="spin" aria-hidden="true"></span> Querying the databases …';
    elResults.innerHTML = "";

    // Bring the results area into view and give it focus, so the answer is
    // where the eye already is — and so keyboard and screen-reader users land
    // on it too rather than being left at the top of the form.
    var pane = document.getElementById("lit-pane") || elStatus;
    pane.scrollIntoView({
      behavior: reducedMotion() ? "auto" : "smooth",
      block: "start"
    });
    elStatus.setAttribute("tabindex", "-1");
    elStatus.focus({ preventScroll: true });

    var wanted = [];
    if ($("#src-inspire").checked) wanted.push(["INSPIRE-HEP", fromInspire(f)]);
    if ($("#src-crossref").checked) wanted.push(["Crossref", fromCrossref(f)]);
    if ($("#src-openalex").checked) wanted.push(["OpenAlex", fromOpenAlex(f)]);
    if ($("#src-arxiv") && $("#src-arxiv").checked) wanted.push(["arXiv", fromArxiv(f)]);

    if (!wanted.length) {
      elStatus.textContent = "Select at least one database.";
      return;
    }

    // Grouping is by match quality across all databases, so nothing can be
    // drawn until every request has settled.
    var settled = wanted.map(function (w) {
      return w[1].then(
        function (rows) { return { name: w[0], rows: rows }; },
        function (err) { return { name: w[0], rows: [], err: err }; }
      );
    });

    Promise.all(settled).then(function (groups) {
      var failures = groups.filter(function (g) { return g.err; })
                           .map(function (g) { return { name: g.name, err: g.err }; });
      var ok = groups.filter(function (g) { return !g.err; });

      var rows = mergeAll(ok);
      rows.forEach(function (r) { r.bucket = classify(r, f); });
      if (f.sort === "date") rows = byDateDesc(rows);

      elResults.innerHTML = renderBuckets(rows, f, failures);

      var found = ok.reduce(function (n, g) { return n + g.rows.length; }, 0);
      var merged = found - rows.length;
      elStatus.textContent = rows.length
        ? rows.length + " papers from " + ok.length + " database" +
          (ok.length > 1 ? "s" : "") +
          (merged > 0 ? " (" + merged + " duplicate records merged)" : "") +
          ". Links open in a new tab."
        : (failures.length ? "No database could be reached."
                           : "No results. Try loosening the query or widening the dates.");
    });
  }

  form.addEventListener("submit", run);

  $("#lit-clear").addEventListener("click", function () {
    form.reset();
    userTouched = {};
    elResults.innerHTML = "";
    elOutbound.innerHTML = "";
    elStatus.textContent = "";
    renderChips(null);
    elFree.focus();
  });

  // Example queries
  Array.prototype.forEach.call(document.querySelectorAll("[data-example]"), function (b) {
    b.addEventListener("click", function (e) {
      e.preventDefault();
      elFree.value = b.getAttribute("data-example");
      userTouched = {};
      applyParse();
      run();
    });
  });

  // Prefill from ?q= so searches can be linked to.
  var qs = new URLSearchParams(location.search).get("q");
  if (qs) { elFree.value = qs; applyParse(); run(); }
  else renderChips(null);
})();
