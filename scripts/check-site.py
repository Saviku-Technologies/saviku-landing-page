#!/usr/bin/env python3
"""Static checks for the saviku.co static site.

Run: python3 scripts/check-site.py
Exits non-zero on any error. Warnings are informational.

Covers what a browser would otherwise have to tell us:
  1. HTML tag balance / nesting
  2. every local href + src resolves to a file that exists
  3. every class used in markup is defined in CSS (typo catcher)
  4. CSS braces balance, and every var(--token) referenced is defined
  5. the retired teal palette stays dead (handoff §8.5)
"""
from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
OPTIONAL_CLOSE = {"li", "p", "td", "th", "tr", "option", "dt", "dd"}

errors: list[str] = []
warnings: list[str] = []


class Checker(HTMLParser):
    def __init__(self, name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.name = name
        self.stack: list[tuple[str, int]] = []
        self.classes: set[str] = set()
        self.refs: list[tuple[str, int]] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for cls in (a.get("class") or "").split():
            self.classes.add(cls)
        if a.get("id"):
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key):
                self.refs.append((a[key], self.getpos()[0]))
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            open_tag, line = self.stack.pop()
            if open_tag == tag:
                return
            if open_tag not in OPTIONAL_CLOSE:
                errors.append(
                    f"{self.name}: <{open_tag}> opened line {line} but </{tag}> "
                    f"found at line {self.getpos()[0]}"
                )
                return
        errors.append(f"{self.name}: stray </{tag}> at line {self.getpos()[0]}")

    def finish(self):
        for tag, line in self.stack:
            if tag not in OPTIONAL_CLOSE:
                errors.append(f"{self.name}: <{tag}> at line {line} never closed")


# ---- CSS -------------------------------------------------------------------
css_text = ""
for css in sorted((ROOT / "assets").glob("*.css")):
    body = css.read_text(encoding="utf-8")
    css_text += body
    if body.count("{") != body.count("}"):
        errors.append(
            f"{css.name}: unbalanced braces ({body.count('{')} open, {body.count('}')} close)"
        )

defined_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", css_text))
for token in sorted(set(re.findall(r"var\((--[a-z0-9-]+)", css_text))):
    if token not in defined_tokens:
        errors.append(f"css: var({token}) used but never defined")

css_classes = set(re.findall(r"\.([a-zA-Z][\w-]*)", css_text))

# ---- HTML ------------------------------------------------------------------
pages = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("legal/*.html"))
if not pages:
    errors.append("no html pages found")

all_used: set[str] = set()

for page in pages:
    rel = page.relative_to(ROOT).as_posix()
    checker = Checker(rel)
    checker.feed(page.read_text(encoding="utf-8"))
    checker.finish()
    all_used |= checker.classes

    for cls in sorted(checker.classes):
        if cls not in css_classes:
            errors.append(f"{rel}: class \"{cls}\" has no CSS rule")

    for ref, line in checker.refs:
        target = ref.split("#", 1)[0].split("?", 1)[0]
        if not target:
            anchor = ref.lstrip("#")
            if anchor and anchor not in checker.ids:
                errors.append(f"{rel}:{line}: anchor #{anchor} has no matching id")
            continue
        if re.match(r"^(https?:|mailto:|tel:|data:)", target):
            continue
        if target.startswith("/"):
            resolved = ROOT / target.lstrip("/")
        else:
            resolved = page.parent / target
        if target.endswith("/"):
            resolved = resolved / "index.html"
        if not resolved.exists():
            errors.append(f"{rel}:{line}: {ref} -> missing {resolved.relative_to(ROOT)}")

# ---- retired palette -------------------------------------------------------
for path in pages + sorted((ROOT / "assets").glob("*.css")) + sorted((ROOT / "assets").glob("*.js")):
    text = path.read_text(encoding="utf-8")
    for dead in ("39A8AF", "2C8189", "saviku-teal"):
        if dead.lower() in text.lower() and "RETIRED" not in text:
            errors.append(f"{path.name}: retired teal token '{dead}' is back")

# ---- informational ---------------------------------------------------------
for cls in sorted(css_classes - all_used):
    if cls.startswith(("is-", "no-", "has-", "band--", "button", "nav-links--")):
        continue
    warnings.append(f"css class .{cls} is defined but unused in markup")

# ---- report ----------------------------------------------------------------
print(f"checked {len(pages)} pages, {len(css_classes)} css classes, {len(defined_tokens)} tokens")
for w in warnings:
    print("  warn:", w)
if errors:
    print(f"\n{len(errors)} error(s):")
    for e in errors:
        print("  ✗", e)
    sys.exit(1)
print("\n✓ all checks passed")
