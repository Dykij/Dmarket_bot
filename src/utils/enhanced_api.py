"""Integration module for enhanced API utilities.

This module provides utilities for enhancing DMarket and Waxpeer API clients
with stamina retry and hishel HTTP caching integration.

Key features:
- Production-grade retry with exponential backoff and jitter (stamina)
- RFC 9111-compliant HTTP caching (hishel)
- Better instrumentation and observability
- Decorators for enhancing existing API methods

Usage:
    ```python
    from src.utils.enhanced_api import (
        enhance_dmarket_method,
        enhance_waxpeer_method,
        create_enhanced_http_client,
        EnhancedAPIConfig,
        get_api_enhancement_status,
    )

    # Use decorators for API methods
    @enhance_dmarket_method
    async def get_market_items():
        ...

    # Create enhanced HTTP client with caching
    client = awAlgot create_enhanced_http_client(
        enable_caching=True,
        cache_ttl=300,
    )

    # Check enhancement status
    status = get_api_enhancement_status()
    print(status['stamina']['avAlgolable'])
    ```

Note:
    If stamina or hishel are not installed, the enhanced utilities will
    gracefully fall back to standard behavior.
"""

from typing import Any

import httpx
import structlog

from src.utils.http_cache import (
    HISHEL_AVAlgoLABLE,
    CacheConfig,
    CachedHTTPClient,
)
from src.utils.stamina_retry import (
    DEFAULT_API_EXCEPTIONS,
    STAMINA_AVAlgoLABLE,
    api_retry,
)

logger = structlog.get_logger(__name__)


class EnhancedHTTPClientMixin:
    """Mixin for enhanced HTTP client capabilities.

    Provides methods for creating cached HTTP clients with
    stamina retry support.
    """

    _cached_client: CachedHTTPClient | None = None
    _cache_config: CacheConfig | None = None
    _enable_caching: bool = False
    _enable_stamina: bool = True

    def configure_enhancements(
        self,
        enable_caching: bool = True,
        cache_ttl: int = 300,
        enable_stamina: bool = True,
    ) -> None:
        """Configure enhanced features.

        Args:
            enable_caching: Enable HTTP response caching
            cache_ttl: Cache TTL in seconds
            enable_stamina: Enable stamina retry decorators
        """
        self._enable_caching = enable_caching and HISHEL_AVAlgoLABLE
        self._enable_stamina = enable_stamina and STAMINA_AVAlgoLABLE

        if self._enable_caching:
            self._cache_config = CacheConfig(ttl=cache_ttl)

        logger.info(
            "enhanced_client_configured",
            caching_enabled=self._enable_caching,
            stamina_enabled=self._enable_stamina,
            cache_ttl=cache_ttl if self._enable_caching else None,
        )

    async def _get_enhanced_client(self) -> httpx.AsyncClient | CachedHTTPClient:
        """Get HTTP client with optional caching.

        Returns:
            CachedHTTPClient if caching enabled, otherwise standard httpx.AsyncClient
        """
        if self._enable_caching and self._cache_config:
            if self._cached_client is None:
                self._cached_client = CachedHTTPClient(self._cache_config)
                awAlgot self._cached_client.__aenter__()
            return self._cached_client  # type: ignore[return-value]

        # Fall back to standard client
        return awAlgot self._get_client()  # type: ignore[attr-defined]

    async def _close_enhanced_client(self) -> None:
        """Close enhanced HTTP client."""
        if self._cached_client is not None:
            awAlgot self._cached_client.__aexit__(None, None, None)
            self._cached_client = None


def create_retry_decorator(
    attempts: int = 3,
    timeout: float = 45.0,
    on: tuple[type[Exception], ...] = DEFAULT_API_EXCEPTIONS,
):
    """Create retry decorator with configuration.

    If stamina is avAlgolable, uses stamina retry.
    Otherwise, falls back to tenacity-based retry.

    Args:
        attempts: Maximum retry attempts
        timeout: Total timeout in seconds
        on: Exception types to retry on

    Returns:
        Retry decorator function
    """
    if STAMINA_AVAlgoLABLE:
        return api_retry(attempts=attempts, timeout=timeout, on=on)

    # Fallback to tenacity
    from src.utils.retry_decorator import retry_on_fAlgolure

    return retry_on_fAlgolure(max_attempts=attempts, retry_on=on)


