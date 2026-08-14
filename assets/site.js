/* Saviku — saviku.co interaction layer.
   Small, dependency-free, CSP-safe (external file, no inline handlers).
   Everything here is progressive enhancement: with JS off the page is a
   complete, readable document — the nav stays solid, sections stay visible,
   and the FAQ still opens (native <details>). */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduced.matches) document.documentElement.classList.add("no-motion");

  /* ---- mobile drawer ---------------------------------------------------- */
  var toggle = document.querySelector("[data-nav-toggle]");
  var drawer = document.getElementById("drawer");
  var close = drawer ? drawer.querySelector("[data-nav-close]") : null;

  function setDrawer(open) {
    if (!drawer || !toggle) return;
    drawer.setAttribute("data-open", open ? "true" : "false");
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("is-locked", open);
    if (open) {
      var first = close || drawer.querySelector("a, button");
      if (first) window.setTimeout(function () { first.focus(); }, 0);
    } else {
      toggle.focus();
    }
  }

  if (toggle && drawer) {
    toggle.addEventListener("click", function () {
      setDrawer(drawer.getAttribute("data-open") !== "true");
    });
    drawer.addEventListener("click", function (e) {
      var t = e.target;
      if (t.closest("[data-nav-close]") || t.closest("a")) setDrawer(false);
    });
    document.addEventListener("keydown", function (e) {
      if (drawer.getAttribute("data-open") !== "true") return;
      if (e.key === "Escape") {
        setDrawer(false);
        return;
      }
      if (e.key !== "Tab") return;

      var focusable = drawer.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (e.shiftKey && (document.activeElement === first || !drawer.contains(document.activeElement))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth >= 900 && drawer.getAttribute("data-open") === "true") setDrawer(false);
    });
  }

  /* ---- reveal on scroll ------------------------------------------------- */
  var targets = document.querySelectorAll("[data-reveal]");
  if (targets.length) {
    if (reduced.matches || !("IntersectionObserver" in window)) {
      Array.prototype.forEach.call(targets, function (el) { el.classList.add("is-in"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
      document.documentElement.classList.add("reveal-ready");
      Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
    }
  }

  /* ---- WhatsApp example carousel --------------------------------------- */
  var carousels = document.querySelectorAll("[data-carousel]");
  Array.prototype.forEach.call(carousels, function (root) {
    var track = root.querySelector("[data-carousel-track]");
    var section = root.closest(".chat-showcase");
    var prev = section ? section.querySelector("[data-carousel-prev]") : null;
    var next = section ? section.querySelector("[data-carousel-next]") : null;
    var carouselQueued = false;
    if (!track || !prev || !next) return;

    function carouselStep() {
      var card = track.querySelector(".chat-example");
      if (!card) return track.clientWidth * .85;
      var styles = window.getComputedStyle(track);
      var gap = parseFloat(styles.columnGap || styles.gap) || 0;
      return card.getBoundingClientRect().width + gap;
    }

    function updateCarousel() {
      carouselQueued = false;
      prev.disabled = track.scrollLeft <= 8;
      next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 8;
    }

    function queueCarouselUpdate() {
      if (carouselQueued) return;
      carouselQueued = true;
      window.requestAnimationFrame(updateCarousel);
    }

    prev.addEventListener("click", function () {
      track.scrollBy({ left: -carouselStep(), behavior: reduced.matches ? "auto" : "smooth" });
    });
    next.addEventListener("click", function () {
      track.scrollBy({ left: carouselStep(), behavior: reduced.matches ? "auto" : "smooth" });
    });
    track.addEventListener("scroll", queueCarouselUpdate, { passive: true });
    window.addEventListener("resize", queueCarouselUpdate, { passive: true });
    updateCarousel();
  });

  /* ---- scroll-driven bits: header state, step rail, mobile CTA ---------- */
  var header = document.querySelector(".site-header");
  var mobileCta = document.querySelector("[data-mobile-cta]");
  var hero = document.querySelector(".hero");
  var stepList = document.querySelector("[data-steps]");
  var steps = stepList ? stepList.querySelectorAll(".step") : [];
  var queued = false;

  function frame() {
    queued = false;
    var y = window.pageYOffset;

    if (header) header.classList.toggle("is-stuck", y > 12);

    if (mobileCta) {
      var past = hero ? hero.offsetHeight * 0.7 : 420;
      var nearEnd = y + window.innerHeight > document.body.scrollHeight - 260;
      mobileCta.classList.toggle("is-on", y > past && !nearEnd);
    }

    if (stepList && steps.length) {
      var listTop = stepList.getBoundingClientRect().top + y;
      var line = y + window.innerHeight * 0.58;
      var fill = 0;
      Array.prototype.forEach.call(steps, function (step) {
        var mid = step.getBoundingClientRect().top + y + 16;
        var on = line >= mid;
        step.classList.toggle("is-on", on);
        if (on) fill = Math.max(fill, mid - listTop);
      });
      stepList.style.setProperty("--fill", fill + "px");
    }
  }

  function onScroll() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(frame);
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  frame();

  /* ---- footer year ------------------------------------------------------ */
  var year = document.querySelector("[data-year]");
  if (year) year.textContent = String(new Date().getFullYear());
})();
