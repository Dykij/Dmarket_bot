"""Tests for http_cache module.

Tests cover:
- CacheConfig configuration
- CachedHTTPClient functionality
- Cache statistics tracking
- Factory functions
- Cache key generation
- Fallback behavior when hishel is not available
"""

from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from src.utils.http_cache import (
    HISHEL_AVAILABLE,
    CacheConfig,
    CachedHTTPClient,
    CacheStats,
    CacheStorageType,
    close_cached_client,
    create_cached_client,
    get_cache_key,
    get_cached_client,
)


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()

        assert config.ttl == 300
        assert config.always_cache is False
        assert config.storage_type == CacheStorageType.MEMORY
        assert config.max_size == 100 * 1024 * 1024  # 100 MB
        assert config.cacheable_methods == ("GET", "HEAD")
        assert 200 in config.cacheable_status_codes

    def test_custom_config(self):
        """Test custom configuration values."""
        custom_dir = Path("/tmp/custom_cache")
        config = CacheConfig(
            ttl=600,
            always_cache=True,
            storage_type=CacheStorageType.SQLITE,
            cache_dir=custom_dir,
            max_size=50 * 1024 * 1024,
        )

        assert config.ttl == 600
        assert config.always_cache is True
        assert config.storage_type == CacheStorageType.SQLITE
        assert config.cache_dir == custom_dir
        assert config.max_size == 50 * 1024 * 1024


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total_requests == 0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25, total_requests=100)

        assert stats.hit_rate == 75.0

    def test_hit_rate_with_no_requests(self):
        """Test hit rate with no requests."""
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_hit_rate_partial(self):
        """Test hit rate with partial hits."""
        stats = CacheStats(hits=3, misses=7, total_requests=10)

        assert stats.hit_rate == 30.0


class TestCacheStorageType:
    """Tests for CacheStorageType enum."""

    def test_storage_types(self):
        """Test all storage type values."""
        assert CacheStorageType.MEMORY == "memory"
        assert CacheStorageType.FILESYSTEM == "filesystem"
        assert CacheStorageType.SQLITE == "sqlite"


class TestCachedHTTPClient:
    """Tests for CachedHTTPClient class."""

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client as async context manager."""
        config = CacheConfig()

        async with CachedHTTPClient(config) as client:
            assert client._client is not None

        assert client._client is None

    @pytest.mark.asyncio
    async def test_client_requires_context(self):
        """Test client requires context manager initialization."""
        client = CachedHTTPClient()

        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.get("https://example.com")

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test cache statistics tracking."""
        async with CachedHTTPClient() as client:
            assert client.stats.total_requests == 0
            assert client.stats.hits == 0
            assert client.stats.misses == 0

    @pytest.mark.asyncio
    async def test_stats_reset(self):
        """Test resetting cache statistics."""
        async with CachedHTTPClient() as client:
            # Manually set stats
            client._stats.hits = 10
            client._stats.misses = 5
            client._stats.total_requests = 15

            client.reset_stats()

            assert client.stats.hits == 0
            assert client.stats.misses == 0
            assert client.stats.total_requests == 0

    def test_is_from_cache_without_hishel(self):
        """Test is_from_cache returns False when hishel not available."""
        response = Mock(spec=httpx.Response)
        response.extensions = {}

        # When hishel is not available
        with patch("src.utils.http_cache.HISHEL_AVAILABLE", False):
            result = CachedHTTPClient.is_from_cache(response)
            assert result is False

    def test_is_from_cache_with_hishel(self):
        """Test is_from_cache with hishel extension."""
        response = Mock(spec=httpx.Response)
        response.extensions = {"hishel_from_cache": True}

        # When hishel is available
        if HISHEL_AVAILABLE:
            result = CachedHTTPClient.is_from_cache(response)
            assert result is True


class TestCacheKeyGeneration:
    """Tests for get_cache_key function."""

    def test_basic_cache_key(self):
        """Test basic cache key generation."""
        key1 = get_cache_key("GET", "https://api.example.com/items")
        key2 = get_cache_key("GET", "https://api.example.com/items")

        assert key1 == key2
        assert len(key1) == 16

    def test_different_methods_different_keys(self):
        """Test different methods produce different keys."""
        key_get = get_cache_key("GET", "https://api.example.com/items")
        key_post = get_cache_key("POST", "https://api.example.com/items")

        assert key_get != key_post

    def test_different_urls_different_keys(self):
        """Test different URLs produce different keys."""
        key1 = get_cache_key("GET", "https://api.example.com/items")
        key2 = get_cache_key("GET", "https://api.example.com/users")

        assert key1 != key2

    def test_params_affect_cache_key(self):
        """Test query params affect cache key."""
        key_no_params = get_cache_key("GET", "https://api.example.com/items")
        key_with_params = get_cache_key(
            "GET",
            "https://api.example.com/items",
            params={"game": "csgo", "limit": 100},
        )

        assert key_no_params != key_with_params

    def test_params_order_independent(self):
        """Test params order doesn't affect cache key."""
        key1 = get_cache_key(
            "GET",
            "https://api.example.com/items",
            params={"a": 1, "b": 2},
        )
        key2 = get_cache_key(
            "GET",
            "https://api.example.com/items",
            params={"b": 2, "a": 1},
        )

        assert key1 == key2


class TestFactoryFunctions:
    """Tests for factory functions."""

    @pytest.mark.asyncio
    async def test_create_cached_client(self):
        """Test create_cached_client context manager."""
        config = CacheConfig(ttl=60)

        async with create_cached_client(config) as client:
            assert isinstance(client, CachedHTTPClient)
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_get_cached_client_singleton(self):
        """Test get_cached_client returns singleton."""
        # Clean up any existing global client
        await close_cached_client()

        client1 = await get_cached_client()
        client2 = await get_cached_client()

        try:
            assert client1 is client2
        finally:
            await close_cached_client()

    @pytest.mark.asyncio
    async def test_close_cached_client(self):
        """Test closing global cached client."""
        await close_cached_client()

        # Get a new client
        client = await get_cached_client()
        assert client is not None

        # Close it
        await close_cached_client()

        # Getting again should create a new one
        client2 = await get_cached_client()
        assert client2 is not None

        await close_cached_client()


class TestHishelAvailability:
    """Tests for hishel availability detection."""

    def test_hishel_availability_constant(self):
        """Test HISHEL_AVAILABLE constant is boolean."""
        assert isinstance(HISHEL_AVAILABLE, bool)


class TestFallbackBehavior:
    """Tests for fallback behavior when hishel is not available."""

    @pytest.mark.asyncio
    async def test_fallback_client_creation(self):
        """Test client creation without hishel."""
        with patch("src.utils.http_cache.HISHEL_AVAILABLE", False):
            config = CacheConfig()
            async with CachedHTTPClient(config) as client:
                # Should create regular httpx client
                assert client._client is not None
