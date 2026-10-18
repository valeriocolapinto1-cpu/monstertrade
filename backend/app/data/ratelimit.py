import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Token bucket: al massimo `capacity` richieste, ricaricate a `rate` al secondo."""

    def __init__(
        self,
        capacity: int,
        per_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if capacity < 1 or per_seconds <= 0:
            raise ValueError("capacity >= 1 e per_seconds > 0")
        self.capacity = capacity
        self.rate = capacity / per_seconds
        self._tokens = float(capacity)
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = self._clock()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                self._sleep((1 - self._tokens) / self.rate)
