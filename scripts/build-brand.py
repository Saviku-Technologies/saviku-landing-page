#!/usr/bin/env python3
"""Generate the Saviku brand SVGs from one geometry definition.

The mark is the two-bubble lockup mark: a filled navy speech bubble behind, a
stroked green speech bubble in front with the check contained inside, and a
knocked-out gap where the green bubble crosses the navy one.

Geometry was traced from the official raster (brand/saviku-logo-source.png) by
scripts/measure-mark.py, so the coordinates below are in that file's pixel
space. The wordmark glyphs (SAVIKU / TECHNOLOGIES) are the real vector paths
lifted from the supplied lockup — they are not redrawn.

Colour note: the mark ships in the Harbor tokens (--saviku-green #1E9E57,
--saviku-navy #0D3592) rather than the raster's own #038F5F / #07264D, so it
sits correctly against the rest of the palette. Change GREEN/NAVY below if the
raster's values are declared canonical instead.

Run: python3 scripts/build-brand.py
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BRAND = ROOT / "brand"

GREEN = "#1E9E57"
NAVY = "#0D3592"

# ---- geometry (source raster pixel space) -----------------------------------
STROKE = 28          # green outline + check stroke weight
GAP = 23             # white knockout between the two bubbles

# green bubble: centreline rounded rect x135..464 y344..594 r64, tail bottom-left
GREEN_BUBBLE = (
    "M199 344 H400 A64 64 0 0 1 464 408 V530 A64 64 0 0 1 400 594 "
    "H252 L176 659 L179 590 A55 55 0 0 1 135 535 V408 A64 64 0 0 1 199 344 Z"
)
# navy bubble: rounded rect x288..616 y248..512 r68, plus a tail wedge bottom-right
NAVY_BUBBLE = (
    "M356 248 H548 A68 68 0 0 1 616 316 V444 A68 68 0 0 1 548 512 "
    "H356 A68 68 0 0 1 288 444 V316 A68 68 0 0 1 356 248 Z"
)
NAVY_TAIL = "M491 504 H570 V576 Z"
# check: centreline endpoints are the round-cap centres, i.e. 14 in from the
# visible tips measured radially (not along the stroke axis)
CHECK = "M232 471 L279 516 L371 425"

# rendered extents: x 121..616, y 248..673  ->  centred in a square box
BOX = "103 195 531 531"


def mark_body(green: str, navy: str, mask_id: str) -> str:
    """The mark itself. `mask_id` knocks the green bubble's whole silhouette —
    its filled interior *and* a halo around the outline — out of the navy bubble,
    so the gap is genuinely transparent and works on any background."""
    return f"""  <defs>
    <mask id="{mask_id}" maskUnits="userSpaceOnUse" x="103" y="195" width="531" height="531">
      <rect x="103" y="195" width="531" height="531" fill="#fff"/>
      <path d="{GREEN_BUBBLE}" fill="#000" stroke="#000"
            stroke-width="{STROKE + 2 * GAP}" stroke-linecap="round" stroke-linejoin="round"/>
    </mask>
  </defs>
  <g mask="url(#{mask_id})" fill="{navy}">
    <path d="{NAVY_BUBBLE}"/>
    <path d="{NAVY_TAIL}"/>
  </g>
  <path d="{GREEN_BUBBLE}" fill="none" stroke="{green}"
        stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{CHECK}" fill="none" stroke="{navy}"
        stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round"/>"""


