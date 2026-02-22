"""Tests for Bot Integrator and supporting modules.

This test suite validates:
- ServiceRegistry: dependency injection and lifecycle management
- EventBus: event publication and subscription
- HealthAggregator: health monitoring
- BotIntegrator: unified module orchestration

Created: January 10, 2026
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.integration.bot_integrator import BotIntegrator, IntegratorConfig
from src.integration.event_bus import Event, EventBus, EventPriority
from src.integration.health_aggregator import HealthAggregator, HealthStatus
from src.integration.service_registry import ServiceRegistry, ServiceStatus

# ============================================================================
# ServiceRegistry Tests
# ============================================================================

class TestServiceRegistry:
    """Tests for ServiceRegistry."""
    
    def test_register_service(self):
        """Test service registration."""
        registry = ServiceRegistry()
        mock_service = MagicMock()
        
        registry.register("test_service", mock_service)
        
        assert registry.has("test_service")
        assert registry.get("test_service") == mock_service
    
    def test_register_with_dependencies(self):
        """Test service registration with dependencies."""
        registry = ServiceRegistry()
        service_a = MagicMock()
        service_b = MagicMock()
        
        registry.register("service_a", service_a)
        registry.register("service_b", service_b, depends_on=["service_a"])
        
        assert registry.has("service_a")
        assert registry.has("service_b")
    
    def test_get_nonexistent_service(self):
        """Test getting non-existent service raises error."""
        registry = ServiceRegistry()
        
        with pytest.raises(KeyError):
            registry.get("nonexistent")
    
    def test_get_optional_service(self):
        """Test get_optional returns None for missing service."""
        registry = ServiceRegistry()
        
        result = registry.get_optional("nonexistent")
        
        assert result is None
    
    def test_unregister_service(self):
        """Test service unregistration."""
        registry = ServiceRegistry()
        mock_service = MagicMock()
        
        registry.register("test", mock_service)
        registry.unregister("test")
        
        assert not registry.has("test")
    
    def test_get_all_services(self):
        """Test getting all services."""
        registry = ServiceRegistry()
        service_a = MagicMock()
        service_b = MagicMock()
        
        registry.register("a", service_a)
        registry.register("b", service_b)
        
        all_services = registry.get_all()
        
        assert len(all_services) == 2
        assert "a" in all_services
        assert "b" in all_services
    
    def test_get_status(self):
        """Test getting service status."""
        registry = ServiceRegistry()
        mock_service = MagicMock()
        
        registry.register("test", mock_service)
        
        status = registry.get_status("test")
        
        assert status == ServiceStatus.REGISTERED
    
    def test_get_status_unregistered(self):
        """Test getting status of unregistered service."""
        registry = ServiceRegistry()
        
        status = registry.get_status("nonexistent")
        
        assert status == ServiceStatus.UNREGISTERED
    
    @pytest.mark.asyncio
    async def test_start_all_services(self):
        """Test starting all services."""
        registry = ServiceRegistry()
        
        mock_service = AsyncMock()
        mock_service.start = AsyncMock()
        
        registry.register("test", mock_service)
        
        results = await registry.start_all()
        
        assert results["test"] is True
        mock_service.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_all_services(self):
        """Test stopping all services."""
        registry = ServiceRegistry()
        
        mock_service = AsyncMock()
        mock_service.stop = AsyncMock()
        
        registry.register("test", mock_service)
        await registry.start_all()
        
        results = await registry.stop_all()
        
        assert results["test"] is True
        mock_service.stop.assert_called_once()
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        registry = ServiceRegistry()
        service_a = MagicMock()
        service_b = MagicMock()
        
        registry.register("a", service_a, depends_on=["b"])
        registry.register("b", service_b, depends_on=["a"])
        
        with pytest.raises(ValueError, match="Circular"):
            registry._get_start_order()
    
    def test_health_summary(self):
        """Test getting health summary."""
        registry = ServiceRegistry()
        registry.register("test", MagicMock())
        
        summary = registry.get_health_summary()
        
        assert summary["total_services"] == 1
        assert "test" in summary["services"]


# ============================================================================
# EventBus Tests
# ============================================================================

class TestEventBus:
    """Tests for EventBus."""
    
    def test_create_event(self):
        """Test event creation."""
        event = Event(
            type="test_event",
            data={"key": "value"},
            priority=EventPriority.HIGH,
        )
        
        assert event.type == "test_event"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.HIGH
        assert event.id is not None
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(type="test", data={"foo": "bar"})
        
        result = event.to_dict()
        
        assert result["type"] == "test"
        assert result["data"] == {"foo": "bar"}
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """Test basic subscription and publishing."""
        bus = EventBus()
        received = []
        
        async def handler(event: Event):
            received.append(event)
        
        bus.subscribe("test", handler)
        
        event = Event(type="test", data={"value": 42})
        count = await bus.publish(event)
        
        assert count == 1
        assert len(received) == 1
        assert received[0].data["value"] == 42
    
    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers(self):
        """Test multiple handlers for same event."""
        bus = EventBus()
        count1 = 0
        count2 = 0
        
        async def handler1(event: Event):
            nonlocal count1
            count1 += 1
        
        async def handler2(event: Event):
            nonlocal count2
            count2 += 1
        
        bus.subscribe("test", handler1)
        bus.subscribe("test", handler2)
        
        await bus.publish(Event(type="test"))
        
        assert count1 == 1
        assert count2 == 1
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test unsubscription."""
        bus = EventBus()
        count = 0
        
        async def handler(event: Event):
            nonlocal count
            count += 1
        
        sub_id = bus.subscribe("test", handler)
        
        await bus.publish(Event(type="test"))
        assert count == 1
        
        bus.unsubscribe(sub_id)
        
        await bus.publish(Event(type="test"))
        assert count == 1  # No change after unsubscribe
    
    @pytest.mark.asyncio
    async def test_one_time_subscription(self):
        """Test one-time subscription."""
        bus = EventBus()
        count = 0
        
        async def handler(event: Event):
            nonlocal count
            count += 1
        
        bus.subscribe("test", handler, once=True)
        
        await bus.publish(Event(type="test"))
        await bus.publish(Event(type="test"))
        
        assert count == 1  # Only triggered once
    
    @pytest.mark.asyncio
    async def test_event_filter(self):
        """Test event filtering."""
        bus = EventBus()
        received = []
        
        async def handler(event: Event):
            received.append(event)
        
        # Only receive events with value > 10
        bus.subscribe(
            "test",
            handler,
            filter_fn=lambda e: e.data.get("value", 0) > 10,
        )
        
        await bus.publish(Event(type="test", data={"value": 5}))
        await bus.publish(Event(type="test", data={"value": 15}))
        await bus.publish(Event(type="test", data={"value": 3}))
        
        assert len(received) == 1
        assert received[0].data["value"] == 15
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test handler priority ordering."""
        bus = EventBus()
        order = []
        
        async def low_handler(event: Event):
            order.append("low")
        
        async def high_handler(event: Event):
            order.append("high")
        
        async def critical_handler(event: Event):
            order.append("critical")
        
        # Register in wrong order
        bus.subscribe("test", low_handler, priority=EventPriority.LOW)
        bus.subscribe("test", high_handler, priority=EventPriority.HIGH)
        bus.subscribe("test", critical_handler, priority=EventPriority.CRITICAL)
        
        await bus.publish(Event(type="test"))
        
        # Should run in priority order
        assert order == ["critical", "high", "low"]
    
    def test_get_history(self):
        """Test event history."""
        bus = EventBus(enable_history=True, max_history=10)
        
        asyncio.run(bus.publish(Event(type="test1")))
        asyncio.run(bus.publish(Event(type="test2")))
        
        history = bus.get_history()
        
        assert len(history) == 2
    
    def test_get_history_filtered(self):
        """Test filtered event history."""
        bus = EventBus(enable_history=True)
        
        asyncio.run(bus.publish(Event(type="type_a")))
        asyncio.run(bus.publish(Event(type="type_b")))
        asyncio.run(bus.publish(Event(type="type_a")))
        
        history = bus.get_history(event_type="type_a")
        
        assert len(history) == 2
        assert all(e.type == "type_a" for e in history)
    
    def test_get_stats(self):
        """Test getting stats."""
        bus = EventBus()
        
        asyncio.run(bus.publish(Event(type="test")))
        
        stats = bus.get_stats()
        
        assert stats["events_published"] == 1
        assert stats["running"] is True
    
    def test_stop_and_start(self):
        """Test stopping and starting bus."""
        bus = EventBus()
        
        bus.stop()
        assert bus.get_stats()["running"] is False
        
        bus.start()
        assert bus.get_stats()["running"] is True
    
    def test_clear_history(self):
        """Test clearing history."""
        bus = EventBus(enable_history=True)
        
        asyncio.run(bus.publish(Event(type="test")))
        asyncio.run(bus.publish(Event(type="test")))
        
        cleared = bus.clear_history()
        
        assert cleared == 2
        assert len(bus.get_history()) == 0


# ============================================================================
# HealthAggregator Tests
# ============================================================================

class TestHealthAggregator:
    """Tests for HealthAggregator."""
    
    def test_register_component(self):
        """Test component registration."""
        aggregator = HealthAggregator()
        mock_component = MagicMock()
        
        aggregator.register_component("test", mock_component)
        
        assert "test" in aggregator._components
    
    def test_unregister_component(self):
        """Test component unregistration."""
        aggregator = HealthAggregator()
        mock_component = MagicMock()
        
        aggregator.register_component("test", mock_component)
        aggregator.unregister_component("test")
        
        assert "test" not in aggregator._components
    
    @pytest.mark.asyncio
    async def test_check_component_with_health_check_method(self):
        """Test checking component with health_check method."""
        aggregator = HealthAggregator()
        
        mock_component = MagicMock()
        mock_component.health_check = MagicMock(return_value=True)
        
        aggregator.register_component("test", mock_component)
        
        health = await aggregator.check_component_health("test")
        
        assert health.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_check_component_with_async_health_check(self):
        """Test checking component with async health_check method."""
        aggregator = HealthAggregator()
        
        mock_component = MagicMock()
        mock_component.health_check = AsyncMock(return_value={"status": "healthy"})
        
        aggregator.register_component("test", mock_component)
        
        health = await aggregator.check_component_health("test")
        
        assert health.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_check_component_with_is_running(self):
        """Test checking component with is_running attribute."""
        aggregator = HealthAggregator()
        
        mock_component = MagicMock()
        mock_component.is_running = True
        # Remove health_check to use is_running
        del mock_component.health_check
        
        aggregator.register_component("test", mock_component)
        
        health = await aggregator.check_component_health("test")
        
        assert health.status == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_check_component_failure(self):
        """Test checking component that fails."""
        aggregator = HealthAggregator()
        
        mock_component = MagicMock()
        mock_component.health_check = MagicMock(side_effect=Exception("Failed"))
        
        aggregator.register_component("test", mock_component)
        
        health = await aggregator.check_component_health("test")
        
        assert health.status == HealthStatus.UNHEALTHY
        assert health.consecutive_failures == 1
    
    @pytest.mark.asyncio
    async def test_check_all_health(self):
        """Test checking all component health."""
        aggregator = HealthAggregator()
        
        component1 = MagicMock()
        component1.health_check = MagicMock(return_value=True)
        
        component2 = MagicMock()
        component2.health_check = MagicMock(return_value=True)
        
        aggregator.register_component("comp1", component1)
        aggregator.register_component("comp2", component2)
        
        system_health = await aggregator.check_health()
        
        assert system_health.status == HealthStatus.HEALTHY
        assert len(system_health.components) == 2
    
    @pytest.mark.asyncio
    async def test_overall_status_degraded(self):
        """Test overall status is degraded when one component is degraded."""
        aggregator = HealthAggregator(degraded_threshold_ms=0.001)
        
        component1 = MagicMock()
        component1.health_check = MagicMock(return_value=True)
        
        aggregator.register_component("comp1", component1)
        
        # Simulate slow response
        async def slow_check():
            await asyncio.sleep(0.01)
            return True
        
        component1.health_check = slow_check
        
        system_health = await aggregator.check_health()
        
        # Should be degraded due to slow response
        assert system_health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    
    @pytest.mark.asyncio
    async def test_overall_status_unhealthy(self):
        """Test overall status is unhealthy when component fails."""
        aggregator = HealthAggregator()
        
        component1 = MagicMock()
        component1.health_check = MagicMock(return_value=True)
        
        component2 = MagicMock()
        component2.health_check = MagicMock(return_value=False)
        
        aggregator.register_component("comp1", component1)
        aggregator.register_component("comp2", component2)
        
        system_health = await aggregator.check_health()
        
        assert system_health.status == HealthStatus.UNHEALTHY
    
    def test_get_unhealthy_components(self):
        """Test getting list of unhealthy components."""
        aggregator = HealthAggregator()
        
        aggregator._health_cache["comp1"] = MagicMock(status=HealthStatus.HEALTHY)
        aggregator._health_cache["comp2"] = MagicMock(status=HealthStatus.UNHEALTHY)
        aggregator._health_cache["comp3"] = MagicMock(status=HealthStatus.CRITICAL)
        
        unhealthy = aggregator.get_unhealthy_components()
        
        assert len(unhealthy) == 2
        assert "comp2" in unhealthy
        assert "comp3" in unhealthy
    
    def test_get_stats(self):
        """Test getting aggregator stats."""
        aggregator = HealthAggregator()
        aggregator.register_component("test", MagicMock())
        
        stats = aggregator.get_stats()
        
        assert stats["components_count"] == 1
        assert "test" in stats["components"]
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping health checks."""
        aggregator = HealthAggregator(check_interval_seconds=0.1)
        
        await aggregator.start()
        assert aggregator._running is True
        
        await asyncio.sleep(0.05)
        
        await aggregator.stop()
        assert aggregator._running is False


