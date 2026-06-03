"""Tests for src/integration/service_registry module.

Tests for ServiceRegistry, ServiceStatus, and ServiceInfo.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.integration.service_registry import (
    ServiceInfo,
    ServiceRegistry,
    ServiceStatus,
)


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_unregistered(self):
        """Test UNREGISTERED value."""
        assert ServiceStatus.UNREGISTERED == "unregistered"

    def test_registered(self):
        """Test REGISTERED value."""
        assert ServiceStatus.REGISTERED == "registered"

    def test_initializing(self):
        """Test INITIALIZING value."""
        assert ServiceStatus.INITIALIZING == "initializing"

    def test_running(self):
        """Test RUNNING value."""
        assert ServiceStatus.RUNNING == "running"

    def test_stopping(self):
        """Test STOPPING value."""
        assert ServiceStatus.STOPPING == "stopping"

    def test_stopped(self):
        """Test STOPPED value."""
        assert ServiceStatus.STOPPED == "stopped"

    def test_error(self):
        """Test ERROR value."""
        assert ServiceStatus.ERROR == "error"


class TestServiceInfo:
    """Tests for ServiceInfo dataclass."""

    def test_init_minimal(self):
        """Test minimal initialization."""
        service = MagicMock()
        info = ServiceInfo(name="test", instance=service)

        assert info.name == "test"
        assert info.instance is service
        assert info.status == ServiceStatus.REGISTERED
        assert info.depends_on == []
        assert info.registered_at is not None
        assert info.started_at is None
        assert info.error is None

    def test_init_with_dependencies(self):
        """Test initialization with dependencies."""
        service = MagicMock()
        info = ServiceInfo(
            name="test",
            instance=service,
            depends_on=["dep1", "dep2"],
        )

        assert info.depends_on == ["dep1", "dep2"]


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_init(self):
        """Test initialization."""
        registry = ServiceRegistry()

        assert registry._services == {}
        assert registry._factories == {}
        assert registry._started is False

    def test_register_service(self):
        """Test registering a service."""
        registry = ServiceRegistry()
        service = MagicMock()

        registry.register("test_service", service)

        assert "test_service" in registry._services
        assert registry._services["test_service"].instance is service

    def test_register_service_with_dependencies(self):
        """Test registering with dependencies."""
        registry = ServiceRegistry()
        service = MagicMock()

        registry.register("test", service, depends_on=["dep1", "dep2"])

        assert registry._services["test"].depends_on == ["dep1", "dep2"]

    def test_register_replaces_existing(self):
        """Test registering overwrites existing service."""
        registry = ServiceRegistry()
        service1 = MagicMock()
        service2 = MagicMock()

        registry.register("test", service1)
        registry.register("test", service2)

        assert registry._services["test"].instance is service2

    def test_register_factory(self):
        """Test registering a factory."""
        registry = ServiceRegistry()

        def factory():
            return MagicMock()

        registry.register_factory("test", factory, depends_on=["dep1"])

        assert "test" in registry._factories
        assert "test" in registry._services
        assert registry._services["test"].status == ServiceStatus.UNREGISTERED

    def test_get_service(self):
        """Test getting a registered service."""
        registry = ServiceRegistry()
        service = MagicMock()

        registry.register("test", service)
        retrieved = registry.get("test")

        assert retrieved is service

    def test_get_service_not_found(self):
        """Test getting unregistered service raises KeyError."""
        registry = ServiceRegistry()

        with pytest.raises(KeyError, match="Service not found"):
            registry.get("unknown")

    def test_get_lazy_initializes_factory(self):
        """Test get initializes service from factory."""
        registry = ServiceRegistry()
        service = MagicMock()

        def factory():
            return service

        registry.register_factory("test", factory)

        # Initial status is unregistered
        assert registry._services["test"].status == ServiceStatus.UNREGISTERED

        retrieved = registry.get("test")

        assert retrieved is service
        assert registry._services["test"].status == ServiceStatus.REGISTERED

    def test_get_optional_found(self):
        """Test get_optional returns service when found."""
        registry = ServiceRegistry()
        service = MagicMock()

        registry.register("test", service)
        result = registry.get_optional("test")

        assert result is service

    def test_get_optional_not_found(self):
        """Test get_optional returns None when not found."""
        registry = ServiceRegistry()

        result = registry.get_optional("unknown")

        assert result is None

    def test_has_true(self):
        """Test has returns True for registered service."""
        registry = ServiceRegistry()
        registry.register("test", MagicMock())

        assert registry.has("test") is True

    def test_has_false(self):
        """Test has returns False for unregistered service."""
        registry = ServiceRegistry()

        assert registry.has("unknown") is False

    def test_unregister(self):
        """Test unregistering a service."""
        registry = ServiceRegistry()
        registry.register("test", MagicMock())

        registry.unregister("test")

        assert "test" not in registry._services

    def test_unregister_with_factory(self):
        """Test unregistering removes factory too."""
        registry = ServiceRegistry()
        registry.register_factory("test", lambda: MagicMock())

        registry.unregister("test")

        assert "test" not in registry._services
        assert "test" not in registry._factories

    def test_get_all(self):
        """Test getting all services."""
        registry = ServiceRegistry()
        service1 = MagicMock()
        service2 = MagicMock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        all_services = registry.get_all()

        assert len(all_services) == 2
        assert all_services["service1"] is service1
        assert all_services["service2"] is service2

    def test_get_status_registered(self):
        """Test get_status for registered service."""
        registry = ServiceRegistry()
        registry.register("test", MagicMock())

        status = registry.get_status("test")

        assert status == ServiceStatus.REGISTERED

    def test_get_status_unregistered(self):
        """Test get_status for unknown service."""
        registry = ServiceRegistry()

        status = registry.get_status("unknown")

        assert status == ServiceStatus.UNREGISTERED

    def test_get_start_order_no_dependencies(self):
        """Test start order with no dependencies."""
        registry = ServiceRegistry()
        registry.register("a", MagicMock())
        registry.register("b", MagicMock())
        registry.register("c", MagicMock())

        order = registry._get_start_order()

        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}

    def test_get_start_order_with_dependencies(self):
        """Test start order respects dependencies."""
        registry = ServiceRegistry()
        registry.register("app", MagicMock(), depends_on=["db", "cache"])
        registry.register("db", MagicMock())
        registry.register("cache", MagicMock())

        order = registry._get_start_order()

        # db and cache should come before app
        app_idx = order.index("app")
        db_idx = order.index("db")
        cache_idx = order.index("cache")

        assert db_idx < app_idx
        assert cache_idx < app_idx

    def test_get_start_order_circular_dependency(self):
        """Test circular dependency detection."""
        registry = ServiceRegistry()
        registry.register("a", MagicMock(), depends_on=["b"])
        registry.register("b", MagicMock(), depends_on=["c"])
        registry.register("c", MagicMock(), depends_on=["a"])

        with pytest.raises(ValueError, match="Circular dependency"):
            registry._get_start_order()

    @pytest.mark.asyncio
    async def test_start_all(self):
        """Test starting all services."""
        registry = ServiceRegistry()

        service1 = MagicMock()
        service1.start = AsyncMock()

        service2 = MagicMock()
        service2.start = MagicMock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        results = await registry.start_all()

        assert results["service1"] is True
        assert results["service2"] is True
        service1.start.assert_awaited_once()
        service2.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_all_handles_error(self):
        """Test start_all handles service errors."""
        registry = ServiceRegistry()

        service = MagicMock()
        service.start = MagicMock(side_effect=Exception("Start error"))

        registry.register("failing", service)

        results = await registry.start_all()

        assert results["failing"] is False
        assert registry._services["failing"].status == ServiceStatus.ERROR

    @pytest.mark.asyncio
    async def test_stop_all(self):
        """Test stopping all services."""
        registry = ServiceRegistry()

        service1 = MagicMock()
        service1.stop = AsyncMock()

        service2 = MagicMock()
        service2.stop = MagicMock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        results = await registry.stop_all()

        assert results["service1"] is True
        assert results["service2"] is True

    @pytest.mark.asyncio
    async def test_stop_all_handles_error(self):
        """Test stop_all handles service errors."""
        registry = ServiceRegistry()

        service = MagicMock()
        service.stop = MagicMock(side_effect=Exception("Stop error"))

        registry.register("failing", service)

        results = await registry.stop_all()

        assert results["failing"] is False

    def test_get_health_summary(self):
        """Test getting health summary."""
        registry = ServiceRegistry()
        registry.register("service1", MagicMock())
        registry.register("service2", MagicMock())

        summary = registry.get_health_summary()

        assert summary["total_services"] == 2
        assert "services" in summary
        assert "service1" in summary["services"]
        assert "service2" in summary["services"]
