"""Simple in-process fixed-window rate limiter (ADR-018).

The mission requires rate limits on credential validation, payment
initiation, and webhooks. This is an in-memory, per-process fixed-window
limiter keyed by identity. It is intentionally small and bounded (expired
windows are pruned on access) and is documented as single-process only;
distributed rate limiting is out of scope for V3.
"""

import threading
import time


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests < 1 or window_seconds <= 0:
            raise ValueError("max_requests and window_seconds must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._counts: dict[str, tuple[int, float]] = {}

    def allow(self, key: str) -> bool:
        """Return True when the key is within budget, consuming one slot."""
        now = time.monotonic()
        with self._lock:
            count, window_start = self._counts.get(key, (0, now))
            if now - window_start >= self.window_seconds:
                count, window_start = 0, now
            if count >= self.max_requests:
                self._counts[key] = (count, window_start)
                return False
            self._counts[key] = (count + 1, window_start)
            self._prune(now)
            return True

    def reset(self) -> None:
        """Clear all recorded windows so a fresh test case starts unthrottled."""
        with self._lock:
            self._counts.clear()

    def retry_after_seconds(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            _, window_start = self._counts.get(key, (0, now))
            return max(0, int(self.window_seconds - (now - window_start)) + 1)

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, (_, window_start) in self._counts.items()
            if now - window_start >= self.window_seconds
        ]
        for key in expired:
            del self._counts[key]