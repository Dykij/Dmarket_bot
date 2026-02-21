"""Tests for reactive_websocket module.

This module tests the ReactiveDMarketWebSocket class and Observable
for real-time market data streaming.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.reactive_websocket import (
    EventType,
    Observable,
    ReactiveDMarketWebSocket,
    Subscription,
    SubscriptionState,
)


class TestObservable:
    """Tests for Observable class."""

    @pytest.fixture
    def observable(self):
        """Create Observable instance."""
        return Observable[dict]()

    @pytest.mark.asyncio
    async def test_emit_sync_observer(self, observable):
        """Test emitting events to sync observer."""
        received = []

        def handler(data):
            received.append(data)

        observable.subscribe(handler)
        awAlgot observable.emit({"test": "data"})

        assert len(received) == 1
        assert received[0] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_emit_async_observer(self, observable):
        """Test emitting events to async observer."""
        received = []

        async def handler(data):
            received.append(data)

        observable.subscribe_async(handler)
        awAlgot observable.emit({"test": "data"})

        assert len(received) == 1
        assert received[0] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_subscribe_multiple_sync(self, observable):
        """Test multiple sync subscribers."""
        received1 = []
        received2 = []

        def handler1(data):
            received1.append(data)

        def handler2(data):
            received2.append(data)

        observable.subscribe(handler1)
        observable.subscribe(handler2)
        awAlgot observable.emit({"event": "test"})

        assert len(received1) == 1
        assert len(received2) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self, observable):
        """Test unsubscribing."""
        received = []

        def handler(data):
            received.append(data)

        observable.subscribe(handler)
        awAlgot observable.emit({"first": True})

        observable.unsubscribe(handler)
        awAlgot observable.emit({"second": True})

        assert len(received) == 1
        assert received[0] == {"first": True}

    def test_clear_observers(self, observable):
        """Test clearing all observers."""
        def sync_handler(data):
            pass

        async def async_handler(data):
            pass

        observable.subscribe(sync_handler)
        observable.subscribe_async(async_handler)

        observable.clear()

        assert len(observable._observers) == 0
        assert len(observable._async_observers) == 0


class TestSubscription:
    """Tests for Subscription class."""

    def test_init(self):
        """Test initialization."""
        subscription = Subscription(
            topic="balance",
            params={"userId": "123"},
        )

        assert subscription.topic == "balance"
        assert subscription.params == {"userId": "123"}
        assert subscription.state == SubscriptionState.IDLE
        assert subscription.event_count == 0
        assert subscription.error_count == 0

    def test_init_without_params(self):
        """Test initialization without params."""
        subscription = Subscription(topic="test")

        assert subscription.topic == "test"
        assert subscription.params == {}

    def test_update_state(self):
        """Test state change."""
        subscription = Subscription(topic="test")

        subscription.update_state(SubscriptionState.ACTIVE)
        assert subscription.state == SubscriptionState.ACTIVE

        subscription.update_state(SubscriptionState.ERROR)
        assert subscription.state == SubscriptionState.ERROR

    def test_record_event(self):
        """Test recording events."""
        subscription = Subscription(topic="test")

        assert subscription.event_count == 0
        assert subscription.last_event_at is None

        subscription.record_event()

        assert subscription.event_count == 1
        assert subscription.last_event_at is not None

    def test_record_error(self):
        """Test recording errors."""
        subscription = Subscription(topic="test")

        assert subscription.error_count == 0

        subscription.record_error()
        subscription.record_error()

        assert subscription.error_count == 2


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self):
        """Test that required event types exist."""
        assert EventType.BALANCE_UPDATE is not None
        assert EventType.ORDER_CREATED is not None
        assert EventType.ORDER_UPDATED is not None
        assert EventType.MARKET_PRICE_CHANGE is not None
        assert EventType.TARGET_MATCHED is not None

    def test_event_type_values(self):
        """Test event type values are strings."""
        assert EventType.BALANCE_UPDATE == "balance:update"
        assert EventType.ORDER_CREATED == "order:created"
        assert EventType.MARKET_PRICE_CHANGE == "market:price"


class TestSubscriptionState:
    """Tests for SubscriptionState enum."""

    def test_states_exist(self):
        """Test that required states exist."""
        assert SubscriptionState.IDLE is not None
        assert SubscriptionState.ACTIVE is not None
        assert SubscriptionState.ERROR is not None
        assert SubscriptionState.SUBSCRIBING is not None

    def test_state_values(self):
        """Test state values are strings."""
        assert SubscriptionState.IDLE == "idle"
        assert SubscriptionState.ACTIVE == "active"
        assert SubscriptionState.ERROR == "error"


class TestReactiveDMarketWebSocket:
    """Tests for ReactiveDMarketWebSocket class."""

    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client."""
        client = MagicMock()
        client.public_key = "test_public_key"
        client.secret_key = "test_secret_key"
        return client

    @pytest.fixture
    def websocket(self, mock_api_client):
        """Create ReactiveDMarketWebSocket instance."""
        return ReactiveDMarketWebSocket(
            api_client=mock_api_client,
            auto_reconnect=True,
            max_reconnect_attempts=5,
        )

    def test_init(self, websocket):
        """Test initialization."""
        assert websocket.is_connected is False
        assert websocket.auto_reconnect is True
        assert websocket.max_reconnect_attempts == 5
        assert websocket.reconnect_attempts == 0

    def test_init_observables(self, websocket):
        """Test observables are initialized."""
        assert EventType.BALANCE_UPDATE in websocket.observables
        assert EventType.ORDER_CREATED in websocket.observables
        assert EventType.MARKET_PRICE_CHANGE in websocket.observables
        assert websocket.all_events is not None
        assert websocket.connection_state is not None

    def test_subscriptions_dict_empty(self, websocket):
        """Test subscriptions dict is initially empty."""
        assert websocket.subscriptions == {}

    def test_ws_endpoint(self, websocket):
        """Test WebSocket endpoint."""
        assert "dmarket.com" in websocket.WS_ENDPOINT
        assert websocket.WS_ENDPOINT.startswith("wss://")

    @pytest.mark.asyncio
    async def test_connect_when_already_connected(self, websocket):
        """Test connect returns True when already connected."""
        websocket.is_connected = True

        result = awAlgot websocket.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect(self, websocket):
        """Test disconnection."""
        # Set up connected state
        websocket.is_connected = True
        websocket.ws_connection = MagicMock()
        websocket.ws_connection.close = AsyncMock()
        websocket.session = MagicMock()
        websocket.session.close = AsyncMock()

        awAlgot websocket.disconnect()

        assert websocket.is_connected is False

    @pytest.mark.asyncio
    async def test_connection_state_observable_emit(self, websocket):
        """Test connection state observable can emit."""
        states_received = []

        def state_handler(is_connected):
            states_received.append(is_connected)

        websocket.connection_state.subscribe(state_handler)

        # Emit events
        awAlgot websocket.connection_state.emit(True)
        assert states_received == [True]

        awAlgot websocket.connection_state.emit(False)
        assert states_received == [True, False]

    @pytest.mark.asyncio
    async def test_all_events_observable_emit(self, websocket):
        """Test all events observable can emit."""
        events_received = []

        def event_handler(event):
            events_received.append(event)

        websocket.all_events.subscribe(event_handler)

        test_event = {"type": "test", "data": {"value": 123}}
        awAlgot websocket.all_events.emit(test_event)

        assert len(events_received) == 1
        assert events_received[0] == test_event

    @pytest.mark.asyncio
    async def test_specific_event_observable(self, websocket):
        """Test subscribing to specific event types."""
        balance_events = []

        def balance_handler(event):
            balance_events.append(event)

        websocket.observables[EventType.BALANCE_UPDATE].subscribe(balance_handler)

        awAlgot websocket.observables[EventType.BALANCE_UPDATE].emit({"balance": 100.0})

        assert len(balance_events) == 1
        assert balance_events[0] == {"balance": 100.0}

    def test_default_auto_reconnect(self, mock_api_client):
        """Test default auto_reconnect is True."""
        ws = ReactiveDMarketWebSocket(api_client=mock_api_client)
        assert ws.auto_reconnect is True

    def test_default_max_reconnect_attempts(self, mock_api_client):
        """Test default max_reconnect_attempts is 10."""
        ws = ReactiveDMarketWebSocket(api_client=mock_api_client)
        assert ws.max_reconnect_attempts == 10
