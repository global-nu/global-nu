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
  var elResults  = $("#lit-results");
  var elSortBar  = $("#lit-sort");
  var elFilters  = $("#lit-filters");
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

  // Words that are never author surnames even when capitalised. Two fates:
  // DROP is search grammar that carries no meaning for any database; KIND is
  // the document type the reader is after ("lecture notes", "review") — it
  // used to be dropped with the grammar, which silently turned "lecture
  // notes string theory" into a bare "string theory" search. KIND words are
  // real query terms: they go to the topic, just never to an author guess.
  var DROP = new Set((
    "a an an the of in on for with without from to by as at or not new " +
    "paper papers preprint about search find " +
    "all any between since after before during last recent latest recently " +
    "year years month months day days week weeks and et al"
  ).split(" "));
  var KIND = new Set((
    "review reviews lecture lectures notes note thesis theses " +
    "introduction introductory course courses primer textbook textbooks " +
    "pedagogical school schools"
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
      if (DROP.has(lower)) return;
      if (KIND.has(lower)) { out.topic.push(lower); return; }
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
      // What the DATABASES are asked for, which is not the same question as
      // how the answer is displayed. Only the date axis is worth pushing
      // upstream: asking for the most recent records genuinely changes which
      // twenty come back. Citations are not pushed — see the note above
      // SORTS — and neither is a subfield, which no database indexes the way
      // this page groups it.
      sort: sortKey === "date" ? "date" : "relevance"
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
    // Topic terms: BARE when they are the whole query, `ft` otherwise.
    // Verified live, both ways: "lecture notes string theory" bare returns
    // the Les Houches notes ranked by true relevance, while the ft version
    // matches any long review that cites lecture notes and, sorted by
    // citations, buried the target under Quantum Entanglement; but
    // "a Feruglio and modular forms" bare (or with abs/parentheses) is 0
    // hits — with an author clause only `ft` combines. Date clauses chain
    // fine with bare terms (also verified).
    if (f.topic) parts.push(parts.length ? "ft " + f.topic : f.topic);
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
    p.set("select", "title,author,issued,container-title,DOI,URL,type,subject");
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
    // Physical Sciences only (domain 3 in OpenAlex's topic hierarchy —
    // verified live: "string theory" drops from every field of knowledge to
    // 367k physics records). OpenAlex indexes everything; this page is on a
    // physics site and marketing papers matching the word "theory" are how
    // a search for lecture notes once returned the Theory of Planned
    // Behaviour.
    var filt = ["primary_topic.domain.id:3"];
    if (f.author.length) {
      filt.push("raw_author_name.search:" + f.author.join(" "));
    }
    if (f.from) filt.push("from_publication_date:" + padDate(f.from, true));
    if (f.to) filt.push("to_publication_date:" + padDate(f.to, false));
    p.set("filter", filt.join(","));
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

  /* DataCite carries arXiv's subject headings as prose with the category
     identifier in brackets — "High Energy Physics - Experiment (hep-ex)",
     under subjectScheme "arXiv". The bracket is the part that means
     something; the prose is the same string in every record. Anything
     deposited under another scheme (DataCite adds "FOS: Physical sciences")
     is not an arXiv category and is left alone. */
  function arxivSubjects(list) {
    var out = [];
    (list || []).forEach(function (x) {
      if (!x || String(x.subjectScheme || "").toLowerCase() !== "arxiv") return;
      var m = /\(([a-z-]+(?:\.[a-z-]+)?)\)\s*$/i.exec(String(x.subject || ""));
      if (m && out.indexOf(m[1].toLowerCase()) === -1) out.push(m[1].toLowerCase());
    });
    return out;
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
          cats: arxivSubjects(a.subjects),
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
      fields: "titles,authors,arxiv_eprints,publication_info,earliest_date," +
              "dois,citation_count,control_number,inspire_categories"
    });
    // Relevance mode leaves INSPIRE's own ranking alone: sort=mostcited
    // turned every topic search into "the most cited papers that mention
    // these words", which for "lecture notes string theory" was Quantum
    // Entanglement and the PDG Review.
    if (f.sort === "date") p.set("sort", "mostrecent");
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
            citeFrom: typeof m.citation_count === "number" ? CITE_SOURCE : "",
            // Both classifications INSPIRE holds: the arXiv categories the
            // preprint was deposited under, and INSPIRE's own subject terms
            // (Phenomenology-HEP, Experiment-HEP, Astrophysics, …), which are
            // the only ones a record with no eprint carries.
            cats: (ep && ep.categories) || [],
            inspireCats: (m.inspire_categories || []).map(function (c) {
              return c.term;
            }),
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
          // Present only when the publisher deposited it, which for physics
          // journals is most of the time not at all. Free when it is there.
          crSubjects: it.subject || [],
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
          // OpenAlex classifies every work in a four-level hierarchy
          // (domain > field > subfield > topic). The topic is the useful
          // level — "Neutrino Physics Research" is a topic, while its
          // subfield is the much coarser "Nuclear and High Energy Physics".
          topic: (w.primary_topic && w.primary_topic.display_name) || "",
          topicField: (w.primary_topic && w.primary_topic.subfield &&
                       w.primary_topic.subfield.display_name) || "",
          links: compact([
            w.doi && { label: "DOI", href: w.doi },
            loc.landing_page_url && { label: "Publisher", href: loc.landing_page_url }
          ])
        };
      });
    });
  }

  /* Semantic Scholar, keyless Graph API with fieldsOfStudy=Physics. The
     shared anonymous pool rate-limits aggressively (HTTP 429); the failure
     is reported like any other source and the search still answers from the
     rest. */
  function s2Url(f) {
    var q = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (f.author.length) q = (q ? q + " " : "") + f.author.join(" ");
    var p = new URLSearchParams();
    p.set("query", q || "neutrino");
    p.set("fieldsOfStudy", "Physics");
    p.set("fields", "paperId,title,authors,year,publicationDate,venue," +
                    "externalIds,citationCount,s2FieldsOfStudy");
    p.set("limit", "20");
    if (yearOf(f.from) || yearOf(f.to)) {
      p.set("year", (yearOf(f.from) || "") + "-" + (yearOf(f.to) || ""));
    }
    return "https://api.semanticscholar.org/graph/v1/paper/search?" + p.toString();
  }

  function fromS2(f) {
    return getJSON(s2Url(f)).then(function (d) {
      return (d.data || []).map(function (w) {
        var ext = w.externalIds || {};
        return {
          source: "Semantic Scholar",
          date: w.publicationDate || (w.year ? w.year + "-01-01" : ""),
          title: w.title || "(untitled)",
          authors: (w.authors || []).slice(0, 6).map(function (a) { return a.name; }),
          more: (w.authors || []).length > 6,
          year: w.year || "",
          journal: w.venue || "",
          citations: w.citationCount,
          s2fields: (w.s2FieldsOfStudy || []).map(function (x) {
            return x && x.category;
          }).filter(Boolean),
          links: compact([
            ext.ArXiv && { label: "arXiv", href: "https://arxiv.org/abs/" + ext.ArXiv },
            ext.DOI && { label: "DOI", href: "https://doi.org/" + ext.DOI },
            w.paperId && { label: "Semantic Scholar",
                           href: "https://www.semanticscholar.org/paper/" + w.paperId }
          ])
        };
      });
    });
  }

  function compact(a) { return a.filter(Boolean); }

  /* ---------------------------------------------------------------
     Sanity filters on what the databases return
     --------------------------------------------------------------- */

  // Crossref carries records "issued" in 2114. With the date sort those
  // float above every real paper, so an implausible year loses its date and
  // sinks instead.
  var THIS_YEAR = new Date().getFullYear();
  function plausibleYear(y) {
    y = parseInt(y, 10);
    return y >= 1800 && y <= THIS_YEAR + 1;
  }
  function saneDates(r) {
    if (r.date && !plausibleYear(r.date.slice(0, 4))) r.date = "";
    if (r.year && !plausibleYear(r.year)) r.year = "";
    return r;
  }

  // INSPIRE and arXiv are physics by construction; Crossref and OpenAlex
  // index every field of knowledge and their relevance ranking returns
  // anything containing one query word ("theory" -> Theory of Planned
  // Behaviour). A record that ONLY generic databases returned must show the
  // substantive query terms in its title or venue: all of them for short
  // queries, all but one when four or more.
  var PHYSICS_NATIVE = { "INSPIRE-HEP": 1, "arXiv": 1, "Semantic Scholar": 1 };
  function passesTermGate(r, terms) {
    if (!terms.length) return true;
    var hay = " " + normTitle(r.title + " " + (r.journal || "")) + " ";
    var hit = terms.filter(function (t) {
      return hay.indexOf(" " + t + " ") > -1 || hay.indexOf(t) > -1;
    }).length;
    var need = terms.length >= 4 ? terms.length - 1 : terms.length;
    return hit >= need;
  }
  function gateTerms(f) {
    return normTitle(f.topic + " " + f.title).split(" ")
      .filter(function (t) { return t.length >= 3 && !DROP.has(t); });
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

  /* Subject information is per-database and none of them has it all:
     INSPIRE knows the arXiv categories and its own subject terms, OpenAlex
     knows its topic, Semantic Scholar its fields of study, Crossref whatever
     the publisher deposited. A merged record must keep every one of them, or
     the subfield of a paper would depend on which database happened to be
     first in the list rather than on what is known about the paper. */
  var TAG_LISTS = ["cats", "inspireCats", "s2fields", "crSubjects"];

  /* A count from INSPIRE always wins, whichever record happened to lead the
     merge. Without this the number depended on the order the databases
     answered in: the same paper showed 93 from INSPIRE or 147 from OpenAlex
     depending on which one had led. See the note above `fillCitations`. */
  function mergeCitations(target, other) {
    if (other.citeFrom === CITE_SOURCE) {
      target.citations = other.citations;
      target.citeFrom = other.citeFrom;
      return;
    }
    if (target.citeFrom === CITE_SOURCE) return;
    if (typeof target.citations !== "number" && typeof other.citations === "number") {
      target.citations = other.citations;
    }
  }

  function mergeTags(target, other) {
    TAG_LISTS.forEach(function (k) {
      if (!other[k] || !other[k].length) return;
      var have = target[k] || [];
      other[k].forEach(function (v) {
        if (v && have.indexOf(v) === -1) have.push(v);
      });
      target[k] = have;
    });
    if (!target.topic && other.topic) target.topic = other.topic;
    if (!target.topicField && other.topicField) target.topicField = other.topicField;
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
        mergeCitations(t, r);
        mergeTags(t, r);
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
      mergeCitations(first, r);
      mergeTags(first, r);
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
     Citations come from INSPIRE, and from nowhere else

     Every database here counts citations, and they do not agree — the same
     paper is 93 at INSPIRE, a different number at OpenAlex, a third at
     Semantic Scholar, because they index different literature. Mixed into one
     column those numbers are not comparable, and the "Citations" sort stops
     meaning anything: it would rank a paper high for being indexed by the
     most generous counter rather than for being used. For high-energy physics
     INSPIRE is the count the field actually quotes, so it is the only one
     this page shows.

     Two consequences, both deliberate:

       * a record INSPIRE returned carries INSPIRE's number, whichever
         database led the merge (see `mergeCitations`);
       * a record INSPIRE did NOT return is looked up here, by arXiv id or
         DOI, in one extra request per twenty records. INSPIRE answers 20
         results per search, so a paper it knows perfectly well is often
         simply not among the twenty it sent back — dropping its count for
         that reason would be an artefact of the page size, not a fact about
         the paper.

     What no lookup finds keeps NO count at all rather than borrowing one:
     an empty cell is honest, a foreign number wearing INSPIRE's meaning is
     not. Such a record sorts as unknown, which puts it at the bottom in both
     directions — the same rule undated records follow.

     With INSPIRE unticked in "Search in", no count is shown anywhere: the
     reader has asked not to use the one source this page trusts for them.
     --------------------------------------------------------------- */

  var CITE_SOURCE = "INSPIRE-HEP";
  var CITE_BATCH = 20;          // ids per lookup request
  var CITE_MAX_REQUESTS = 3;    // never more than 60 records looked up

  // The identifier INSPIRE can be asked by. arXiv first: it is the one a
  // preprint always has, and it needs no escaping. A DOI may contain
  // brackets (10.1007/JHEP09(2020)178) — verified to work as written.
  function citeTerm(r) {
    var doi = "", arx = "";
    (r.links || []).forEach(function (l) {
      if (!arx && /arxiv\.org\/abs\//i.test(l.href)) {
        arx = l.href.replace(/^.*abs\//i, "").replace(/v\d+$/, "");
      }
      if (!doi && /doi\.org\//i.test(l.href)) {
        doi = l.href.replace(/^.*doi\.org\//i, "");
      }
    });
    if (arx) return { term: "arxiv " + arx, key: arx.toLowerCase() };
    if (doi) return { term: "doi " + doi, key: doi.toLowerCase() };
    return null;
  }

  function fillCitations(rows, useInspire) {
    rows.forEach(function (r) {
      if (r.citeFrom !== CITE_SOURCE) delete r.citations;
    });
    if (!useInspire) return Promise.resolve();

    var want = [];
    rows.forEach(function (r) {
      if (r.citeFrom === CITE_SOURCE) return;
      var t = citeTerm(r);
      if (t) want.push({ row: r, term: t.term, key: t.key });
    });
    if (!want.length) return Promise.resolve();

    var batches = [];
    for (var i = 0; i < want.length; i += CITE_BATCH) {
      if (batches.length >= CITE_MAX_REQUESTS) break;
      batches.push(want.slice(i, i + CITE_BATCH));
    }

    return Promise.all(batches.map(function (b) {
      var p = new URLSearchParams({
        q: b.map(function (x) { return x.term; }).join(" or "),
        size: String(b.length),
        fields: "citation_count,dois,arxiv_eprints"
      });
      return getJSON("https://inspirehep.net/api/literature?" + p.toString())
        .then(function (d) {
          var by = {};
          (d.hits && d.hits.hits ? d.hits.hits : []).forEach(function (h) {
            var m = h.metadata || {};
            if (typeof m.citation_count !== "number") return;
            (m.dois || []).forEach(function (x) {
              by[String(x.value).toLowerCase()] = m.citation_count;
            });
            (m.arxiv_eprints || []).forEach(function (x) {
              by[String(x.value).toLowerCase()] = m.citation_count;
            });
          });
          b.forEach(function (x) {
            if (typeof by[x.key] === "number") {
              x.row.citations = by[x.key];
              x.row.citeFrom = CITE_SOURCE;
            }
          });
        }, function () {
          // A failed lookup leaves those rows without a count, which is the
          // same state they were in a moment ago. It must never take the
          // search down with it.
        });
    }));
  }

  /* ---------------------------------------------------------------
     Subfield classification

     Which corner of physics a paper belongs to. The scheme is not invented
     here: it is the arXiv subject taxonomy (arxiv.org/category_taxonomy) —
     the classification the papers were actually deposited under — collapsed
     into the handful of groups a reader of this page separates by eye. Each
     database is asked for whatever part of it it holds:

       INSPIRE           arxiv_eprints[].categories, plus its own
                         inspire_categories (Phenomenology-HEP,
                         Experiment-HEP, Astrophysics, Gravitation and
                         Cosmology, Theory-Nucl, Instrumentation, …), which
                         is the only classification a record with no eprint
                         carries
       arXiv / DataCite  subjects deposited under subjectScheme "arXiv"
       OpenAlex          primary_topic, from its domain/field/subfield/topic
                         hierarchy
       Semantic Scholar  s2FieldsOfStudy
       Crossref          subject, when the publisher deposited any

     NEUTRINO PHYSICS IS NOT AN ARXIV CATEGORY. It runs through hep-ph,
     hep-ex, astro-ph.HE and nucl-ex at once — which is precisely why a page
     on this site needs it as a group of its own. So it is decided separately
     — from OpenAlex's topic, or from the words of the title and of the venue,
     the venue being how a proceedings volume of a neutrino conference gives
     its own subject away — and it OUTRANKS the arXiv bucket: a hep-ph paper
     on oscillations belongs under neutrinos, not under phenomenology.

     The label is a reading aid over the results of one search. It is not a
     claim about the paper beyond what the databases themselves say, and a
     record none of them classified is shown as Unclassified rather than
     guessed into a group.
     --------------------------------------------------------------- */

  var SUBFIELDS = [
    { id: "neutrino", label: "Neutrino physics" },
    { id: "hep-ph",   label: "Particle phenomenology" },
    { id: "hep-ex",   label: "Particle experiment" },
    { id: "hep-th",   label: "Fields, strings & math. physics" },
    { id: "nucl",     label: "Nuclear physics" },
    { id: "astro-he", label: "Astroparticle & HE astrophysics" },
    { id: "cosmo",    label: "Cosmology & gravitation" },
    { id: "astro",    label: "Astronomy & astrophysics" },
    { id: "instr",    label: "Instrumentation & data" },
    { id: "other",    label: "Other physics" },
    { id: "none",     label: "Unclassified" }
  ];

  var SUBFIELD_LABEL = {};
  var SUBFIELD_ORDER = {};
  SUBFIELDS.forEach(function (s, i) {
    SUBFIELD_LABEL[s.id] = s.label;
    SUBFIELD_ORDER[s.id] = i;
  });

  // arXiv category -> group, keys lower case. A category with a subdivision
  // ("astro-ph.co") is looked up whole and then by its archive alone, so a
  // subdivision arXiv adds after this was written lands in its archive's
  // group instead of falling through to "other".
  var ARXIV_GROUP = {
    "hep-ph": "hep-ph",
    "hep-ex": "hep-ex",
    "hep-th": "hep-th", "hep-lat": "hep-th", "math-ph": "hep-th",
    "nucl-th": "nucl", "nucl-ex": "nucl",
    "astro-ph.he": "astro-he",
    "astro-ph.co": "cosmo", "gr-qc": "cosmo",
    "astro-ph": "astro", "astro-ph.ga": "astro",
    "astro-ph.sr": "astro", "astro-ph.ep": "astro",
    "astro-ph.im": "instr", "physics.ins-det": "instr",
    "physics.acc-ph": "instr", "physics.data-an": "instr",
    "physics.comp-ph": "instr"
  };

  // INSPIRE's own subject terms, lower-cased. Verified against the live API
  // rather than recalled: a record's inspire_categories[].term.
  var INSPIRE_GROUP = {
    "phenomenology-hep": "hep-ph",
    "experiment-hep": "hep-ex",
    "theory-hep": "hep-th",
    "lattice": "hep-th",
    "math and math physics": "hep-th",
    "theory-nucl": "nucl",
    "experiment-nucl": "nucl",
    "astrophysics": "astro-he",
    "gravitation and cosmology": "cosmo",
    "instrumentation": "instr",
    "accelerators": "instr",
    "computing": "instr",
    "general physics": "other",
    "other": "other"
  };

  // Word boundaries, not substrings: "neutron" is not "neutrino", and a
  // title that merely contains the letters is not a neutrino paper. The
  // spellings are those that actually appear in titles in this field.
  var NU_RE = new RegExp(
    "\\b(?:neutrino|neutrinos|neutrino's|antineutrino|antineutrinos|" +
    "neutrinoless|cevns|pmns|majoron|majorons)\\b" +
    "|\\bdouble[\\s-]beta\\b|0\\u03bd\\u03b2\\u03b2|\\b0nubb\\b", "i");

  // Last resort, on OpenAlex's topic wording and Semantic Scholar's fields.
  // Ordered: the first pattern that matches wins, so the narrower subjects
  // are listed before the ones whose words they contain.
  var TOPIC_GROUP = [
    [/dark matter|cosmic ray|astroparticle|gamma-ray|high[\s-]energy astro/i, "astro-he"],
    [/cosmolog|dark energy|inflation|cosmic microwave|gravitation|relativit/i, "cosmo"],
    [/astronom|galax|stellar|solar physic|planet/i, "astro"],
    [/nuclear/i, "nucl"],
    [/string theory|quantum field|supersymmetr|conformal|lattice|mathematical physic/i, "hep-th"],
    [/particle|collider|chromodynamic|hadron|standard model|quark/i, "hep-ph"],
    [/detector|instrument|accelerator|data analysis/i, "instr"],
    [/physics/i, "other"]
  ];

  function subfieldOf(r) {
    var i;
    if (NU_RE.test(String(r.title || "") + " " + String(r.journal || ""))) {
      return "neutrino";
    }
    if (/neutrino/i.test(r.topic || "")) return "neutrino";

    var cats = (r.cats || []).map(function (c) { return String(c).toLowerCase(); });
    for (i = 0; i < cats.length; i++) {
      var g = ARXIV_GROUP[cats[i]] || ARXIV_GROUP[cats[i].split(".")[0]];
      if (!g && /^(?:physics|quant-ph|cond-mat|nlin|math)/.test(cats[i])) g = "other";
      if (g) return g;
    }

    var ins = (r.inspireCats || []).map(function (c) { return String(c).toLowerCase(); });
    for (i = 0; i < ins.length; i++) {
      if (INSPIRE_GROUP[ins[i]]) return INSPIRE_GROUP[ins[i]];
    }

    var words = [r.topic, r.topicField].concat(r.s2fields || [], r.crSubjects || [])
                  .filter(Boolean).join(" ");
    for (i = 0; i < TOPIC_GROUP.length; i++) {
      if (TOPIC_GROUP[i][0].test(words)) return TOPIC_GROUP[i][1];
    }
    return "none";
  }

  /* ---------------------------------------------------------------
     Relevance

     Each database ranks in its own way, over its own subset. Once the
     answers are merged those rankings cannot be compared — the third hit at
     OpenAlex and the third at INSPIRE are not equally good — so an order
     that means the same thing for every row has to be computed here, from
     the query and the record alone. Deliberately simple and bounded, and
     every term is something visible in the row itself:

       up to 45   the authors asked for, by the fraction actually present
       up to 40   the title asked for: 40 when it matches, 25 when contained
       up to 25   the topic words, by the fraction found in title or venue
                  (a word found only in the journal name counts two fifths)
              8   a collaboration name matched
       up to 12   corroboration: 4 for each database that returned the record

     TWO NUMBERS, NOT ONE. Citations and age are returned separately and are
     consulted ONLY when the match score is exactly equal — a genuine
     tie-break, not a term. They were a term once, worth up to 10 and 2
     points, and that quietly made this page do the thing the rest of the
     file exists to avoid: a paper with 20 000 citations matching four query
     words out-ranked one with none matching all five. The page says
     citations only break ties, and this is what makes that sentence true.
     Sorting BY citations is a button of its own, where it is the question.
     --------------------------------------------------------------- */

  function relevance(r, f, terms) {
    var s = 0;
    if (f.author.length) {
      var have = r.authors.map(surnameOf);
      var hit = 0;
      f.author.forEach(function (want) {
        var w = surnameOf(want);
        if (have.some(function (h) { return h === w || h.indexOf(w) === 0; })) hit++;
      });
      s += 45 * (hit / f.author.length);
    }
    if (f.title) {
      var a = normTitle(r.title), b = normTitle(f.title);
      if (a === b) s += 40;
      else if (b.length > 12 && a.indexOf(b) > -1) s += 25;
    }
    if (terms.length) {
      var inTitle = " " + normTitle(r.title) + " ";
      var inVenue = " " + normTitle(r.journal || "") + " ";
      var n = 0;
      terms.forEach(function (t) {
        if (inTitle.indexOf(t) > -1) n += 1;
        else if (inVenue.indexOf(t) > -1) n += 0.4;
      });
      s += 25 * Math.min(1, n / terms.length);
    }
    if (f.collab) {
      var hay = normTitle(r.title + " " + (r.journal || ""));
      if (hay.indexOf(normTitle(f.collab)) > -1) s += 8;
    }
    s += Math.min(12, 4 * (r.sources || [r.source]).length);
    return s;
  }

  /* The tie-break, on the same bounded scale, consulted only when two rows
     score exactly the same match. Ten points of citations against two of
     recency: between two papers the query cannot tell apart, the one the
     field has actually used comes first. */
  function tieBreak(r) {
    var t = 0;
    if (typeof r.citations === "number" && r.citations > 0) {
      t += Math.min(10, 4 * Math.log(1 + r.citations) / Math.LN10);
    }
    var y = parseInt(String(r.date || r.year || "").slice(0, 4), 10);
    if (y && y >= THIS_YEAR - 3) t += 2;
    return t;
  }

  /* ---------------------------------------------------------------
     Ordering

     Four keys, each reversible. The ordering is applied HERE, to the merged
     set already on the page, and changing it never refetches: the answer is
     already downloaded, and a click that costs five API calls to reorder
     twenty rows the reader is looking at would be a worse page.

     Which also fixes what "most cited" can honestly mean. Asking INSPIRE for
     sort=mostcited does not return the most cited papers ON the subject, it
     returns the most cited papers that MENTION the words — the failure this
     file already records for topic searches (see fromInspire). The databases
     are therefore always asked for their own best matches; the citation
     ranking is over that set, and the status line says how large it is.

     A record missing the key sinks to the bottom in BOTH directions. It is
     not "the smallest year", and floating undated records to the top of an
     ascending sort would be a bug dressed as an order.
     --------------------------------------------------------------- */

  // One key for time, not two. There were a "Year" and a "Month" button, and
  // the pair was a distinction without a use: the same question asked at two
  // resolutions, where the finer one answers the coarser as well. A record
  // known only to the year sorts at its January, so nothing is lost.
  var SORTS = [
    { id: "relevance", label: "Relevance",
      down: "best match first", up: "weakest match first" },
    { id: "date", label: "Date",
      down: "newest first", up: "oldest first" },
    { id: "citations", label: "Citations",
      down: "most cited first", up: "least cited first" },
    { id: "subfield", label: "Subfield",
      down: "largest group first", up: "smallest group first" }
  ];

  var sortKey = "relevance";
  var sortDir = -1;                 // -1 descending, +1 ascending
  var hidden = {};                  // subfield id -> true when filtered out

  // "2025-03-10" and a bare "2025" both order; a year alone is placed at its
  // January, which is where a record that only says "2025" belongs — that is
  // also what lets ONE key do the work: a record known only to the year still
  // sorts against records known to the day, instead of needing a coarser
  // button of its own.
  function dateKey(r) {
    var d = r.date || (r.year ? String(r.year) + "-01-01" : "");
    if (!/^\d{4}/.test(d)) return null;
    return (d + "-01-01").slice(0, 10);
  }

  function citeKey(r) {
    return typeof r.citations === "number" ? r.citations : null;
  }

  // Best match first, then the tie-break. The direction is NOT applied here:
  // this is what "equal for the chosen key" falls back to, and a reader
  // sorting by year ascending still wants the better match first among the
  // papers of one year.
  function byMatch(a, b) {
    return (b.score - a.score) || (b.tie - a.tie);
  }

  function compareBy(key, dir) {
    return function (a, b) {
      var ka, kb;
      if (key === "date") { ka = dateKey(a); kb = dateKey(b); }
      else if (key === "citations") { ka = citeKey(a); kb = citeKey(b); }
      else {
        // Relevance: the match decides, the tie-break settles what it
        // cannot, and BOTH follow the chosen direction.
        return dir * ((a.score - b.score) || (a.tie - b.tie));
      }
      if (ka === null && kb === null) return byMatch(a, b);
      if (ka === null) return 1;            // always last, both directions
      if (kb === null) return -1;
      if (ka === kb) return byMatch(a, b);
      // A date key is an ISO string, a citation count is a number; `<`
      // orders both correctly.
      return dir * (ka < kb ? -1 : 1);
    };
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
    "OpenAlex": "src--openalex",
    "Semantic Scholar": "src--s2"
  };

  /* Eleven subfields cannot each have a legible colour of their own, and a
     palette that large stops being a code and becomes decoration. So the chip
     carries the precise label as TEXT and is tinted by the broad family it
     belongs to — five tones, every one of them an accent token already
     measured against this section's background in tools/tests/test_theme.js. */
  var SUBFIELD_TONE = {
    "neutrino": "nu",
    "hep-ph": "hep", "hep-ex": "hep",
    "hep-th": "thy", "nucl": "thy",
    "astro-he": "sky", "cosmo": "sky", "astro": "sky",
    "instr": "dim", "other": "dim", "none": "dim"
  };

  var BUCKET_LABEL = {};
  BUCKETS.forEach(function (b) { BUCKET_LABEL[b.id] = b.label; });

  // `showMatch` only outside the relevance view. There the rows already sit
  // under the heading that names their match quality, and repeating it on
  // every row would be noise; in a flat or subfield-grouped list that heading
  // is gone and the information would be lost with it.
  function renderItem(r, showMatch) {
    var authors = r.authors.filter(Boolean).join(", ") + (r.more ? ", et al." : "");
    var when = r.date || (r.year ? String(r.year) : "");
    var meta = compact([
      when && '<time class="pub__year" datetime="' + esc(when) + '">' +
              esc(prettyDate(when)) + "</time>",
      r.journal && '<span class="journal">' + esc(r.journal) + "</span>",
      typeof r.citations === "number" &&
        '<span class="muted" title="Citation count from INSPIRE-HEP">' +
          r.citations + " citations</span>"
    ]).join("");
    var links = r.links.map(function (l) {
      return '<a href="' + esc(l.href) + '" target="_blank" rel="noopener noreferrer">' +
             esc(l.label) + "</a>";
    }).join("");
    var srcs = (r.sources || [r.source]).map(function (s) {
      return '<span class="src ' + (SRC_CLASS[s] || "") + '">' + esc(s) + "</span>";
    }).join("");
    var sf = r.subfield || "none";
    var tags = '<span class="sf sf--' + SUBFIELD_TONE[sf] + '">' +
               esc(SUBFIELD_LABEL[sf]) + "</span>";
    if (showMatch && BUCKET_LABEL[r.bucket]) {
      tags += '<span class="sf sf--match">' + esc(BUCKET_LABEL[r.bucket]) + "</span>";
    }
    var first = r.links[0];
    var title = first
      ? '<a class="pub__title" href="' + esc(first.href) +
        '" target="_blank" rel="noopener noreferrer">' + esc(r.title) + "</a>"
      : '<span class="pub__title">' + esc(r.title) + "</span>";
    return "<li>" + title +
           '<div class="pub__authors">' + esc(authors) + "</div>" +
           '<div class="pub__ref">' + meta + links + '<span class="src-row">' +
           tags + srcs + "</span></div></li>";
  }

  function head(failures, rows) {
    var out = [];
    if (failures.length) {
      out.push('<div class="notice"><p>' +
        failures.map(function (x) {
          return esc(x.name) + " unavailable (" + esc(x.err.message) + ")";
        }).join("; ") +
        ". The outbound buttons above still work.</p></div>");
    }
    if (!rows.length) {
      out.push('<p class="muted">' + (anyHidden()
        ? "Every result is in a subfield you have switched off."
        : "No results. Try loosening the query or widening the dates.") +
        "</p>");
    }
    return out;
  }

  // Relevance view: the match buckets, strongest first — the grouping IS the
  // relevance statement, and the score decides the order inside each group.
  //
  // THE SEQUENCE OF BUCKETS REVERSES TOO. It did not, once: ascending
  // relevance reordered the rows inside each group while leaving the groups
  // themselves strongest-first, so the best match on the page stayed in
  // position one — while the status line and the button's accessible name
  // both announced "weakest match first". A control that says it reversed
  // and did not is worse than no control.
  function renderBuckets(rows, failures) {
    var out = head(failures, rows);
    if (!rows.length) return out.join("");
    var cmp = compareBy("relevance", sortDir);
    var order = sortDir < 0 ? BUCKETS : BUCKETS.slice().reverse();
    order.forEach(function (b) {
      var group = rows.filter(function (r) { return r.bucket === b.id; })
                      .sort(cmp);
      if (!group.length) return;
      out.push(
        '<section class="lit-bucket lit-bucket--' + b.id + '">' +
        '<h3 class="lit-group">' + esc(b.label) +
        '<span class="count">' + group.length + "</span></h3>" +
        '<p class="lit-group__note">' + esc(b.note) + "</p>" +
        '<ul class="publist">' + group.map(function (r) {
          return renderItem(r, false);
        }).join("") + "</ul></section>");
    });
    return out.join("");
  }

  // Year, month and citations: one list. Buckets would cut the very ordering
  // that was asked for into four unrelated runs — a 2027 paper below a 1998
  // one because they matched differently.
  function renderFlat(rows, failures) {
    var out = head(failures, rows);
    if (!rows.length) return out.join("");
    var sorted = rows.slice().sort(compareBy(sortKey, sortDir));
    out.push('<ul class="publist">' + sorted.map(function (r) {
      return renderItem(r, true);
    }).join("") + "</ul>");
    return out.join("");
  }

  // Subfield view: one section per group. The groups are ordered by size,
  // reversibly; inside a group the order is relevance, because "the neutrino
  // papers" is a question about which of them, not about which order.
  function renderSubfields(rows, failures) {
    var out = head(failures, rows);
    if (!rows.length) return out.join("");
    var by = {};
    rows.forEach(function (r) { (by[r.subfield] = by[r.subfield] || []).push(r); });
    var ids = Object.keys(by).sort(function (a, b) {
      if (by[a].length !== by[b].length) {
        return sortDir * (by[a].length - by[b].length);
      }
      return SUBFIELD_ORDER[a] - SUBFIELD_ORDER[b];
    });
    var cmp = compareBy("relevance", -1);
    ids.forEach(function (id) {
      var group = by[id].sort(cmp);
      out.push(
        '<section class="lit-bucket lit-bucket--sf sf-block--' +
        SUBFIELD_TONE[id] + '">' +
        '<h3 class="lit-group">' + esc(SUBFIELD_LABEL[id]) +
        '<span class="count">' + group.length + "</span></h3>" +
        '<ul class="publist">' + group.map(function (r) {
          return renderItem(r, true);
        }).join("") + "</ul></section>");
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
     The controls over the results, and redrawing without refetching

     Everything below works on `state`, the merged answer of the last search.
     A click on a sort button or a subfield filter redraws from it; no request
     leaves the browser. That is what makes the buttons instant, and it is
     also the honest scope of the ordering: it ranks what was retrieved, and
     the status line says how much that is.
     --------------------------------------------------------------- */

  var state = { rows: [], failures: [], dbs: 0, merged: 0, gated: 0 };

  function anyHidden() {
    return Object.keys(hidden).some(function (k) { return hidden[k]; });
  }

  function visibleRows() {
    return state.rows.filter(function (r) { return !hidden[r.subfield]; });
  }

  /* The sort bar is drawn from the start, before any search has run, and the
     filter bar only once there is something to filter.

     Not symmetry for its own sake: the order is pushed UPSTREAM for the date
     keys — a search with Year or Month active asks each database for its most
     recent records, which changes which twenty come back. Hidden until the
     first answer arrived, the bar made that unreachable on the query that
     needed it, and a reader wanting the twenty most recent papers had to
     search, click, and search again. The filter bar has no such duty: it can
     only narrow an answer that exists. */
  function renderControls() {
    if (!elSortBar || !elFilters) return;
    var live = !!state.rows.length;

    var bits = ['<span class="lit-sort__label">Sort by</span>'];
    SORTS.forEach(function (o) {
      var on = o.id === sortKey;
      var way = on ? (sortDir < 0 ? o.down : o.up) : o.down;
      // The arrow is decorative; the direction is in the accessible name, so
      // a screen reader announces "Year, newest year first" and not "Year".
      bits.push('<button type="button" class="lit-sort__btn" data-sort="' +
        o.id + '" aria-pressed="' + (on ? "true" : "false") +
        '" aria-label="' + esc(o.label + ", " + way +
        (on ? " (press again to reverse)" : "")) + '" title="' + esc(way) + '">' +
        esc(o.label) + '<span class="lit-sort__dir" aria-hidden="true">' +
        (on ? (sortDir < 0 ? "\u2193" : "\u2191") : "") + "</span></button>");
    });
    elSortBar.innerHTML = bits.join("");
    elSortBar.hidden = false;

    if (!live) { elFilters.hidden = true; elFilters.innerHTML = ""; return; }

    // Counts are over ALL rows, not over the visible ones: a filter chip
    // whose number changed as you switched other chips off would be telling
    // you about the filter rather than about the answer.
    var counts = {};
    state.rows.forEach(function (r) {
      counts[r.subfield] = (counts[r.subfield] || 0) + 1;
    });
    var ids = Object.keys(counts).sort(function (a, b) {
      return SUBFIELD_ORDER[a] - SUBFIELD_ORDER[b];
    });
    if (ids.length < 2) { elFilters.hidden = true; elFilters.innerHTML = ""; return; }

    var f = ['<span class="lit-sort__label">Subfield</span>'];
    ids.forEach(function (id) {
      var off = !!hidden[id];
      f.push('<button type="button" class="lit-filter sf--' + SUBFIELD_TONE[id] +
        '" data-sf="' + id + '" aria-pressed="' + (off ? "false" : "true") +
        '" aria-label="' + esc(SUBFIELD_LABEL[id] + ", " + counts[id] +
        (off ? " papers, hidden — show them" : " papers, shown — hide them")) +
        '">' + esc(SUBFIELD_LABEL[id]) +
        '<span class="lit-filter__n">' + counts[id] + "</span></button>");
    });
    // No aria-pressed on this one, deliberately: it is a command, not a
    // toggle, and marking it pressed/unpressed would describe a state it does
    // not have. The label says what it does instead.
    if (anyHidden()) {
      f.push('<button type="button" class="lit-filter lit-filter--all" ' +
             'data-sf="*" aria-label="Show every subfield again">' +
             "Show all</button>");
    }
    elFilters.innerHTML = f.join("");
    elFilters.hidden = false;
  }

  function renderStatus(shown) {
    if (!state.rows.length) {
      elStatus.textContent = state.dbs === 0
        ? "No database could be reached."
        : "No results. Try loosening the query or widening the dates.";
      return;
    }
    var active = SORTS.filter(function (o) { return o.id === sortKey; })[0];
    var bits = [];
    bits.push(state.rows.length + " paper" + (state.rows.length === 1 ? "" : "s") +
              " from " + state.dbs + " database" + (state.dbs === 1 ? "" : "s"));
    if (state.merged > 0) {
      bits.push(state.merged === 1 ? "1 duplicate record merged"
                                   : state.merged + " duplicate records merged");
    }
    if (state.gated > 0) {
      bits.push(state.gated === 1 ? "1 off-topic record dropped"
                                  : state.gated + " off-topic records dropped");
    }
    if (shown.length !== state.rows.length) {
      bits.push(shown.length + " shown");
    }
    bits.push("ordered by " + active.label.toLowerCase() + ", " +
              (sortDir < 0 ? active.down : active.up));
    elStatus.textContent = bits.join(" · ") + ". Links open in a new tab.";
  }

  /* Both bars are redrawn wholesale on every click, which throws away the
     focused element — so a reader working by keyboard would press Enter on
     "Year" and find the focus back at the top of the document, with no way to
     reverse it without tabbing the whole way down again. Put it back on the
     button that was just used. */
  function refocus(bar, sel) {
    var el = bar && bar.querySelector(sel);
    if (el && document.activeElement !== el) el.focus();
  }

  function draw() {
    renderControls();
    var rows = visibleRows();
    elResults.innerHTML =
      sortKey === "relevance" ? renderBuckets(rows, state.failures)
      : sortKey === "subfield" ? renderSubfields(rows, state.failures)
      : renderFlat(rows, state.failures);
    renderStatus(rows);
  }

  if (elSortBar) {
    elSortBar.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("[data-sort]") : null;
      if (!b) return;
      var id = b.getAttribute("data-sort");
      // Clicking the active key reverses it; clicking another key starts it
      // in its natural direction, which for every key here is descending —
      // newest, most cited, best match, largest group.
      if (id === sortKey) sortDir = -sortDir;
      else { sortKey = id; sortDir = -1; }
      draw();
      refocus(elSortBar, '[data-sort="' + id + '"]');
    });
  }

  if (elFilters) {
    elFilters.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("[data-sf]") : null;
      if (!b) return;
      var id = b.getAttribute("data-sf");
      if (id === "*") hidden = {};
      else hidden[id] = !hidden[id];
      draw();
      // "Show all" disappears the moment it works, so the focus goes to the
      // chip the reader was last thinking about instead — never to nowhere.
      refocus(elFilters, id === "*" ? "[data-sf]" : '[data-sf="' + id + '"]');
    });
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
    // A subfield filter belongs to one answer: keeping "neutrino physics
    // only" switched on across a search for something else would hide the new
    // answer behind a decision taken about the old one. The sort key is the
    // opposite case — it is a standing preference and survives.
    hidden = {};
    state = { rows: [], failures: [], dbs: 0, merged: 0, gated: 0 };
    renderControls();

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
    // Also decides whether the citation lookup may run at all: with INSPIRE
    // unticked the reader has asked not to use the one source this page
    // trusts for counts, so no count is shown.
    var useInspire = $("#src-inspire").checked;
    if (useInspire) wanted.push(["INSPIRE-HEP", fromInspire(f)]);
    if ($("#src-crossref").checked) wanted.push(["Crossref", fromCrossref(f)]);
    if ($("#src-openalex").checked) wanted.push(["OpenAlex", fromOpenAlex(f)]);
    if ($("#src-arxiv") && $("#src-arxiv").checked) wanted.push(["arXiv", fromArxiv(f)]);
    if ($("#src-s2") && $("#src-s2").checked) wanted.push(["Semantic Scholar", fromS2(f)]);

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

      ok.forEach(function (g) { g.rows.forEach(saneDates); });
      var rows = mergeAll(ok);
      var afterMerge = rows.length;

      var terms = gateTerms(f);
      rows = rows.filter(function (r) {
        var physicsNative = (r.sources || [r.source]).some(function (s) {
          return PHYSICS_NATIVE[s];
        });
        return physicsNative || passesTermGate(r, terms);
      });

      // The citation counts are settled BEFORE anything is scored: the
      // relevance tie-break reads them, and a score computed against a
      // number that is about to be replaced would rank the page by a figure
      // it never shows.
      return fillCitations(rows, useInspire).then(function () {
        // Classified and scored ONCE, here. The sort buttons reorder the
        // same objects afterwards; recomputing a score on every click would
        // be work for nothing and, worse, a chance for the order to disagree
        // with the labels the reader is looking at.
        rows.forEach(function (r) {
          r.bucket = classify(r, f);
          r.subfield = subfieldOf(r);
          r.score = relevance(r, f, terms);
          r.tie = tieBreak(r);
        });

        // Two different losses, counted separately. They used to be added
        // together and reported as duplicates, which credited the merge with
        // records the physics gate had thrown out.
        var found = ok.reduce(function (n, g) { return n + g.rows.length; }, 0);
        state = {
          rows: rows,
          failures: failures,
          dbs: ok.length,
          merged: found - afterMerge,
          gated: afterMerge - rows.length
        };
        draw();
      });
    });
  }

  form.addEventListener("submit", run);

  $("#lit-clear").addEventListener("click", function () {
    form.reset();
    userTouched = {};
    hidden = {};
    state = { rows: [], failures: [], dbs: 0, merged: 0, gated: 0 };
    renderControls();
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
  // The sort bar exists before the first search — see renderControls — so it
  // has to be drawn once at start-up too, not only when an answer arrives.
  renderControls();

  var qs = new URLSearchParams(location.search).get("q");
  if (qs) { elFree.value = qs; applyParse(); run(); }
  else renderChips(null);
})();
