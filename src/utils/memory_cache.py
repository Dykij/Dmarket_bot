"""TTL Memory cache.

v15.2: Uses OrderedDict for O(1) eviction instead of O(n) min-scan.
"""
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 300) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    async def get(self, key: str) -> Any:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.time() > expiry:
            del self._cache[key]
            return None
        # Move to end (most recently accessed)
        self._cache.move_to_end(key)
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if len(self._cache) >= self.max_size:
            # O(1): evict oldest (first) entry
            self._cache.popitem(last=False)
        self._cache[key] = (value, time.time() + (ttl or self.default_ttl))
        self._cache.move_to_end(key)
