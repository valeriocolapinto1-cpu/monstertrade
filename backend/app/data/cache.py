import gzip
import hashlib
import io
import time
from pathlib import Path

import pandas as pd

from app.data.models import normalize_ohlcv


class FrameCache:
    """Cache su disco delle risposte delle fonti (CSV compresso), con scadenza."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self.directory / f"{digest}.csv.gz"

    def get(self, key: str, ttl_seconds: float) -> pd.DataFrame | None:
        path = self._path(key)
        if not path.exists() or time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        frame = pd.read_csv(path, index_col="ts", parse_dates=["ts"], compression="gzip")
        return normalize_ohlcv(frame)

    def set(self, key: str, frame: pd.DataFrame) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        frame.to_csv(buffer, index_label="ts")
        tmp = self._path(key).with_suffix(".tmp")
        with tmp.open("wb") as handle:
            handle.write(gzip.compress(buffer.getvalue().encode()))
        tmp.replace(self._path(key))
