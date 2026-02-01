"""Tests for portfolio/analyzer.py - Portfolio risk and diversification analysis.

Phase 3 tests for achieving 80% coverage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.portfolio.analyzer import (
    ConcentrationRisk,
    DiversificationReport,
    PortfolioAnalyzer,
    RiskReport,
)
from src.portfolio.models import (
    ItemCategory,
    ItemRarity,
    Portfolio,
    PortfolioItem,
)


# ============================================================================
# ConcentrationRisk Tests
# ============================================================================


class TestConcentrationRisk:
    """Tests for ConcentrationRisk dataclass."""

    def test_concentration_risk_creation(self):
        """Test basic ConcentrationRisk creation."""
        risk = ConcentrationRisk(
            item_title="AK-47 | Redline",
            value=Decimal("500.00"),
            percentage=35.0,
            risk_level="high",
        )

        assert risk.item_title == "AK-47 | Redline"
        assert risk.value == Decimal("500.00")
        assert risk.percentage == 35.0
        assert risk.risk_level == "high"

    def test_concentration_risk_to_dict(self):
        """Test ConcentrationRisk to_dict conversion."""
        risk = ConcentrationRisk(
            item_title="Test Item",
            value=Decimal("100.00"),
            percentage=25.5,
            risk_level="medium",
        )

        result = risk.to_dict()

        assert result["item_title"] == "Test Item"
        assert result["value"] == 100.0
        assert result["percentage"] == 25.5
        assert result["risk_level"] == "medium"


# ============================================================================
# DiversificationReport Tests
# ============================================================================


class TestDiversificationReport:
    """Tests for DiversificationReport dataclass."""

    def test_diversification_report_defaults(self):
        """Test DiversificationReport default values."""
        report = DiversificationReport()

        assert report.by_game == {}
        assert report.by_category == {}
        assert report.by_rarity == {}
        assert report.concentration_risks == []
        assert report.diversification_score == 0.0
        assert report.recommendations == []

    def test_diversification_report_with_data(self):
        """Test DiversificationReport with data."""
        risk = ConcentrationRisk(
            item_title="Item",
            value=Decimal(100),
            percentage=50.0,
            risk_level="critical",
        )

        report = DiversificationReport(
            by_game={"csgo": 60.0, "dota2": 40.0},
            by_category={"weapon": 70.0, "sticker": 30.0},
            by_rarity={"covert": 50.0, "rare": 50.0},
            concentration_risks=[risk],
            diversification_score=65.0,
            recommendations=["Add more games"],
        )

        assert report.by_game == {"csgo": 60.0, "dota2": 40.0}
        assert len(report.concentration_risks) == 1
        assert report.diversification_score == 65.0

    def test_diversification_report_to_dict(self):
        """Test DiversificationReport to_dict conversion."""
        risk = ConcentrationRisk(
            item_title="Item",
            value=Decimal(100),
            percentage=50.0,
            risk_level="high",
        )

        report = DiversificationReport(
            by_game={"csgo": 100.0},
            concentration_risks=[risk],
            diversification_score=50.0,
            recommendations=["Diversify"],
        )

        result = report.to_dict()

        assert result["by_game"] == {"csgo": 100.0}
        assert len(result["concentration_risks"]) == 1
        assert result["diversification_score"] == 50.0
        assert result["recommendations"] == ["Diversify"]


# ============================================================================
# RiskReport Tests
# ============================================================================


class TestRiskReport:
    """Tests for RiskReport dataclass."""

    def test_risk_report_defaults(self):
        """Test RiskReport default values."""
        report = RiskReport()

        assert report.volatility_score == 0.0
        assert report.liquidity_score == 0.0
        assert report.concentration_score == 0.0
        assert report.overall_risk_score == 0.0
        assert report.risk_level == "low"
        assert report.high_risk_items == []
        assert report.recommendations == []

    def test_risk_report_with_data(self):
        """Test RiskReport with data."""
        report = RiskReport(
            volatility_score=45.0,
            liquidity_score=70.0,
            concentration_score=30.0,
            overall_risk_score=48.0,
            risk_level="medium",
            high_risk_items=["Item1", "Item2"],
            recommendations=["Reduce volatility"],
        )

        assert report.volatility_score == 45.0
        assert report.risk_level == "medium"
        assert len(report.high_risk_items) == 2

    def test_risk_report_to_dict(self):
        """Test RiskReport to_dict conversion."""
        report = RiskReport(
            volatility_score=50.0,
            overall_risk_score=50.0,
            risk_level="medium",
        )

        result = report.to_dict()

        assert result["volatility_score"] == 50.0
        assert result["overall_risk_score"] == 50.0
        assert result["risk_level"] == "medium"


# ============================================================================
# PortfolioAnalyzer Tests - Diversification
# ============================================================================


class TestPortfolioAnalyzerDiversification:
    """Tests for PortfolioAnalyzer diversification analysis."""

    @pytest.fixture()
    def analyzer(self):
        """Create PortfolioAnalyzer instance."""
        return PortfolioAnalyzer()

    @pytest.fixture()
    def empty_portfolio(self):
        """Create empty portfolio."""
        return Portfolio(user_id=12345, items=[])

    @pytest.fixture()
    def single_item_portfolio(self):
        """Create portfolio with single item."""
        item = PortfolioItem(
            item_id="item_001",
            title="AK-47 | Redline",
            game="csgo",
            quantity=1,
            buy_price=Decimal("10.00"),
            current_price=Decimal("15.00"),
            category=ItemCategory.WEAPON,
            rarity=ItemRarity.CLASSIFIED,
        )
        return Portfolio(user_id=12345, items=[item])

    @pytest.fixture()
    def diversified_portfolio(self):
        """Create diversified portfolio."""
        items = [
            PortfolioItem(
                item_id="item_001",
                title="AK-47 | Redline",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("15.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CLASSIFIED,
            ),
            PortfolioItem(
                item_id="item_002",
                title="Dragonclaw Hook",
                game="dota2",
                quantity=1,
                buy_price=Decimal("400.00"),
                current_price=Decimal("450.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.COVERT,
            ),
            PortfolioItem(
                item_id="item_003",
                title="Sticker | Titan",
                game="csgo",
                quantity=1,
                buy_price=Decimal("50.00"),
                current_price=Decimal("55.00"),
                category=ItemCategory.STICKER,
                rarity=ItemRarity.COVERT,
            ),
        ]
        return Portfolio(user_id=12345, items=items)

    def test_analyze_diversification_empty_portfolio(self, analyzer, empty_portfolio):
        """Test diversification analysis on empty portfolio."""
        result = analyzer.analyze_diversification(empty_portfolio)

        assert isinstance(result, DiversificationReport)
        assert result.diversification_score == 0
        assert "empty" in result.recommendations[0].lower()

    def test_analyze_diversification_single_item(self, analyzer, single_item_portfolio):
        """Test diversification analysis with single item."""
        result = analyzer.analyze_diversification(single_item_portfolio)

        assert isinstance(result, DiversificationReport)
        assert result.by_game.get("csgo", 0) == 100.0
        assert len(result.concentration_risks) > 0  # Should flag concentration

    def test_analyze_diversification_diversified(self, analyzer, diversified_portfolio):
        """Test diversification analysis with diversified portfolio."""
        result = analyzer.analyze_diversification(diversified_portfolio)

        assert isinstance(result, DiversificationReport)
        assert "csgo" in result.by_game
        assert "dota2" in result.by_game
        assert result.diversification_score > 0

    def test_analyze_diversification_high_concentration(self, analyzer):
        """Test detection of high concentration risk."""
        items = [
            PortfolioItem(
                item_id="item_001",
                title="Big Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("1000.00"),
                current_price=Decimal("1000.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.COVERT,
            ),
            PortfolioItem(
                item_id="item_002",
                title="Small Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.00"),
                category=ItemCategory.STICKER,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_diversification(portfolio)

        # Big Item is ~99% of portfolio, should be flagged
        assert any(r.item_title == "Big Item" for r in result.concentration_risks)

    def test_analyze_diversification_zero_value_portfolio(self, analyzer):
        """Test diversification analysis with zero value portfolio."""
        items = [
            PortfolioItem(
                item_id="item_001",
                title="Free Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal(0),
                current_price=Decimal(0),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_diversification(portfolio)

        assert isinstance(result, DiversificationReport)


# ============================================================================
# PortfolioAnalyzer Tests - Risk Analysis
# ============================================================================


class TestPortfolioAnalyzerRisk:
    """Tests for PortfolioAnalyzer risk analysis."""

    @pytest.fixture()
    def analyzer(self):
        """Create PortfolioAnalyzer instance."""
        return PortfolioAnalyzer()

    @pytest.fixture()
    def empty_portfolio(self):
        """Create empty portfolio."""
        return Portfolio(user_id=12345, items=[])

    def test_analyze_risk_empty_portfolio(self, analyzer, empty_portfolio):
        """Test risk analysis on empty portfolio."""
        result = analyzer.analyze_risk(empty_portfolio)

        assert isinstance(result, RiskReport)
        assert result.risk_level == "unknown"
        assert "empty" in result.recommendations[0].lower()

    def test_analyze_risk_low_risk(self, analyzer):
        """Test risk analysis for low risk portfolio."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title=f"Item{i}",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("11.00"),  # 10% profit
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            )
            for i in range(10)
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_risk(portfolio)

        assert result.risk_level in {"low", "medium"}

    def test_analyze_risk_high_volatility(self, analyzer):
        """Test risk analysis with high volatility items."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Winner",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("50.00"),  # +400%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Loser",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("20.00"),  # -80%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_risk(portfolio)

        assert result.volatility_score > 50  # High volatility

    def test_analyze_risk_low_liquidity(self, analyzer):
        """Test risk analysis with low liquidity items."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Expensive Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("1000.00"),
                current_price=Decimal("1000.00"),
                category=ItemCategory.KNIFE,
                rarity=ItemRarity.COVERT,  # Rare = less liquid
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_risk(portfolio)

        # Should have lower liquidity score
        assert result.liquidity_score < 100

    def test_analyze_risk_high_concentration(self, analyzer):
        """Test risk analysis with high concentration."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Dominant Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("900.00"),
                current_price=Decimal("900.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Small Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.00"),
                category=ItemCategory.STICKER,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_risk(portfolio)

        assert result.concentration_score > 50  # High concentration

    def test_analyze_risk_levels(self, analyzer):
        """Test different risk level classifications."""
        # Low risk scenario
        low_items = [
            PortfolioItem(
                item_id="item_auto",
                title=f"Item{i}",
                game=["csgo", "dota2"][i % 2],
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.50"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            )
            for i in range(20)
        ]
        low_portfolio = Portfolio(user_id=12345, items=low_items)
        low_result = analyzer.analyze_risk(low_portfolio)

        # Result should be calculable
        assert low_result.overall_risk_score >= 0

    def test_analyze_risk_zero_value(self, analyzer):
        """Test risk analysis with zero value portfolio."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Zero Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal(0),
                current_price=Decimal(0),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_risk(portfolio)

        assert isinstance(result, RiskReport)


