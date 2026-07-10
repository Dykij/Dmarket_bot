"""
liquidity_analyzer.py — Item liquidity analysis for trading decisions.

Evaluates market depth, sales velocity, and price stability to determine
if an item is liquid enough for profitable trading.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class LiquidityMetrics:
    """Liquidity analysis result for a single item."""
    item_title: str
    sales_per_week: float
    avg_time_to_sell_days: float
    active_offers_count: int
    price_stability: float
    market_depth: float
    liquidity_score: float
    is_liquid: bool


class LiquidityAnalyzer:
    """Analyzes item liquidity based on market data."""

    def __init__(
        self,
        api_client: Any,
        min_sales_per_week: float = 10.0,
        max_time_to_sell_days: float = 7.0,
        max_active_offers: int = 50,
        min_price_stability: float = 0.85,
        min_liquidity_score: float = 60.0,
    ) -> None:
        self.api = api_client
        self.min_sales_per_week = min_sales_per_week
        self.max_time_to_sell_days = max_time_to_sell_days
        self.max_active_offers = max_active_offers
        self.min_price_stability = min_price_stability
        self.min_liquidity_score = min_liquidity_score

    async def analyze_item_liquidity(
        self,
        item_title: str,
        sales_data: list[dict[str, Any]] | None = None,
        active_offers: int = 0,
    ) -> LiquidityMetrics:
        """Analyze liquidity for a single item."""
        sales_per_week = 0.0
        avg_time_to_sell = 0.0
        price_stability = 1.0
        market_depth = 0.0

        if sales_data:
            sales_per_week = len(sales_data) / max(1, len(sales_data) / 7.0)
            prices = [s.get("price", 0) for s in sales_data if s.get("price")]
            if len(prices) >= 2:
                mean_p = sum(prices) / len(prices)
                variance = sum((p - mean_p) ** 2 for p in prices) / len(prices)
                price_stability = max(0, 1 - (variance ** 0.5 / max(mean_p, 0.01)))

        # Liquidity score: weighted combination of factors
        score = 0.0
        score += min(30, sales_per_week * 3)  # max 30 from sales velocity
        score += min(30, (1 - min(active_offers / max(self.max_active_offers, 1), 1)) * 30)
        score += min(20, price_stability * 20)
        score += min(20, market_depth * 20)

        is_liquid = (
            sales_per_week >= self.min_sales_per_week
            and price_stability >= self.min_price_stability
            and score >= self.min_liquidity_score
        )

        return LiquidityMetrics(
            item_title=item_title,
            sales_per_week=sales_per_week,
            avg_time_to_sell_days=avg_time_to_sell,
            active_offers_count=active_offers,
            price_stability=price_stability,
            market_depth=market_depth,
            liquidity_score=score,
            is_liquid=is_liquid,
        )
