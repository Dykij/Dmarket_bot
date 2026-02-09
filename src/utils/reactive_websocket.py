"""Reactive WebSocket client for DMarket API.

Provides real-time subscriptions to DMarket events with reactive programming patterns.
Supports balance updates, order events, and market changes with push notifications.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

import aiohttp
from aiohttp import ClientSession

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class EventType(StrEnum):
    """WebSocket event types."""

    BALANCE_UPDATE = "balance:update"
    ORDER_CREATED = "order:created"
    ORDER_UPDATED = "order:updated"
    ORDER_COMPLETED = "order:completed"
    ORDER_CANCELLED = "order:cancelled"
    MARKET_PRICE_CHANGE = "market:price"
    MARKET_ITEM_ADDED = "market:item:added"
    MARKET_ITEM_REMOVED = "market:item:removed"
    TARGET_MATCHED = "target:matched"
    TRADE_COMPLETED = "trade:completed"


class SubscriptionState(StrEnum):
    """Subscription states."""

    IDLE = "idle"
    SUBSCRIBING = "subscribing"
    ACTIVE = "active"
    UNSUBSCRIBING = "unsubscribing"
    ERROR = "error"


class Observable(Generic[T]):  # noqa: UP046
    """Observable pattern implementation for event streams."""

    def __init__(self) -> None:
        """Initialize observable."""
        self._observers: list[Callable[[T], None]] = []
        self._async_observers: list[Callable[[T], Any]] = []

    def subscribe(self, observer: Callable[[T], None]) -> None:
        """Subscribe to events.

        Args:
            observer: Synchronous observer function

        """
        if observer not in self._observers:
            self._observers.append(observer)

    def subscribe_async(self, observer: Callable[[T], Any]) -> None:
        """Subscribe to events with async handler.

        Args:
            observer: Asynchronous observer function

        """
        if observer not in self._async_observers:
            self._async_observers.append(observer)

    def unsubscribe(self, observer: Callable[[T], None]) -> None:
        """Unsubscribe from events.

        Args:
            observer: Observer to remove

        """
        if observer in self._observers:
            self._observers.remove(observer)

    def unsubscribe_async(self, observer: Callable[[T], Any]) -> None:
        """Unsubscribe async observer.

        Args:
            observer: Async observer to remove

        """
        if observer in self._async_observers:
            self._async_observers.remove(observer)

    async def emit(self, data: T) -> None:
        """Emit event to all observers.

        Args:
            data: Event data

        """
        # Call synchronous observers
        for observer in self._observers:
            try:
                observer(data)
            except (TypeError, RuntimeError, ValueError):
                logger.exception("Error in synchronous observer")

        # Call asynchronous observers
        tasks = []
        for observer in self._async_observers:
            try:
                tasks.append(asyncio.create_task(observer(data)))
            except (TypeError, RuntimeError, asyncio.CancelledError):
                logger.exception("Error creating async observer task")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def clear(self) -> None:
        """Clear all observers."""
        self._observers.clear()
        self._async_observers.clear()


class Subscription:
    """Represents an active subscription."""

    def __init__(
        self,
        topic: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize subscription.

        Args:
            topic: Topic name
            params: Subscription parameters

        """
        self.topic = topic
        self.params = params or {}
        self.state = SubscriptionState.IDLE
        self.created_at = datetime.now(UTC)
        self.last_event_at: datetime | None = None
        self.event_count = 0
        self.error_count = 0

    def update_state(self, state: SubscriptionState) -> None:
        """Update subscription state.

        Args:
            state: New state

        """
        self.state = state
        logger.debug("Subscription %s state: %s", self.topic, state)

    def record_event(self) -> None:
        """Record event received."""
        self.event_count += 1
        self.last_event_at = datetime.now(UTC)

    def record_error(self) -> None:
        """Record error."""
        self.error_count += 1


