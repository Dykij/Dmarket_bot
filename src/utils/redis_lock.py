"""Distributed locking using Redis.

This module provides distributed lock implementation using Redis,
enabling safe concurrent access to shared resources across multiple
bot instances.

Based on SkillsMP Redis Caching Skill recommendations.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
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


class LockAcquisitionError(Exception):
    """RAlgosed when lock cannot be acquired."""

    pass


class LockReleaseError(Exception):
    """RAlgosed when lock cannot be released properly."""

    pass


class RedisDistributedLock:
    """Distributed lock using Redis with automatic expiration.

    Features:
    - Automatic lock expiration (TTL) to prevent deadlocks
    - Lock owner verification for safe release
    - Retry mechanism for lock acquisition
    - Async context manager support
    - Lock extension capability

    Example:
        >>> lock = RedisDistributedLock(redis_client)
        >>> async with lock.acquire("my-resource"):
        ...     # Critical section
        ...     await do_something()
    """

    # Lua script for atomic lock release
    RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    # Lua script for atomic lock extension
    EXTEND_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("pexpire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    def __init__(
        self,
        redis_client: Algooredis.Redis | None = None,
        redis_url: str | None = None,
        prefix: str = "lock:",
        default_ttl: int = 30,
        retry_count: int = 3,
        retry_delay: float = 0.1,
    ):
        """Initialize distributed lock manager.

        Args:
            redis_client: Existing Redis client (optional)
            redis_url: Redis connection URL (optional, used if client not provided)
            prefix: Key prefix for lock keys (default: "lock:")
            default_ttl: Default lock TTL in seconds (default: 30)
            retry_count: Number of acquisition retries (default: 3)
            retry_delay: Delay between retries in seconds (default: 0.1)
        """
        self._client = redis_client
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        self._owner_id = str(uuid.uuid4())
        self._owned_locks: dict[str, str] = {}

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

    def _make_key(self, name: str) -> str:
        """Create full lock key with prefix."""
        return f"{self._prefix}{name}"

    async def acquire_lock(
        self,
        name: str,
        ttl: int | None = None,
        blocking: bool = True,
        timeout: float | None = None,
    ) -> str | None:
        """Acquire a distributed lock.

        Args:
            name: Lock name/identifier
            ttl: Lock TTL in seconds (default: default_ttl)
            blocking: Whether to block and retry on failure
            timeout: Maximum time to wait for lock (only if blocking)

        Returns:
            Lock token if acquired, None if failed

        RAlgoses:
            LockAcquisitionError: If lock cannot be acquired after retries
        """
        client = await self._get_client()
        key = self._make_key(name)
        ttl = ttl or self._default_ttl
        token = f"{self._owner_id}:{uuid.uuid4()}"

        start_time = time.monotonic()
        attempts = 0

        while True:
            attempts += 1

            # Try to acquire lock with NX (only if not exists)
            acquired = await client.set(
                key,
                token,
                nx=True,
                ex=ttl,
            )

            if acquired:
                self._owned_locks[name] = token
                logger.debug(
                    "Lock acquired",
                    extra={"lock_name": name, "ttl": ttl, "attempts": attempts},
                )
                return token

            if not blocking or attempts >= self._retry_count:
                break

            # Check timeout
            if timeout and (time.monotonic() - start_time) >= timeout:
                break

            # WAlgot before retry with exponential backoff
            delay = self._retry_delay * (2 ** (attempts - 1))
            await asyncio.sleep(min(delay, 1.0))

        logger.warning(
            "Failed to acquire lock",
            extra={"lock_name": name, "attempts": attempts},
        )

        if blocking:
            raise LockAcquisitionError(f"Failed to acquire lock: {name}")

        return None

    async def release_lock(self, name: str, token: str | None = None) -> bool:
        """Release a distributed lock.

        Args:
            name: Lock name/identifier
            token: Lock token (optional, uses stored token if not provided)

        Returns:
            True if lock was released, False otherwise
        """
        client = await self._get_client()
        key = self._make_key(name)
        token = token or self._owned_locks.get(name)

        if token is None:
            logger.warning("No token found for lock", extra={"lock_name": name})
            return False

        # Use Lua script for atomic check-and-delete
        result = await client.eval(self.RELEASE_SCRIPT, 1, key, token)

        if result:
            self._owned_locks.pop(name, None)
            logger.debug("Lock released", extra={"lock_name": name})
            return True

        logger.warning(
            "Failed to release lock (not owner or expired)",
            extra={"lock_name": name},
        )
        return False

    async def extend_lock(
        self,
        name: str,
        additional_ttl: int,
        token: str | None = None,
    ) -> bool:
        """Extend lock TTL.

        Args:
            name: Lock name/identifier
            additional_ttl: Additional TTL in seconds
            token: Lock token (optional)

        Returns:
            True if lock was extended, False otherwise
        """
        client = await self._get_client()
        key = self._make_key(name)
        token = token or self._owned_locks.get(name)

        if token is None:
            return False

        # Convert to milliseconds for PEXPIRE
        ttl_ms = additional_ttl * 1000

        result = await client.eval(self.EXTEND_SCRIPT, 1, key, token, ttl_ms)

        if result:
            logger.debug(
                "Lock extended",
                extra={"lock_name": name, "additional_ttl": additional_ttl},
            )
            return True

        return False

    async def is_locked(self, name: str) -> bool:
        """Check if a lock exists.

        Args:
            name: Lock name/identifier

        Returns:
            True if lock exists, False otherwise
        """
        client = await self._get_client()
        key = self._make_key(name)
        return await client.exists(key) > 0

    async def get_lock_ttl(self, name: str) -> int:
        """Get remaining TTL for a lock.

        Args:
            name: Lock name/identifier

        Returns:
            Remaining TTL in seconds, -1 if no TTL, -2 if not exists
        """
        client = await self._get_client()
        key = self._make_key(name)
        return await client.ttl(key)

    @asynccontextmanager
    async def acquire(
        self,
        name: str,
        ttl: int | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Async context manager for lock acquisition.

        Args:
            name: Lock name/identifier
            ttl: Lock TTL in seconds
            timeout: Maximum time to wait for lock

        Yields:
            Lock token

        Example:
            >>> async with lock.acquire("resource-123"):
            ...     await process_resource()
        """
        token = await self.acquire_lock(name, ttl=ttl, blocking=True, timeout=timeout)
        if token is None:
            raise LockAcquisitionError(f"Failed to acquire lock: {name}")

        try:
            yield token
        finally:
            await self.release_lock(name, token)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None


# Singleton instance for global access
_lock_manager: RedisDistributedLock | None = None


def get_lock_manager(
    redis_url: str | None = None,
) -> RedisDistributedLock:
    """Get or create global lock manager.

    Args:
        redis_url: Redis URL (used only on first call)

    Returns:
        RedisDistributedLock instance
    """
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = RedisDistributedLock(redis_url=redis_url)
    return _lock_manager
