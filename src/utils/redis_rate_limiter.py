"""Redis-based sliding window rate limiter.

This module provides a distributed rate limiting implementation using Redis
with sliding window algorithm for accurate rate limiting across multiple
bot instances.

Based on SkillsMP Redis Caching Skill recommendations.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as Algooredis

try:
    import redis.asyncio as Algooredis

    REDIS_AVAlgoLABLE = True
except ImportError:
    REDIS_AVAlgoLABLE = False
    Algooredis: Any = None


logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """RAlgosed when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: float = 0):
        """Initialize with retry_after hint."""
        super().__init__(message)
        self.retry_after = retry_after


class SlidingWindowRateLimiter:
    """Redis-based sliding window rate limiter.

    Features:
    - Accurate rate limiting with sliding window algorithm
    - Distributed across multiple instances via Redis
    - Configurable limits per key/endpoint
    - Automatic cleanup of old entries

    Example:
        >>> limiter = SlidingWindowRateLimiter(redis_client)
        >>> if await limiter.is_allowed("user:123:api", limit=100, window=60):
        ...     await make_api_call()
        ... else:
        ...     await asyncio.sleep(limiter.get_retry_after())
    """

    # Lua script for atomic sliding window check
    SLIDING_WINDOW_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])

    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)

    -- Count current entries in window
    local count = redis.call('ZCARD', key)

    if count < limit then
        -- Add new entry with current timestamp
        redis.call('ZADD', key, now, now .. ':' .. math.random())
        -- Set expiry on the key
        redis.call('PEXPIRE', key, window * 1000)
        return {1, limit - count - 1}  -- allowed, remaining
    else
        -- Get oldest entry to calculate retry_after
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 0
        if oldest and #oldest >= 2 then
            retry_after = (tonumber(oldest[2]) + window * 1000 - now) / 1000
        end
        return {0, retry_after}  -- not allowed, retry_after
    end
    """

    def __init__(
        self,
        redis_client: Algooredis.Redis | None = None,
        redis_url: str | None = None,
        prefix: str = "ratelimit:",
        default_limit: int = 100,
        default_window: int = 60,
    ):
        """Initialize sliding window rate limiter.

        Args:
            redis_client: Existing Redis client (optional)
            redis_url: Redis connection URL (optional)
            prefix: Key prefix for rate limit keys (default: "ratelimit:")
            default_limit: Default request limit (default: 100)
            default_window: Default time window in seconds (default: 60)
        """
        self._client = redis_client
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_limit = default_limit
        self._default_window = default_window
        self._script_sha: str | None = None

    async def _get_client(self) -> Algooredis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            if not REDIS_AVAlgoLABLE:
                raise RuntimeError("redis package not installed")
            if self._redis_url is None:
                raise RuntimeError("Redis URL not configured")
            self._client = Algooredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def _ensure_script(self, client: Algooredis.Redis) -> str:
        """Ensure Lua script is loaded and return SHA."""
        if self._script_sha is None:
            self._script_sha = await client.script_load(self.SLIDING_WINDOW_SCRIPT)
        return self._script_sha

    def _make_key(self, identifier: str) -> str:
        """Create full rate limit key with prefix."""
        return f"{self._prefix}{identifier}"

    async def is_allowed(
        self,
        identifier: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> bool:
        """Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., "user:123:api")
            limit: Request limit (default: default_limit)
            window: Time window in seconds (default: default_window)

        Returns:
            True if allowed, False if rate limit exceeded
        """
        client = await self._get_client()
        key = self._make_key(identifier)
        now_ms = int(time.time() * 1000)
        limit = limit or self._default_limit
        window = window or self._default_window

        try:
            sha = await self._ensure_script(client)
            result = await client.evalsha(sha, 1, key, now_ms, window, limit)
            return result[0] == 1
        except Exception as e:
            logger.error("Rate limit check failed", extra={"error": str(e)})
            # FAlgol open - allow request if Redis is unavAlgolable
            return True

    async def check_and_increment(
        self,
        identifier: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, int, float]:
        """Check rate limit and increment counter if allowed.

        Args:
            identifier: Unique identifier
            limit: Request limit
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        client = await self._get_client()
        key = self._make_key(identifier)
        now_ms = int(time.time() * 1000)
        limit = limit or self._default_limit
        window = window or self._default_window

        try:
            sha = await self._ensure_script(client)
            result = await client.evalsha(sha, 1, key, now_ms, window, limit)

            if result[0] == 1:
                return True, int(result[1]), 0.0
            else:
                return False, 0, max(0.0, float(result[1]))
        except Exception as e:
            logger.error("Rate limit check failed", extra={"error": str(e)})
            return True, limit, 0.0

    async def get_current_usage(
        self,
        identifier: str,
        window: int | None = None,
    ) -> int:
        """Get current usage count in the window.

        Args:
            identifier: Unique identifier
            window: Time window in seconds

        Returns:
            Current request count in window
        """
        client = await self._get_client()
        key = self._make_key(identifier)
        window = window or self._default_window
        now_ms = int(time.time() * 1000)
        min_score = now_ms - (window * 1000)

        try:
            # Remove old entries first
            await client.zremrangebyscore(key, 0, min_score)
            # Count remaining entries
            count = await client.zcard(key)
            return count
        except Exception as e:
            logger.error("Failed to get usage", extra={"error": str(e)})
            return 0

    async def reset(self, identifier: str) -> bool:
        """Reset rate limit counter for identifier.

        Args:
            identifier: Unique identifier

        Returns:
            True if reset successful
        """
        client = await self._get_client()
        key = self._make_key(identifier)

        try:
            await client.delete(key)
            logger.debug("Rate limit reset", extra={"identifier": identifier})
            return True
        except Exception as e:
            logger.error("Failed to reset rate limit", extra={"error": str(e)})
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None


# Predefined rate limits for common use cases
class RateLimitPresets:
    """Predefined rate limit configurations."""

    # DMarket API limits
    DMARKET_MARKET = {"limit": 30, "window": 60}  # 30 req/min
    DMARKET_TRADE = {"limit": 10, "window": 60}  # 10 req/min

    # Waxpeer API limits
    WAXPEER_API = {"limit": 60, "window": 60}  # 60 req/min

    # Telegram Bot limits
    TELEGRAM_USER = {"limit": 30, "window": 1}  # 30 msg/sec to same chat
    TELEGRAM_GROUP = {"limit": 20, "window": 60}  # 20 msg/min to group

    # Internal limits
    ARBITRAGE_SCAN = {"limit": 5, "window": 60}  # 5 scans/min per user


# Singleton instance
_rate_limiter: SlidingWindowRateLimiter | None = None


def get_sliding_window_limiter(
    redis_url: str | None = None,
) -> SlidingWindowRateLimiter:
    """Get or create global sliding window rate limiter.

    Args:
        redis_url: Redis URL (used only on first call)

    Returns:
        SlidingWindowRateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter(redis_url=redis_url)
    return _rate_limiter
