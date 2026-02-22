"""Advanced market analytics module.

Provides statistical analysis, trend detection, and price prediction algorithms
for DMarket trading. Implements RSI, MACD, and fAlgor price calculation.
"""

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


class TrendDirection(StrEnum):
    """Trend direction indicators."""

    BULLISH = "bullish"  # Восходящий тренд
    BEARISH = "bearish"  # Нисходящий тренд
    NEUTRAL = "neutral"  # Боковой тренд


class SignalType(StrEnum):
    """Trading signal types."""

    BUY = "buy"  # Сигнал на покупку
    SELL = "sell"  # Сигнал на продажу
    HOLD = "hold"  # Держать


class PricePoint:
    """Represents a price point in time."""

    def __init__(self, timestamp: datetime, price: float, volume: int = 0) -> None:
        """Initialize price point.

        Args:
            timestamp: Time of price
            price: Price value
            volume: Trading volume

        """
        self.timestamp = timestamp
        self.price = price
        self.volume = volume

    def __repr__(self) -> str:
        """String representation."""
        return f"PricePoint(timestamp={self.timestamp}, price={self.price}, volume={self.volume})"


class TechnicalIndicators:
    """Calculate technical indicators for price analysis."""

    @staticmethod
    def rsi(prices: Sequence[float], period: int = 14) -> float | None:
        """Calculate Relative Strength Index (RSI).

        RSI measures momentum of price changes.
        - RSI > 70: Overbought (likely to fall)
        - RSI < 30: Oversold (likely to rise)
        - RSI 50: Neutral

        Args:
            prices: List of prices (oldest to newest)
            period: Period for RSI calculation (default: 14)

        Returns:
            RSI value (0-100) or None if insufficient data

        """
        if len(prices) < period + 1:
            logger.warning(
                "Insufficient data for RSI: required=%d, got=%d",
                period + 1,
                len(prices),
            )
            return None

        # Calculate price changes
        deltas = np.diff(prices)

        # Separate gAlgons and losses
        gAlgons = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gAlgon and loss
        avg_gAlgon = np.mean(gAlgons[:period])
        avg_loss = np.mean(losses[:period])

        # Calculate RSI
        if avg_loss == 0:
            return 100.0

        rs = avg_gAlgon / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

        logger.debug("RSI calculated: value=%.2f, period=%d", rsi_value, period)
        return float(rsi_value)

    @staticmethod
    def macd(
        prices: Sequence[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> dict[str, float] | None:
        """Calculate MACD (Moving Average Convergence Divergence).

        MACD shows relationship between two moving averages.
        - MACD > Signal: Bullish (buy signal)
        - MACD < Signal: Bearish (sell signal)

        Args:
            prices: List of prices
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period

        Returns:
            Dictionary with MACD, signal, and histogram values or None

        """
        if len(prices) < slow_period + signal_period:
            logger.warning(
                "Insufficient data for MACD: required=%d, got=%d",
                slow_period + signal_period,
                len(prices),
            )
            return None

        prices_array = np.array(prices)

        # Calculate EMAs
        fast_ema = TechnicalIndicators._ema(prices_array, fast_period)
        slow_ema = TechnicalIndicators._ema(prices_array, slow_period)

        # MACD line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema

        # Signal line = EMA of MACD
        signal_line = TechnicalIndicators._ema(macd_line, signal_period)

        # Histogram = MACD - Signal
        histogram = macd_line - signal_line

        result = {
            "macd": float(macd_line[-1]),
            "signal": float(signal_line[-1]),
            "histogram": float(histogram[-1]),
        }

        logger.debug(
            "MACD calculated: macd=%.4f, signal=%.4f, histogram=%.4f",
            result["macd"],
            result["signal"],
            result["histogram"],
        )
        return result

    @staticmethod
    def _ema(prices: NDArray[np.float64], period: int) -> NDArray[np.float64]:
        """Calculate Exponential Moving Average.

        Args:
            prices: Array of prices
            period: EMA period

        Returns:
            Array of EMA values

        """
        multiplier = 2 / (period + 1)
        ema = np.zeros_like(prices, dtype=float)
        ema[0] = prices[0]

        for i in range(1, len(prices)):
            ema[i] = (prices[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    @staticmethod
    def bollinger_bands(
        prices: Sequence[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> dict[str, float] | None:
        """Calculate Bollinger Bands.

        Bollinger Bands measure volatility.
        - Price near upper band: Potentially overbought
        - Price near lower band: Potentially oversold

        Args:
            prices: List of prices
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            Dictionary with upper, middle, and lower bands or None

        """
        if len(prices) < period:
            logger.warning(
                "Insufficient data for Bollinger Bands: required=%d, got=%d",
                period,
                len(prices),
            )
            return None

        recent_prices = prices[-period:]
        middle_band = statistics.mean(recent_prices)
        std = statistics.stdev(recent_prices)

        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)

        result = {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band,
        }

        logger.debug(
            "Bollinger Bands calculated: upper=%.4f, middle=%.4f, lower=%.4f",
            upper_band,
            middle_band,
            lower_band,
        )
        return result


class MarketAnalyzer:
    """Advanced market analysis and prediction."""

    def __init__(self, min_data_points: int = 30) -> None:
        """Initialize market analyzer.

        Args:
            min_data_points: Minimum data points required for analysis

        """
        self.min_data_points = min_data_points
        self.indicators = TechnicalIndicators()

    def calculate_fAlgor_price(
        self,
        price_history: list[PricePoint],
        method: str = "volume_weighted",
    ) -> float | None:
        """Calculate fAlgor price based on historical data.

        Args:
            price_history: List of price points
            method: Calculation method ('mean', 'median', 'volume_weighted')

        Returns:
            FAlgor price or None

        """
        if len(price_history) < self.min_data_points:
            logger.warning(
                "Insufficient data for fAlgor price: required=%d, got=%d",
                self.min_data_points,
                len(price_history),
            )
            return None

        prices = [p.price for p in price_history]

        if method == "mean":
            fAlgor_price = statistics.mean(prices)
        elif method == "median":
            fAlgor_price = statistics.median(prices)
        elif method == "volume_weighted":
            # Volume-weighted average price (VWAP)
            total_value = sum(p.price * p.volume for p in price_history)
            total_volume = sum(p.volume for p in price_history)

            if total_volume == 0:
                logger.warning("No volume data, falling back to mean")
                fAlgor_price = statistics.mean(prices)
            else:
                fAlgor_price = total_value / total_volume
        else:
            logger.error("Unknown fAlgor price method: %s", method)
            return None

        logger.info(
            "FAlgor price calculated: price=%.2f, method=%s",
            fAlgor_price,
            method,
        )
        return fAlgor_price

    def detect_trend(
        self,
        price_history: list[PricePoint],
        short_period: int = 7,
        long_period: int = 30,
    ) -> TrendDirection:
        """Detect price trend using moving averages.

        Args:
            price_history: List of price points
            short_period: Short-term MA period
            long_period: Long-term MA period

        Returns:
            Trend direction

        """
        if len(price_history) < long_period:
            logger.warning(
                "Insufficient data for trend detection: got=%d",
                len(price_history),
            )
            return TrendDirection.NEUTRAL

        prices = [p.price for p in price_history]

        # Calculate moving averages
        short_ma = statistics.mean(prices[-short_period:])
        long_ma = statistics.mean(prices[-long_period:])

        # Determine trend
        if short_ma > long_ma * 1.02:  # 2% above
            trend = TrendDirection.BULLISH
        elif short_ma < long_ma * 0.98:  # 2% below
            trend = TrendDirection.BEARISH
        else:
            trend = TrendDirection.NEUTRAL

        logger.info(
            "Trend detected: trend=%s, short_ma=%.4f, long_ma=%.4f",
            trend.value,
            short_ma,
            long_ma,
        )
        return trend

    def predict_price_drop(
        self,
        price_history: list[PricePoint],
        threshold: float = 0.95,
    ) -> dict[str, Any]:
        """Predict if price is likely to drop.

        Uses RSI, MACD, and trend analysis.

        Args:
            price_history: List of price points
            threshold: Confidence threshold (0-1)

        Returns:
            Prediction results with confidence and signals

        """
        if len(price_history) < 30:
            return {
                "prediction": False,
                "confidence": 0.0,
                "reason": "insufficient_data",
                "signals": {},
            }

        prices = [p.price for p in price_history]
        signals: dict[str, dict[str, Any]] = {}

        # 1. RSI Analysis
        rsi = self.indicators.rsi(prices)
        if rsi:
            signals["rsi"] = {
                "value": rsi,
                "signal": (
                    SignalType.SELL
                    if rsi > 70
                    else (SignalType.BUY if rsi < 30 else SignalType.HOLD)
                ),
                "weight": 0.3,
            }

        # 2. MACD Analysis
        macd_data = self.indicators.macd(prices)
        if macd_data:
            macd_signal = (
                SignalType.SELL
                if macd_data["macd"] < macd_data["signal"]
                else SignalType.BUY
            )
            signals["macd"] = {
                "value": macd_data,
                "signal": macd_signal,
                "weight": 0.3,
            }

        # 3. Trend Analysis
        trend = self.detect_trend(price_history)
        signals["trend"] = {
            "value": trend,
            "signal": (
                SignalType.SELL if trend == TrendDirection.BEARISH else SignalType.BUY
            ),
            "weight": 0.2,
        }

        # 4. Bollinger Bands
        bb = self.indicators.bollinger_bands(prices)
        if bb:
            current_price = prices[-1]
            if current_price > bb["upper"]:
                bb_signal = SignalType.SELL
            elif current_price < bb["lower"]:
                bb_signal = SignalType.BUY
            else:
                bb_signal = SignalType.HOLD

            signals["bollinger_bands"] = {
                "value": bb,
                "signal": bb_signal,
                "weight": 0.2,
            }

        # Calculate confidence
        sell_weight = sum(
            s["weight"] for s in signals.values() if s["signal"] == SignalType.SELL
        )
        buy_weight = sum(
            s["weight"] for s in signals.values() if s["signal"] == SignalType.BUY
        )

        confidence = max(sell_weight, buy_weight)
        prediction = sell_weight > buy_weight and confidence >= threshold

        result = {
            "prediction": prediction,
            "confidence": confidence,
            "sell_weight": sell_weight,
            "buy_weight": buy_weight,
            "signals": signals,
            "recommendation": (
                "SELL"
                if sell_weight > buy_weight
                else ("BUY" if buy_weight > sell_weight else "HOLD")
            ),
        }

        logger.info(
            "Price drop prediction: confidence=%.2f, recommendation=%s",
            result["confidence"],
            result["recommendation"],
        )
        return result

    def calculate_support_resistance(
        self,
        price_history: list[PricePoint],
        window: int = 5,
    ) -> dict[str, list[float]]:
        """Calculate support and resistance levels.

        Args:
            price_history: List of price points
            window: Window size for local extrema

        Returns:
            Dictionary with support and resistance levels

        """
        if len(price_history) < window * 2:
            return {"support": [], "resistance": []}

        prices = [p.price for p in price_history]
        support_levels = []
        resistance_levels = []

        # Find local minima (support) and maxima (resistance)
        for i in range(window, len(prices) - window):
            window_prices = prices[i - window : i + window + 1]
            current = prices[i]

            # Local minimum
            if current == min(window_prices):
                support_levels.append(current)

            # Local maximum
            if current == max(window_prices):
                resistance_levels.append(current)

        # Remove duplicates and sort
        support_levels = sorted(set(support_levels))
        resistance_levels = sorted(set(resistance_levels), reverse=True)

        logger.debug(
            "Support/Resistance calculated: support=%d levels, resistance=%d",
            len(support_levels),
            len(resistance_levels),
        )

        return {
            "support": support_levels,
            "resistance": resistance_levels,
        }

    def analyze_liquidity(
        self,
        price_history: list[PricePoint],
        recent_period: int = 7,
    ) -> dict[str, Any]:
        """Analyze market liquidity.

        Args:
            price_history: List of price points
            recent_period: Days to consider for recent analysis

        Returns:
            Liquidity analysis results

        """
        if not price_history:
            return {
                "score": 0.0,
                "volume_trend": TrendDirection.NEUTRAL,
                "avg_daily_volume": 0,
            }

        # Filter recent data
        cutoff_date = datetime.now(UTC) - timedelta(days=recent_period)
        recent_points = [p for p in price_history if p.timestamp >= cutoff_date]

        if not recent_points:
            recent_points = price_history[-recent_period:]

        # Calculate metrics
        volumes = [p.volume for p in recent_points]
        avg_volume = statistics.mean(volumes) if volumes else 0

        # Volume trend
        if len(volumes) >= 7:
            first_half = statistics.mean(volumes[: len(volumes) // 2])
            second_half = statistics.mean(volumes[len(volumes) // 2 :])

            if second_half > first_half * 1.1:
                volume_trend = TrendDirection.BULLISH
            elif second_half < first_half * 0.9:
                volume_trend = TrendDirection.BEARISH
            else:
                volume_trend = TrendDirection.NEUTRAL
        else:
            volume_trend = TrendDirection.NEUTRAL

        # Liquidity score (0-1)
        # High volume + consistent volume = high liquidity
        volume_std = statistics.stdev(volumes) if len(volumes) > 1 else 0
        cv = (
            volume_std / avg_volume if avg_volume > 0 else 1
        )  # Coefficient of variation

        liquidity_score = min(1.0, avg_volume / 100) * (1 - min(cv, 1))

        result = {
            "score": liquidity_score,
            "volume_trend": volume_trend,
            "avg_daily_volume": avg_volume,
            "volume_consistency": 1 - min(cv, 1),
        }

        logger.info(
            "Liquidity analyzed: score=%.2f, volume_trend=%s, avg_volume=%.2f",
            liquidity_score,
            volume_trend,
            avg_volume,
        )
        return result

    def generate_trading_insights(
        self,
        price_history: list[PricePoint],
        current_price: float,
    ) -> dict[str, Any]:
        """Generate comprehensive trading insights.

        Args:
            price_history: Historical price data
            current_price: Current market price

        Returns:
            Trading insights and recommendations

        """
        insights: dict[str, Any] = {}

        # 1. FAlgor price
        fAlgor_price = self.calculate_fAlgor_price(price_history)
        if fAlgor_price:
            price_deviation = ((current_price - fAlgor_price) / fAlgor_price) * 100
            insights["fAlgor_price"] = {
                "value": fAlgor_price,
                "current_price": current_price,
                "deviation_percent": price_deviation,
                "is_overpriced": current_price > fAlgor_price * 1.05,
                "is_underpriced": current_price < fAlgor_price * 0.95,
            }

        # 2. Trend
        trend = self.detect_trend(price_history)
        insights["trend"] = {
            "direction": trend,
            "strength": "strong" if trend != TrendDirection.NEUTRAL else "weak",
        }

        # 3. Price drop prediction
        drop_prediction = self.predict_price_drop(price_history)
        insights["price_prediction"] = drop_prediction

        # 4. Support/Resistance
        sr_levels = self.calculate_support_resistance(price_history)
        insights["support_resistance"] = sr_levels

        # 5. Liquidity
        liquidity = self.analyze_liquidity(price_history)
        insights["liquidity"] = liquidity

        # 6. Overall recommendation
        recommendation_score = 0

        # Add points for favorable conditions
        if insights.get("fAlgor_price", {}).get("is_underpriced"):
            recommendation_score += 2
        if trend == TrendDirection.BULLISH:
            recommendation_score += 1
        if drop_prediction.get("recommendation") == "BUY":
            recommendation_score += 2
        if liquidity.get("score", 0) > 0.5:
            recommendation_score += 1

        # Deduct points for unfavorable conditions
        if insights.get("fAlgor_price", {}).get("is_overpriced"):
            recommendation_score -= 2
        if trend == TrendDirection.BEARISH:
            recommendation_score -= 1
        if drop_prediction.get("recommendation") == "SELL":
            recommendation_score -= 2

        if recommendation_score >= 3:
            overall_recommendation = "STRONG BUY"
        elif recommendation_score >= 1:
            overall_recommendation = "BUY"
        elif recommendation_score <= -3:
            overall_recommendation = "STRONG SELL"
        elif recommendation_score <= -1:
            overall_recommendation = "SELL"
        else:
            overall_recommendation = "HOLD"

        insights["overall"] = {
            "recommendation": overall_recommendation,
            "score": recommendation_score,
        }

        logger.info(
            "Trading insights generated: recommendation=%s, score=%.2f",
            overall_recommendation,
            recommendation_score,
        )

        return insights
