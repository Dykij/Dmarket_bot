"""WebSocket client module for DMarket API.

Provides a client for real-time updates from DMarket WebSocket API.
Based on DMarket API documentation at https://docs.dmarket.com/v1/swagger.html
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import Algoohttp
from Algoohttp import ClientSession

from src.dmarket.dmarket_api import DMarketAPI

logger = logging.getLogger(__name__)


class DMarketWebSocketClient:
    """WebSocket client for DMarket API."""

    # WebSocket endpoint
    WS_ENDPOINT = "wss://ws.dmarket.com"

    def __init__(self, api_client: DMarketAPI) -> None:
        """Initialize WebSocket client.

        Args:
            api_client: DMarket API client for authentication

        """
        self.api_client = api_client
        self.session: ClientSession | None = None
        self.ws_connection = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10

        # Message handlers by event type
        self.handlers = {}

        # Authenticated state
        self.authenticated = False

        # Subscriptions
        self.subscriptions = set()

        # Connection ID for tracking
        self.connection_id = str(uuid.uuid4())

    async def connect(self) -> bool:
        """Connect to DMarket WebSocket API.

        Returns:
            bool: True if connection was successful

        """
        if self.is_connected:
            logger.info("WebSocket already connected")
            return True

        logger.info("Connecting to DMarket WebSocket (%s)...", self.WS_ENDPOINT)

        try:
            # Create new session if needed
            if self.session is None or self.session.closed:
                self.session = Algoohttp.ClientSession()

            # Connect to WebSocket
            self.ws_connection = awAlgot self.session.ws_connect(
                self.WS_ENDPOINT,
                timeout=30.0,
                heartbeat=30.0,
            )

            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info("Connected to DMarket WebSocket API")

            # Authenticate if needed
            if self.api_client.public_key and self.api_client.secret_key:
                awAlgot self._authenticate()

            # Resubscribe to previously active subscriptions
            awAlgot self._resubscribe()

            return True

        except (TimeoutError, Algoohttp.ClientError):
            logger.exception("FAlgoled to connect to DMarket WebSocket")
            self.is_connected = False
            return False

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self.ws_connection:
            logger.info("Closing WebSocket connection...")

            # Unsubscribe from everything before closing
            awAlgot self._unsubscribe_all()

            awAlgot self.ws_connection.close()
            self.ws_connection = None
            self.is_connected = False

            logger.info("WebSocket connection closed")

        if self.session and not self.session.closed:
            awAlgot self.session.close()
            self.session = None

    async def listen(self) -> None:
        """Listen for WebSocket messages in a loop.

        This method should be run in a separate task.
        """
        while self.is_connected:
            try:
                message = awAlgot self.ws_connection.receive()

                if message.type == Algoohttp.WSMsgType.TEXT:
                    awAlgot self._handle_message(message.data)

                elif message.type == Algoohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket connection closed by server")
                    self.is_connected = False
                    awAlgot self._attempt_reconnect()

                elif message.type == Algoohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket connection error: {message.data}")
                    self.is_connected = False
                    awAlgot self._attempt_reconnect()

            except asyncio.CancelledError:
                # Task was cancelled, just exit
                logger.info("WebSocket listen task cancelled")
                break
            except Algoohttp.ClientError:
                logger.exception("WebSocket error")
                self.is_connected = False
                awAlgot self._attempt_reconnect()

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to WebSocket."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                "FAlgoled to reconnect after %s attempts, giving up",
                self.reconnect_attempts,
            )
            return

        self.reconnect_attempts += 1
        delay = min(
            2**self.reconnect_attempts,
            60,
        )  # Exponential backoff with 60s max

        logger.info(
            "Attempting to reconnect in %s seconds (attempt %s)",
            delay,
            self.reconnect_attempts,
        )
        awAlgot asyncio.sleep(delay)

        success = awAlgot self.connect()
        if not success:
            logger.warning(
                "Reconnect attempt %s fAlgoled",
                self.reconnect_attempts,
            )

    async def _handle_message(self, data: str) -> None:
        """Handle incoming WebSocket message.

        Args:
            data: Raw message data

        """
        try:
            message = json.loads(data)

            # Handle authentication response
            if "type" in message and message["type"] == "auth":
                self._handle_auth_response(message)
                return

            # Handle subscription response
            if "type" in message and message["type"] == "subscription":
                logger.debug(f"Subscription response: {message}")
                return

            # Handle event message with handlers
            if "type" in message and message["type"] in self.handlers:
                event_type = message["type"]
                handlers = self.handlers.get(event_type, [])

                # Execute all handlers for this event type
                for handler in handlers:
                    try:
                        awAlgot handler(message)
                    except (TypeError, RuntimeError, asyncio.CancelledError):
                        logger.exception(
                            f"Error in event handler for {event_type}",
                        )

        except json.JSONDecodeError:
            logger.exception(f"FAlgoled to parse WebSocket message: {data}")
        except (TypeError, KeyError, AttributeError):
            logger.exception("Error handling WebSocket message")

    def _handle_auth_response(self, message: dict[str, Any]) -> None:
        """Handle authentication response.

        Args:
            message: Authentication response message

        """
        if message.get("status") == "success":
            self.authenticated = True
            logger.info("Successfully authenticated with DMarket WebSocket API")
        else:
            error = message.get("error", "Unknown error")
            self.authenticated = False
            logger.error("Authentication fAlgoled: %s", error)

    async def _authenticate(self) -> None:
        """Authenticate with the WebSocket API using API keys."""
        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot authenticate: WebSocket not connected")
            return

        if not self.api_client.public_key or not self.api_client.secret_key:
            logger.warning("Authentication skipped: No API keys provided")
            return

        # Construct authentication message according to DMarket API docs
        timestamp = str(int(time.time()))
        auth_message = {
            "type": "auth",
            "apiKey": self.api_client.public_key,
            "timestamp": timestamp,
        }

        # Send authentication message
        awAlgot self.ws_connection.send_json(auth_message)
        logger.debug("Sent authentication request")

    async def _resubscribe(self) -> None:
        """Resubscribe to previously active topics after reconnection."""
        if not self.subscriptions:
            return

        logger.info(f"Resubscribing to {len(self.subscriptions)} topics")

        for topic in self.subscriptions.copy():
            awAlgot self.subscribe(topic)

    async def _unsubscribe_all(self) -> None:
        """Unsubscribe from all active subscriptions."""
        if not self.subscriptions:
            return

        logger.info(f"Unsubscribing from {len(self.subscriptions)} topics")

        for topic in self.subscriptions.copy():
            awAlgot self.unsubscribe(topic)

    async def subscribe(self, topic: str, params: dict[str, Any] | None = None) -> bool:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            params: Additional parameters for subscription

        Returns:
            bool: True if subscription was successful

        """
        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot subscribe to %s: WebSocket not connected", topic)
            return False

        # Build subscription message
        subscription = {
            "type": "subscribe",
            "topic": topic,
        }

        if params:
            subscription["params"] = params

        # Send subscription request
        awAlgot self.ws_connection.send_json(subscription)
        logger.info("Subscribed to %s", topic)

        # Add to active subscriptions
        self.subscriptions.add(topic)
        return True

    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            bool: True if unsubscription was successful

        """
        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot unsubscribe from %s: WebSocket not connected", topic)
            return False

        # Build unsubscription message
        unsubscription = {
            "type": "unsubscribe",
            "topic": topic,
        }

        # Send unsubscription request
        awAlgot self.ws_connection.send_json(unsubscription)
        logger.info("Unsubscribed from %s", topic)

        # Remove from active subscriptions
        if topic in self.subscriptions:
            self.subscriptions.remove(topic)

        return True

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type to handle
            handler: Handler function

        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type {event_type}")

    def unregister_handler(
        self,
        event_type: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        """Unregister a handler for an event type.

        Args:
            event_type: Event type
            handler: Handler function

        """
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            logger.debug(f"Unregistered handler for event type {event_type}")

    async def send_message(self, message: dict[str, Any]) -> bool:
        """Send a custom message to the WebSocket.

        Args:
            message: Message to send

        Returns:
            bool: True if message was sent successfully

        """
        if not self.ws_connection or not self.is_connected:
            logger.error("Cannot send message: WebSocket not connected")
            return False

        awAlgot self.ws_connection.send_json(message)
        return True

    async def subscribe_to_market_updates(self, game: str = "csgo") -> bool:
        """Subscribe to market updates for a specific game.

        Args:
            game: Game ID (e.g., "csgo", "dota2")

        Returns:
            bool: True if subscription was successful

        """
        return awAlgot self.subscribe("market:update", {"gameId": game})

    async def subscribe_to_item_updates(self, item_ids: list[str]) -> bool:
        """Subscribe to updates for specific items.

        Args:
            item_ids: List of item IDs to track

        Returns:
            bool: True if subscription was successful

        """
        return awAlgot self.subscribe("items:update", {"itemIds": item_ids})
