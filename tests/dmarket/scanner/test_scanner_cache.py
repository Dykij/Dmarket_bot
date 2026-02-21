"""Unit tests for src/dmarket/scanner/cache.py.

Tests for ScannerCache including:
- Initialization
- Cache operations (get, set, clear)
- TTL expiration
- Eviction policies
- Statistics tracking
- Key generation
"""

import time

import pytest


class TestScannerCacheInit:
    """Tests for ScannerCache initialization."""

    def test_init_with_default_values(self):
        """Test initialization with default parameters."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        assert cache.ttl == 300
        assert cache._max_size == 1000
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._evictions == 0

    def test_init_with_custom_ttl(self):
        """Test initialization with custom TTL."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(ttl=600)

        assert cache.ttl == 600

    def test_init_with_custom_max_size(self):
        """Test initialization with custom max size."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(max_size=500)

        assert cache._max_size == 500


class TestScannerCacheTTL:
    """Tests for TTL property."""

    def test_get_ttl(self):
        """Test getting TTL value."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(ttl=120)

        assert cache.ttl == 120

    def test_set_ttl_valid(self):
        """Test setting valid TTL value."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.ttl = 600

        assert cache.ttl == 600

    def test_set_ttl_zero(self):
        """Test setting TTL to zero."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.ttl = 0

        assert cache.ttl == 0

    def test_set_ttl_negative_rAlgoses_error(self):
        """Test setting negative TTL rAlgoses error."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        with pytest.rAlgoses(ValueError, match="non-negative"):
            cache.ttl = -1


class TestScannerCacheMakeKey:
    """Tests for _make_key method."""

    def test_make_key_string(self):
        """Test key generation from string."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        key = cache._make_key("test_key")

        assert key == "test_key"

    def test_make_key_tuple(self):
        """Test key generation from tuple."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        key = cache._make_key(("level", "game", 100))

        assert key == "level_game_100"

    def test_make_key_empty_tuple(self):
        """Test key generation from empty tuple."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        key = cache._make_key(())

        assert key == ""


class TestScannerCacheGet:
    """Tests for get method."""

    def test_get_missing_key(self):
        """Test getting non-existent key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        result = cache.get("missing_key")

        assert result is None
        assert cache._misses == 1

    def test_get_existing_key(self):
        """Test getting existing key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("test_key", [{"item": "test"}])

        result = cache.get("test_key")

        assert result == [{"item": "test"}]
        assert cache._hits == 1

    def test_get_expired_key(self):
        """Test getting expired key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(ttl=1)  # 1 second expiration
        cache.set("test_key", [{"item": "test"}])

        # WAlgot for expiration
        time.sleep(1.1)

        result = cache.get("test_key")

        assert result is None
        assert cache._misses == 1
        assert cache._evictions == 1

    def test_get_with_tuple_key(self):
        """Test getting value with tuple key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set(("level", "game"), [{"item": "test"}])

        result = cache.get(("level", "game"))

        assert result == [{"item": "test"}]


class TestScannerCacheSet:
    """Tests for set method."""

    def test_set_basic(self):
        """Test basic set operation."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        items = [{"item": "test", "price": 100}]

        cache.set("test_key", items)

        assert len(cache) == 1
        assert cache.get("test_key") == items

    def test_set_with_tuple_key(self):
        """Test set with tuple key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        items = [{"item": "test"}]

        cache.set(("level", "game"), items)

        assert len(cache) == 1

    def test_set_evicts_when_full(self):
        """Test set evicts oldest when cache is full."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(max_size=2)
        cache.set("key1", [{"item": "1"}])
        time.sleep(0.01)  # Ensure different timestamps
        cache.set("key2", [{"item": "2"}])
        time.sleep(0.01)

        cache.set("key3", [{"item": "3"}])

        assert len(cache) == 2
        assert cache._evictions == 1
        # key1 should be evicted as oldest
        assert cache.get("key1") is None


class TestScannerCacheEvictOldest:
    """Tests for _evict_oldest method."""

    def test_evict_oldest_empty_cache(self):
        """Test evict on empty cache does nothing."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        cache._evict_oldest()

        assert len(cache) == 0
        assert cache._evictions == 0

    def test_evict_oldest_removes_oldest(self):
        """Test evict removes oldest entry."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("old_key", [{"item": "old"}])
        time.sleep(0.01)
        cache.set("new_key", [{"item": "new"}])

        cache._evict_oldest()

        assert len(cache) == 1
        assert cache.get("old_key") is None
        assert cache.get("new_key") is not None


class TestScannerCacheClear:
    """Tests for clear method."""

    def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        cache.clear()

        assert len(cache) == 0

    def test_clear_cache_with_items(self):
        """Test clearing cache with items."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [{"item": "1"}])
        cache.set("key2", [{"item": "2"}])

        cache.clear()

        assert len(cache) == 0


