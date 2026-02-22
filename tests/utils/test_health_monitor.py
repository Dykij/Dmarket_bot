"""Tests for health monitoring module.

Tests cover:
- Individual service health checks (database, redis, API)
- Overall status aggregation
- Heartbeat monitoring loop
- Alert callback system
- FAlgolure threshold handling
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.health_monitor import (
    HealthCheckResult,
    HealthMonitor,
    HeartbeatConfig,
    ServiceStatus,
)


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_status_values(self) -> None:
        """Test that all status values are strings."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.UNKNOWN.value == "unknown"


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating a health check result."""
        result = HealthCheckResult(
            service="test_service",
            status=ServiceStatus.HEALTHY,
            response_time_ms=50.5,
            message="Test message",
        )

        assert result.service == "test_service"
        assert result.status == ServiceStatus.HEALTHY
        assert result.response_time_ms == 50.5
        assert result.message == "Test message"
        assert isinstance(result.last_check, datetime)

    def test_result_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = HealthCheckResult(
            service="test_service",
            status=ServiceStatus.HEALTHY,
            response_time_ms=50.5,
            message="Test message",
            details={"key": "value"},
        )

        result_dict = result.to_dict()

        assert result_dict["service"] == "test_service"
        assert result_dict["status"] == "healthy"
        assert result_dict["response_time_ms"] == 50.5
        assert result_dict["message"] == "Test message"
        assert result_dict["details"] == {"key": "value"}
        assert "last_check" in result_dict

    def test_result_default_values(self) -> None:
        """Test default values in result."""
        result = HealthCheckResult(
            service="test",
            status=ServiceStatus.HEALTHY,
            response_time_ms=10.0,
        )

        assert result.message == ""
        assert result.details == {}


class TestHeartbeatConfig:
    """Tests for HeartbeatConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = HeartbeatConfig()

        assert config.interval_seconds == 30
        assert config.timeout_seconds == 10
        assert config.failure_threshold == 3
        assert config.recovery_threshold == 2

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = HeartbeatConfig(
            interval_seconds=60,
            timeout_seconds=15,
            failure_threshold=5,
            recovery_threshold=3,
        )

        assert config.interval_seconds == 60
        assert config.timeout_seconds == 15
        assert config.failure_threshold == 5
        assert config.recovery_threshold == 3


