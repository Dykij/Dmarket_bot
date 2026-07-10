"""TTL Memory cache."""
import time
from typing import Any


class TTLCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[key] = (value, time.time() + (ttl or self.default_ttl))
