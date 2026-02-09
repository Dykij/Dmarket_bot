"""Watchlist Module for tracking favorite items.

Allows users to create and manage watchlists of items they want to monitor.

Features:
- Create multiple watchlists per user
- Add/remove items from watchlists
- Track price changes for watchlisted items
- Get alerts when watchlisted items reach target prices
- Export watchlists

Usage:
    ```python
    from src.portfolio.watchlist import WatchlistManager

    manager = WatchlistManager(user_id=123)

    # Create watchlist
    wl = await manager.create_watchlist("High-value items")

    # Add item
    await manager.add_item(wl.id, "AK-47 | Redline", target_price=50.0)

    # Check prices
    updates = await manager.check_prices(dmarket_api)
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class PriceDirection(StrEnum):
    """Price movement direction."""

    UP = "up"
    DOWN = "down"
    UNCHANGED = "unchanged"


@dataclass
class WatchlistItem:
    """An item in a watchlist."""

    item_id: str
    item_name: str
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    target_price: Decimal | None = None  # Target price to alert
    last_price: Decimal | None = None
    last_checked: datetime | None = None
    notes: str | None = None
    game: str = "csgo"
    marketplace: str = "dmarket"

    # Price history (last 10 prices)
    price_history: list[tuple[datetime, Decimal]] = field(default_factory=list)

    def update_price(self, new_price: Decimal) -> PriceDirection:
        """Update price and return direction.

        Args:
            new_price: New current price

        Returns:
            Price direction
        """
        old_price = self.last_price
        self.last_price = new_price
        self.last_checked = datetime.now(UTC)

        # Add to history
        self.price_history.append((datetime.now(UTC), new_price))
        if len(self.price_history) > 10:
            self.price_history = self.price_history[-10:]

        if old_price is None:
            return PriceDirection.UNCHANGED
        if new_price > old_price:
            return PriceDirection.UP
        if new_price < old_price:
            return PriceDirection.DOWN
        return PriceDirection.UNCHANGED

    def is_target_reached(self) -> bool:
        """Check if target price is reached.

        Returns:
            True if current price <= target price
        """
        if self.target_price is None or self.last_price is None:
            return False
        return self.last_price <= self.target_price

    @property
    def price_change(self) -> Decimal | None:
        """Get price change from first recorded price.

        Returns:
            Price change or None
        """
        if len(self.price_history) < 2:
            return None
        first_price = self.price_history[0][1]
        last_price = self.price_history[-1][1]
        return last_price - first_price

    @property
    def price_change_percent(self) -> Decimal | None:
        """Get percentage price change.

        Returns:
            Price change percent or None
        """
        if len(self.price_history) < 2:
            return None
        first_price = self.price_history[0][1]
        if first_price == 0:
            return None
        change = self.price_change
        if change is None:
            return None
        return (change / first_price) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "added_at": self.added_at.isoformat(),
            "target_price": str(self.target_price) if self.target_price else None,
            "last_price": str(self.last_price) if self.last_price else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "price_change": str(self.price_change) if self.price_change else None,
            "price_change_percent": str(round(self.price_change_percent, 2)) if self.price_change_percent else None,
            "is_target_reached": self.is_target_reached(),
            "game": self.game,
            "notes": self.notes,
        }


@dataclass
class Watchlist:
    """A user's watchlist."""

    watchlist_id: str
    user_id: int
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    items: dict[str, WatchlistItem] = field(default_factory=dict)
    is_default: bool = False
    description: str | None = None

    def add_item(
        self,
        item_name: str,
        target_price: float | Decimal | None = None,
        game: str = "csgo",
        notes: str | None = None,
    ) -> WatchlistItem:
        """Add item to watchlist.

        Args:
            item_name: Item name
            target_price: Optional target price
            game: Game
            notes: Optional notes

        Returns:
            Added item
        """
        item_id = f"wi_{uuid4().hex[:8]}"
        item = WatchlistItem(
            item_id=item_id,
            item_name=item_name,
            target_price=Decimal(str(target_price)) if target_price else None,
            game=game,
            notes=notes,
        )
        self.items[item_id] = item
        self.updated_at = datetime.now(UTC)
        return item

    def remove_item(self, item_id: str) -> bool:
        """Remove item from watchlist.

        Args:
            item_id: Item ID

        Returns:
            True if removed
        """
        if item_id in self.items:
            del self.items[item_id]
            self.updated_at = datetime.now(UTC)
            return True
        return False

    def get_item_by_name(self, item_name: str) -> WatchlistItem | None:
        """Get item by name.

        Args:
            item_name: Item name

        Returns:
            Item or None
        """
        for item in self.items.values():
            if item.item_name.lower() == item_name.lower():
                return item
        return None

    @property
    def item_count(self) -> int:
        """Get number of items."""
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "watchlist_id": self.watchlist_id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "item_count": self.item_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "items": [item.to_dict() for item in self.items.values()],
        }


