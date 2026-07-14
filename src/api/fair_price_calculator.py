"""
fair_price_calculator.py — Unified price beacon.

Aggregates prices from multiple sources (Market.CSGO, Waxpeer,
CSFloat, Steam, DMarket) and calculates a "fair price" using
median with outlier removal.

Algorithm:
  1. Collect prices from all available sources
  2. Remove outliers (min and max if >2 sources)
  3. Calculate median of remaining prices
  4. Apply dynamic margin based on liquidity
  5. Return fair sell price for DMarket listing

This replaces paid oracle cross-market pricing for the specific
use case of "what price should I list this item at on DMarket".
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("FairPrice")


@dataclass
class FairPriceResult:
    """Result of fair price calculation."""
    title: str
    fair_price: float         # Median price (no outliers)
    sell_price: float         # Fair price + margin (for DMarket listing)
    sources: dict[str, float] # {source: price}
    source_count: int         # Number of sources with data
    outlier_removed: str | None  # Which source was removed as outlier
    margin_pct: float         # Applied margin percentage
    volume_total: int         # Total volume across sources
    confidence: str           # "high", "medium", "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "fair_price": round(self.fair_price, 2),
            "sell_price": round(self.sell_price, 2),
            "sources": {k: round(v, 2) for k, v in self.sources.items()},
            "source_count": self.source_count,
            "outlier_removed": self.outlier_removed,
            "margin_pct": self.margin_pct,
            "volume_total": self.volume_total,
            "confidence": self.confidence,
        }


class FairPriceCalculator:
    """
    Calculates fair sell price from multiple marketplace sources.

    Usage:
        calc = FairPriceCalculator()
        result = calc.calculate(
            title="AK-47 | Redline (Field-Tested)",
            prices={"marketcsgo": 30.55, "waxpeer": 3.14, "steam": 35.16},
            volumes={"marketcsgo": 442, "waxpeer": 388},
            dmarket_buy_price=12.00,
        )
        print(result.sell_price)  # Price to list on DMarket
    """

    # Margin tiers based on volume (total listings across sources)
    MARGIN_TIERS = [
        (100, 3.0),   # Very liquid: 3% margin
        (50, 5.0),    # Liquid: 5% margin
        (20, 7.0),    # Medium: 7% margin
        (5, 10.0),    # Low liquidity: 10% margin
        (0, 15.0),    # Very low: 15% margin
    ]

    # Steam price adjustment (Steam Wallet prices are ~15% higher)
    # NOTE: SteamOracle already applies this factor before returning prices.
    # Do NOT apply it again here — that would double-adjust (0.85*0.85=0.7225).
    STEAM_ADJUSTMENT = 1.0  # Identity — upstream oracles handle conversion

    def calculate(
        self,
        title: str,
        prices: dict[str, float],
        volumes: dict[str, int] | None = None,
        dmarket_buy_price: float = 0.0,
    ) -> FairPriceResult:
        """
        Calculate fair sell price from multiple sources.

        Args:
            title: Item name
            prices: {source: price_usd} from each oracle
            volumes: {source: volume_count} for liquidity assessment
            dmarket_buy_price: What we paid on DMarket (for min margin check)

        Returns:
            FairPriceResult with fair_price and sell_price
        """
        if volumes is None:
            volumes = {}

        # Filter out zero/invalid prices
        valid_prices = {k: v for k, v in prices.items() if v > 0}

        if not valid_prices:
            return FairPriceResult(
                title=title,
                fair_price=0.0,
                sell_price=0.0,
                sources=prices,
                source_count=0,
                outlier_removed=None,
                margin_pct=0.0,
                volume_total=0,
                confidence="none",
            )

        # Adjust Steam prices (they're ~15% higher than cash market)
        adjusted = {}
        outlier_removed = None
        for source, price in valid_prices.items():
            if source == "steam":
                adjusted[source] = price * self.STEAM_ADJUSTMENT
            else:
                adjusted[source] = price

        # Remove outliers if we have >2 sources
        if len(adjusted) > 2:
            min_source = min(adjusted, key=adjusted.get)  # type: ignore
            max_source = max(adjusted, key=adjusted.get)  # type: ignore

            # Only remove if outlier is >2x the median of others
            others = {k: v for k, v in adjusted.items() if k != min_source}
            if others:
                others_median = statistics.median(others.values())
                if adjusted[min_source] < others_median * 0.3:
                    outlier_removed = min_source
                    del adjusted[min_source]
                elif len(adjusted) > 2:
                    others = {k: v for k, v in adjusted.items() if k != max_source}
                    if others:
                        others_median = statistics.median(others.values())
                        if adjusted[max_source] > others_median * 2.0:
                            outlier_removed = max_source
                            del adjusted[max_source]

        # Calculate median
        price_values = list(adjusted.values())
        if not price_values:
            return FairPriceResult(
                title=title,
                fair_price=0.0,
                sell_price=0.0,
                sources=prices,
                source_count=0,
                outlier_removed=outlier_removed,
                margin_pct=0.0,
                volume_total=0,
                confidence="none",
            )

        fair_price = statistics.median(price_values)

        # Calculate total volume
        total_volume = sum(volumes.get(k, 0) for k in valid_prices)

        # Determine margin based on liquidity
        margin_pct = 15.0  # default
        for min_vol, margin in self.MARGIN_TIERS:
            if total_volume >= min_vol:
                margin_pct = margin
                break

        # Sell price = fair price + margin
        sell_price = fair_price * (1 + margin_pct / 100.0)

        # Ensure minimum margin over buy price
        if dmarket_buy_price > 0:
            min_sell = dmarket_buy_price * 1.03  # at least 3% profit
            sell_price = max(sell_price, min_sell)

        # Confidence level
        if len(adjusted) >= 3:
            confidence = "high"
        elif len(adjusted) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

        return FairPriceResult(
            title=title,
            fair_price=fair_price,
            sell_price=sell_price,
            sources=prices,
            source_count=len(valid_prices),
            outlier_removed=outlier_removed,
            margin_pct=margin_pct,
            volume_total=total_volume,
            confidence=confidence,
        )
