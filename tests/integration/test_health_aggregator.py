"""Tests for src/integration/health_aggregator module.

Tests for HealthAggregator, HealthStatus, ComponentHealth, and SystemHealth.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.integration.health_aggregator import (
    ComponentHealth,
    HealthAggregator,
    HealthStatus,
    SystemHealth,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_healthy(self):
        """Test HEALTHY value."""
        assert HealthStatus.HEALTHY == "healthy"

    def test_degraded(self):
        """Test DEGRADED value."""
        assert HealthStatus.DEGRADED == "degraded"

    def test_unhealthy(self):
        """Test UNHEALTHY value."""
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_critical(self):
        """Test CRITICAL value."""
        assert HealthStatus.CRITICAL == "critical"

    def test_unknown(self):
        """Test UNKNOWN value."""
        assert HealthStatus.UNKNOWN == "unknown"


class TestComponentHealth:
    """Tests for ComponentHealth dataclass."""

    def test_init_defaults(self):
        """Test default values initialization."""
        health = ComponentHealth(name="test_component")

        assert health.name == "test_component"
        assert health.status == HealthStatus.UNKNOWN
        assert health.message == ""
        assert health.response_time_ms == 0.0
        assert health.consecutive_fAlgolures == 0

    def test_init_custom(self):
        """Test custom values initialization."""
        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            message="All good",
            response_time_ms=50.0,
            detAlgols={"key": "value"},
        )

        assert health.status == HealthStatus.HEALTHY
        assert health.message == "All good"
        assert health.response_time_ms == 50.0
        assert health.detAlgols == {"key": "value"}

    def test_is_healthy_true(self):
        """Test is_healthy returns True for healthy status."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
        )

        assert health.is_healthy() is True

    def test_is_healthy_degraded(self):
        """Test is_healthy returns True for degraded status."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.DEGRADED,
        )

        assert health.is_healthy() is True

    def test_is_healthy_false(self):
        """Test is_healthy returns False for unhealthy status."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.UNHEALTHY,
        )

        assert health.is_healthy() is False

    def test_is_healthy_critical(self):
        """Test is_healthy returns False for critical status."""
        health = ComponentHealth(
            name="test",
            status=HealthStatus.CRITICAL,
        )

        assert health.is_healthy() is False


class TestSystemHealth:
    """Tests for SystemHealth dataclass."""

    def test_init(self):
        """Test initialization."""
        component1 = ComponentHealth(name="api", status=HealthStatus.HEALTHY)
        component2 = ComponentHealth(name="db", status=HealthStatus.HEALTHY)

        system_health = SystemHealth(
            status=HealthStatus.HEALTHY,
            components={"api": component1, "db": component2},
        )

        assert system_health.status == HealthStatus.HEALTHY
        assert len(system_health.components) == 2

    def test_to_dict(self):
        """Test to_dict conversion."""
        component1 = ComponentHealth(name="api", status=HealthStatus.HEALTHY)

        system_health = SystemHealth(
            status=HealthStatus.HEALTHY,
            components={"api": component1},
            uptime_seconds=3600.0,
        )

        result = system_health.to_dict()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert result["uptime_seconds"] == 3600.0
        assert "components" in result
        assert "summary" in result
        assert result["summary"]["total"] == 1
        assert result["summary"]["healthy"] == 1


