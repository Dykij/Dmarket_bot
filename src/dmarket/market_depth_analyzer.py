"""Market Depth Analyzer - refactored from market_analysis.py.

This module provides market depth analysis functionality with improved
code readability following Phase 2 refactoring guidelines.

Author: DMarket Telegram Bot
Created: 2026-01-01
Phase: 2 (Week 3-4)
"""

import os
import time
from typing import Any

import structlog
from dotenv import load_dotenv

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.rate_limiter import RateLimiter

# Load environment variables
load_dotenv()

# Get API keys from environment
DMARKET_PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY", "")
DMARKET_SECRET_KEY = os.getenv("DMARKET_SECRET_KEY", "")
DMARKET_API_URL = os.getenv("DMARKET_API_URL", "https://api.dmarket.com")

# Create rate limiter
rate_limiter = RateLimiter(is_authorized=True)

logger = structlog.get_logger(__name__)


class MarketDepthAnalyzer:
    """Analyzes market depth for items using DMarket API v1.1.0."""

    def __init__(self, dmarket_api: DMarketAPI | None = None):
        """Initialize analyzer with optional API client.

        Args:
            dmarket_api: DMarket API client instance or None to create new
        """
        self.dmarket_api = dmarket_api
        self._owns_client = dmarket_api is None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            self.dmarket_api = DMarketAPI(
                DMARKET_PUBLIC_KEY,
                DMARKET_SECRET_KEY,
                DMARKET_API_URL,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        if self._owns_client and hasattr(self.dmarket_api, "_close_client"):
            try:
                await self.dmarket_api._close_client()
            except Exception as e:
                logger.warning("client_cleanup_error", error=str(e))

    async def analyze(
        self,
        game: str = "csgo",
        items: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Analyze market depth for given items.

        Args:
            game: Game code (csgo, dota2, rust, tf2)
            items: List of item titles (if None, fetches popular items)
            limit: Maximum number of items to analyze

        Returns:
            Dictionary with market depth analysis

        Example:
            >>> async with MarketDepthAnalyzer() as analyzer:
            ...     result = await analyzer.analyze(
            ...         game="csgo", items=["AK-47 | Redline (Field-Tested)"]
            ...     )
            ...     print(f"Liquidity: {result['summary']['average_liquidity_score']}")
        """
        logger.info("starting_market_depth_analysis", game=game)

        try:
            item_titles = await self._get_item_titles(game, items, limit)

            if not item_titles:
                return self._empty_result(game)

            aggregated = await self._fetch_aggregated_prices(game, item_titles)

            if not aggregated:
                return self._empty_result(game)

            depth_analysis = self._analyze_items(aggregated)
            summary = self._calculate_summary(depth_analysis)

            logger.info(
                "market_depth_analysis_complete",
                items_count=len(depth_analysis),
                avg_liquidity=summary.get("average_liquidity_score", 0),
            )

            return {
                "game": game,
                "timestamp": int(time.time()),
                "items_analyzed": len(depth_analysis),
                "market_depth": depth_analysis,
                "summary": summary,
            }

        except Exception as e:
            logger.exception("market_depth_analysis_failed", error=str(e))
            return self._error_result(game, str(e))

    async def _get_item_titles(self, game: str, items: list[str] | None, limit: int) -> list[str]:
        """Get item titles to analyze.

        Returns provided items or fetches popular items from market.
        """
        if items is not None:
            return items

        await rate_limiter.wait_if_needed("market")
        market_items = await self.dmarket_api.get_market_items(
            game=game,
            limit=limit,
            sort_by="best_deal",
        )

        titles = [item.get("title") for item in market_items.get("items", []) if item.get("title")][
            :limit
        ]

        if not titles:
            logger.warning("no_items_found_for_analysis", game=game)

        return titles

    async def _fetch_aggregated_prices(self, game: str, titles: list[str]) -> dict[str, Any] | None:
        """Fetch aggregated prices from DMarket API."""
        await rate_limiter.wait_if_needed("market")

        aggregated = await self.dmarket_api.get_aggregated_prices_bulk(
            game=game,
            titles=titles,
            limit=len(titles),
        )

        if not aggregated or "aggregatedPrices" not in aggregated:
            logger.warning("aggregated_prices_fetch_failed", game=game)
            return None

        return aggregated

    def _analyze_items(self, aggregated: dict[str, Any]) -> list[dict[str, Any]]:
        """Analyze each item and calculate depth metrics."""
        depth_analysis = []

        for price_data in aggregated["aggregatedPrices"]:
            item_analysis = self._analyze_single_item(price_data)
            depth_analysis.append(item_analysis)

        return depth_analysis

    def _analyze_single_item(self, price_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze single item depth metrics."""
        title = price_data["title"]
        order_count = price_data.get("orderCount", 0)
        offer_count = price_data.get("offerCount", 0)
        order_price = float(price_data.get("orderBestPrice", 0)) / 100
        offer_price = float(price_data.get("offerBestPrice", 0)) / 100

        total_volume = order_count + offer_count
        buy_pressure = self._calculate_pressure(order_count, total_volume)
        sell_pressure = self._calculate_pressure(offer_count, total_volume)

        spread = offer_price - order_price
        spread_percent = self._calculate_spread_percent(spread, order_price)

        liquidity_score = min(100, total_volume * 2)

        market_balance, balance_description = self._determine_market_balance(
            buy_pressure, sell_pressure
        )

        return {
            "title": title,
            "order_count": order_count,
            "offer_count": offer_count,
            "total_volume": total_volume,
            "order_price": order_price,
            "offer_price": offer_price,
            "spread": spread,
            "spread_percent": spread_percent,
            "buy_pressure": buy_pressure,
            "sell_pressure": sell_pressure,
            "liquidity_score": liquidity_score,
            "market_balance": market_balance,
            "balance_description": balance_description,
            "arbitrage_potential": spread_percent > 5.0,
        }

    def _calculate_pressure(self, count: int, total: int) -> float:
        """Calculate buy or sell pressure as percentage."""
        if total <= 0:
            return 0.0
        return (count / total) * 100

    def _calculate_spread_percent(self, spread: float, order_price: float) -> float:
        """Calculate spread as percentage of order price."""
        if order_price <= 0:
            return 0.0
        return (spread / order_price) * 100

    def _determine_market_balance(
        self, buy_pressure: float, sell_pressure: float
    ) -> tuple[str, str]:
        """Determine market balance from buy/sell pressure.

        Returns:
            Tuple of (balance_type, description)
        """
        if buy_pressure > 60:
            return "buyer_dominated", "Преобладают покупатели"

        if sell_pressure > 60:
            return "seller_dominated", "Преобладают продавцы"

        return "balanced", "Сбалансированный рынок"

    def _calculate_summary(self, depth_analysis: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate summary statistics from depth analysis."""
        if not depth_analysis:
            return {}

        avg_liquidity = sum(item["liquidity_score"] for item in depth_analysis) / len(
            depth_analysis
        )

        avg_spread = sum(item["spread_percent"] for item in depth_analysis) / len(depth_analysis)

        high_liquidity_count = sum(1 for item in depth_analysis if item["liquidity_score"] >= 50)

        arbitrage_opportunities = sum(1 for item in depth_analysis if item["arbitrage_potential"])

        market_health = self._determine_market_health(avg_liquidity)

        return {
            "items_analyzed": len(depth_analysis),
            "average_liquidity_score": round(avg_liquidity, 1),
            "average_spread_percent": round(avg_spread, 2),
            "high_liquidity_items": high_liquidity_count,
            "arbitrage_opportunities": arbitrage_opportunities,
            "market_health": market_health,
        }

    def _determine_market_health(self, avg_liquidity: float) -> str:
        """Determine market health from average liquidity score."""
        if avg_liquidity >= 75:
            return "excellent"
        if avg_liquidity >= 50:
            return "good"
        if avg_liquidity >= 25:
            return "moderate"
        return "poor"

    def _empty_result(self, game: str) -> dict[str, Any]:
        """Return empty result structure."""
        return {
            "game": game,
            "items_analyzed": 0,
            "market_depth": [],
            "summary": {},
        }

    def _error_result(self, game: str, error: str) -> dict[str, Any]:
        """Return error result structure."""
        return {
            "game": game,
            "items_analyzed": 0,
            "market_depth": [],
            "summary": {},
            "error": error,
        }


# Backward compatibility wrapper
async def analyze_market_depth(
    game: str = "csgo",
    items: list[str] | None = None,
    limit: int = 50,
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Analyze market depth (legacy function wrapper).

    This function provides backward compatibility with the original implementation.
    New code should use MarketDepthAnalyzer class directly.

    Args:
        game: Game code (csgo, dota2, rust, tf2)
        items: List of item titles (if None, fetches popular items)
        limit: Maximum number of items to analyze
        dmarket_api: DMarket API client instance or None

    Returns:
        Dictionary with market depth analysis

    Example:
        >>> result = await analyze_market_depth(game="csgo", limit=10)
        >>> print(f"Average liquidity: {result['summary']['average_liquidity_score']}")
    """
    async with MarketDepthAnalyzer(dmarket_api=dmarket_api) as analyzer:
        return await analyzer.analyze(game=game, items=items, limit=limit)
