"""Generate the PWA icons (a white check mark on brand blue) with only the standard library."""
import math
import struct
import zlib
from pathlib import Path

BLUE = (0x4B, 0x68, 0xFF)
WHITE = (255, 255, 255)
YELLOW = (0xFF, 0xE2, 0x4B)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def render(size, maskable):
    ss = 3
    rows = []
    pad = 0.0 if maskable else 0.0
    radius = 0.0 if maskable else size * 0.22
    scale = 0.62 if maskable else 0.78  # maskable icons need a larger safe zone
    # check mark geometry in unit square
    pts = [(0.27, 0.54), (0.43, 0.70), (0.74, 0.34)]
    for y in range(size):
        row = bytearray()
        for x in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                for sx in range(ss):
                    px, py = x + (sx + 0.5) / ss, y + (sy + 0.5) / ss
                    inside = True
                    if radius:
                        cx = min(max(px, radius), size - radius)
                        cy = min(max(py, radius), size - radius)
                        inside = math.hypot(px - cx, py - cy) <= radius
                    if not inside:
                        continue
                    col = BLUE
                    u, v = (px / size - 0.5) / scale + 0.5, (py / size - 0.5) / scale + 0.5
                    d = min(seg_dist(u, v, *pts[0], *pts[1]), seg_dist(u, v, *pts[1], *pts[2]))
                    if d < 0.055:
                        col = WHITE
                    elif math.hypot(u - 0.80, v - 0.24) < 0.07:  # yellow "offer" dot
                        col = YELLOW
                    r += col[0]; g += col[1]; b += col[2]; a += 255
            n = ss * ss
            row += bytes((r // n, g // n, b // n, a // n))
        rows.append(bytes(row))
    return rows


def write_png(path, size, maskable=False):
    rows = render(size, maskable)
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "public"
    out.mkdir(exist_ok=True)
    write_png(out / "icon-192.png", 192)
    write_png(out / "icon-512.png", 512)
    write_png(out / "icon-maskable-512.png", 512, maskable=True)
    write_png(out / "apple-touch-icon.png", 180, maskable=True)
    print("icons written to", out)
