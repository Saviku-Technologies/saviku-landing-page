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

  /* ---- presentational escrow countdown (recorded server time is authoritative) */
  var releaseCounters = document.querySelectorAll("[data-release-countdown]");
  Array.prototype.forEach.call(releaseCounters, function (counter) {
    var duration = Math.max(0, parseInt(counter.getAttribute("data-countdown-seconds"), 10) || 0);
    var dueAt = Date.now() + duration * 1000;
    var timer = null;

    function renderCountdown() {
      var left = Math.max(0, Math.floor((dueAt - Date.now()) / 1000));
      var hours = Math.floor(left / 3600);
      var minutes = Math.floor((left % 3600) / 60);
      var seconds = left % 60;
      counter.textContent = hours + "h " + String(minutes).padStart(2, "0") + "m " + String(seconds).padStart(2, "0") + "s";
      counter.setAttribute("aria-label", hours + " hours " + minutes + " minutes remaining");
      if (!left && timer) window.clearInterval(timer);
    }

    renderCountdown();
    timer = window.setInterval(renderCountdown, 1000);
  });

  /* ---- example decks ----------------------------------------------------
     One engine for every set of example screens on the page: the hero phone,
     the "inside the conversation" flows and the guest cards. Cards are stacked
     like a deck; the front one advances automatically while the deck is in view
     and can always be driven by hand (buttons, dots, arrow keys, swipe).

     Progressive enhancement: without JS the cards are a plain readable stack
     and no dead controls are rendered — the whole control bar is built here.
     Autoplay pauses on hover, on keyboard focus, when scrolled out of view, and
     permanently once the visitor presses pause (WCAG 2.2.2). */
  var decks = document.querySelectorAll("[data-deck]");

  Array.prototype.forEach.call(decks, function (deck) {
    var cards = Array.prototype.slice.call(deck.querySelectorAll("[data-deck-card]"));
    if (cards.length < 2) return;

    var interval = parseInt(deck.getAttribute("data-deck-interval"), 10) || 5600;
    var until = parseInt(deck.getAttribute("data-deck-until"), 10) || 0;
    var compact = deck.hasAttribute("data-deck-compact");
    var noun = deck.getAttribute("data-deck-noun") || "example";

    var index = 0;
    var timer = null;
    var visible = false;
    var held = false;      // hover / focus
    var paused = false;    // explicit, sticky
    var active = null;     // null forces the first viewport evaluation to initialise controls

    /* ---- control bar, built rather than duplicated in markup ---------- */
    function el(tag, cls, attrs) {
      var node = document.createElement(tag);
      if (cls) node.className = cls;
      for (var key in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, key)) node.setAttribute(key, attrs[key]);
      }
      return node;
    }

    function cardName(i) {
      return (cards[i].getAttribute("data-deck-title")
        || cards[i].getAttribute("aria-label")
        || noun + " " + (i + 1)).replace(/\s+example$/i, "");
    }

    /* A slot is only honoured inside an explicit [data-deck-scope]; without one
       we always build the bar right after the deck. Falling back to parentNode
       would let a deck adopt a *different* deck's slot when the two share an
       ancestor. */
    var scope = deck.closest("[data-deck-scope]");
    var bar = scope ? scope.querySelector("[data-deck-controls]") : null;
    if (!bar) {
      bar = el("div", null, {});
      deck.parentNode.insertBefore(bar, deck.nextSibling);
    }
    bar.className = "deck-controls" + (compact ? " deck-controls--compact" : "");

    var prevBtn = null;
    var nextBtn = null;
    if (!compact) {
      prevBtn = el("button", "deck-nav deck-nav--prev",
        { type: "button", "aria-label": "Previous " + noun });
      bar.appendChild(prevBtn);
    }

    var dotWrap = el("div", "deck-dots", {});
    var dots = cards.map(function (card, i) {
      var dot = el("button", null, { type: "button", "aria-label": "Show " + cardName(i) });
      dotWrap.appendChild(dot);
      return dot;
    });
    bar.appendChild(dotWrap);

    if (!compact) {
      nextBtn = el("button", "deck-nav deck-nav--next",
        { type: "button", "aria-label": "Next " + noun });
      bar.appendChild(nextBtn);
    }

    var toggle = el("button", "deck-play",
      { type: "button", "aria-pressed": "false", "aria-label": "Pause automatic playback" });
    bar.appendChild(toggle);

    var status = el("p", "deck-status", { "aria-live": "polite" });
    bar.appendChild(status);

    /* ---- state ------------------------------------------------------- */
    function render(announce) {
      cards.forEach(function (card, i) {
        var pos = (i - index + cards.length) % cards.length;
        card.setAttribute("data-pos", pos <= 2 ? String(pos) : "back");
        card.setAttribute("aria-hidden", pos === 0 ? "false" : "true");
      });
      dots.forEach(function (dot, i) {
        if (i === index) dot.setAttribute("aria-current", "true");
        else dot.removeAttribute("aria-current");
      });
      status.textContent = announce
        ? (index + 1) + " of " + cards.length + ": " + cardName(index)
        : "";
    }

    function playable() {
      return active && visible && !held && !paused && !reduced.matches;
    }

    function sync() {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
      if (playable()) timer = window.setInterval(function () { go(1, false); }, interval);
    }

    function go(delta, announce) {
      index = (index + delta + cards.length) % cards.length;
      render(announce !== false);
      sync();
    }

    function jump(i) {
      index = i;
      render(true);
      sync();
    }

    /* ---- turn the engine on/off for the viewport ---------------------- */
    function evaluate() {
      var want = !until || window.innerWidth < until;
      if (want === active) return;
      active = want;
      deck.classList.toggle("is-ready", active);
      bar.hidden = !active;
      if (active) {
        index = 0;
        render(false);
      } else {
        cards.forEach(function (card) {
          card.removeAttribute("data-pos");
          card.setAttribute("aria-hidden", "false");
        });
      }
      sync();
    }

    if (prevBtn) prevBtn.addEventListener("click", function () { go(-1); });
    if (nextBtn) nextBtn.addEventListener("click", function () { go(1); });
    dots.forEach(function (dot, i) {
      dot.addEventListener("click", function () { jump(i); });
    });
    toggle.addEventListener("click", function () {
      paused = !paused;
      toggle.setAttribute("aria-pressed", paused ? "true" : "false");
      toggle.setAttribute("aria-label",
        paused ? "Play automatic playback" : "Pause automatic playback");
      sync();
    });

    deck.addEventListener("keydown", function (e) {
      if (!active) return;
      if (e.key === "ArrowRight") { e.preventDefault(); go(1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(-1); }
    });

    /* Hover pausing is for pointing devices only: on a touch screen
       pointerenter fires on tap and the matching pointerleave may never come,
       which would strand autoplay off. Focus pausing is likewise limited to
       keyboard focus, since a tap on a control also focuses it. */
    var viaKeyboard = false;
    document.addEventListener("keydown", function (e) {
      if (e.key === "Tab" || e.key === "ArrowLeft" || e.key === "ArrowRight") viaKeyboard = true;
    }, true);
    document.addEventListener("pointerdown", function () { viaKeyboard = false; }, true);

    [deck, bar].forEach(function (node) {
      node.addEventListener("pointerenter", function (e) {
        if (e.pointerType && e.pointerType !== "mouse") return;
        held = true;
        sync();
      });
      node.addEventListener("pointerleave", function (e) {
        if (e.pointerType && e.pointerType !== "mouse") return;
        held = false;
        sync();
      });
      node.addEventListener("focusin", function () {
        if (!viaKeyboard) return;
        held = true;
        sync();
      });
      node.addEventListener("focusout", function () { held = false; sync(); });
    });

    /* swipe */
    var startX = 0;
    var startY = 0;
    var tracking = false;
    deck.addEventListener("pointerdown", function (e) {
      if (!active || e.pointerType === "mouse") return;
      tracking = true;
      startX = e.clientX;
      startY = e.clientY;
    });
    deck.addEventListener("pointerup", function (e) {
      if (!tracking) return;
      tracking = false;
      var dx = e.clientX - startX;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(e.clientY - startY)) go(dx < 0 ? 1 : -1);
    });
    deck.addEventListener("pointercancel", function () { tracking = false; });

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        sync();
      }, { threshold: 0.35 }).observe(deck);
    } else {
      visible = true;
    }

    window.addEventListener("resize", function () { evaluate(); }, { passive: true });
    evaluate();
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