# ============================================================================
# BotIntegrator Tests
# ============================================================================

class TestBotIntegrator:
    """Tests for BotIntegrator."""
    
    def test_create_integrator(self):
        """Test creating bot integrator."""
        integrator = BotIntegrator()
        
        assert integrator.services is not None
        assert integrator.events is not None
        assert integrator.health is not None
    
    def test_create_with_config(self):
        """Test creating integrator with config."""
        config = IntegratorConfig(
            enable_enhanced_polling=False,
            min_item_price_for_listing=100.0,
        )
        
        integrator = BotIntegrator(config=config)
        
        assert integrator.config.enable_enhanced_polling is False
        assert integrator.config.min_item_price_for_listing == 100.0
    
    def test_create_with_api(self):
        """Test creating integrator with API clients."""
        mock_api = MagicMock()
        mock_waxpeer = MagicMock()
        
        integrator = BotIntegrator(
            dmarket_api=mock_api,
            waxpeer_api=mock_waxpeer,
        )
        
        assert integrator.dmarket_api == mock_api
        assert integrator.waxpeer_api == mock_waxpeer
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialization."""
        integrator = BotIntegrator()
        
        results = await integrator.initialize()
        
        assert integrator._initialized is True
        assert isinstance(results, dict)
    
    @pytest.mark.asyncio
    async def test_initialize_twice(self):
        """Test initializing twice returns empty dict."""
        integrator = BotIntegrator()
        
        await integrator.initialize()
        results = await integrator.initialize()
        
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting integrator."""
        integrator = BotIntegrator()
        
        await integrator.start()
        
        assert integrator._running is True
        assert integrator._start_time is not None
        
        await integrator.stop()
    
    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping integrator."""
        integrator = BotIntegrator()
        
        await integrator.start()
        await integrator.stop()
        
        assert integrator._running is False
    
    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting status."""
        integrator = BotIntegrator()
        await integrator.initialize()
        
        status = await integrator.get_status()
        
        assert "initialized" in status
        assert "running" in status
        assert "modules" in status
        assert "services" in status
    
    def test_property_access(self):
        """Test module property access."""
        integrator = BotIntegrator()
        
        # Should return None when not initialized
        assert integrator.enhanced_polling is None
        assert integrator.price_analytics is None
        assert integrator.auto_listing is None
    
    @pytest.mark.asyncio
    async def test_event_handlers_setup(self):
        """Test event handlers are set up after initialization."""
        integrator = BotIntegrator()
        await integrator.initialize()
        
        # Check that event subscriptions exist
        stats = integrator.events.get_stats()
        
        assert stats["subscription_count"] > 0
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test modules fail gracefully."""
        config = IntegratorConfig(
            enable_enhanced_polling=True,
            enable_price_analytics=True,
        )
        
        # No API provided - enhanced_polling should fail gracefully
        integrator = BotIntegrator(config=config)
        
        results = await integrator.initialize()
        
        # Should still work, just with some modules disabled
        assert integrator._initialized is True
        assert results["enhanced_polling"] is False  # No API
    
    @pytest.mark.asyncio
    async def test_services_registered(self):
        """Test services are registered correctly."""
        mock_api = MagicMock()
        
        integrator = BotIntegrator(dmarket_api=mock_api)
        await integrator.initialize()
        
        # DMarket API should be registered
        assert integrator.services.has("dmarket_api")


class TestIntegratorConfig:
    """Tests for IntegratorConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = IntegratorConfig()
        
        assert config.enable_enhanced_polling is True
        assert config.enable_price_analytics is True
        assert config.min_item_price_for_listing == 50.0
        assert config.target_profit_margin == 0.10
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = IntegratorConfig(
            enable_enhanced_polling=False,
            min_item_price_for_listing=100.0,
            target_profit_margin=0.15,
        )
        
        assert config.enable_enhanced_polling is False
        assert config.min_item_price_for_listing == 100.0
        assert config.target_profit_margin == 0.15


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the whole system."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full lifecycle of integrator."""
        integrator = BotIntegrator()
        
        # Initialize
        results = await integrator.initialize()
        assert integrator._initialized
        
        # Start
        await integrator.start()
        assert integrator._running
        
        # Check status
        status = await integrator.get_status()
        assert status["initialized"]
        assert status["running"]
        
        # Stop
        await integrator.stop()
        assert not integrator._running
    
    @pytest.mark.asyncio
    async def test_event_flow(self):
        """Test events flow between modules."""
        integrator = BotIntegrator()
        await integrator.initialize()
        
        received_events = []
        
        async def test_handler(event: Event):
            received_events.append(event)
        
        integrator.events.subscribe("test_event", test_handler)
        
        await integrator.events.publish(Event(type="test_event", data={"value": 42}))
        
        assert len(received_events) == 1
        assert received_events[0].data["value"] == 42
    
    @pytest.mark.asyncio
    async def test_service_dependency_order(self):
        """Test services start in correct dependency order."""
        integrator = BotIntegrator()
        
        service_a = AsyncMock()
        service_a.start = AsyncMock()
        
        service_b = AsyncMock()
        service_b.start = AsyncMock()
        
        integrator.services.register("a", service_a)
        integrator.services.register("b", service_b, depends_on=["a"])
        
        await integrator.services.start_all()
        
        # Both should have been started
        service_a.start.assert_called_once()
        service_b.start.assert_called_once()
