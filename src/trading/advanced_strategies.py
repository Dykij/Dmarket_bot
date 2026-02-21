"""
Advanced Trading Strategies - Продвинутые торговые стратегии.

Расширенные торговые возможности из SkillsMP trading-best-practices:
- Market manipulation detection
- Sentiment analysis
- Optimal entry point calculation
- Risk management

Usage:
    ```python
    from src.trading.advanced_strategies import AdvancedTradingSkills

    skills = AdvancedTradingSkills()

    # Detect market manipulation
    is_manipulated = await skills.detect_market_manipulation(prices)

    # Analyze sentiment
    sentiment = await skills.sentiment_analysis("AK-47 | Redline")

    # Find optimal entry
    signal = await skills.optimal_entry_point(item)
    ```

Created: January 2026
Based on: trading-best-practices skill from SkillsMP
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

# Conditional imports for type checking
if TYPE_CHECKING:
    from src.trading.regime_detector import RegimeDetector


logger = structlog.get_logger(__name__)


class EntrySignal(StrEnum):
    """Entry point signals."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WAIT = "wait"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class ManipulationType(StrEnum):
    """Types of market manipulation."""

    WASH_TRADING = "wash_trading"
    PUMP_AND_DUMP = "pump_and_dump"
    SPOOFING = "spoofing"
    LAYERING = "layering"
    NONE = "none"


class SentimentLevel(StrEnum):
    """Market sentiment levels."""

    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class Item:
    """Trading item representation."""

    item_id: str
    name: str
    game: str
    current_price: float
    suggested_price: float | None = None
    price_history: list[float] = field(default_factory=list)
    volume_history: list[int] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ManipulationAnalysis:
    """Result of manipulation detection."""

    detected: bool
    type: ManipulationType
    confidence: float  # 0.0 - 1.0
    indicators: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detected": self.detected,
            "type": self.type.value,
            "confidence": round(self.confidence, 2),
            "indicators": self.indicators,
            "recommendation": self.recommendation,
        }


@dataclass
class SentimentAnalysis:
    """Result of sentiment analysis."""

    level: SentimentLevel
    score: float  # -1.0 to 1.0
    sources: dict[str, float] = field(default_factory=dict)
    trending: bool = False
    mentions_24h: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": round(self.score, 2),
            "sources": self.sources,
            "trending": self.trending,
            "mentions_24h": self.mentions_24h,
        }


@dataclass
class EntryPointAnalysis:
    """Result of entry point calculation."""

    signal: EntrySignal
    confidence: float
    entry_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    risk_reward_ratio: float | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal": self.signal.value,
            "confidence": round(self.confidence, 2),
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "risk_reward_ratio": (
                round(self.risk_reward_ratio, 2) if self.risk_reward_ratio else None
            ),
            "reasons": self.reasons,
        }


