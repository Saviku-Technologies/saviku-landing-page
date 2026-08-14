#!/usr/bin/env python3
"""One-off: propagate the redesigned shell (Harbor BRAND context) to every
document page. Idempotent — safe to re-run.

Touches only the shell: doctype/head links, the brand mark, the skip link,
the nav-links modifier, the footer block, and the script tag. Body copy of the
legal documents is left exactly as it is.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = [p for p in sorted(ROOT.glob("*.html")) if p.name != "index.html"]
PAGES += sorted(ROOT.glob("legal/*.html"))

HEAD_EXTRA = (
    '<meta name="theme-color" content="#091B4F">'
    '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">'
    '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">'
    '<link rel="icon" sizes="512x512" href="/assets/icon-512.png">'
)
BRAND_IMG = '<img src="/assets/saviku-mark-mono.svg" alt="" width="30" height="30">'
SKIP = '<a class="skip-link" href="#main">Skip to content</a>'
SCRIPT = '<script src="/assets/site.js?v=5" defer></script>'

FOOTER = (
    '<footer class="site-footer"><div class="wrap footer-doc">'
    '<a class="brand" href="/">' + BRAND_IMG + "Saviku</a>"
    '<nav class="footer-doc-links" aria-label="Footer">{links}</nav>'
    '<p class="small">© <span data-year>2026</span> Saviku Technologies · '
    '<a href="/support.html">Support</a></p>'
    "</div></footer>"
)

changed = []

for page in PAGES:
    src = original = page.read_text(encoding="utf-8")

    # 1. cache-bust the stylesheet and add the icon/theme head tags once
    src = src.replace("/assets/site.css?v=4", "/assets/site.css?v=9")
    if 'rel="icon"' not in src:
        src = src.replace("</head>", HEAD_EXTRA + "</head>", 1)

    # 2. mono mark on the navy header/footer instead of the colour raster logo
    src = re.sub(
        r'<img src="/assets/saviku-logo\.png" alt="">',
        BRAND_IMG,
        src,
    )

    # 3. skip link
    if "skip-link" not in src:
        src = re.sub(r"<body>", "<body>" + SKIP, src, count=1)

    # 4. main landmark target for the skip link
    src = src.replace('<main class="wrap legal">', '<main class="wrap legal" id="main">')

    # 5. document pages have no hamburger — keep their 1-2 nav links visible on mobile
    src = src.replace(
        '<div class="nav-links">', '<div class="nav-links nav-links--inline">'
    )

    # 6. rebuild the footer, preserving each page's contextual links
    match = re.search(
        r'<footer class="site-footer"><div class="wrap(?: footer-doc)?">(.*?)</div></footer>',
        src,
        re.S,
    )
    if match:
        inner = match.group(1)
        links = inner
        # strip a previously generated wrapper so re-runs stay clean
        nav = re.search(r'<nav class="footer-doc-links"[^>]*>(.*?)</nav>', inner, re.S)
        if nav:
            links = nav.group(1)
        else:
            links = re.sub(r'<a class="brand".*?</a>', "", links, flags=re.S)
            links = re.sub(r"<p class=\"small\">.*?</p>", "", links, flags=re.S)
        src = src[: match.start()] + FOOTER.format(links=links.strip()) + src[match.end() :]

    # 7. defer-loaded behaviour (footer year, drawer where present)
    if "/assets/site.js" not in src:
        src = src.replace("</body>", SCRIPT + "</body>", 1)

    if src != original:
        page.write_text(src, encoding="utf-8")
        changed.append(page.relative_to(ROOT).as_posix())

print(f"updated {len(changed)} of {len(PAGES)} pages")
for name in changed:
    print("  •", name)
