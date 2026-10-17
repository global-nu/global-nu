/* global-nu — theme toggle and mobile navigation.
 *
 * Deliberately small and dependency-free. The theme is applied before first
 * paint by the inline script in base.html; this file only handles the toggle
 * itself, so the two must agree on the storage key ("gnu-theme") and on the
 * data-theme attribute.
 *
 * With no saved choice the root element carries NO data-theme attribute —
 * that is what lets the stylesheet's prefers-color-scheme query decide.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "gnu-theme";

  function current() {
    var explicit = root.getAttribute("data-theme");
    if (explicit === "light" || explicit === "dark") return explicit;
    // No saved choice: fall back to the operating system. Guarded because a
    // browser without matchMedia would otherwise throw here and take the whole
    // toggle down with it — the theme is decorative, the button must not be.
    var mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)");
    return mq && mq.matches ? "light" : "dark";
  }

  function label(btn, theme) {
    var next = theme === "dark" ? "light" : "dark";
    btn.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
    btn.setAttribute("aria-label", "Switch to " + next + " theme");
  }

  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    label(toggle, current());
    toggle.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* private mode: the choice simply does not persist */
      }
      label(toggle, next);
    });
  }

  /* Reveal on scroll. Progressive: without IntersectionObserver, or with
     reduced motion asked for, everything is simply shown at once — the class
     is only ever added, never used to hide something that JS might fail to
     un-hide. */
  var reduced = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var targets = document.querySelectorAll(".reveal");
  if (!targets.length) {
    /* nothing to do */
  } else if (reduced || !("IntersectionObserver" in window)) {
    for (var i = 0; i < targets.length; i++) targets[i].classList.add("is-in");
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    for (var j = 0; j < targets.length; j++) io.observe(targets[j]);
  }

  var toTop = document.querySelector(".to-top");
  if (toTop) {
    var onScroll = function () {
      toTop.classList.toggle("is-on", window.scrollY > 700);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
    });
  }

  var navToggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav");
  if (navToggle && nav) {
    var setOpen = function (open) {
      nav.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    };
    navToggle.addEventListener("click", function () {
      setOpen(!nav.classList.contains("is-open"));
    });
    /* The menu is an overlay, so it must also close the ways overlays do:
       Escape (focus back on the button), a click outside, or following a link
       to a section of the same page. */
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) {
        setOpen(false);
        navToggle.focus();
      }
    });
    document.addEventListener("click", function (e) {
      if (nav.classList.contains("is-open") && !nav.contains(e.target) &&
          !navToggle.contains(e.target)) setOpen(false);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) setOpen(false);
    });
  }
})();

/* Copy buttons and the "More details" toggle of the Results summary.
   Progressive: without JS the citation link goes to data.html#cite, the
   copy buttons do nothing harmful, and every column of the summary table is
   shown (the hiding rule is scoped to .js). */
(function () {
  "use strict";

  function flash(el, text) {
    var old = el.textContent;
    el.classList.add("is-done");
    el.textContent = text;
    setTimeout(function () { el.classList.remove("is-done"); el.textContent = old; }, 1600);
  }

  function copy(text, el, ev) {
    if (!navigator.clipboard) return false;
    if (ev) ev.preventDefault();
    navigator.clipboard.writeText(text).then(
      function () { flash(el, "Copied"); },
      function () { flash(el, "Copy failed"); });
    return true;
  }

  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-copy],[data-copy-cite]");
    if (!el) return;
    if (el.hasAttribute("data-copy")) {
      copy(el.getAttribute("data-copy"), el, ev);
      return;
    }
    var tpl = document.getElementById("cite-" + el.getAttribute("data-copy-cite"));
    if (!tpl) return;                     /* no template here: follow the link */
    var text = (tpl.content ? tpl.content.textContent : tpl.textContent).trim() + "\n";
    copy(text, el, ev);
  });

  var toggles = document.querySelectorAll(".more-toggle");
  for (var i = 0; i < toggles.length; i++) {
    (function (btn) {
      var box = btn.closest(".lvl1");
      btn.hidden = false;
      btn.addEventListener("click", function () {
        var on = box.classList.toggle("is-more");
        btn.setAttribute("aria-expanded", on ? "true" : "false");
        btn.textContent = on ? "Fewer details" : "More details: 2σ and accuracy";
      });
    })(toggles[i]);
  }
})();

/* Hide the right-edge shadow of a scrolling table once it is scrolled to the end. */
(function () {
  "use strict";
  var boxes = document.querySelectorAll(".ts-wrap > .table-scroll");
  for (var i = 0; i < boxes.length; i++) {
    (function (box) {
      var upd = function () {
        box.parentNode.classList.toggle("is-end",
          box.scrollLeft + box.clientWidth >= box.scrollWidth - 2);
      };
      box.addEventListener("scroll", upd, { passive: true });
      window.addEventListener("resize", upd);
      upd();
    })(boxes[i]);
  }
})();

/* Installable app (see sw.js at the site root): register the service worker,
   and offer "Install" where the browser allows it. Only over https or on
   localhost — browsers refuse a service worker anywhere else. */
(function () {
  "use strict";
  var me = document.currentScript && document.currentScript.src;
  var standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if ("serviceWorker" in navigator && me &&
      (location.protocol === "https:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname))) {
    navigator.serviceWorker.register(new URL("../../sw.js", me).href).catch(function () {});
  }
  var box = document.querySelector(".app-install");
  if (!box || standalone) return;
  var btn = box.querySelector(".app-install__btn");
  var deferred = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferred = e;
    box.hidden = false;
  });
  btn.addEventListener("click", function () {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(function () { deferred = null; box.hidden = true; });
  });
  window.addEventListener("appinstalled", function () { box.hidden = true; });
  // Safari on iPhone and iPad has no install prompt: say how instead.
  if (/iPhone|iPad|iPod/.test(navigator.userAgent) && "standalone" in navigator) {
    box.hidden = false;
    btn.hidden = true;
    box.querySelector(".app-install__ios").hidden = false;
  }
})();
