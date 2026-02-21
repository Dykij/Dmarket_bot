"""
Sales History Module for Trend Analysis and Liquidity Assessment.

This module integrates with DMarket's /trade-aggregator/v1/last-sales endpoint
to analyze historical sales data and assess item liquidity and price trends.
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class SalesStats(BaseModel):
    """Statistics calculated from sales history."""

    title: str
    game_id: str
    total_sales: int = Field(ge=0)
    avg_price_usd: float = Field(ge=0)
    min_price_usd: float = Field(ge=0)
    max_price_usd: float = Field(ge=0)
    price_volatility: float = Field(ge=0, description="Standard deviation")
    turnover_rate: float = Field(ge=0, description="Sales per day over analysis period")
    trend: str = Field(description="up, down, or stable", pattern="^(up|down|stable)$")
    last_sale_date: datetime | None = None
    is_liquid: bool = Field(description="Meets minimum liquidity threshold")


class SalesHistoryAnalyzer:
    """Analyzes sales history to determine item liquidity and trends."""

    def __init__(
        self,
        api_client: Any,
        min_sales_for_liquid: int = 5,
        analysis_days: int = 7,
        cache_ttl: int = 3600,
    ):
        """Initialize sales history analyzer.

        Args:
            api_client: DMarket API client instance
            min_sales_for_liquid: Minimum sales in period to consider liquid
            analysis_days: Days of history to analyze
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self.api = api_client
        self.min_sales_for_liquid = min_sales_for_liquid
        self.analysis_days = analysis_days
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[SalesStats, datetime]] = {}

        logger.info(
            "sales_history_analyzer_initialized",
            min_sales=min_sales_for_liquid,
            days=analysis_days,
        )

    async def get_sales_history(
        self,
        title: str,
        game_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch sales history from DMarket API.

        Args:
            title: Item title
            game_id: Game identifier
            filters: Optional filters (exterior, float, etc.)
            limit: Max number of sales (up to 20)

        Returns:
            List of sale records
        """
        try:
            # Use /trade-aggregator/v1/last-sales endpoint
            params = {
                "title": title,
                "gameId": game_id,
                "limit": min(limit, 20),
                "txOperationType": "Offer",  # Sell-side history
            }

            if filters:
                # Add filters like exterior[], float[], etc.
                for key, value in filters.items():
                    if isinstance(value, list):
                        params[f"{key}[]"] = value
                    else:
                        params[key] = value

            response = await self.api.get_last_sales(**params)

            if not response or "sales" not in response:
                logger.warning(
                    "no_sales_history",
                    title=title,
                    game_id=game_id,
                )
                return []

            sales = response["sales"]
            logger.debug(
                "fetched_sales_history",
                title=title,
                count=len(sales),
            )
            return sales

        except Exception as e:
            logger.error(
                "sales_history_fetch_error",
                title=title,
                error=str(e),
                exc_info=True,
            )
            return []

    async def analyze_sales(
        self,
        title: str,
        game_id: str,
        filters: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> SalesStats | None:
        """Analyze sales history and compute statistics.

        Args:
            title: Item title
            game_id: Game identifier
            filters: Optional filters
            use_cache: Whether to use cached results

        Returns:
            SalesStats or None if insufficient data
        """
        cache_key = f"{game_id}:{title}:{filters!s}"

        # Check cache
        if use_cache and cache_key in self._cache:
            stats, cached_at = self._cache[cache_key]
            age = (datetime.now() - cached_at).total_seconds()
            if age < self.cache_ttl:
                logger.debug("sales_stats_from_cache", title=title)
                return stats

        # Fetch sales
        sales = await self.get_sales_history(title, game_id, filters)

        if not sales or len(sales) < 2:
            logger.warning(
                "insufficient_sales_data",
                title=title,
                count=len(sales) if sales else 0,
            )
            return None

        # Calculate statistics
        try:
            prices = [
                float(sale.get("price", {}).get("USD", 0)) / 100 for sale in sales
            ]
            dates = [
                datetime.fromisoformat(sale.get("date", datetime.now().isoformat()))
                for sale in sales
            ]

            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)

            # Calculate volatility (standard deviation)
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            volatility = variance**0.5

            # Calculate turnover rate
            date_range = (max(dates) - min(dates)).days or 1
            turnover_rate = len(sales) / date_range

            # Determine trend (simple linear regression)
            if len(prices) >= 3:
                n = len(prices)
                x = list(range(n))
                x_mean = sum(x) / n
                y_mean = avg_price

                numerator = sum(
                    (x[i] - x_mean) * (prices[i] - y_mean) for i in range(n)
                )
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

                if denominator > 0:
                    slope = numerator / denominator
                    if slope > 0.01:
                        trend = "up"
                    elif slope < -0.01:
                        trend = "down"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            # Assess liquidity
            is_liquid = (
                len(sales) >= self.min_sales_for_liquid
                and turnover_rate >= 0.5  # At least 0.5 sales/day
            )

            stats = SalesStats(
                title=title,
                game_id=game_id,
                total_sales=len(sales),
                avg_price_usd=round(avg_price, 2),
                min_price_usd=round(min_price, 2),
                max_price_usd=round(max_price, 2),
                price_volatility=round(volatility, 2),
                turnover_rate=round(turnover_rate, 2),
                trend=trend,
                last_sale_date=max(dates) if dates else None,
                is_liquid=is_liquid,
            )

            # Cache results
            self._cache[cache_key] = (stats, datetime.now())

            logger.info(
                "sales_analysis_complete",
                title=title,
                total_sales=stats.total_sales,
                trend=stats.trend,
                is_liquid=stats.is_liquid,
            )

            return stats

        except Exception as e:
            logger.error(
                "sales_analysis_error",
                title=title,
                error=str(e),
                exc_info=True,
            )
            return None

    async def filter_by_liquidity(
        self,
        opportunities: list[dict[str, Any]],
        game_id: str,
    ) -> list[dict[str, Any]]:
        """Filter arbitrage opportunities by liquidity.

        Args:
            opportunities: List of arbitrage opportunities
            game_id: Game identifier

        Returns:
            Filtered list with only liquid items
        """
        if not opportunities:
            return []

        logger.info(
            "filtering_by_liquidity",
            count=len(opportunities),
            game_id=game_id,
        )

        tasks = []
        for opp in opportunities:
            title = opp.get("title", "")
            if title:
                tasks.append(self.analyze_sales(title, game_id))

        # Analyze all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        filtered = []
        for opp, result in zip(opportunities, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "liquidity_check_failed",
                    title=opp.get("title"),
                    error=str(result),
                )
                continue

            if result and result.is_liquid:
                # Enhance opportunity with sales stats
                opp["sales_stats"] = {
                    "avg_price": result.avg_price_usd,
                    "volatility": result.price_volatility,
                    "trend": result.trend,
                    "turnover_rate": result.turnover_rate,
                }
                filtered.append(opp)

        logger.info(
            "liquidity_filtering_complete",
            original=len(opportunities),
            filtered=len(filtered),
            removed=len(opportunities) - len(filtered),
        )

        return filtered

    def clear_cache(self) -> None:
        """Clear the sales stats cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("sales_cache_cleared", count=count)

    async def get_trending_items(
        self,
        game_id: str,
        titles: list[str],
        trend_type: str = "up",
    ) -> list[SalesStats]:
        """Get items with specific trend.

        Args:
            game_id: Game identifier
            titles: List of item titles to analyze
            trend_type: Type of trend (up, down, stable)

        Returns:
            List of SalesStats matching the trend
        """
        tasks = [self.analyze_sales(title, game_id) for title in titles]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        trending = []
        for result in results:
            if isinstance(result, SalesStats) and result.trend == trend_type:
                trending.append(result)

        logger.info(
            "trending_items_found",
            game_id=game_id,
            trend_type=trend_type,
            count=len(trending),
        )

        return trending
