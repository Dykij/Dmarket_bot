"""
trends.py — Trend detection and overall-signal aggregation.

Splits the more complex "interpret-many-indicators-into-one-decision" logic
out of the indicator code so each piece stays small and focused.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .enums import Signal, Trend
from .models import PriceAnalysis, TrendAnalysis


class _TrendMixin:
    """Mixin with trend analysis and overall-signal aggregation.

    Mixed into `PriceAnalytics` (see `core.py`).
    Uses `Signal` and `Trend` enums and `PriceAnalysis` / `TrendAnalysis` models.
    """

    # Declared here for mypy; actual implementation lives in _IndicatorMixin.
    calculate_sma: Any

    def analyze_trend(
        self,
        prices: list[float],
        timestamps: list[datetime] | None = None,
    ) -> TrendAnalysis | None:
        """Analyze price trend.

        Args:
            prices: List of prices (oldest first)
            timestamps: Optional timestamps for each price

        Returns:
            Trend analysis or None if insufficient data
        """
        if len(prices) < 10:
            return None

        # Calculate moving averages
        sma_short = self.calculate_sma(prices[-10:], 10)
        sma_long = (
            self.calculate_sma(prices[-20:], 20) if len(prices) >= 20 else sma_short
        )

        if sma_short is None:
            return None

        current_price = prices[-1]

        # Determine trend direction
        price_vs_sma = current_price - sma_short
        sma_slope = (sma_short - (sma_long or sma_short)) / (sma_long or 1)

        if price_vs_sma > 0 and sma_slope > 0.02:
            trend = Trend.STRONG_UP
            strength = min(100, abs(sma_slope) * 500 + 50)
        elif price_vs_sma > 0:
            trend = Trend.UP
            strength = min(100, abs(sma_slope) * 500 + 30)
        elif price_vs_sma < 0 and sma_slope < -0.02:
            trend = Trend.STRONG_DOWN
            strength = min(100, abs(sma_slope) * 500 + 50)
        elif price_vs_sma < 0:
            trend = Trend.DOWN
            strength = min(100, abs(sma_slope) * 500 + 30)
        else:
            trend = Trend.NEUTRAL
            strength = 20

        # Find support and resistance
        support = min(prices[-20:]) if len(prices) >= 20 else min(prices)
        resistance = max(prices[-20:]) if len(prices) >= 20 else max(prices)

        # Count days in current direction
        direction_days = 1
        for i in range(len(prices) - 2, -1, -1):
            if (trend in {Trend.UP, Trend.STRONG_UP} and prices[i] < prices[i + 1]) or (
                trend in {Trend.DOWN, Trend.STRONG_DOWN} and prices[i] > prices[i + 1]
            ):
                direction_days += 1
            else:
                break

        # Predict direction
        if trend in {Trend.STRONG_UP, Trend.UP}:
            predicted = "up"
        elif trend in {Trend.STRONG_DOWN, Trend.DOWN}:
            predicted = "down"
        else:
            predicted = "sideways"

        return TrendAnalysis(
            trend=trend,
            strength=round(strength, 2),
            direction_days=direction_days,
            support_level=round(support, 2),
            resistance_level=round(resistance, 2),
            predicted_direction=predicted,
            confidence=round(strength * 0.8, 2),
        )

    def _calculate_overall_signal(
        self,
        analysis: PriceAnalysis,
    ) -> tuple[Signal, float]:
        """Calculate overall trading signal from all indicators.

        Args:
            analysis: Price analysis with indicators

        Returns:
            (signal, confidence) tuple
        """
        signals: list[tuple[Signal, float]] = []

        # RSI signal
        if analysis.rsi:
            weight = 0.3
            signals.append((analysis.rsi.signal, weight))

        # MACD signal
        if analysis.macd:
            weight = 0.25
            signals.append((analysis.macd.signal, weight))

        # Bollinger signal
        if analysis.bollinger:
            weight = 0.2
            signals.append((analysis.bollinger.signal, weight))

        # Trend signal
        if analysis.trend:
            weight = 0.25
            if analysis.trend.trend in {Trend.STRONG_UP, Trend.UP}:
                signals.append((Signal.BUY, weight * analysis.trend.strength / 100))
            elif analysis.trend.trend in {Trend.STRONG_DOWN, Trend.DOWN}:
                signals.append((Signal.SELL, weight * analysis.trend.strength / 100))
            else:
                signals.append((Signal.HOLD, weight))

        if not signals:
            return Signal.HOLD, 0.0

        # Calculate weighted signal
        signal_scores = {
            Signal.STRONG_BUY: 2,
            Signal.BUY: 1,
            Signal.HOLD: 0,
            Signal.SELL: -1,
            Signal.STRONG_SELL: -2,
        }

        weighted_sum = sum(signal_scores[s] * w for s, w in signals)
        total_weight = sum(w for _, w in signals)

        if total_weight == 0:
            return Signal.HOLD, 0.0

        avg_score = weighted_sum / total_weight

        # Convert back to signal
        if avg_score >= 1.5:
            signal = Signal.STRONG_BUY
        elif avg_score >= 0.5:
            signal = Signal.BUY
        elif avg_score <= -1.5:
            signal = Signal.STRONG_SELL
        elif avg_score <= -0.5:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        # Calculate confidence
        confidence = min(100, abs(avg_score) * 50)

        return signal, round(confidence, 2)
