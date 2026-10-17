/* global-nu — filters for the conference lists, and a calendar of what is shown.
 *
 * Reads the facets render.py writes on every row (data-scope, data-kind,
 * data-continent, data-status, data-start, data-end) and hides the rows that
 * do not match. Nothing is fetched and nothing is re-ordered. A related event
 * listed under its conference stays visible when its conference is, whatever
 * its own facets: the group is one entry. A domain block whose rows are all
 * hidden is hidden with them, and the count line says how many are shown.
 *
 * Without this script the form stays hidden and every list is complete.
 */
(function () {
  "use strict";

  var form = document.getElementById("conf-filters");
  if (!form || !document.querySelectorAll) return;
  form.hidden = false;

  var KEY = "gnu-conf-filters";
  var rows = document.querySelectorAll(".conf-list > li");
  var count = form.querySelector(".conf-filters__count");

  function today() {
    var d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function parse(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || "");
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }

  function matches(li, f) {
    if (f.nu && li.getAttribute("data-scope") !== "neutrino") return false;
    if (f.cont && li.getAttribute("data-continent") !== f.cont) return false;
    if (f.kind && li.getAttribute("data-kind") !== f.kind) return false;
    if (f.status && li.getAttribute("data-status") !== f.status) return false;
    if (f.when) {
      var start = parse(li.getAttribute("data-start"));
      var end = parse(li.getAttribute("data-end")) || start;
      if (!start) return false;
      var from = today(), to = today();
      to.setMonth(to.getMonth() + (+f.when));
      if (end < from || start > to) return false;
    }
    return true;
  }

  function state() {
    return {
      nu: form.elements.nu.checked,
      when: form.elements.when.value,
      cont: form.elements.cont.value,
      kind: form.elements.kind.value,
      status: form.elements.status.value
    };
  }

  function apply() {
    var f = state(), shown = 0, i;
    for (i = 0; i < rows.length; i++) {
      var ok = matches(rows[i], f);
      rows[i].hidden = !ok;
      if (ok) shown++;
    }
    var blocks = document.querySelectorAll(".conf-scope");
    for (i = 0; i < blocks.length; i++) {
      var any = blocks[i].querySelector(".conf-list > li:not([hidden])");
      blocks[i].hidden = !any;
    }
    var all = !f.nu && !f.when && !f.cont && !f.kind && !f.status;
    count.textContent = all ? rows.length + " meetings listed." :
      shown + " of " + rows.length + " meetings match." + (shown ? "" : " Loosen a filter to see more.");
    try { localStorage.setItem(KEY, JSON.stringify(f)); } catch (e) { /* not kept */ }
  }

  try {
    var saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved) {
      form.elements.nu.checked = !!saved.nu;
      ["when", "cont", "kind", "status"].forEach(function (k) {
        if (saved[k] && form.elements[k].querySelector('option[value="' + saved[k] + '"]')) {
          form.elements[k].value = saved[k];
        }
      });
    }
  } catch (e) { /* storage unavailable: start from defaults */ }

  form.addEventListener("change", apply);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  apply();

  /* The calendar of what is shown: the same format as data/feeds/conferences.ics,
     built from the visible rows (related events included). */
  function esc(s) {
    return (s || "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
  }
  function ymd(d) {
    return d.getFullYear() + ("0" + (d.getMonth() + 1)).slice(-2) + ("0" + d.getDate()).slice(-2);
  }
  var btn = document.getElementById("conf-ics");
  if (btn && window.Blob && window.URL && URL.createObjectURL) {
    btn.addEventListener("click", function () {
      var stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
      var out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//global-nu.org//conferences//EN",
                 "CALSCALE:GREGORIAN"];
      var items = document.querySelectorAll(".conf-list > li:not([hidden]), .conf-list > li:not([hidden]) .conf-sub > li");
      for (var i = 0; i < items.length; i++) {
        var li = items[i], s = parse(li.getAttribute("data-start"));
        if (!s) continue;
        var e = parse(li.getAttribute("data-end")) || s;
        e = new Date(e.getFullYear(), e.getMonth(), e.getDate() + 1);
        out.push("BEGIN:VEVENT", "UID:" + esc(li.getAttribute("data-url") || ("row" + i)) + "@global-nu.org",
                 "DTSTAMP:" + stamp, "DTSTART;VALUE=DATE:" + ymd(s), "DTEND;VALUE=DATE:" + ymd(e),
                 "SUMMARY:" + esc(li.getAttribute("data-title")));
        if (li.getAttribute("data-place")) out.push("LOCATION:" + esc(li.getAttribute("data-place")));
        if (li.getAttribute("data-url")) out.push("URL:" + li.getAttribute("data-url"));
        out.push("END:VEVENT");
      }
      out.push("END:VCALENDAR");
      var url = URL.createObjectURL(new Blob([out.join("\r\n") + "\r\n"], { type: "text/calendar" }));
      var a = document.createElement("a");
      a.href = url;
      a.download = "global-nu-conferences.ics";
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
    });
  } else if (btn) {
    btn.hidden = true;
  }
})();
