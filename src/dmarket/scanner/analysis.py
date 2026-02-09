"""Arbitrage analysis and profit calculation.

This module provides analysis functionality for:
- Profit calculation with commission consideration
- Item analysis and scoring
- Statistics aggregation
- Best opportunity finding

Used by ArbitrageScanner for item analysis.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# DMarket commission rate (7%)
DMARKET_COMMISSION = 0.07

# Minimum profit thresholds by level
MIN_PROFIT_THRESHOLDS = {
    "boost": 1.0,
    "standard": 5.0,
    "medium": 5.0,
    "advanced": 10.0,
    "pro": 20.0,
}


def calculate_profit(
    buy_price: float,
    sell_price: float,
    commission: float = DMARKET_COMMISSION,
) -> tuple[float, float]:
    """Calculate profit from arbitrage trade.

    Args:
        buy_price: Purchase price in USD
        sell_price: Selling price in USD
        commission: Commission rate (default: 7%)

    Returns:
        Tuple of (absolute_profit, profit_percent)
    """
    if buy_price <= 0:
        return 0.0, 0.0

    # Calculate net sell price after commission
    net_sell_price = sell_price * (1 - commission)

    # Calculate profit
    absolute_profit = net_sell_price - buy_price
    profit_percent = (absolute_profit / buy_price) * 100

    return round(absolute_profit, 2), round(profit_percent, 2)


def calculate_roi(
    total_investment: float,
    total_profit: float,
) -> float:
    """Calculate return on investment.

    Args:
        total_investment: Total amount invested
        total_profit: Total profit earned

    Returns:
        ROI percentage
    """
    if total_investment <= 0:
        return 0.0
    return round((total_profit / total_investment) * 100, 2)


def analyze_item(
    item: dict[str, Any],
    min_profit_percent: float = 5.0,
    max_profit_percent: float = 100.0,
) -> dict[str, Any] | None:
    """Analyze single item for arbitrage opportunity.

    Args:
        item: Item data dictionary
        min_profit_percent: Minimum profit % to consider
        max_profit_percent: Maximum profit % to consider

    Returns:
        Analysis result dict or None if not profitable
    """
    buy_price = _extract_price(item, "price", "buy_price")
    sell_price = _extract_price(item, "suggestedPrice", "suggested_price", "sell_price")

    if buy_price is None or sell_price is None:
        return None

    if buy_price <= 0 or sell_price <= buy_price:
        return None

    absolute_profit, profit_percent = calculate_profit(buy_price, sell_price)

    # Check profit thresholds
    if profit_percent < min_profit_percent or profit_percent > max_profit_percent:
        return None

    return {
        "item_id": item.get("itemId", item.get("id", "")),
        "title": item.get("title", item.get("name", "")),
        "buy_price": buy_price,
        "sell_price": sell_price,
        "absolute_profit": absolute_profit,
        "profit_percent": profit_percent,
        "game": item.get("gameId", item.get("game", "")),
        "extra_data": item.get("extra", {}),
    }


def score_opportunity(opportunity: dict[str, Any]) -> float:
    """Calculate score for arbitrage opportunity.

    Higher score = better opportunity.

    Args:
        opportunity: Analyzed opportunity dict

    Returns:
        Score value (higher is better)
    """
    profit_percent = opportunity.get("profit_percent", 0.0)
    absolute_profit = opportunity.get("absolute_profit", 0.0)
    buy_price = opportunity.get("buy_price", 1.0)

    # Base score from profit percentage
    score = profit_percent * 1.0

    # Bonus for absolute profit (scaled by price)
    if buy_price > 0:
        profit_factor = min(absolute_profit / buy_price, 1.0)
        score += profit_factor * 10

    # Penalty for very high profit (potential price error)
    if profit_percent > 50:
        score *= 0.8
    elif profit_percent > 80:
        score *= 0.5

    return round(score, 2)


def find_best_opportunities(
    opportunities: list[dict[str, Any]],
    limit: int = 10,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Find best arbitrage opportunities from list.

    Args:
        opportunities: List of analyzed opportunities
        limit: Maximum number to return
        min_score: Minimum score threshold

    Returns:
        List of best opportunities sorted by score
    """
    # Score all opportunities
    scored = []
    for opp in opportunities:
        score = score_opportunity(opp)
        if score >= min_score:
            scored.append({**opp, "score": score})

    # Sort by score descending
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)

    return scored[:limit]


