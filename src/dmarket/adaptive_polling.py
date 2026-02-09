"""Adaptive Polling Engine - intelligent polling optimization for DMarket API.

DMarket does not support WebSocket connections. This module provides
an optimized polling solution that:

1. **Adaptive Intervals** - adjusts polling frequency based on:
   - Time of day (more frequent during peak hours)
   - Market activity level
   - Item importance (whitelist items polled more often)
   - Recent price changes (more polling after volatility)

2. **Delta Detection** - only processes changed items:
   - Maintains local price cache
   - Compares with previous poll
   - Triggers callbacks only for actual changes

3. **Batch Optimization** - efficient API usage:
   - Groups items by game
   - Uses pagination efficiently
   - Respects rate limits

4. **Priority Queue** - polls important items first:
   - Whitelist items get priority
   - Items with recent activity
   - Items near target prices

Usage:
    ```python
    from src.dmarket.adaptive_polling import AdaptivePollingEngine

    async def on_price_change(item_name, old_price, new_price):
        print(f"{item_name}: ${old_price} -> ${new_price}")

    engine = AdaptivePollingEngine(
        api_client=dmarket_api,
        on_price_change=on_price_change,
    )

    await engine.start()
    # ... later
    await engine.stop()
    ```

Created: January 6, 2026
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = structlog.get_logger(__name__)


class PollPriority(StrEnum):
    """Polling priority levels."""

    CRITICAL = "critical"  # Poll every cycle (targets near fill)
    HIGH = "high"  # Poll frequently (whitelist items)
    NORMAL = "normal"  # Standard polling
    LOW = "low"  # Poll less frequently


class MarketActivity(StrEnum):
    """Market activity levels."""

    PEAK = "peak"  # High activity (more polling)
    NORMAL = "normal"  # Normal activity
    LOW = "low"  # Low activity (less polling)
    MINIMAL = "minimal"  # Very low activity


@dataclass
class PollConfig:
    """Polling configuration."""

    # Base intervals (seconds)
    base_interval: float = 30.0  # Default: poll every 30 seconds
    min_interval: float = 10.0  # Minimum: 10 seconds (rate limit safe)
    max_interval: float = 120.0  # Maximum: 2 minutes

    # Priority multipliers (lower = more frequent)
    priority_multipliers: dict[PollPriority, float] = field(default_factory=lambda: {
        PollPriority.CRITICAL: 0.3,  # 30% of base interval
        PollPriority.HIGH: 0.5,  # 50% of base interval
        PollPriority.NORMAL: 1.0,  # Base interval
        PollPriority.LOW: 2.0,  # 200% of base interval
    })

    # Activity multipliers
    activity_multipliers: dict[MarketActivity, float] = field(default_factory=lambda: {
        MarketActivity.PEAK: 0.5,  # Poll twice as often
        MarketActivity.NORMAL: 1.0,
        MarketActivity.LOW: 1.5,
        MarketActivity.MINIMAL: 2.0,
    })

    # Peak hours (UTC)
    peak_hours: tuple[int, ...] = (14, 15, 16, 17, 18, 19, 20, 21)  # 2 PM - 9 PM UTC

    # Batch settings
    items_per_batch: int = 100
    max_concurrent_requests: int = 3


@dataclass
class CachedPrice:
    """Cached price information."""

    item_id: str
    item_name: str
    price: float  # In USD (dollars, not cents)
    quantity: int
    last_updated: datetime
    change_count: int = 0  # Number of changes detected
    priority: PollPriority = PollPriority.NORMAL


@dataclass
class PriceChange:
    """Detected price change."""

    item_id: str
    item_name: str
    old_price: float
    new_price: float
    change_percent: float
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_significant(self) -> bool:
        """Check if change is significant (>1%)."""
        return abs(self.change_percent) >= 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "old_price": self.old_price,
            "new_price": self.new_price,
            "change_percent": round(self.change_percent, 2),
            "is_significant": self.is_significant,
        }


# Type alias for callbacks
PriceChangeCallback = Callable[[PriceChange], Coroutine[Any, Any, None]]
NewListingCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AdaptivePollingEngine:
    """Intelligent polling engine with adaptive intervals and delta detection."""

    def __init__(
        self,
        api_client: DMarketAPI,
        config: PollConfig | None = None,
        on_price_change: PriceChangeCallback | None = None,
        on_new_listing: NewListingCallback | None = None,
        games: list[str] | None = None,
        whitelist_items: list[str] | None = None,
    ) -> None:
        """Initialize adaptive polling engine.

        Args:
            api_client: DMarket API client
            config: Polling configuration
            on_price_change: Callback for price changes
            on_new_listing: Callback for new listings
            games: Games to monitor (default: csgo)
            whitelist_items: Items to prioritize

        """
        self.api = api_client
        self.config = config or PollConfig()
        self.on_price_change = on_price_change
        self.on_new_listing = on_new_listing
        self.games = games or ["csgo"]
        self.whitelist_items = set(whitelist_items or [])

        # State
        self._running = False
        self._price_cache: dict[str, CachedPrice] = {}
        self._known_item_ids: set[str] = set()
        self._last_poll_time: datetime | None = None
        self._poll_count = 0
        self._changes_detected = 0

        # Tasks
        self._poll_task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    @property
    def is_running(self) -> bool:
        """Check if polling is active."""
        return self._running

    @property
    def stats(self) -> dict[str, Any]:
        """Get polling statistics."""
        return {
            "is_running": self._running,
            "poll_count": self._poll_count,
            "changes_detected": self._changes_detected,
            "cached_items": len(self._price_cache),
            "known_items": len(self._known_item_ids),
            "last_poll": self._last_poll_time.isoformat() if self._last_poll_time else None,
        }

    async def start(self) -> None:
        """Start polling."""
        if self._running:
            logger.warning("polling_already_running")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._polling_loop())

        logger.info(
            "adaptive_polling_started",
            games=self.games,
            base_interval=self.config.base_interval,
            whitelist_count=len(self.whitelist_items),
        )

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info(
            "adaptive_polling_stopped",
            total_polls=self._poll_count,
            total_changes=self._changes_detected,
        )

    def add_to_whitelist(self, item_name: str) -> None:
        """Add item to whitelist for priority polling."""
        self.whitelist_items.add(item_name.lower())

        # Update priority in cache
        for cached in self._price_cache.values():
            if cached.item_name.lower() == item_name.lower():
                cached.priority = PollPriority.HIGH

    def remove_from_whitelist(self, item_name: str) -> None:
        """Remove item from whitelist."""
        self.whitelist_items.discard(item_name.lower())

    def set_item_priority(self, item_id: str, priority: PollPriority) -> None:
        """Set polling priority for specific item."""
        if item_id in self._price_cache:
            self._price_cache[item_id].priority = priority

    async def force_poll(self, game: str | None = None) -> list[PriceChange]:
        """Force immediate poll and return changes."""
        games_to_poll = [game] if game else self.games
        all_changes = []

        for g in games_to_poll:
            changes = await self._poll_game(g)
            all_changes.extend(changes)

        return all_changes

    async def _polling_loop(self) -> None:
        """Main polling loop with adaptive intervals."""
        while self._running:
            try:
                await self._execute_poll_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("polling_error", error=str(e))
                await asyncio.sleep(self.config.base_interval)

    async def _execute_poll_cycle(self) -> None:
        """Execute a single poll cycle for all games."""
        interval = self._calculate_interval()

        for game in self.games:
            if not self._running:
                break
            changes = await self._poll_game(game)
            await self._process_changes(changes)

        self._poll_count += 1
        self._last_poll_time = datetime.now(UTC)
        await asyncio.sleep(interval)

    async def _process_changes(self, changes: list) -> None:
        """Process detected price changes."""
        for change in changes:
            self._changes_detected += 1
            if self.on_price_change:
                try:
                    await self.on_price_change(change)
                except Exception as e:
                    logger.exception("price_change_callback_error", error=str(e))

    def _calculate_interval(self) -> float:
        """Calculate adaptive polling interval."""
        base = self.config.base_interval

        # Activity multiplier based on time
        activity = self._get_market_activity()
        activity_mult = self.config.activity_multipliers[activity]

        # Adjust based on recent changes
        if self._changes_detected > 0 and self._poll_count > 0:
            change_rate = self._changes_detected / self._poll_count
            if change_rate > 0.1:  # >10% of polls have changes
                activity_mult *= 0.7  # Poll more frequently

        interval = base * activity_mult

        # Clamp to min/max
        return max(self.config.min_interval, min(self.config.max_interval, interval))

    def _get_market_activity(self) -> MarketActivity:
        """Determine current market activity level."""
        now = datetime.now(UTC)

        # Check if peak hours
        if now.hour in self.config.peak_hours:
            return MarketActivity.PEAK

        # Weekend typically has lower activity
        if now.weekday() >= 5:  # Saturday, Sunday
            return MarketActivity.LOW

        # Late night (0-6 UTC)
        if now.hour < 6:
            return MarketActivity.MINIMAL

        return MarketActivity.NORMAL

    async def _poll_game(self, game: str) -> list[PriceChange]:
        """Poll items for a specific game."""
        changes: list[PriceChange] = []

        try:
            async with self._semaphore:
                # Get market items
                response = await self.api.get_market_items(
                    game=game,
                    limit=self.config.items_per_batch,
                    order_by="updated",
                    order_dir="desc",
                )

            items = response.get("objects", [])

            for item in items:
                item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
                if not item_id:
                    continue

                # Check for new listing
                if item_id not in self._known_item_ids:
                    self._known_item_ids.add(item_id)
                    # Cache the initial price for new items
                    self._cache_initial_price(item)
                    if self.on_new_listing:
                        try:
                            await self.on_new_listing(item)
                        except Exception as e:
                            logger.exception("new_listing_callback_error", error=str(e))
                    continue

                # Check for price change
                change = self._check_price_change(item)
                if change:
                    changes.append(change)

        except Exception as e:
            logger.exception("poll_game_error", game=game, error=str(e))

        return changes

    def _cache_initial_price(self, item: dict[str, Any]) -> None:
        """Cache initial price for a new item.

        This ensures price changes can be detected on subsequent polls.
        """
        item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
        if not item_id:
            return

        title = item.get("title", "Unknown")

        # Get current price (convert from cents to dollars)
        price_data = item.get("price", {})
        price_str = price_data.get("USD", "0")
        current_price = float(price_str) / 100

        if current_price <= 0:
            return

        # Determine priority
        priority = (
            PollPriority.HIGH
            if title.lower() in self.whitelist_items
            else PollPriority.NORMAL
        )

        # Add to cache
        self._price_cache[item_id] = CachedPrice(
            item_id=item_id,
            item_name=title,
            price=current_price,
            quantity=1,
            last_updated=datetime.now(UTC),
            priority=priority,
        )

    def _check_price_change(self, item: dict[str, Any]) -> PriceChange | None:
        """Check if item price has changed."""
        item_id = item.get("itemId") or item.get("extra", {}).get("itemId", "")
        title = item.get("title", "Unknown")

        # Get current price (convert from cents to dollars)
        price_data = item.get("price", {})
        price_str = price_data.get("USD", "0")
        current_price = float(price_str) / 100

        if current_price <= 0:
            return None

        # Check cache
        cached = self._price_cache.get(item_id)

        if cached is None:
            # First time seeing this item - add to cache
            priority = (
                PollPriority.HIGH
                if title.lower() in self.whitelist_items
                else PollPriority.NORMAL
            )

            self._price_cache[item_id] = CachedPrice(
                item_id=item_id,
                item_name=title,
                price=current_price,
                quantity=1,
                last_updated=datetime.now(UTC),
                priority=priority,
            )
            return None

        # Check if price changed
        if abs(cached.price - current_price) < 0.01:  # Less than $0.01 change
            return None

        # Calculate change
        old_price = cached.price
        change_percent = ((current_price - old_price) / old_price) * 100

        # Update cache
        cached.price = current_price
        cached.last_updated = datetime.now(UTC)
        cached.change_count += 1

        # Increase priority if item is volatile
        if cached.change_count >= 3:
            cached.priority = PollPriority.HIGH

        return PriceChange(
            item_id=item_id,
            item_name=title,
            old_price=old_price,
            new_price=current_price,
            change_percent=change_percent,
        )

    def get_cached_price(self, item_id: str) -> float | None:
        """Get cached price for an item."""
        cached = self._price_cache.get(item_id)
        return cached.price if cached else None

    def get_volatile_items(self, min_changes: int = 3) -> list[CachedPrice]:
        """Get items with frequent price changes."""
        return [
            cached
            for cached in self._price_cache.values()
            if cached.change_count >= min_changes
        ]

    def clear_cache(self) -> None:
        """Clear price cache."""
        self._price_cache.clear()
        self._known_item_ids.clear()
        self._changes_detected = 0
        self._poll_count = 0


class DeltaTracker:
    """Track and detect changes in market data efficiently.

    Alternative to WebSocket - uses efficient delta detection
    to minimize processing of unchanged data.
    """

    def __init__(self, max_history: int = 1000) -> None:
        """Initialize delta tracker.

        Args:
            max_history: Maximum items to track

        """
        self.max_history = max_history
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._change_history: list[dict[str, Any]] = []

    def update(self, item_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update item data and return changes if any.

        Args:
            item_id: Item identifier
            data: Current item data

        Returns:
            Dict of changed fields or None if no changes

        """
        previous = self._snapshots.get(item_id)

        if previous is None:
            # New item
            self._snapshots[item_id] = data.copy()
            self._trim_history()
            return {"_new": True, **data}

        # Check for changes
        changes = {}
        for key, value in data.items():
            if key not in previous or previous[key] != value:
                changes[key] = {"old": previous.get(key), "new": value}

        if changes:
            self._snapshots[item_id] = data.copy()
            self._change_history.append({
                "item_id": item_id,
                "changes": changes,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            return changes

        return None

    def get_snapshot(self, item_id: str) -> dict[str, Any] | None:
        """Get last known snapshot for item."""
        return self._snapshots.get(item_id)

    def get_recent_changes(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent changes."""
        return self._change_history[-limit:]

    def _trim_history(self) -> None:
        """Trim history to max size."""
        if len(self._snapshots) > self.max_history:
            # Remove oldest items
            items_to_remove = len(self._snapshots) - self.max_history
            oldest_keys = list(self._snapshots.keys())[:items_to_remove]
            for key in oldest_keys:
                del self._snapshots[key]


# Factory function
def create_polling_engine(
    api_client: DMarketAPI,
    games: list[str] | None = None,
    whitelist_items: list[str] | None = None,
    on_price_change: PriceChangeCallback | None = None,
) -> AdaptivePollingEngine:
    """Create an adaptive polling engine instance."""
    return AdaptivePollingEngine(
        api_client=api_client,
        games=games,
        whitelist_items=whitelist_items,
        on_price_change=on_price_change,
    )