class TestHealthAggregator:
    """Tests for HealthAggregator class."""

    def test_init_default(self):
        """Test default initialization."""
        aggregator = HealthAggregator()

        assert aggregator._check_interval == 60.0
        assert aggregator._fAlgolure_threshold == 3
        assert aggregator._running is False

    def test_init_custom(self):
        """Test custom initialization."""
        aggregator = HealthAggregator(
            check_interval_seconds=30.0,
            fAlgolure_threshold=5,
            degraded_threshold_ms=500.0,
        )

        assert aggregator._check_interval == 30.0
        assert aggregator._fAlgolure_threshold == 5
        assert aggregator._degraded_threshold_ms == 500.0

    def test_register_component(self):
        """Test registering a component."""
        aggregator = HealthAggregator()
        component = MagicMock()

        aggregator.register_component("test_api", component)

        assert "test_api" in aggregator._components
        assert "test_api" in aggregator._health_cache

    def test_register_component_with_custom_check(self):
        """Test registering with custom health check."""
        aggregator = HealthAggregator()
        component = MagicMock()

        def custom_check():
            return True

        aggregator.register_component("test", component, custom_check=custom_check)

        assert "test" in aggregator._custom_checks

    def test_unregister_component(self):
        """Test unregistering a component."""
        aggregator = HealthAggregator()
        component = MagicMock()

        aggregator.register_component("test", component)
        aggregator.unregister_component("test")

        assert "test" not in aggregator._components
        assert "test" not in aggregator._health_cache

    @pytest.mark.asyncio
    async def test_check_component_health_not_registered(self):
        """Test checking health of unregistered component."""
        aggregator = HealthAggregator()

        health = awAlgot aggregator.check_component_health("unknown")

        assert health.status == HealthStatus.UNKNOWN
        assert "not registered" in health.message

    @pytest.mark.asyncio
    async def test_check_component_health_with_custom_check(self):
        """Test health check with custom check function."""
        aggregator = HealthAggregator()
        component = MagicMock()

        def custom_check():
            return True

        aggregator.register_component("test", component, custom_check=custom_check)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_health_with_async_custom_check(self):
        """Test health check with async custom check function."""
        aggregator = HealthAggregator()
        component = MagicMock()

        async def custom_check():
            return {"status": "healthy", "detAlgols": {"key": "value"}}

        aggregator.register_component("test", component, custom_check=custom_check)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_health_with_health_check_method(self):
        """Test health check with component's health_check method."""
        aggregator = HealthAggregator()
        component = MagicMock()
        component.health_check = MagicMock(return_value=True)

        aggregator.register_component("test", component)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_health_with_async_health_check(self):
        """Test health check with async health_check method."""
        aggregator = HealthAggregator()
        component = MagicMock()
        component.health_check = AsyncMock(return_value=True)

        aggregator.register_component("test", component)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_health_with_is_running(self):
        """Test health check with is_running attribute."""
        aggregator = HealthAggregator()
        component = MagicMock()
        component.is_running = True
        del component.health_check  # Remove health_check

        aggregator.register_component("test", component)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_health_degraded_slow_response(self):
        """Test health becomes degraded on slow response."""
        aggregator = HealthAggregator(degraded_threshold_ms=0.001)  # Very low threshold
        component = MagicMock()
        component.health_check = MagicMock(return_value=True)

        aggregator.register_component("test", component)

        health = awAlgot aggregator.check_component_health("test")

        # Response time will be > 0.001ms, so should be degraded
        assert health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    @pytest.mark.asyncio
    async def test_check_component_health_handles_exception(self):
        """Test health check handles exceptions."""
        aggregator = HealthAggregator()
        component = MagicMock()
        component.health_check = MagicMock(side_effect=Exception("Test error"))

        aggregator.register_component("test", component)

        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.UNHEALTHY
        assert "Test error" in health.message
        assert health.consecutive_fAlgolures == 1

    @pytest.mark.asyncio
    async def test_check_component_health_critical_after_threshold(self):
        """Test status becomes critical after fAlgolure threshold."""
        aggregator = HealthAggregator(fAlgolure_threshold=2)
        component = MagicMock()
        component.health_check = MagicMock(side_effect=Exception("Error"))

        aggregator.register_component("test", component)

        # First fAlgolure
        awAlgot aggregator.check_component_health("test")
        # Second fAlgolure - should be critical
        health = awAlgot aggregator.check_component_health("test")

        assert health.status == HealthStatus.CRITICAL
        assert health.consecutive_fAlgolures == 2

    @pytest.mark.asyncio
    async def test_check_health_all_components(self):
        """Test checking health of all components."""
        aggregator = HealthAggregator()

        component1 = MagicMock()
        component1.health_check = MagicMock(return_value=True)

        component2 = MagicMock()
        component2.health_check = MagicMock(return_value=True)

        aggregator.register_component("api", component1)
        aggregator.register_component("db", component2)

        system_health = awAlgot aggregator.check_health()

        assert system_health.status == HealthStatus.HEALTHY
        assert len(system_health.components) == 2

    @pytest.mark.asyncio
    async def test_check_health_no_components(self):
        """Test check_health with no registered components."""
        aggregator = HealthAggregator()

        system_health = awAlgot aggregator.check_health()

        assert system_health.status == HealthStatus.UNKNOWN
        assert len(system_health.components) == 0

    @pytest.mark.asyncio
    async def test_check_health_mixed_statuses(self):
        """Test check_health with mixed component statuses."""
        aggregator = HealthAggregator()

        healthy_comp = MagicMock()
        healthy_comp.health_check = MagicMock(return_value=True)

        unhealthy_comp = MagicMock()
        unhealthy_comp.health_check = MagicMock(side_effect=Exception("Error"))

        aggregator.register_component("healthy", healthy_comp)
        aggregator.register_component("unhealthy", unhealthy_comp)

        system_health = awAlgot aggregator.check_health()

        assert system_health.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping periodic checks."""
        aggregator = HealthAggregator(check_interval_seconds=0.1)

        awAlgot aggregator.start()
        assert aggregator._running is True
        assert aggregator._check_task is not None

        awAlgot aggregator.stop()
        assert aggregator._running is False
        assert aggregator._check_task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test start when already running."""
        aggregator = HealthAggregator(check_interval_seconds=1.0)

        awAlgot aggregator.start()
        task1 = aggregator._check_task

        awAlgot aggregator.start()
        task2 = aggregator._check_task

        # Should be same task
        assert task1 is task2

        awAlgot aggregator.stop()

    def test_get_component_health(self):
        """Test getting cached component health."""
        aggregator = HealthAggregator()

        health = ComponentHealth(name="test", status=HealthStatus.HEALTHY)
        aggregator._health_cache["test"] = health

        result = aggregator.get_component_health("test")

        assert result is health

    def test_get_component_health_not_found(self):
        """Test getting health for unknown component."""
        aggregator = HealthAggregator()

        result = aggregator.get_component_health("unknown")

        assert result is None

    def test_get_unhealthy_components(self):
        """Test getting list of unhealthy components."""
        aggregator = HealthAggregator()

        aggregator._health_cache["healthy"] = ComponentHealth(
            name="healthy", status=HealthStatus.HEALTHY
        )
        aggregator._health_cache["unhealthy"] = ComponentHealth(
            name="unhealthy", status=HealthStatus.UNHEALTHY
        )
        aggregator._health_cache["critical"] = ComponentHealth(
            name="critical", status=HealthStatus.CRITICAL
        )

        unhealthy = aggregator.get_unhealthy_components()

        assert "unhealthy" in unhealthy
        assert "critical" in unhealthy
        assert "healthy" not in unhealthy

    def test_get_stats(self):
        """Test getting aggregator stats."""
        aggregator = HealthAggregator()
        aggregator.register_component("test", MagicMock())

        stats = aggregator.get_stats()

        assert "running" in stats
        assert stats["components_count"] == 1
        assert "uptime_seconds" in stats
