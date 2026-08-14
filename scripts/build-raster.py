#!/usr/bin/env python3
"""Build the raster brand assets (favicons need SVG; sharing previews need PNG).

These are derived from the official artwork in brand/saviku-logo-source.png, not
from the traced SVG — a link preview and a home-screen icon should carry the real
lockup. The source has a faux-transparency checkerboard baked in, so ink is
separated from background by luminance and re-composited as white-on-navy per
handoff §5 (marketing OG: navy-deep base, gold check motif, white type).

Pure stdlib: PNG decode via zlib, box-filter downscale, PNG encode via zlib.

Run: python3 scripts/build-raster.py
"""
from __future__ import annotations

import math
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
exec((ROOT / "scripts" / "measure-mark.py").read_text().split("def main")[0])  # decode_png

NAVY_DEEP = (0x09, 0x1B, 0x4F)
GOLD = (0xF4, 0xBE, 0x4C)

SRC = ROOT / "brand" / "saviku-logo-source.png"
# measured ink extents in the source (scripts/measure-mark.py)
MARK_BOX = (121, 248, 616, 673)


# ---------------------------------------------------------------- png encode
def write_png(path: pathlib.Path, w: int, h: int, rgb: bytearray) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)                       # filter: none
        raw += rgb[y * w * 3 : (y + 1) * w * 3]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)
    print(f"  wrote {path.relative_to(ROOT)}  ({w}x{h}, {len(png)/1024:.1f} kB)")


# ------------------------------------------------------- ink alpha extraction
def load_alpha(box):
    """Return (w, h, alpha[]) for a crop of the source: 1.0 = ink, 0.0 = paper.

    Both brand colours sit far below the baked checkerboard in luminance
    (navy ~0.03, green ~0.21, paper ~0.96), so a ramp cleanly separates them and
    keeps the artwork's own antialiasing."""
    sw, sh, ch, px = decode_png(str(SRC))
    x0, y0, x1, y1 = box
    w, h = x1 - x0 + 1, y1 - y0 + 1
    lo, hi = 0.50, 0.92                     # fully ink .. fully paper
    alpha = [0.0] * (w * h)
    for y in range(h):
        row = (y + y0) * sw
        for x in range(w):
            i = (row + x + x0) * ch
            r, g, b = px[i] / 255, px[i + 1] / 255, px[i + 2] / 255
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            a = (hi - lum) / (hi - lo)
            alpha[y * w + x] = 0.0 if a < 0 else (1.0 if a > 1 else a)
    return w, h, alpha


def downscale(w, h, alpha, tw, th):
    """Box filter — also does the antialiasing for us."""
    out = [0.0] * (tw * th)
    for ty in range(th):
        sy0, sy1 = ty * h // th, max(ty * h // th + 1, (ty + 1) * h // th)
        for tx in range(tw):
            sx0, sx1 = tx * w // tw, max(tx * w // tw + 1, (tx + 1) * w // tw)
            total = n = 0
            for sy in range(sy0, sy1):
                base = sy * w
                for sx in range(sx0, sx1):
                    total += alpha[base + sx]
                    n += 1
            out[ty * tw + tx] = total / n
    return out


# ------------------------------------------------------------- motif + canvas
MOTIF = [((14, 40), (26, 52), (52, 22)), ((80, 106), (92, 118), (118, 88)),
         ((-4, 106), (8, 118), (34, 88)), ((98, 40), (110, 52), (136, 22))]


def seg_dist(px, py, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - a[0]) * vx + (py - a[1]) * vy) / L))
    return math.hypot(px - (a[0] + vx * t), py - (a[1] + vy * t))


def canvas(w, h, bg, motif_opacity=0.0, tile=132, weight=2.25):
    buf = bytearray(w * h * 3)
    for y in range(h):
        my = y % tile
        for x in range(w):
            r, g, b = bg
            if motif_opacity:
                mx = x % tile
                d = min(min(seg_dist(mx, my, p[i], p[i + 1]) for i in range(2))
                        for p in MOTIF)
                cov = max(0.0, min(1.0, weight + 0.5 - d))
                if cov:
                    a = cov * motif_opacity
                    r = round(r + (GOLD[0] - r) * a)
                    g = round(g + (GOLD[1] - g) * a)
                    b = round(b + (GOLD[2] - b) * a)
            i = (y * w + x) * 3
            buf[i], buf[i + 1], buf[i + 2] = r, g, b
    return buf


def stamp(buf, cw, ch, alpha, aw, ah, ox, oy, ink=(255, 255, 255)):
    for y in range(ah):
        ty = oy + y
        if not 0 <= ty < ch:
            continue
        for x in range(aw):
            a = alpha[y * aw + x]
            if a <= 0.004:
                continue
            tx = ox + x
            if not 0 <= tx < cw:
                continue
            i = (ty * cw + tx) * 3
            buf[i] = round(buf[i] + (ink[0] - buf[i]) * a)
            buf[i + 1] = round(buf[i + 1] + (ink[1] - buf[i + 1]) * a)
            buf[i + 2] = round(buf[i + 2] + (ink[2] - buf[i + 2]) * a)


print("building raster brand assets from the official artwork")

# ---- full lockup, ink-separated once, reused at every size ------------------
lw, lh, lockup = load_alpha((121, 248, 1700, 700))
print(f"  source lockup ink: {lw}x{lh}")

# 1. OG card: 1200x630, navy-deep + gold check motif + white lockup
OW, OH = 1200, 630
og = canvas(OW, OH, NAVY_DEEP, motif_opacity=0.085)
tw = int(OW * 0.70)
th = max(1, round(tw * lh / lw))
stamp(og, OW, OH, downscale(lw, lh, lockup, tw, th), tw, th,
      (OW - tw) // 2, (OH - th) // 2)
# gold rule along the bottom
for y in range(OH - 10, OH):
    for x in range(OW):
        i = (y * OW + x) * 3
        og[i], og[i + 1], og[i + 2] = GOLD
write_png(ROOT / "assets" / "og-cover.png", OW, OH, og)

# 2. app / home-screen icons: navy-deep square + white mark
mw, mh, mark = load_alpha(MARK_BOX)
for size, name in ((512, "icon-512.png"), (180, "apple-touch-icon.png")):
    pad = round(size * 0.19)
    inner = size - 2 * pad
    if mw >= mh:
        tw2, th2 = inner, max(1, round(inner * mh / mw))
    else:
        th2, tw2 = inner, max(1, round(inner * mw / mh))
    icon = canvas(size, size, NAVY_DEEP)
    stamp(icon, size, size, downscale(mw, mh, mark, tw2, th2), tw2, th2,
          (size - tw2) // 2, (size - th2) // 2)
    write_png(ROOT / "assets" / name, size, size, icon)

print("done")
