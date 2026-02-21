"""Unit tests for DMarket API cache module.

This module contAlgons tests for src/dmarket/api/cache.py covering:
- Cache key generation
- Cacheability checks
- Cache get/save operations
- Cache clearing operations

Target: 20+ tests to achieve 70%+ coverage of cache.py
"""

from src.dmarket.api.cache import (
    CACHE_TTL,
    clear_cache,
    clear_cache_for_endpoint,
    get_cache_key,
    get_from_cache,
    is_cacheable,
    save_to_cache,
)

# TestGetCacheKey


class TestGetCacheKey:
    """Tests for get_cache_key function."""

    def test_get_cache_key_simple(self):
        """Test cache key generation with method and path only."""
        # Act
        key = get_cache_key("GET", "/test/path")

        # Assert
        assert "GET" in key
        assert "/test/path" in key

    def test_get_cache_key_with_params(self):
        """Test cache key generation with query parameters."""
        # Arrange
        params = {"limit": 10, "offset": 0}

        # Act
        key = get_cache_key("GET", "/test/path", params=params)

        # Assert
        assert "limit" in key
        assert "10" in key

    def test_get_cache_key_with_data(self):
        """Test cache key generation with POST data."""
        # Arrange
        data = {"item_id": "123", "price": 1000}

        # Act
        key = get_cache_key("POST", "/test/path", data=data)

        # Assert
        assert "item_id" in key or "123" in key

    def test_get_cache_key_with_params_and_data(self):
        """Test cache key generation with both params and data."""
        # Arrange
        params = {"game": "csgo"}
        data = {"targets": [{"id": "1"}]}

        # Act
        key = get_cache_key("POST", "/test", params=params, data=data)

        # Assert
        assert "game" in key
        assert "targets" in key

    def test_get_cache_key_different_for_different_params(self):
        """Test that different params produce different keys."""
        # Arrange
        params1 = {"limit": 10}
        params2 = {"limit": 20}

        # Act
        key1 = get_cache_key("GET", "/test", params=params1)
        key2 = get_cache_key("GET", "/test", params=params2)

        # Assert
        assert key1 != key2

    def test_get_cache_key_consistent(self):
        """Test that same inputs produce same key."""
        # Arrange
        params = {"a": 1, "b": 2}

        # Act
        key1 = get_cache_key("GET", "/test", params=params)
        key2 = get_cache_key("GET", "/test", params=params)

        # Assert
        assert key1 == key2


# TestIsCacheable


class TestIsCacheable:
    """Tests for is_cacheable function."""

    def test_is_cacheable_get_market_items(self):
        """Test that market items endpoint is cacheable with short TTL."""
        # Act
        is_cache, ttl_type = is_cacheable("GET", "/exchange/v1/market/items")

        # Assert
        assert is_cache is True
        assert ttl_type == "short"

    def test_is_cacheable_get_balance(self):
        """Test that balance endpoint is cacheable with short TTL."""
        # Act
        is_cache, ttl_type = is_cacheable("GET", "/account/v1/balance")

        # Assert
        assert is_cache is True
        assert ttl_type == "short"

    def test_is_cacheable_get_games(self):
        """Test that games endpoint is cacheable with long TTL."""
        # Act
        is_cache, ttl_type = is_cacheable("GET", "/game/v1/games")

        # Assert
        assert is_cache is True
        assert ttl_type == "long"

    def test_is_cacheable_get_meta(self):
        """Test that market meta endpoint is cacheable with long TTL."""
        # Act
        is_cache, ttl_type = is_cacheable("GET", "/exchange/v1/market/meta")

        # Assert
        assert is_cache is True
        assert ttl_type == "long"

    def test_is_cacheable_get_aggregated_prices(self):
        """Test that aggregated prices endpoint is cacheable with medium TTL."""
        # Act
        is_cache, ttl_type = is_cacheable(
            "GET", "/exchange/v1/market/aggregated-prices"
        )

        # Assert
        assert is_cache is True
        assert ttl_type == "medium"

    def test_is_cacheable_post_not_cacheable(self):
        """Test that POST requests are not cacheable."""
        # Act
        is_cache, ttl_type = is_cacheable("POST", "/exchange/v1/market/items")

        # Assert
        assert is_cache is False
        assert ttl_type == ""

    def test_is_cacheable_unknown_endpoint(self):
        """Test that unknown endpoints are not cacheable."""
        # Act
        is_cache, ttl_type = is_cacheable("GET", "/unknown/endpoint")

        # Assert
        assert is_cache is False
        assert ttl_type == ""


# TestSaveAndGetFromCache