class TestScannerCacheInvalidate:
    """Tests for invalidate method."""

    def test_invalidate_all(self):
        """Test invalidate all entries."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [{"item": "1"}])
        cache.set("key2", [{"item": "2"}])

        count = cache.invalidate()

        assert count == 2
        assert len(cache) == 0

    def test_invalidate_with_pattern(self):
        """Test invalidate entries matching pattern."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("csgo_key1", [{"item": "1"}])
        cache.set("csgo_key2", [{"item": "2"}])
        cache.set("dota_key", [{"item": "3"}])

        count = cache.invalidate("csgo")

        assert count == 2
        assert len(cache) == 1
        assert cache.get("dota_key") is not None

    def test_invalidate_no_matches(self):
        """Test invalidate with no matches."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [{"item": "1"}])

        count = cache.invalidate("nonexistent")

        assert count == 0
        assert len(cache) == 1


class TestScannerCacheStatistics:
    """Tests for get_statistics method."""

    def test_statistics_empty_cache(self):
        """Test statistics on empty cache."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(ttl=300, max_size=1000)

        stats = cache.get_statistics()

        assert stats["size"] == 0
        assert stats["max_size"] == 1000
        assert stats["ttl"] == 300
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["hit_rate"] == 0.0

    def test_statistics_after_operations(self):
        """Test statistics after cache operations."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [{"item": "1"}])
        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("missing")  # miss

        stats = cache.get_statistics()

        assert stats["size"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 66.67  # 2/3 * 100

    def test_statistics_hit_rate_calculation(self):
        """Test hit rate calculation."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key", [])

        # 4 hits
        for _ in range(4):
            cache.get("key")

        # 1 miss
        cache.get("missing")

        stats = cache.get_statistics()

        assert stats["hit_rate"] == 80.0  # 4/5 * 100


class TestScannerCacheDunderMethods:
    """Tests for __len__ and __contAlgons__ methods."""

    def test_len_empty(self):
        """Test len on empty cache."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        assert len(cache) == 0

    def test_len_with_items(self):
        """Test len with items."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [])
        cache.set("key2", [])

        assert len(cache) == 2

    def test_contAlgons_existing_key(self):
        """Test contAlgons with existing key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()
        cache.set("key1", [])

        assert "key1" in cache

    def test_contAlgons_missing_key(self):
        """Test contAlgons with missing key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache()

        assert "missing" not in cache

    def test_contAlgons_expired_key(self):
        """Test contAlgons with expired key."""
        from src.dmarket.scanner.cache import ScannerCache

        cache = ScannerCache(ttl=1)  # 1 second expiration
        cache.set("key1", [])

        time.sleep(1.1)

        assert "key1" not in cache


class TestGenerateCacheKey:
    """Tests for generate_cache_key function."""

    def test_basic_key(self):
        """Test basic key generation."""
        from src.dmarket.scanner.cache import generate_cache_key

        key = generate_cache_key("standard", "csgo")

        assert key == "scanner:standard:csgo"

    def test_key_with_extra_params(self):
        """Test key generation with extra parameters."""
        from src.dmarket.scanner.cache import generate_cache_key

        key = generate_cache_key(
            "standard", "csgo", {"min_price": 100, "max_price": 500}
        )

        assert "scanner:standard:csgo" in key
        assert "min_price=100" in key
        assert "max_price=500" in key

    def test_key_extra_params_sorted(self):
        """Test extra params are sorted for consistency."""
        from src.dmarket.scanner.cache import generate_cache_key

        key1 = generate_cache_key("standard", "csgo", {"b": 2, "a": 1})
        key2 = generate_cache_key("standard", "csgo", {"a": 1, "b": 2})

        assert key1 == key2

    def test_key_with_empty_extra(self):
        """Test key generation with empty extra params."""
        from src.dmarket.scanner.cache import generate_cache_key

        key1 = generate_cache_key("standard", "csgo", {})
        key2 = generate_cache_key("standard", "csgo")

        assert key1 == key2


class TestScannerCacheIntegration:
    """Integration tests for ScannerCache."""

    def test_full_workflow(self):
        """Test complete cache workflow."""
        from src.dmarket.scanner.cache import ScannerCache, generate_cache_key

        cache = ScannerCache(ttl=60, max_size=100)

        # Generate keys
        key1 = generate_cache_key("standard", "csgo")
        key2 = generate_cache_key("boost", "dota2")

        # Set items
        items1 = [{"item": "AK-47", "profit": 10.0}]
        items2 = [{"item": "Dragon Claw", "profit": 5.0}]

        cache.set(key1, items1)
        cache.set(key2, items2)

        # Get items
        assert cache.get(key1) == items1
        assert cache.get(key2) == items2

        # Check statistics
        stats = cache.get_statistics()
        assert stats["size"] == 2
        assert stats["hits"] == 2
        assert stats["misses"] == 0

        # Invalidate by pattern
        cache.invalidate("csgo")
        assert cache.get(key1) is None
        assert cache.get(key2) == items2

        # Clear
        cache.clear()
        assert len(cache) == 0
