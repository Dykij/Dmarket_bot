"""
enums.py — Enums used by price analytics.
"""

from enum import StrEnum


class Trend(StrEnum):
    """Price trend direction."""

    STRONG_UP = "strong_up"      # RSI > 70, price increasing
    UP = "up"                    # Price above SMA, increasing
    NEUTRAL = "neutral"          # No clear direction
    DOWN = "down"                # Price below SMA, decreasing
    STRONG_DOWN = "strong_down"  # RSI < 30, price decreasing


class Signal(StrEnum):
    """Trading signal."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class LiquidityLevel(StrEnum):
    """Liquidity level classification."""

    VERY_HIGH = "very_high"      # 100+ listings
    HIGH = "high"                # 50-100 listings
    MEDIUM = "medium"            # 20-50 listings
    LOW = "low"                  # 5-20 listings
    VERY_LOW = "very_low"        # < 5 listings
