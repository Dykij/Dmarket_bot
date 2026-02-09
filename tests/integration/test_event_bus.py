"""Tests for src/integration/event_bus module.

Tests for EventBus, Event, Subscription, and EventTypes.
"""


import pytest

from src.integration.event_bus import (
    Event,
    EventBus,
    EventPriority,
    EventTypes,
    Subscription,
)


class TestEventPriority:
    """Tests for EventPriority enum."""

    def test_low(self):
        """Test LOW priority."""
        assert EventPriority.LOW == "low"

    def test_normal(self):
        """Test NORMAL priority."""
        assert EventPriority.NORMAL == "normal"

    def test_high(self):
        """Test HIGH priority."""
        assert EventPriority.HIGH == "high"

    def test_critical(self):
        """Test CRITICAL priority."""
        assert EventPriority.CRITICAL == "critical"


class TestEvent:
    """Tests for Event dataclass."""

    def test_init_minimal(self):
        """Test minimal event initialization."""
        event = Event(type="test_event")

        assert event.type == "test_event"
        assert event.data == {}
        assert event.priority == EventPriority.NORMAL
        assert event.id is not None
        assert event.timestamp is not None

    def test_init_full(self):
        """Test full event initialization."""
        event = Event(
            type="test_event",
            data={"key": "value"},
            priority=EventPriority.HIGH,
            source="test_source",
        )

        assert event.type == "test_event"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.HIGH
        assert event.source == "test_source"

    def test_to_dict(self):
        """Test to_dict conversion."""
        event = Event(
            type="test_event",
            data={"key": "value"},
            source="test",
        )

        event_dict = event.to_dict()

        assert event_dict["type"] == "test_event"
        assert event_dict["data"] == {"key": "value"}
        assert event_dict["source"] == "test"
        assert "id" in event_dict
        assert "timestamp" in event_dict


class TestSubscription:
    """Tests for Subscription dataclass."""

    def test_init(self):
        """Test subscription initialization."""
        async def handler(event: Event):
            pass

        sub = Subscription(
            id="sub_1",
            event_type="test_event",
            handler=handler,
        )

        assert sub.id == "sub_1"
        assert sub.event_type == "test_event"
        assert sub.priority == EventPriority.NORMAL
        assert sub.is_async is True
        assert sub.once is False


class TestEventBus:
    """Tests for EventBus class."""

    def test_init_default(self):
        """Test default initialization."""
        bus = EventBus()

        assert bus._running is True
        assert bus._events_published == 0
        assert bus._events_handled == 0

    def test_init_custom(self):
        """Test custom initialization."""
        bus = EventBus(max_history=500, enable_history=False)

        assert bus._max_history == 500
        assert bus._enable_history is False

    def test_subscribe(self):
        """Test subscribing to events."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        sub_id = bus.subscribe("test_event", handler)

        assert sub_id is not None
        assert len(bus._subscriptions["test_event"]) == 1

    def test_subscribe_with_priority(self):
        """Test subscribing with priority."""
        bus = EventBus()

        async def handler1(event: Event):
            pass

        async def handler2(event: Event):
            pass

        bus.subscribe("test", handler1, priority=EventPriority.LOW)
        bus.subscribe("test", handler2, priority=EventPriority.HIGH)

        # Higher priority should be first
        subs = bus._subscriptions["test"]
        assert subs[0].priority == EventPriority.HIGH
        assert subs[1].priority == EventPriority.LOW

    def test_subscribe_with_filter(self):
        """Test subscribing with filter function."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        def filter_fn(event: Event) -> bool:
            return event.data.get("important", False)

        sub_id = bus.subscribe("test", handler, filter_fn=filter_fn)

        assert bus._subscriptions["test"][0].filter_fn is not None

    def test_subscribe_once(self):
        """Test one-time subscription."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        sub_id = bus.subscribe("test", handler, once=True)

        assert bus._subscriptions["test"][0].once is True

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        sub_id = bus.subscribe("test", handler)
        assert len(bus._subscriptions["test"]) == 1

        result = bus.unsubscribe(sub_id)

        assert result is True
        assert len(bus._subscriptions["test"]) == 0

    def test_unsubscribe_not_found(self):
        """Test unsubscribing with invalid ID."""
        bus = EventBus()

        result = bus.unsubscribe("invalid_id")

        assert result is False

    def test_unsubscribe_all(self):
        """Test unsubscribing all handlers for event type."""
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)
        bus.subscribe("test", handler)
        bus.subscribe("test", handler)

        count = bus.unsubscribe_all("test")

        assert count == 3
        assert "test" not in bus._subscriptions

    @pytest.mark.asyncio
    async def test_publish(self):
        """Test publishing events."""
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("test", handler)

        event = Event(type="test", data={"value": 123})
        handlers_run = await bus.publish(event)

        assert handlers_run == 1
        assert len(received) == 1
        assert received[0].data["value"] == 123

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        """Test publishing to event with no subscribers."""
        bus = EventBus()

        event = Event(type="no_subscribers")
        handlers_run = await bus.publish(event)

        assert handlers_run == 0

    @pytest.mark.asyncio
    async def test_publish_not_running(self):
        """Test publishing when bus is stopped."""
        bus = EventBus()
        bus.stop()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)

        event = Event(type="test")
        handlers_run = await bus.publish(event)

        assert handlers_run == 0

    def test_get_stats(self):
        """Test getting bus statistics."""
        bus = EventBus()

        stats = bus.get_stats()

        assert "running" in stats
        assert "events_published" in stats
        assert "events_handled" in stats
        assert "subscription_count" in stats

    def test_stop_and_start(self):
        """Test stopping and starting bus."""
        bus = EventBus()
        assert bus._running is True

        bus.stop()
        assert bus._running is False

        bus.start()
        assert bus._running is True


class TestEventTypes:
    """Tests for EventTypes constants."""

    def test_price_events(self):
        """Test price event types."""
        assert EventTypes.PRICE_UPDATE == "price_update"
        assert EventTypes.PRICE_CHANGE == "price_change"
        assert EventTypes.PRICE_ALERT == "price_alert"

    def test_trading_events(self):
        """Test trading event types."""
        assert EventTypes.TRADE_EXECUTED == "trade_executed"
        assert EventTypes.TRADE_FAILED == "trade_failed"
        assert EventTypes.ORDER_CREATED == "order_created"

    def test_inventory_events(self):
        """Test inventory event types."""
        assert EventTypes.ITEM_LISTED == "item_listed"
        assert EventTypes.ITEM_SOLD == "item_sold"
        assert EventTypes.INVENTORY_UPDATED == "inventory_updated"

    def test_system_events(self):
        """Test system event types."""
        assert EventTypes.SERVICE_STARTED == "service_started"
        assert EventTypes.SERVICE_STOPPED == "service_stopped"
        assert EventTypes.HEALTH_CHECK == "health_check"