def aggregate_statistics(
    opportunities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate statistics from opportunities.

    Args:
        opportunities: List of opportunities

    Returns:
        Statistics dictionary
    """
    if not opportunities:
        return {
            "count": 0,
            "total_potential_profit": 0.0,
            "avg_profit_percent": 0.0,
            "min_profit_percent": 0.0,
            "max_profit_percent": 0.0,
            "total_investment_needed": 0.0,
        }

    profits = [o.get("profit_percent", 0.0) for o in opportunities]
    absolute_profits = [o.get("absolute_profit", 0.0) for o in opportunities]
    buy_prices = [o.get("buy_price", 0.0) for o in opportunities]

    return {
        "count": len(opportunities),
        "total_potential_profit": round(sum(absolute_profits), 2),
        "avg_profit_percent": round(sum(profits) / len(profits), 2),
        "min_profit_percent": round(min(profits), 2),
        "max_profit_percent": round(max(profits), 2),
        "total_investment_needed": round(sum(buy_prices), 2),
    }


def _extract_price(item: dict[str, Any], *keys: str) -> float | None:
    """Extract price from item using multiple possible keys.

    Args:
        item: Item dictionary
        keys: Possible keys to check

    Returns:
        Price value or None
    """
    for key in keys:
        value = item.get(key)
        if value is not None:
            price = _parse_price(value)
            if price is not None:
                return price
    return None


def _parse_price(value: Any) -> float | None:
    """Parse price value from various formats.

    Args:
        value: Price value (int, float, str, or dict)

    Returns:
        Float price or None
    """
    if isinstance(value, dict):
        # Price dict format: {"USD": "1000"}
        usd = value.get("USD", value.get("usd"))
        if usd is not None:
            return _parse_price(usd)
        return None

    if isinstance(value, (int, float)):
        # Assume cents if > 1000
        if value > 1000:
            return round(value / 100, 2)
        return round(float(value), 2)

    if isinstance(value, str):
        try:
            num = float(value)
            if num > 1000:
                return round(num / 100, 2)
            return round(num, 2)
        except ValueError:
            return None

    return None


class AnalysisStats:
    """Statistics tracker for arbitrage analysis."""

    def __init__(self) -> None:
        """Initialize statistics tracker."""
        self._scans = 0
        self._items_analyzed = 0
        self._opportunities_found = 0
        self._by_level: dict[str, dict[str, int]] = {}
        self._by_game: dict[str, dict[str, int]] = {}

    def record_scan(
        self,
        level: str,
        game: str,
        items_analyzed: int,
        opportunities_found: int,
    ) -> None:
        """Record scan statistics.

        Args:
            level: Arbitrage level
            game: Game code
            items_analyzed: Number of items analyzed
            opportunities_found: Number of opportunities found
        """
        self._scans += 1
        self._items_analyzed += items_analyzed
        self._opportunities_found += opportunities_found

        # Track by level
        if level not in self._by_level:
            self._by_level[level] = {"scans": 0, "opportunities": 0}
        self._by_level[level]["scans"] += 1
        self._by_level[level]["opportunities"] += opportunities_found

        # Track by game
        if game not in self._by_game:
            self._by_game[game] = {"scans": 0, "opportunities": 0}
        self._by_game[game]["scans"] += 1
        self._by_game[game]["opportunities"] += opportunities_found

    def get_stats(self) -> dict[str, Any]:
        """Get all statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_scans": self._scans,
            "total_items_analyzed": self._items_analyzed,
            "total_opportunities_found": self._opportunities_found,
            "by_level": self._by_level.copy(),
            "by_game": self._by_game.copy(),
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._scans = 0
        self._items_analyzed = 0
        self._opportunities_found = 0
        self._by_level.clear()
        self._by_game.clear()
