"""Process-local request limits.

Counters live in this process only. A restart clears them. Rejected calls are
not recorded, so a window holds accepted calls and stays bounded by the limit.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


def client_address(
    *,
    peer: str | None,
    forwarded_for: str = "",
    real_ip: str = "",
    trusted_proxy_count: int = 1,
) -> str:
    if trusted_proxy_count <= 0:
        return peer or "unknown"
    real = real_ip.strip()
    if real:
        return real
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if hops:
        if len(hops) >= trusted_proxy_count:
            return hops[-trusted_proxy_count]
        return hops[-1]
    return peer or "unknown"


class SlidingWindow:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = time.monotonic if clock is None else clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        cutoff = now - self._window
        with self._lock:
            if len(self._hits) > 1024:
                stale = [
                    item
                    for item, hits in self._hits.items()
                    if not hits or hits[-1] <= cutoff
                ]
                for item in stale:
                    del self._hits[item]
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            else:
                while hits and hits[0] <= cutoff:
                    hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True


class DistinctCap:
    """Admit each new key until `limit` distinct keys are stored.

    A key that was already admitted is admitted again and does not consume
    another slot.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._lock = threading.Lock()
        self._keys: set[str] = set()

    def reserve(self, key: str) -> bool:
        with self._lock:
            if key in self._keys:
                return True
            if len(self._keys) >= self._limit:
                return False
            self._keys.add(key)
            return True
