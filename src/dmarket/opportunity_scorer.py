"""Arbitrage Opportunity Scorer - intelligent scoring for trade opportunities.

This module provides intelligent scoring of arbitrage opportunities based on:
- Profit margin and ROI
- Liquidity and volume analysis
- Price volatility risk
- Historical success rate
- Time-to-sell estimation
- Competition analysis
- Seasonal factors

The scorer helps prioritize which opportunities to act on first.

Usage:
    ```python
    from src.dmarket.opportunity_scorer import OpportunityScorer, TradeOpportunity

    scorer = OpportunityScorer()

    opportunity = TradeOpportunity(
        item_name="AK-47 | Redline",
        buy_price=10.00,
        sell_price=12.50,
        platform_buy="dmarket",
        platform_sell="waxpeer",
    )

    score = await scorer.score_opportunity(opportunity)

    if score.total_score >= 70:
        await execute_trade(opportunity)
    ```

Created: January 6, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Commission rates for different platforms
PLATFORM_COMMISSIONS: dict[str, float] = {
    "dmarket": 0.07,  # 7%
    "waxpeer": 0.06,  # 6%
    "steam": 0.13,  # 13%
    "buff163": 0.025,  # 2.5%
}


class RiskLevel(StrEnum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class OpportunityType(StrEnum):
    """Type of arbitrage opportunity."""

    CROSS_PLATFORM = "cross_platform"  # Buy on one platform, sell on another
    INTRAMARKET = "intramarket"  # Buy and sell on same platform
    TARGET_BASED = "target_based"  # Using buy orders
    INSTANT_BUY = "instant_buy"  # Direct purchase


@dataclass
class TradeOpportunity:
    """Represents a trading opportunity."""

    item_name: str
    buy_price: float
    sell_price: float
    platform_buy: str = "dmarket"
    platform_sell: str = "dmarket"
    opportunity_type: OpportunityType = OpportunityType.CROSS_PLATFORM

    # Optional metadata
    game: str = "csgo"
    item_id: str | None = None
    quantity_available: int = 1
    average_sell_time_hours: float | None = None
    daily_volume: int | None = None
    price_volatility: float | None = None
    competition_count: int | None = None

    @property
    def gross_profit(self) -> float:
        """Calculate gross profit before commission."""
        return self.sell_price - self.buy_price

    @property
    def net_profit(self) -> float:
        """Calculate net profit after commissions."""
        sell_commission = PLATFORM_COMMISSIONS.get(self.platform_sell, 0.07)
        net_sell = self.sell_price * (1 - sell_commission)
        return net_sell - self.buy_price

    @property
    def roi_percent(self) -> float:
        """Calculate ROI percentage."""
        if self.buy_price <= 0:
            return 0.0
        return (self.net_profit / self.buy_price) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "platform_buy": self.platform_buy,
            "platform_sell": self.platform_sell,
            "opportunity_type": self.opportunity_type,
            "game": self.game,
            "gross_profit": self.gross_profit,
            "net_profit": round(self.net_profit, 2),
            "roi_percent": round(self.roi_percent, 2),
        }


@dataclass
class OpportunityScore:
    """Scoring result for a trade opportunity."""

    opportunity: TradeOpportunity

    # Individual scores (0-100)
    profit_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 0.0
    speed_score: float = 0.0
    competition_score: float = 0.0
    confidence_score: float = 0.0

    # Aggregated
    total_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM

    # Recommendations
    recommended_action: str = "hold"
    priority_rank: int = 0

    scored_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_recommended(self) -> bool:
        """Check if opportunity is recommended for execution."""
        return self.total_score >= 60 and self.risk_level in {
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "opportunity": self.opportunity.to_dict(),
            "scores": {
                "profit": round(self.profit_score, 1),
                "liquidity": round(self.liquidity_score, 1),
                "risk": round(self.risk_score, 1),
                "speed": round(self.speed_score, 1),
                "competition": round(self.competition_score, 1),
                "confidence": round(self.confidence_score, 1),
            },
            "total_score": round(self.total_score, 1),
            "risk_level": self.risk_level,
            "recommended_action": self.recommended_action,
            "is_recommended": self.is_recommended,
            "priority_rank": self.priority_rank,
        }


class OpportunityScorer:
    """Score and rank arbitrage opportunities."""

    # Scoring weights (must sum to 1.0)
    WEIGHTS: dict[str, float] = {
        "profit": 0.30,  # 30% weight
        "liquidity": 0.20,  # 20% weight
        "risk": 0.20,  # 20% weight
        "speed": 0.15,  # 15% weight
        "competition": 0.10,  # 10% weight
        "confidence": 0.05,  # 5% weight
    }

    # ROI thresholds for profit scoring
    ROI_THRESHOLDS: dict[str, float] = {
        "excellent": 15.0,  # 15%+ ROI
        "good": 10.0,  # 10%+ ROI
        "acceptable": 5.0,  # 5%+ ROI
        "minimum": 3.0,  # 3%+ ROI (DMarket commission)
    }

    # Daily volume thresholds
    VOLUME_THRESHOLDS: dict[str, int] = {
        "high": 50,  # 50+ sales/day
        "medium": 20,  # 20+ sales/day
        "low": 5,  # 5+ sales/day
    }

    def __init__(
        self,
        min_roi_percent: float = 3.0,
        max_risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
        prefer_fast_sales: bool = True,
    ) -> None:
        """Initialize scorer.

        Args:
            min_roi_percent: Minimum ROI to consider
            max_risk_tolerance: Maximum acceptable risk level
            prefer_fast_sales: Prefer items that sell quickly

        """
        self.min_roi_percent = min_roi_percent
        self.max_risk_tolerance = max_risk_tolerance
        self.prefer_fast_sales = prefer_fast_sales

    async def score_opportunity(
        self,
        opportunity: TradeOpportunity,
        price_history: list[dict[str, Any]] | None = None,
    ) -> OpportunityScore:
        """Score a single opportunity.

        Args:
            opportunity: Trade opportunity to score
            price_history: Optional historical price data

        Returns:
            OpportunityScore with detailed breakdown

        """
        # Calculate individual scores
        profit_score = self._score_profit(opportunity)
        liquidity_score = self._score_liquidity(opportunity)
        risk_score = self._score_risk(opportunity, price_history)
        speed_score = self._score_speed(opportunity)
        competition_score = self._score_competition(opportunity)
        confidence_score = self._score_confidence(opportunity)

        # Calculate weighted total
        total_score = (
            profit_score * self.WEIGHTS["profit"]
            + liquidity_score * self.WEIGHTS["liquidity"]
            + risk_score * self.WEIGHTS["risk"]
            + speed_score * self.WEIGHTS["speed"]
            + competition_score * self.WEIGHTS["competition"]
            + confidence_score * self.WEIGHTS["confidence"]
        )

        # Determine risk level
        risk_level = self._determine_risk_level(
            roi=opportunity.roi_percent,
            volatility=opportunity.price_volatility,
            volume=opportunity.daily_volume,
        )

        # Determine recommended action
        recommended_action = self._determine_action(
            total_score=total_score,
            risk_level=risk_level,
            roi=opportunity.roi_percent,
        )

        score = OpportunityScore(
            opportunity=opportunity,
            profit_score=profit_score,
            liquidity_score=liquidity_score,
            risk_score=risk_score,
            speed_score=speed_score,
            competition_score=competition_score,
            confidence_score=confidence_score,
            total_score=total_score,
            risk_level=risk_level,
            recommended_action=recommended_action,
        )

        logger.info(
            "opportunity_scored",
            item=opportunity.item_name,
            total_score=round(total_score, 1),
            roi=round(opportunity.roi_percent, 2),
            risk_level=risk_level,
            action=recommended_action,
        )

        return score

    async def rank_opportunities(
        self,
        opportunities: list[TradeOpportunity],
    ) -> list[OpportunityScore]:
        """Score and rank multiple opportunities.

        Args:
            opportunities: List of opportunities to rank

        Returns:
            Sorted list of scored opportunities (highest score first)

        """
        scores = []

        for opp in opportunities:
            score = await self.score_opportunity(opp)
            scores.append(score)

        # Sort by total score (descending)
        scores.sort(key=lambda s: s.total_score, reverse=True)

        # Assign priority ranks
        for i, score in enumerate(scores):
            score.priority_rank = i + 1

        logger.info(
            "opportunities_ranked",
            total=len(scores),
            recommended=sum(1 for s in scores if s.is_recommended),
        )

        return scores

    def _score_profit(self, opportunity: TradeOpportunity) -> float:
        """Score based on profit potential."""
        roi = opportunity.roi_percent

        if roi >= self.ROI_THRESHOLDS["excellent"]:
            return 100.0
        if roi >= self.ROI_THRESHOLDS["good"]:
            return 80.0 + (roi - 10) * 2  # 80-100 range
        if roi >= self.ROI_THRESHOLDS["acceptable"]:
            return 60.0 + (roi - 5) * 4  # 60-80 range
        if roi >= self.ROI_THRESHOLDS["minimum"]:
            return 40.0 + (roi - 3) * 10  # 40-60 range
        if roi > 0:
            return roi * (40 / 3)  # 0-40 range
        return 0.0

    def _score_liquidity(self, opportunity: TradeOpportunity) -> float:
        """Score based on market liquidity."""
        volume = opportunity.daily_volume

        if volume is None:
            return 50.0  # Unknown, assume medium

        if volume >= self.VOLUME_THRESHOLDS["high"]:
            return 100.0
        if volume >= self.VOLUME_THRESHOLDS["medium"]:
            return 70.0 + (volume - 20) * 1  # 70-100 range
        if volume >= self.VOLUME_THRESHOLDS["low"]:
            return 40.0 + (volume - 5) * 2  # 40-70 range
        if volume > 0:
            return volume * 8  # 0-40 range
        return 10.0  # Very low liquidity

    def _score_risk(
        self,
        opportunity: TradeOpportunity,
        price_history: list[dict[str, Any]] | None,
    ) -> float:
        """Score based on risk (higher score = lower risk)."""
        volatility = opportunity.price_volatility

        # If we have price history, calculate volatility
        if price_history and volatility is None:
            prices = [p.get("price", 0) for p in price_history[-20:]]
            if len(prices) >= 2:
                import statistics

                mean_price = statistics.mean(prices)
                if mean_price > 0:
                    volatility = statistics.stdev(prices) / mean_price

        if volatility is None:
            return 50.0  # Unknown, assume medium risk

        # Lower volatility = higher score
        if volatility < 0.05:
            return 100.0  # Very stable
        if volatility < 0.10:
            return 80.0  # Stable
        if volatility < 0.20:
            return 60.0  # Moderate volatility
        if volatility < 0.30:
            return 40.0  # High volatility
        return 20.0  # Very high volatility

    def _score_speed(self, opportunity: TradeOpportunity) -> float:
        """Score based on expected time to sell."""
        sell_time = opportunity.average_sell_time_hours

        if sell_time is None:
            # Estimate based on volume
            volume = opportunity.daily_volume
            if volume is None:
                return 50.0
            # Higher volume = faster sales
            sell_time = 24 / max(1, volume) * 10  # Rough estimate

        if sell_time <= 1:
            return 100.0  # Sells within 1 hour
        if sell_time <= 6:
            return 85.0  # Sells within 6 hours
        if sell_time <= 24:
            return 70.0  # Sells within a day
        if sell_time <= 72:
            return 50.0  # Sells within 3 days
        if sell_time <= 168:
            return 30.0  # Sells within a week
        return 10.0  # Takes longer than a week

    def _score_competition(self, opportunity: TradeOpportunity) -> float:
        """Score based on competition (lower competition = higher score)."""
        competition = opportunity.competition_count

        if competition is None:
            return 50.0  # Unknown

        if competition == 0:
            return 100.0  # No competition
        if competition <= 3:
            return 85.0  # Low competition
        if competition <= 10:
            return 70.0  # Medium competition
        if competition <= 25:
            return 50.0  # High competition
        return 30.0  # Very high competition

    def _score_confidence(self, opportunity: TradeOpportunity) -> float:
        """Score based on data completeness and confidence."""
        confidence = 100.0

        # Penalize missing data
        if opportunity.daily_volume is None:
            confidence -= 15

        if opportunity.price_volatility is None:
            confidence -= 15

        if opportunity.average_sell_time_hours is None:
            confidence -= 10

        if opportunity.competition_count is None:
            confidence -= 10

        # Cross-platform has more variables
        if opportunity.opportunity_type == OpportunityType.CROSS_PLATFORM:
            confidence -= 5

        return max(30.0, confidence)

    def _determine_risk_level(
        self,
        roi: float,
        volatility: float | None,
        volume: int | None,
    ) -> RiskLevel:
        """Determine overall risk level."""
        risk_factors = 0

        # ROI risk
        if roi < 5:
            risk_factors += 1
        if roi < 3:
            risk_factors += 1

        # Volatility risk
        if volatility is not None:
            if volatility > 0.30:
                risk_factors += 2
            elif volatility > 0.20:
                risk_factors += 1

        # Volume risk
        if volume is not None:
            if volume < 5:
                risk_factors += 2
            elif volume < 20:
                risk_factors += 1

        if risk_factors >= 4:
            return RiskLevel.VERY_HIGH
        if risk_factors >= 3:
            return RiskLevel.HIGH
        if risk_factors >= 1:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _determine_action(
        self,
        total_score: float,
        risk_level: RiskLevel,
        roi: float,
    ) -> str:
        """Determine recommended action."""
        if roi < self.min_roi_percent:
            return "skip"  # Below minimum ROI

        if risk_level == RiskLevel.VERY_HIGH:
            return "avoid"  # Too risky

        if risk_level == RiskLevel.HIGH and total_score < 70:
            return "caution"  # Proceed with caution

        if total_score >= 80:
            return "strong_buy"  # Excellent opportunity
        if total_score >= 70:
            return "buy"  # Good opportunity
        if total_score >= 60:
            return "consider"  # Consider buying
        if total_score >= 50:
            return "monitor"  # Monitor for better entry
        return "skip"  # Not recommended


# Singleton instance
_scorer: OpportunityScorer | None = None


def get_opportunity_scorer() -> OpportunityScorer:
    """Get singleton scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = OpportunityScorer()
    return _scorer
