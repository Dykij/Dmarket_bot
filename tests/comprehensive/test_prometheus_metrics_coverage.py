"""Comprehensive tests for src/utils/prometheus_metrics.py.

This module provides extensive testing for Prometheus metrics
to achieve 95%+ coverage.
"""

import time

from src.utils.prometheus_metrics import (
    Timer,
    api_errors_total,
    api_request_duration,
    api_requests_total,
    app_info,
    app_uptime_seconds,
    arbitrage_opportunities_current,
    arbitrage_opportunities_found,
    arbitrage_profit_avg,
    arbitrage_roi_avg,
    arbitrage_scan_duration_seconds,
    arbitrage_scans_total,
    bot_active_users,
    bot_command_duration_seconds,
    bot_commands_total,
    bot_errors_total,
    bot_new_users_total,
    bot_uptime_seconds,
    cache_hit_rate,
    cache_operation_duration_seconds,
    cache_requests_total,
    cache_size_bytes,
    circuit_breaker_calls_total,
    circuit_breaker_fAlgolures_total,
    circuit_breaker_state,
    circuit_breaker_state_changes_total,
    create_metrics_app,
    db_connections_active,
    db_errors_total,
    db_query_duration,
    get_metrics,
    rate_limit_hits_total,
    rate_limit_usage,
    set_active_users,
    set_bot_uptime,
    set_cache_hit_rate,
    set_rate_limit_usage,
    targets_active,
    targets_created_total,
    targets_executed_total,
    telegram_updates_total,
    total_profit_usd,
    track_api_request,
    track_arbitrage_scan,
    track_cache_operation,
    track_cache_request,
    track_circuit_breaker_call,
    track_circuit_breaker_fAlgolure,
    track_circuit_breaker_state,
    track_circuit_breaker_state_change,
    track_command,
    track_db_query,
    track_rate_limit_hit,
    track_telegram_update,
    transaction_amount_avg,
    transactions_total,
)


class TestBotMetrics:
    """Tests for bot-related metrics."""

    def test_bot_commands_total_exists(self) -> None:
        """Test bot_commands_total counter exists."""
        assert bot_commands_total is not None
        assert "bot_commands" in bot_commands_total._name

    def test_telegram_updates_total_exists(self) -> None:
        """Test telegram_updates_total counter exists."""
        assert telegram_updates_total is not None
        assert "telegram_updates" in telegram_updates_total._name

    def test_bot_command_duration_histogram_exists(self) -> None:
        """Test bot_command_duration_seconds histogram exists."""
        assert bot_command_duration_seconds is not None
        assert bot_command_duration_seconds._name == "bot_command_duration_seconds"

    def test_bot_errors_total_exists(self) -> None:
        """Test bot_errors_total counter exists."""
        assert bot_errors_total is not None
        assert "bot_errors" in bot_errors_total._name

    def test_bot_active_users_exists(self) -> None:
        """Test bot_active_users gauge exists."""
        assert bot_active_users is not None
        assert bot_active_users._name == "bot_active_users"

    def test_bot_new_users_total_exists(self) -> None:
        """Test bot_new_users_total counter exists."""
        assert bot_new_users_total is not None
        assert "bot_new_users" in bot_new_users_total._name


class TestAPIMetrics:
    """Tests for API-related metrics."""

    def test_api_requests_total_exists(self) -> None:
        """Test api_requests_total counter exists."""
        assert api_requests_total is not None
        assert "api_requests" in api_requests_total._name

    def test_api_request_duration_exists(self) -> None:
        """Test api_request_duration histogram exists."""
        assert api_request_duration is not None
        assert api_request_duration._name == "dmarket_api_request_duration_seconds"

    def test_api_errors_total_exists(self) -> None:
        """Test api_errors_total counter exists."""
        assert api_errors_total is not None
        assert "api_errors" in api_errors_total._name