class TestSaveAndGetFromCache:
    """Tests for save_to_cache and get_from_cache functions."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_save_and_get_cache(self):
        """Test basic save and retrieve from cache."""
        # Arrange
        cache_key = "test:key"
        data = {"result": "success", "items": [1, 2, 3]}

        # Act
        save_to_cache(cache_key, data)
        cached = get_from_cache(cache_key)

        # Assert
        assert cached is not None
        assert cached["result"] == "success"
        assert cached["items"] == [1, 2, 3]

    def test_get_from_cache_nonexistent(self):
        """Test getting non-existent cache key."""
        # Act
        cached = get_from_cache("nonexistent:key")

        # Assert
        assert cached is None

    def test_cache_ttl_short(self):
        """Test that short TTL is applied correctly."""
        # Arrange
        cache_key = "test:short"
        data = {"value": 1}

        # Act
        save_to_cache(cache_key, data, "short")
        cached = get_from_cache(cache_key)

        # Assert
        assert cached is not None
        assert CACHE_TTL["short"] == 30

    def test_cache_ttl_medium(self):
        """Test that medium TTL is applied correctly."""
        # Arrange
        cache_key = "test:medium"
        data = {"value": 2}

        # Act
        save_to_cache(cache_key, data, "medium")
        cached = get_from_cache(cache_key)

        # Assert
        assert cached is not None
        assert CACHE_TTL["medium"] == 300

    def test_cache_ttl_long(self):
        """Test that long TTL is applied correctly."""
        # Arrange
        cache_key = "test:long"
        data = {"value": 3}

        # Act
        save_to_cache(cache_key, data, "long")
        cached = get_from_cache(cache_key)

        # Assert
        assert cached is not None
        assert CACHE_TTL["long"] == 1800


# TestClearCache


class TestClearCache:
    """Tests for cache clearing functions."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_clear_cache_all(self):
        """Test clearing all cache."""
        # Arrange
        save_to_cache("key1", {"data": 1})
        save_to_cache("key2", {"data": 2})
        save_to_cache("key3", {"data": 3})

        # Act
        clear_cache()

        # Assert
        assert get_from_cache("key1") is None
        assert get_from_cache("key2") is None
        assert get_from_cache("key3") is None

    def test_clear_cache_for_endpoint(self):
        """Test clearing cache for specific endpoint."""
        # Arrange
        save_to_cache("GET:/account/v1/balance:[]", {"balance": 100})
        save_to_cache("GET:/market/items:[]", {"items": []})
        save_to_cache("GET:/account/v1/balance?test:[]", {"balance": 200})

        # Act
        clear_cache_for_endpoint("/account/v1/balance")

        # Assert
        assert get_from_cache("GET:/account/v1/balance:[]") is None
        assert get_from_cache("GET:/account/v1/balance?test:[]") is None
        assert get_from_cache("GET:/market/items:[]") is not None

    def test_clear_cache_for_endpoint_no_match(self):
        """Test clearing cache for non-matching endpoint."""
        # Arrange
        save_to_cache("key1", {"data": 1})
        save_to_cache("key2", {"data": 2})

        # Act
        clear_cache_for_endpoint("/nonexistent/path")

        # Assert - no crash, nothing cleared
        assert get_from_cache("key1") is not None
        assert get_from_cache("key2") is not None


# TestCacheEdgeCases


class TestCacheEdgeCases:
    """Tests for edge cases."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_save_cache_with_unknown_ttl_type(self):
        """Test saving with unknown TTL type defaults to medium."""
        # Arrange
        cache_key = "test:unknown"
        data = {"value": 1}

        # Act
        save_to_cache(cache_key, data, "unknown_ttl")
        cached = get_from_cache(cache_key)

        # Assert - should use medium TTL as default
        assert cached is not None

    def test_cache_overwrite(self):
        """Test that saving to same key overwrites previous value."""
        # Arrange
        cache_key = "test:overwrite"

        # Act
        save_to_cache(cache_key, {"version": 1})
        save_to_cache(cache_key, {"version": 2})
        cached = get_from_cache(cache_key)

        # Assert
        assert cached["version"] == 2

    def test_cache_with_empty_data(self):
        """Test caching empty data."""
        # Arrange
        cache_key = "test:empty"

        # Act
        save_to_cache(cache_key, {})
        cached = get_from_cache(cache_key)

        # Assert
        assert cached == {}

    def test_cache_with_nested_data(self):
        """Test caching nested data structures."""
        # Arrange
        cache_key = "test:nested"
        data = {"level1": {"level2": {"level3": [1, 2, 3]}}}

        # Act
        save_to_cache(cache_key, data)
        cached = get_from_cache(cache_key)

        # Assert
        assert cached["level1"]["level2"]["level3"] == [1, 2, 3]
