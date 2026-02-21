"""Market Regime Detection Module.

Provides market regime detection and adaptive strategy selection:
- Trending Up / Down detection
- Ranging market identification
- Volatile market detection
- Regime-specific strategy recommendations

Based on SkillsMP `market-regimes` skill best practices.

Usage:
    ```python
    from src.trading.regime_detector import RegimeDetector, MarketRegime

    detector = RegimeDetector()

    # Analyze price series
    analysis = detector.detect_regime(prices=[100, 102, 105, 103, 108, 110])

    print(analysis.regime)  # MarketRegime.TRENDING_UP
    print(analysis.confidence)  # 0.85
    print(analysis.suggested_strategy)  # "momentum_long"
    ```

Created: January 23, 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MarketRegime(StrEnum):
    """Market regime types."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeAnalysis:
    """Result of market regime analysis."""

    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    suggested_strategy: str

    # Technical indicators
    trend_strength: float = 0.0  # ADX-like measure
    volatility: float = 0.0  # Standard deviation normalized
    momentum: float = 0.0  # Rate of change

    # Price stats
    price_change_pct: float = 0.0
    avg_price: float = 0.0

    # Metadata
    window_size: int = 20
    data_points: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 2),
            "suggested_strategy": self.suggested_strategy,
            "trend_strength": round(self.trend_strength, 2),
            "volatility": round(self.volatility, 4),
            "momentum": round(self.momentum, 4),
            "price_change_pct": round(self.price_change_pct, 2),
            "window_size": self.window_size,
            "data_points": self.data_points,
        }


# Strategy recommendations per regime
REGIME_STRATEGIES: dict[MarketRegime, dict[str, Any]] = {
    MarketRegime.TRENDING_UP: {
        "strategy": "momentum_long",
        "description": "Follow the trend, buy dips, hold winners",
        "actions": ["buy_breakouts", "trail_stops", "scale_in"],
        "risk_level": "medium",
        "hold_duration": "medium-long",
    },
    MarketRegime.TRENDING_DOWN: {
        "strategy": "defensive",
        "description": "Reduce exposure, sell rallies, preserve capital",
        "actions": ["reduce_positions", "tight_stops", "wait_reversal"],
        "risk_level": "low",
        "hold_duration": "short",
    },
    MarketRegime.RANGING: {
        "strategy": "mean_reversion",
        "description": "Buy support, sell resistance, range trading",
        "actions": ["buy_support", "sell_resistance", "quick_profits"],
        "risk_level": "medium",
        "hold_duration": "short",
    },
    MarketRegime.VOLATILE: {
        "strategy": "volatility_play",
        "description": "Smaller positions, wider stops, quick scalps",
        "actions": ["reduce_size", "wide_stops", "scalp_moves"],
        "risk_level": "high",
        "hold_duration": "very_short",
    },
    MarketRegime.UNKNOWN: {
        "strategy": "cautious",
        "description": "Wait for clarity, paper trade, small positions",
        "actions": ["observe", "paper_trade", "small_test"],
        "risk_level": "low",
        "hold_duration": "none",
    },
}


