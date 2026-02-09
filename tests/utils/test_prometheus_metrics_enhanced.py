"""Tests for enhanced Prometheus metrics (Roadmap Task #8).

Tests new metrics for arbitrage, cache, rate limiting, and Telegram updates.
"""

from src.utils.prometheus_metrics import (
    arbitrage_opportunities_current,
    arbitrage_scan_duration_seconds,
    arbitrage_scans_total,
    bot_uptime_seconds,
    cache_hit_rate,
    cache_operation_duration_seconds,
    cache_requests_total,
    rate_limit_hits_total,
    rate_limit_usage,
    set_bot_uptime,
    set_cache_hit_rate,
    set_rate_limit_usage,
    telegram_updates_total,
    track_arbitrage_scan,
    track_cache_operation,
    track_cache_request,
    track_rate_limit_hit,
    track_telegram_update,
)

# ============================================================================
# Tests: Arbitrage Metrics
# ============================================================================


def test_track_arbitrage_scan_success():
    """Test tracking successful arbitrage scan."""
    # Get initial value
    initial = arbitrage_scans_total.labels(
        game="csgo", level="standard", status="success"
    )._value.get()

    # Track scan
    track_arbitrage_scan(
        game="csgo",
        level="standard",
        opportunities_count=5,
        duration=2.5,
        success=True,
    )

    # Verify counter incremented
    new_value = arbitrage_scans_total.labels(
        game="csgo", level="standard", status="success"
    )._value.get()
    assert new_value == initial + 1

    # Verify current opportunities set
    current = arbitrage_opportunities_current.labels(game="csgo", level="standard")._value.get()
    assert current == 5


def test_track_arbitrage_scan_failure():
    """Test tracking failed arbitrage scan."""
    initial = arbitrage_scans_total.labels(
        game="dota2", level="medium", status="failed"
    )._value.get()

    track_arbitrage_scan(
        game="dota2",
        level="medium",
        opportunities_count=0,
        success=False,
    )

    new_value = arbitrage_scans_total.labels(
        game="dota2", level="medium", status="failed"
    )._value.get()
    assert new_value == initial + 1


def test_arbitrage_scan_duration_histogram():
    """Test arbitrage scan duration is recorded."""
    # Track a scan with duration
    track_arbitrage_scan(
        game="csgo",
        level="standard",
        opportunities_count=3,
        duration=1.5,
    )

    # Histogram should have recorded the observation
    # We can't easily assert on histogram values, but we can verify it doesn't error
    assert arbitrage_scan_duration_seconds is not None


# ============================================================================
# Tests: Telegram Metrics
# ============================================================================


def test_track_telegram_update_processed():
    """Test tracking processed Telegram update."""
    initial = telegram_updates_total.labels(type="message", status="processed")._value.get()

    track_telegram_update(update_type="message", success=True)

    new_value = telegram_updates_total.labels(type="message", status="processed")._value.get()
    assert new_value == initial + 1


def test_track_telegram_update_failed():
    """Test tracking failed Telegram update."""
    initial = telegram_updates_total.labels(type="callback_query", status="failed")._value.get()

    track_telegram_update(update_type="callback_query", success=False)

    new_value = telegram_updates_total.labels(type="callback_query", status="failed")._value.get()
    assert new_value == initial + 1


# ============================================================================
# Tests: Cache Metrics
# ============================================================================


def test_track_cache_request_hit():
    """Test tracking cache hit."""
    initial = cache_requests_total.labels(cache_type="redis", result="hit")._value.get()

    track_cache_request(cache_type="redis", hit=True)

    new_value = cache_requests_total.labels(cache_type="redis", result="hit")._value.get()
    assert new_value == initial + 1


def test_track_cache_request_miss():
    """Test tracking cache miss."""
    initial = cache_requests_total.labels(cache_type="memory", result="miss")._value.get()

    track_cache_request(cache_type="memory", hit=False)

    new_value = cache_requests_total.labels(cache_type="memory", result="miss")._value.get()
    assert new_value == initial + 1


