"""
price_analytics — Technical analysis for DMarket bot.

Re-exports the public API so callers can keep using
`from src.analytics.price_analytics import PriceAnalytics, Signal, ...`.
"""

from __future__ import annotations

from .core import PriceAnalytics
from .enums import LiquidityLevel, Signal, Trend
from .indicators import _IndicatorMixin
from .liquidity import _LiquidityMixin
from .models import (
    BollingerBands,
    LiquidityScore,
    MACDResult,
    PriceAnalysis,
    RSIResult,
    TrendAnalysis,
)
from .trends import _TrendMixin

__all__ = [
    # Enums
    "Trend",
    "Signal",
    "LiquidityLevel",
    # Models
    "RSIResult",
    "MACDResult",
    "BollingerBands",
    "LiquidityScore",
    "TrendAnalysis",
    "PriceAnalysis",
    # Engine
    "PriceAnalytics",
    # Factory
    "create_price_analytics",
    # Mixins (exposed for advanced use / testing)
    "_IndicatorMixin",
    "_LiquidityMixin",
    "_TrendMixin",
]


def create_price_analytics(
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
) -> "PriceAnalytics":
    """Factory function — convenience wrapper for `PriceAnalytics(...)`.

    Args:
        rsi_period: RSI period
        macd_fast: MACD fast period
        macd_slow: MACD slow period

    Returns:
        PriceAnalytics instance
    """
    return PriceAnalytics(
        rsi_period=rsi_period,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
    )
