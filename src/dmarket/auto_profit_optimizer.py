"""Auto-Profit Optimizer - automatically optimize trading parameters for maximum profit.

This module provides intelligent optimization of:
- Minimum profit thresholds based on market conditions
- Target price calculations
- Timing of trades (when to buy/sell)
- Position sizing based on risk tolerance
- Rebalancing recommendations

Usage:
    ```python
    from src.dmarket.auto_profit_optimizer import AutoProfitOptimizer

    optimizer = AutoProfitOptimizer(
        balance=100.0,
        risk_tolerance="medium",
    )

    # Get optimized trading parameters
    params = await optimizer.get_optimal_parameters(
        market_volatility=0.15,
        avg_daily_volume=50,
    )

    # Apply recommendations
    min_profit = params.min_profit_threshold
    position_size = params.max_position_size
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


class RiskTolerance(StrEnum):
    """Risk tolerance levels."""

    CONSERVATIVE = "conservative"  # Low risk, stable returns
    MODERATE = "moderate"  # Balanced approach
    AGGRESSIVE = "aggressive"  # Higher risk for higher returns


class MarketCondition(StrEnum):
    """Current market condition."""

    BULL = "bull"  # Rising prices
    BEAR = "bear"  # Falling prices
    STABLE = "stable"  # Sideways movement
    VOLATILE = "volatile"  # High volatility


@dataclass
class TradingParameters:
    """Optimized trading parameters."""

    # Profit thresholds
    min_profit_threshold: float  # Minimum profit to execute trade
    target_profit_percent: float  # Target profit percentage
    stop_loss_percent: float  # Maximum acceptable loss

    # Position sizing
    max_position_size: float  # Maximum amount per trade
    max_portfolio_percent: float  # Max % of balance per item
    max_concurrent_positions: int  # Max simultaneous trades

    # Timing
    recommended_hold_hours: int  # Recommended holding time
    optimal_entry_discount: float  # Discount from avg price to enter

    # Risk management
    diversification_ratio: float  # How spread out positions should be
    reserve_balance_percent: float  # % of balance to keep as reserve

    # Market-specific
    market_condition: MarketCondition
    volatility_adjustment: float  # Adjustment factor for volatility

    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profit": {
                "min_threshold": round(self.min_profit_threshold, 2),
                "target_percent": round(self.target_profit_percent, 2),
                "stop_loss_percent": round(self.stop_loss_percent, 2),
            },
            "position": {
                "max_size": round(self.max_position_size, 2),
                "max_portfolio_percent": round(self.max_portfolio_percent, 2),
                "max_concurrent": self.max_concurrent_positions,
            },
            "timing": {
                "hold_hours": self.recommended_hold_hours,
                "entry_discount": round(self.optimal_entry_discount, 3),
            },
            "risk": {
                "diversification": round(self.diversification_ratio, 2),
                "reserve_percent": round(self.reserve_balance_percent, 2),
            },
            "market": {
                "condition": self.market_condition,
                "volatility_adjustment": round(self.volatility_adjustment, 2),
            },
        }


@dataclass
class PositionRecommendation:
    """Recommendation for a specific position."""

    item_name: str
    action: str  # "buy", "sell", "hold", "close"
    reason: str
    urgency: str  # "immediate", "soon", "when_convenient"
    target_price: float | None = None
    quantity: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item": self.item_name,
            "action": self.action,
            "reason": self.reason,
            "urgency": self.urgency,
            "target_price": self.target_price,
            "quantity": self.quantity,
        }


class AutoProfitOptimizer:
    """Automatically optimize trading parameters for maximum profit."""

    # Base parameters by risk tolerance
    RISK_PROFILES: dict[RiskTolerance, dict[str, Any]] = {
        RiskTolerance.CONSERVATIVE: {
            "min_roi_percent": 5.0,
            "target_roi_percent": 10.0,
            "stop_loss_percent": 3.0,
            "max_portfolio_percent": 10.0,
            "max_concurrent": 5,
            "reserve_percent": 30.0,
            "diversification": 0.8,
        },
        RiskTolerance.MODERATE: {
            "min_roi_percent": 3.0,
            "target_roi_percent": 8.0,
            "stop_loss_percent": 5.0,
            "max_portfolio_percent": 15.0,
            "max_concurrent": 10,
            "reserve_percent": 20.0,
            "diversification": 0.6,
        },
        RiskTolerance.AGGRESSIVE: {
            "min_roi_percent": 2.0,
            "target_roi_percent": 15.0,
            "stop_loss_percent": 8.0,
            "max_portfolio_percent": 25.0,
            "max_concurrent": 20,
            "reserve_percent": 10.0,
            "diversification": 0.4,
        },
    }

    # Commission rate for DMarket
    DMARKET_COMMISSION = 0.07  # 7%

    def __init__(
        self,
        balance: float,
        risk_tolerance: RiskTolerance | str = RiskTolerance.MODERATE,
        currency: str = "USD",
    ) -> None:
        """Initialize optimizer.

        Args:
            balance: Current account balance
            risk_tolerance: Risk tolerance level
            currency: Currency (USD default)

        """
        self.balance = balance
        self.risk_tolerance = (
            RiskTolerance(risk_tolerance)
            if isinstance(risk_tolerance, str)
            else risk_tolerance
        )
        self.currency = currency
        self._profile = self.RISK_PROFILES[self.risk_tolerance]

    async def get_optimal_parameters(
        self,
        market_volatility: float = 0.10,
        avg_daily_volume: int = 30,
        current_positions: int = 0,
    ) -> TradingParameters:
        """Get optimized trading parameters based on current conditions.

        Args:
            market_volatility: Current market volatility (0-1)
            avg_daily_volume: Average daily trading volume
            current_positions: Number of current open positions

        Returns:
            Optimized TradingParameters

        """
        # Determine market condition
        market_condition = self._assess_market_condition(
            volatility=market_volatility,
            volume=avg_daily_volume,
        )

        # Calculate volatility adjustment
        volatility_adjustment = self._calculate_volatility_adjustment(market_volatility)

        # Calculate profit thresholds
        base_min_roi = self._profile["min_roi_percent"]
        adjusted_min_roi = base_min_roi * volatility_adjustment

        # Ensure profit covers commission
        min_profit_percent = max(
            adjusted_min_roi,
            self.DMARKET_COMMISSION * 100 + 1.0,  # At least 1% above commission
        )

        # Calculate position sizing
        avAlgolable_balance = self.balance * (1 - self._profile["reserve_percent"] / 100)
        max_position = avAlgolable_balance * (
            self._profile["max_portfolio_percent"] / 100
        )

        # Adjust for current positions
        # Note: remaining_slots calculation kept for future use in position sizing
        _ = max(
            0,
            self._profile["max_concurrent"] - current_positions,
        )

        # Calculate optimal entry discount
        entry_discount = self._calculate_entry_discount(
            volatility=market_volatility,
            market_condition=market_condition,
        )

        # Calculate recommended hold time
        hold_hours = self._calculate_hold_time(
            volume=avg_daily_volume,
            volatility=market_volatility,
        )

        params = TradingParameters(
            min_profit_threshold=min_profit_percent,
            target_profit_percent=self._profile["target_roi_percent"]
            * volatility_adjustment,
            stop_loss_percent=self._profile["stop_loss_percent"],
            max_position_size=max_position,
            max_portfolio_percent=self._profile["max_portfolio_percent"],
            max_concurrent_positions=self._profile["max_concurrent"],
            recommended_hold_hours=hold_hours,
            optimal_entry_discount=entry_discount,
            diversification_ratio=self._profile["diversification"],
            reserve_balance_percent=self._profile["reserve_percent"],
            market_condition=market_condition,
            volatility_adjustment=volatility_adjustment,
        )

        logger.info(
            "parameters_optimized",
            risk_tolerance=self.risk_tolerance,
            market_condition=market_condition,
            min_profit=round(min_profit_percent, 2),
            max_position=round(max_position, 2),
        )

        return params

    def calculate_optimal_buy_price(
        self,
        current_price: float,
        target_profit_percent: float,
        market_volatility: float = 0.10,
    ) -> float:
        """Calculate optimal buy price for target profit.

        Args:
            current_price: Current market price
            target_profit_percent: Desired profit percentage
            market_volatility: Current volatility

        Returns:
            Optimal maximum buy price

        """
        # Account for commission
        effective_sell = current_price * (1 - self.DMARKET_COMMISSION)

        # Calculate buy price for target profit
        target_multiplier = 1 + (target_profit_percent / 100)
        optimal_buy = effective_sell / target_multiplier

        # Add volatility buffer
        volatility_buffer = optimal_buy * market_volatility * 0.5
        optimal_buy -= volatility_buffer

        return round(optimal_buy, 2)

    def calculate_optimal_sell_price(
        self,
        buy_price: float,
        min_profit_percent: float = 5.0,
    ) -> float:
        """Calculate optimal sell price after purchase.

        Args:
            buy_price: Price item was purchased at
            min_profit_percent: Minimum desired profit

        Returns:
            Minimum sell price for profit

        """
        # Calculate break-even (accounting for commission)
        break_even = buy_price / (1 - self.DMARKET_COMMISSION)

        # Add profit margin
        target_price = break_even * (1 + min_profit_percent / 100)

        return round(target_price, 2)

    async def get_rebalancing_recommendations(
        self,
        current_positions: list[dict[str, Any]],
    ) -> list[PositionRecommendation]:
        """Get recommendations for rebalancing portfolio.

        Args:
            current_positions: List of current positions with:
                - item_name: Item name
                - buy_price: Purchase price
                - current_price: Current market price
                - quantity: Amount held
                - hold_time_hours: How long held

        Returns:
            List of position recommendations

        """
        recommendations = []

        for position in current_positions:
            item_name = position.get("item_name", "Unknown")
            buy_price = position.get("buy_price", 0)
            current_price = position.get("current_price", 0)
            hold_time = position.get("hold_time_hours", 0)

            if buy_price <= 0 or current_price <= 0:
                continue

            # Calculate current P&L
            commission = current_price * self.DMARKET_COMMISSION
            net_price = current_price - commission
            profit_percent = ((net_price - buy_price) / buy_price) * 100

            # Generate recommendation
            rec = self._generate_position_recommendation(
                item_name=item_name,
                buy_price=buy_price,
                current_price=current_price,
                profit_percent=profit_percent,
                hold_time=hold_time,
            )

            if rec:
                recommendations.append(rec)

        # Sort by urgency
        urgency_order = {"immediate": 0, "soon": 1, "when_convenient": 2}
        recommendations.sort(key=lambda r: urgency_order.get(r.urgency, 3))

        return recommendations

    def _assess_market_condition(
        self,
        volatility: float,
        volume: int,
    ) -> MarketCondition:
        """Assess current market condition."""
        if volatility > 0.25:
            return MarketCondition.VOLATILE
        if volume > 50 and volatility < 0.10:
            return MarketCondition.BULL
        if volume < 10:
            return MarketCondition.BEAR
        return MarketCondition.STABLE

    def _calculate_volatility_adjustment(self, volatility: float) -> float:
        """Calculate adjustment factor based on volatility."""
        if volatility < 0.05:
            return 0.8  # Low volatility: can accept lower margins
        if volatility < 0.15:
            return 1.0  # Normal
        if volatility < 0.25:
            return 1.3  # High volatility: need higher margins
        return 1.5  # Very high volatility

    def _calculate_entry_discount(
        self,
        volatility: float,
        market_condition: MarketCondition,
    ) -> float:
        """Calculate optimal entry discount from average price."""
        base_discount = 0.02  # 2% base

        # Adjust for volatility
        volatility_bonus = volatility * 0.3

        # Adjust for market condition
        condition_bonus = {
            MarketCondition.BULL: -0.01,  # Less discount needed
            MarketCondition.BEAR: 0.03,  # Need bigger discount
            MarketCondition.STABLE: 0.0,
            MarketCondition.VOLATILE: 0.02,
        }.get(market_condition, 0)

        return base_discount + volatility_bonus + condition_bonus

    def _calculate_hold_time(
        self,
        volume: int,
        volatility: float,
    ) -> int:
        """Calculate recommended holding time in hours."""
        # Base hold time inversely related to volume
        base_hours = max(1, 24 * 7 // max(1, volume))

        # Adjust for volatility
        if volatility > 0.20:
            base_hours = int(base_hours * 0.5)  # Sell faster in volatile market

        return min(168, max(1, base_hours))  # 1 hour to 1 week

    def _generate_position_recommendation(
        self,
        item_name: str,
        buy_price: float,
        current_price: float,
        profit_percent: float,
        hold_time: int,
    ) -> PositionRecommendation | None:
        """Generate recommendation for a single position."""
        target_profit = self._profile["target_roi_percent"]
        stop_loss = self._profile["stop_loss_percent"]

        # Check if profit target reached
        if profit_percent >= target_profit:
            return PositionRecommendation(
                item_name=item_name,
                action="sell",
                reason=f"Profit target reached ({profit_percent:.1f}%)",
                urgency="immediate",
                target_price=current_price,
            )

        # Check for stop loss
        if profit_percent <= -stop_loss:
            return PositionRecommendation(
                item_name=item_name,
                action="close",
                reason=f"Stop loss triggered ({profit_percent:.1f}%)",
                urgency="immediate",
                target_price=current_price,
            )

        # Check for extended hold time
        if hold_time > 168 and profit_percent < 0:  # > 1 week
            return PositionRecommendation(
                item_name=item_name,
                action="sell",
                reason=f"Extended hold time with loss ({hold_time}h)",
                urgency="soon",
                target_price=current_price,
            )

        # Profitable but below target
        if profit_percent > 3.0:  # Above commission
            return PositionRecommendation(
                item_name=item_name,
                action="hold",
                reason=f"Profitable ({profit_percent:.1f}%), waiting for target",
                urgency="when_convenient",
            )

        return None


# Factory function
def create_optimizer(
    balance: float,
    risk_tolerance: str = "moderate",
) -> AutoProfitOptimizer:
    """Create an auto-profit optimizer instance."""
    return AutoProfitOptimizer(
        balance=balance,
        risk_tolerance=risk_tolerance,
    )
