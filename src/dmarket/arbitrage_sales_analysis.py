"""Module for analyzing historical sales data for DMarket arbitrage.

This module provides tools for analyzing:
- Historical sales trends
- Price fluctuations
- Item sales volume
- Time-to-sell estimates for different items
- Profit potential based on historical data

Based on DMarket API documentation: https://docs.dmarket.com/v1/swagger.html
"""

import datetime
import logging
import operator
import time
from typing import Any

import pandas as pd

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SalesAnalyzer:
    """Analyzer for historical sales data on DMarket."""

    def __init__(self, api_client: DMarketAPI | None = None) -> None:
        """Initialize Sales Analyzer.

        Args:
            api_client: DMarket API client (optional)

        """
        self.api_client = api_client
        self._sales_cache = {}  # Cache for sales data
        self._cache_ttl = 3600  # Cache TTL (1 hour)
        self._rate_limiter = RateLimiter(is_authorized=True)

        # Safe defaults for volume analysis
        # very_high >= 3, high >= 1.5, medium >= 0.5, low < 0.5
        self.very_high_volume_threshold = 3  # Sales per day
        self.high_volume_threshold = 1.5  # Sales per day
        self.medium_volume_threshold = 0.5  # Sales per day
        self.min_sample_size = 3  # Minimum for analysis

    async def get_api_client(self) -> DMarketAPI:
        """Get or create API client.

        Returns:
            DMarket API client

        """
        if not self.api_client:
            import os

            self.api_client = DMarketAPI(
                public_key=os.environ.get("DMARKET_PUBLIC_KEY", ""),
                secret_key=os.environ.get("DMARKET_SECRET_KEY", ""),
                api_url=os.environ.get("DMARKET_API_URL", "https://api.dmarket.com"),
            )
        return self.api_client

    async def get_item_sales_history(
        self,
        item_name: str,
        game: str = "csgo",
        days: int = 30,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Get sales history for a specific item.

        Args:
            item_name: Item name
            game: Game name (csgo, dota2, etc.)
            days: Number of days to look back
            use_cache: Whether to use cached data

        Returns:
            List of sales data

        """
        cache_key = f"{game}:{item_name}:{days}"

        # Check cache first
        if use_cache and cache_key in self._sales_cache:
            cached_data, cache_time = self._sales_cache[cache_key]
            if time.time() - cache_time < self._cache_ttl:
                logger.debug(f"Using cached sales data for {item_name}")
                return cached_data

        # Get API client
        api_client = await self.get_api_client()

        try:
            # First we need to get the item ID for the given item name
            items_response = await api_client.get_market_items(
                game=game,
                title=item_name,
                limit=1,
            )

            if "items" not in items_response or not items_response["items"]:
                logger.warning(f"Item not found: {item_name}")
                return {"sales": []}

            item_id = items_response["items"][0].get("itemId")
            if not item_id:
                logger.warning(f"Item ID not found for: {item_name}")
                return {"sales": []}

            # Calculate date range
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=days)

            # Format dates for API
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            # Get sales history from API
            # Endpoint: /exchange/v1/sales/history (based on DMarket docs)
            sales_data = await api_client._request(
                method="GET",
                path="/exchange/v1/sales/history",
                params={
                    "gameId": game,
                    "itemId": item_id,
                    "from": start_date_str,
                    "to": end_date_str,
                },
            )

            # Process sales data
            sales = []
            if "sales" in sales_data:
                sales = sales_data["sales"]

            # Cache the results
            self._sales_cache[cache_key] = (sales, time.time())

            return sales

        except Exception as e:
            logger.exception(f"Error getting sales history for {item_name}: {e}")
            return {"sales": []}

    async def analyze_sales_volume(
        self,
        item_name: str,
        game: str = "csgo",
        days: int = 30,
    ) -> dict[str, Any]:
        """Analyze sales volume for an item.

        Args:
            item_name: Item name
            game: Game name
            days: Number of days to analyze

        Returns:
            Sales volume statistics

        """
        # Get sales history
        sales = await self.get_item_sales_history(item_name, game, days)

        # Handle both list and dict responses
        if isinstance(sales, dict):
            sales_list = sales.get("sales", [])
        else:
            sales_list = sales or []

        if not sales_list:
            return {
                "sales_count": 0,
                "sales_per_day": 0,
                "volume_category": "low",
                "is_liquid": False,
                "price_range": {"min": 0, "max": 0},
            }

        # Calculate sales per day
        sales_count = len(sales_list)
        sales_per_day = sales_count / min(
            days,
            30,
        )  # In case we have less data than requested

        # Categorize volume
        volume_category = "low"
        if sales_per_day >= self.very_high_volume_threshold:
            volume_category = "very_high"
        elif sales_per_day >= self.high_volume_threshold:
            volume_category = "high"
        elif sales_per_day >= self.medium_volume_threshold:
            volume_category = "medium"

        # Determine if item is liquid (sells quickly)
        is_liquid = sales_per_day >= self.medium_volume_threshold

        # Calculate price range from sales
        prices = [
            float(sale.get("price", {}).get("amount", 0)) / 100 for sale in sales_list
        ]
        price_range = {
            "min": round(min(prices), 2) if prices else 0,
            "max": round(max(prices), 2) if prices else 0,
        }

        return {
            "sales_count": sales_count,
            "sales_per_day": round(sales_per_day, 2),
            "volume_category": volume_category,
            "is_liquid": is_liquid,
            "price_range": price_range,
        }

    async def estimate_time_to_sell(
        self,
        item_name: str,
        game: str = "csgo",
        current_price: float | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Estimate time needed to sell an item at the current price.

        Args:
            item_name: Item name
            current_price: Current selling price
            game: Game name
            days: Number of days to analyze

        Returns:
            Time to sell estimation

        """
        # Get sales history
        sales = await self.get_item_sales_history(item_name, game, days)

        # Check if we have enough sales data
        sales_list = sales if isinstance(sales, list) else sales.get("sales", [])
        has_sales = sales and (isinstance(sales, list) or sales.get("sales"))
        if not has_sales or len(sales_list) < self.min_sample_size:
            return {
                "estimated_days": None,
                "estimated_hours": None,
                "confidence": "very_low",
                "message": "Insufficient sales data for estimation",
                "recommendation": "unknown",
            }

        # Convert sales data to pandas DataFrame for analysis
        try:
            sales_df = pd.DataFrame(sales_list)

            # Process timestamps and prices
            # Handle both 'date' and 'timestamp' fields
            if "date" in sales_df.columns:
                sales_df["timestamp"] = pd.to_datetime(sales_df["date"], unit="s")
            elif "timestamp" in sales_df.columns:
                sales_df["timestamp"] = pd.to_datetime(sales_df["timestamp"])

            # Extract price from nested structure
            sales_df["price"] = sales_df["price"].apply(
                lambda x: (
                    float(x.get("amount", 0)) / 100
                    if isinstance(x, dict)
                    else float(x) / 100
                ),
            )

            # Sort by price
            sales_df = sales_df.sort_values("price")

            # Find percentage of sales at or above current price
            if current_price is not None:
                price_percentile = (sales_df["price"] >= current_price).mean()
            else:
                # If no current price, use median
                price_percentile = 0.5

            # Estimate time to sell based on volume and price percentile
            volume_stats = await self.analyze_sales_volume(item_name, game, days)
            sales_per_day = volume_stats["sales_per_day"]

            if sales_per_day == 0:
                estimated_days = None
                confidence = "very_low"
                message = "No recent sales data avAlgolable"
            else:
                # Adjust days based on price percentile
                if price_percentile > 0:
                    # Higher percentile means longer time to sell
                    estimated_days = round(1 / (sales_per_day * price_percentile), 1)
                else:
                    # No sales at this price or higher
                    estimated_days = None

                # Determine confidence level
                if len(sales) >= 20 and sales_per_day >= 1:
                    confidence = "high"
                elif len(sales) >= 10:
                    confidence = "medium"
                else:
                    confidence = "low"

                if estimated_days is not None:
                    if estimated_days < 1:
                        message = "Likely to sell within a day"
                    elif estimated_days < 3:
                        message = f"Likely to sell within {estimated_days} days"
                    elif estimated_days < 7:
                        message = "May take about a week to sell"
                    else:
                        message = f"May take {int(estimated_days)} days or more to sell"
                else:
                    message = "Price may be too high based on historical data"

            # Convert estimated_days to hours
            estimated_hours = (
                estimated_days * 24 if estimated_days is not None else None
            )

            # Generate recommendation
            if estimated_days is not None and estimated_days < 3:
                recommendation = "good"
            elif estimated_days is not None and estimated_days < 7:
                recommendation = "fAlgor"
            else:
                recommendation = "poor"

            return {
                "estimated_days": estimated_days,
                "estimated_hours": (
                    round(estimated_hours, 1) if estimated_hours is not None else None
                ),
                "confidence": confidence,
                "message": message,
                "recommendation": recommendation,
                "price_percentile": round(price_percentile, 2),
                "sales_analyzed": len(sales),
            }

        except Exception as e:
            logger.exception(f"Error estimating time to sell for {item_name}: {e}")
            return {
                "estimated_days": None,
                "estimated_hours": None,
                "confidence": "very_low",
                "message": f"Error analyzing sales data: {e!s}",
                "recommendation": "unknown",
            }

    async def analyze_price_trends(
        self,
        item_name: str,
        game: str = "csgo",
        days: int = 30,
    ) -> dict[str, Any]:
        """Analyze price trends for an item.

        Args:
            item_name: Item name
            game: Game name
            days: Number of days to analyze

        Returns:
            Price trend analysis

        """
        # Get sales history
        sales = await self.get_item_sales_history(item_name, game, days)

        # Insufficient sales data
        if sales is None or len(sales) < self.min_sample_size:
            return {
                "trend": "unknown",
                "trend_direction": "stable",
                "price_change_percent": None,
                "volatility": None,
                "average_price": None,
                "message": "Insufficient sales data for analysis",
            }

        # Convert sales data to pandas DataFrame for analysis
        try:
            sales_df = pd.DataFrame(sales)

            # Process timestamps and prices
            # Handle both 'date' (from test data) and 'timestamp' fields
            if "date" in sales_df.columns:
                sales_df["timestamp"] = pd.to_datetime(sales_df["date"], unit="s")
            elif "timestamp" in sales_df.columns:
                sales_df["timestamp"] = pd.to_datetime(sales_df["timestamp"])
            else:
                raise KeyError("Neither 'date' nor 'timestamp' field found")

            # Handle price extraction from different formats
            sales_df["price"] = sales_df["price"].apply(
                lambda x: (
                    float(x.get("amount", 0)) / 100
                    if isinstance(x, dict)
                    else float(x) / 100
                ),
            )

            # Sort by timestamp
            sales_df = sales_df.sort_values("timestamp")

            # Calculate daily averages
            sales_df["date"] = sales_df["timestamp"].dt.date
            daily_avg = sales_df.groupby("date")["price"].mean().reset_index()

            if len(daily_avg) < 2:
                return {
                    "trend": "stable",
                    "price_change_percent": 0,
                    "volatility": 0,
                    "message": "Insufficient data points for trend analysis",
                }

            # Calculate trend metrics
            first_price = daily_avg["price"].iloc[0]
            last_price = daily_avg["price"].iloc[-1]
            price_change = last_price - first_price
            price_change_percent = (
                (price_change / first_price * 100) if first_price > 0 else 0
            )

            # Calculate volatility (standard deviation as percentage of mean)
            mean_price = daily_avg["price"].mean()
            std_price = daily_avg["price"].std()
            volatility = (std_price / mean_price * 100) if mean_price > 0 else 0

            # Determine trend
            if abs(price_change_percent) < 5:
                trend = "stable"
                trend_direction = "stable"
                message = "Price has been relatively stable"
            elif price_change_percent >= 15:
                trend = "strong_upward"
                trend_direction = "rising"
                message = "Price is rising significantly"
            elif price_change_percent >= 5:
                trend = "upward"
                trend_direction = "rising"
                message = "Price has an upward trend"
            elif price_change_percent <= -15:
                trend = "strong_downward"
                trend_direction = "falling"
                message = "Price is falling significantly"
            elif price_change_percent <= -5:
                trend = "downward"
                trend_direction = "falling"
                message = "Price has a downward trend"
            else:
                trend = "slight_fluctuation"
                trend_direction = "stable"
                message = "Price shows slight fluctuations"

            # Adjust message based on volatility
            if volatility > 20:
                message += " with high volatility"
            elif volatility > 10:
                message += " with moderate volatility"

            return {
                "trend": trend,
                "trend_direction": trend_direction,
                "price_change_percent": round(price_change_percent, 2),
                "price_change": round(price_change, 2),
                "volatility": round(volatility, 2),
                "average_price": round(mean_price, 2),
                "first_price": round(first_price, 2),
                "last_price": round(last_price, 2),
                "min_price": round(daily_avg["price"].min(), 2),
                "max_price": round(daily_avg["price"].max(), 2),
                "message": message,
            }

        except Exception as e:
            logger.exception(f"Error analyzing price trends for {item_name}: {e}")
            return {
                "trend": "unknown",
                "price_change_percent": None,
                "volatility": None,
                "message": f"Error analyzing price data: {e!s}",
            }

    async def evaluate_arbitrage_potential(
        self,
        item_name: str,
        buy_price: float,
        sell_price: float,
        game: str = "csgo",
        days: int = 30,
    ) -> dict[str, Any]:
        """Evaluate arbitrage potential based on historical data.

        Args:
            item_name: Item name
            buy_price: Potential buying price
            sell_price: Potential selling price
            game: Game name
            days: Number of days to analyze

        Returns:
            Arbitrage potential evaluation

        """
        # Calculate raw profit
        raw_profit = sell_price - buy_price
        profit_percent = (raw_profit / buy_price * 100) if buy_price > 0 else 0

        # Get volume analysis
        volume_stats = await self.analyze_sales_volume(item_name, game, days)

        # Get time to sell estimation
        time_to_sell = await self.estimate_time_to_sell(
            item_name,
            sell_price,
            game,
            days,
        )

        # Get price trend analysis
        price_trends = await self.analyze_price_trends(item_name, game, days)

        # Calculate risk level
        risk_level = "high"  # Default to high risk

        if volume_stats["is_liquid"] and time_to_sell["estimated_days"] is not None:
            if (
                time_to_sell["estimated_days"] < 2
                and price_trends["trend"] != "strong_downward"
            ):
                risk_level = "low"
            elif time_to_sell["estimated_days"] < 5 and price_trends["trend"] not in {
                "strong_downward",
                "downward",
            }:
                risk_level = "medium"

        # Calculate ROI (Return on Investment) taking into account time
        daily_roi = None
        if (
            time_to_sell["estimated_days"] is not None
            and time_to_sell["estimated_days"] > 0
        ):
            daily_roi = profit_percent / time_to_sell["estimated_days"]

        # Determine overall rating
        rating = 0  # 0-10 scale

        # Base rating on profit
        if profit_percent > 50:
            rating += 3
        elif profit_percent > 25:
            rating += 2
        elif profit_percent > 10:
            rating += 1

        # Adjust based on volume
        if volume_stats["volume_category"] == "high":
            rating += 3
        elif volume_stats["volume_category"] == "medium":
            rating += 2
        elif volume_stats["volume_category"] == "low":
            rating += 1

        # Adjust based on time to sell
        if time_to_sell["estimated_days"] is not None:
            if time_to_sell["estimated_days"] < 1:
                rating += 3
            elif time_to_sell["estimated_days"] < 3:
                rating += 2
            elif time_to_sell["estimated_days"] < 7:
                rating += 1

        # Adjust based on price trend
        if price_trends["trend"] in {"strong_upward", "upward"}:
            rating += 1
        elif price_trends["trend"] == "strong_downward":
            rating -= 1

        # Cap rating at 0-10
        rating = max(0, min(10, rating))

        # Generate summary message
        if rating >= 8:
            summary = (
                "Excellent arbitrage opportunity with high potential ROI and low risk"
            )
        elif rating >= 6:
            summary = "Good arbitrage opportunity with solid potential returns"
        elif rating >= 4:
            summary = "Average opportunity with moderate risk and returns"
        elif rating >= 2:
            summary = "Below average opportunity with higher risk or lower returns"
        else:
            summary = "Poor arbitrage opportunity with high risk or minimal returns"

        return {
            "rating": rating,
            "raw_profit": round(raw_profit, 2),
            "profit_percent": round(profit_percent, 2),
            "expected_profit": round(raw_profit, 2),
            "profit_percentage": round(profit_percent, 2),
            "risk_level": risk_level,
            "estimated_sell_time_hours": time_to_sell.get("estimated_hours"),
            "recommendation": "recommended" if rating >= 6 else "not recommended",
            "daily_roi": round(daily_roi, 2) if daily_roi is not None else None,
            "volume": volume_stats,
            "time_to_sell": time_to_sell,
            "price_trends": price_trends,
            "summary": summary,
        }

    async def batch_analyze_items(
        self,
        game: str,
        items: list[dict[str, Any]],
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Batch analyze multiple items for arbitrage potential.

        Args:
            game: Game name
            items: List of items with title and buy_price
            days: Number of days to analyze

        Returns:
            List of analysis results

        """
        results = []

        for item in items:
            item_name = item.get("title", "")
            buy_price = item.get("buy_price", 0)

            if not item_name or buy_price <= 0:
                continue

            try:
                # Get sales volume
                volume_stats = await self.analyze_sales_volume(
                    item_name=item_name,
                    game=game,
                    days=days,
                )

                # Get price trends
                price_trends = await self.analyze_price_trends(
                    item_name=item_name,
                    game=game,
                    days=days,
                )

                results.append(
                    {
                        "title": item_name,
                        "sales_volume": volume_stats.get("sales_count", 0),
                        "price_trend": price_trends.get("trend", "unknown"),
                        "liquidity": volume_stats.get("volume_category", "low"),
                        "is_liquid": volume_stats.get("is_liquid", False),
                    },
                )

            except Exception as e:
                logger.exception(f"Error analyzing {item_name}: {e}")
                # Continue processing other items

        return results

    async def find_best_arbitrage_opportunities(
        self,
        game: str = "csgo",
        min_profit_percent: float = 5.0,
        max_risk_level: str = "medium",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find the best arbitrage opportunities.

        Args:
            game: Game name
            min_profit_percent: Minimum profit percentage
            max_risk_level: Maximum acceptable risk level (low, medium, high)
            limit: Maximum number of results to return

        Returns:
            Sorted list of best opportunities

        """
        # Get API client
        api = await self.get_api_client()

        # Get market items
        try:
            items_response = await api.get_market_items(
                game=game,
                limit=100,
            )

            if "items" not in items_response or not items_response["items"]:
                return []

            items = items_response["items"]

        except Exception as e:
            logger.exception(f"Error getting market items: {e}")
            return []

        # Filter and sort opportunities
        opportunities = []

        # Define risk levels
        risk_levels = {"low": 0, "medium": 1, "high": 2}
        max_risk_value = risk_levels.get(max_risk_level, 1)

        for item in items:
            item_name = item.get("title", "")
            if not item_name:
                continue

            # Get current price
            current_price = 0
            if "price" in item and isinstance(item["price"], dict):
                current_price = float(item["price"].get("amount", 0)) / 100

            # Assume sell price is 10% higher for analysis
            sell_price = current_price * 1.1

            try:
                analysis = await self.evaluate_arbitrage_potential(
                    item_name=item_name,
                    buy_price=current_price,
                    sell_price=sell_price,
                    game=game,
                )

                # Filter by profit percentage and risk level
                if (
                    analysis.get("profit_percentage", 0) >= min_profit_percent
                    and risk_levels.get(analysis.get("risk_level", "high"), 2)
                    <= max_risk_value
                ):
                    opportunities.append(
                        {
                            "title": item_name,
                            "expected_profit": analysis.get("expected_profit", 0),
                            "profit_percentage": analysis.get("profit_percentage", 0),
                            "risk_level": analysis.get("risk_level", "high"),
                            "estimated_sell_time_hours": analysis.get(
                                "estimated_sell_time_hours"
                            ),
                            "recommendation": analysis.get("recommendation", ""),
                        },
                    )

            except Exception as e:
                logger.exception(f"Error analyzing {item_name}: {e}")
                # Continue processing other items

        # Sort by profit percentage (descending)
        opportunities.sort(key=operator.itemgetter("profit_percentage"), reverse=True)

        # Limit results
        return opportunities[:limit]


async def batch_analyze_items(
    game: str,
    items: list[dict[str, Any]],
    days: int = 30,
) -> list[dict[str, Any]]:
    """Batch analyze multiple items for arbitrage potential.

    Args:
        game: Game name
        items: List of items with title and buy_price
        days: Number of days to analyze

    Returns:
        List of analysis results

    """
    analyzer = SalesAnalyzer()
    results = []

    for item in items:
        item_name = item.get("title", "")
        buy_price = item.get("buy_price", 0)

        if not item_name or buy_price <= 0:
            continue

        try:
            # Get sales volume
            volume_stats = await analyzer.analyze_sales_volume(
                item_name=item_name,
                game=game,
                days=days,
            )

            # Get price trends
            price_trends = await analyzer.analyze_price_trends(
                item_name=item_name,
                game=game,
                days=days,
            )

            results.append(
                {
                    "title": item_name,
                    "sales_volume": volume_stats.get("sales_count", 0),
                    "price_trend": price_trends.get("trend", "unknown"),
                    "liquidity": volume_stats.get("volume_category", "low"),
                    "is_liquid": volume_stats.get("is_liquid", False),
                },
            )

        except Exception as e:
            logger.exception(f"Error analyzing {item_name}: {e}")
            # Continue processing other items

    return results


async def find_best_arbitrage_opportunities(
    game: str = "csgo",
    min_profit_percent: float = 5.0,
    max_risk_level: str = "medium",
    limit: int = 10,
    api_client: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Find the best arbitrage opportunities.

    Args:
        game: Game name
        min_profit_percent: Minimum profit percentage
        max_risk_level: Maximum acceptable risk level (low, medium, high)
        limit: Maximum number of results to return
        api_client: DMarket API client (optional)

    Returns:
        Sorted list of best opportunities

    """
    analyzer = SalesAnalyzer(api_client)

    # Get API client
    api = await analyzer.get_api_client()

    # Get market items
    try:
        items_response = await api.get_market_items(
            game=game,
            limit=100,
        )

        if "items" not in items_response or not items_response["items"]:
            return []

        items = items_response["items"]

    except Exception as e:
        logger.exception(f"Error getting market items: {e}")
        return []

    # Filter and sort opportunities
    opportunities = []

    # Define risk levels
    risk_levels = {"low": 0, "medium": 1, "high": 2}
    max_risk_value = risk_levels.get(max_risk_level, 1)

    for item in items:
        item_name = item.get("title", "")
        if not item_name:
            continue

        # Get current price
        current_price = 0
        if "price" in item and isinstance(item["price"], dict):
            current_price = float(item["price"].get("amount", 0)) / 100

        # Assume sell price is 10% higher for analysis
        sell_price = current_price * 1.1

        try:
            analysis = await analyzer.evaluate_arbitrage_potential(
                item_name=item_name,
                buy_price=current_price,
                sell_price=sell_price,
                game=game,
            )

            # Filter by profit percentage and risk level
            if (
                analysis.get("profit_percentage", 0) >= min_profit_percent
                and risk_levels.get(analysis.get("risk_level", "high"), 2)
                <= max_risk_value
            ):
                opportunities.append(
                    {
                        "title": item_name,
                        "expected_profit": analysis.get("expected_profit", 0),
                        "profit_percentage": analysis.get("profit_percentage", 0),
                        "risk_level": analysis.get("risk_level", "high"),
                        "estimated_sell_time_hours": analysis.get(
                            "estimated_sell_time_hours"
                        ),
                        "recommendation": analysis.get("recommendation", ""),
                    },
                )

        except Exception as e:
            logger.exception(f"Error analyzing {item_name}: {e}")
            # Continue processing other items

    # Sort by profit percentage (descending)
    opportunities.sort(key=operator.itemgetter("profit_percentage"), reverse=True)

    # Limit results
    return opportunities[:limit]


async def analyze_item_liquidity(
    item_id: str,
    api_client: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Analyze item liquidity based on sales data.

    Args:
        item_id: Item ID to analyze
        api_client: DMarket API client (optional)

    Returns:
        Dictionary with liquidity analysis

    """
    analyzer = SalesAnalyzer(api_client)

    try:
        # Get sales volume analysis
        volume_data = await analyzer.analyze_sales_volume(item_id)

        if not volume_data or "error" in volume_data:
            return {
                "error": True,
                "message": "Failed to analyze item liquidity",
                "liquidity": "unknown",
            }

        # Get liquidity from volume category
        volume_category = volume_data.get("volume_category", "low")

        return {
            "item_id": item_id,
            "liquidity": volume_category,
            "daily_sales": volume_data.get("avg_daily_sales", 0),
            "total_sales": volume_data.get("total_sales", 0),
            "volume_category": volume_category,
        }
    except (ValueError, KeyError, TypeError):
        logger.exception("Error analyzing item liquidity")
        return {
            "error": True,
            "message": "Failed to analyze item",
            "liquidity": "unknown",
        }


def enhanced_arbitrage_search(
    game: str = "csgo",
    min_profit: float = 1.0,
    api_client: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Enhanced arbitrage search with additional filters.

    Args:
        game: Game name (reserved for future implementation)
        min_profit: Minimum profit threshold (reserved)
        api_client: DMarket API client (reserved)

    Returns:
        List of arbitrage opportunities

    """
    # This is a simplified implementation
    # In production, you would fetch actual items and analyze them
    _ = game, min_profit, api_client  # Mark as intentionally unused
    return []


def get_sales_volume_stats(
    game: str = "csgo",
    api_client: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Get sales volume statistics for a game.

    Args:
        game: Game name
        api_client: DMarket API client (optional)

    Returns:
        Dictionary with volume statistics

    """
    # This is a placeholder implementation
    # In a real scenario, you would aggregate data from multiple items
    return {
        "game": game,
        "total_volume": 0,
        "high_volume_items": [],
        "medium_volume_items": [],
        "low_volume_items": [],
        "error": False,
    }
