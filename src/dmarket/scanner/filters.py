"""Item filtering for arbitrage scanner.

This module provides filtering functionality for:
- Blacklist/whitelist filtering
- Item name pattern matching
- Game-specific filters
- Price-based filtering

Works with ItemFilters class from item_filters.py.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.item_filters import ItemFilters

logger = logging.getLogger(__name__)


class ScannerFilters:
    """Filter manager for arbitrage scanner.

    Provides methods to filter items based on various criteria.
    Integrates with ItemFilters for blacklist/whitelist support.
    """

    def __init__(self, item_filters: ItemFilters | None = None) -> None:
        """Initialize scanner filters.

        Args:
            item_filters: Optional ItemFilters instance for blacklist/whitelist
        """
        self._item_filters = item_filters

    @property
    def item_filters(self) -> ItemFilters | None:
        """Get current item filters."""
        return self._item_filters

    @item_filters.setter
    def item_filters(self, value: ItemFilters | None) -> None:
        """Set item filters."""
        self._item_filters = value

    def is_item_allowed(self, item_name: str) -> bool:
        """Check if item is allowed by filters.

        Args:
            item_name: Item name to check

        Returns:
            True if item is allowed, False if blacklisted
        """
        if self._item_filters is None:
            return True
        return self._item_filters.is_item_allowed(item_name)

    def is_item_blacklisted(self, item_name: str) -> bool:
        """Check if item is blacklisted.

        Args:
            item_name: Item name to check

        Returns:
            True if item is blacklisted
        """
        if self._item_filters is None:
            return False
        return self._item_filters.is_item_blacklisted(item_name)

    def apply_filters(
        self,
        items: list[dict[str, Any]],
        game: str | None = None,
    ) -> list[dict[str, Any]]:
        """Apply all filters to item list.

        Args:
            items: List of items to filter
            game: Optional game code for game-specific filters

        Returns:
            Filtered list of items
        """
        if not items:
            return items

        if self._item_filters is None:
            return items

        filtered = self._item_filters.filter_items(items, game)
        removed_count = len(items) - len(filtered)

        if removed_count > 0:
            logger.info(
                "Items filtered",
                extra={
                    "original_count": len(items),
                    "filtered_count": len(filtered),
                    "removed_count": removed_count,
                    "game": game,
                },
            )

        return filtered

    def filter_by_price(
        self,
        items: list[dict[str, Any]],
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> list[dict[str, Any]]:
        """Filter items by price range.

        Args:
            items: List of items to filter
            min_price: Minimum price in USD (inclusive)
            max_price: Maximum price in USD (inclusive)

        Returns:
            Filtered list of items
        """
        if min_price is None and max_price is None:
            return items

        filtered = []
        for item in items:
            price = self._get_item_price(item)
            if price is None:
                continue

            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue

            filtered.append(item)

        return filtered

    def filter_by_profit(
        self,
        items: list[dict[str, Any]],
        min_profit_percent: float | None = None,
        max_profit_percent: float | None = None,
    ) -> list[dict[str, Any]]:
        """Filter items by profit percentage.

        Args:
            items: List of items with profit data
            min_profit_percent: Minimum profit % (inclusive)
            max_profit_percent: Maximum profit % (inclusive)

        Returns:
            Filtered list of items
        """
        if min_profit_percent is None and max_profit_percent is None:
            return items

        filtered = []
        for item in items:
            profit = item.get("profit_percent", 0.0)

            if min_profit_percent is not None and profit < min_profit_percent:
                continue
            if max_profit_percent is not None and profit > max_profit_percent:
                continue

            filtered.append(item)

        return filtered

    @staticmethod
    def _get_item_price(item: dict[str, Any]) -> float | None:
        """Extract price from item dictionary.

        Args:
            item: Item dictionary

        Returns:
            Price in USD or None if not found
        """
        # Try different price field formats
        price = item.get("price")
        if isinstance(price, dict):
            # Price as dict with USD key
            usd_price = price.get("USD", price.get("usd"))
            if usd_price is not None:
                try:
                    # Price might be in cents
                    return float(usd_price) / 100 if float(usd_price) > 1000 else float(usd_price)
                except (ValueError, TypeError):
                    return None
        elif price is not None:
            try:
                return float(price)
            except (ValueError, TypeError):
                return None

        # Try buy_price field
        buy_price = item.get("buy_price")
        if buy_price is not None:
            try:
                return float(buy_price)
            except (ValueError, TypeError):
                pass

        return None


def create_filter_key(
    game: str,
    level: str,
    extra_filters: dict[str, Any] | None = None,
) -> str:
    """Create a filter key for caching filtered results.

    Args:
        game: Game code
        level: Arbitrage level
        extra_filters: Additional filter parameters

    Returns:
        Filter key string
    """
    parts = [f"filter:{game}:{level}"]
    if extra_filters:
        for k, v in sorted(extra_filters.items()):
            parts.append(f"{k}={v}")
    return ":".join(parts)