# ============================================================================
# PortfolioAnalyzer Tests - Performers
# ============================================================================


class TestPortfolioAnalyzerPerformers:
    """Tests for PortfolioAnalyzer performer analysis."""

    @pytest.fixture()
    def analyzer(self):
        """Create PortfolioAnalyzer instance."""
        return PortfolioAnalyzer()

    @pytest.fixture()
    def mixed_portfolio(self):
        """Create portfolio with mixed performance."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Top Performer",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("30.00"),  # +200%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Mid Performer",
                game="csgo",
                quantity=1,
                buy_price=Decimal("20.00"),
                current_price=Decimal("22.00"),  # +10%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Worst Performer",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("50.00"),  # -50%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
        ]
        return Portfolio(user_id=12345, items=items)

    def test_get_top_performers(self, analyzer, mixed_portfolio):
        """Test getting top performers."""
        top = analyzer.get_top_performers(mixed_portfolio, limit=2)

        assert len(top) == 2
        assert top[0].title == "Top Performer"

    def test_get_top_performers_limit(self, analyzer, mixed_portfolio):
        """Test top performers with limit."""
        top = analyzer.get_top_performers(mixed_portfolio, limit=1)

        assert len(top) == 1
        assert top[0].title == "Top Performer"

    def test_get_worst_performers(self, analyzer, mixed_portfolio):
        """Test getting worst performers."""
        worst = analyzer.get_worst_performers(mixed_portfolio, limit=2)

        assert len(worst) == 2
        assert worst[0].title == "Worst Performer"

    def test_get_worst_performers_limit(self, analyzer, mixed_portfolio):
        """Test worst performers with limit."""
        worst = analyzer.get_worst_performers(mixed_portfolio, limit=1)

        assert len(worst) == 1
        assert worst[0].title == "Worst Performer"

    def test_performers_empty_portfolio(self, analyzer):
        """Test performers on empty portfolio."""
        portfolio = Portfolio(user_id=12345, items=[])

        top = analyzer.get_top_performers(portfolio, limit=5)
        worst = analyzer.get_worst_performers(portfolio, limit=5)

        assert len(top) == 0
        assert len(worst) == 0


# ============================================================================
# PortfolioAnalyzer Tests - Private Methods
# ============================================================================


class TestPortfolioAnalyzerPrivateMethods:
    """Tests for PortfolioAnalyzer private methods."""

    @pytest.fixture()
    def analyzer(self):
        """Create PortfolioAnalyzer instance."""
        return PortfolioAnalyzer()

    def test_calculate_distribution(self, analyzer):
        """Test distribution calculation."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Item1",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("100.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Item2",
                game="dota2",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("100.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
        ]

        distribution = analyzer._calculate_distribution(
            items, lambda x: x.game, Decimal("200.00")
        )

        assert distribution["csgo"] == 50.0
        assert distribution["dota2"] == 50.0

    def test_calculate_volatility_score_empty(self, analyzer):
        """Test volatility score with empty portfolio."""
        portfolio = Portfolio(user_id=12345, items=[])

        score = analyzer._calculate_volatility_score(portfolio)

        assert score == 0.0

    def test_calculate_volatility_score_single_item(self, analyzer):
        """Test volatility score with single item."""
        item = PortfolioItem(
            item_id="item_auto",
            title="Item",
            game="csgo",
            quantity=1,
            buy_price=Decimal("10.00"),
            current_price=Decimal("15.00"),  # +50%
            category=ItemCategory.WEAPON,
            rarity=ItemRarity.CONSUMER,
        )
        portfolio = Portfolio(user_id=12345, items=[item])

        score = analyzer._calculate_volatility_score(portfolio)

        assert score == 50.0  # abs(pnl_percent)

    def test_calculate_liquidity_score_empty(self, analyzer):
        """Test liquidity score with empty portfolio."""
        portfolio = Portfolio(user_id=12345, items=[])

        score = analyzer._calculate_liquidity_score(portfolio)

        assert score == 100.0

    def test_calculate_liquidity_score_zero_value(self, analyzer):
        """Test liquidity score with zero value."""
        item = PortfolioItem(
            item_id="item_auto",
            title="Item",
            game="csgo",
            quantity=1,
            buy_price=Decimal(0),
            current_price=Decimal(0),
            category=ItemCategory.WEAPON,
            rarity=ItemRarity.CONSUMER,
        )
        portfolio = Portfolio(user_id=12345, items=[item])

        score = analyzer._calculate_liquidity_score(portfolio)

        assert score == 100.0

    def test_calculate_concentration_score_empty(self, analyzer):
        """Test concentration score with empty items."""
        score = analyzer._calculate_concentration_score([], Decimal(0))

        assert score == 0.0

    def test_find_high_risk_items(self, analyzer):
        """Test finding high risk items."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="High Concentration",
                game="csgo",
                quantity=1,
                buy_price=Decimal("400.00"),
                current_price=Decimal("400.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Large Loss",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("50.00"),  # -50%
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Very Expensive",
                game="csgo",
                quantity=1,
                buy_price=Decimal("600.00"),
                current_price=Decimal("600.00"),
                category=ItemCategory.KNIFE,
                rarity=ItemRarity.COVERT,
            ),
        ]

        high_risk = analyzer._find_high_risk_items(items, Decimal("1050.00"))

        assert len(high_risk) > 0

    def test_generate_diversification_recommendations_single_game(self, analyzer):
        """Test recommendations for single game portfolio."""
        by_game = {"csgo": 100.0}
        by_category = {"weapon": 100.0}
        concentration_risks = []
        score = 25.0

        recs = analyzer._generate_diversification_recommendations(
            by_game, by_category, concentration_risks, score
        )

        assert any("diversifying" in r.lower() for r in recs)

    def test_generate_diversification_recommendations_good(self, analyzer):
        """Test recommendations for well-diversified portfolio."""
        by_game = {"csgo": 33.0, "dota2": 33.0, "tf2": 34.0}
        by_category = {"weapon": 30.0, "sticker": 30.0, "case": 40.0}
        concentration_risks = []
        score = 85.0

        recs = analyzer._generate_diversification_recommendations(
            by_game, by_category, concentration_risks, score
        )

        assert any("well diversified" in r.lower() for r in recs)

    def test_generate_risk_recommendations_high_volatility(self, analyzer):
        """Test recommendations for high volatility."""
        recs = analyzer._generate_risk_recommendations(
            volatility=60.0,
            liquidity=80.0,
            concentration=30.0,
            high_risk_items=[],
        )

        assert any("volatile" in r.lower() for r in recs)

    def test_generate_risk_recommendations_low_liquidity(self, analyzer):
        """Test recommendations for low liquidity."""
        recs = analyzer._generate_risk_recommendations(
            volatility=30.0,
            liquidity=40.0,
            concentration=30.0,
            high_risk_items=[],
        )

        assert any("illiquid" in r.lower() for r in recs)

    def test_generate_risk_recommendations_high_concentration(self, analyzer):
        """Test recommendations for high concentration."""
        recs = analyzer._generate_risk_recommendations(
            volatility=30.0,
            liquidity=80.0,
            concentration=60.0,
            high_risk_items=[],
        )

        assert any("concentration" in r.lower() for r in recs)

    def test_generate_risk_recommendations_good(self, analyzer):
        """Test recommendations for good risk profile."""
        recs = analyzer._generate_risk_recommendations(
            volatility=30.0,
            liquidity=80.0,
            concentration=30.0,
            high_risk_items=[],
        )

        assert any("manageable" in r.lower() for r in recs)


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestPortfolioAnalyzerEdgeCases:
    """Edge case tests for PortfolioAnalyzer."""

    @pytest.fixture()
    def analyzer(self):
        """Create PortfolioAnalyzer instance."""
        return PortfolioAnalyzer()

    def test_very_large_portfolio(self, analyzer):
        """Test with very large portfolio."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title=f"Item{i}",
                game=["csgo", "dota2", "tf2", "rust"][i % 4],
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            )
            for i in range(1000)
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        div_result = analyzer.analyze_diversification(portfolio)
        risk_result = analyzer.analyze_risk(portfolio)

        assert isinstance(div_result, DiversificationReport)
        assert isinstance(risk_result, RiskReport)

    def test_extreme_price_differences(self, analyzer):
        """Test with extreme price differences."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title="Cheap Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("0.01"),
                current_price=Decimal("0.01"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            ),
            PortfolioItem(
                item_id="item_auto",
                title="Expensive Item",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100000.00"),
                current_price=Decimal("100000.00"),
                category=ItemCategory.KNIFE,
                rarity=ItemRarity.CONTRABAND,
            ),
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_diversification(portfolio)

        # Should detect extreme concentration
        assert len(result.concentration_risks) > 0

    def test_all_same_game_category(self, analyzer):
        """Test with all items in same game and category."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title=f"AK-47 Skin {i}",
                game="csgo",
                quantity=1,
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CLASSIFIED,
            )
            for i in range(5)
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        result = analyzer.analyze_diversification(portfolio)

        assert result.by_game.get("csgo", 0) == 100.0
        assert "weapon" in result.by_category

    def test_negative_pnl_all_items(self, analyzer):
        """Test with all items having negative P&L."""
        items = [
            PortfolioItem(
                item_id="item_auto",
                title=f"Loser{i}",
                game="csgo",
                quantity=1,
                buy_price=Decimal("100.00"),
                current_price=Decimal("50.00"),
                category=ItemCategory.WEAPON,
                rarity=ItemRarity.CONSUMER,
            )
            for i in range(5)
        ]
        portfolio = Portfolio(user_id=12345, items=items)

        risk_result = analyzer.analyze_risk(portfolio)

        # Should have high risk items (large losses)
        assert len(risk_result.high_risk_items) > 0