class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    @pytest.fixture()
    def mock_database(self) -> MagicMock:
        """Create mock database manager."""
        db = MagicMock()
        db.get_db_status = AsyncMock(return_value={"pool_size": 5, "connected": True})
        return db

    @pytest.fixture()
    def mock_redis(self) -> MagicMock:
        """Create mock Redis cache."""
        redis = MagicMock()
        redis.health_check = AsyncMock(
            return_value={"redis_ping": True, "connected": True}
        )
        return redis

    @pytest.fixture()
    def monitor(self, mock_database: MagicMock, mock_redis: MagicMock) -> HealthMonitor:
        """Create health monitor with mocks."""
        return HealthMonitor(
            database=mock_database,
            redis_cache=mock_redis,
            telegram_bot_token="test_token",
            config=HeartbeatConfig(interval_seconds=1, failure_threshold=2),
        )

    @pytest.mark.asyncio()
    async def test_check_database_healthy(
        self, monitor: HealthMonitor, mock_database: MagicMock
    ) -> None:
        """Test database health check when healthy."""
        result = await monitor.check_database()

        assert result.service == "database"
        assert result.status == ServiceStatus.HEALTHY
        assert result.message == "Database connection OK"
        assert result.response_time_ms >= 0  # Can be 0 if instant
        mock_database.get_db_status.assert_called_once()

    @pytest.mark.asyncio()
    async def test_check_database_unhealthy(
        self, monitor: HealthMonitor, mock_database: MagicMock
    ) -> None:
        """Test database health check when unhealthy."""
        mock_database.get_db_status = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await monitor.check_database()

        assert result.service == "database"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "Connection failed" in result.message

    @pytest.mark.asyncio()
    async def test_check_database_not_configured(self) -> None:
        """Test database health check when not configured."""
        monitor = HealthMonitor()

        result = await monitor.check_database()

        assert result.service == "database"
        assert result.status == ServiceStatus.UNKNOWN
        assert "not configured" in result.message

    @pytest.mark.asyncio()
    async def test_check_redis_healthy(
        self, monitor: HealthMonitor, mock_redis: MagicMock
    ) -> None:
        """Test Redis health check when healthy."""
        result = await monitor.check_redis()

        assert result.service == "redis"
        assert result.status == ServiceStatus.HEALTHY
        assert result.message == "Redis connection OK"
        mock_redis.health_check.assert_called_once()

    @pytest.mark.asyncio()
    async def test_check_redis_degraded(
        self, monitor: HealthMonitor, mock_redis: MagicMock
    ) -> None:
        """Test Redis health check when degraded (using memory cache)."""
        mock_redis.health_check = AsyncMock(return_value={"redis_ping": False})

        result = await monitor.check_redis()

        assert result.service == "redis"
        assert result.status == ServiceStatus.DEGRADED
        assert "memory cache" in result.message

    @pytest.mark.asyncio()
    async def test_check_redis_unhealthy(
        self, monitor: HealthMonitor, mock_redis: MagicMock
    ) -> None:
        """Test Redis health check when unhealthy."""
        mock_redis.health_check = AsyncMock(side_effect=Exception("Redis error"))

        result = await monitor.check_redis()

        assert result.service == "redis"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "Redis error" in result.message

    @pytest.mark.asyncio()
    async def test_check_dmarket_api_healthy(self, monitor: HealthMonitor) -> None:
        """Test DMarket API health check when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_dmarket_api()

        assert result.service == "dmarket_api"
        assert result.status == ServiceStatus.HEALTHY
        assert "accessible" in result.message

    @pytest.mark.asyncio()
    async def test_check_dmarket_api_rate_limited(self, monitor: HealthMonitor) -> None:
        """Test DMarket API health check when rate limited."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_dmarket_api()

        assert result.service == "dmarket_api"
        assert result.status == ServiceStatus.DEGRADED
        assert "rate limited" in result.message

    @pytest.mark.asyncio()
    async def test_check_dmarket_api_timeout(self, monitor: HealthMonitor) -> None:
        """Test DMarket API health check when timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            result = await monitor.check_dmarket_api()

        assert result.service == "dmarket_api"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "timeout" in result.message.lower()

    @pytest.mark.asyncio()
    async def test_check_telegram_api_healthy(self, monitor: HealthMonitor) -> None:
        """Test Telegram API health check when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"username": "test_bot"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_telegram_api()

        assert result.service == "telegram_api"
        assert result.status == ServiceStatus.HEALTHY
        assert "accessible" in result.message

    @pytest.mark.asyncio()
    async def test_check_telegram_api_not_configured(self) -> None:
        """Test Telegram API health check when not configured."""
        monitor = HealthMonitor()

        result = await monitor.check_telegram_api()

        assert result.service == "telegram_api"
        assert result.status == ServiceStatus.UNKNOWN
        assert "not configured" in result.message

    @pytest.mark.asyncio()
    async def test_run_all_checks(self, monitor: HealthMonitor) -> None:
        """Test running all health checks."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "result": {}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await monitor.run_all_checks()

        assert "database" in results
        assert "redis" in results
        assert "dmarket_api" in results
        assert "telegram_api" in results

    @pytest.mark.asyncio()
    async def test_get_overall_status_healthy(self, monitor: HealthMonitor) -> None:
        """Test overall status when all services healthy."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
            "redis": HealthCheckResult("redis", ServiceStatus.HEALTHY, 5.0),
        }

        status = monitor.get_overall_status()
        assert status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio()
    async def test_get_overall_status_unhealthy(self, monitor: HealthMonitor) -> None:
        """Test overall status when any service unhealthy."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
            "redis": HealthCheckResult("redis", ServiceStatus.UNHEALTHY, 5.0),
        }

        status = monitor.get_overall_status()
        assert status == ServiceStatus.UNHEALTHY

    @pytest.mark.asyncio()
    async def test_get_overall_status_degraded(self, monitor: HealthMonitor) -> None:
        """Test overall status when any service degraded."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
            "redis": HealthCheckResult("redis", ServiceStatus.DEGRADED, 5.0),
        }

        status = monitor.get_overall_status()
        assert status == ServiceStatus.DEGRADED

    @pytest.mark.asyncio()
    async def test_get_overall_status_unknown(self, monitor: HealthMonitor) -> None:
        """Test overall status when no checks performed."""
        status = monitor.get_overall_status()
        assert status == ServiceStatus.UNKNOWN

    def test_get_status_summary(self, monitor: HealthMonitor) -> None:
        """Test getting status summary."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
        }
        monitor._failure_counts = {"database": 0}

        summary = monitor.get_status_summary()

        assert "overall_status" in summary
        assert "timestamp" in summary
        assert "services" in summary
        assert "failure_counts" in summary
        assert "database" in summary["services"]

    @pytest.mark.asyncio()
    async def test_alert_callback_triggered(self, monitor: HealthMonitor) -> None:
        """Test that alert callbacks are triggered."""
        alert_called = False
        alert_result: HealthCheckResult | None = None

        async def alert_callback(result: HealthCheckResult) -> None:
            nonlocal alert_called, alert_result
            alert_called = True
            alert_result = result

        monitor.register_alert_callback(alert_callback)

        # Simulate failure threshold reached
        unhealthy_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=100.0,
            message="Test failure",
        )

        # Need to exceed failure threshold (2 in config)
        await monitor._update_service_status("test", unhealthy_result)
        await monitor._update_service_status("test", unhealthy_result)

        assert alert_called
        assert alert_result is not None
        assert alert_result.status == ServiceStatus.UNHEALTHY

    @pytest.mark.asyncio()
    async def test_recovery_alert(self, monitor: HealthMonitor) -> None:
        """Test that recovery alerts are triggered."""
        alerts: list[HealthCheckResult] = []

        async def alert_callback(result: HealthCheckResult) -> None:
            alerts.append(result)

        monitor.register_alert_callback(alert_callback)
        monitor._failure_counts["test"] = 3  # Service was unhealthy

        # Simulate recovery
        healthy_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.HEALTHY,
            response_time_ms=50.0,
        )

        await monitor._update_service_status("test", healthy_result)
        await monitor._update_service_status("test", healthy_result)

        # Should have recovery alert
        assert len(alerts) == 1
        assert alerts[0].status == ServiceStatus.HEALTHY
        assert "recovered" in alerts[0].message

    @pytest.mark.asyncio()
    async def test_start_stop_heartbeat(self, monitor: HealthMonitor) -> None:
        """Test starting and stopping heartbeat."""
        with patch.object(monitor, "run_all_checks", new_callable=AsyncMock):
            await monitor.start_heartbeat()

            assert monitor.is_running
            assert monitor._heartbeat_task is not None

            await asyncio.sleep(0.1)  # Let heartbeat run briefly

            await monitor.stop_heartbeat()

            assert not monitor.is_running

    @pytest.mark.asyncio()
    async def test_heartbeat_already_running(self, monitor: HealthMonitor) -> None:
        """Test starting heartbeat when already running."""
        with patch.object(monitor, "run_all_checks", new_callable=AsyncMock):
            await monitor.start_heartbeat()

            # Try to start agAlgon
            await monitor.start_heartbeat()

            # Should still only have one task
            assert monitor.is_running

            await monitor.stop_heartbeat()

    def test_last_results_property(self, monitor: HealthMonitor) -> None:
        """Test last_results property returns copy."""
        monitor._last_results = {
            "test": HealthCheckResult("test", ServiceStatus.HEALTHY, 10.0),
        }

        results = monitor.last_results

        # Should be a copy - modifying it shouldn't affect original
        new_result = HealthCheckResult("new", ServiceStatus.HEALTHY, 0.0)
        results["new_key"] = new_result
        assert "new_key" not in monitor._last_results


class TestHealthMonitorIntegration:
    """Integration tests for HealthMonitor."""

    @pytest.mark.asyncio()
    async def test_full_health_check_cycle(self) -> None:
        """Test a full health check cycle with mocks."""
        mock_db = MagicMock()
        mock_db.get_db_status = AsyncMock(return_value={"connected": True})

        mock_redis = MagicMock()
        mock_redis.health_check = AsyncMock(return_value={"redis_ping": True})

        monitor = HealthMonitor(
            database=mock_db,
            redis_cache=mock_redis,
            config=HeartbeatConfig(failure_threshold=1),
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "result": {}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await monitor.run_all_checks()

        # All checks should complete
        assert len(results) == 4

        # Summary should be avAlgolable
        summary = monitor.get_status_summary()
        assert summary["overall_status"] in {
            "healthy",
            "degraded",
            "unhealthy",
            "unknown",
        }


class TestHealthMonitorExtended:
    """Extended tests for HealthMonitor to improve coverage."""

    @pytest.fixture()
    def mock_database(self) -> MagicMock:
        """Create mock database manager."""
        db = MagicMock()
        db.get_db_status = AsyncMock(return_value={"pool_size": 5, "connected": True})
        return db

    @pytest.fixture()
    def mock_redis(self) -> MagicMock:
        """Create mock Redis cache."""
        redis = MagicMock()
        redis.health_check = AsyncMock(
            return_value={"redis_ping": True, "connected": True}
        )
        return redis

    @pytest.fixture()
    def monitor(self, mock_database: MagicMock, mock_redis: MagicMock) -> HealthMonitor:
        """Create health monitor with mocks."""
        return HealthMonitor(
            database=mock_database,
            redis_cache=mock_redis,
            telegram_bot_token="test_token",
            config=HeartbeatConfig(interval_seconds=1, failure_threshold=2),
        )

    @pytest.mark.asyncio()
    async def test_check_redis_not_configured(self) -> None:
        """Test Redis health check when not configured."""
        monitor = HealthMonitor()

        result = await monitor.check_redis()

        assert result.service == "redis"
        assert result.status == ServiceStatus.UNKNOWN
        assert "not configured" in result.message

    @pytest.mark.asyncio()
    async def test_check_dmarket_api_error(self, monitor: HealthMonitor) -> None:
        """Test DMarket API health check when error occurs."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_dmarket_api()

        assert result.service == "dmarket_api"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "500" in result.message

    @pytest.mark.asyncio()
    async def test_check_dmarket_api_exception(self, monitor: HealthMonitor) -> None:
        """Test DMarket API health check when exception occurs."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await monitor.check_dmarket_api()

        assert result.service == "dmarket_api"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "Network error" in result.message

    @pytest.mark.asyncio()
    async def test_check_telegram_api_error(self, monitor: HealthMonitor) -> None:
        """Test Telegram API health check when error occurs."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_telegram_api()

        assert result.service == "telegram_api"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "401" in result.message

    @pytest.mark.asyncio()
    async def test_check_telegram_api_not_ok(self, monitor: HealthMonitor) -> None:
        """Test Telegram API health check when response not ok."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "description": "Invalid token"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await monitor.check_telegram_api()

        assert result.service == "telegram_api"
        assert result.status == ServiceStatus.UNHEALTHY

    @pytest.mark.asyncio()
    async def test_check_telegram_api_exception(self, monitor: HealthMonitor) -> None:
        """Test Telegram API health check when exception occurs."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            result = await monitor.check_telegram_api()

        assert result.service == "telegram_api"
        assert result.status == ServiceStatus.UNHEALTHY
        assert "Connection refused" in result.message

    @pytest.mark.asyncio()
    async def test_sync_alert_callback(self, monitor: HealthMonitor) -> None:
        """Test that sync alert callbacks work."""
        sync_callback_called = False

        def sync_callback(result: HealthCheckResult) -> None:
            nonlocal sync_callback_called
            sync_callback_called = True

        monitor.register_alert_callback(sync_callback)

        # Simulate failure threshold reached
        unhealthy_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=100.0,
            message="Test failure",
        )

        await monitor._update_service_status("test", unhealthy_result)
        await monitor._update_service_status("test", unhealthy_result)

        assert sync_callback_called

    @pytest.mark.asyncio()
    async def test_alert_callback_with_exception(self, monitor: HealthMonitor) -> None:
        """Test that exceptions in alert callbacks are handled."""

        def failing_callback(result: HealthCheckResult) -> None:
            raise ValueError("Callback error")

        monitor.register_alert_callback(failing_callback)

        # Simulate failure threshold reached - should not raise
        unhealthy_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.UNHEALTHY,
            response_time_ms=100.0,
        )

        await monitor._update_service_status("test", unhealthy_result)
        await monitor._update_service_status("test", unhealthy_result)

        # Should complete without rAlgosing
        assert True

    @pytest.mark.asyncio()
    async def test_heartbeat_loop_with_error(self, monitor: HealthMonitor) -> None:
        """Test heartbeat loop handles errors gracefully."""
        call_count = 0

        async def failing_check() -> dict[str, HealthCheckResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First check failed")
            return {}

        with patch.object(monitor, "run_all_checks", side_effect=failing_check):
            await monitor.start_heartbeat()
            await asyncio.sleep(0.2)  # Let loop run
            await monitor.stop_heartbeat()

        # Loop should have continued despite error
        assert call_count >= 1

    @pytest.mark.asyncio()
    async def test_get_overall_status_with_unknown(
        self, monitor: HealthMonitor
    ) -> None:
        """Test overall status when some services are unknown."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
            "redis": HealthCheckResult("redis", ServiceStatus.UNKNOWN, 5.0),
        }

        status = monitor.get_overall_status()
        assert status == ServiceStatus.UNKNOWN

    @pytest.mark.asyncio()
    async def test_update_service_status_healthy_resets_failure_count(
        self, monitor: HealthMonitor
    ) -> None:
        """Test that healthy status resets failure count after recovery threshold."""
        monitor._failure_counts["test"] = 5
        monitor._success_counts["test"] = 0

        healthy_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.HEALTHY,
            response_time_ms=50.0,
        )

        # First healthy update
        await monitor._update_service_status("test", healthy_result)
        assert monitor._success_counts["test"] == 1

        # Second healthy update - should trigger recovery
        await monitor._update_service_status("test", healthy_result)
        assert monitor._failure_counts["test"] == 0

    @pytest.mark.asyncio()
    async def test_get_status_summary_includes_success_counts(
        self, monitor: HealthMonitor
    ) -> None:
        """Test that status summary includes success counts."""
        monitor._last_results = {
            "database": HealthCheckResult("database", ServiceStatus.HEALTHY, 10.0),
        }
        monitor._failure_counts = {"database": 0}
        monitor._success_counts = {"database": 5}

        summary = monitor.get_status_summary()

        assert "success_counts" in summary
        assert summary["success_counts"]["database"] == 5

    @pytest.mark.asyncio()
    async def test_stop_heartbeat_when_not_running(
        self, monitor: HealthMonitor
    ) -> None:
        """Test stopping heartbeat when not running."""
        # Should not raise error
        await monitor.stop_heartbeat()
        assert not monitor.is_running

    def test_monitor_without_config(self) -> None:
        """Test monitor creation without explicit config."""
        monitor = HealthMonitor()
        assert monitor.config is not None
        assert monitor.config.interval_seconds == 30  # Default value
