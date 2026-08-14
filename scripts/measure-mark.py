#!/usr/bin/env python3
"""Measure the Saviku mark straight out of the official transparent PNG, so the
SVG we ship is traced from real coordinates instead of eyeballed.

Pure stdlib PNG decode (zlib + struct): IHDR -> IDAT -> unfilter -> RGBA.
"""
from __future__ import annotations

import struct
import sys
import zlib


def decode_png(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a png"
    pos, idat, meta = 8, bytearray(), {}
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            w, h, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            meta = dict(w=w, h=h, depth=depth, color=color, interlace=interlace)
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        pos += 12 + length

    assert meta["depth"] == 8, f"unsupported bit depth {meta['depth']}"
    assert meta["interlace"] == 0, "interlaced png unsupported"
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[meta["color"]]
    w, h = meta["w"], meta["h"]
    raw = zlib.decompress(bytes(idat))
    stride = w * channels

    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p : p + stride])
        p += stride
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return w, h, channels, bytes(out)


def main(path, xmax):
    w, h, ch, px = decode_png(path)
    print(f"{path}\n  {w}x{h}, {ch} channels\n")

    def at(x, y):
        i = (y * w + x) * ch
        r, g, b = px[i], px[i + 1], px[i + 2]
        a = px[i + 3] if ch == 4 else 255
        return r, g, b, a

    navy, green = [], []
    for y in range(h):
        for x in range(min(w, xmax)):
            r, g, b, a = at(x, y)
            if a < 140:
                continue
            # navy is very dark (~#07264D): blue clearly dominant, all channels low
            if b > 40 and b > r + 25 and g < 95 and r < 80:
                navy.append((x, y))
            # green (~#038F5F)
            elif g > 90 and g > r + 50 and g > b + 30:
                green.append((x, y))

    for name, pts in (("navy", navy), ("green", green)):
        if not pts:
            print(f"  {name}: none found")
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        print(f"  {name}: bbox x {min(xs)}..{max(xs)} (w {max(xs)-min(xs)+1}), "
              f"y {min(ys)}..{max(ys)} (h {max(ys)-min(ys)+1}), {len(pts)} px")

    gset = set(green)
    nset = set(navy)

    # green stroke width, measured across a row through the middle of the bubble
    gys = [p[1] for p in green]
    mid = (min(gys) + max(gys)) // 2
    row = sorted(x for (x, y) in green if y == mid)
    runs = []
    if row:
        start = prev = row[0]
        for x in row[1:]:
            if x != prev + 1:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
    print(f"\n  green runs on row y={mid}: "
          + ", ".join(f"{a}-{b} (w{b-a+1})" for a, b in runs))

    # vertical runs down the middle of the green bubble
    gxs = [p[0] for p in green]
    cx = (min(gxs) + max(gxs)) // 2
    col = sorted(y for (x, y) in green if x == cx)
    vruns = []
    if col:
        start = prev = col[0]
        for y in col[1:]:
            if y != prev + 1:
                vruns.append((start, prev))
                start = y
            prev = y
        vruns.append((start, prev))
    print(f"  green runs on col x={cx}: "
          + ", ".join(f"{a}-{b} (h{b-a+1})" for a, b in vruns))

    # navy check vs navy bubble: the check lives inside the green bubble's box
    if green and navy:
        gx0, gx1 = min(gxs), max(gxs)
        gy0, gy1 = min(gys), max(gys)
        inside = [(x, y) for (x, y) in navy if gx0 < x < gx1 and gy0 < y < gy1]
        outside = [(x, y) for (x, y) in navy if not (gx0 < x < gx1 and gy0 < y < gy1)]
        for name, pts in (("navy check (inside green)", inside),
                          ("navy bubble (outside green)", outside)):
            if not pts:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            print(f"\n  {name}: x {min(xs)}..{max(xs)} (w {max(xs)-min(xs)+1}), "
                  f"y {min(ys)}..{max(ys)} (h {max(ys)-min(ys)+1})")

        # check geometry: leftmost, lowest (the vertex), rightmost
        if inside:
            lo = min(inside, key=lambda p: p[0])
            vertex = max(inside, key=lambda p: p[1])
            hi = max(inside, key=lambda p: p[0])
            print(f"    left tip  ~{lo}")
            print(f"    vertex    ~{vertex}")
            print(f"    right tip ~{hi}")
            ys_check = [p[1] for p in inside]
            top_row = min(ys_check)
            tops = [x for (x, y) in inside if y <= top_row + 2]
            print(f"    topmost x range at y~{top_row}: {min(tops)}..{max(tops)}")

    # green tail: rows below the bubble body
    if green:
        gy1 = max(gys)
        for probe in (gy1 - 4, gy1 - 30, gy1 - 60):
            r = sorted(x for (x, y) in green if y == probe)
            if r:
                print(f"  green row y={probe}: x {min(r)}..{max(r)}")

    # navy tail extent below the navy bubble body
    if navy:
        nys = [p[1] for p in navy]
        ny1 = max(nys)
        for probe in (ny1 - 4, ny1 - 40):
            r = sorted(x for (x, y) in navy if y == probe)
            if r:
                print(f"  navy row y={probe}: x {min(r)}..{max(r)}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10**9)