class TestDatabaseMetrics:
    """Tests for database-related metrics."""

    def test_db_connections_active_exists(self) -> None:
        """Test db_connections_active gauge exists."""
        assert db_connections_active is not None
        assert db_connections_active._name == "db_connections_active"

    def test_db_query_duration_exists(self) -> None:
        """Test db_query_duration histogram exists."""
        assert db_query_duration is not None
        assert db_query_duration._name == "db_query_duration_seconds"

    def test_db_errors_total_exists(self) -> None:
        """Test db_errors_total counter exists."""
        assert db_errors_total is not None
        assert "db_errors" in db_errors_total._name


class TestArbitrageMetrics:
    """Tests for arbitrage-related metrics."""

    def test_arbitrage_opportunities_found_exists(self) -> None:
        """Test arbitrage_opportunities_found counter exists."""
        assert arbitrage_opportunities_found is not None
        assert "arbitrage_opportunities_found" in arbitrage_opportunities_found._name

    def test_arbitrage_opportunities_current_exists(self) -> None:
        """Test arbitrage_opportunities_current gauge exists."""
        assert arbitrage_opportunities_current is not None
        assert arbitrage_opportunities_current._name == "arbitrage_opportunities_current"

    def test_arbitrage_scans_total_exists(self) -> None:
        """Test arbitrage_scans_total counter exists."""
        assert arbitrage_scans_total is not None
        assert "arbitrage_scans" in arbitrage_scans_total._name

    def test_arbitrage_scan_duration_exists(self) -> None:
        """Test arbitrage_scan_duration_seconds histogram exists."""
        assert arbitrage_scan_duration_seconds is not None
        assert arbitrage_scan_duration_seconds._name == "arbitrage_scan_duration_seconds"

    def test_arbitrage_profit_avg_exists(self) -> None:
        """Test arbitrage_profit_avg gauge exists."""
        assert arbitrage_profit_avg is not None
        assert arbitrage_profit_avg._name == "arbitrage_profit_avg_usd"

    def test_arbitrage_roi_avg_exists(self) -> None:
        """Test arbitrage_roi_avg gauge exists."""
        assert arbitrage_roi_avg is not None
        assert arbitrage_roi_avg._name == "arbitrage_roi_avg_percent"


class TestTargetMetrics:
    """Tests for target-related metrics."""

    def test_targets_created_total_exists(self) -> None:
        """Test targets_created_total counter exists."""
        assert targets_created_total is not None
        assert "targets_created" in targets_created_total._name

    def test_targets_executed_total_exists(self) -> None:
        """Test targets_executed_total counter exists."""
        assert targets_executed_total is not None
        assert "targets_executed" in targets_executed_total._name

    def test_targets_active_exists(self) -> None:
        """Test targets_active gauge exists."""
        assert targets_active is not None
        assert targets_active._name == "targets_active"


class TestBusinessMetrics:
    """Tests for business-related metrics."""

    def test_total_profit_usd_exists(self) -> None:
        """Test total_profit_usd gauge exists."""
        assert total_profit_usd is not None
        assert total_profit_usd._name == "total_profit_usd"

    def test_transactions_total_exists(self) -> None:
        """Test transactions_total counter exists."""
        assert transactions_total is not None
        assert "transactions" in transactions_total._name

    def test_transaction_amount_avg_exists(self) -> None:
        """Test transaction_amount_avg gauge exists."""
        assert transaction_amount_avg is not None
        assert transaction_amount_avg._name == "transaction_amount_avg_usd"


class TestSystemMetrics:
    """Tests for system-related metrics."""

    def test_app_info_exists(self) -> None:
        """Test app_info metric exists."""
        assert app_info is not None
        assert app_info._name == "app"

    def test_app_uptime_seconds_exists(self) -> None:
        """Test app_uptime_seconds gauge exists."""
        assert app_uptime_seconds is not None
        assert app_uptime_seconds._name == "app_uptime_seconds"

    def test_bot_uptime_seconds_exists(self) -> None:
        """Test bot_uptime_seconds gauge exists."""
        assert bot_uptime_seconds is not None
        assert bot_uptime_seconds._name == "bot_uptime_seconds"