class ReactiveDMarketWebSocket:
    """Reactive WebSocket client for DMarket API.

    Provides event-driven architecture with observables for real-time updates.
    """

    WS_ENDPOINT = "wss://ws.dmarket.com/api/v1/ws"

    def __init__(
        self,
        api_client: DMarketAPI,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
    ) -> None:
        """Initialize reactive WebSocket client.

        Args:
            api_client: DMarket API client for authentication
            auto_reconnect: Auto-reconnect on connection loss
            max_reconnect_attempts: Maximum reconnection attempts

        """
        self.api_client = api_client
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts

        self.session: ClientSession | None = None
        self.ws_connection = None
        self.is_connected = False
        self.reconnect_attempts = 0

        # Observables for different event types
        self.observables: dict[EventType, Observable[dict[str, Any]]] = {
            event_type: Observable() for event_type in EventType
        }

        # Generic observable for all events
        self.all_events = Observable[dict[str, Any]]()

        # Active subscriptions
        self.subscriptions: dict[str, Subscription] = {}

        # Listen task
        self._listen_task: asyncio.Task | None = None

        # Connection state observable
        self.connection_state = Observable[bool]()

    async def connect(self) -> bool:
        """Connect to DMarket WebSocket API.

        Returns:
            True if connection successful

        """
        if self.is_connected:
            logger.info("WebSocket already connected")
            return True

        logger.info("Connecting to DMarket WebSocket (%s)...", self.WS_ENDPOINT)

        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

            self.ws_connection = await self.session.ws_connect(
                self.WS_ENDPOINT,
                timeout=30.0,
                heartbeat=30.0,
            )

            self.is_connected = True
            self.reconnect_attempts = 0

            logger.info("Connected to DMarket WebSocket API")

            # Emit connection state
            await self.connection_state.emit(True)

            # Authenticate
            await self._authenticate()

            # Start listening
            self._listen_task = asyncio.create_task(self._listen())

            # Resubscribe to active subscriptions
            await self._resubscribe_all()

            return True

        except (TimeoutError, aiohttp.ClientError):
            logger.exception("Failed to connect to WebSocket")
            self.is_connected = False
            await self.connection_state.emit(False)
            return False

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        logger.info("Disconnecting from WebSocket...")

        # Cancel listen task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from all
        await self._unsubscribe_all()

        # Close WebSocket
        if self.ws_connection:
            await self.ws_connection.close()
            self.ws_connection = None

        self.is_connected = False
        await self.connection_state.emit(False)

        # Close session
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

        logger.info("Disconnected from WebSocket")

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self.is_connected and self.ws_connection:
            try:
                message = await self.ws_connection.receive()

                if message.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(message.data)

                elif message.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket closed by server")
                    self.is_connected = False
                    await self.connection_state.emit(False)
                    if self.auto_reconnect:
                        await self._attempt_reconnect()
                    break

                elif message.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket error: %s", message.data)
                    self.is_connected = False
                    await self.connection_state.emit(False)
                    if self.auto_reconnect:
                        await self._attempt_reconnect()
                    break

            except asyncio.CancelledError:
                logger.info("Listen task cancelled")
                break
            except (
                aiohttp.ClientError,
                TimeoutError,
                ConnectionError,
            ):
                logger.exception("Error in listen loop")
                if self.auto_reconnect:
                    await self._attempt_reconnect()
                break

    async def _handle_message(self, data: str) -> None:
        """Handle incoming message.

        Args:
            data: Raw message data

        """
        try:
            message = json.loads(data)

            # Extract event type
            event_type_str = message.get("type")
            if not event_type_str:
                logger.warning("Message without type: %s", message)
                return

            # Emit to all events observable
            await self.all_events.emit(message)

            # Check if it's a known event type
            try:
                event_type = EventType(event_type_str)

                # Update subscription stats
                topic = message.get("topic")
                if topic and topic in self.subscriptions:
                    self.subscriptions[topic].record_event()

                # Emit to specific observable
                if event_type in self.observables:
                    await self.observables[event_type].emit(message)

            except ValueError:
                # Unknown event type, still emit to all_events
                logger.debug("Unknown event type: %s", event_type_str)

        except json.JSONDecodeError:
            logger.exception(f"Failed to parse message: {data}")
        except (KeyError, TypeError, AttributeError):
            logger.exception("Error handling message")

    async def _authenticate(self) -> None:
        """Authenticate with WebSocket API."""
        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot authenticate: not connected")
            return

        auth_message = {
            "type": "auth",
            "apiKey": self.api_client.public_key,
            "timestamp": str(int(datetime.now(UTC).timestamp())),
        }

        await self.ws_connection.send_json(auth_message)
        logger.debug("Sent authentication request")

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                "Max reconnect attempts (%s) reached",
                self.max_reconnect_attempts,
            )
            return

        self.reconnect_attempts += 1
        delay = min(2**self.reconnect_attempts, 60)

        logger.info(
            f"Reconnecting in {delay}s (attempt {self.reconnect_attempts}/"
            f"{self.max_reconnect_attempts})"
        )

        await asyncio.sleep(delay)
        await self.connect()

    async def subscribe_to(
        self,
        topic: str,
        params: dict[str, Any] | None = None,
    ) -> Subscription:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            params: Subscription parameters

        Returns:
            Subscription object

        """
        if topic in self.subscriptions:
            logger.warning("Already subscribed to %s", topic)
            return self.subscriptions[topic]

        subscription = Subscription(topic, params)
        subscription.update_state(SubscriptionState.SUBSCRIBING)

        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot subscribe to %s: not connected", topic)
            subscription.update_state(SubscriptionState.ERROR)
            return subscription

        # Build subscription message
        sub_message = {
            "type": "subscribe",
            "topic": topic,
        }
        if params:
            sub_message["params"] = params

        # Send subscription
        await self.ws_connection.send_json(sub_message)
        subscription.update_state(SubscriptionState.ACTIVE)
        self.subscriptions[topic] = subscription

        logger.info("Subscribed to %s", topic)
        return subscription

    async def unsubscribe_from(self, topic: str) -> bool:
        """Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            True if successful

        """
        if topic not in self.subscriptions:
            logger.warning("Not subscribed to %s", topic)
            return False

        subscription = self.subscriptions[topic]
        subscription.update_state(SubscriptionState.UNSUBSCRIBING)

        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot unsubscribe from %s: not connected", topic)
            return False

        # Build unsubscription message
        unsub_message = {
            "type": "unsubscribe",
            "topic": topic,
        }

        # Send unsubscription
        await self.ws_connection.send_json(unsub_message)
        del self.subscriptions[topic]

        logger.info("Unsubscribed from %s", topic)
        return True

    async def _resubscribe_all(self) -> None:
        """Resubscribe to all active subscriptions."""
        if not self.subscriptions:
            return

        logger.info("Resubscribing to %s topics", len(self.subscriptions))

        for topic, subscription in list(self.subscriptions.items()):
            await self.subscribe_to(topic, subscription.params)

    async def _unsubscribe_all(self) -> None:
        """Unsubscribe from all topics."""
        if not self.subscriptions:
            return

        logger.info("Unsubscribing from %s topics", len(self.subscriptions))

        for topic in list(self.subscriptions.keys()):
            await self.unsubscribe_from(topic)

    # Convenience methods for common subscriptions

    async def subscribe_to_balance_updates(self) -> Subscription:
        """Subscribe to balance updates.

        Returns:
            Subscription object

        """
        return await self.subscribe_to("balance:updates")

    async def subscribe_to_order_events(self) -> Subscription:
        """Subscribe to all order events.

        Returns:
            Subscription object

        """
        return await self.subscribe_to("orders:*")

    async def subscribe_to_market_prices(
        self,
        game: str = "csgo",
        items: list[str] | None = None,
    ) -> Subscription:
        """Subscribe to market price changes.

        Args:
            game: Game ID
            items: Optional list of specific item IDs

        Returns:
            Subscription object

        """
        params = {"gameId": game}
        if items:
            params["itemIds"] = items

        return await self.subscribe_to("market:prices", params)

    async def subscribe_to_target_matches(self) -> Subscription:
        """Subscribe to target match events.

        Returns:
            Subscription object

        """
        return await self.subscribe_to("targets:matched")

    def get_subscription_stats(self) -> dict[str, Any]:
        """Get statistics for all subscriptions.

        Returns:
            Statistics dictionary

        """
        return {
            "total_subscriptions": len(self.subscriptions),
            "subscriptions": [
                {
                    "topic": sub.topic,
                    "state": sub.state,
                    "events_received": sub.event_count,
                    "errors": sub.error_count,
                    "last_event_at": (sub.last_event_at.isoformat() if sub.last_event_at else None),
                    "created_at": sub.created_at.isoformat(),
                }
                for sub in self.subscriptions.values()
            ],
        }