def write(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def build_mark(name: str, green: str, navy: str, mask_id: str) -> None:
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{BOX}" width="480" height="480" role="img" aria-label="Saviku">
{mark_body(green, navy, mask_id)}
</svg>
"""
    write(ASSETS / name, svg)


def wordmark_bbox(svg: str):
    """Union bbox of the wordmark glyph outlines in lockup user space.

    Each glyph is <g transform="translate(tx,ty) scale(s,-s)"><path d="M H L V Q Z"/>.
    Quadratics are flattened; that is exact enough for a bbox at these sizes.
    """
    x0 = y0 = 1e18
    x1 = y1 = -1e18
    for tx, ty, sx, sy, d in re.findall(
        r'transform="translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+),([-\d.]+)\)"[^>]*>'
        r'\s*<path d="([^"]+)"',
        svg,
    ):
        tx, ty, sx, sy = float(tx), float(ty), float(sx), float(sy)
        toks = re.findall(r"([MLHVQZ])|(-?\d*\.?\d+)", d.upper())
        flat = [(a or b) for a, b in toks]
        cx = cy = 0.0
        start = (0.0, 0.0)
        pts = []
        i = 0
        cmd = "M"
        while i < len(flat):
            t = flat[i]
            if t in "MLHVQZ":
                cmd = t
                i += 1
                if cmd == "Z":
                    cx, cy = start
                    pts.append((cx, cy))
                continue
            take = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4}[cmd]
            n = [float(v) for v in flat[i : i + take]]
            i += take
            if cmd == "M":
                cx, cy = n
                start = (cx, cy)
                pts.append((cx, cy))
            elif cmd == "L":
                cx, cy = n
                pts.append((cx, cy))
            elif cmd == "H":
                cx = n[0]
                pts.append((cx, cy))
            elif cmd == "V":
                cy = n[0]
                pts.append((cx, cy))
            elif cmd == "Q":
                px, py = cx, cy
                for k in range(1, 9):
                    u = k / 8
                    v = 1 - u
                    pts.append((v * v * px + 2 * v * u * n[0] + u * u * n[2],
                                v * v * py + 2 * v * u * n[1] + u * u * n[3]))
                cx, cy = n[2], n[3]
        for gx, gy in pts:
            ux, uy = tx + gx * sx, ty + gy * sy
            x0, y0 = min(x0, ux), min(y0, uy)
            x1, y1 = max(x1, ux), max(y1, uy)
    return x0, y0, x1, y1


# ---- how the mark sits against the wordmark, measured on the official raster
SRC_MARK = (121, 248, 616, 673)      # x0 y0 x1 y1
SRC_WORD = (699, 335, 1640, 612)


def build_lockup(name: str, green: str, navy: str, mask_id: str) -> None:
    """Mark + the official SAVIKU / TECHNOLOGIES glyph paths.

    The mark is scaled and positioned so its size and spacing relative to the
    wordmark match the official artwork exactly (the supplied lockup carried the
    older single-bubble mark at a different size, so its box is not reused)."""
    wordmark = (BRAND / "wordmark-paths.svg").read_text(encoding="utf-8").strip()
    wx0, wy0, wx1, wy1 = wordmark_bbox(wordmark)
    if green != GREEN or navy != NAVY:
        wordmark = wordmark.replace(GREEN, green).replace(NAVY, navy)

    mx0, my0, mx1, my1 = SRC_MARK
    sx0, sy0, sx1, sy1 = SRC_WORD
    k = (wx1 - wx0) / (sx1 - sx0)            # match the wordmark's own scale
    dx = wx0 - (sx0 - mx0) * k - mx0 * k     # preserve the source gap
    dy = wy0 - (sy0 - my0) * k - my0 * k     # preserve the source overhang

    lx0, ly0 = min(wx0, mx0 * k + dx), min(wy0, my0 * k + dy)
    lx1, ly1 = max(wx1, mx1 * k + dx), max(wy1, my1 * k + dy)
    pad = 18.0
    vb = (lx0 - pad, ly0 - pad, (lx1 - lx0) + 2 * pad, (ly1 - ly0) + 2 * pad)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]:.1f} {vb[1]:.1f} {vb[2]:.1f} {vb[3]:.1f}" width="{vb[2]:.0f}" height="{vb[3]:.0f}" role="img" aria-label="Saviku Technologies">
  <g transform="translate({dx:.2f},{dy:.2f}) scale({k:.5f})">
{mark_body(green, navy, mask_id)}
  </g>
{wordmark}
</svg>
"""
    write(ASSETS / name, svg)
    print(f"    mark scale {k:.4f}, mark box "
          f"{mx0*k+dx:.0f},{my0*k+dy:.0f} -> {mx1*k+dx:.0f},{my1*k+dy:.0f}; "
          f"viewBox {vb[2]:.0f}x{vb[3]:.0f}")


print("building brand assets from traced geometry")
build_mark("saviku-mark.svg", GREEN, NAVY, "knock")
build_mark("saviku-mark-mono.svg", "#FFFFFF", "#FFFFFF", "knock")
build_mark("favicon.svg", GREEN, NAVY, "knock")
build_lockup("saviku-lockup.svg", GREEN, NAVY, "knock")
build_lockup("saviku-lockup-mono.svg", "#FFFFFF", "#FFFFFF", "knock")
print("done")