class RegimeDetector:
    """Market regime detector.

    Analyzes price series to determine current market regime
    and provides strategy recommendations.

    Uses multiple indicators:
    - Simple Moving Averages (SMA)
    - Rate of Change (ROC)
    - Volatility (Standard Deviation)
    - Trend Strength (ADX-like)
    """

    # Thresholds for regime detection
    TREND_THRESHOLD = 0.02  # 2% trend to consider trending
    VOLATILITY_THRESHOLD = 0.05  # 5% std dev = volatile
    RANGING_VOLATILITY = 0.02  # < 2% std dev = ranging

    def __init__(
        self,
        window: int = 20,
        trend_threshold: float | None = None,
        volatility_threshold: float | None = None,
    ) -> None:
        """Initialize detector.

        Args:
            window: Default analysis window
            trend_threshold: Custom trend threshold
            volatility_threshold: Custom volatility threshold
        """
        self.window = window
        self.trend_threshold = trend_threshold or self.TREND_THRESHOLD
        self.volatility_threshold = volatility_threshold or self.VOLATILITY_THRESHOLD

    def detect_regime(
        self,
        prices: list[float],
        window: int | None = None,
    ) -> RegimeAnalysis:
        """Detect market regime from price series.

        Args:
            prices: List of prices (oldest to newest)
            window: Analysis window (default: self.window)

        Returns:
            RegimeAnalysis with detected regime and metrics
        """
        window = window or self.window

        if len(prices) < 3:
            return self._unknown_regime(len(prices))

        # Use last N prices
        analysis_prices = prices[-window:] if len(prices) > window else prices
        n = len(analysis_prices)

        # Calculate metrics
        avg_price = sum(analysis_prices) / n

        # Price change from start to end
        price_change = analysis_prices[-1] - analysis_prices[0]
        price_change_pct = (
            (price_change / analysis_prices[0]) * 100 if analysis_prices[0] > 0 else 0
        )

        # Momentum (rate of change)
        momentum = price_change / analysis_prices[0] if analysis_prices[0] > 0 else 0

        # Volatility (normalized standard deviation)
        mean = sum(analysis_prices) / n
        variance = sum((p - mean) ** 2 for p in analysis_prices) / n
        std_dev = variance**0.5
        volatility = std_dev / mean if mean > 0 else 0

        # Trend strength (simplified ADX-like)
        # Count directional moves
        up_moves = 0
        down_moves = 0
        for i in range(1, n):
            if analysis_prices[i] > analysis_prices[i - 1]:
                up_moves += 1
            elif analysis_prices[i] < analysis_prices[i - 1]:
                down_moves += 1

        total_moves = up_moves + down_moves
        directional_ratio = (
            abs(up_moves - down_moves) / total_moves if total_moves > 0 else 0
        )
        trend_strength = directional_ratio * abs(momentum)

        # Determine regime
        regime, confidence = self._classify_regime(
            momentum=momentum,
            volatility=volatility,
            trend_strength=trend_strength,
            directional_ratio=directional_ratio,
        )

        # Get strategy
        strategy_info = REGIME_STRATEGIES.get(
            regime, REGIME_STRATEGIES[MarketRegime.UNKNOWN]
        )

        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            suggested_strategy=strategy_info["strategy"],
            trend_strength=trend_strength,
            volatility=volatility,
            momentum=momentum,
            price_change_pct=price_change_pct,
            avg_price=avg_price,
            window_size=window,
            data_points=n,
        )

    def _classify_regime(
        self,
        momentum: float,
        volatility: float,
        trend_strength: float,
        directional_ratio: float,
    ) -> tuple[MarketRegime, float]:
        """Classify regime based on metrics.

        Args:
            momentum: Rate of change
            volatility: Normalized volatility
            trend_strength: ADX-like strength
            directional_ratio: Up/down move ratio

        Returns:
            Tuple of (regime, confidence)
        """
        # High volatility = volatile market
        if volatility > self.volatility_threshold:
            confidence = min(1.0, volatility / self.volatility_threshold - 0.5)
            return MarketRegime.VOLATILE, max(0.5, confidence)

        # Low volatility + low momentum = ranging
        if (
            volatility < self.RANGING_VOLATILITY
            and abs(momentum) < self.trend_threshold / 2
        ):
            confidence = 1.0 - (volatility / self.RANGING_VOLATILITY)
            return MarketRegime.RANGING, max(0.5, min(0.9, confidence))

        # Trending up
        if momentum > self.trend_threshold and directional_ratio > 0.3:
            confidence = min(
                1.0, momentum / self.trend_threshold * 0.5 + directional_ratio * 0.5
            )
            return MarketRegime.TRENDING_UP, max(0.5, confidence)

        # Trending down
        if momentum < -self.trend_threshold and directional_ratio > 0.3:
            confidence = min(
                1.0,
                abs(momentum) / self.trend_threshold * 0.5 + directional_ratio * 0.5,
            )
            return MarketRegime.TRENDING_DOWN, max(0.5, confidence)

        # Weak trend or mixed - ranging
        if abs(momentum) < self.trend_threshold:
            return MarketRegime.RANGING, 0.6

        # Fallback
        return MarketRegime.UNKNOWN, 0.5

    def _unknown_regime(self, data_points: int) -> RegimeAnalysis:
        """Return unknown regime for insufficient data."""
        return RegimeAnalysis(
            regime=MarketRegime.UNKNOWN,
            confidence=0.0,
            suggested_strategy="cautious",
            data_points=data_points,
        )

    def get_strategy_details(self, regime: MarketRegime) -> dict[str, Any]:
        """Get detailed strategy for regime.

        Args:
            regime: Market regime

        Returns:
            Strategy details
        """
        return REGIME_STRATEGIES.get(regime, REGIME_STRATEGIES[MarketRegime.UNKNOWN])

    def analyze_multi_timeframe(
        self,
        prices: list[float],
        windows: list[int] | None = None,
    ) -> dict[str, RegimeAnalysis]:
        """Analyze regime across multiple timeframes.

        Args:
            prices: Price series
            windows: List of windows to analyze

        Returns:
            Dict of window -> RegimeAnalysis
        """
        windows = windows or [5, 10, 20, 50]
        results = {}

        for window in windows:
            if len(prices) >= window:
                analysis = self.detect_regime(prices, window=window)
                results[f"window_{window}"] = analysis

        return results

    def get_regime_summary(
        self,
        multi_analysis: dict[str, RegimeAnalysis],
    ) -> dict[str, Any]:
        """Summarize multi-timeframe analysis.

        Args:
            multi_analysis: Results from analyze_multi_timeframe

        Returns:
            Summary with dominant regime
        """
        if not multi_analysis:
            return {
                "dominant_regime": MarketRegime.UNKNOWN,
                "agreement": 0.0,
                "recommendation": "insufficient_data",
            }

        # Count regimes
        regime_counts: dict[MarketRegime, float] = {}
        total_confidence = 0.0

        for analysis in multi_analysis.values():
            regime = analysis.regime
            conf = analysis.confidence
            regime_counts[regime] = regime_counts.get(regime, 0) + conf
            total_confidence += conf

        # Find dominant
        dominant_regime = max(regime_counts.items(), key=lambda x: x[1])[0]
        agreement = (
            regime_counts[dominant_regime] / total_confidence
            if total_confidence > 0
            else 0
        )

        strategy = self.get_strategy_details(dominant_regime)

        return {
            "dominant_regime": dominant_regime,
            "agreement": round(agreement, 2),
            "regime_scores": {k.value: round(v, 2) for k, v in regime_counts.items()},
            "recommendation": strategy["strategy"],
            "risk_level": strategy["risk_level"],
            "timeframes_analyzed": len(multi_analysis),
        }


