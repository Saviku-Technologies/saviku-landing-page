#!/usr/bin/env python3
"""Publish the FAQ from data/faq.json.

The landing page is the only place FAQ text is edited. This writes the
immutable versioned document, the current faq.json alias, the manifest
pin (version + sha256), and the homepage #faq section. A published
version's bytes are never rewritten: change the text by bumping version.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "faq.json"
MANIFEST = ROOT / "manifest.json"
INDEX = ROOT / "index.html"
LOCK = ROOT / "faq.lock.json"
START = "<!-- faq:generated -->"
END = "<!-- /faq:generated -->"


def canonical(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_answer(text: str) -> str:
    """The same words as the JSON, as the homepage paragraphs."""
    blocks: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        label, sep, rest = para.partition(":")
        words = label.split()
        titled = bool(words) and all(word[:1].isupper() or word[:1].isdigit() for word in words)
        if sep and rest.startswith(" ") and titled and 1 <= len(label) <= 40:
            blocks.append(f"<p><strong>{_esc(label)}:</strong>{_esc(rest)}</p>")
            continue
        if len(para) <= 60 and ":" not in para and "." not in para:
            blocks.append(f"<p><strong>{_esc(para)}</strong></p>")
            continue
        blocks.append(f"<p>{_esc(para)}</p>")
    return "\n          ".join(blocks)


def render_faq_html(doc: dict) -> str:
    details = []
    for entry in doc["entries"]:
        title = entry["title"]["en"]
        body = render_answer(entry["answer"]["en"])
        details.append(
            "        <details>\n"
            f"          <summary>{_esc(title)}</summary>\n"
            f"          {body}\n"
            "        </details>"
        )
    return START + "\n" + "\n".join(details) + "\n        " + END


def splice_index(html: str, block: str) -> str:
    if START not in html or END not in html:
        raise SystemExit("index.html is missing faq:generated markers")
    pre, _, rest = html.partition(START)
    _, _, post = rest.partition(END)
    return pre + block + post


def load_lock() -> dict:
    if not LOCK.exists():
        return {"platform_faq": {}}
    return json.loads(LOCK.read_text(encoding="utf-8"))


def main() -> int:
    check = "--check" in sys.argv
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    version = str(doc.get("version") or "")
    if not version.startswith("v") or not doc.get("entries"):
        raise SystemExit("data/faq.json needs a version (vN) and entries")
    body = canonical(doc)
    digest = sha256(body)
    target = ROOT / "legal" / "faq" / f"{version}.json"
    if target.exists() and target.read_bytes() != body:
        raise SystemExit(
            f"legal/faq/{version}.json is already published. "
            "Bump version in data/faq.json instead of editing it."
        )
    lock = load_lock()
    locked = (lock.get("platform_faq") or {}).get(version)
    if locked and locked != digest:
        raise SystemExit(f"faq.lock.json pins {version} at {locked}, document hashes to {digest}")

    html = INDEX.read_text(encoding="utf-8")
    updated_html = splice_index(html, render_faq_html(doc))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["platform_faq"] = {
        "version": version,
        # Site-root path, same shape as the terms entries. stage-site.js
        # strips the /legal prefix for the copy at /legal/manifest.json,
        # which is the file the app joins onto public_legal_base_url.
        "url": f"/legal/faq/{version}.json",
        "sha256": digest,
        "effective_at": doc.get("effective_at"),
        "description": "Saviku help and FAQ. The site and the WhatsApp bot both quote this document.",
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    lock.setdefault("platform_faq", {})[version] = digest
    lock_text = json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
    alias = ROOT / "faq.json"

    if check:
        problems = []
        if not target.exists() or target.read_bytes() != body:
            problems.append(f"legal/faq/{version}.json")
        if not alias.exists() or alias.read_bytes() != body:
            problems.append("faq.json")
        if INDEX.read_text(encoding="utf-8") != updated_html:
            problems.append("index.html #faq")
        if MANIFEST.read_text(encoding="utf-8") != manifest_text:
            problems.append("manifest.json platform_faq")
        if LOCK.read_text(encoding="utf-8") != lock_text:
            problems.append("faq.lock.json")
        if problems:
            raise SystemExit("FAQ outputs drifted from data/faq.json: " + ", ".join(problems))
        print(f"faq {version} {digest} matches the published files")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    alias.write_bytes(body)
    INDEX.write_text(updated_html, encoding="utf-8")
    MANIFEST.write_text(manifest_text, encoding="utf-8")
    LOCK.write_text(lock_text, encoding="utf-8")
    print(f"published faq {version} {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
