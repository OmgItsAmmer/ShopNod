"""UUIDv7 generation (time-ordered, strictly monotonic within a process)."""
from __future__ import annotations

import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0


def uuid7() -> uuid.UUID:
    global _last_ms, _counter
    with _lock:
        ms = int(time.time() * 1000) & ((1 << 48) - 1)
        if ms <= _last_ms:  # same millisecond (or clock went back): keep ordering with a 12-bit counter
            ms = _last_ms
            _counter += 1
            if _counter >= 1 << 12:
                ms += 1
                _counter = 0
        else:
            _counter = int.from_bytes(os.urandom(2), "big") & 0x3FF  # start low so the counter has headroom
        _last_ms = ms
        counter = _counter
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms << 80) | (0x7 << 76) | (counter << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)
