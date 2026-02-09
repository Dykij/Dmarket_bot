"""Redis-based distributed cache for DMarket Bot.

This module provides a Redis-backed cache implementation for distributed
caching across multiple bot instances, with TTL support and async operations.
"""

import logging
from typing import Any, cast

import orjson

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None  # type: ignore[assignment]

from src.utils.memory_cache import TTLCache

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-based distributed cache with TTL support.

    Features:
    - Distributed caching across multiple instances
    - TTL (Time To Live) support
    - Async operations
    - Automatic fallback to in-memory cache if Redis unavailable
    - Pickle serialization for complex objects
    """

    def __init__(
        self,
        redis_url: str | None = None,
        default_ttl: int = 300,
        fallback_to_memory: bool = True,
        max_memory_size: int = 1000,
        max_connections: int = 50,
        socket_keepalive: bool = True,
    ):
        """Initialize Redis cache with optimized connection pooling.

        Args:
            redis_url: Redis connection URL (redis://localhost:6379/0)
            default_ttl: Default TTL in seconds (default: 300 = 5 minutes)
            fallback_to_memory: Use in-memory cache if Redis unavailable
            max_connections: Maximum connections in pool (default: 50)
            socket_keepalive: Enable TCP keepalive
            max_memory_size: Max size for fallback memory cache
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.socket_keepalive = socket_keepalive
        self._redis: aioredis.Redis[bytes] | None = None
        self._connected = False

        # Fallback to in-memory cache
        self._fallback_enabled = fallback_to_memory
        self._memory_cache: TTLCache | None = None
        if fallback_to_memory:
            self._memory_cache = TTLCache(
                max_size=max_memory_size,
                default_ttl=default_ttl,
            )

        # Statistics
        self._hits = 0
        self._misses = 0
        self._errors = 0

    async def connect(self) -> bool:
        """Connect to Redis server.

        Returns:
            True if connected successfully, False otherwise
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis library not available. Install with: pip install redis[hiredis]")
            if self._fallback_enabled:
                logger.info("Falling back to in-memory cache")
                return False
            raise RuntimeError("Redis not available and fallback disabled")

        if not self.redis_url:
            logger.warning("Redis URL not configured. Using in-memory cache")
            return False

        try:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We'll handle encoding ourselves
                max_connections=self.max_connections,
                socket_keepalive=self.socket_keepalive,
                socket_keepalive_options=(
                    {
                        1: 1,  # TCP_KEEPIDLE
                        2: 1,  # TCP_KEEPINTVL
                        3: 3,  # TCP_KEEPCNT
                    }
                    if self.socket_keepalive
                    else None
                ),
            )

            # Test connection
            await self._redis.ping()

            self._connected = True
            logger.info(
                f"Connected to Redis at {self.redis_url} (pool size: {self.max_connections})"
            )
            return True

        except Exception:
            logger.exception("Failed to connect to Redis")
            self._connected = False

            if not self._fallback_enabled:
                raise

            logger.info("Falling back to in-memory cache")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")

        if self._memory_cache:
            await self._memory_cache.stop_cleanup()

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        # Try Redis first
        if self._connected and self._redis:
            try:
                value = await self._redis.get(key)
                if value is not None:
                    self._hits += 1
                    return orjson.loads(value)
                self._misses += 1
                return None
            except Exception:
                logger.exception("Redis get error for key %s", key)
                self._errors += 1
                # Fall through to memory cache

        # Fallback to memory cache
        if self._memory_cache:
            value = await self._memory_cache.get(key)
            if value is not None:
                self._hits += 1
            else:
                self._misses += 1
            return value

        self._misses += 1
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default)

        Returns:
            True if successful, False otherwise
        """
        ttl = ttl or self.default_ttl

        # Try Redis first
        if self._connected and self._redis:
            try:
                serialized = orjson.dumps(value)
                await self._redis.setex(key, ttl, serialized)
                return True
            except Exception:
                logger.exception("Redis set error for key %s", key)
                self._errors += 1
                # Fall through to memory cache

        # Fallback to memory cache
        if self._memory_cache:
            await self._memory_cache.set(key, value, ttl)
            return True

        return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        success = False

        # Delete from Redis
        if self._connected and self._redis:
            try:
                result = await self._redis.delete(key)
                success = result > 0
            except Exception:
                logger.exception("Redis delete error for key %s", key)
                self._errors += 1

        # Delete from memory cache
        if self._memory_cache:
            await self._memory_cache.delete(key)
            success = True

        return success

    async def clear(self, pattern: str | None = None) -> int:
        """Clear cache entries.

        Args:
            pattern: Pattern to match keys (e.g., "market:*")
                    If None, clears all keys

        Returns:
            Number of keys deleted
        """
        count = 0

        # Clear from Redis
        if self._connected and self._redis:
            try:
                if pattern:
                    keys = await self._redis.keys(pattern)
                    if keys:
                        count = await self._redis.delete(*keys)
                else:
                    await self._redis.flushdb()
                    count = 1  # Indicate success
            except Exception:
                logger.exception("Redis clear error")
                self._errors += 1

        # Clear from memory cache
        if self._memory_cache:
            if pattern:
                # Memory cache doesn't support patterns, clear all
                await self._memory_cache.clear()
            else:
                await self._memory_cache.clear()

        return count

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        # Check Redis
        if self._connected and self._redis:
            try:
                return bool(await self._redis.exists(key))
            except Exception:
                logger.exception("Redis exists error for key %s", key)
                self._errors += 1

        # Check memory cache
        if self._memory_cache:
            value = await self._memory_cache.get(key)
            return value is not None

        return False

    async def increment(
        self,
        key: str,
        amount: int = 1,
        ttl: int | None = None,
    ) -> int:
        """Increment a counter in cache.

        Args:
            key: Cache key
            amount: Amount to increment by
            ttl: TTL in seconds (None = use default)

        Returns:
            New value after increment
        """
        ttl = ttl or self.default_ttl

        # Use Redis if available (atomic increment)
        if self._connected and self._redis:
            try:
                pipeline = self._redis.pipeline()
                pipeline.incrby(key, amount)
                pipeline.expire(key, ttl)
                results = await pipeline.execute()
                return cast("int", results[0])
            except Exception:
                logger.exception("Redis increment error for key %s", key)
                self._errors += 1

        # Fallback to memory cache (non-atomic)
        if self._memory_cache:
            current = await self._memory_cache.get(key) or 0
            new_value = current + amount
            await self._memory_cache.set(key, new_value, ttl)
            return new_value

        return amount

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        stats: dict[str, Any] = {
            "connected": self._connected,
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "fallback_enabled": self._fallback_enabled,
        }

        # Add memory cache stats if available
        if self._memory_cache:
            stats["memory_cache"] = await self._memory_cache.get_stats()

        return stats

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on cache.

        Returns:
            Health check results
        """
        health: dict[str, Any] = {
            "redis_connected": False,
            "redis_ping": False,
            "memory_cache_available": self._memory_cache is not None,
        }

        if self._connected and self._redis:
            try:
                pong = await self._redis.ping()
                health["redis_connected"] = True
                health["redis_ping"] = pong
            except Exception as e:
                logger.exception("Redis health check failed")
                health["error"] = str(e)

        return health


# Global cache instance (initialized in main.py)
_global_cache: RedisCache | None = None


def get_cache() -> RedisCache:
    """Get global cache instance.

    Returns:
        Global RedisCache instance

    Raises:
        RuntimeError: If cache not initialized
    """
    if _global_cache is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first in main.py")
    return _global_cache


async def init_cache(
    redis_url: str | None = None,
    default_ttl: int = 300,
) -> RedisCache:
    """Initialize global cache instance.

    Args:
        redis_url: Redis connection URL
        default_ttl: Default TTL in seconds

    Returns:
        Initialized RedisCache instance
    """
    global _global_cache

    _global_cache = RedisCache(
        redis_url=redis_url,
        default_ttl=default_ttl,
        fallback_to_memory=True,
    )

    await _global_cache.connect()

    logger.info("Global cache initialized")

    return _global_cache


async def close_cache() -> None:
    """Close global cache instance."""
    global _global_cache

    if _global_cache:
        await _global_cache.disconnect()
        _global_cache = None
        logger.info("Global cache closed")


# ============================================================================
# Hierarchical Cache (Roadmap Task #6)
# ============================================================================


class CacheKey:
    """Helper class for building hierarchical cache keys.

    Roadmap Task #6: Hierarchical caching with smart TTL
    """

    # Cache prefixes
    MARKET_ITEMS = "market:items"
    BALANCE = "balance"
    TARGETS = "targets"
    USER_SETTINGS = "user:settings"
    USER_PROFILE = "user:profile"
    ARBITRAGE_RESULTS = "arbitrage:results"
    SALES_HISTORY = "sales:history"

    @staticmethod
    def market_items(
        game: str,
        level: str | None = None,
        price_from: int | None = None,
        price_to: int | None = None,
    ) -> str:
        """Build cache key for market items.

        Pattern: market:items:{game}:{level}:{price_from}:{price_to}

        Args:
            game: Game identifier (csgo, dota2, etc.)
            level: Arbitrage level (boost, standard, etc.)
            price_from: Min price filter
            price_to: Max price filter

        Returns:
            Hierarchical cache key
        """
        parts = [CacheKey.MARKET_ITEMS, game]

        if level:
            parts.append(level)
        if price_from is not None:
            parts.append(str(price_from))
        if price_to is not None:
            parts.append(str(price_to))

        return ":".join(parts)

    @staticmethod
    def balance(user_id: int) -> str:
        """Build cache key for user balance.

        Pattern: balance:{user_id}
        """
        return f"{CacheKey.BALANCE}:{user_id}"

    @staticmethod
    def targets(user_id: int, game: str | None = None) -> str:
        """Build cache key for user targets.

        Pattern: targets:{user_id}:{game}
        """
        if game:
            return f"{CacheKey.TARGETS}:{user_id}:{game}"
        return f"{CacheKey.TARGETS}:{user_id}"

    @staticmethod
    def user_settings(user_id: int) -> str:
        """Build cache key for user settings.

        Pattern: user:settings:{user_id}
        """
        return f"{CacheKey.USER_SETTINGS}:{user_id}"

    @staticmethod
    def user_profile(user_id: int) -> str:
        """Build cache key for user profile.

        Pattern: user:profile:{user_id}
        """
        return f"{CacheKey.USER_PROFILE}:{user_id}"

    @staticmethod
    def arbitrage_results(game: str, level: str) -> str:
        """Build cache key for arbitrage scan results.

        Pattern: arbitrage:results:{game}:{level}
        """
        return f"{CacheKey.ARBITRAGE_RESULTS}:{game}:{level}"

    @staticmethod
    def sales_history(item_id: str, days: int = 7) -> str:
        """Build cache key for sales history.

        Pattern: sales:history:{item_id}:{days}
        """
        return f"{CacheKey.SALES_HISTORY}:{item_id}:{days}"


class CacheTTL:
    """Smart TTL values for different data types.

    Roadmap Task #6: Dynamic TTL based on data volatility
    """

    # Market data (volatile)
    MARKET_ITEMS = 300  # 5 minutes
    ARBITRAGE_RESULTS = 180  # 3 minutes (faster refresh)
    SALES_HISTORY = 600  # 10 minutes (historical data)

    # User data (semi-static)
    BALANCE = 600  # 10 minutes
    TARGETS = 900  # 15 minutes
    USER_SETTINGS = 1800  # 30 minutes (rarely changes)
    USER_PROFILE = 3600  # 1 hour (very static)

    # Query cache (database)
    DB_QUERY = 600  # 10 minutes

    @staticmethod
    def get_ttl(cache_type: str) -> int:
        """Get TTL for cache type.

        Args:
            cache_type: Cache key prefix (e.g., "market:items")

        Returns:
            TTL in seconds
        """
        ttl_map = {
            CacheKey.MARKET_ITEMS: CacheTTL.MARKET_ITEMS,
            CacheKey.ARBITRAGE_RESULTS: CacheTTL.ARBITRAGE_RESULTS,
            CacheKey.SALES_HISTORY: CacheTTL.SALES_HISTORY,
            CacheKey.BALANCE: CacheTTL.BALANCE,
            CacheKey.TARGETS: CacheTTL.TARGETS,
            CacheKey.USER_SETTINGS: CacheTTL.USER_SETTINGS,
            CacheKey.USER_PROFILE: CacheTTL.USER_PROFILE,
        }

        for prefix, ttl in ttl_map.items():
            if cache_type.startswith(prefix):
                return ttl

        # Default TTL
        return 300


class HierarchicalCache:
    """Enhanced cache with hierarchical key management and smart TTL.

    Roadmap Task #6: Complete hierarchical caching solution

    Features:
    - Hierarchical key structure
    - Smart TTL based on data type
    - Automatic invalidation
    - Batch operations
    - Cache warming support
    """

    def __init__(self, redis_cache: RedisCache):
        """Initialize hierarchical cache.

        Args:
            redis_cache: Underlying Redis cache instance
        """
        self.cache = redis_cache

    async def get_market_items(
        self,
        game: str,
        level: str | None = None,
        price_from: int | None = None,
        price_to: int | None = None,
    ) -> Any | None:
        """Get cached market items.

        Args:
            game: Game identifier
            level: Arbitrage level
            price_from: Min price
            price_to: Max price

        Returns:
            Cached data or None
        """
        key = CacheKey.market_items(game, level, price_from, price_to)
        return await self.cache.get(key)

    async def set_market_items(
        self,
        data: Any,
        game: str,
        level: str | None = None,
        price_from: int | None = None,
        price_to: int | None = None,
    ) -> bool:
        """Cache market items with smart TTL.

        Args:
            data: Data to cache
            game: Game identifier
            level: Arbitrage level
            price_from: Min price
            price_to: Max price

        Returns:
            True if successful
        """
        key = CacheKey.market_items(game, level, price_from, price_to)
        ttl = CacheTTL.MARKET_ITEMS
        return await self.cache.set(key, data, ttl)

    async def get_balance(self, user_id: int) -> Any | None:
        """Get cached user balance."""
        key = CacheKey.balance(user_id)
        return await self.cache.get(key)

    async def set_balance(self, user_id: int, data: Any) -> bool:
        """Cache user balance with smart TTL."""
        key = CacheKey.balance(user_id)
        ttl = CacheTTL.BALANCE
        return await self.cache.set(key, data, ttl)

    async def invalidate_balance(self, user_id: int) -> bool:
        """Invalidate user balance cache."""
        key = CacheKey.balance(user_id)
        return await self.cache.delete(key)

    async def get_targets(self, user_id: int, game: str | None = None) -> Any | None:
        """Get cached user targets."""
        key = CacheKey.targets(user_id, game)
        return await self.cache.get(key)

    async def set_targets(self, user_id: int, data: Any, game: str | None = None) -> bool:
        """Cache user targets with smart TTL."""
        key = CacheKey.targets(user_id, game)
        ttl = CacheTTL.TARGETS
        return await self.cache.set(key, data, ttl)

    async def invalidate_targets(self, user_id: int, game: str | None = None) -> bool:
        """Invalidate user targets cache."""
        key = CacheKey.targets(user_id, game)
        if game:
            # Invalidate specific game
            return await self.cache.delete(key)
        # Invalidate all games for user
        pattern = f"{CacheKey.TARGETS}:{user_id}:*"
        count = await self.cache.clear(pattern)
        return count > 0

    async def get_arbitrage_results(self, game: str, level: str) -> Any | None:
        """Get cached arbitrage scan results."""
        key = CacheKey.arbitrage_results(game, level)
        return await self.cache.get(key)

    async def set_arbitrage_results(self, game: str, level: str, data: Any) -> bool:
        """Cache arbitrage results with smart TTL."""
        key = CacheKey.arbitrage_results(game, level)
        ttl = CacheTTL.ARBITRAGE_RESULTS
        return await self.cache.set(key, data, ttl)

    async def warm_cache(self, games: list[str], levels: list[str]) -> dict[str, int]:
        """Warm cache with common queries.

        Roadmap Task #6: Cache warming on startup

        Args:
            games: List of games to warm
            levels: List of levels to warm

        Returns:
            Statistics about warmed entries
        """
        stats = {"attempted": 0, "succeeded": 0, "failed": 0}

        logger.info("Starting cache warming...")

        # This would be called with actual data from scanner
        # For now, just log the intent
        for game in games:
            for level in levels:
                stats["attempted"] += 1
                key = CacheKey.arbitrage_results(game, level)
                logger.debug(f"Would warm cache for: {key}")

        logger.info(f"Cache warming completed: {stats}")
        return stats

    async def invalidate_market_data(self, game: str | None = None) -> int:
        """Invalidate all market data cache.

        Args:
            game: Specific game to invalidate, or None for all

        Returns:
            Number of keys invalidated
        """
        if game:
            pattern = f"{CacheKey.MARKET_ITEMS}:{game}:*"
        else:
            pattern = f"{CacheKey.MARKET_ITEMS}:*"

        count = await self.cache.clear(pattern)
        logger.info(f"Invalidated {count} market data cache entries")
        return count


# Global hierarchical cache instance
_global_hierarchical_cache: HierarchicalCache | None = None


def get_hierarchical_cache() -> HierarchicalCache:
    """Get global hierarchical cache instance.

    Returns:
        Global HierarchicalCache instance

    Raises:
        RuntimeError: If not initialized
    """
    if _global_hierarchical_cache is None:
        raise RuntimeError(
            "Hierarchical cache not initialized. Call init_hierarchical_cache() first"
        )
    return _global_hierarchical_cache


async def init_hierarchical_cache(redis_cache: RedisCache | None = None) -> HierarchicalCache:
    """Initialize global hierarchical cache.

    Args:
        redis_cache: Redis cache instance (uses global if None)

    Returns:
        Initialized HierarchicalCache
    """
    global _global_hierarchical_cache

    if redis_cache is None:
        redis_cache = get_cache()

    _global_hierarchical_cache = HierarchicalCache(redis_cache)

    logger.info("Hierarchical cache initialized")

    return _global_hierarchical_cache