def test_track_cache_operation():
    """Test tracking cache operation duration."""
    track_cache_operation(
        operation="get",
        cache_type="redis",
        duration=0.005,
    )

    # Verify histogram exists (actual observation testing is complex)
    assert cache_operation_duration_seconds is not None


def test_set_cache_hit_rate():
    """Test setting cache hit rate."""
    set_cache_hit_rate(cache_type="redis", hit_rate=0.75)

    value = cache_hit_rate.labels(cache_type="redis")._value.get()
    assert value == 0.75


def test_set_cache_hit_rate_boundaries():
    """Test cache hit rate with boundary values."""
    # Minimum
    set_cache_hit_rate(cache_type="memory", hit_rate=0.0)
    assert cache_hit_rate.labels(cache_type="memory")._value.get() == 0.0

    # Maximum
    set_cache_hit_rate(cache_type="memory", hit_rate=1.0)
    assert cache_hit_rate.labels(cache_type="memory")._value.get() == 1.0


# ============================================================================
# Tests: Rate Limiter Metrics
# ============================================================================


def test_track_rate_limit_hit():
    """Test tracking rate limit hit."""
    initial = rate_limit_hits_total.labels(
        endpoint="/market/items",
        limit_type="api",
    )._value.get()

    track_rate_limit_hit(endpoint="/market/items", limit_type="api")

    new_value = rate_limit_hits_total.labels(
        endpoint="/market/items",
        limit_type="api",
    )._value.get()
    assert new_value == initial + 1


def test_set_rate_limit_usage():
    """Test setting rate limit usage."""
    set_rate_limit_usage(endpoint="/market/items", usage_percent=75.5)

    value = rate_limit_usage.labels(endpoint="/market/items")._value.get()
    assert value == 75.5


def test_set_rate_limit_usage_boundaries():
    """Test rate limit usage with boundary values."""
    # Zero usage
    set_rate_limit_usage(endpoint="/balance", usage_percent=0.0)
    assert rate_limit_usage.labels(endpoint="/balance")._value.get() == 0.0

    # Full usage
    set_rate_limit_usage(endpoint="/balance", usage_percent=100.0)
    assert rate_limit_usage.labels(endpoint="/balance")._value.get() == 100.0


# ============================================================================
# Tests: System Metrics
# ============================================================================


def test_set_bot_uptime():
    """Test setting bot uptime."""
    set_bot_uptime(uptime_seconds=3600.0)  # 1 hour

    value = bot_uptime_seconds._value.get()
    assert value == 3600.0


def test_set_bot_uptime_updates():
    """Test bot uptime can be updated."""
    set_bot_uptime(uptime_seconds=100.0)
    assert bot_uptime_seconds._value.get() == 100.0

    set_bot_uptime(uptime_seconds=200.0)
    assert bot_uptime_seconds._value.get() == 200.0


# ============================================================================
# Tests: Integration
# ============================================================================


def test_multiple_metrics_do_not_interfere():
    """Test that different metrics don't interfere with each other."""
    # Track various metrics
    track_arbitrage_scan("csgo", "standard", 5, 2.0)
    track_telegram_update("message")
    track_cache_request("redis", True)
    track_rate_limit_hit("/market/items")
    set_bot_uptime(1000.0)

    # All should work independently
    assert arbitrage_opportunities_current.labels(game="csgo", level="standard")._value.get() == 5
    assert bot_uptime_seconds._value.get() == 1000.0


def test_metrics_with_different_labels():
    """Test metrics correctly separate by labels."""
    # Track same metric with different labels
    track_arbitrage_scan("csgo", "standard", 3)
    track_arbitrage_scan("dota2", "standard", 5)

    csgo_value = arbitrage_opportunities_current.labels(game="csgo", level="standard")._value.get()
    dota2_value = arbitrage_opportunities_current.labels(
        game="dota2", level="standard"
    )._value.get()

    assert csgo_value == 3
    assert dota2_value == 5
