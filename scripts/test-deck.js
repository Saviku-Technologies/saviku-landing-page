/* Behaviour test for the example-deck engine in assets/site.js.
 *
 * There is no browser available in this environment, so this runs the real
 * site.js against a minimal DOM stub and asserts the deck's observable state:
 * which control bar gets built where, which card is in front, how data-pos
 * rotates, and exactly when the autoplay timer is allowed to run.
 *
 * Run: node scripts/test-deck.js
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
let failures = 0;
let checks = 0;

function ok(cond, label) {
  checks++;
  if (cond) return;
  failures++;
  console.log("  ✗ " + label);
}
function show(v) {
  if (v && typeof v === "object" && v.tagName) {
    return "<" + v.tagName.toLowerCase() + (v.className ? " class=\"" + v.className + "\"" : "") + ">";
  }
  try { return JSON.stringify(v); } catch (e) { return String(v); }
}
function eq(actual, expected, label) {
  ok(actual === expected, label + "  (got " + show(actual) + ", want " + show(expected) + ")");
}

/* ------------------------------------------------------------------ DOM stub */
let nodeSeq = 0;

class El {
  constructor(tag) {
    this.tagName = String(tag || "div").toUpperCase();
    this.attrs = new Map();
    this.children = [];
    this.parentNode = null;
    this.listeners = new Map();
    this._class = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.id = "n" + nodeSeq++;
    this.style = { setProperty() {}, removeProperty() {} };
    const self = this;
    this.classList = {
      add: (c) => self._setClasses(self._classes().concat([c])),
      remove: (c) => self._setClasses(self._classes().filter((x) => x !== c)),
      contains: (c) => self._classes().indexOf(c) !== -1,
      toggle: (c, on) => (on === undefined ? (self.classList.contains(c) ? self.classList.remove(c) : self.classList.add(c)) : on ? self.classList.add(c) : self.classList.remove(c)),
    };
  }
  _classes() { return this._class.split(/\s+/).filter(Boolean); }
  _setClasses(list) { this._class = Array.from(new Set(list)).join(" "); }
  get className() { return this._class; }
  set className(v) { this._class = v == null ? "" : String(v); }

