"""
core.py — The main PriceAnalytics orchestrator.

Composes:
    _IndicatorMixin (SMA/EMA/RSI/MACD/Bollinger)
    _LiquidityMixin (liquidity scoring)
    _TrendMixin     (trend analysis + overall signal)

Provides the public entry points:
    - PriceAnalytics.__init__  → configure indicator periods
    - analyze_item             → full analysis pipeline returning PriceAnalysis
"""

from __future__ import annotations

from decimal import Decimal

import structlog

from .indicators import _IndicatorMixin
from .liquidity import _LiquidityMixin
from .models import PriceAnalysis
from .trends import _TrendMixin

logger = structlog.get_logger(__name__)


class PriceAnalytics(
    _IndicatorMixin,
    _LiquidityMixin,
    _TrendMixin,
):
    """Price analytics engine with technical indicators.

    Public entry point: `analyze_item` returns a complete `PriceAnalysis`
    with all indicators, trend, liquidity and an overall weighted signal.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bollinger_period: int = 20,
        bollinger_std: float = 2.0,
    ) -> None:
        """Initialize analytics engine.

        Args:
            rsi_period: Period for RSI calculation
            macd_fast: Fast EMA period for MACD
            macd_slow: Slow EMA period for MACD
            macd_signal: Signal line period for MACD
            bollinger_period: Period for Bollinger Bands
            bollinger_std: Standard deviation multiplier for bands
        """
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bollinger_period = bollinger_period
        self.bollinger_std = bollinger_std

    def analyze_item(
        self,
        item_name: str,
        price_history: list[float],
        current_price: Decimal,
        listings_count: int = 0,
        min_listing_price: Decimal | None = None,
        max_listing_price: Decimal | None = None,
    ) -> PriceAnalysis:
        """Perform complete price analysis.

        Args:
            item_name: Item name
            price_history: Historical prices (oldest first)
            current_price: Current price
            listings_count: Number of active listings
            min_listing_price: Minimum listing price
            max_listing_price: Maximum listing price

        Returns:
            Complete price analysis
        """
        analysis = PriceAnalysis(
            item_name=item_name,
            current_price=current_price,
        )

        # Calculate technical indicators if enough data
        if len(price_history) >= self.rsi_period + 1:
            analysis.rsi = self.calculate_rsi(price_history)

        if len(price_history) >= self.macd_slow + self.macd_signal:
            analysis.macd = self.calculate_macd(price_history)

        if len(price_history) >= self.bollinger_period:
            analysis.bollinger = self.calculate_bollinger_bands(price_history)

        # Moving averages
        analysis.sma_20 = self.calculate_sma(price_history, 20)
        analysis.sma_50 = self.calculate_sma(price_history, 50)
        analysis.ema_12 = self.calculate_ema(price_history, 12)
        analysis.ema_26 = self.calculate_ema(price_history, 26)

        # Trend analysis
        analysis.trend = self.analyze_trend(price_history)

        # Liquidity
        if listings_count > 0 and min_listing_price and max_listing_price:
            analysis.liquidity = self.calculate_liquidity(
                listings_count=listings_count,
                min_price=min_listing_price,
                max_price=max_listing_price,
                avg_price=current_price,
            )

        # Calculate overall signal
        analysis.overall_signal, analysis.confidence = self._calculate_overall_signal(
            analysis
        )

        return analysis
