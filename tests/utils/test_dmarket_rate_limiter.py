"""Tests for DMarketRateLimiter (Roadmap Task #3).

Tests per-endpoint rate limiting with aiolimiter integration.
"""

import asyncio
import time

import pytest

from src.utils.rate_limiter import DMarketRateLimiter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def rate_limiter():
    """Create DMarketRateLimiter instance."""
    return DMarketRateLimiter()


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_rate_limiter_initialization(rate_limiter):
    """Test rate limiter initializes with correct endpoints."""
    assert rate_limiter is not None

    # Check all expected endpoints are configured
    expected_endpoints = ["market", "inventory", "targets", "account", "trade", "other"]

    for endpoint in expected_endpoints:
        assert endpoint in rate_limiter._endpoint_limits
        assert endpoint in rate_limiter._limiters
        assert endpoint in rate_limiter._usage_counts
        assert endpoint in rate_limiter._429_counts


def test_rate_limiter_has_correct_limits(rate_limiter):
    """Test endpoint limits match specification."""
    expected_limits = {
        "market": 30,
        "inventory": 20,
        "targets": 10,
        "account": 15,
        "trade": 10,
        "other": 20,
    }

    for endpoint, expected_limit in expected_limits.items():
        actual_limit = rate_limiter._endpoint_limits[endpoint]
        assert actual_limit == expected_limit, (
            f"{endpoint}: expected {expected_limit}, got {actual_limit}"
        )


# ============================================================================
# Tests: Endpoint Category Detection
# ============================================================================


@pytest.mark.parametrize(
    "path,expected_category",
    [
        ("/exchange/v1/market/items", "market"),
        ("/exchange/v1/market/aggregated-prices", "market"),
        ("/exchange/v1/market/best-offers", "market"),
        ("/exchange/v1/market/search", "market"),
        ("/exchange/v1/user/inventory", "inventory"),
        ("/exchange/v1/target-lists", "targets"),
        ("/account/v1/balance", "account"),
        ("/api/v1/account/balance", "account"),
        ("/exchange/v1/market/items/buy", "trade"),
        ("/exchange/v1/user/offers/edit", "trade"),
        ("/some/unknown/endpoint", "other"),
    ],
)
def test_get_endpoint_category(rate_limiter, path, expected_category):
    """Test endpoint category detection from paths."""
    category = rate_limiter.get_endpoint_category(path)
    assert category == expected_category


# ============================================================================
# Tests: Rate Limiting
# ============================================================================


@pytest.mark.asyncio()
async def test_acquire_allows_request_within_limit(rate_limiter):
    """Test acquire() allows requests within rate limit."""
    # Should complete quickly since limit not reached
    start_time = time.time()
    await rate_limiter.acquire("market")
    elapsed = time.time() - start_time

    # Should not block significantly
    assert elapsed < 0.5

    # Check usage count incremented
    assert rate_limiter._usage_counts["market"] == 1


@pytest.mark.asyncio()
async def test_acquire_blocks_when_limit_reached():
    """Test acquire() blocks when rate limit is reached."""
    # Create limiter with very low limit for testing
    limiter = DMarketRateLimiter()

    # Override limit to 2 requests per second for fast testing
    from aiolimiter import AsyncLimiter

    limiter._limiters["market"] = AsyncLimiter(max_rate=2, time_period=1.0)

    # Make 2 quick requests (should be fine)
    await limiter.acquire("market")
    await limiter.acquire("market")

    # Third request should block briefly
    start_time = time.time()
    await limiter.acquire("market")
    elapsed = time.time() - start_time

    # Should have been delayed (~0.5s for third request in 1s window)
    assert elapsed >= 0.3  # Allow some tolerance


@pytest.mark.asyncio()
async def test_acquire_with_full_path(rate_limiter):
    """Test acquire() works with full endpoint paths."""
    # Pass full path instead of category
    await rate_limiter.acquire("/exchange/v1/market/items")

    # Should map to "market" category
    assert rate_limiter._usage_counts["market"] == 1


