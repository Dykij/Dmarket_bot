"""Event Bus for inter-module communication.

This module provides event-driven communication between different
bot components, enabling loose coupling and reactive architecture.

Usage:
    ```python
    from src.integration.event_bus import EventBus, Event

    bus = EventBus()

    # Subscribe to events
    async def on_price_change(event: Event):
        print(f"Price changed: {event.data}")

    bus.subscribe("price_change", on_price_change)

    # Publish events
    await bus.publish(Event("price_change", {"item": "AWP", "price": 100}))
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class EventPriority(StrEnum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Event:
    """Event data container."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


@dataclass
class Subscription:
    """Event subscription information."""

    id: str
    event_type: str
    handler: Callable[[Event], Coroutine[Any, Any, None]] | Callable[[Event], None]
    priority: EventPriority = EventPriority.NORMAL
    filter_fn: Callable[[Event], bool] | None = None
    is_async: bool = True
    once: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """Event bus for inter-module communication.

    Features:
    - Async event handling
    - Event prioritization
    - Event filtering
    - One-time subscriptions
    - Event history
    - Error handling
    """

    def __init__(
        self,
        max_history: int = 1000,
        enable_history: bool = True,
    ) -> None:
        """Initialize event bus.

        Args:
            max_history: Maximum events to keep in history
            enable_history: Whether to track event history
        """
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = max_history
        self._enable_history = enable_history
        self._lock = asyncio.Lock()
        self._running = True

        # Stats
        self._events_published = 0
        self._events_handled = 0
        self._handler_errors = 0

        logger.info(
            "EventBus initialized",
            max_history=max_history,
            enable_history=enable_history,
        )

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Event], Coroutine[Any, Any, None]] | Callable[[Event], None],
        priority: EventPriority = EventPriority.NORMAL,
        filter_fn: Callable[[Event], bool] | None = None,
        once: bool = False,
    ) -> str:
        """Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function (async or sync)
            priority: Handler priority (higher runs first)
            filter_fn: Optional filter function
            once: If True, unsubscribe after first event

        Returns:
            Subscription ID
        """
        is_async = asyncio.iscoroutinefunction(handler)

        subscription = Subscription(
            id=str(uuid4()),
            event_type=event_type,
            handler=handler,
            priority=priority,
            filter_fn=filter_fn,
            is_async=is_async,
            once=once,
        )

        self._subscriptions[event_type].append(subscription)

        # Sort by priority (higher first)
        priority_order = {
            EventPriority.CRITICAL: 0,
            EventPriority.HIGH: 1,
            EventPriority.NORMAL: 2,
            EventPriority.LOW: 3,
        }
        self._subscriptions[event_type].sort(
            key=lambda s: priority_order.get(s.priority, 2)
        )

        logger.debug(
            "event_subscription_added",
            event_type=event_type,
            subscription_id=subscription.id,
            priority=priority.value,
        )

        return subscription.id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events.

        Args:
            subscription_id: ID of subscription to remove

        Returns:
            True if subscription was found and removed
        """
        for event_type, subs in self._subscriptions.items():
            for sub in subs:
                if sub.id == subscription_id:
                    subs.remove(sub)
                    logger.debug(
                        "event_subscription_removed",
                        event_type=event_type,
                        subscription_id=subscription_id,
                    )
                    return True

        return False

    def unsubscribe_all(self, event_type: str) -> int:
        """Unsubscribe all handlers for an event type.

        Args:
            event_type: Type of event

        Returns:
            Number of subscriptions removed
        """
        count = len(self._subscriptions.get(event_type, []))
        if event_type in self._subscriptions:
            del self._subscriptions[event_type]
        return count

    async def publish(
        self,
        event: Event,
        wait: bool = True,
    ) -> int:
        """Publish an event.

        Args:
            event: Event to publish
            wait: If True, wait for all handlers to complete

        Returns:
            Number of handlers that processed the event
        """
        if not self._running:
            logger.warning("event_bus_not_running", event_type=event.type)
            return 0

        self._events_published += 1

        # Add to history
        if self._enable_history:
            async with self._lock:
                self._history.append(event)
                # Trim history if too large
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

        # Get subscribers
        subscribers = self._subscriptions.get(event.type, [])
        if not subscribers:
            logger.debug("no_subscribers", event_type=event.type)
            return 0

        # Process handlers
        handlers_run = 0
        to_remove = []

        for sub in subscribers:
            # Apply filter
            if sub.filter_fn and not sub.filter_fn(event):
                continue

            try:
                if sub.is_async:
                    if wait:
                        await sub.handler(event)
                    else:
                        asyncio.create_task(sub.handler(event))
                else:
                    sub.handler(event)

                handlers_run += 1
                self._events_handled += 1

                # Mark for removal if one-time
                if sub.once:
                    to_remove.append(sub)

            except Exception as e:
                self._handler_errors += 1
                logger.exception(
                    "event_handler_error",
                    event_type=event.type,
                    subscription_id=sub.id,
                    error=str(e),
                )

        # Remove one-time subscriptions
        for sub in to_remove:
            if sub in self._subscriptions[event.type]:
                self._subscriptions[event.type].remove(sub)

        logger.debug(
            "event_published",
            event_type=event.type,
            event_id=event.id,
            handlers_run=handlers_run,
        )

        return handlers_run

    async def publish_many(
        self,
        events: list[Event],
        wait: bool = True,
    ) -> int:
        """Publish multiple events.

        Args:
            events: Events to publish
            wait: If True, wait for all handlers to complete

        Returns:
            Total number of handlers run
        """
        total = 0
        for event in events:
            total += await self.publish(event, wait=wait)
        return total

    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history.

        Args:
            event_type: Filter by event type (optional)
            limit: Maximum events to return

        Returns:
            List of events
        """
        events = self._history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "running": self._running,
            "events_published": self._events_published,
            "events_handled": self._events_handled,
            "handler_errors": self._handler_errors,
            "subscription_count": sum(
                len(subs) for subs in self._subscriptions.values()
            ),
            "event_types": list(self._subscriptions.keys()),
            "history_size": len(self._history),
        }

    def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        logger.info("EventBus stopped")

    def start(self) -> None:
        """Start the event bus."""
        self._running = True
        logger.info("EventBus started")

    def clear_history(self) -> int:
        """Clear event history.

        Returns:
            Number of events cleared
        """
        count = len(self._history)
        self._history.clear()
        return count


# Predefined event types for type safety
class EventTypes:
    """Standard event type constants."""

    # Price events
    PRICE_UPDATE = "price_update"
    PRICE_CHANGE = "price_change"
    PRICE_ALERT = "price_alert"

    # Trading events
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    ORDER_CREATED = "order_created"
    ORDER_CANCELLED = "order_cancelled"

    # Inventory events
    ITEM_LISTED = "item_listed"
    ITEM_SOLD = "item_sold"
    ITEM_DELISTED = "item_delisted"
    INVENTORY_UPDATED = "inventory_updated"

    # Analytics events
    ANALYTICS_SIGNAL = "analytics_signal"
    TREND_DETECTED = "trend_detected"
    ANOMALY_DETECTED = "anomaly_detected"

    # System events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_ERROR = "service_error"
    HEALTH_CHECK = "health_check"

    # User events
    USER_ACTION = "user_action"
    ALERT_TRIGGERED = "alert_triggered"
    REPORT_GENERATED = "report_generated"
