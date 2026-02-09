"""Base types for the strategy system.

This module contains shared enums, dataclasses, and the IFindingStrategy interface
used by all strategy implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

# ============================================================================
# Enums
# ============================================================================


class StrategyType(StrEnum):
    """Types of finding strategies."""

    CROSS_PLATFORM_ARBITRAGE = "cross_platform"
    INTRAMARKET_ARBITRAGE = "intramarket"
    FLOAT_VALUE_ARBITRAGE = "float_value"
    PATTERN_PHASE_ARBITRAGE = "pattern_phase"
    TARGET_SYSTEM = "target_system"
    SMART_MARKET_FINDER = "smart_market"
    ENHANCED_SCANNER = "enhanced_scanner"
    TRENDING_ITEMS = "trending_items"
    QUICK_FLIP = "quick_flip"


class RiskLevel(StrEnum):
    """Risk level for an opportunity."""

    VERY_LOW = "very_low"  # Instant arbitrage
    LOW = "low"  # Arbitrage with short lock
    MEDIUM = "medium"  # Investments 3-7 days
    HIGH = "high"  # Rare items, long lock
    VERY_HIGH = "very_high"  # Patterns, collectibles


class OpportunityStatus(StrEnum):
    """Status of an opportunity."""

    ACTIVE = "active"  # Current opportunity
    EXPIRED = "expired"  # Expired
    PURCHASED = "purchased"  # Purchased
    FAILED = "failed"  # Failed attempt
    PENDING = "pending"  # In processing


class ActionType(StrEnum):
    """Type of recommended action."""

    BUY_NOW = "buy_now"  # Buy now
    CREATE_TARGET = "create_target"  # Create target
    WATCH = "watch"  # Watch
    CREATE_ADVANCED_ORDER = "create_advanced_order"  # Advanced order
    SKIP = "skip"  # Skip


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class OpportunityScore:
    """Comprehensive score for an opportunity."""

    profit_score: float  # 0-100, profitability score
    liquidity_score: float  # 0-100, liquidity score
    risk_score: float  # 0-100, risk score (higher = riskier)
    confidence_score: float  # 0-100, confidence in assessment
    time_score: float  # 0-100, time to sell score

    @property
    def total_score(self) -> float:
        """Total weighted score."""
        weights = {
            "profit": 0.30,
            "liquidity": 0.25,
            "risk": 0.20,  # Inverted (100 - risk)
            "confidence": 0.15,
            "time": 0.10,
        }
        return (
            self.profit_score * weights["profit"]
            + self.liquidity_score * weights["liquidity"]
            + (100 - self.risk_score) * weights["risk"]
            + self.confidence_score * weights["confidence"]
            + self.time_score * weights["time"]
        )


@dataclass
class UnifiedOpportunity:
    """Unified opportunity structure for all strategies."""

    # Identification
    id: str
    title: str
    game: str

    # Strategy and type
    strategy_type: StrategyType
    action_type: ActionType

    # Prices
    buy_price: Decimal
    sell_price: Decimal
    profit_usd: Decimal
    profit_percent: Decimal

    # Scores
    score: OpportunityScore
    risk_level: RiskLevel

    # Status
    status: OpportunityStatus = OpportunityStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Strategy-specific additional data
    metadata: dict[str, Any] = field(default_factory=dict)

    # Float Value (for float strategies)
    float_value: float | None = None
    float_min: float | None = None
    float_max: float | None = None

    # Pattern/Phase (for pattern strategies)
    pattern_id: int | None = None
    phase: str | None = None

    # Trade Lock
    trade_lock_days: int = 0

    # Liquidity
    daily_sales: int | None = None
    offers_count: int = 0
    orders_count: int = 0

    # Price sources
    source_platform: str = "dmarket"
    target_platform: str | None = None

    # Recommendations
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "game": self.game,
            "strategy_type": self.strategy_type.value,
            "action_type": self.action_type.value,
            "buy_price": float(self.buy_price),
            "sell_price": float(self.sell_price),
            "profit_usd": float(self.profit_usd),
            "profit_percent": float(self.profit_percent),
            "total_score": self.score.total_score,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "trade_lock_days": self.trade_lock_days,
            "float_value": self.float_value,
            "pattern_id": self.pattern_id,
            "phase": self.phase,
            "notes": self.notes,
            "metadata": self.metadata,
        }


@dataclass
class StrategyConfig:
    """Strategy configuration."""

    # Common parameters
    game: str = "csgo"
    min_price: Decimal = Decimal("1.0")
    max_price: Decimal = Decimal("100.0")
    min_profit_percent: Decimal = Decimal("5.0")
    min_profit_usd: Decimal = Decimal("0.30")
    limit: int = 50

    # Risk and liquidity
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    min_liquidity_score: float = 30.0
    min_daily_sales: int = 3

    # Trade Lock
    max_trade_lock_days: int = 7

    # Float filters
    float_min: float | None = None
    float_max: float | None = None

    # Pattern filters
    pattern_ids: list[int] | None = None
    phases: list[str] | None = None

    # Caching
    cache_ttl_seconds: int = 300  # 5 minutes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "game": self.game,
            "min_price": float(self.min_price),
            "max_price": float(self.max_price),
            "min_profit_percent": float(self.min_profit_percent),
            "min_profit_usd": float(self.min_profit_usd),
            "limit": self.limit,
            "max_risk_level": self.max_risk_level.value,
            "min_liquidity_score": self.min_liquidity_score,
            "min_daily_sales": self.min_daily_sales,
            "max_trade_lock_days": self.max_trade_lock_days,
            "float_min": self.float_min,
            "float_max": self.float_max,
            "pattern_ids": self.pattern_ids,
            "phases": self.phases,
        }


# ============================================================================
# Strategy Interface
# ============================================================================


class IFindingStrategy(ABC):
    """Abstract interface for all finding strategies."""

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Strategy type."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Strategy description."""

    @abstractmethod
    async def find_opportunities(
        self,
        config: StrategyConfig,
    ) -> list[UnifiedOpportunity]:
        """Find opportunities for given configuration.

        Args:
            config: Search configuration

        Returns:
            List of unified opportunities
        """

    @abstractmethod
    def validate_config(self, config: StrategyConfig) -> bool:
        """Validate configuration for this strategy.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid
        """

    def get_default_config(self) -> StrategyConfig:
        """Get default configuration for strategy.

        Returns:
            Default configuration
        """
        return StrategyConfig()
