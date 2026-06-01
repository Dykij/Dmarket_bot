"""Price Analytics Module with Technical Indicators.

Provides advanced price analysis using technical indicators:
- RSI (Relative Strength Index) - momentum oscillator
- MACD (Moving Average Convergence Divergence) - trend following
- Bollinger Bands - volatility indicator
- SMA/EMA (Simple/Exponential Moving Averages)
- Liquidity scoring - market depth analysis
- Trend detection - price direction analysis

This module is a thin facade. The actual implementation lives in the
`price_analytics` sub-package:

    - enums.py      — Trend, Signal, LiquidityLevel
    - models.py     — RSIResult, MACDResult, BollingerBands,
                      LiquidityScore, TrendAnalysis, PriceAnalysis
    - indicators.py — SMA, EMA, RSI, MACD, Bollinger Bands calculations
    - liquidity.py  — Liquidity scoring
    - trends.py     — Trend detection + overall-signal aggregation
    - core.py       — PriceAnalytics (the orchestrator)
    - __init__.py   — Public re-exports

Usage:
    ```python
    from src.analytics.price_analytics import PriceAnalytics

    analytics = PriceAnalytics()
    rsi = analytics.calculate_rsi(prices)
    analysis = analytics.analyze_item("AK-47 | Redline", history, Decimal("102.50"))
    print(f"Trend: {analysis.trend.trend.value}")
    print(f"RSI: {analysis.rsi.value}")
    print(f"Overall: {analysis.overall_signal.value} (conf {analysis.confidence}%)")
    ```

Created: January 10, 2026
Refactored: June 1, 2026 (split into package for maintainability)
"""

from __future__ import annotations

from .price_analytics import (
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
    create_price_analytics,
)

__all__ = [
    "BollingerBands",
    "LiquidityLevel",
    "LiquidityScore",
    "MACDResult",
    "PriceAnalysis",
    "PriceAnalytics",
    "RSIResult",
    "Signal",
    "Trend",
    "TrendAnalysis",
    "create_price_analytics",
]
