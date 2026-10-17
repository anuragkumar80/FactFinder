"""In-memory sliding-window rate limiter (per client IP). Fine for a single-process demo."""
import threading
import time
from collections import defaultdict, deque

from .errors import RateLimited


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record a hit, or raise RateLimited if `key` is over the limit."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                wait = int(self.window - (now - q[0])) + 1
                raise RateLimited(f"Too many live checks. Try again in about {wait} seconds, "
                                  f"or pick a demo claim (those load instantly).")
            q.append(now)
