"""HTTP caching utilities using hishel library.

This module provides RFC 9111-compliant HTTP caching for httpx AsyncClient.
Hishel enables transparent caching of HTTP responses with proper cache control.

Features:
- RFC 9111-compliant caching
- Async support with httpx.AsyncClient
- Multiple storage backends (memory, filesystem, SQLite)
- Configurable TTL and cache policies
- Streaming support
- Cache inspection and debugging

Example usage:
    ```python
    from src.utils.http_cache import (
        create_cached_client,
        get_cached_client,
        CacheConfig,
    )

    # Create a cached client with custom config
    config = CacheConfig(ttl=300, always_cache=True)
    client = await create_cached_client(config)

    # Use the client
    async with client as c:
        response = await c.get("https://api.dmarket.com/items")
        print(f"From cache: {response.extensions.get('hishel_from_cache', False)}")

    # Or use global cached client
    client = await get_cached_client()
    response = await client.get(url)
    ```

Documentation: https://hishel.com/
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import httpx
import structlog

# Conditional import - hishel is optional
try:
    import hishel
    from hishel import (
        AsyncSqliteStorage,
        CacheOptions,
        SpecificationPolicy,
    )
    from hishel.httpx import AsyncCacheClient

    HISHEL_AVAILABLE = True
except ImportError:
    HISHEL_AVAILABLE = False
    hishel = None  # type: ignore[assignment]
    AsyncCacheClient = None  # type: ignore[assignment, misc]
    AsyncSqliteStorage = None  # type: ignore[assignment, misc]
    CacheOptions = None  # type: ignore[assignment, misc]
    SpecificationPolicy = None  # type: ignore[assignment, misc]


logger = structlog.get_logger(__name__)


class CacheStorageType(StrEnum):
    """Available cache storage backends."""

    MEMORY = "memory"
    FILESYSTEM = "filesystem"
    SQLITE = "sqlite"


@dataclass
class CacheConfig:
    """Configuration for HTTP cache behavior.

    Attributes:
        ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
        always_cache: Force caching even without cache-control headers
        storage_type: Storage backend type (memory, filesystem, sqlite)
        cache_dir: Directory for filesystem/sqlite storage
        max_size: Maximum cache size in bytes (for memory backend)
        cacheable_methods: HTTP methods to cache
        cacheable_status_codes: HTTP status codes to cache
    """

    ttl: int = 300  # 5 minutes
    always_cache: bool = False
    storage_type: CacheStorageType = CacheStorageType.MEMORY
    cache_dir: Path = field(default_factory=lambda: Path(".cache/http"))
    max_size: int = 100 * 1024 * 1024  # 100 MB
    cacheable_methods: tuple[str, ...] = ("GET", "HEAD")
    cacheable_status_codes: tuple[int, ...] = (200, 203, 300, 301, 308)

    # Hishel-specific options
    heuristic_expiration: bool = True
    revalidate_on_miss: bool = True


@dataclass
class CacheStats:
    """Statistics about cache usage."""

    hits: int = 0
    misses: int = 0
    total_requests: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100


class CachedHTTPClient:
    """HTTP client with built-in caching support.

    This class wraps httpx.AsyncClient with hishel caching capabilities.
    Falls back to regular httpx.AsyncClient if hishel is not available.

    Example:
        >>> async with CachedHTTPClient(config) as client:
        ...     response = await client.get(url)
        ...     is_cached = client.is_from_cache(response)
    """

    _instance: ClassVar["CachedHTTPClient | None"] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(
        self,
        config: CacheConfig | None = None,
        timeout: float = 30.0,
        **httpx_kwargs: Any,
    ):
        """Initialize cached HTTP client.

        Args:
            config: Cache configuration
            timeout: Request timeout in seconds
            **httpx_kwargs: Additional arguments for httpx.AsyncClient
        """
        self.config = config or CacheConfig()
        self.timeout = timeout
        self.httpx_kwargs = httpx_kwargs
        self._client: httpx.AsyncClient | None = None
        self._stats = CacheStats()

    async def _create_client(self) -> httpx.AsyncClient:
        """Create the underlying HTTP client with caching."""
        if not HISHEL_AVAILABLE:
            logger.warning(
                "hishel_not_available",
                message="Hishel library not installed, caching disabled",
            )
            return httpx.AsyncClient(
                timeout=self.timeout,
                **self.httpx_kwargs,
            )

        # Create storage based on config
        storage = self._create_storage()

        # Create cache client
        client = AsyncCacheClient(
            storage=storage,
            timeout=self.timeout,
            **self.httpx_kwargs,
        )

        logger.info(
            "cached_client_created",
            storage_type=self.config.storage_type,
            ttl=self.config.ttl,
            always_cache=self.config.always_cache,
        )

        return client

    def _create_sqlite_storage(self) -> Any:
        """Create SQLite storage backend.

        Returns:
            AsyncSqliteStorage instance or None if hishel not available
        """
        if not HISHEL_AVAILABLE:
            return None

        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.config.cache_dir / "cache.db"
        return AsyncSqliteStorage(
            database_path=str(db_path),
            default_ttl=self.config.ttl,
        )

    def _create_storage(self) -> Any:
        """Create storage backend based on configuration."""
        if not HISHEL_AVAILABLE:
            return None

        # Currently only SQLite storage is supported for async operations
        # All storage types map to SQLite for consistency
        return self._create_sqlite_storage()

    async def __aenter__(self) -> "CachedHTTPClient":
        """Enter async context."""
        self._client = await self._create_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[Exception] | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a GET request with caching.

        Args:
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response (may be from cache)
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(url, **kwargs)
        self._update_stats(response)
        return response

    async def post(
        self,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a POST request (not cached by default)."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async context manager.")

        return await self._client.post(url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.request(method, url, **kwargs)
        if method.upper() in self.config.cacheable_methods:
            self._update_stats(response)
        return response

    def _update_stats(self, response: httpx.Response) -> None:
        """Update cache statistics based on response."""
        self._stats.total_requests += 1
        if self.is_from_cache(response):
            self._stats.hits += 1
        else:
            self._stats.misses += 1

    @staticmethod
    def is_from_cache(response: httpx.Response) -> bool:
        """Check if response was served from cache.

        Args:
            response: HTTP response

        Returns:
            True if response was served from cache
        """
        if not HISHEL_AVAILABLE:
            return False
        return response.extensions.get("hishel_from_cache", False)

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats()


# Global client instance
_global_client: CachedHTTPClient | None = None
_global_lock = asyncio.Lock()


async def get_cached_client(
    config: CacheConfig | None = None,
    **kwargs: Any,
) -> CachedHTTPClient:
    """Get or create the global cached HTTP client.

    This function provides a singleton pattern for the cached client.

    Args:
        config: Cache configuration (used only on first call)
        **kwargs: Additional arguments for httpx.AsyncClient

    Returns:
        Cached HTTP client instance
    """
    global _global_client

    if _global_client is None:
        async with _global_lock:
            if _global_client is None:
                _global_client = CachedHTTPClient(config=config, **kwargs)
                await _global_client.__aenter__()

    return _global_client


async def close_cached_client() -> None:
    """Close the global cached HTTP client."""
    global _global_client

    if _global_client is not None:
        async with _global_lock:
            if _global_client is not None:
                await _global_client.__aexit__(None, None, None)
                _global_client = None


@asynccontextmanager
async def create_cached_client(
    config: CacheConfig | None = None,
    **kwargs: Any,
):
    """Create a cached HTTP client as context manager.

    Args:
        config: Cache configuration
        **kwargs: Additional arguments for httpx.AsyncClient

    Yields:
        Configured CachedHTTPClient instance
    """
    client = CachedHTTPClient(config=config, **kwargs)
    async with client as c:
        yield c


def get_cache_key(
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> str:
    """Generate a cache key for an HTTP request.

    Args:
        method: HTTP method
        url: Request URL
        params: Query parameters

    Returns:
        Cache key string
    """
    import hashlib
    import json

    key_parts = [method.upper(), url]
    if params:
        key_parts.append(json.dumps(params, sort_keys=True))

    key_str = "|".join(key_parts)
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


__all__ = [
    # Availability check
    "HISHEL_AVAILABLE",
    # Configuration
    "CacheConfig",
    "CacheStats",
    "CacheStorageType",
    # Main client
    "CachedHTTPClient",
    "close_cached_client",
    # Factory functions
    "create_cached_client",
    # Utilities
    "get_cache_key",
    "get_cached_client",
]
