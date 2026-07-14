"""
price_analytics.py — DEPRECATED monolith.
Python resolves `src.analytics.price_analytics` to the `price_analytics/` package directory.
Re-exports kept for backward compatibility — use the package directly.
"""
from src.analytics.price_analytics import (
    BollingerBands,
    LiquidityLevel,
    LiquidityScore,
    MACDResult,
    PriceAnalysis,
    PriceAnalytics,
    RSIResult,
    Signal,
    Trend,
    TrendAnalysis,
    _IndicatorMixin,
    _LiquidityMixin,
    _TrendMixin,
    create_price_analytics,
)

__all__ = [
    "BollingerBands", "LiquidityLevel", "LiquidityScore",
    "MACDResult", "PriceAnalysis", "PriceAnalytics", "RSIResult",
    "Signal", "Trend", "TrendAnalysis",
    "_IndicatorMixin", "_LiquidityMixin", "_TrendMixin",
    "create_price_analytics",
]
