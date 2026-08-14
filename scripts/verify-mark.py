#!/usr/bin/env python3
"""Verify the traced mark against the official raster, pixel by pixel.

There is no SVG rasteriser available in this environment, so this does its own:
the path data from scripts/build-brand.py is flattened to polylines (proper SVG
endpoint->centre arc conversion), then each pixel is classified by distance to
the skeleton — which is exactly what a stroke is. The result is compared with
the official artwork's own pixels and reported as intersection-over-union.

Run: python3 scripts/verify-mark.py
"""
from __future__ import annotations

import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

exec((ROOT / "scripts" / "measure-mark.py").read_text().split("def main")[0])  # decode_png

spec = (ROOT / "scripts" / "build-brand.py").read_text()


def const(name):
    m = re.search(rf"^{name} = \(?\s*\n?((?:\s*\"[^\"]*\"\s*\n?)+)\)?", spec, re.M)
    if m:
        return "".join(re.findall(r'"([^"]*)"', m.group(1)))
    m = re.search(rf'^{name} = "([^"]*)"', spec, re.M)
    return m.group(1)


GREEN_BUBBLE, NAVY_BUBBLE, NAVY_TAIL, CHECK = (
    const(n) for n in ("GREEN_BUBBLE", "NAVY_BUBBLE", "NAVY_TAIL", "CHECK")
)
STROKE = int(re.search(r"^STROKE = (\d+)", spec, re.M).group(1))
GAP = int(re.search(r"^GAP = (\d+)", spec, re.M).group(1))
HALF = STROKE / 2


# ---- path -> polyline ------------------------------------------------------
def arc_points(x0, y0, rx, ry, large, sweep, x1, y1, step=2.0):
    """SVG endpoint arc -> centre parameterisation (W3C implementation notes)."""
    if x0 == x1 and y0 == y1:
        return []
    dx2, dy2 = (x0 - x1) / 2, (y0 - y1) / 2
    lam = dx2 * dx2 / (rx * rx) + dy2 * dy2 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * dy2 * dy2 - ry * ry * dx2 * dx2
    den = rx * rx * dy2 * dy2 + ry * ry * dx2 * dx2
    co = math.sqrt(max(0.0, num / den))
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * dy2 / ry, -co * ry * dx2 / rx
    cx, cy = cxp + (x0 + x1) / 2, cyp + (y0 + y1) / 2

    def ang(ux, uy, vx, vy):
        d = (math.hypot(ux, uy) * math.hypot(vx, vy)) or 1e-12
        a = math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / d)))
        return -a if ux * vy - uy * vx < 0 else a

    th0 = ang(1, 0, (dx2 - cxp) / rx, (dy2 - cyp) / ry)
    dth = ang((dx2 - cxp) / rx, (dy2 - cyp) / ry, (-dx2 - cxp) / rx, (-dy2 - cyp) / ry)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    n = max(2, int(abs(dth) * max(rx, ry) / step))
    return [
        (cx + rx * math.cos(th0 + dth * i / n), cy + ry * math.sin(th0 + dth * i / n))
        for i in range(1, n + 1)
    ]


def flatten(d):
    toks = re.findall(r"([MLHVAZ])|(-?\d*\.?\d+)", d.upper())
    pts, cmd, nums, start = [], None, [], None
    i = 0
    flat = [(t[0] or t[1]) for t in toks]
    while i < len(flat):
        t = flat[i]
        if t in "MLHVAZ":
            cmd = t
            i += 1
            if cmd == "Z":
                if start:
                    pts.append(start)
            continue
        take = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7}[cmd]
        nums = [float(v) for v in flat[i : i + take]]
        i += take
        if cmd == "M":
            pts.append((nums[0], nums[1]))
            start = (nums[0], nums[1])
        elif cmd == "L":
            pts.append((nums[0], nums[1]))
        elif cmd == "H":
            pts.append((nums[0], pts[-1][1]))
        elif cmd == "V":
            pts.append((pts[-1][0], nums[0]))
        elif cmd == "A":
            x0, y0 = pts[-1]
            pts.extend(arc_points(x0, y0, nums[0], nums[1], int(nums[3]), int(nums[4]),
                                  nums[5], nums[6]))
    return pts


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L))
    return math.hypot(px - (ax + vx * t), py - (ay + vy * t))


def poly_dist(px, py, poly):
    best = 1e18
    for j in range(len(poly) - 1):
        ax, ay = poly[j]
        bx, by = poly[j + 1]
        if min(ax, bx) - best > px or px > max(ax, bx) + best:
            if min(ay, by) - best > py or py > max(ay, by) + best:
                continue
        d = seg_dist(px, py, ax, ay, bx, by)
        if d < best:
            best = d
    return best


def inside(px, py, poly):
    c = False
    for j in range(len(poly) - 1):
        ax, ay = poly[j]
        bx, by = poly[j + 1]
        if (ay > py) != (by > py) and px < ax + (py - ay) / (by - ay + 1e-18) * (bx - ax):
            c = not c
    return c


green_poly = flatten(GREEN_BUBBLE)
navy_poly = flatten(NAVY_BUBBLE)
tail_poly = flatten(NAVY_TAIL)
check_poly = flatten(CHECK)

# ---- official raster -------------------------------------------------------
w, h, ch, px = decode_png(str(ROOT / "brand" / "saviku-logo-source.png"))


def at(x, y):
    i = (y * w + x) * ch
    return px[i], px[i + 1], px[i + 2]


def truth(x, y):
    r, g, b = at(x, y)
    if b > 40 and b > r + 25 and g < 95 and r < 80:
        return "N"
    if g > 90 and g > r + 50 and g > b + 30:
        return "G"
    return "."


def traced(x, y):
    if poly_dist(x, y, green_poly) <= HALF:
        return "G"
    if poly_dist(x, y, check_poly) <= HALF:
        return "N"
    if inside(x, y, navy_poly) or inside(x, y, tail_poly):
        # the green bubble's whole silhouette (interior + halo) is knocked out
        knocked = inside(x, y, green_poly) or poly_dist(x, y, green_poly) <= HALF + GAP
        if not knocked:
            return "N"
    return "."


X0, X1, Y0, Y1 = 100, 640, 230, 700
stats = {c: [0, 0, 0] for c in "GN"}   # [both, truth-only, traced-only]
edge = 0
for y in range(Y0, Y1):
    for x in range(X0, X1):
        t, m = truth(x, y), traced(x, y)
        if t == m:
            if t in stats:
                stats[t][0] += 1
            continue
        # a 1px disagreement on a boundary is antialiasing, not a trace error
        if min(abs(poly_dist(x, y, p) - HALF) for p in (green_poly, check_poly)) < 1.6:
            edge += 1
            continue
        if t in stats:
            stats[t][1] += 1
        if m in stats:
            stats[m][2] += 1

print("traced SVG vs official raster\n")
total_iou = []
for c, label in (("G", "green bubble"), ("N", "navy (bubble + check)")):
    both, only_t, only_m = stats[c]
    union = both + only_t + only_m
    iou = both / union if union else 1.0
    total_iou.append(iou)
    print(f"  {label:24s} IoU {iou*100:6.2f}%   "
          f"shared {both:6d}  raster-only {only_t:5d}  traced-only {only_m:5d}")
print(f"\n  antialiased boundary pixels ignored: {edge}")
print(f"  mean IoU: {sum(total_iou)/len(total_iou)*100:.2f}%")
