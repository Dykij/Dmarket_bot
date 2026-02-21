"""Smart Item Recommendations Module.

Provides intelligent item recommendations based on:
- User's trading history and profit patterns
- Market conditions and arbitrage opportunities
- Risk tolerance and balance
- Item liquidity and popularity
- Historical price trends

Usage:
    ```python
    from src.ml.smart_recommendations import SmartRecommendations

    recommender = SmartRecommendations(user_balance=100.0)

    # Get recommendations
    recs = await recommender.get_recommendations(
        available_items=items,
        user_inventory=inventory,
    )

    for rec in recs:
        print(f"{rec.item_name}: {rec.recommendation_type} - {rec.reason}")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class RecommendationType(StrEnum):
    """Types of recommendations."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    AVOID = "avoid"
    ARBITRAGE = "arbitrage"
    WATCHLIST = "watchlist"


class RiskLevel(StrEnum):
    """Risk level classification."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ItemRecommendation:
    """Single item recommendation."""

    item_name: str
    item_id: str
    recommendation_type: RecommendationType
    confidence: float  # 0-100
    risk_level: RiskLevel

    # Price info
    current_price: float
    target_price: float | None = None
    expected_profit: float | None = None
    expected_profit_percent: float | None = None

    # Reasons and details
    reason: str = ""
    factors: list[str] = field(default_factory=list)

    # Timing
    time_horizon: str = "24h"  # Expected time to realize profit
    urgency: str = "normal"  # "immediate", "high", "normal", "low"

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "item_id": self.item_id,
            "recommendation": self.recommendation_type.value,
            "confidence": round(self.confidence, 2),
            "risk_level": self.risk_level.value,
            "current_price": self.current_price,
            "target_price": self.target_price,
            "expected_profit": (
                round(self.expected_profit, 2) if self.expected_profit else None
            ),
            "expected_profit_percent": (
                round(self.expected_profit_percent, 2)
                if self.expected_profit_percent
                else None
            ),
            "reason": self.reason,
            "factors": self.factors,
            "time_horizon": self.time_horizon,
            "urgency": self.urgency,
        }


@dataclass
class RecommendationBatch:
    """Batch of recommendations."""

    recommendations: list[ItemRecommendation]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_potential_profit: float = 0.0
    avg_confidence: float = 0.0

    # Summary by type
    buy_count: int = 0
    sell_count: int = 0
    arbitrage_count: int = 0

    def sort_by_profit(self) -> None:
        """Sort recommendations by expected profit."""
        self.recommendations.sort(
            key=lambda x: x.expected_profit_percent or 0,
            reverse=True,
        )

    def sort_by_confidence(self) -> None:
        """Sort recommendations by confidence."""
        self.recommendations.sort(
            key=lambda x: x.confidence,
            reverse=True,
        )

    def filter_by_risk(self, max_risk: RiskLevel) -> list[ItemRecommendation]:
        """Filter recommendations by maximum risk level."""
        risk_order = [
            RiskLevel.VERY_LOW,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
        ]
        max_risk_idx = risk_order.index(max_risk)

        return [
            rec
            for rec in self.recommendations
            if risk_order.index(rec.risk_level) <= max_risk_idx
        ]


class SmartRecommendations:
    """Smart recommendation engine.

    Generates personalized item recommendations based on:
    - User's balance and risk tolerance
    - Market conditions
    - Historical trading performance
    - Arbitrage opportunities
    """

    # Commissions for profit calculation
    DMARKET_COMMISSION = 0.07  # 7%
    WAXPEER_COMMISSION = 0.06  # 6%
    STEAM_COMMISSION = 0.15  # 15%

    def __init__(
        self,
        user_balance: float = 100.0,
        risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
        max_single_item_percent: float = 0.3,  # Max 30% of balance per item
        min_profit_threshold: float = 0.05,  # Min 5% profit
        min_confidence_threshold: float = 50.0,
    ) -> None:
        """Initialize recommendation engine.

        Args:
            user_balance: User's current balance
            risk_tolerance: User's risk tolerance level
            max_single_item_percent: Max percentage of balance for single item
            min_profit_threshold: Minimum profit percentage for recommendation
            min_confidence_threshold: Minimum confidence for recommendation
        """
        self.user_balance = user_balance
        self.risk_tolerance = risk_tolerance
        self.max_single_item_percent = max_single_item_percent
        self.min_profit_threshold = min_profit_threshold
        self.min_confidence_threshold = min_confidence_threshold

        # Trading history for personalization
        self._trading_history: list[dict[str, Any]] = []
        self._successful_items: set[str] = set()
        self._avoided_items: set[str] = set()

        # Cache
        self._recommendation_cache: dict[str, ItemRecommendation] = {}
        self._cache_ttl = timedelta(minutes=10)

    def set_user_balance(self, balance: float) -> None:
        """Update user balance."""
        self.user_balance = max(0.0, balance)

    def set_risk_tolerance(self, risk: RiskLevel) -> None:
        """Update risk tolerance."""
        self.risk_tolerance = risk

    def add_trading_history(self, trade: dict[str, Any]) -> None:
        """Add trade to history for learning.

        Args:
            trade: Trade details with item_name, profit, etc.
        """
        self._trading_history.append(trade)

        # Track successful items
        if trade.get("profit", 0) > 0:
            self._successful_items.add(trade.get("item_name", ""))
        elif trade.get("profit", 0) < -trade.get("price", 0) * 0.1:  # >10% loss
            self._avoided_items.add(trade.get("item_name", ""))

    async def get_recommendations(
        self,
        available_items: list[dict[str, Any]],
        user_inventory: list[dict[str, Any]] | None = None,
        cross_platform_prices: dict[str, dict[str, float]] | None = None,
        max_recommendations: int = 10,
    ) -> RecommendationBatch:
        """Get personalized recommendations.

        Args:
            available_items: Items available on market
            user_inventory: User's current inventory
            cross_platform_prices: Prices on other platforms for arbitrage
            max_recommendations: Maximum number of recommendations

        Returns:
            RecommendationBatch with recommendations
        """
        recommendations: list[ItemRecommendation] = []

        # Analyze available items for buying
        for item in available_items:
            rec = await self._analyze_buy_opportunity(item, cross_platform_prices)
            if rec and rec.confidence >= self.min_confidence_threshold:
                recommendations.append(rec)

        # Analyze inventory for selling
        if user_inventory:
            for item in user_inventory:
                rec = await self._analyze_sell_opportunity(item, cross_platform_prices)
                if rec and rec.confidence >= self.min_confidence_threshold:
                    recommendations.append(rec)

        # Find arbitrage opportunities
        if cross_platform_prices:
            arb_recs = await self._find_arbitrage_opportunities(
                available_items,
                cross_platform_prices,
            )
            recommendations.extend(arb_recs)

        # Sort by expected profit
        recommendations.sort(
            key=lambda x: (x.expected_profit_percent or 0) * x.confidence / 100,
            reverse=True,
        )

        # Limit to max recommendations
        recommendations = recommendations[:max_recommendations]

        # Calculate summary and return
        return RecommendationBatch(
            recommendations=recommendations,
            total_potential_profit=sum(r.expected_profit or 0 for r in recommendations),
            avg_confidence=(
                sum(r.confidence for r in recommendations) / len(recommendations)
                if recommendations
                else 0
            ),
            buy_count=sum(
                1
                for r in recommendations
                if r.recommendation_type == RecommendationType.BUY
            ),
            sell_count=sum(
                1
                for r in recommendations
                if r.recommendation_type == RecommendationType.SELL
            ),
            arbitrage_count=sum(
                1
                for r in recommendations
                if r.recommendation_type == RecommendationType.ARBITRAGE
            ),
        )

    async def _analyze_buy_opportunity(
        self,
        item: dict[str, Any],
        cross_platform_prices: dict[str, dict[str, float]] | None = None,
    ) -> ItemRecommendation | None:
        """Analyze item for buy opportunity.

        Args:
            item: Item data
            cross_platform_prices: Prices on other platforms

        Returns:
            ItemRecommendation or None
        """
        item_name = item.get("title", item.get("name", "unknown"))
        item_id = item.get("itemId", item.get("id", ""))

        # Get price
        price_data = item.get("price", {})
        if isinstance(price_data, dict):
            current_price = float(price_data.get("USD", 0)) / 100
        else:
            current_price = float(price_data) / 100 if price_data else 0

        if current_price <= 0:
            return None

        # Check if within budget
        max_price = self.user_balance * self.max_single_item_percent
        if current_price > max_price:
            return None

        # Check if previously avoided
        if item_name in self._avoided_items:
            return None

        # Calculate factors
        factors = []
        confidence = 50.0  # Base confidence
        risk_level = RiskLevel.MEDIUM

        # Factor 1: Previous success with item
        if item_name in self._successful_items:
            confidence += 15
            factors.append("Previously profitable item")

        # Factor 2: Price relative to suggested price
        suggested_price = item.get("suggestedPrice", {})
        if isinstance(suggested_price, dict):
            suggested = float(suggested_price.get("USD", 0)) / 100
        else:
            suggested = 0

        if suggested > 0:
            discount = (suggested - current_price) / suggested
            if discount > 0.1:  # 10% below suggested
                confidence += 20
                factors.append(f"Price {discount:.1%} below suggested")
                risk_level = RiskLevel.LOW
            elif discount < -0.1:  # 10% above suggested
                confidence -= 20
                factors.append(f"Price {abs(discount):.1%} above suggested")
                risk_level = RiskLevel.HIGH

        # Factor 3: Cross-platform arbitrage potential
        target_price = current_price * 1.1  # Default 10% profit target
        if cross_platform_prices and item_name in cross_platform_prices:
            other_prices = cross_platform_prices[item_name]
            best_sell_price = max(other_prices.values()) if other_prices else 0

            if best_sell_price > current_price * 1.15:  # >15% profit potential
                confidence += 25
                target_price = best_sell_price * (1 - self.WAXPEER_COMMISSION)
                factors.append(
                    f"Cross-platform arbitrage: sell at ${best_sell_price:.2f}"
                )
                risk_level = RiskLevel.LOW

        # Factor 4: Liquidity (if available)
        if item.get("salesCount", 0) > 10:
            confidence += 10
            factors.append("High liquidity")
        elif item.get("salesCount", 0) < 3:
            confidence -= 10
            factors.append("Low liquidity")
            risk_level = RiskLevel.HIGH

        # Factor 5: Price trend
        price_history = item.get("priceHistory", [])
        if len(price_history) >= 5:
            recent_avg = sum(price_history[-5:]) / 5
            if current_price < recent_avg * 0.9:  # 10% below recent average
                confidence += 15
                factors.append("Price below recent average")
            elif current_price > recent_avg * 1.1:  # 10% above recent average
                confidence -= 15
                factors.append("Price above recent average")

        # Adjust confidence for risk tolerance
        confidence = self._adjust_for_risk_tolerance(confidence, risk_level)

        if confidence < self.min_confidence_threshold:
            return None

        # Calculate expected profit
        expected_profit = (
            target_price - current_price - (current_price * self.DMARKET_COMMISSION)
        )
        expected_profit_percent = (
            (expected_profit / current_price) * 100 if current_price > 0 else 0
        )

        if expected_profit_percent < self.min_profit_threshold * 100:
            return None

        return ItemRecommendation(
            item_name=item_name,
            item_id=item_id,
            recommendation_type=RecommendationType.BUY,
            confidence=min(100, max(0, confidence)),
            risk_level=risk_level,
            current_price=current_price,
            target_price=target_price,
            expected_profit=expected_profit,
            expected_profit_percent=expected_profit_percent,
            reason=f"Buy opportunity with {expected_profit_percent:.1f}% profit potential",
            factors=factors,
            time_horizon="24h",
            urgency="normal" if confidence < 70 else "high",
        )

    async def _analyze_sell_opportunity(
        self,
        item: dict[str, Any],
        cross_platform_prices: dict[str, dict[str, float]] | None = None,
    ) -> ItemRecommendation | None:
        """Analyze inventory item for sell opportunity.

        Args:
            item: Inventory item data
            cross_platform_prices: Prices on other platforms

        Returns:
            ItemRecommendation or None
        """
        item_name = item.get("title", item.get("name", "unknown"))
        item_id = item.get("itemId", item.get("id", ""))

        # Get purchase price and current price
        purchase_price = item.get("purchasePrice", 0)
        if isinstance(purchase_price, dict):
            purchase_price = float(purchase_price.get("USD", 0)) / 100
        else:
            purchase_price = float(purchase_price) / 100 if purchase_price else 0

        current_price = item.get("currentPrice", item.get("price", 0))
        if isinstance(current_price, dict):
            current_price = float(current_price.get("USD", 0)) / 100
        else:
            current_price = float(current_price) / 100 if current_price else 0

        if current_price <= 0:
            return None

        factors = []
        confidence = 50.0
        risk_level = RiskLevel.MEDIUM
        recommendation_type = RecommendationType.HOLD

        # Calculate current profit/loss
        if purchase_price > 0:
            profit_percent = ((current_price - purchase_price) / purchase_price) * 100
            net_profit = current_price * (1 - self.DMARKET_COMMISSION) - purchase_price

            if profit_percent > 20:  # >20% profit
                recommendation_type = RecommendationType.SELL
                confidence += 30
                factors.append(f"Take profit: {profit_percent:.1f}% gain")
                risk_level = RiskLevel.LOW
            elif profit_percent < -15:  # >15% loss
                recommendation_type = RecommendationType.SELL
                confidence += 10
                factors.append(f"Stop loss: {abs(profit_percent):.1f}% loss")
                risk_level = RiskLevel.HIGH
        else:
            profit_percent = 0
            net_profit = 0

        # Check cross-platform prices
        if cross_platform_prices and item_name in cross_platform_prices:
            other_prices = cross_platform_prices[item_name]
            best_sell_price = max(other_prices.values()) if other_prices else 0

            if best_sell_price > current_price * 1.1:
                recommendation_type = RecommendationType.SELL
                confidence += 20
                factors.append(
                    f"Better price on other platform: ${best_sell_price:.2f}"
                )

        # Hold time factor
        purchase_date = item.get("purchaseDate")
        if purchase_date:
            if isinstance(purchase_date, str):
                try:
                    purchase_date = datetime.fromisoformat(purchase_date)
                except ValueError:
                    purchase_date = None

            if purchase_date:
                hold_time = datetime.now(UTC) - purchase_date
                if hold_time > timedelta(days=30) and profit_percent < 5:
                    recommendation_type = RecommendationType.SELL
                    confidence += 10
                    factors.append(
                        f"Held for {hold_time.days} days with minimal profit"
                    )

        if recommendation_type == RecommendationType.HOLD:
            return None

        return ItemRecommendation(
            item_name=item_name,
            item_id=item_id,
            recommendation_type=recommendation_type,
            confidence=min(100, max(0, confidence)),
            risk_level=risk_level,
            current_price=current_price,
            target_price=current_price,
            expected_profit=net_profit,
            expected_profit_percent=profit_percent,
            reason=(
                f"Sell recommendation: {factors[0]}"
                if factors
                else "Sell to realize gains"
            ),
            factors=factors,
            time_horizon="immediate",
            urgency="high" if profit_percent > 20 or profit_percent < -15 else "normal",
        )

    async def _find_arbitrage_opportunities(
        self,
        items: list[dict[str, Any]],
        cross_platform_prices: dict[str, dict[str, float]],
    ) -> list[ItemRecommendation]:
        """Find cross-platform arbitrage opportunities.

        Args:
            items: Available items
            cross_platform_prices: Prices on other platforms

        Returns:
            List of arbitrage recommendations
        """
        recommendations = []

        for item in items:
            item_name = item.get("title", item.get("name", "unknown"))
            item_id = item.get("itemId", item.get("id", ""))

            # Get DMarket price
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                dmarket_price = float(price_data.get("USD", 0)) / 100
            else:
                dmarket_price = float(price_data) / 100 if price_data else 0

            if dmarket_price <= 0:
                continue

            # Check cross-platform prices
            if item_name not in cross_platform_prices:
                continue

            other_prices = cross_platform_prices[item_name]

            for platform, price in other_prices.items():
                # Calculate profit
                commission = (
                    self.WAXPEER_COMMISSION
                    if "waxpeer" in platform.lower()
                    else self.STEAM_COMMISSION
                )
                net_sell_price = price * (1 - commission)
                buy_cost = dmarket_price * (
                    1 + self.DMARKET_COMMISSION * 0.5
                )  # DMarket buyer commission is lower

                profit = net_sell_price - buy_cost
                profit_percent = (profit / buy_cost) * 100 if buy_cost > 0 else 0

                if profit_percent > 8:  # >8% profit after fees
                    confidence = min(90, 50 + profit_percent * 2)

                    recommendations.append(
                        ItemRecommendation(
                            item_name=item_name,
                            item_id=item_id,
                            recommendation_type=RecommendationType.ARBITRAGE,
                            confidence=confidence,
                            risk_level=(
                                RiskLevel.LOW
                                if profit_percent > 15
                                else RiskLevel.MEDIUM
                            ),
                            current_price=dmarket_price,
                            target_price=price,
                            expected_profit=profit,
                            expected_profit_percent=profit_percent,
                            reason=f"Arbitrage: Buy on DMarket, sell on {platform} for {profit_percent:.1f}% profit",
                            factors=[
                                f"DMarket price: ${dmarket_price:.2f}",
                                f"{platform} price: ${price:.2f}",
                                f"Net profit after fees: ${profit:.2f}",
                            ],
                            time_horizon="immediate",
                            urgency="high",
                        )
                    )

        return recommendations

    def _adjust_for_risk_tolerance(
        self,
        confidence: float,
        item_risk: RiskLevel,
    ) -> float:
        """Adjust confidence based on user's risk tolerance.

        Args:
            confidence: Base confidence
            item_risk: Item's risk level

        Returns:
            Adjusted confidence
        """
        risk_levels = [
            RiskLevel.VERY_LOW,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
        ]
        user_risk_idx = risk_levels.index(self.risk_tolerance)
        item_risk_idx = risk_levels.index(item_risk)

        # If item is riskier than user tolerance, reduce confidence
        risk_diff = item_risk_idx - user_risk_idx

        if risk_diff > 0:
            # Item is riskier than tolerance
            confidence -= risk_diff * 15
        elif risk_diff < 0:
            # Item is safer than tolerance
            confidence += abs(risk_diff) * 5

        return confidence

    def get_portfolio_recommendations(
        self,
        current_holdings: list[dict[str, Any]],
        target_diversification: int = 5,
    ) -> list[str]:
        """Get portfolio-level recommendations.

        Args:
            current_holdings: Current portfolio items
            target_diversification: Target number of different items

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check diversification
        unique_items = len({h.get("name", "") for h in current_holdings})
        if unique_items < target_diversification:
            recommendations.append(
                f"Consider diversifying: you have {unique_items} unique items, target is {target_diversification}"
            )

        # Check concentration
        total_value = sum(
            float(h.get("currentPrice", h.get("price", 0))) / 100
            for h in current_holdings
        )

        for holding in current_holdings:
            value = float(holding.get("currentPrice", holding.get("price", 0))) / 100
            if total_value > 0 and value / total_value > 0.4:  # >40% in one item
                recommendations.append(
                    f"High concentration risk: {holding.get('name', 'item')} is {value / total_value:.1%} of portfolio"
                )

        # Check balance utilization
        if self.user_balance > total_value * 2:
            recommendations.append("Underutilized balance: consider investing more")
        elif total_value > self.user_balance * 5:
            recommendations.append("High leverage: consider reducing positions")

        return recommendations


# Factory function
def create_smart_recommendations(
    user_balance: float = 100.0,
    risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
) -> SmartRecommendations:
    """Create smart recommendations instance.

    Args:
        user_balance: User's balance
        risk_tolerance: Risk tolerance level

    Returns:
        SmartRecommendations instance
    """
    return SmartRecommendations(
        user_balance=user_balance,
        risk_tolerance=risk_tolerance,
    )
