"""Portfolio analyzer for risk and diversification analysis.

Provides analytics for portfolio optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import logging
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from .models import Portfolio, PortfolioItem


logger = logging.getLogger(__name__)


@dataclass
class ConcentrationRisk:
    """Risk from concentration in single item/category.

    Attributes:
        item_title: Item or category name
        value: Value of this concentration
        percentage: Percentage of portfolio
        risk_level: Risk level (low/medium/high/critical)
    """

    item_title: str
    value: Decimal
    percentage: float
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_title": self.item_title,
            "value": float(self.value),
            "percentage": self.percentage,
            "risk_level": self.risk_level,
        }


@dataclass
class DiversificationReport:
    """Report on portfolio diversification.

    Attributes:
        by_game: Distribution by game
        by_category: Distribution by category
        by_rarity: Distribution by rarity
        concentration_risks: High concentration areas
        diversification_score: Overall score (0-100)
        recommendations: Improvement suggestions
    """

    by_game: dict[str, float] = field(default_factory=dict)
    by_category: dict[str, float] = field(default_factory=dict)
    by_rarity: dict[str, float] = field(default_factory=dict)
    concentration_risks: list[ConcentrationRisk] = field(default_factory=list)
    diversification_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "by_game": self.by_game,
            "by_category": self.by_category,
            "by_rarity": self.by_rarity,
            "concentration_risks": [r.to_dict() for r in self.concentration_risks],
            "diversification_score": self.diversification_score,
            "recommendations": self.recommendations,
        }


@dataclass
class RiskReport:
    """Comprehensive risk analysis report.

    Attributes:
        volatility_score: Portfolio volatility (0-100)
        liquidity_score: Ease of selling (0-100)
        concentration_score: Concentration risk (0-100, lower is better)
        overall_risk_score: Combined risk score (0-100)
        risk_level: Overall risk level
        high_risk_items: Items contributing most to risk
        recommendations: Risk mitigation suggestions
    """

    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    concentration_score: float = 0.0
    overall_risk_score: float = 0.0
    risk_level: str = "low"
    high_risk_items: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "volatility_score": self.volatility_score,
            "liquidity_score": self.liquidity_score,
            "concentration_score": self.concentration_score,
            "overall_risk_score": self.overall_risk_score,
            "risk_level": self.risk_level,
            "high_risk_items": self.high_risk_items,
            "recommendations": self.recommendations,
        }


class PortfolioAnalyzer:
    """Analyzer for portfolio risk and diversification.

    Provides tools for understanding portfolio composition
    and identifying optimization opportunities.
    """

    # Concentration thresholds
    CONCENTRATION_HIGH = 30.0  # >30% is high concentration
    CONCENTRATION_CRITICAL = 50.0  # >50% is critical

    # Diversification score weights
    GAME_WEIGHT = 0.3
    CATEGORY_WEIGHT = 0.4
    ITEM_WEIGHT = 0.3

    def analyze_diversification(self, portfolio: Portfolio) -> DiversificationReport:
        """Analyze portfolio diversification.

        Args:
            portfolio: Portfolio to analyze

        Returns:
            DiversificationReport with analysis
        """
        if not portfolio.items:
            return DiversificationReport(
                diversification_score=0,
                recommendations=["Your portfolio is empty. Start adding items!"],
            )

        total_value = sum(item.current_value for item in portfolio.items)
        if total_value == 0:
            return DiversificationReport()

        # Ensure total_value is Decimal for type safety
        total_value_decimal = (
            Decimal(total_value) if not isinstance(total_value, Decimal) else total_value
        )

        # Calculate distributions
        by_game = self._calculate_distribution(
            portfolio.items, lambda x: x.game, total_value_decimal
        )
        by_category = self._calculate_distribution(
            portfolio.items, lambda x: x.category.value, total_value_decimal
        )
        by_rarity = self._calculate_distribution(
            portfolio.items, lambda x: x.rarity.value, total_value_decimal
        )

        # Find concentration risks
        concentration_risks = self._find_concentration_risks(portfolio.items, total_value_decimal)

        # Calculate diversification score
        diversification_score = self._calculate_diversification_score(
            by_game, by_category, portfolio.items, total_value_decimal
        )

        # Generate recommendations
        recommendations = self._generate_diversification_recommendations(
            by_game, by_category, concentration_risks, diversification_score
        )

        return DiversificationReport(
            by_game=by_game,
            by_category=by_category,
            by_rarity=by_rarity,
            concentration_risks=concentration_risks,
            diversification_score=diversification_score,
            recommendations=recommendations,
        )

    def analyze_risk(self, portfolio: Portfolio) -> RiskReport:
        """Analyze portfolio risk.

        Args:
            portfolio: Portfolio to analyze

        Returns:
            RiskReport with analysis
        """
        if not portfolio.items:
            return RiskReport(
                risk_level="unknown",
                recommendations=["Cannot assess risk on empty portfolio"],
            )

        total_value = sum(item.current_value for item in portfolio.items)
        if total_value == 0:
            return RiskReport()

        # Ensure total_value is Decimal for type safety
        total_value_decimal = (
            Decimal(total_value) if not isinstance(total_value, Decimal) else total_value
        )

        # Calculate risk scores
        volatility_score = self._calculate_volatility_score(portfolio)
        liquidity_score = self._calculate_liquidity_score(portfolio)
        concentration_score = self._calculate_concentration_score(
            portfolio.items, total_value_decimal
        )

        # Overall risk
        overall_risk_score = (
            volatility_score * 0.3 + (100 - liquidity_score) * 0.3 + concentration_score * 0.4
        )

        # Determine risk level
        if overall_risk_score < 25:
            risk_level = "low"
        elif overall_risk_score < 50:
            risk_level = "medium"
        elif overall_risk_score < 75:
            risk_level = "high"
        else:
            risk_level = "critical"

        # Find high risk items
        high_risk_items = self._find_high_risk_items(portfolio.items, total_value_decimal)

        # Generate recommendations
        recommendations = self._generate_risk_recommendations(
            volatility_score,
            liquidity_score,
            concentration_score,
            high_risk_items,
        )

        return RiskReport(
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            concentration_score=concentration_score,
            overall_risk_score=overall_risk_score,
            risk_level=risk_level,
            high_risk_items=high_risk_items,
            recommendations=recommendations,
        )

    def get_top_performers(
        self,
        portfolio: Portfolio,
        limit: int = 5,
    ) -> list[PortfolioItem]:
        """Get top performing items by P&L %.

        Args:
            portfolio: Portfolio to analyze
            limit: Number of items to return

        Returns:
            List of top performers
        """
        return sorted(
            portfolio.items,
            key=lambda x: x.pnl_percent,
            reverse=True,
        )[:limit]

    def get_worst_performers(
        self,
        portfolio: Portfolio,
        limit: int = 5,
    ) -> list[PortfolioItem]:
        """Get worst performing items by P&L %.

        Args:
            portfolio: Portfolio to analyze
            limit: Number of items to return

        Returns:
            List of worst performers
        """
        return sorted(
            portfolio.items,
            key=lambda x: x.pnl_percent,
        )[:limit]

    def _calculate_distribution(
        self,
        items: list[PortfolioItem],
        key_func: Any,
        total_value: Decimal,
    ) -> dict[str, float]:
        """Calculate value distribution by key."""
        distribution: dict[str, Decimal] = {}

        for item in items:
            key = key_func(item)
            if key not in distribution:
                distribution[key] = Decimal(0)
            distribution[key] += item.current_value

        return {k: float(v / total_value * 100) for k, v in distribution.items()}

    def _find_concentration_risks(
        self,
        items: list[PortfolioItem],
        total_value: Decimal,
    ) -> list[ConcentrationRisk]:
        """Find areas of high concentration."""
        risks: list[ConcentrationRisk] = []

        # Check individual items
        for item in items:
            percentage = float(item.current_value / total_value * 100)
            if percentage >= self.CONCENTRATION_HIGH:
                risk_level = "critical" if percentage >= self.CONCENTRATION_CRITICAL else "high"
                risks.append(
                    ConcentrationRisk(
                        item_title=item.title,
                        value=item.current_value,
                        percentage=percentage,
                        risk_level=risk_level,
                    )
                )

        # Check categories
        by_category: dict[str, Decimal] = {}
        for item in items:
            cat = item.category.value
            if cat not in by_category:
                by_category[cat] = Decimal(0)
            by_category[cat] += item.current_value

        for cat, value in by_category.items():
            percentage = float(value / total_value * 100)
            if percentage >= self.CONCENTRATION_HIGH:
                risk_level = "critical" if percentage >= self.CONCENTRATION_CRITICAL else "high"
                risks.append(
                    ConcentrationRisk(
                        item_title=f"Category: {cat}",
                        value=value,
                        percentage=percentage,
                        risk_level=risk_level,
                    )
                )

        return sorted(risks, key=lambda x: x.percentage, reverse=True)

    def _calculate_diversification_score(
        self,
        by_game: dict[str, float],
        by_category: dict[str, float],
        items: list[PortfolioItem],
        total_value: Decimal,
    ) -> float:
        """Calculate overall diversification score (0-100)."""
        # Game diversity (more games = better)
        game_score = min(len(by_game) * 25, 100)  # Max 4 games

        # Category diversity
        category_score = min(len(by_category) * 15, 100)  # Max ~7 categories

        # Item diversity (check for concentration)
        max_item_concentration = 0.0
        for item in items:
            concentration = float(item.current_value / total_value * 100)
            max_item_concentration = max(max_item_concentration, concentration)

        # Lower concentration = higher score
        item_score = max(0, 100 - max_item_concentration)

        # Weighted average
        return (
            game_score * self.GAME_WEIGHT
            + category_score * self.CATEGORY_WEIGHT
            + item_score * self.ITEM_WEIGHT
        )

    def _calculate_volatility_score(self, portfolio: Portfolio) -> float:
        """Calculate volatility score based on P&L distribution."""
        if not portfolio.items:
            return 0.0

        pnl_percents = [item.pnl_percent for item in portfolio.items]

        if len(pnl_percents) < 2:
            return abs(pnl_percents[0]) if pnl_percents else 0.0

        # Standard deviation of P&L %
        mean = sum(pnl_percents) / len(pnl_percents)
        variance = sum((p - mean) ** 2 for p in pnl_percents) / len(pnl_percents)
        std_dev = variance**0.5

        # Normalize to 0-100 scale (assuming 50% std dev = 100 score)
        return min(std_dev * 2, 100)

    def _calculate_liquidity_score(self, portfolio: Portfolio) -> float:
        """Calculate liquidity score based on item types.

        Higher value items and rare items are less liquid.
        """
        if not portfolio.items:
            return 100.0

        total_value = sum(item.current_value for item in portfolio.items)
        if total_value == 0:
            return 100.0

        # High value items reduce liquidity
        high_value_ratio = (
            sum(item.current_value for item in portfolio.items if item.current_price > Decimal(100))
            / total_value
        )

        # Rare items reduce liquidity
        rare_ratio = (
            sum(
                item.current_value
                for item in portfolio.items
                if item.rarity.value in {"covert", "contraband", "extraordinary"}
            )
            / total_value
        )

        liquidity = 100 - (float(high_value_ratio) * 30 + float(rare_ratio) * 20)
        return max(0, min(100, liquidity))

    def _calculate_concentration_score(
        self,
        items: list[PortfolioItem],
        total_value: Decimal,
    ) -> float:
        """Calculate concentration score (higher = more concentrated = riskier)."""
        if not items or total_value == 0:
            return 0.0

        # Herfindahl-Hirschman Index
        hhi = sum((float(item.current_value / total_value * 100)) ** 2 for item in items)

        # Normalize to 0-100 scale
        # Perfect diversification across 10 items = 1000 HHI
        # Single item = 10000 HHI
        return min(hhi / 100, 100)

    def _find_high_risk_items(
        self,
        items: list[PortfolioItem],
        total_value: Decimal,
    ) -> list[str]:
        """Find items contributing most to portfolio risk."""
        high_risk: list[str] = []

        for item in items:
            # High concentration
            if item.current_value / total_value > Decimal("0.3"):
                high_risk.append(f"{item.title} (high concentration)")
            # Large loss
            elif item.pnl_percent < -20:
                high_risk.append(f"{item.title} (large loss: {item.pnl_percent:.1f}%)")
            # Very expensive item
            elif item.current_price > Decimal(500):
                high_risk.append(f"{item.title} (high value item)")

        return high_risk[:5]  # Top 5

    def _generate_diversification_recommendations(
        self,
        by_game: dict[str, float],
        by_category: dict[str, float],
        concentration_risks: list[ConcentrationRisk],
        score: float,
    ) -> list[str]:
        """Generate diversification recommendations."""
        recommendations: list[str] = []

        if score < 30:
            recommendations.append("⚠️ Portfolio is highly concentrated")

        if len(by_game) == 1:
            recommendations.append("Consider diversifying across multiple games")

        if len(by_category) < 3:
            recommendations.append("Add items from different categories (weapons, stickers, cases)")

        for risk in concentration_risks[:2]:
            if risk.risk_level == "critical":
                recommendations.append(
                    f"🔴 Critical: {risk.item_title} is {risk.percentage:.1f}% of portfolio"
                )
            elif risk.risk_level == "high":
                recommendations.append(
                    f"🟡 High: {risk.item_title} is {risk.percentage:.1f}% of portfolio"
                )

        if not recommendations:
            recommendations.append("✅ Portfolio is well diversified!")

        return recommendations

    def _generate_risk_recommendations(
        self,
        volatility: float,
        liquidity: float,
        concentration: float,
        high_risk_items: list[str],
    ) -> list[str]:
        """Generate risk mitigation recommendations."""
        recommendations: list[str] = []

        if volatility > 50:
            recommendations.append("Consider selling volatile items with large losses")

        if liquidity < 50:
            recommendations.append(
                "Portfolio contains many illiquid items - consider more liquid alternatives"
            )

        if concentration > 50:
            recommendations.append("Reduce concentration by selling largest positions partially")

        for item in high_risk_items[:2]:
            recommendations.append(f"Review: {item}")

        if not recommendations:
            recommendations.append("✅ Portfolio risk is manageable")

        return recommendations


__all__ = [
    "ConcentrationRisk",
    "DiversificationReport",
    "PortfolioAnalyzer",
    "RiskReport",
]