class AdaptiveTrader:
    """Adaptive trader that adjusts behavior based on market regime.

    Adjusts:
    - Position sizing
    - Stop-loss levels
    - Take-profit targets
    - Entry/exit timing
    """

    # Regime-based multipliers
    POSITION_MULTIPLIERS = {
        MarketRegime.TRENDING_UP: 1.0,
        MarketRegime.TRENDING_DOWN: 0.5,
        MarketRegime.RANGING: 0.7,
        MarketRegime.VOLATILE: 0.4,
        MarketRegime.UNKNOWN: 0.3,
    }

    STOP_LOSS_MULTIPLIERS = {
        MarketRegime.TRENDING_UP: 1.0,  # Normal stops
        MarketRegime.TRENDING_DOWN: 0.7,  # Tighter stops
        MarketRegime.RANGING: 0.8,
        MarketRegime.VOLATILE: 1.5,  # Wider stops
        MarketRegime.UNKNOWN: 0.5,
    }

    def __init__(
        self,
        detector: RegimeDetector | None = None,
        base_position_size: float = 100.0,
        base_stop_loss_pct: float = 10.0,
        base_take_profit_pct: float = 15.0,
    ) -> None:
        """Initialize adaptive trader.

        Args:
            detector: Regime detector instance
            base_position_size: Base position size in USD
            base_stop_loss_pct: Base stop loss percentage
            base_take_profit_pct: Base take profit percentage
        """
        self.detector = detector or RegimeDetector()
        self.base_position_size = base_position_size
        self.base_stop_loss_pct = base_stop_loss_pct
        self.base_take_profit_pct = base_take_profit_pct

    def get_adapted_params(
        self,
        prices: list[float],
        balance: float | None = None,
    ) -> dict[str, Any]:
        """Get trading parameters adapted to current regime.

        Args:
            prices: Recent price history
            balance: Current balance (optional)

        Returns:
            Adapted trading parameters
        """
        # Detect regime
        analysis = self.detector.detect_regime(prices)
        regime = analysis.regime

        # Calculate adapted values
        pos_multiplier = self.POSITION_MULTIPLIERS.get(regime, 0.5)
        sl_multiplier = self.STOP_LOSS_MULTIPLIERS.get(regime, 1.0)

        # Adjust position size
        adapted_position = (
            self.base_position_size * pos_multiplier * analysis.confidence
        )

        # Adjust stop loss (wider in volatile, tighter in trending down)
        adapted_stop_loss = self.base_stop_loss_pct * sl_multiplier

        # Adjust take profit based on volatility
        volatility_factor = 1 + analysis.volatility * 2  # Higher vol = higher targets
        adapted_take_profit = self.base_take_profit_pct * volatility_factor

        # Cap by balance if provided
        if balance:
            adapted_position = min(adapted_position, balance * 0.2)  # Max 20% per trade

        strategy_info = self.detector.get_strategy_details(regime)

        return {
            "regime": regime.value,
            "confidence": analysis.confidence,
            "position_size": round(adapted_position, 2),
            "stop_loss_pct": round(adapted_stop_loss, 1),
            "take_profit_pct": round(adapted_take_profit, 1),
            "strategy": strategy_info["strategy"],
            "actions": strategy_info["actions"],
            "risk_level": strategy_info["risk_level"],
            "hold_duration": strategy_info["hold_duration"],
            # Raw metrics
            "volatility": analysis.volatility,
            "momentum": analysis.momentum,
            "trend_strength": analysis.trend_strength,
        }

    def should_trade(
        self,
        prices: list[float],
        min_confidence: float = 0.6,
    ) -> tuple[bool, str]:
        """Determine if trading is advisable.

        Args:
            prices: Price history
            min_confidence: Minimum confidence to trade

        Returns:
            Tuple of (should_trade, reason)
        """
        analysis = self.detector.detect_regime(prices)

        # Don't trade unknown regimes
        if analysis.regime == MarketRegime.UNKNOWN:
            return False, "Market regime unclear, waiting for clarity"

        # Don't trade low confidence
        if analysis.confidence < min_confidence:
            return (
                False,
                f"Low confidence ({analysis.confidence:.0%}), waiting for confirmation",
            )

        # Caution in volatile markets
        if analysis.regime == MarketRegime.VOLATILE and analysis.volatility > 0.1:
            return False, "Extreme volatility detected, waiting for stability"

        # Caution in strong downtrends
        if (
            analysis.regime == MarketRegime.TRENDING_DOWN
            and analysis.trend_strength > 0.05
        ):
            return False, "Strong downtrend detected, waiting for reversal"

        return True, f"Trading conditions favorable ({analysis.regime.value})"


# Factory functions
def create_regime_detector(
    window: int = 20,
    trend_threshold: float = 0.02,
    volatility_threshold: float = 0.05,
) -> RegimeDetector:
    """Create regime detector.

    Args:
        window: Analysis window
        trend_threshold: Trend detection threshold
        volatility_threshold: Volatility threshold

    Returns:
        RegimeDetector instance
    """
    return RegimeDetector(
        window=window,
        trend_threshold=trend_threshold,
        volatility_threshold=volatility_threshold,
    )


def create_adaptive_trader(
    base_position_size: float = 100.0,
    base_stop_loss_pct: float = 10.0,
    base_take_profit_pct: float = 15.0,
) -> AdaptiveTrader:
    """Create adaptive trader.

    Args:
        base_position_size: Base position size
        base_stop_loss_pct: Base stop loss %
        base_take_profit_pct: Base take profit %

    Returns:
        AdaptiveTrader instance
    """
    return AdaptiveTrader(
        base_position_size=base_position_size,
        base_stop_loss_pct=base_stop_loss_pct,
        base_take_profit_pct=base_take_profit_pct,
    )
