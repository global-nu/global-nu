/* global-nu service worker — makes the site installable and readable offline.
   Written to the site root by build.py, which fills in VERSION (a hash of
   every stylesheet, script and icon) and PRECACHE.

   What it does, and does not:
   - pages: network first, so the daily content is always fresh when online;
     the last copy seen is kept for reading offline (at most MAX_PAGES);
   - assets/ (versioned with ?v=): cache first;
   - figure images: kept after first view, if small;
   - data files, archives, PDFs, the 6D tables, JupyterLite: never cached —
     the app is for reading, the downloads stay on the website;
   - other hosts (INSPIRE, arXiv, the analytics counter): not touched. */
"use strict";

var VERSION = "36bd1317b9";
var PRECACHE = [
    "./",
    "index.html",
    "offline.html",
    "manifest.webmanifest",
    "assets/css/explorer.css?v=ea0ffdb6",
    "assets/css/search.css?v=68b37779",
    "assets/css/site.css?v=6f84bde2",
    "assets/js/chi2.js?v=fc43978c",
    "assets/js/confilter.js?v=f7bc4f35",
    "assets/js/confmap.js?v=c8b857a5",
    "assets/js/explorer.js?v=6ff2d1f8",
    "assets/js/figure.js?v=778f8d08",
    "assets/js/map.js?v=b6efba93",
    "assets/js/search.js?v=89dd8ef5",
    "assets/js/site.js?v=239a5c47",
    "assets/js/svgzoom.js?v=a5080536",
    "assets/fonts/archivo-latin-600-normal.woff2",
    "assets/fonts/archivo-latin-700-normal.woff2",
    "assets/fonts/archivo-latin-800-normal.woff2",
    "assets/fonts/inter-latin-400-normal.woff2",
    "assets/fonts/inter-latin-500-normal.woff2",
    "assets/fonts/inter-latin-600-normal.woff2",
    "assets/fonts/jetbrains-mono-latin-400-normal.woff2",
    "assets/fonts/jetbrains-mono-latin-600-normal.woff2",
    "assets/icons/apple-touch-icon.png",
    "assets/icons/icon-192.png",
    "assets/icons/icon-512.png",
    "assets/favicon.svg"
  ];
var STATIC = "gn-static-" + VERSION;
var PAGES = "gn-pages";
var MAX_PAGES = 80;
var MAX_IMAGE = 2 * 1024 * 1024;

var NEVER = /\/(?:data|chi2_6d|lite|download|tables)\/|\.(?:csv|json|txt|gz|zip|tar|pdf|npz|npy|dat|ipynb|ics|atom|xml)(?:$|\?)/i;
var IMAGE = /\.(?:svg|png|jpe?g|webp|avif|gif)(?:$|\?)/i;

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(STATIC)
    .then(function (c) { return c.addAll(PRECACHE); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) {
      return k.indexOf("gn-static-") === 0 && k !== STATIC;
    }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(cache) {
  return cache.keys().then(function (keys) {
    if (keys.length <= MAX_PAGES) return;
    return Promise.all(keys.slice(0, keys.length - MAX_PAGES).map(function (k) {
      return cache.delete(k);
    }));
  });
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // A page: the network, then the last copy, then the offline page.
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then(function (res) {
      if (res.ok) {
        var copy = res.clone();
        caches.open(PAGES).then(function (c) {
          return c.put(url.pathname, copy).then(function () { return trim(c); });
        });
      }
      return res;
    }).catch(function () {
      return caches.match(url.pathname)
        .then(function (r) { return r || caches.match("offline.html"); });
    }));
    return;
  }

  // Page scripts and styles outside assets/ (unversioned): the network
  // first, the last copy for offline reading.
  if (/\.(?:js|css)$/i.test(url.pathname) && url.pathname.indexOf("/assets/") < 0 &&
      url.pathname.indexOf("/lite/") < 0) {
    e.respondWith(fetch(req).then(function (res) {
      if (res.ok) {
        var copy = res.clone();
        caches.open(PAGES).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () { return caches.match(req); }));
    return;
  }

  if (NEVER.test(url.pathname) && !IMAGE.test(url.pathname)) return;

  // Versioned assets never change under the same URL.
  if (url.pathname.indexOf("/assets/") >= 0) {
    e.respondWith(caches.match(req).then(function (r) {
      return r || fetch(req).then(function (res) {
        if (res.ok) {
          var copy = res.clone();
          caches.open(STATIC).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    }));
    return;
  }

  // Figures: the network first, a small copy kept for offline reading.
  if (IMAGE.test(url.pathname) && url.pathname.indexOf("/lite/") < 0) {
    e.respondWith(fetch(req).then(function (res) {
      var n = +(res.headers.get("content-length") || 0);
      if (res.ok && n && n < MAX_IMAGE) {
        var copy = res.clone();
        caches.open(PAGES).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () { return caches.match(req); }));
  }
});