  setAttribute(k, v) { this.attrs.set(k, String(v)); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  hasAttribute(k) { return this.attrs.has(k); }
  removeAttribute(k) { this.attrs.delete(k); }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  insertBefore(child, ref) {
    child.parentNode = this;
    const i = ref ? this.children.indexOf(ref) : -1;
    if (i === -1) this.children.push(child);
    else this.children.splice(i, 0, child);
    return child;
  }
  get nextSibling() {
    if (!this.parentNode) return null;
    const sib = this.parentNode.children;
    return sib[sib.indexOf(this) + 1] || null;
  }

  descendants() {
    const out = [];
    for (const c of this.children) { out.push(c); out.push(...c.descendants()); }
    return out;
  }
  matches(sel) {
    return sel.split(",").map((s) => s.trim()).filter(Boolean).some((s) => {
      // only the selector shapes site.js actually uses
      const attr = s.match(/^\[([\w-]+)\]$/);
      if (attr) return this.hasAttribute(attr[1]);
      const cls = s.match(/^\.([\w-]+)$/);
      if (cls) return this.classList.contains(cls[1]);
      if (/^[a-zA-Z]+$/.test(s)) return this.tagName === s.toUpperCase();
      const id = s.match(/^#([\w-]+)$/);
      if (id) return this.getAttribute("id") === id[1];
      return false;
    });
  }
  querySelectorAll(sel) { return this.descendants().filter((n) => n.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest(sel) {
    let n = this;
    while (n) { if (n.matches && n.matches(sel)) return n; n = n.parentNode; }
    return null;
  }
  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(fn);
  }
  fire(type, ev) {
    (this.listeners.get(type) || []).forEach((fn) => fn(Object.assign({
      type, preventDefault() {}, target: this, clientX: 0, clientY: 0,
    }, ev || {})));
  }
  getBoundingClientRect() { return { top: 0, left: 0, width: 320, height: 480 }; }
}

function build(spec, parent) {
  const el = new El(spec.tag);
  if (spec.class) el.className = spec.class;
  for (const k in spec.attrs || {}) el.setAttribute(k, spec.attrs[k]);
  (spec.kids || []).forEach((k) => build(k, el));
  if (parent) parent.appendChild(el);
  return el;
}

function cards(n, extra) {
  return Array.from({ length: n }, (_, i) => ({
    tag: "article",
    attrs: Object.assign({ "data-deck-card": "", "data-deck-title": "Card " + (i + 1) }, extra || {}),
  }));
}

/* the three decks on the page, in page order */
const doc = new El("body");
const heroFigure = build({
  tag: "figure", attrs: { "data-deck-scope": "" }, kids: [
    { tag: "div", class: "device-screen deck deck--frame", attrs: { "data-deck": "", "data-deck-compact": "", "data-deck-noun": "product example" }, kids: cards(6) },
    { tag: "div", attrs: { "data-deck-controls": "" } },
  ],
}, doc);
const showcase = build({
  tag: "section", attrs: { "data-deck-scope": "" }, kids: [
    { tag: "div", class: "deck-column", kids: [
      { tag: "div", class: "deck deck--stack", attrs: { "data-deck": "", "data-deck-noun": "example" }, kids: cards(6) },
      { tag: "p", class: "carousel-hint" },
    ] },
  ],
}, doc);
const guests = build({
  tag: "div", class: "guest-examples deck deck--stack",
  attrs: { "data-deck": "", "data-deck-until": "900", "data-deck-noun": "card" },
  kids: cards(3),
}, doc);

/* ---------------------------------------------------------------- window stub */
let observers = [];
let timers = new Map();
let timerSeq = 1;

const win = {
  innerWidth: 390,
  innerHeight: 800,
  pageYOffset: 0,
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  requestAnimationFrame: (fn) => fn(),
  addEventListener(type, fn) { (this._l = this._l || {})[type] = (this._l[type] || []).concat(fn); },
  fire(type, ev) { ((this._l || {})[type] || []).forEach((fn) => fn(ev || {})); },
  setInterval(fn, ms) { const id = timerSeq++; timers.set(id, { fn, ms }); return id; },
  clearInterval(id) { timers.delete(id); },
  setTimeout(fn) { return 0; },
  getComputedStyle: () => ({ gap: "0px", columnGap: "0px" }),
  IntersectionObserver: class {
    constructor(cb) { this.cb = cb; observers.push(this); }
    observe(el) { this.el = el; }
    unobserve() {}
  },
};
win.window = win;

const documentStub = {
  documentElement: new El("html"),
  body: doc,
  querySelector: (s) => doc.querySelector(s),
  querySelectorAll: (s) => doc.querySelectorAll(s),
  getElementById: () => null,
  createElement: (t) => new El(t),
  addEventListener(type, fn) { (this._l = this._l || {})[type] = (this._l[type] || []).concat(fn); },
  fire(type, ev) { ((this._l || {})[type] || []).forEach((fn) => fn(ev)); },
  activeElement: null,
};

const sandbox = {
  window: win, document: documentStub, Math, JSON, Date, String, Number, Object,
  Array, parseInt, parseFloat, console,
};
sandbox.globalThis = sandbox;
// in a browser `window` *is* the global, so bare references resolve too
["setInterval", "clearInterval", "setTimeout", "requestAnimationFrame",
  "matchMedia", "getComputedStyle", "IntersectionObserver"].forEach(function (k) {
  sandbox[k] = typeof win[k] === "function" && k !== "IntersectionObserver"
    ? win[k].bind(win)
    : win[k];
});

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(ROOT, "assets", "site.js"), "utf8"), sandbox);

/* ------------------------------------------------------------------- asserts */
console.log("deck engine behaviour\n");

const heroDeck = heroFigure.querySelector("[data-deck]");
const heroSlot = heroFigure.querySelector("[data-deck-controls]");
const showDeck = showcase.querySelector("[data-deck]");

// 1. the control bar must land in the provided slot, never on the deck itself
ok(heroSlot.classList.contains("deck-controls"), "hero: control bar built into the slot");
ok(heroDeck.classList.contains("deck") && heroDeck.classList.contains("deck--frame"),
  "hero: deck keeps its own classes (slot lookup did not hit the deck)");
eq(heroSlot.querySelectorAll(".deck-nav").length, 0, "hero: compact bar has no prev/next");
eq(heroSlot.querySelectorAll(".deck-dots")[0].children.length, 6, "hero: 6 dots");
eq(heroSlot.querySelectorAll(".deck-play").length, 1, "hero: pause toggle present");

// 2. full bar is inserted directly after the deck
const showBar = showcase.querySelector(".deck-controls");
ok(showBar !== null, "showcase: control bar created");
eq(showDeck.nextSibling, showBar, "showcase: bar inserted right after the deck");
eq(showBar.querySelectorAll(".deck-nav").length, 2, "showcase: prev + next");
eq(showBar.querySelectorAll(".deck-dots")[0].children.length, 6, "showcase: 6 dots");

// 3. progressive enhancement: is-ready only after JS
ok(showDeck.classList.contains("is-ready"), "showcase: deck marked ready");

// 4. initial stack order
const pos = (deck) => deck.querySelectorAll("[data-deck-card]").map((c) => c.getAttribute("data-pos"));
eq(pos(showDeck).join(","), "0,1,2,back,back,back", "showcase: initial data-pos rotation");
eq(showDeck.querySelectorAll("[data-deck-card]")[0].getAttribute("aria-hidden"), "false",
  "showcase: front card exposed to AT");
eq(showDeck.querySelectorAll("[data-deck-card]")[1].getAttribute("aria-hidden"), "true",
  "showcase: cards behind hidden from AT");

// 5. manual next rotates the deck
showBar.querySelectorAll(".deck-nav--next")[0].fire("click");
eq(pos(showDeck).join(","), "back,0,1,2,back,back", "showcase: next advances the front card");
showBar.querySelectorAll(".deck-nav--prev")[0].fire("click");
eq(pos(showDeck).join(","), "0,1,2,back,back,back", "showcase: prev goes back");

// wrap-around
for (let i = 0; i < 5; i++) showBar.querySelectorAll(".deck-nav--next")[0].fire("click");
eq(pos(showDeck).join(","), "1,2,back,back,back,0", "showcase: wraps past the last card");
showBar.querySelectorAll(".deck-nav--next")[0].fire("click");
eq(pos(showDeck).join(","), "0,1,2,back,back,back", "showcase: wraps back to the first");

// 6. dots jump directly and mark current
showBar.querySelectorAll(".deck-dots")[0].children[3].fire("click");
eq(pos(showDeck)[3], "0", "showcase: dot jumps to its card");
eq(showBar.querySelectorAll(".deck-dots")[0].children[3].getAttribute("aria-current"), "true",
  "showcase: active dot marked aria-current");
eq(showBar.querySelectorAll(".deck-dots")[0].children[0].getAttribute("aria-current"), null,
  "showcase: inactive dot clears aria-current");

// 7. autoplay gating — nothing runs until the deck is actually in view
eq(timers.size, 0, "autoplay: idle while off-screen");
observers.forEach((o) => o.cb([{ isIntersecting: true }]));
ok(timers.size >= 2, "autoplay: starts for on-screen decks");

// mouse hover pauses, leaving resumes
const before = timers.size;
showDeck.fire("pointerenter", { pointerType: "mouse" });
eq(timers.size, before - 1, "autoplay: mouse hover pauses that deck");
showDeck.fire("pointerleave", { pointerType: "mouse" });
eq(timers.size, before, "autoplay: leaving resumes");

// a touch tap must NOT strand autoplay off
showDeck.fire("pointerenter", { pointerType: "touch" });
eq(timers.size, before, "autoplay: touch tap does not pause (no pointerleave on mobile)");

// explicit pause is sticky
const playBtn = showBar.querySelectorAll(".deck-play")[0];
playBtn.fire("click");
eq(playBtn.getAttribute("aria-pressed"), "true", "pause: aria-pressed set");
eq(timers.size, before - 1, "pause: timer stopped");
showDeck.fire("pointerleave", { pointerType: "mouse" });
eq(timers.size, before - 1, "pause: stays paused after hover ends");
playBtn.fire("click");
eq(timers.size, before, "pause: pressing play resumes");

// 8. autoplay actually advances
const at = pos(showDeck).indexOf("0");
Array.from(timers.values()).forEach((t) => t.fn());
ok(pos(showDeck).indexOf("0") !== at, "autoplay: tick advances the front card");

// 9. keyboard
showDeck.fire("keydown", { key: "ArrowRight" });
const afterKey = pos(showDeck).indexOf("0");
showDeck.fire("keydown", { key: "ArrowLeft" });
eq(pos(showDeck).indexOf("0"), (afterKey - 1 + 6) % 6, "keyboard: arrows move the deck");

// 10. swipe
const swipeAt = pos(showDeck).indexOf("0");
showDeck.fire("pointerdown", { pointerType: "touch", clientX: 200, clientY: 100 });
showDeck.fire("pointerup", { pointerType: "touch", clientX: 120, clientY: 105 });
eq(pos(showDeck).indexOf("0"), (swipeAt + 1) % 6, "swipe: left swipe advances");

// 11. the guest deck is a deck on mobile and a plain grid on desktop
const guestBar = doc.children[doc.children.indexOf(guests) + 1];
ok(guests.classList.contains("is-ready"), "guests: deck active at 390px");
eq(guestBar.hidden, false, "guests: controls visible at 390px");
// this deck shares the autoplay tick fired above, so assert the shape of the
// rotation rather than a fixed index
const gp = pos(guests);
eq(gp.filter((p) => p === "0").length, 1, "guests: exactly one card in front");
eq(gp.slice().sort().join(","), "0,1,2", "guests: stacked as a rotation at 390px");

win.innerWidth = 1200;
win.fire("resize");
ok(!guests.classList.contains("is-ready"), "guests: deck stands down at 1200px");
eq(guestBar.hidden, true, "guests: controls hidden at 1200px");
eq(pos(guests).join(","), ",,", "guests: data-pos cleared so the 3-up grid lays out");
eq(guests.querySelectorAll("[data-deck-card]")[2].getAttribute("aria-hidden"), "false",
  "guests: every card exposed to AT in grid mode");

win.innerWidth = 390;
win.fire("resize");
ok(guests.classList.contains("is-ready"), "guests: deck returns below 900px");
eq(pos(guests).join(","), "0,1,2", "guests: restacks on return");

// the other two decks are unaffected by width
ok(showDeck.classList.contains("is-ready"), "showcase: deck stays on at every width");
ok(heroDeck.classList.contains("is-ready"), "hero: deck stays on at every width");

console.log(`\n${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