class AdvancedTradingSkills:
    """Advanced trading capabilities from SkillsMP."""

    def __init__(
        self,
        min_data_points: int = 10,
        manipulation_threshold: float = 0.7,
    ):
        """
        Initialize advanced trading skills.

        Args:
            min_data_points: Minimum data points for analysis
            manipulation_threshold: Threshold for manipulation detection
        """
        self.min_data_points = min_data_points
        self.manipulation_threshold = manipulation_threshold

        # Lazy import for regime detector to avoid circular imports
        self._regime_detector: RegimeDetector | None = None

    @property
    def regime_detector(self) -> RegimeDetector:
        """Get regime detector instance."""
        if self._regime_detector is None:
            # Import at runtime to avoid circular imports
            from src.trading.regime_detector import RegimeDetector as RD

            self._regime_detector = RD()
        return self._regime_detector

    async def detect_market_manipulation(
        self,
        prices: list[float],
        volumes: list[int] | None = None,
    ) -> ManipulationAnalysis:
        """
        Detect potential market manipulation.

        Args:
            prices: Historical prices
            volumes: Historical volumes

        Returns:
            Manipulation analysis result
        """
        if len(prices) < self.min_data_points:
            return ManipulationAnalysis(
                detected=False,
                type=ManipulationType.NONE,
                confidence=0.0,
                recommendation="Insufficient data for analysis",
            )

        indicators = []
        confidence_scores = []

        # 1. Volume spike detection
        if volumes:
            volume_spike = await self._detect_volume_spike(volumes)
            if volume_spike > 0:
                indicators.append(f"Volume spike detected (score: {volume_spike:.2f})")
                confidence_scores.append(volume_spike)

        # 2. Price manipulation patterns
        price_manipulation = await self._detect_price_manipulation(prices)
        if price_manipulation > 0:
            indicators.append(
                f"Price manipulation pattern (score: {price_manipulation:.2f})"
            )
            confidence_scores.append(price_manipulation)

        # 3. Wash trading detection
        wash_trading = await self._detect_wash_trading(prices, volumes)
        if wash_trading > 0:
            indicators.append(f"Wash trading suspected (score: {wash_trading:.2f})")
            confidence_scores.append(wash_trading)

        # 4. Pump and dump detection
        pump_dump = await self._detect_pump_and_dump(prices)
        if pump_dump > 0:
            indicators.append(f"Pump and dump pattern (score: {pump_dump:.2f})")
            confidence_scores.append(pump_dump)

        # Calculate overall confidence
        if confidence_scores:
            overall_confidence = sum(confidence_scores) / len(confidence_scores)
        else:
            overall_confidence = 0.0

        # Determine manipulation type
        manipulation_type = ManipulationType.NONE
        if overall_confidence >= self.manipulation_threshold:
            if pump_dump > wash_trading and pump_dump > price_manipulation:
                manipulation_type = ManipulationType.PUMP_AND_DUMP
            elif wash_trading > 0.5:
                manipulation_type = ManipulationType.WASH_TRADING
            else:
                manipulation_type = ManipulationType.SPOOFING

        detected = overall_confidence >= self.manipulation_threshold

        recommendation = "Safe to trade"
        if detected:
            recommendation = (
                "AVOID - High risk of manipulation. Wait for market stabilization."
            )
        elif overall_confidence > 0.4:
            recommendation = (
                "CAUTION - Some manipulation indicators detected. Trade with care."
            )

        logger.info(
            "manipulation_analysis_complete",
            detected=detected,
            type=manipulation_type,
            confidence=overall_confidence,
        )

        return ManipulationAnalysis(
            detected=detected,
            type=manipulation_type,
            confidence=overall_confidence,
            indicators=indicators,
            recommendation=recommendation,
        )

    async def _detect_volume_spike(self, volumes: list[int]) -> float:
        """Detect abnormal volume spikes."""
        if len(volumes) < 5:
            return 0.0

        avg_volume = statistics.mean(volumes[:-1])
        if avg_volume == 0:
            return 0.0

        std_volume = (
            statistics.stdev(volumes[:-1]) if len(volumes) > 2 else avg_volume * 0.5
        )
        latest_volume = volumes[-1]

        # Calculate z-score
        z_score = (latest_volume - avg_volume) / (std_volume or 1)

        # Normalize to 0-1
        if z_score > 3:
            return min(1.0, z_score / 5)
        return 0.0

    async def _detect_price_manipulation(self, prices: list[float]) -> float:
        """Detect price manipulation patterns."""
        if len(prices) < 5:
            return 0.0

        # Calculate price changes
        changes = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] > 0
        ]

        if not changes:
            return 0.0

        # Look for unusual price movements
        avg_change = abs(statistics.mean(changes))
        max_change = max(abs(c) for c in changes)

        # Large sudden moves indicate manipulation
        if max_change > 0.2:  # 20%+ move
            return min(1.0, max_change * 2)

        # Consistent small increases (pump pattern)
        positive_changes = sum(1 for c in changes if c > 0.02)
        if positive_changes >= len(changes) * 0.8:
            return 0.5

        return 0.0

    async def _detect_wash_trading(
        self,
        prices: list[float],
        volumes: list[int] | None,
    ) -> float:
        """Detect wash trading (fake trades to inflate volume)."""
        if not volumes or len(volumes) < 5:
            return 0.0

        # Wash trading often shows high volume with minimal price movement
        price_change = abs(prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        avg_volume = statistics.mean(volumes)

        # High volume but low price movement
        if avg_volume > 100 and price_change < 0.01:
            return 0.6

        return 0.0

    async def _detect_pump_and_dump(self, prices: list[float]) -> float:
        """Detect pump and dump patterns."""
        if len(prices) < 10:
            return 0.0

        mid_point = len(prices) // 2

        # Calculate price change in first half (pump)
        pump_change = (
            (prices[mid_point] - prices[0]) / prices[0] if prices[0] > 0 else 0
        )

        # Calculate price change in second half (dump)
        dump_change = (
            (prices[-1] - prices[mid_point]) / prices[mid_point]
            if prices[mid_point] > 0
            else 0
        )

        # Classic pump and dump: rapid increase followed by rapid decrease
        if pump_change > 0.3 and dump_change < -0.2:
            return min(1.0, (pump_change - dump_change))

        return 0.0

    async def sentiment_analysis(self, item_name: str) -> SentimentAnalysis:
        """
        Analyze market sentiment for an item.

        Args:
            item_name: Name of the item

        Returns:
            Sentiment analysis result
        """
        # In production, this would integrate with:
        # - Reddit API for r/GlobalOffensiveTrade, etc.
        # - Twitter/X API
        # - Steam community forums
        # - Trading forums

        # For now, return neutral sentiment with mock data
        logger.info("sentiment_analysis", item=item_name)

        # Mock sentiment sources
        sources = {
            "reddit": 0.2,  # Slightly bullish
            "twitter": 0.0,  # Neutral
            "forums": -0.1,  # Slightly bearish
        }

        avg_score = statistics.mean(sources.values())

        level = SentimentLevel.NEUTRAL
        if avg_score > 0.6:
            level = SentimentLevel.VERY_BULLISH
        elif avg_score > 0.2:
            level = SentimentLevel.BULLISH
        elif avg_score < -0.6:
            level = SentimentLevel.VERY_BEARISH
        elif avg_score < -0.2:
            level = SentimentLevel.BEARISH

        return SentimentAnalysis(
            level=level,
            score=avg_score,
            sources=sources,
            trending=abs(avg_score) > 0.3,
            mentions_24h=42,  # Mock data
        )

    async def optimal_entry_point(self, item: Item) -> EntryPointAnalysis:
        """
        Calculate optimal entry point for an item.

        Args:
            item: Item to analyze

        Returns:
            Entry point analysis
        """
        reasons = []
        confidence = 0.5

        if len(item.price_history) < self.min_data_points:
            return EntryPointAnalysis(
                signal=EntrySignal.WAIT,
                confidence=0.3,
                reasons=["Insufficient historical data for analysis"],
            )

        # 1. Analyze market regime
        regime_analysis = self.regime_detector.detect_regime(item.price_history)

        # Import MarketRegime at runtime to avoid circular imports
        from src.trading.regime_detector import MarketRegime as MR

        # Regime-based entry logic
        if regime_analysis.regime == MR.TRENDING_DOWN:
            return EntryPointAnalysis(
                signal=EntrySignal.WAIT,
                confidence=0.7,
                reasons=["Market is in downtrend - wait for reversal"],
            )

        if regime_analysis.regime == MR.TRENDING_UP:
            reasons.append("Uptrend detected - momentum favorable")
            confidence += 0.2

        if regime_analysis.regime == MR.VOLATILE:
            reasons.append("High volatility - increased risk")
            confidence -= 0.1

        # 2. Calculate support/resistance levels
        avg_price = statistics.mean(item.price_history)
        min_price = min(item.price_history)
        max_price = max(item.price_history)

        # Entry near support is favorable
        if item.current_price <= avg_price * 1.05:
            reasons.append("Price near support level")
            confidence += 0.1

        # 3. Compare to suggested price
        if item.suggested_price:
            profit_margin = (
                item.suggested_price - item.current_price
            ) / item.current_price
            if profit_margin > 0.1:  # 10%+ profit potential
                reasons.append(f"Profit potential: {profit_margin:.1%}")
                confidence += 0.15
            elif profit_margin < 0.03:
                reasons.append("Low profit margin")
                confidence -= 0.1

        # 4. Check manipulation
        manipulation = await self.detect_market_manipulation(
            item.price_history,
            item.volume_history or None,
        )
        if manipulation.detected:
            return EntryPointAnalysis(
                signal=EntrySignal.WAIT,
                confidence=0.8,
                reasons=["Market manipulation detected - avoid"],
            )

        # 5. Calculate entry point and targets
        entry_price = item.current_price
        target_price = item.suggested_price or (avg_price * 1.1)
        stop_loss = min_price * 0.95

        # Risk/Reward ratio
        risk = entry_price - stop_loss
        reward = target_price - entry_price
        risk_reward = reward / risk if risk > 0 else 0

        if risk_reward > 2:
            reasons.append(f"Favorable R:R ratio ({risk_reward:.1f}:1)")
            confidence += 0.1
        elif risk_reward < 1:
            reasons.append("Poor risk/reward ratio")
            confidence -= 0.2

        # Determine final signal
        signal = EntrySignal.WAIT
        confidence = max(0.0, min(1.0, confidence))

        if confidence >= 0.7:
            signal = EntrySignal.STRONG_BUY
        elif confidence >= 0.55:
            signal = EntrySignal.BUY
        elif confidence <= 0.3:
            signal = EntrySignal.SELL

        logger.info(
            "entry_point_analysis",
            item=item.name,
            signal=signal,
            confidence=confidence,
        )

        return EntryPointAnalysis(
            signal=signal,
            confidence=confidence,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            risk_reward_ratio=risk_reward,
            reasons=reasons,
        )

    async def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        risk_percent: float = 0.02,  # 2% risk per trade
    ) -> dict[str, Any]:
        """
        Calculate optimal position size based on risk management.

        Args:
            account_balance: Total account balance
            entry_price: Planned entry price
            stop_loss: Stop loss price
            risk_percent: Maximum risk per trade (default 2%)

        Returns:
            Position sizing details
        """
        risk_amount = account_balance * risk_percent
        price_risk = abs(entry_price - stop_loss)

        if price_risk == 0:
            return {"error": "Stop loss cannot equal entry price"}

        quantity = risk_amount / price_risk
        position_value = quantity * entry_price

        return {
            "quantity": round(quantity, 2),
            "position_value": round(position_value, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_percent": risk_percent * 100,
            "max_loss": round(quantity * price_risk, 2),
        }

    async def analyze_trade_opportunity(
        self,
        item: Item,
        account_balance: float = 1000.0,
    ) -> dict[str, Any]:
        """
        Complete analysis of a trade opportunity.

        Args:
            item: Item to analyze
            account_balance: Account balance for position sizing

        Returns:
            Complete trade analysis
        """
        # 1. Entry point analysis
        entry = await self.optimal_entry_point(item)

        # 2. Sentiment analysis
        sentiment = await self.sentiment_analysis(item.name)

        # 3. Manipulation check
        manipulation = await self.detect_market_manipulation(
            item.price_history,
            item.volume_history or None,
        )

        # 4. Position sizing (if entry is favorable)
        position = None
        if entry.signal in (EntrySignal.BUY, EntrySignal.STRONG_BUY):
            position = await self.calculate_position_size(
                account_balance=account_balance,
                entry_price=entry.entry_price or item.current_price,
                stop_loss=entry.stop_loss or item.current_price * 0.95,
            )

        return {
            "item": {
                "name": item.name,
                "game": item.game,
                "current_price": item.current_price,
                "suggested_price": item.suggested_price,
            },
            "entry_analysis": entry.to_dict(),
            "sentiment": sentiment.to_dict(),
            "manipulation": manipulation.to_dict(),
            "position_sizing": position,
            "recommendation": self._generate_recommendation(
                entry, sentiment, manipulation
            ),
        }

    def _generate_recommendation(
        self,
        entry: EntryPointAnalysis,
        sentiment: SentimentAnalysis,
        manipulation: ManipulationAnalysis,
    ) -> str:
        """Generate trading recommendation."""
        if manipulation.detected:
            return "🔴 AVOID - Market manipulation detected"

        if entry.signal == EntrySignal.STRONG_BUY:
            if sentiment.level in (SentimentLevel.BULLISH, SentimentLevel.VERY_BULLISH):
                return "🟢 STRONG BUY - Technical and sentiment aligned"
            return "🟢 BUY - Technical signals favorable"

        if entry.signal == EntrySignal.BUY:
            return "🟡 CONSIDER - Entry conditions acceptable"

        if entry.signal == EntrySignal.WAIT:
            return "⏳ WAIT - Wait for better entry conditions"

        return "🔴 AVOID - Unfavorable conditions"
