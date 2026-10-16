"""UUIDv7 generation (time-ordered)."""
from __future__ import annotations

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = (rand >> 62) & 0xFFF  # 12 bits
    rand_b = rand & ((1 << 62) - 1)  # 62 bits
    value = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)
