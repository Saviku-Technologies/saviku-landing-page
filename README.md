# saviku.co

Static marketing + legal site for Saviku. No build step, no dependencies — plain
HTML, two CSS files and one small JS file. Deployed as a static site with
`_headers` and `_redirects`.

## Run it locally

```bash
python3 -m http.server 8000
# then open http://localhost:8000/
```

Use a server, not `file://` — every asset path is root-absolute (`/assets/...`).

## Design system

This site is the **BRAND** context of the Harbor colour system
(`docs/HANDOFF-color-system.md` in the main repo). The door test decides which
context a surface belongs to:

> Reached from a WhatsApp conversation → **PRODUCT** (green).
> Represents the company / visited directly → **BRAND** (navy). ← this site

So: navy header and footer, gold primary CTAs, green as an accent only (icons,
one accent word per headline — never body text, never a large fill).
`--wa-green` appears **only** on a literal "chat on WhatsApp" action.

- `assets/tokens.css` — the single source of truth for colour, type, spacing,
  radius, elevation and motion. Both contexts import this file. The retired
  teal family (`#39A8AF`, `#2C8189`) must never come back.
- `assets/site.css` — everything else: the shell, the homepage, and the
  document/legal pages. Mobile-first; every breakpoint is `min-width`.
- `assets/site.js` — progressive enhancement only. Sticky-header state, the
  mobile drawer, scroll reveal, the step rail, the sticky mobile CTA and the
  footer year. With JS off the page is still complete and readable.

### Type

System font stack throughout, so there is no webfont request and no FOUT.
Montserrat ExtraBold is permitted for `h1`/`h2` on brand pages only: drop
`montserrat-800.woff2` into `assets/fonts/`, uncomment the `@font-face` at the
bottom of `tokens.css`, and prepend `Montserrat` to `--font-display`.

### The hero device

The WhatsApp thread in the hero is drawn in CSS, not a screenshot — it stays
crisp at any density, weighs nothing, and is the one place PRODUCT tokens
(`--product-green`, `--product-chip`, `--wa-chat-bg`) appear on this site,
because it is a picture of a product surface. It is exposed to assistive tech
as a single labelled image.

## Content Security Policy

`_headers` ships a strict CSP: `default-src 'self'` with no `'unsafe-inline'`.
That means **no inline `<style>`, no `style="..."` attributes and no inline
`<script>` or `on*` handlers** anywhere in this site. Put CSS in `site.css` and
behaviour in `site.js`. (Programmatic `element.style.setProperty` is fine — the
CSSOM is not covered by CSP.)

## Brand assets

Everything is generated — do not hand-edit the files in `assets/`.

`brand/` holds the sources of truth:

- `saviku-logo-source.png` — the official two-bubble lockup as supplied. Note it
  has a faux-transparency checkerboard baked into it, so it is not usable as a
  drop-in transparent asset; the scripts separate ink from background by
  luminance instead.
- `wordmark-paths.svg` — the real SAVIKU / TECHNOLOGIES glyph outlines lifted
  from the supplied lockup. These are never redrawn.

```bash
python3 scripts/measure-mark.py brand/saviku-logo-source.png 660  # geometry of the mark
python3 scripts/build-brand.py                                    # -> mark, lockup, favicon (SVG)
python3 scripts/verify-mark.py                                    # trace vs official artwork, per-pixel
python3 scripts/build-raster.py                                   # -> og-cover, app icons (PNG)
```

The **mark SVGs are a trace**: the two bubbles, the knockout gap and the check
were measured off the official raster and rebuilt as vector geometry, because no
vector original was available. `verify-mark.py` rasterises the trace and compares
it with the artwork pixel by pixel — currently **95.4% mean IoU** (green bubble
94.1%, navy 96.8%), with bounding boxes within 1px on a 495px-wide mark. Replace
the trace with the real vector if one turns up; the geometry lives in one place
at the top of `build-brand.py`.

The **PNG assets use the official artwork directly**, not the trace, since a link
preview and a home-screen icon should carry the real lockup.

Colour: the mark ships in the Harbor tokens (`#1E9E57` green, `#0D3592` navy).
The supplied raster is slightly different — `#038F5F` green, `#07264D` navy — so
if those values are canonical, change `GREEN`/`NAVY` in `build-brand.py` and the
palette in `tokens.css` together. Right now the mark matches the site.

The knockout between the two bubbles is an SVG `<mask>`, not a white halo, so the
gap is genuinely transparent and the mark works on navy, on white and in the
`-mono` variants alike.

## Example decks

Every set of example screens on the page — the hero phone, the "inside the
conversation" flows and the guest cards — is driven by one engine in `site.js`.
Markup declares only the cards; the whole control bar (prev/next, dots, pause)
is built at runtime, so nothing dead renders when JS is off.

```html
<div class="deck deck--stack" data-deck data-deck-noun="example"
     tabindex="0" role="group" aria-roledescription="carousel" aria-label="...">
  <article data-deck-card data-deck-title="Block dates in chat">...</article>
</div>
```

| attribute | effect |
|---|---|
| `data-deck` | marks the deck (exact attribute — `data-deck-*` never matches) |
| `data-deck-card` | one card; `data-deck-title` names it for dots and announcements |
| `data-deck-interval` | ms between auto-advances (default 5600) |
| `data-deck-compact` | dots + pause only, no prev/next arrows (used in the hero) |
| `data-deck-until="900"` | deck below that width, plain grid at or above it (guest cards) |
| `data-deck-scope` + `data-deck-controls` | render the control bar into a specific slot instead of after the deck |

How it behaves: cards stack in a **single CSS grid cell**, so the deck is exactly
as tall as its tallest card with no measuring, no absolute positioning and no
layout shift when it advances. `.is-ready` is added by JS — before that the cards
are a plain readable stack. Autoplay runs only while the deck is in view and
stops on mouse hover, on keyboard focus, and permanently once the visitor presses
pause (WCAG 2.2.2). Hover/focus pausing deliberately ignores touch input, since a
tap fires `pointerenter` with no matching `pointerleave` and would otherwise
strand autoplay off on a phone. Manual control: buttons, dots, swipe, arrow keys.
Under `prefers-reduced-motion` autoplay never starts and the controls still work.

## Scripts

```bash
node   scripts/test-deck.js        # deck engine behaviour (44 checks, DOM stub)
python3 scripts/check-site.py     # tag balance, dead links, unknown classes, undefined tokens, dead teal
python3 scripts/apply-shell.py    # re-apply the shared header/footer to every document page (idempotent)
python3 scripts/build-brand.py    # regenerate the brand SVGs
python3 scripts/build-raster.py   # regenerate og-cover.png and the app icons
```

`check-site.py` exits non-zero on any error. Run it before deploying.

## Known follow-ups

- Brand dark mode is v2 (handoff §4). Product surfaces stay light in v1 by
  design — they have to match the WhatsApp chat context, not the OS theme.
- If a true vector of the logo becomes available, drop it in and retire the
  traced geometry (see **Brand assets** above).
