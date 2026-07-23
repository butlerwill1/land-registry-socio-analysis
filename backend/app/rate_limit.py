from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status


class FixedWindowRateLimiter:
    def __init__(self, requests: int, window_seconds: int) -> None:
        self._requests = requests
        self._window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            entries = self._entries[key]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self._requests:
                retry_after = max(1, int(entries[0] + self._window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many data requests. Try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            entries.append(now)


def enforce_data_rate_limit(request: Request, subject: str | None = None) -> None:
    host = request.client.host if request.client else "unknown"
    identity = subject or host
    request.app.state.data_rate_limiter.check(identity)
