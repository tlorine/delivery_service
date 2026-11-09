import time
from collections import deque

from app.core.errors import RateLimited


class SlidingWindowLimiter:
    """In-process limiter. Valid while the API runs as a single instance (ADR-0006: move to proxy/Redis
    when scaling out)."""

    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 100_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> None:
        now = time.monotonic()
        if len(self._hits) > self.max_keys:
            self._hits.clear()
        q = self._hits.setdefault(key, deque())
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise RateLimited(extra={"retry_after_seconds": int(self.window - (now - q[0])) + 1})
        q.append(now)
