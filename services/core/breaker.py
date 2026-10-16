"""A small circuit breaker per external provider (OpenAI, push, Stripe)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    reset_timeout_s: float = 30.0
    failures: int = 0
    opened_at: float | None = None
    _clock: callable = field(default=time.monotonic, repr=False)

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self._clock() - self.opened_at >= self.reset_timeout_s:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        if self.state == "half_open":
            self.opened_at = self._clock()
            return
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = self._clock()

    async def call(self, fn, *args, **kwargs):
        if not self.allow():
            raise CircuitOpenError(self.name)
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


def all_states() -> dict[str, str]:
    for n in ("openai", "push", "stripe"):
        get_breaker(n)
    return {n: b.state for n, b in _breakers.items()}


def reset_all() -> None:
    _breakers.clear()