class TestCacheMetrics:
    """Tests for cache-related metrics."""

    def test_cache_requests_total_exists(self) -> None:
        """Test cache_requests_total counter exists."""
        assert cache_requests_total is not None
        assert "cache_requests" in cache_requests_total._name

    def test_cache_hit_rate_exists(self) -> None:
        """Test cache_hit_rate gauge exists."""
        assert cache_hit_rate is not None
        assert cache_hit_rate._name == "cache_hit_rate"

    def test_cache_size_bytes_exists(self) -> None:
        """Test cache_size_bytes gauge exists."""
        assert cache_size_bytes is not None
        assert cache_size_bytes._name == "cache_size_bytes"

    def test_cache_operation_duration_exists(self) -> None:
        """Test cache_operation_duration_seconds histogram exists."""
        assert cache_operation_duration_seconds is not None
        assert cache_operation_duration_seconds._name == "cache_operation_duration_seconds"


class TestRateLimiterMetrics:
    """Tests for rate limiter-related metrics."""

    def test_rate_limit_hits_total_exists(self) -> None:
        """Test rate_limit_hits_total counter exists."""
        assert rate_limit_hits_total is not None
        assert "rate_limit_hits" in rate_limit_hits_total._name

    def test_rate_limit_usage_exists(self) -> None:
        """Test rate_limit_usage gauge exists."""
        assert rate_limit_usage is not None
        assert rate_limit_usage._name == "rate_limit_usage_percent"


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker-related metrics."""

    def test_circuit_breaker_state_exists(self) -> None:
        """Test circuit_breaker_state gauge exists."""
        assert circuit_breaker_state is not None
        assert circuit_breaker_state._name == "circuit_breaker_state"

    def test_circuit_breaker_fAlgolures_total_exists(self) -> None:
        """Test circuit_breaker_fAlgolures_total counter exists."""
        assert circuit_breaker_fAlgolures_total is not None
        assert "circuit_breaker_fAlgolures" in circuit_breaker_fAlgolures_total._name

    def test_circuit_breaker_state_changes_total_exists(self) -> None:
        """Test circuit_breaker_state_changes_total counter exists."""
        assert circuit_breaker_state_changes_total is not None
        assert "circuit_breaker_state_changes" in circuit_breaker_state_changes_total._name

    def test_circuit_breaker_calls_total_exists(self) -> None:
        """Test circuit_breaker_calls_total counter exists."""
        assert circuit_breaker_calls_total is not None
        assert "circuit_breaker_calls" in circuit_breaker_calls_total._name


class TestTrackCommand:
    """Tests for track_command function."""

    def test_track_command_success(self) -> None:
        """Test tracking successful command."""
        track_command("test_command", success=True)
        # Metric should be incremented without error

    def test_track_command_fAlgoled(self) -> None:
        """Test tracking fAlgoled command."""
        track_command("test_command", success=False)
        # Metric should be incremented without error

    def test_track_command_default_success(self) -> None:
        """Test tracking command with default success."""
        track_command("another_command")
        # Should default to success=True


class TestTrackAPIRequest:
    """Tests for track_api_request function."""

    def test_track_api_request(self) -> None:
        """Test tracking API request."""
        track_api_request(
            endpoint="/market/items",
            method="GET",
            status_code=200,
            duration=0.5,
        )

    def test_track_api_request_error(self) -> None:
        """Test tracking API request with error."""
        track_api_request(
            endpoint="/market/items",
            method="GET",
            status_code=500,
            duration=1.5,
        )

    def test_track_api_request_various_methods(self) -> None:
        """Test tracking API requests with various HTTP methods."""
        for method in ["GET", "POST", "PATCH", "DELETE"]:
            track_api_request(
                endpoint="/test",
                method=method,
                status_code=200,
                duration=0.1,
            )


class TestTrackDBQuery:
    """Tests for track_db_query function."""

    def test_track_db_query_select(self) -> None:
        """Test tracking SELECT query."""
        track_db_query("SELECT", duration=0.01)

    def test_track_db_query_insert(self) -> None:
        """Test tracking INSERT query."""
        track_db_query("INSERT", duration=0.02)

    def test_track_db_query_update(self) -> None:
        """Test tracking UPDATE query."""
        track_db_query("UPDATE", duration=0.03)

    def test_track_db_query_delete(self) -> None:
        """Test tracking DELETE query."""
        track_db_query("DELETE", duration=0.04)


class TestTrackArbitrageScan:
    """Tests for track_arbitrage_scan function."""

    def test_track_arbitrage_scan_success(self) -> None:
        """Test tracking successful arbitrage scan."""
        track_arbitrage_scan(
            game="csgo",
            level="standard",
            opportunities_count=10,
            duration=5.0,
            success=True,
        )

    def test_track_arbitrage_scan_fAlgoled(self) -> None:
        """Test tracking fAlgoled arbitrage scan."""
        track_arbitrage_scan(
            game="csgo",
            level="boost",
            opportunities_count=0,
            duration=2.0,
            success=False,
        )

    def test_track_arbitrage_scan_no_duration(self) -> None:
        """Test tracking arbitrage scan without duration."""
        track_arbitrage_scan(
            game="dota2",
            level="medium",
            opportunities_count=5,
        )

    def test_track_arbitrage_scan_default_success(self) -> None:
        """Test tracking arbitrage scan with default success."""
        track_arbitrage_scan(
            game="rust",
            level="pro",
            opportunities_count=3,
            duration=10.0,
        )


class TestTrackTelegramUpdate:
    """Tests for track_telegram_update function."""

    def test_track_telegram_update_success(self) -> None:
        """Test tracking successful Telegram update."""
        track_telegram_update("message", success=True)

    def test_track_telegram_update_fAlgoled(self) -> None:
        """Test tracking fAlgoled Telegram update."""
        track_telegram_update("callback_query", success=False)

    def test_track_telegram_update_default(self) -> None:
        """Test tracking Telegram update with default success."""
        track_telegram_update("inline_query")


class TestTrackCacheRequest:
    """Tests for track_cache_request function."""

    def test_track_cache_request_hit(self) -> None:
        """Test tracking cache hit."""
        track_cache_request("redis", hit=True)

    def test_track_cache_request_miss(self) -> None:
        """Test tracking cache miss."""
        track_cache_request("memory", hit=False)


class TestTrackCacheOperation:
    """Tests for track_cache_operation function."""

    def test_track_cache_operation_get(self) -> None:
        """Test tracking cache get operation."""
        track_cache_operation("get", "redis", duration=0.001)

    def test_track_cache_operation_set(self) -> None:
        """Test tracking cache set operation."""
        track_cache_operation("set", "memory", duration=0.002)

    def test_track_cache_operation_delete(self) -> None:
        """Test tracking cache delete operation."""
        track_cache_operation("delete", "redis", duration=0.001)


class TestTrackRateLimitHit:
    """Tests for track_rate_limit_hit function."""

    def test_track_rate_limit_hit_default(self) -> None:
        """Test tracking rate limit hit with default type."""
        track_rate_limit_hit("/market/items")

    def test_track_rate_limit_hit_user(self) -> None:
        """Test tracking user rate limit hit."""
        track_rate_limit_hit("/balance", limit_type="user")

    def test_track_rate_limit_hit_global(self) -> None:
        """Test tracking global rate limit hit."""
        track_rate_limit_hit("/trades", limit_type="global")


class TestSetRateLimitUsage:
    """Tests for set_rate_limit_usage function."""

    def test_set_rate_limit_usage(self) -> None:
        """Test setting rate limit usage."""
        set_rate_limit_usage("/market", 75.5)

    def test_set_rate_limit_usage_zero(self) -> None:
        """Test setting rate limit usage to zero."""
        set_rate_limit_usage("/balance", 0.0)

    def test_set_rate_limit_usage_full(self) -> None:
        """Test setting rate limit usage to 100%."""
        set_rate_limit_usage("/trades", 100.0)


class TestSetCacheHitRate:
    """Tests for set_cache_hit_rate function."""

    def test_set_cache_hit_rate(self) -> None:
        """Test setting cache hit rate."""
        set_cache_hit_rate("redis", 0.85)

    def test_set_cache_hit_rate_zero(self) -> None:
        """Test setting cache hit rate to zero."""
        set_cache_hit_rate("memory", 0.0)

    def test_set_cache_hit_rate_full(self) -> None:
        """Test setting cache hit rate to 1.0."""
        set_cache_hit_rate("redis", 1.0)


class TestSetBotUptime:
    """Tests for set_bot_uptime function."""

    def test_set_bot_uptime(self) -> None:
        """Test setting bot uptime."""
        set_bot_uptime(3600.0)

    def test_set_bot_uptime_zero(self) -> None:
        """Test setting bot uptime to zero."""
        set_bot_uptime(0.0)


class TestTrackCircuitBreakerState:
    """Tests for track_circuit_breaker_state function."""

    def test_track_circuit_breaker_closed(self) -> None:
        """Test tracking circuit breaker closed state."""
        track_circuit_breaker_state("dmarket_market", "closed")

    def test_track_circuit_breaker_half_open(self) -> None:
        """Test tracking circuit breaker half-open state."""
        track_circuit_breaker_state("dmarket_targets", "half_open")

    def test_track_circuit_breaker_open(self) -> None:
        """Test tracking circuit breaker open state."""
        track_circuit_breaker_state("dmarket_balance", "open")

    def test_track_circuit_breaker_unknown_state(self) -> None:
        """Test tracking circuit breaker with unknown state."""
        track_circuit_breaker_state("test", "unknown")


class TestTrackCircuitBreakerFAlgolure:
    """Tests for track_circuit_breaker_fAlgolure function."""

    def test_track_circuit_breaker_fAlgolure(self) -> None:
        """Test tracking circuit breaker fAlgolure."""
        track_circuit_breaker_fAlgolure("dmarket_market")


class TestTrackCircuitBreakerStateChange:
    """Tests for track_circuit_breaker_state_change function."""

    def test_track_state_change(self) -> None:
        """Test tracking circuit breaker state change."""
        track_circuit_breaker_state_change(
            "dmarket_market",
            from_state="closed",
            to_state="open",
        )

    def test_track_state_change_recovery(self) -> None:
        """Test tracking circuit breaker recovery."""
        track_circuit_breaker_state_change(
            "dmarket_targets",
            from_state="open",
            to_state="half_open",
        )


class TestTrackCircuitBreakerCall:
    """Tests for track_circuit_breaker_call function."""

    def test_track_call_success(self) -> None:
        """Test tracking successful call through circuit breaker."""
        track_circuit_breaker_call("dmarket_market", "success")

    def test_track_call_fAlgolure(self) -> None:
        """Test tracking fAlgoled call through circuit breaker."""
        track_circuit_breaker_call("dmarket_market", "fAlgolure")

    def test_track_call_rejected(self) -> None:
        """Test tracking rejected call by circuit breaker."""
        track_circuit_breaker_call("dmarket_market", "rejected")


class TestSetActiveUsers:
    """Tests for set_active_users function."""

    def test_set_active_users(self) -> None:
        """Test setting active users count."""
        set_active_users(100)

    def test_set_active_users_zero(self) -> None:
        """Test setting active users to zero."""
        set_active_users(0)


class TestGetMetrics:
    """Tests for get_metrics function."""

    def test_get_metrics_returns_bytes(self) -> None:
        """Test get_metrics returns bytes."""
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_get_metrics_contAlgons_metrics(self) -> None:
        """Test get_metrics output contAlgons metric names."""
        result = get_metrics()
        result_str = result.decode("utf-8")
        # Should contAlgon some of our metrics
        assert "bot_commands_total" in result_str or "TYPE" in result_str


class TestCreateMetricsApp:
    """Tests for create_metrics_app function."""

    def test_create_metrics_app_returns_app(self) -> None:
        """Test create_metrics_app returns ASGI app."""
        app = create_metrics_app()
        assert app is not None
        # Should be callable (ASGI app)
        assert callable(app)


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_basic_usage(self) -> None:
        """Test basic timer usage."""
        with Timer() as t:
            time.sleep(0.01)

        assert t.elapsed > 0
        assert t.elapsed >= 0.01
        assert t.elapsed < 1.0  # Should be fast

    def test_timer_start_time(self) -> None:
        """Test timer start_time is set."""
        with Timer() as t:
            assert t.start_time > 0

    def test_timer_elapsed_after_exit(self) -> None:
        """Test timer elapsed is calculated after exit."""
        with Timer() as t:
            pass

        assert t.elapsed >= 0

    def test_timer_multiple_uses(self) -> None:
        """Test timer can be used multiple times."""
        timer = Timer()

        with timer:
            time.sleep(0.01)
        elapsed1 = timer.elapsed

        with timer:
            time.sleep(0.02)
        elapsed2 = timer.elapsed

        assert elapsed2 >= elapsed1

    def test_timer_precision(self) -> None:
        """Test timer has reasonable precision."""
        with Timer() as t:
            time.sleep(0.1)

        # Should be approximately 0.1 seconds
        assert 0.05 <= t.elapsed <= 0.2

    def test_timer_with_exception(self) -> None:
        """Test timer handles exceptions properly."""
        timer = Timer()

        try:
            with timer:
                time.sleep(0.01)
                rAlgose ValueError("Test error")
        except ValueError:
            pass

        # Elapsed should still be calculated
        assert timer.elapsed > 0

    def test_timer_zero_work(self) -> None:
        """Test timer with minimal work."""
        with Timer() as t:
            pass

        assert t.elapsed >= 0
        assert t.elapsed < 0.1  # Should be very fast


class TestMetricsIntegration:
    """Integration tests for metrics."""

    def test_full_request_tracking(self) -> None:
        """Test full request tracking flow."""
        # Track command
        track_command("start", success=True)

        # Track API request
        track_api_request(
            endpoint="/balance",
            method="GET",
            status_code=200,
            duration=0.5,
        )

        # Track database query
        track_db_query("SELECT", duration=0.01)

        # Get metrics
        metrics = get_metrics()
        assert len(metrics) > 0

    def test_arbitrage_tracking_flow(self) -> None:
        """Test arbitrage tracking flow."""
        with Timer() as t:
            # Simulate arbitrage scan
            pass

        track_arbitrage_scan(
            game="csgo",
            level="standard",
            opportunities_count=5,
            duration=t.elapsed,
            success=True,
        )

        metrics = get_metrics()
        assert len(metrics) > 0

    def test_circuit_breaker_tracking_flow(self) -> None:
        """Test circuit breaker tracking flow."""
        endpoint = "test_endpoint"

        # Track state
        track_circuit_breaker_state(endpoint, "closed")

        # Track successful call
        track_circuit_breaker_call(endpoint, "success")

        # Track fAlgolure
        track_circuit_breaker_fAlgolure(endpoint)

        # Track state change
        track_circuit_breaker_state_change(
            endpoint,
            from_state="closed",
            to_state="open",
        )

        track_circuit_breaker_state(endpoint, "open")

        metrics = get_metrics()
        assert len(metrics) > 0
