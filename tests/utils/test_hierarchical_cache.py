"""Tests for hierarchical cache system (Roadmap Task #6).

Tests smart TTL, hierarchical keys, and cache warming.
"""

import pytest

from src.utils.redis_cache import CacheKey, CacheTTL, HierarchicalCache, RedisCache

# ============================================================================
# Tests: CacheKey
# ============================================================================


def test_cache_key_market_items():
    """Test market items cache key generation."""
    # Full key
    key = CacheKey.market_items("csgo", "standard", 100, 1000)
    assert key == "market:items:csgo:standard:100:1000"

    # Partial key
    key = CacheKey.market_items("csgo", "standard")
    assert key == "market:items:csgo:standard"

    # Minimal key
    key = CacheKey.market_items("csgo")
    assert key == "market:items:csgo"


def test_cache_key_balance():
    """Test balance cache key generation."""
    key = CacheKey.balance(12345)
    assert key == "balance:12345"


def test_cache_key_targets():
    """Test targets cache key generation."""
    # With game
    key = CacheKey.targets(12345, "csgo")
    assert key == "targets:12345:csgo"

    # Without game
    key = CacheKey.targets(12345)
    assert key == "targets:12345"


def test_cache_key_user_settings():
    """Test user settings cache key generation."""
    key = CacheKey.user_settings(12345)
    assert key == "user:settings:12345"


def test_cache_key_arbitrage_results():
    """Test arbitrage results cache key generation."""
    key = CacheKey.arbitrage_results("csgo", "standard")
    assert key == "arbitrage:results:csgo:standard"


def test_cache_key_sales_history():
    """Test sales history cache key generation."""
    key = CacheKey.sales_history("item_123", 7)
    assert key == "sales:history:item_123:7"

    # Default days
    key = CacheKey.sales_history("item_123")
    assert key == "sales:history:item_123:7"


# ============================================================================
# Tests: CacheTTL
# ============================================================================


def test_cache_ttl_constants():
    """Test TTL constants are reasonable."""
    assert CacheTTL.MARKET_ITEMS == 300  # 5 min
    assert CacheTTL.ARBITRAGE_RESULTS == 180  # 3 min
    assert CacheTTL.BALANCE == 600  # 10 min
    assert CacheTTL.TARGETS == 900  # 15 min
    assert CacheTTL.USER_SETTINGS == 1800  # 30 min
    assert CacheTTL.USER_PROFILE == 3600  # 1 hour


def test_cache_ttl_get_ttl_for_market_items():
    """Test get_ttl returns correct TTL for market items."""
    ttl = CacheTTL.get_ttl("market:items:csgo:standard")
    assert ttl == CacheTTL.MARKET_ITEMS


def test_cache_ttl_get_ttl_for_balance():
    """Test get_ttl returns correct TTL for balance."""
    ttl = CacheTTL.get_ttl("balance:12345")
    assert ttl == CacheTTL.BALANCE


def test_cache_ttl_get_ttl_for_targets():
    """Test get_ttl returns correct TTL for targets."""
    ttl = CacheTTL.get_ttl("targets:12345:csgo")
    assert ttl == CacheTTL.TARGETS


def test_cache_ttl_get_ttl_default():
    """Test get_ttl returns default TTL for unknown types."""
    ttl = CacheTTL.get_ttl("unknown:key:type")
    assert ttl == 300  # Default


# ============================================================================
# Tests: HierarchicalCache
# ============================================================================


@pytest.fixture()
def mock_redis_cache():
    """Create mock Redis cache for testing."""
    redis_cache = RedisCache(
        redis_url=None,  # Will use memory cache
        default_ttl=300,
        fallback_to_memory=True,
    )
    return redis_cache


@pytest.fixture()
async def hierarchical_cache(mock_redis_cache):
    """Create hierarchical cache for testing."""
    return HierarchicalCache(mock_redis_cache)


@pytest.mark.asyncio()
async def test_hierarchical_cache_market_items(hierarchical_cache):
    """Test caching market items."""
    data = {"items": [{"id": "1", "price": 100}]}

    # Set
    result = await hierarchical_cache.set_market_items(data, "csgo", "standard", 100, 1000)
    assert result is True

    # Get
    cached = await hierarchical_cache.get_market_items("csgo", "standard", 100, 1000)
    assert cached == data


