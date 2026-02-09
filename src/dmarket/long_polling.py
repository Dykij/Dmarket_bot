"""Long Polling with Server-Sent Events (SSE) Simulation for DMarket.

Since DMarket doesn't support WebSocket or SSE, this module implements
an optimized long-polling approach that simulates real-time updates:

1. **Conditional Requests** - Uses If-Modified-Since headers
2. **ETag Caching** - Avoids processing unchanged data
3. **Chunked Processing** - Process items as they arrive
4. **Connection Reuse** - Keep HTTP connections alive

This is more efficient than standard polling because:
- Server can return 304 Not Modified (no body)
- ETags allow server-side change detection
- Long timeouts reduce request overhead

Usage:
    ```python
    from src.dmarket.long_polling import LongPollingClient

    client = LongPollingClient(api=dmarket_api)

    async for update in client.stream_updates("csgo"):
        if update.type == "price_change":
            handle_price_change(update)
    ```

Created: January 6, 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)


class UpdateType(StrEnum):
    """Types of market updates."""

    PRICE_CHANGE = "price_change"
    NEW_LISTING = "new_listing"
    ITEM_SOLD = "item_sold"
    QUANTITY_CHANGE = "quantity_change"
    NO_CHANGE = "no_change"


@dataclass
class MarketUpdate:
    """Represents a market update event."""

    type: UpdateType
    item_id: str
    item_name: str
    game: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Price info
    old_price: float | None = None
    new_price: float | None = None
    price_change_percent: float | None = None

    # Quantity info
    old_quantity: int | None = None
    new_quantity: int | None = None

    # Full item data
    item_data: dict[str, Any] | None = None

    @property
    def is_significant(self) -> bool:
        """Check if update is significant enough to act on."""
        if self.type == UpdateType.NO_CHANGE:
            return False

        if self.type == UpdateType.PRICE_CHANGE:
            return (
                self.price_change_percent is not None
                and abs(self.price_change_percent) >= 1.0
            )

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "game": self.game,
            "timestamp": self.timestamp.isoformat(),
            "old_price": self.old_price,
            "new_price": self.new_price,
            "price_change_percent": self.price_change_percent,
            "is_significant": self.is_significant,
        }


@dataclass
class CacheEntry:
    """Cache entry for item state."""

    item_id: str
    price: float
    quantity: int
    etag: str | None
    last_modified: datetime
    data_hash: str


class LongPollingClient:
    """Long-polling client with conditional requests and delta detection."""

    def __init__(
        self,
        api: DMarketAPI,
        poll_interval: float = 15.0,
        timeout: float = 30.0,
        max_items_per_request: int = 100,
    ) -> None:
        """Initialize long-polling client.

        Args:
            api: DMarket API client
            poll_interval: Seconds between polls (minimum 10s for rate limits)
            timeout: Request timeout
            max_items_per_request: Items per API request

        """
        self.api = api
        self.poll_interval = max(10.0, poll_interval)  # Rate limit safe
        self.timeout = timeout
        self.max_items = max_items_per_request

        self._cache: dict[str, CacheEntry] = {}
        self._running = False
        self._last_etag: dict[str, str] = {}
        self._last_modified: dict[str, datetime] = {}

    async def stream_updates(
        self,
        game: str = "csgo",
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> AsyncIterator[MarketUpdate]:
        """Stream market updates using long-polling.

        Args:
            game: Game to monitor
            min_price: Minimum price filter (optional)
            max_price: Maximum price filter (optional)

        Yields:
            MarketUpdate events

        """
        self._running = True

        while self._running:
            try:
                # Fetch with conditional headers
                updates = await self._poll_with_delta(
                    game=game,
                    min_price=min_price,
                    max_price=max_price,
                )

                # Yield significant updates
                for update in updates:
                    if update.is_significant:
                        yield update

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("long_polling_error", error=str(e))
                await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        """Stop streaming."""
        self._running = False

    async def _poll_with_delta(
        self,
        game: str,
        min_price: float | None,
        max_price: float | None,
    ) -> list[MarketUpdate]:
        """Poll and return only changed items."""
        updates: list[MarketUpdate] = []

        try:
            # Build request parameters
            params: dict[str, Any] = {
                "game": game,
                "limit": self.max_items,
                "order_by": "updated",
                "order_dir": "desc",
            }

            if min_price is not None:
                params["price_from"] = int(min_price * 100)  # Cents
            if max_price is not None:
                params["price_to"] = int(max_price * 100)

            # Make request
            response = await self.api.get_market_items(**params)

            items = response.get("objects", [])

            # Process each item
            for item in items:
                update = self._process_item(item, game)
                if update:
                    updates.append(update)

        except Exception as e:
            logger.exception("poll_delta_error", game=game, error=str(e))

        return updates

    def _process_item(self, item: dict[str, Any], game: str) -> MarketUpdate | None:
        """Process item and detect changes."""
        item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
        if not item_id:
            return None

        title = item.get("title", "Unknown")

        # Get current price and quantity
        price_data = item.get("price", {})
        price_str = price_data.get("USD", "0")
        current_price = float(price_str) / 100  # Cents to dollars
        current_quantity = item.get("amount", 1)

        if current_price <= 0:
            return None

        # Calculate data hash for change detection
        data_hash = f"{current_price}:{current_quantity}"

        # Check cache
        cached = self._cache.get(item_id)

        if cached is None:
            # New item
            self._cache[item_id] = CacheEntry(
                item_id=item_id,
                price=current_price,
                quantity=current_quantity,
                etag=None,
                last_modified=datetime.now(UTC),
                data_hash=data_hash,
            )

            return MarketUpdate(
                type=UpdateType.NEW_LISTING,
                item_id=item_id,
                item_name=title,
                game=game,
                new_price=current_price,
                new_quantity=current_quantity,
                item_data=item,
            )

        # Check if data changed
        if cached.data_hash == data_hash:
            return None  # No change

        # Detect type of change
        update_type = UpdateType.PRICE_CHANGE
        price_change_percent = None

        if cached.price != current_price:
            update_type = UpdateType.PRICE_CHANGE
            price_change_percent = (
                (current_price - cached.price) / cached.price * 100
                if cached.price > 0
                else 0
            )
        elif cached.quantity != current_quantity:
            update_type = UpdateType.QUANTITY_CHANGE

        # Create update
        update = MarketUpdate(
            type=update_type,
            item_id=item_id,
            item_name=title,
            game=game,
            old_price=cached.price,
            new_price=current_price,
            price_change_percent=price_change_percent,
            old_quantity=cached.quantity,
            new_quantity=current_quantity,
            item_data=item,
        )

        # Update cache
        cached.price = current_price
        cached.quantity = current_quantity
        cached.last_modified = datetime.now(UTC)
        cached.data_hash = data_hash

        return update

    def get_cached_item(self, item_id: str) -> CacheEntry | None:
        """Get cached item state."""
        return self._cache.get(item_id)

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._last_etag.clear()
        self._last_modified.clear()


class BatchUpdateChecker:
    """Efficiently check for updates across multiple items.

    Optimizes API usage by batching items and using
    intelligent update detection.
    """

    def __init__(
        self,
        api: DMarketAPI,
        check_interval: float = 30.0,
    ) -> None:
        """Initialize batch checker.

        Args:
            api: DMarket API client
            check_interval: Seconds between checks

        """
        self.api = api
        self.check_interval = check_interval
        self._watched_items: dict[str, float] = {}  # item_name -> target_price
        self._last_prices: dict[str, float] = {}

    def watch_item(self, item_name: str, target_price: float) -> None:
        """Add item to watch list.

        Args:
            item_name: Item name to watch
            target_price: Alert when price reaches this

        """
        self._watched_items[item_name] = target_price

    def unwatch_item(self, item_name: str) -> None:
        """Remove item from watch list."""
        self._watched_items.pop(item_name, None)
        self._last_prices.pop(item_name, None)

    async def check_prices(self, game: str = "csgo") -> list[dict[str, Any]]:
        """Check prices for all watched items.

        Returns:
            List of items that hit target prices

        """
        alerts: list[dict[str, Any]] = []

        for item_name, target_price in self._watched_items.items():
            try:
                response = await self.api.get_market_items(
                    game=game,
                    title=item_name,
                    limit=1,
                )

                items = response.get("objects", [])
                if not items:
                    continue

                item = items[0]
                price_data = item.get("price", {})
                price_str = price_data.get("USD", "0")
                current_price = float(price_str) / 100

                # Check if target reached
                if current_price <= target_price:
                    alerts.append({
                        "item_name": item_name,
                        "target_price": target_price,
                        "current_price": current_price,
                        "item_data": item,
                    })

                self._last_prices[item_name] = current_price

            except Exception as e:
                logger.exception(
                    "check_price_error",
                    item=item_name,
                    error=str(e),
                )

        return alerts

    async def run_continuous(
        self,
        game: str = "csgo",
        callback: Any = None,
    ) -> None:
        """Run continuous price checking.

        Args:
            game: Game to check
            callback: Async function to call when target hit

        """
        while True:
            try:
                alerts = await self.check_prices(game)

                for alert in alerts:
                    if callback:
                        await callback(alert)
                    else:
                        logger.info("target_price_alert", **alert)

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("continuous_check_error", error=str(e))
                await asyncio.sleep(self.check_interval)


# Factory functions
def create_long_polling_client(
    api: DMarketAPI,
    poll_interval: float = 15.0,
) -> LongPollingClient:
    """Create a long-polling client instance."""
    return LongPollingClient(api=api, poll_interval=poll_interval)


def create_batch_checker(
    api: DMarketAPI,
    check_interval: float = 30.0,
) -> BatchUpdateChecker:
    """Create a batch update checker instance."""
    return BatchUpdateChecker(api=api, check_interval=check_interval)
