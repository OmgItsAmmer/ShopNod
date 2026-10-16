"""Location without PostGIS: geohash6 cells + Haversine (Plan 3 §0.3)."""
from __future__ import annotations

import math

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_DECODE = {c: i for i, c in enumerate(_BASE32)}
EARTH_RADIUS_M = 6_371_000.0


def encode(lat: float, lng: float, precision: int = 6) -> str:
    lat_i, lng_i = (-90.0, 90.0), (-180.0, 180.0)
    bits, bit, ch, even = 0, 0, 0, True
    out = []
    while len(out) < precision:
        if even:
            mid = (lng_i[0] + lng_i[1]) / 2
            if lng >= mid:
                ch = (ch << 1) | 1
                lng_i = (mid, lng_i[1])
            else:
                ch <<= 1
                lng_i = (lng_i[0], mid)
        else:
            mid = (lat_i[0] + lat_i[1]) / 2
            if lat >= mid:
                ch = (ch << 1) | 1
                lat_i = (mid, lat_i[1])
            else:
                ch <<= 1
                lat_i = (lat_i[0], mid)
        even = not even
        bit += 1
        if bit == 5:
            out.append(_BASE32[ch])
            bit, ch = 0, 0
    _ = bits
    return "".join(out)


def decode(gh: str) -> tuple[float, float]:
    """Cell centre (lat, lng)."""
    lat_i, lng_i = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for c in gh:
        cd = _DECODE[c]
        for mask in (16, 8, 4, 2, 1):
            iv = lng_i if even else lat_i
            mid = (iv[0] + iv[1]) / 2
            if cd & mask:
                iv[0] = mid
            else:
                iv[1] = mid
            even = not even
    return (sum(lat_i) / 2, sum(lng_i) / 2)


def _cell_size(gh: str) -> tuple[float, float]:
    """(lat height, lng width) in degrees of a cell."""
    lat_bits = (5 * len(gh)) // 2
    lng_bits = 5 * len(gh) - lat_bits
    return 180.0 / (1 << lat_bits), 360.0 / (1 << lng_bits)


def neighbours(gh: str) -> list[str]:
    """The cell itself plus the 8 around it (9 total, de-duplicated)."""
    lat, lng = decode(gh)
    dlat, dlng = _cell_size(gh)
    cells: list[str] = []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            la = max(-89.999999, min(89.999999, lat + i * dlat))
            lo = lng + j * dlng
            if lo > 180:
                lo -= 360
            elif lo < -180:
                lo += 360
            c = encode(la, lo, len(gh))
            if c not in cells:
                cells.append(c)
    return cells


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def round_distance_m(d: float, step: int = 50) -> int:
    """Every distance shown or sent is rounded to 50 m."""
    return int(round(d / step) * step)


# Haversine as a Postgres function, created by the first migration.
HAVERSINE_SQL = """
CREATE OR REPLACE FUNCTION haversine_m(lat1 double precision, lng1 double precision,
                                       lat2 double precision, lng2 double precision)
RETURNS double precision LANGUAGE sql IMMUTABLE AS $$
  SELECT 2 * 6371000 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2) +
    cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lng2 - lng1) / 2), 2)))
$$;
"""
