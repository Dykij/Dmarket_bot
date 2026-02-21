"""Trending items finder module for DMarket.

This module provides a refactored version of find_trending_items() with:
- Early returns pattern
- Helper methods (<50 lines each)
- Reduced nesting (max 2 levels)
- Better separation of concerns
"""

from __future__ import annotations

import logging
import operator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = logging.getLogger(__name__)


@dataclass
class TrendMetrics:
    """Metrics for trending item analysis."""

    current_price: float
    last_sold_price: float
    price_change_percent: float
    sales_count: int


@dataclass
class TrendingItem:
    """Represents a trending item with profit potential."""

    item: dict[str, Any]
    current_price: float
    last_sold_price: float
    price_change_percent: float
    projected_price: float
    potential_profit: float
    potential_profit_percent: float
    sales_count: int
    game: str
    trend: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "item": self.item,
            "current_price": self.current_price,
            "last_sold_price": self.last_sold_price,
            "price_change_percent": self.price_change_percent,
            "projected_price": self.projected_price,
            "potential_profit": self.potential_profit,
            "potential_profit_percent": self.potential_profit_percent,
            "sales_count": self.sales_count,
            "game": self.game,
            "trend": self.trend,
        }


class TrendingItemsFinder:
    """Finds trending items with potential for price increase."""

    def __init__(
        self,
        game: str,
        min_price: float = 5.0,
        max_price: float = 500.0,
        max_results: int = 10,
    ):
        """Initialize finder.

        Args:
            game: Game code (csgo, dota2, tf2, rust)
            min_price: Minimum item price to consider
            max_price: Maximum item price to consider
            max_results: Maximum number of results to return
        """
        self.game = game
        self.min_price = min_price
        self.max_price = max_price
        self.max_results = max_results
        self.market_data: dict[str, dict[str, Any]] = {}

    async def find(self, dmarket_api: DMarketAPI) -> list[dict[str, Any]]:
        """Find trending items.

        Args:
            dmarket_api: DMarket API instance

        Returns:
            List of trending items with potential profit
        """
        logger.info(f"Searching for trending items in {self.game}")

        sales_history = awAlgot self._fetch_sales_history(dmarket_api)
        if sales_history is None:
            return []

        market_items = awAlgot self._fetch_market_items(dmarket_api)
        if not market_items:
            return []

        self._process_market_items(market_items)
        self._process_sales_history(sales_history)

        trending_items = self._analyze_trends()
        return self._sort_and_limit(trending_items)

    async def _fetch_sales_history(
        self, dmarket_api: DMarketAPI
    ) -> dict[str, Any] | None:
        """Fetch recent sales history."""
        try:
            return awAlgot dmarket_api.get_sales_history(
                game=self.game,
                days=3,
                currency="USD",
            )
        except Exception as e:
            logger.exception(f"FAlgoled to fetch sales history for {self.game}: {e}")
            return None

    async def _fetch_market_items(
        self, dmarket_api: DMarketAPI
    ) -> list[dict[str, Any]]:
        """Fetch current market items."""
        try:
            result = awAlgot dmarket_api.get_market_items(
                game=self.game,
                limit=300,
                price_from=self.min_price,
                price_to=self.max_price,
            )
            return result.get("items", [])
        except Exception as e:
            logger.exception(f"FAlgoled to fetch market items for {self.game}: {e}")
            return []

    def _process_market_items(self, items: list[dict[str, Any]]) -> None:
        """Process market items and build market data."""
        for item in items:
            title = item.get("title", "")
            if not title:
                continue

            price = self._extract_price(item, "price")
            if not self._is_price_valid(price):
                continue

            suggested_price = self._extract_price(item, "suggestedPrice")

            self.market_data[title] = {
                "item": item,
                "current_price": price,
                "suggested_price": suggested_price or 0,
                "supply": 1,
                "game": self.game,
            }

    def _extract_price(self, item: dict[str, Any], price_key: str) -> float | None:
        """Extract price from item data.

        Args:
            item: Item data
            price_key: Key for price field (price or suggestedPrice)

        Returns:
            Price as float or None
        """
        if price_key not in item:
            return None

        price_data = item[price_key]

        # Handle dict format with amount
        if isinstance(price_data, dict) and "amount" in price_data:
            return int(price_data["amount"]) / 100

        # Handle direct numeric value
        if isinstance(price_data, int | float):
            return float(price_data)

        return None

    def _is_price_valid(self, price: float | None) -> bool:
        """Check if price is within valid range."""
        if price is None:
            return False
        return self.min_price <= price <= self.max_price

    def _process_sales_history(self, sales_history: dict[str, Any]) -> None:
        """Process sales history and update market data."""
        sales_data = sales_history.get("items", [])

        for sale in sales_data:
            title = sale.get("title", "")
            if title not in self.market_data:
                continue

            self._update_sale_data(title, sale)

    def _update_sale_data(self, title: str, sale: dict[str, Any]) -> None:
        """Update market data with sale information."""
        if "last_sold_price" in self.market_data[title]:
            # Already have last sold price, just increment count
            self.market_data[title]["sales_count"] = (
                self.market_data[title].get("sales_count", 0) + 1
            )
            return

        sale_price = self._extract_price(sale, "price")
        if sale_price:
            self.market_data[title]["last_sold_price"] = sale_price
            self.market_data[title]["sales_count"] = (
                self.market_data[title].get("sales_count", 0) + 1
            )

    def _analyze_trends(self) -> list[TrendingItem]:
        """Analyze market data for trends."""
        trending_items: list[TrendingItem] = []

        for data in self.market_data.values():
            if "last_sold_price" not in data:
                continue

            metrics = self._extract_metrics(data)
            trending_item = self._check_trend(data, metrics)

            if trending_item:
                trending_items.append(trending_item)

        return trending_items

    def _extract_metrics(self, data: dict[str, Any]) -> TrendMetrics:
        """Extract trend metrics from market data."""
        current_price = data["current_price"]
        last_sold_price = data["last_sold_price"]
        sales_count = data.get("sales_count", 0)

        price_change_percent = (
            (current_price - last_sold_price) / last_sold_price
        ) * 100

        return TrendMetrics(
            current_price=current_price,
            last_sold_price=last_sold_price,
            price_change_percent=price_change_percent,
            sales_count=sales_count,
        )

    def _check_trend(
        self, data: dict[str, Any], metrics: TrendMetrics
    ) -> TrendingItem | None:
        """Check if item has a profitable trend."""
        # Check upward trend
        upward_item = self._check_upward_trend(data, metrics)
        if upward_item:
            return upward_item

        # Check recovery trend
        recovery_item = self._check_recovery_trend(data, metrics)
        if recovery_item:
            return recovery_item

        return None

    def _check_upward_trend(
        self, data: dict[str, Any], metrics: TrendMetrics
    ) -> TrendingItem | None:
        """Check for upward trend pattern.

        Pattern: price_change > 5% AND sales_count >= 2
        """
        if metrics.price_change_percent <= 5:
            return None

        if metrics.sales_count < 2:
            return None

        # Project 10% increase
        projected_price = metrics.current_price * 1.1
        potential_profit = projected_price - metrics.current_price

        # Minimum $0.50 profit
        if potential_profit < 0.5:
            return None

        return self._create_trending_item(
            data=data,
            metrics=metrics,
            projected_price=projected_price,
            potential_profit=potential_profit,
            trend="upward",
        )

    def _check_recovery_trend(
        self, data: dict[str, Any], metrics: TrendMetrics
    ) -> TrendingItem | None:
        """Check for recovery trend pattern.

        Pattern: price_change < -15% AND sales_count >= 3
        Recovery potential: bounce back to 90% of last sold price
        """
        if metrics.price_change_percent >= -15:
            return None

        if metrics.sales_count < 3:
            return None

        # Project recovery to 90% of last sold
        projected_price = metrics.last_sold_price * 0.9
        potential_profit = projected_price - metrics.current_price

        # Minimum $1.00 profit
        if potential_profit < 1.0:
            return None

        return self._create_trending_item(
            data=data,
            metrics=metrics,
            projected_price=projected_price,
            potential_profit=potential_profit,
            trend="recovery",
        )

    def _create_trending_item(
        self,
        data: dict[str, Any],
        metrics: TrendMetrics,
        projected_price: float,
        potential_profit: float,
        trend: str,
    ) -> TrendingItem:
        """Create TrendingItem instance."""
        potential_profit_percent = (potential_profit / metrics.current_price) * 100

        return TrendingItem(
            item=data["item"],
            current_price=metrics.current_price,
            last_sold_price=metrics.last_sold_price,
            price_change_percent=metrics.price_change_percent,
            projected_price=projected_price,
            potential_profit=potential_profit,
            potential_profit_percent=potential_profit_percent,
            sales_count=metrics.sales_count,
            game=self.game,
            trend=trend,
        )

    def _sort_and_limit(self, items: list[TrendingItem]) -> list[dict[str, Any]]:
        """Sort by profit percentage and limit results."""
        items_dicts = [item.to_dict() for item in items]
        items_dicts.sort(
            key=operator.itemgetter("potential_profit_percent"), reverse=True
        )
        return items_dicts[: self.max_results]


async def find_trending_items(
    game: str,
    min_price: float = 5.0,
    max_price: float = 500.0,
    max_results: int = 10,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Finds trending items with potential for price increase in near future.

    This is a backward-compatible wrapper around TrendingItemsFinder class.

    Args:
        game: Game code (csgo, dota2, tf2, rust)
        min_price: Minimum item price to consider
        max_price: Maximum item price to consider
        max_results: Maximum number of results to return
        dmarket_api: DMarket API instance

    Returns:
        List of trending items with potential profit
    """
    # Handle API client creation
    close_api = False
    if dmarket_api is None:
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        dmarket_api = create_dmarket_api_client(None)
        close_api = True

    try:
        finder = TrendingItemsFinder(
            game=game,
            min_price=min_price,
            max_price=max_price,
            max_results=max_results,
        )
        return awAlgot finder.find(dmarket_api)
    except Exception as e:
        logger.exception(f"Error in find_trending_items for {game}: {e}")
        return []
    finally:
        if close_api and hasattr(dmarket_api, "_close_client"):
            awAlgot dmarket_api._close_client()