@pytest.mark.asyncio()
async def test_parallel_acquires_respect_limits():
    """Test parallel requests respect rate limits."""
    limiter = DMarketRateLimiter()

    # Override limit for testing
    from aiolimiter import AsyncLimiter

    limiter._limiters["market"] = AsyncLimiter(max_rate=5, time_period=1.0)

    # Make 10 parallel requests
    start_time = time.time()
    tasks = [limiter.acquire("market") for _ in range(10)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    # Should take at least 0.8 seconds (allow tolerance for system delays)
    # 5 req in first second, 5 in second = minimum ~1s theoretical
    assert elapsed >= 0.8, f"Expected >= 0.8s, got {elapsed:.2f}s"
    assert limiter._usage_counts["market"] == 10


# ============================================================================
# Tests: 429 Error Recording
# ============================================================================


def test_record_429_error(rate_limiter):
    """Test recording 429 errors."""
    # Initially no errors
    assert rate_limiter._429_counts["market"] == 0

    # Record error
    rate_limiter.record_429_error("/exchange/v1/market/items")

    # Count should increment
    assert rate_limiter._429_counts["market"] == 1

    # Record another
    rate_limiter.record_429_error("market")
    assert rate_limiter._429_counts["market"] == 2


def test_record_429_error_multiple_endpoints(rate_limiter):
    """Test recording 429 errors for different endpoints."""
    rate_limiter.record_429_error("market")
    rate_limiter.record_429_error("inventory")
    rate_limiter.record_429_error("market")

    assert rate_limiter._429_counts["market"] == 2
    assert rate_limiter._429_counts["inventory"] == 1
    assert rate_limiter._429_counts["targets"] == 0


# ============================================================================
# Tests: Statistics
# ============================================================================


def test_get_stats_initial_state(rate_limiter):
    """Test get_stats() returns correct initial state."""
    stats = rate_limiter.get_stats()

    assert isinstance(stats, dict)
    assert len(stats) == 6  # 6 endpoint categories

    for category, data in stats.items():
        assert "limit_per_minute" in data
        assert "total_requests" in data
        assert "total_429_errors" in data
        assert data["total_requests"] == 0
        assert data["total_429_errors"] == 0


@pytest.mark.asyncio()
async def test_get_stats_after_requests(rate_limiter):
    """Test get_stats() reflects actual usage."""
    # Make some requests
    await rate_limiter.acquire("market")
    await rate_limiter.acquire("market")
    await rate_limiter.acquire("inventory")

    # Record some errors
    rate_limiter.record_429_error("market")

    stats = rate_limiter.get_stats()

    assert stats["market"]["total_requests"] == 2
    assert stats["market"]["total_429_errors"] == 1
    assert stats["inventory"]["total_requests"] == 1
    assert stats["inventory"]["total_429_errors"] == 0


def test_reset_stats(rate_limiter):
    """Test reset_stats() clears all statistics."""
    # Generate some usage
    rate_limiter._usage_counts["market"] = 10
    rate_limiter._429_counts["inventory"] = 3

    # Reset
    rate_limiter.reset_stats()

    # All should be zero
    for category in rate_limiter._endpoint_limits:
        assert rate_limiter._usage_counts[category] == 0
        assert rate_limiter._429_counts[category] == 0
        assert rate_limiter._warning_sent[category] is False


# ============================================================================
# Tests: Edge Cases
# ============================================================================


@pytest.mark.asyncio()
async def test_acquire_unknown_endpoint_uses_other(rate_limiter):
    """Test unknown endpoints use 'other' category."""
    await rate_limiter.acquire("/some/unknown/path")

    # Should use "other" category
    assert rate_limiter._usage_counts["other"] == 1


@pytest.mark.asyncio()
async def test_acquire_case_insensitive(rate_limiter):
    """Test endpoint detection is case-insensitive."""
    await rate_limiter.acquire("/EXCHANGE/V1/MARKET/ITEMS")
    await rate_limiter.acquire("/exchange/v1/MARKET/items")

    # Both should map to "market"
    assert rate_limiter._usage_counts["market"] == 2


@pytest.mark.asyncio()
async def test_acquire_with_empty_string():
    """Test acquire() handles empty string gracefully."""
    limiter = DMarketRateLimiter()

    # Should not crash, should use "other"
    await limiter.acquire("")
    assert limiter._usage_counts["other"] == 1


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio()
async def test_realistic_usage_pattern():
    """Test realistic API usage pattern."""
    limiter = DMarketRateLimiter()

    # Simulate typical bot behavior
    tasks = []

    # 5 market searches
    for _ in range(5):
        tasks.append(limiter.acquire("market"))

    # 2 inventory checks
    for _ in range(2):
        tasks.append(limiter.acquire("inventory"))

    # 1 target creation
    tasks.append(limiter.acquire("targets"))

    # Execute all
    start_time = time.time()
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    # Should complete (limits high enough)
    assert elapsed < 5.0

    # Check counts
    assert limiter._usage_counts["market"] == 5
    assert limiter._usage_counts["inventory"] == 2
    assert limiter._usage_counts["targets"] == 1

    # Get summary stats
    stats = limiter.get_stats()
    assert stats["market"]["total_requests"] == 5