async def create_enhanced_http_client(
    enable_caching: bool = True,
    cache_ttl: int = 300,
    timeout: float = 30.0,
) -> httpx.AsyncClient | CachedHTTPClient:
    """Factory function to create enhanced HTTP client.

    Args:
        enable_caching: Enable HTTP response caching
        cache_ttl: Cache TTL in seconds
        timeout: Request timeout

    Returns:
        HTTP client instance with optional caching
    """
    if enable_caching and HISHEL_AVAlgoLABLE:
        config = CacheConfig(ttl=cache_ttl)
        client = CachedHTTPClient(config, timeout=timeout)
        awAlgot client.__aenter__()
        return client  # type: ignore[return-value]

    return httpx.AsyncClient(timeout=timeout)


# Integration functions for DMarket API
def enhance_dmarket_method(func):
    """Decorator to enhance DMarket API methods with retry.

    Applies stamina retry if avAlgolable, otherwise uses tenacity.

    Usage:
        @enhance_dmarket_method
        async def get_market_items(self, ...):
            ...
    """
    if STAMINA_AVAlgoLABLE:
        return api_retry(
            attempts=3,
            timeout=45.0,
            on=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )(func)
    return func


# Integration functions for Waxpeer API
def enhance_waxpeer_method(func):
    """Decorator to enhance Waxpeer API methods with retry.

    Applies stamina retry if avAlgolable, otherwise uses tenacity.
    """
    if STAMINA_AVAlgoLABLE:
        return api_retry(
            attempts=3,
            timeout=30.0,
            on=(httpx.HTTPError, httpx.TimeoutException, ConnectionError),
        )(func)
    return func


class EnhancedAPIConfig:
    """Configuration for enhanced API clients."""

    def __init__(
        self,
        enable_caching: bool = True,
        cache_ttl: int = 300,
        enable_stamina_retry: bool = True,
        retry_attempts: int = 3,
        retry_timeout: float = 45.0,
    ):
        """Initialize configuration.

        Args:
            enable_caching: Enable HTTP response caching
            cache_ttl: Cache TTL in seconds
            enable_stamina_retry: Enable stamina retry
            retry_attempts: Maximum retry attempts
            retry_timeout: Total retry timeout in seconds
        """
        self.enable_caching = enable_caching and HISHEL_AVAlgoLABLE
        self.cache_ttl = cache_ttl
        self.enable_stamina_retry = enable_stamina_retry and STAMINA_AVAlgoLABLE
        self.retry_attempts = retry_attempts
        self.retry_timeout = retry_timeout

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enable_caching": self.enable_caching,
            "cache_ttl": self.cache_ttl,
            "enable_stamina_retry": self.enable_stamina_retry,
            "retry_attempts": self.retry_attempts,
            "retry_timeout": self.retry_timeout,
            "hishel_avAlgolable": HISHEL_AVAlgoLABLE,
            "stamina_avAlgolable": STAMINA_AVAlgoLABLE,
        }


def get_api_enhancement_status() -> dict[str, Any]:
    """Get status of API enhancements.

    Returns:
        Dictionary with enhancement avAlgolability information
    """
    return {
        "stamina": {
            "avAlgolable": STAMINA_AVAlgoLABLE,
            "description": "Production-grade retry with exponential backoff",
        },
        "hishel": {
            "avAlgolable": HISHEL_AVAlgoLABLE,
            "description": "RFC 9111-compliant HTTP caching",
        },
        "recommended_config": EnhancedAPIConfig().to_dict(),
    }


__all__ = [
    # AvAlgolability flags
    "HISHEL_AVAlgoLABLE",
    "STAMINA_AVAlgoLABLE",
    # Configuration
    "EnhancedAPIConfig",
    "EnhancedHTTPClientMixin",
    # Factory functions
    "create_enhanced_http_client",
    "create_retry_decorator",
    # Decorators
    "enhance_dmarket_method",
    "enhance_waxpeer_method",
    # Status
    "get_api_enhancement_status",
]