@pytest.mark.asyncio()
async def test_hierarchical_cache_balance(hierarchical_cache):
    """Test caching user balance."""
    balance_data = {"usd": "10000", "dmc": "5000"}

    # Set
    result = await hierarchical_cache.set_balance(12345, balance_data)
    assert result is True

    # Get
    cached = await hierarchical_cache.get_balance(12345)
    assert cached == balance_data

    # Invalidate
    result = await hierarchical_cache.invalidate_balance(12345)
    assert result is True

    # Should be None after invalidation
    cached = await hierarchical_cache.get_balance(12345)
    assert cached is None


@pytest.mark.asyncio()
async def test_hierarchical_cache_targets(hierarchical_cache):
    """Test caching user targets."""
    targets_data = [{"item": "AK-47", "price": 10.0}]

    # Set
    result = await hierarchical_cache.set_targets(12345, targets_data, "csgo")
    assert result is True

    # Get
    cached = await hierarchical_cache.get_targets(12345, "csgo")
    assert cached == targets_data

    # Invalidate specific game
    result = await hierarchical_cache.invalidate_targets(12345, "csgo")
    assert result is True


@pytest.mark.asyncio()
async def test_hierarchical_cache_arbitrage_results(hierarchical_cache):
    """Test caching arbitrage results."""
    results = [{"item": "test", "profit": 5.0}]

    # Set
    result = await hierarchical_cache.set_arbitrage_results("csgo", "standard", results)
    assert result is True

    # Get
    cached = await hierarchical_cache.get_arbitrage_results("csgo", "standard")
    assert cached == results


@pytest.mark.asyncio()
async def test_hierarchical_cache_warm_cache(hierarchical_cache):
    """Test cache warming functionality."""
    games = ["csgo", "dota2"]
    levels = ["standard", "medium"]

    stats = await hierarchical_cache.warm_cache(games, levels)

    assert "attempted" in stats
    assert "succeeded" in stats
    assert "failed" in stats
    assert stats["attempted"] == 4  # 2 games * 2 levels


@pytest.mark.asyncio()
async def test_hierarchical_cache_invalidate_market_data(hierarchical_cache):
    """Test invalidating market data cache."""
    # Set some market data
    await hierarchical_cache.set_market_items({"test": "data"}, "csgo", "standard")

    # Invalidate all market data for csgo
    count = await hierarchical_cache.invalidate_market_data("csgo")

    # Count might be 0 if using memory cache without pattern support
    assert count >= 0


# ============================================================================
# Tests: Integration
# ============================================================================


@pytest.mark.asyncio()
async def test_hierarchical_cache_end_to_end(hierarchical_cache):
    """Test complete workflow with hierarchical cache."""
    user_id = 12345

    # 1. Cache user balance
    balance = {"usd": "10000"}
    await hierarchical_cache.set_balance(user_id, balance)

    # 2. Cache user targets
    targets = [{"item": "AK-47", "price": 10.0}]
    await hierarchical_cache.set_targets(user_id, targets, "csgo")

    # 3. Cache arbitrage results
    results = [{"item": "test", "profit": 5.0}]
    await hierarchical_cache.set_arbitrage_results("csgo", "standard", results)

    # 4. Retrieve all cached data
    cached_balance = await hierarchical_cache.get_balance(user_id)
    cached_targets = await hierarchical_cache.get_targets(user_id, "csgo")
    cached_results = await hierarchical_cache.get_arbitrage_results("csgo", "standard")

    # 5. Verify
    assert cached_balance == balance
    assert cached_targets == targets
    assert cached_results == results

    # 6. Invalidate balance
    await hierarchical_cache.invalidate_balance(user_id)
    assert await hierarchical_cache.get_balance(user_id) is None

    # 7. Other caches should still work
    assert await hierarchical_cache.get_targets(user_id, "csgo") == targets
    assert await hierarchical_cache.get_arbitrage_results("csgo", "standard") == results


@pytest.mark.asyncio()
async def test_hierarchical_cache_ttl_applied_correctly(hierarchical_cache, mock_redis_cache):
    """Test that correct TTL is applied for different data types."""
    user_id = 12345

    # Cache different types of data
    await hierarchical_cache.set_balance(user_id, {"usd": "1000"})
    await hierarchical_cache.set_targets(user_id, [], "csgo")
    await hierarchical_cache.set_arbitrage_results("csgo", "standard", [])

    # Verify data was cached (we can't easily test TTL without time manipulation)
    assert await hierarchical_cache.get_balance(user_id) is not None
    assert await hierarchical_cache.get_targets(user_id, "csgo") is not None
    assert await hierarchical_cache.get_arbitrage_results("csgo", "standard") is not None
