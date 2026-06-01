"""
models.py — Dataclasses for price analytics results.

Contains all the result classes that are returned by PriceAnalytics methods:
- RSIResult (with signal classification)
- MACDResult (with crossover detection)
- BollingerBands (with squeeze detection + signal property)
- LiquidityScore (with tradability property)
- TrendAnalysis (overall trend + prediction)
- PriceAnalysis (the full result aggregating all of the above)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .enums import LiquidityLevel, Signal, Trend


@dataclass
class RSIResult:
    """RSI calculation result."""

    value: float
    signal: Signal
    is_overbought: bool = False
    is_oversold: bool = False

    @classmethod
    def from_value(cls, value: float) -> "RSIResult":
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
    ) -> "MACDResult":
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
