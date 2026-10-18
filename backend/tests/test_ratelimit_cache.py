from pathlib import Path

import pandas as pd
import pytest

from app.data.cache import FrameCache
from app.data.ratelimit import RateLimiter
from tests.conftest import ohlcv


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_rate_limiter_blocks_after_capacity() -> None:
    clock = FakeClock()
    limiter = RateLimiter(capacity=8, per_seconds=60, clock=clock.time, sleep=clock.sleep)
    for _ in range(8):
        limiter.acquire()
    assert clock.slept == []
    limiter.acquire()
    assert clock.slept and clock.slept[0] == pytest.approx(7.5)


def test_rate_limiter_rejects_bad_config() -> None:
    with pytest.raises(ValueError):
        RateLimiter(capacity=0, per_seconds=1)


def test_cache_roundtrip_and_expiry(tmp_path: Path) -> None:
    cache = FrameCache(tmp_path)
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    frame = ohlcv(idx, [1.0, 2.0, 3.0])
    assert cache.get("k", 60) is None
    cache.set("k", frame)
    got = cache.get("k", 60)
    assert got is not None
    pd.testing.assert_frame_equal(got, frame, check_freq=False, check_names=False)
    assert cache.get("k", -1) is None
