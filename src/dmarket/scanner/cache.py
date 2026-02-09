"""Cache management for arbitrage scanner.

This module provides caching functionality for:
- API response caching with TTL
- Cache key generation
- Cache invalidation
- Statistics tracking (hits, misses, evictions)

Uses in-memory TTLCache for fast access.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ScannerCache:
    """Cache manager for arbitrage scanner results.

    Provides TTL-based caching with statistics tracking.

    Attributes:
        ttl: Time-to-live for cache entries in seconds
        max_size: Maximum number of entries in cache
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000) -> None:
        """Initialize scanner cache.

        Args:
            ttl: Default time-to-live in seconds (default: 300)
            max_size: Maximum cache size (default: 1000)
        """
        self._cache: dict[str, tuple[list[dict[str, Any]], float]] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def ttl(self) -> int:
        """Get current TTL value."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        """Set TTL value."""
        if value < 0:
            raise ValueError("TTL must be non-negative")
        self._ttl = value

    def _make_key(self, key: str | tuple[Any, ...]) -> str:
        """Create string key from various input types.

        Args:
            key: Cache key (string or tuple)

        Returns:
            String cache key
        """
        if isinstance(key, tuple):
            return "_".join(str(k) for k in key)
        return str(key)

    def get(self, key: str | tuple[Any, ...]) -> list[dict[str, Any]] | None:
        """Get cached results if not expired.

        Args:
            key: Cache key

        Returns:
            Cached results or None if not found/expired
        """
        cache_key = self._make_key(key)
        entry = self._cache.get(cache_key)

        if entry is None:
            self._misses += 1
            return None

        items, timestamp = entry
        # TTL=0 means no expiration
        if self._ttl > 0 and time.time() - timestamp > self._ttl:
            # Entry expired
            del self._cache[cache_key]
            self._misses += 1
            self._evictions += 1
            logger.debug("Cache entry expired", extra={"key": cache_key})
            return None

        self._hits += 1
        logger.debug(
            "Cache hit",
            extra={"key": cache_key, "items_count": len(items)},
        )
        return items

    def set(
        self,
        key: str | tuple[Any, ...],
        items: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> None:
        """Save results to cache.

        Args:
            key: Cache key
            items: Results to cache
            ttl: Optional custom TTL (uses default if None)
        """
        # Evict oldest entries if cache is full
        if len(self._cache) >= self._max_size:
            self._evict_oldest()

        cache_key = self._make_key(key)
        self._cache[cache_key] = (items, time.time())
        logger.debug(
            "Cache set",
            extra={
                "key": cache_key,
                "items_count": len(items),
                "ttl": ttl or self._ttl,
            },
        )

    def _evict_oldest(self) -> None:
        """Evict oldest cache entry."""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]
        self._evictions += 1
        logger.debug("Cache eviction", extra={"evicted_key": oldest_key})

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        logger.info("Cache cleared")

    def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries matching pattern.

        Args:
            pattern: Key pattern to match (None clears all)

        Returns:
            Number of entries invalidated
        """
        if pattern is None:
            count = len(self._cache)
            self.clear()
            return count

        keys_to_remove = [k for k in self._cache if pattern in k]
        for key in keys_to_remove:
            del self._cache[key]
            self._evictions += 1

        logger.info(
            "Cache invalidated",
            extra={"pattern": pattern, "count": len(keys_to_remove)},
        )
        return len(keys_to_remove)

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats including:
            - size: Current number of entries
            - max_size: Maximum entries
            - ttl: Time-to-live in seconds
            - hits: Number of cache hits
            - misses: Number of cache misses
            - evictions: Number of evictions
            - hit_rate: Hit rate percentage
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": round(hit_rate, 2),
        }

    def __len__(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def __contains__(self, key: str | tuple[Any, ...]) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None


def generate_cache_key(
    level: str,
    game: str,
    extra: dict[str, Any] | None = None,
) -> str:
    """Generate cache key for scanner results.

    Args:
        level: Arbitrage level
        game: Game code
        extra: Additional parameters to include in key

    Returns:
        Cache key string
    """
    parts = [f"scanner:{level}:{game}"]
    if extra:
        for k, v in sorted(extra.items()):
            parts.append(f"{k}={v}")
    return ":".join(parts)
