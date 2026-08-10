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
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
})();
