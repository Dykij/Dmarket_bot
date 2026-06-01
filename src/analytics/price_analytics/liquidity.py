"""
liquidity.py — Liquidity scoring.

Standalone module so the math is easy to test, and so the rest of the
analytics class can stay focused on the technical indicators.
"""

from __future__ import annotations

from decimal import Decimal

from .enums import LiquidityLevel
from .models import LiquidityScore


class _LiquidityMixin:
    """Mixin providing the calculate_liquidity method.

    Mixed into `PriceAnalytics` (see `core.py`).
    Does NOT depend on any attributes from PriceAnalytics — it is fully
    self-contained and could be promoted to a free function in the future.
    """

    def calculate_liquidity(
        self,
        listings_count: int,
        min_price: Decimal,
        max_price: Decimal,
        avg_price: Decimal,
        volume_distribution: list[tuple[Decimal, int]] | None = None,
    ) -> LiquidityScore:
        """Calculate liquidity score.

        Args:
            listings_count: Number of active listings
            min_price: Minimum listing price
            max_price: Maximum listing price
            avg_price: Average listing price
            volume_distribution: Optional (price, count) pAlgors for depth

        Returns:
            Liquidity score
        """
        # Base score from listings count
        if listings_count >= 100:
            level = LiquidityLevel.VERY_HIGH
            base_score = 100
        elif listings_count >= 50:
            level = LiquidityLevel.HIGH
            base_score = 80
        elif listings_count >= 20:
            level = LiquidityLevel.MEDIUM
            base_score = 60
        elif listings_count >= 5:
            level = LiquidityLevel.LOW
            base_score = 40
        else:
            level = LiquidityLevel.VERY_LOW
            base_score = 20

        # Adjust for price spread
        spread = max_price - min_price
        spread_percent = (spread / avg_price * 100) if avg_price > 0 else 0
        spread_penalty = min(20, float(spread_percent))
        score = base_score - spread_penalty

        # Calculate depth score
        depth_score = 0.0
        if volume_distribution:
            total_volume = sum(count for _, count in volume_distribution)
            if total_volume > 0:
                # More volume at lower prices = better depth
                weighted_sum = sum(
                    count / (float(price) + 0.01)
                    for price, count in volume_distribution
                )
                depth_score = min(100, weighted_sum / total_volume * 100)

        return LiquidityScore(
            score=round(max(0, min(100, score)), 2),
            level=level,
            listings_count=listings_count,
            avg_price=avg_price,
            price_spread=spread,
            depth_score=round(depth_score, 2),
        )