@dataclass
class PriceUpdate:
    """Price update notification."""

    item: WatchlistItem
    old_price: Decimal | None
    new_price: Decimal
    direction: PriceDirection
    target_reached: bool = False


class WatchlistManager:
    """Manages user watchlists."""

    MAX_WATCHLISTS_PER_USER = 10
    MAX_ITEMS_PER_WATCHLIST = 100

    def __init__(self, user_id: int | None = None) -> None:
        """Initialize watchlist manager.

        Args:
            user_id: Default user ID
        """
        self.default_user_id = user_id

        # Storage (replace with database in production)
        self._watchlists: dict[str, Watchlist] = {}
        self._user_watchlists: dict[int, list[str]] = {}

    def create_watchlist(
        self,
        name: str,
        user_id: int | None = None,
        description: str | None = None,
        is_default: bool = False,
    ) -> Watchlist | None:
        """Create a new watchlist.

        Args:
            name: Watchlist name
            user_id: User ID
            description: Optional description
            is_default: Is default watchlist

        Returns:
            Created watchlist or None if limit reached
        """
        user_id = user_id or self.default_user_id
        if user_id is None:
            return None

        # Check limit
        user_lists = self._user_watchlists.get(user_id, [])
        if len(user_lists) >= self.MAX_WATCHLISTS_PER_USER:
            logger.warning("watchlist_limit_reached", user_id=user_id)
            return None

        # Create watchlist
        watchlist_id = f"wl_{uuid4().hex[:12]}"
        watchlist = Watchlist(
            watchlist_id=watchlist_id,
            user_id=user_id,
            name=name,
            description=description,
            is_default=is_default,
        )

        # If default, unset others
        if is_default:
            for wl_id in user_lists:
                if wl_id in self._watchlists:
                    self._watchlists[wl_id].is_default = False

        # Store
        self._watchlists[watchlist_id] = watchlist
        if user_id not in self._user_watchlists:
            self._user_watchlists[user_id] = []
        self._user_watchlists[user_id].append(watchlist_id)

        logger.info(
            "watchlist_created",
            watchlist_id=watchlist_id,
            user_id=user_id,
            name=name,
        )

        return watchlist

    def get_watchlist(self, watchlist_id: str) -> Watchlist | None:
        """Get watchlist by ID.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Watchlist or None
        """
        return self._watchlists.get(watchlist_id)

    def get_user_watchlists(self, user_id: int | None = None) -> list[Watchlist]:
        """Get all watchlists for a user.

        Args:
            user_id: User ID

        Returns:
            List of watchlists
        """
        user_id = user_id or self.default_user_id
        if user_id is None:
            return []

        watchlist_ids = self._user_watchlists.get(user_id, [])
        return [
            self._watchlists[wl_id]
            for wl_id in watchlist_ids
            if wl_id in self._watchlists
        ]

    def get_default_watchlist(self, user_id: int | None = None) -> Watchlist | None:
        """Get default watchlist for user.

        Args:
            user_id: User ID

        Returns:
            Default watchlist or None
        """
        for wl in self.get_user_watchlists(user_id):
            if wl.is_default:
                return wl

        # Return first if no default
        watchlists = self.get_user_watchlists(user_id)
        return watchlists[0] if watchlists else None

    def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            True if deleted
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return False

        # Remove from user's list
        user_id = watchlist.user_id
        if user_id in self._user_watchlists:
            self._user_watchlists[user_id] = [
                wl_id for wl_id in self._user_watchlists[user_id]
                if wl_id != watchlist_id
            ]

        del self._watchlists[watchlist_id]
        logger.info("watchlist_deleted", watchlist_id=watchlist_id)
        return True

    def add_item(
        self,
        watchlist_id: str,
        item_name: str,
        target_price: float | Decimal | None = None,
        game: str = "csgo",
        notes: str | None = None,
    ) -> WatchlistItem | None:
        """Add item to watchlist.

        Args:
            watchlist_id: Watchlist ID
            item_name: Item name
            target_price: Target price
            game: Game
            notes: Notes

        Returns:
            Added item or None
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return None

        if len(watchlist.items) >= self.MAX_ITEMS_PER_WATCHLIST:
            logger.warning("watchlist_items_limit_reached", watchlist_id=watchlist_id)
            return None

        # Check if already in watchlist
        existing = watchlist.get_item_by_name(item_name)
        if existing:
            return existing

        return watchlist.add_item(
            item_name=item_name,
            target_price=target_price,
            game=game,
            notes=notes,
        )

    def remove_item(self, watchlist_id: str, item_id: str) -> bool:
        """Remove item from watchlist.

        Args:
            watchlist_id: Watchlist ID
            item_id: Item ID

        Returns:
            True if removed
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return False
        return watchlist.remove_item(item_id)

    def update_item_target(
        self,
        watchlist_id: str,
        item_id: str,
        target_price: float | Decimal | None,
    ) -> bool:
        """Update item target price.

        Args:
            watchlist_id: Watchlist ID
            item_id: Item ID
            target_price: New target price

        Returns:
            True if updated
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist or item_id not in watchlist.items:
            return False

        watchlist.items[item_id].target_price = (
            Decimal(str(target_price)) if target_price else None
        )
        return True

    async def check_prices(
        self,
        prices: dict[str, Decimal],
        user_id: int | None = None,
    ) -> list[PriceUpdate]:
        """Check and update prices for watchlisted items.

        Args:
            prices: Dict of item_name -> current_price
            user_id: Optional user ID filter

        Returns:
            List of price updates
        """
        updates = []

        for watchlist in self.get_user_watchlists(user_id):
            for item in watchlist.items.values():
                current_price = prices.get(item.item_name)
                if current_price is None:
                    continue

                old_price = item.last_price
                direction = item.update_price(current_price)

                # Only report changes
                if direction != PriceDirection.UNCHANGED or item.is_target_reached():
                    updates.append(PriceUpdate(
                        item=item,
                        old_price=old_price,
                        new_price=current_price,
                        direction=direction,
                        target_reached=item.is_target_reached(),
                    ))

        return updates

    def get_all_item_names(self, user_id: int | None = None) -> set[str]:
        """Get all unique item names across watchlists.

        Args:
            user_id: Optional user ID filter

        Returns:
            Set of item names
        """
        names = set()
        for watchlist in self.get_user_watchlists(user_id):
            names.update(item.item_name for item in watchlist.items.values())
        return names

    def get_items_at_target(self, user_id: int | None = None) -> list[WatchlistItem]:
        """Get items that reached their target price.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of items at target
        """
        items = []
        for watchlist in self.get_user_watchlists(user_id):
            for item in watchlist.items.values():
                if item.is_target_reached():
                    items.append(item)
        return items

    def export_watchlist(self, watchlist_id: str) -> dict[str, Any] | None:
        """Export watchlist data.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Watchlist data or None
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return None
        return watchlist.to_dict()

    def get_stats(self, user_id: int | None = None) -> dict[str, Any]:
        """Get watchlist statistics.

        Args:
            user_id: User ID

        Returns:
            Statistics dict
        """
        watchlists = self.get_user_watchlists(user_id)
        total_items = sum(wl.item_count for wl in watchlists)
        at_target = len(self.get_items_at_target(user_id))

        return {
            "watchlist_count": len(watchlists),
            "total_items": total_items,
            "items_at_target": at_target,
            "unique_items": len(self.get_all_item_names(user_id)),
        }


# Global instance
_watchlist_manager: WatchlistManager | None = None


def get_watchlist_manager(user_id: int | None = None) -> WatchlistManager:
    """Get watchlist manager instance."""
    global _watchlist_manager
    if _watchlist_manager is None:
        _watchlist_manager = WatchlistManager(user_id=user_id)
    return _watchlist_manager


def init_watchlist_manager(user_id: int | None = None) -> WatchlistManager:
    """Initialize watchlist manager."""
    global _watchlist_manager
    _watchlist_manager = WatchlistManager(user_id=user_id)
    return _watchlist_manager
