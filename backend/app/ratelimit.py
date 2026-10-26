"""Simple in-memory sliding-window rate limiter (per process). Use Redis for multi-instance deployments."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .errors import APIError


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 3600.0) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > window_seconds:
                events.popleft()
            if len(events) >= limit:
                retry = int(window_seconds - (now - events[0])) + 1
                raise APIError(429, "rate_limited", f"You're going fast! Please try again in about {retry // 60 + 1} min.")
            events.append(now)
