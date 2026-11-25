#!/usr/bin/env python3
"""Rasterise logo.svg (rounded square + glass ring + bottle glyph) into PNG/ICO icons.

Pure standard library: SVG delegates are not available in this environment,
so the same geometry is drawn with signed distance functions and anti-aliasing.
Run: python3 tools/make_icons.py
"""
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icons"

BG = (0x15, 0x17, 0x17)
GOLD = (0xE4, 0xBC, 0x76)
VB = 48.0  # viewBox size
RADIUS = 12.0

# Bottle glyph from logo.svg, in viewBox units.
SEGMENTS = [
    ((12, 9), (12, 39)),
    ((9, 18), (15, 18)),
    ((9, 22), (15, 22)),
    ((6, 31), (24, 31)),
    ((18, 8), (18, 36)),
]
STROKE = 2.5
RING_R = 20.0
RING_W = 1.0


def rounded_box_sdf(x, y, cx, cy, half, r):
    qx = abs(x - cx) - (half - r)
    qy = abs(y - cy) - (half - r)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def segment_distance(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    length2 = vx * vx + vy * vy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length2))
    return math.hypot(wx - t * vx, wy - t * vy)


def coverage(sdf, unit):
    """sdf in viewBox units; unit = viewBox units per pixel."""
    return max(0.0, min(1.0, 0.5 - sdf / unit))


def render(size):
    unit = VB / size
    rows = []
    for py in range(size):
        y = (py + 0.5) * unit
        row = bytearray()
        for px in range(size):
            x = (px + 0.5) * unit
            a = coverage(rounded_box_sdf(x, y, VB / 2, VB / 2, VB / 2, RADIUS), unit)
            if a <= 0:
                row += b"\x00\x00\x00\x00"
                continue
            r, g, b = BG
            ring = coverage(abs(math.hypot(x - 24, y - 24) - RING_R) - RING_W / 2, unit)
            glyph = 0.0
            for (ax, ay), (bx, by) in SEGMENTS:
                glyph = max(glyph, coverage(segment_distance(x, y, ax, ay, bx, by) - STROKE / 2, unit))
            ink = max(ring, glyph)
            if ink > 0:
                r = round(r + (GOLD[0] - r) * ink)
                g = round(g + (GOLD[1] - g) * ink)
                b = round(b + (GOLD[2] - b) * ink)
            alpha = round(a * 255)
            row += bytes((r, g, b, alpha))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))
    path.write_bytes(data)


def write_ico(path, pngs):
    """ICO container with PNG payloads (supported by all current browsers)."""
    count = len(pngs)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = b""
    payload = b""
    for size, data in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        payload += data
    path.write_bytes(header + entries + payload)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        write_png(OUT / name, size, render(size))
        print("written", OUT / name)
    ico_sizes = []
    for size in (16, 32, 48):
        tmp = OUT / f".tmp-{size}.png"
        write_png(tmp, size, render(size))
        ico_sizes.append((size, tmp.read_bytes()))
        tmp.unlink()
    write_ico(ROOT / "favicon.ico", ico_sizes)
    print("written", ROOT / "favicon.ico")


if __name__ == "__main__":
    main()
