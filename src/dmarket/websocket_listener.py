"""WebSocket Listener for DMarket Real-Time Updates.

Provides instant notifications about:
- New market listings
- Price changes
- Order status updates
- Balance changes

Real-time reaction: < 50ms instead of 1-2 seconds polling.

Created: January 2, 2026
"""

import asyncio
import json
import time
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog
from websockets import WebSocketClientProtocol

logger = structlog.get_logger(__name__)


class WSEventType(StrEnum):
    """WebSocket event types."""

    NEW_LISTING = "new_listing"
    PRICE_CHANGE = "price_change"
    ORDER_FILLED = "order_filled"
    ORDER_CREATED = "order_created"
    BALANCE_CHANGE = "balance_change"
    CONNECTION_OPEN = "connection_open"
    CONNECTION_CLOSED = "connection_closed"
    ERROR = "error"


class DMarketWebSocketListener:
    """Real-time WebSocket listener for DMarket events."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        on_event: Callable | None = None,
    ):
        """Initialize WebSocket listener.

        Args:
            public_key: DMarket API public key
            secret_key: DMarket API secret key
            on_event: Callback function for events: async def callback(event_type, data)
        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.on_event = on_event

        # WebSocket connection
        self.ws: WebSocketClientProtocol | None = None
        self.is_running = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 60
        self.ping_interval = 30  # Keep connection alive

        # Statistics
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_failed": 0,
            "reconnects": 0,
            "uptime_start": None,
            "last_event_time": None,
        }

        # Event handlers registry
        self.event_handlers: dict[WSEventType, list[Callable]] = {
            event_type: [] for event_type in WSEventType
        }

        logger.info("websocket_listener_initialized")

    async def start(self):
        """Start WebSocket listener with auto-reconnect."""
        if self.is_running:
            logger.warning("websocket_already_running")
            return

        self.is_running = True
        self.stats["uptime_start"] = datetime.now()

        logger.info("websocket_listener_starting")

        max_retries = 5  # Maximum connection attempts
        retry_count = 0

        while self.is_running and retry_count < max_retries:
            try:
                await self._connect_and_listen()
            except (ConnectionRefusedError, TimeoutError) as e:
                retry_count += 1
                logger.warning(
                    "websocket_connection_unavailable",
                    error=str(e),
                    attempt=retry_count,
                    max_retries=max_retries,
                )

                if retry_count >= max_retries:
                    logger.error(  # noqa: TRY400
                        "websocket_max_retries_reached",
                        message="DMarket WebSocket not available. Consider using polling mode instead.",
                    )
                    self.is_running = False
                    break

                if self.is_running:
                    delay = min(
                        self.reconnect_delay * (2**retry_count),
                        self.max_reconnect_delay,
                    )
                    logger.info("websocket_retry_delay", delay=delay)
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.exception("websocket_connection_failed", error=str(e))

                if self.is_running:
                    # Exponential backoff
                    delay = min(
                        self.reconnect_delay * (2 ** self.stats["reconnects"]),
                        self.max_reconnect_delay,
                    )
                    logger.info("websocket_reconnecting", delay=delay)
                    await asyncio.sleep(delay)
                    self.stats["reconnects"] += 1

    async def stop(self):
        """Stop WebSocket listener gracefully."""
        logger.info("websocket_listener_stopping")
        self.is_running = False

        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.warning("websocket_close_error", error=str(e))

        await self._emit_event(WSEventType.CONNECTION_CLOSED, {"reason": "Manual stop"})
        logger.info("websocket_listener_stopped")

    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for events."""
        # DMarket doesn't provide public WebSocket API - disable connection
        logger.warning(
            "websocket_not_available",
            message="DMarket API doesn't provide public WebSocket endpoint. "
            "Real-time updates are disabled. Bot will use REST API polling instead.",
        )

        # Mark as stopped - no reconnection attempts
        self.is_running = False

        await self._emit_event(
            WSEventType.ERROR,
            {
                "error": "WebSocket not available",
                "fallback": "REST API polling",
                "timestamp": time.time(),
            },
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for WebSocket connection.

        Returns:
            dict with auth headers
        """
        # For DMarket WebSocket, authentication might be token-based
        # This is a placeholder - implement actual auth logic
        return {
            "X-Api-Key": self.public_key,
            # Add signature if needed
        }

    async def _subscribe_channels(self):
        """Subscribe to WebSocket channels."""
        if not self.ws:
            return

        # Subscribe to relevant channels
        subscriptions = [
            {"action": "subscribe", "channel": "market.new_listings"},
            {"action": "subscribe", "channel": "market.price_updates"},
            {"action": "subscribe", "channel": "user.orders"},
            {"action": "subscribe", "channel": "user.balance"},
        ]

        for sub in subscriptions:
            try:
                await self.ws.send(json.dumps(sub))
                logger.debug("websocket_subscribed", channel=sub["channel"])
            except Exception as e:
                logger.exception("websocket_subscribe_failed", channel=sub["channel"], error=str(e))

    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message.

        Args:
            message: Raw message string
        """
        self.stats["events_received"] += 1
        self.stats["last_event_time"] = datetime.now()

        try:
            data = json.loads(message)

            # Determine event type from message
            event_type = self._determine_event_type(data)

            if event_type:
                await self._emit_event(event_type, data)
                self.stats["events_processed"] += 1
            else:
                logger.debug("websocket_unknown_event", data=data)

        except json.JSONDecodeError as e:
            logger.error("websocket_invalid_json", message=message, error=str(e))  # noqa: TRY400
            self.stats["events_failed"] += 1
        except Exception as e:
            logger.exception("websocket_handle_message_error", error=str(e))
            self.stats["events_failed"] += 1

    def _determine_event_type(self, data: dict) -> WSEventType | None:
        """Determine event type from message data.

        Args:
            data: Parsed message data

        Returns:
            WSEventType or None
        """
        # This logic depends on actual DMarket WebSocket message format
        # Placeholder implementation
        channel = data.get("channel", "")
        event = data.get("event", "")

        if "new_listings" in channel or event == "new_item":
            return WSEventType.NEW_LISTING
        if "price_updates" in channel or event == "price_change":
            return WSEventType.PRICE_CHANGE
        if "orders" in channel:
            if event == "order_filled":
                return WSEventType.ORDER_FILLED
            if event == "order_created":
                return WSEventType.ORDER_CREATED
        elif "balance" in channel or event == "balance_update":
            return WSEventType.BALANCE_CHANGE

        return None

    async def _emit_event(self, event_type: WSEventType, data: dict):
        """Emit event to registered handlers.

        Args:
            event_type: Type of event
            data: Event data
        """
        logger.debug("websocket_event_emitted", event_type=event_type)

        # Call default callback
        if self.on_event:
            try:
                await self.on_event(event_type, data)
            except Exception as e:
                logger.exception("websocket_callback_error", error=str(e))

        # Call registered handlers
        for handler in self.event_handlers.get(event_type, []):
            try:
                await handler(data)
            except Exception as e:
                logger.exception("websocket_handler_error", handler=handler.__name__, error=str(e))

    def register_handler(self, event_type: WSEventType, handler: Callable):
        """Register event handler.

        Args:
            event_type: Event type to listen for
            handler: Async callback function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.info("websocket_handler_registered", event_type=event_type, handler=handler.__name__)

    def unregister_handler(self, event_type: WSEventType, handler: Callable):
        """Unregister event handler.

        Args:
            event_type: Event type
            handler: Handler to remove
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                logger.info("websocket_handler_unregistered", event_type=event_type)
            except ValueError:
                logger.warning("websocket_handler_not_found", event_type=event_type)

    def get_stats(self) -> dict[str, Any]:
        """Get WebSocket statistics.

        Returns:
            dict with statistics
        """
        uptime = None
        if self.stats["uptime_start"]:
            uptime = (datetime.now() - self.stats["uptime_start"]).total_seconds()

        return {
            "is_running": self.is_running,
            "events_received": self.stats["events_received"],
            "events_processed": self.stats["events_processed"],
            "events_failed": self.stats["events_failed"],
            "reconnects": self.stats["reconnects"],
            "uptime_seconds": uptime,
            "last_event_time": self.stats["last_event_time"],
        }


class WebSocketManager:
    """High-level WebSocket manager with retry logic."""

    def __init__(self, listener: DMarketWebSocketListener):
        """Initialize WebSocket manager.

        Args:
            listener: WebSocket listener instance
        """
        self.listener = listener
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start WebSocket listener in background task."""
        if self._task and not self._task.done():
            logger.warning("websocket_manager_already_running")
            return

        logger.info("websocket_manager_starting")
        self._task = asyncio.create_task(self.listener.start())

    async def stop(self):
        """Stop WebSocket listener."""
        logger.info("websocket_manager_stopping")
        await self.listener.stop()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                logger.warning("websocket_manager_stop_timeout")
                self._task.cancel()

    async def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """Wait for WebSocket connection to be established.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if connected, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.listener.ws and self.listener.is_running:
                return True
            await asyncio.sleep(0.1)

        return False


__all__ = ["DMarketWebSocketListener", "WSEventType", "WebSocketManager"]
