"""Price Analytics Module with Technical Indicators.

Provides advanced price analysis using technical indicators:
- RSI (Relative Strength Index) - momentum oscillator
- MACD (Moving Average Convergence Divergence) - trend following
- Bollinger Bands - volatility indicator
- SMA/EMA (Simple/Exponential Moving Averages)
- Liquidity scoring - market depth analysis
- Trend detection - price direction analysis

Usage:
    ```python
    from src.analytics.price_analytics import PriceAnalytics

    analytics = PriceAnalytics()

    # Calculate RSI
    rsi = analytics.calculate_rsi(prices)

    # Get full analysis
    analysis = analytics.analyze_item(price_history)
    print(f"Trend: {analysis.trend}")
    print(f"RSI: {analysis.rsi}")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class Trend(StrEnum):
    """Price trend direction."""

    STRONG_UP = "strong_up"  # RSI > 70, price increasing
    UP = "up"  # Price above SMA, increasing
    NEUTRAL = "neutral"  # No clear direction
    DOWN = "down"  # Price below SMA, decreasing
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

    VERY_HIGH = "very_high"  # 100+ listings
    HIGH = "high"  # 50-100 listings
    MEDIUM = "medium"  # 20-50 listings
    LOW = "low"  # 5-20 listings
    VERY_LOW = "very_low"  # < 5 listings


@dataclass
class RSIResult:
    """RSI calculation result."""

    value: float
    signal: Signal
    is_overbought: bool = False
    is_oversold: bool = False

    @classmethod
    def from_value(cls, value: float) -> RSIResult:
        """Create RSI result from value."""
        is_overbought = value > 70
        is_oversold = value < 30

        if value > 80:
            signal = Signal.STRONG_SELL
        elif value > 70:
            signal = Signal.SELL
        elif value < 20:
            signal = Signal.STRONG_BUY
        elif value < 30:
            signal = Signal.BUY
        else:
            signal = Signal.HOLD

        return cls(
            value=round(value, 2),
            signal=signal,
            is_overbought=is_overbought,
            is_oversold=is_oversold,
        )


@dataclass
class MACDResult:
    """MACD calculation result."""

    macd_line: float
    signal_line: float
    histogram: float
    signal: Signal
    is_bullish_crossover: bool = False
    is_bearish_crossover: bool = False

    @classmethod
    def from_values(
        cls,
        macd_line: float,
        signal_line: float,
        prev_macd: float | None = None,
        prev_signal: float | None = None,
    ) -> MACDResult:
        """Create MACD result from values."""
        histogram = macd_line - signal_line

        # Detect crossovers
        is_bullish = False
        is_bearish = False
        if prev_macd is not None and prev_signal is not None:
            is_bullish = prev_macd <= prev_signal and macd_line > signal_line
            is_bearish = prev_macd >= prev_signal and macd_line < signal_line

        if is_bullish:
            signal = Signal.BUY
        elif is_bearish:
            signal = Signal.SELL
        elif histogram > 0:
            signal = Signal.HOLD
        else:
            signal = Signal.HOLD

        return cls(
            macd_line=round(macd_line, 4),
            signal_line=round(signal_line, 4),
            histogram=round(histogram, 4),
            signal=signal,
            is_bullish_crossover=is_bullish,
            is_bearish_crossover=is_bearish,
        )


@dataclass
class BollingerBands:
    """Bollinger Bands result."""

    upper: float
    middle: float  # SMA
    lower: float
    bandwidth: float
    position: float  # 0 = at lower band, 1 = at upper band

    @property
    def is_squeeze(self) -> bool:
        """Check if in squeeze (low volatility)."""
        return self.bandwidth < 0.1

    @property
    def signal(self) -> Signal:
        """Get trading signal."""
        if self.position < 0.1:
            return Signal.BUY
        if self.position > 0.9:
            return Signal.SELL
        return Signal.HOLD


@dataclass
class LiquidityScore:
    """Liquidity analysis result."""

    score: float  # 0-100
    level: LiquidityLevel
    listings_count: int
    avg_price: Decimal
    price_spread: Decimal  # Difference between min and max
    depth_score: float  # How much volume at each price level

    @property
    def is_tradable(self) -> bool:
        """Check if item is easily tradable."""
        return self.score >= 50 and self.listings_count >= 5


@dataclass
class TrendAnalysis:
    """Complete trend analysis."""

    trend: Trend
    strength: float  # 0-100
    direction_days: int  # Days in current direction
    support_level: float
    resistance_level: float
    predicted_direction: str  # "up", "down", "sideways"
    confidence: float  # 0-100


@dataclass
class PriceAnalysis:
    """Complete price analysis result."""

    item_name: str
    current_price: Decimal
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Technical indicators
    rsi: RSIResult | None = None
    macd: MACDResult | None = None
    bollinger: BollingerBands | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None

    # Trend analysis
    trend: TrendAnalysis | None = None

    # Liquidity
    liquidity: LiquidityScore | None = None

    # Overall signal
    overall_signal: Signal = Signal.HOLD
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "current_price": str(self.current_price),
            "analyzed_at": self.analyzed_at.isoformat(),
            "rsi": (
                {
                    "value": self.rsi.value,
                    "signal": self.rsi.signal.value,
                    "overbought": self.rsi.is_overbought,
                    "oversold": self.rsi.is_oversold,
                }
                if self.rsi
                else None
            ),
            "macd": (
                {
                    "macd_line": self.macd.macd_line,
                    "signal_line": self.macd.signal_line,
                    "histogram": self.macd.histogram,
                    "signal": self.macd.signal.value,
                }
                if self.macd
                else None
            ),
            "bollinger": (
                {
                    "upper": self.bollinger.upper,
                    "middle": self.bollinger.middle,
                    "lower": self.bollinger.lower,
                    "signal": self.bollinger.signal.value,
                }
                if self.bollinger
                else None
            ),
            "trend": (
                {
                    "direction": self.trend.trend.value,
                    "strength": self.trend.strength,
                    "support": self.trend.support_level,
                    "resistance": self.trend.resistance_level,
                }
                if self.trend
                else None
            ),
            "liquidity": (
                {
                    "score": self.liquidity.score,
                    "level": self.liquidity.level.value,
                    "listings": self.liquidity.listings_count,
                    "tradable": self.liquidity.is_tradable,
                }
                if self.liquidity
                else None
            ),
            "overall_signal": self.overall_signal.value,
            "confidence": round(self.confidence, 2),
        }


class PriceAnalytics:
    """Price analytics engine with technical indicators."""

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

    def calculate_sma(self, prices: list[float], period: int) -> float | None:
        """Calculate Simple Moving Average.

        Args:
            prices: List of prices (newest first or oldest first)
            period: SMA period

        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None
        return sum(prices[:period]) / period

    def calculate_ema(self, prices: list[float], period: int) -> float | None:
        """Calculate Exponential Moving Average.

        Args:
            prices: List of prices (oldest first)
            period: EMA period

        Returns:
            EMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA

        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def calculate_rsi(
        self, prices: list[float], period: int | None = None
    ) -> RSIResult | None:
        """Calculate Relative Strength Index.

        RSI = 100 - (100 / (1 + RS))
        RS = Average GAlgon / Average Loss

        Args:
            prices: List of prices (oldest first)
            period: RSI period (default: self.rsi_period)

        Returns:
            RSI result or None if insufficient data
        """
        period = period or self.rsi_period

        if len(prices) < period + 1:
            return None

        # Calculate price changes
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gAlgons and losses
        gAlgons = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]

        # Calculate average gAlgon and loss
        avg_gAlgon = sum(gAlgons[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Smooth averages
        for i in range(period, len(gAlgons)):
            avg_gAlgon = (avg_gAlgon * (period - 1) + gAlgons[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # Calculate RSI
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gAlgon / avg_loss
            rsi = 100 - (100 / (1 + rs))

        return RSIResult.from_value(rsi)

    def calculate_macd(
        self,
        prices: list[float],
        fast: int | None = None,
        slow: int | None = None,
        signal: int | None = None,
    ) -> MACDResult | None:
        """Calculate MACD (Moving Average Convergence Divergence).

        MACD Line = Fast EMA - Slow EMA
        Signal Line = EMA of MACD Line
        Histogram = MACD Line - Signal Line

        Args:
            prices: List of prices (oldest first)
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            MACD result or None if insufficient data
        """
        fast = fast or self.macd_fast
        slow = slow or self.macd_slow
        signal = signal or self.macd_signal

        if len(prices) < slow + signal:
            return None

        # Calculate EMAs
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)

        if ema_fast is None or ema_slow is None:
            return None

        macd_line = ema_fast - ema_slow

        # Calculate MACD history for signal line
        macd_history = []
        for i in range(slow - 1, len(prices)):
            subset = prices[: i + 1]
            fast_ema = self.calculate_ema(subset, fast)
            slow_ema = self.calculate_ema(subset, slow)
            if fast_ema is not None and slow_ema is not None:
                macd_history.append(fast_ema - slow_ema)

        if len(macd_history) < signal:
            return None

        signal_line = self.calculate_ema(macd_history, signal)
        if signal_line is None:
            return None

        # Get previous values for crossover detection
        prev_macd = macd_history[-2] if len(macd_history) >= 2 else None
        prev_signal = (
            self.calculate_ema(macd_history[:-1], signal)
            if len(macd_history) >= 2
            else None
        )

        return MACDResult.from_values(
            macd_line=macd_line,
            signal_line=signal_line,
            prev_macd=prev_macd,
            prev_signal=prev_signal,
        )

    def calculate_bollinger_bands(
        self,
        prices: list[float],
        period: int | None = None,
        num_std: float | None = None,
    ) -> BollingerBands | None:
        """Calculate Bollinger Bands.

        Middle = SMA
        Upper = SMA + (std * num_std)
        Lower = SMA - (std * num_std)

        Args:
            prices: List of prices
            period: Period for SMA and std calculation
            num_std: Number of standard deviations

        Returns:
            Bollinger Bands or None if insufficient data
        """
        period = period or self.bollinger_period
        num_std = num_std or self.bollinger_std

        if len(prices) < period:
            return None

        # Calculate SMA
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period

        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance**0.5

        upper = sma + (std * num_std)
        lower = sma - (std * num_std)

        # Calculate bandwidth and position
        bandwidth = (upper - lower) / sma if sma > 0 else 0
        current_price = prices[-1]
        position = (
            (current_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
        )

        return BollingerBands(
            upper=round(upper, 2),
            middle=round(sma, 2),
            lower=round(lower, 2),
            bandwidth=round(bandwidth, 4),
            position=round(max(0, min(1, position)), 4),
        )

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


# Factory function
def create_price_analytics(
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
) -> PriceAnalytics:
    """Create price analytics instance.

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
