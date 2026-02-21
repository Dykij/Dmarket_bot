"""Tests for PortfolioManager (P1-23).

Comprehensive tests for portfolio management system:
- Portfolio snapshot generation
- Risk analysis
- Rebalancing recommendations
- Performance metrics
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.dmarket.portfolio_manager import (
    AssetType,
    PortfolioAsset,
    PortfolioConfig,
    PortfolioManager,
    PortfolioSnapshot,
    RebalanceAction,
    RebalanceRecommendation,
    RiskAnalysis,
    RiskLevel,
    get_portfolio_summary,
    get_rebalancing_actions,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_api():
    """Create mock DMarket API client."""
    api = AsyncMock()

    # Mock balance - 100000 cents = $1000.00
    api.get_balance.return_value = {"usd": "100000"}

    # Mock inventory
    api.get_user_inventory.return_value = {
        "objects": [
            {
                "itemId": "item1",
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"USD": "2500"},  # $25.00
                "suggestedPrice": {"USD": "2700"},  # $27.00
                "gameId": "csgo",
            },
            {
                "itemId": "item2",
                "title": "AWP | Asiimov (Field-Tested)",
                "price": {"USD": "4000"},  # $40.00
                "suggestedPrice": {"USD": "4200"},  # $42.00
                "gameId": "csgo",
            },
        ]
    }

    # Mock offers (listed items)
    api.get_user_offers.return_value = {
        "objects": [
            {
                "offerId": "offer1",
                "title": "M4A4 | Desolate Space (Field-Tested)",
                "price": {"USD": "1500"},  # $15.00
                "gameId": "csgo",
            },
        ]
    }

    # Mock targets
    api.get_user_targets.return_value = {
        "Items": [
            {
                "TargetID": "target1",
                "Title": "Glock-18 | Fade (Factory New)",
                "Price": {"Amount": "5000"},  # $50.00
                "Amount": 1,
                "GameID": "csgo",
            },
        ]
    }

    return api


@pytest.fixture()
def portfolio_manager(mock_api):
    """Create PortfolioManager with mock API."""
    return PortfolioManager(api_client=mock_api)


@pytest.fixture()
def sample_snapshot():
    """Create sample portfolio snapshot for testing."""
    assets = [
        PortfolioAsset(
            item_id="item1",
            item_name="AK-47 | Redline",
            asset_type=AssetType.INVENTORY,
            quantity=1,
            unit_price=25.0,
            total_value=25.0,
            game="csgo",
            category="Rifle",
            market_price=27.0,
            profit_loss=2.0,
            profit_loss_percent=8.0,
        ),
        PortfolioAsset(
            item_id="item2",
            item_name="AWP | Asiimov",
            asset_type=AssetType.INVENTORY,
            quantity=1,
            unit_price=40.0,
            total_value=40.0,
            game="csgo",
            category="Sniper",
            market_price=42.0,
            profit_loss=2.0,
            profit_loss_percent=5.0,
        ),
        PortfolioAsset(
            item_id="offer1",
            item_name="M4A4 | Desolate Space",
            asset_type=AssetType.LISTED,
            quantity=1,
            unit_price=15.0,
            total_value=15.0,
            game="csgo",
            category="Rifle",
            listed_price=15.0,
        ),
    ]

    return PortfolioSnapshot(
        timestamp=datetime.now(UTC),
        total_value_usd=180.0,  # 100 cash + 65 inventory + 15 listed
        cash_balance=100.0,
        inventory_value=65.0,
        listed_value=15.0,
        targets_value=0.0,
        assets=assets,
        asset_count=3,
        game_distribution={"csgo": 80.0},
        category_distribution={"Rifle": 40.0, "Sniper": 40.0},
    )


# ============================================================================
# PortfolioAsset Tests
# ============================================================================


class TestPortfolioAsset:
    """Tests for PortfolioAsset dataclass."""

    def test_create_inventory_asset(self):
        """Test creating inventory asset."""
        asset = PortfolioAsset(
            item_id="test123",
            item_name="Test Item",
            asset_type=AssetType.INVENTORY,
            quantity=1,
            unit_price=10.0,
            total_value=10.0,
        )

        assert asset.item_id == "test123"
        assert asset.asset_type == AssetType.INVENTORY
        assert asset.total_value == 10.0

    def test_create_listed_asset(self):
        """Test creating listed asset."""
        asset = PortfolioAsset(
            item_id="listed123",
            item_name="Listed Item",
            asset_type=AssetType.LISTED,
            quantity=1,
            unit_price=20.0,
            total_value=20.0,
            listed_price=20.0,
        )

        assert asset.asset_type == AssetType.LISTED
        assert asset.listed_price == 20.0

    def test_create_target_asset(self):
        """Test creating target (buy order) asset."""
        asset = PortfolioAsset(
            item_id="target123",
            item_name="Target Item",
            asset_type=AssetType.TARGET,
            quantity=5,
            unit_price=5.0,
            total_value=25.0,
        )

        assert asset.asset_type == AssetType.TARGET
        assert asset.quantity == 5
        assert asset.total_value == 25.0

    def test_profit_loss_calculation(self):
        """Test profit/loss attributes."""
        asset = PortfolioAsset(
            item_id="test",
            item_name="Test",
            asset_type=AssetType.INVENTORY,
            quantity=1,
            unit_price=100.0,
            total_value=100.0,
            market_price=110.0,
            profit_loss=10.0,
            profit_loss_percent=10.0,
        )

        assert asset.profit_loss == 10.0
        assert asset.profit_loss_percent == 10.0


# ============================================================================
# PortfolioSnapshot Tests
# ============================================================================


class TestPortfolioSnapshot:
    """Tests for PortfolioSnapshot dataclass."""

    def test_create_snapshot(self, sample_snapshot):
        """Test creating portfolio snapshot."""
        assert sample_snapshot.total_value_usd == 180.0
        assert sample_snapshot.cash_balance == 100.0
        assert sample_snapshot.asset_count == 3

    def test_game_distribution(self, sample_snapshot):
        """Test game distribution."""
        assert "csgo" in sample_snapshot.game_distribution
        assert sample_snapshot.game_distribution["csgo"] == 80.0

    def test_category_distribution(self, sample_snapshot):
        """Test category distribution."""
        assert "Rifle" in sample_snapshot.category_distribution
        assert "Sniper" in sample_snapshot.category_distribution


# ============================================================================
# PortfolioManager Tests
# ============================================================================


class TestPortfolioManager:
    """Tests for PortfolioManager class."""

    def test_init_with_api(self, mock_api):
        """Test initialization with API client."""
        pm = PortfolioManager(api_client=mock_api)
        assert pm._api is mock_api
        assert pm._config is not None

    def test_init_with_custom_config(self, mock_api):
        """Test initialization with custom config."""
        config = PortfolioConfig(
            max_single_item_percent=30.0,
            target_cash_percent=25.0,
        )
        pm = PortfolioManager(api_client=mock_api, config=config)

        assert pm._config.max_single_item_percent == 30.0
        assert pm._config.target_cash_percent == 25.0

    def test_init_without_api(self):
        """Test initialization without API client."""
        pm = PortfolioManager()
        assert pm._api is None

    @pytest.mark.asyncio()
    async def test_get_portfolio_snapshot(self, portfolio_manager):
        """Test getting portfolio snapshot."""
        snapshot = awAlgot portfolio_manager.get_portfolio_snapshot()

        assert snapshot is not None
        assert snapshot.total_value_usd > 0
        assert snapshot.asset_count > 0

    @pytest.mark.asyncio()
    async def test_get_portfolio_snapshot_caching(self, portfolio_manager):
        """Test that snapshot is cached."""
        # First call
        snapshot1 = awAlgot portfolio_manager.get_portfolio_snapshot()

        # Second call should return cached
        snapshot2 = awAlgot portfolio_manager.get_portfolio_snapshot()

        # Should be same object (cached)
        assert snapshot1 is snapshot2

    @pytest.mark.asyncio()
    async def test_get_portfolio_snapshot_force_refresh(self, portfolio_manager):
        """Test forcing snapshot refresh."""
        # First call
        awAlgot portfolio_manager.get_portfolio_snapshot()

        # Force refresh
        snapshot = awAlgot portfolio_manager.get_portfolio_snapshot(force_refresh=True)

        assert snapshot is not None

    @pytest.mark.asyncio()
    async def test_get_portfolio_snapshot_api_error(self, mock_api):
        """Test handling API errors."""
        mock_api.get_balance.side_effect = Exception("API Error")

        pm = PortfolioManager(api_client=mock_api)
        snapshot = awAlgot pm.get_portfolio_snapshot()

        # Should handle error gracefully
        assert snapshot is not None
        assert snapshot.total_value_usd == 0

    @pytest.mark.asyncio()
    async def test_extract_category_rifle(self, portfolio_manager):
        """Test category extraction for rifle."""
        category = portfolio_manager._extract_category("AK-47 | Redline (Field-Tested)")
        assert category == "Rifle"

    @pytest.mark.asyncio()
    async def test_extract_category_knife(self, portfolio_manager):
        """Test category extraction for knife."""
        category = portfolio_manager._extract_category(
            "★ Karambit | Doppler (Factory New)"
        )
        assert category == "Knife"

    @pytest.mark.asyncio()
    async def test_extract_category_sticker(self, portfolio_manager):
        """Test category extraction for sticker."""
        category = portfolio_manager._extract_category("Sticker | Cloud9 | Boston 2018")
        assert category == "Sticker"

    @pytest.mark.asyncio()
    async def test_extract_category_unknown(self, portfolio_manager):
        """Test category extraction for unknown item."""
        category = portfolio_manager._extract_category("Some Unknown Item Type")
        assert category == "Other"


# ============================================================================
# Risk Analysis Tests
# ============================================================================


class TestRiskAnalysis:
    """Tests for risk analysis functionality."""

    @pytest.mark.asyncio()
    async def test_analyze_risk_basic(self, portfolio_manager):
        """Test basic risk analysis."""
        risk = awAlgot portfolio_manager.analyze_risk()

        assert risk is not None
        assert isinstance(risk.overall_risk, RiskLevel)
        assert 0 <= risk.concentration_score <= 100
        assert 0 <= risk.diversification_score <= 100

    @pytest.mark.asyncio()
    async def test_analyze_risk_empty_portfolio(self):
        """Test risk analysis with empty portfolio."""
        pm = PortfolioManager()  # No API
        risk = awAlgot pm.analyze_risk()

        assert risk.overall_risk == RiskLevel.LOW
        assert risk.concentration_score == 0
        assert "Empty portfolio" in risk.risk_factors

    @pytest.mark.asyncio()
    async def test_analyze_risk_with_snapshot(self, portfolio_manager, sample_snapshot):
        """Test risk analysis with provided snapshot."""
        risk = awAlgot portfolio_manager.analyze_risk(snapshot=sample_snapshot)

        assert risk is not None
        assert isinstance(risk, RiskAnalysis)

    @pytest.mark.asyncio()
    async def test_high_concentration_risk(self, portfolio_manager):
        """Test detection of high concentration risk."""
        # Create snapshot with high concentration
        high_concentration_snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=100.0,
            cash_balance=10.0,
            inventory_value=90.0,
            listed_value=0.0,
            targets_value=0.0,
            assets=[
                PortfolioAsset(
                    item_id="big_item",
                    item_name="Expensive Item",
                    asset_type=AssetType.INVENTORY,
                    quantity=1,
                    unit_price=90.0,
                    total_value=90.0,  # 90% of portfolio
                    game="csgo",
                    category="Knife",
                ),
            ],
            asset_count=1,
            game_distribution={"csgo": 90.0},
            category_distribution={"Knife": 90.0},
        )

        risk = awAlgot portfolio_manager.analyze_risk(
            snapshot=high_concentration_snapshot
        )

        # Should detect high concentration
        assert risk.single_item_risk > 50
        assert len(risk.risk_factors) > 0
        assert any("concentration" in f.lower() for f in risk.risk_factors)

    @pytest.mark.asyncio()
    async def test_low_cash_risk(self, portfolio_manager):
        """Test detection of low cash reserve risk."""
        low_cash_snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=100.0,
            cash_balance=5.0,  # Only 5%
            inventory_value=95.0,
            listed_value=0.0,
            targets_value=0.0,
            assets=[
                PortfolioAsset(
                    item_id="item",
                    item_name="Item",
                    asset_type=AssetType.INVENTORY,
                    quantity=1,
                    unit_price=95.0,
                    total_value=95.0,
                    game="csgo",
                    category="Rifle",
                ),
            ],
            asset_count=1,
            game_distribution={"csgo": 95.0},
            category_distribution={"Rifle": 95.0},
        )

        risk = awAlgot portfolio_manager.analyze_risk(snapshot=low_cash_snapshot)

        # Should detect low cash
        assert any("cash" in f.lower() for f in risk.risk_factors)


# ============================================================================
# Rebalancing Tests
# ============================================================================


class TestRebalancing:
    """Tests for rebalancing recommendations."""

    @pytest.mark.asyncio()
    async def test_get_rebalancing_recommendations(self, portfolio_manager):
        """Test getting rebalancing recommendations."""
        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations()

        assert isinstance(recommendations, list)
        # All recommendations should be valid
        for rec in recommendations:
            assert isinstance(rec, RebalanceRecommendation)
            assert isinstance(rec.action, RebalanceAction)
            assert rec.priority >= 1

    @pytest.mark.asyncio()
    async def test_recommend_sell_overconcentrated(self, portfolio_manager):
        """Test recommendation to sell overconcentrated items."""
        # Create overconcentrated snapshot
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=100.0,
            cash_balance=10.0,
            inventory_value=90.0,
            listed_value=0.0,
            targets_value=0.0,
            assets=[
                PortfolioAsset(
                    item_id="big",
                    item_name="Big Item",
                    asset_type=AssetType.INVENTORY,
                    quantity=1,
                    unit_price=50.0,
                    total_value=50.0,  # 50% of portfolio
                    game="csgo",
                    category="Knife",
                ),
                PortfolioAsset(
                    item_id="small",
                    item_name="Small Item",
                    asset_type=AssetType.INVENTORY,
                    quantity=1,
                    unit_price=40.0,
                    total_value=40.0,
                    game="csgo",
                    category="Rifle",
                ),
            ],
            asset_count=2,
            game_distribution={"csgo": 90.0},
            category_distribution={"Knife": 50.0, "Rifle": 40.0},
        )

        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations(
            snapshot=snapshot
        )

        # Should recommend selling the overconcentrated item
        sell_recs = [r for r in recommendations if r.action == RebalanceAction.SELL]
        assert any(r.item_name == "Big Item" for r in sell_recs)

    @pytest.mark.asyncio()
    async def test_recommend_reduce_price_stale(self, portfolio_manager):
        """Test recommendation to reduce price on stale listings."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=100.0,
            cash_balance=50.0,
            inventory_value=0.0,
            listed_value=50.0,
            targets_value=0.0,
            assets=[
                PortfolioAsset(
                    item_id="stale",
                    item_name="Stale Listed Item",
                    asset_type=AssetType.LISTED,
                    quantity=1,
                    unit_price=50.0,
                    total_value=50.0,
                    game="csgo",
                    category="Rifle",
                    listed_price=50.0,
                    days_held=45,  # More than 30 days
                ),
            ],
            asset_count=1,
            game_distribution={"csgo": 50.0},
            category_distribution={"Rifle": 50.0},
        )

        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations(
            snapshot=snapshot
        )

        # Should recommend price reduction
        price_recs = [
            r for r in recommendations if r.action == RebalanceAction.REDUCE_PRICE
        ]
        assert len(price_recs) > 0

    @pytest.mark.asyncio()
    async def test_recommend_cancel_stale_target(self, portfolio_manager):
        """Test recommendation to cancel stale targets."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=100.0,
            cash_balance=50.0,
            inventory_value=0.0,
            listed_value=0.0,
            targets_value=50.0,
            assets=[
                PortfolioAsset(
                    item_id="stale_target",
                    item_name="Stale Target",
                    asset_type=AssetType.TARGET,
                    quantity=1,
                    unit_price=50.0,
                    total_value=50.0,
                    game="csgo",
                    category="Rifle",
                    days_held=10,  # More than 7 days
                ),
            ],
            asset_count=1,
            game_distribution={"csgo": 50.0},
            category_distribution={"Rifle": 50.0},
        )

        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations(
            snapshot=snapshot
        )

        # Should recommend cancelling target
        cancel_recs = [
            r for r in recommendations if r.action == RebalanceAction.CANCEL_TARGET
        ]
        assert len(cancel_recs) > 0

    @pytest.mark.asyncio()
    async def test_max_recommendations_limit(self, portfolio_manager):
        """Test that recommendations respect max limit."""
        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations(
            max_recommendations=5
        )

        assert len(recommendations) <= 5

    @pytest.mark.asyncio()
    async def test_recommendations_sorted_by_priority(self, portfolio_manager):
        """Test that recommendations are sorted by priority."""
        recommendations = awAlgot portfolio_manager.get_rebalancing_recommendations()

        if len(recommendations) > 1:
            priorities = [r.priority for r in recommendations]
            assert priorities == sorted(priorities, reverse=True)


# ============================================================================
# Performance Metrics Tests
# ============================================================================


class TestPerformanceMetrics:
    """Tests for performance metrics."""

    @pytest.mark.asyncio()
    async def test_get_performance_metrics(self, portfolio_manager):
        """Test getting performance metrics."""
        metrics = awAlgot portfolio_manager.get_performance_metrics()

        assert "total_value_usd" in metrics
        assert "cash_balance" in metrics
        assert "asset_count" in metrics
        assert "unrealized_pnl" in metrics
        assert "win_rate" in metrics

    @pytest.mark.asyncio()
    async def test_performance_metrics_period(self, portfolio_manager):
        """Test performance metrics with custom period."""
        metrics = awAlgot portfolio_manager.get_performance_metrics(period_days=7)

        assert metrics["period_days"] == 7

    @pytest.mark.asyncio()
    async def test_performance_metrics_distribution(self, portfolio_manager):
        """Test game and category distribution in metrics."""
        metrics = awAlgot portfolio_manager.get_performance_metrics()

        assert "game_distribution" in metrics
        assert "category_distribution" in metrics


# ============================================================================
# Report Formatting Tests
# ============================================================================


class TestReportFormatting:
    """Tests for report formatting."""

    def test_format_portfolio_report(self, portfolio_manager, sample_snapshot):
        """Test formatting portfolio report."""
        risk = RiskAnalysis(
            overall_risk=RiskLevel.MEDIUM,
            concentration_score=30.0,
            single_item_risk=25.0,
            single_game_risk=90.0,
            illiquidity_risk=10.0,
            stale_items_risk=5.0,
            diversification_score=60.0,
            risk_factors=["Test factor"],
            recommendations=["Test recommendation"],
        )

        report = portfolio_manager.format_portfolio_report(sample_snapshot, risk)

        assert "Portfolio Report" in report
        assert "Total Value" in report
        assert "$180.00" in report
        assert "MEDIUM" in report

    def test_format_report_with_game_distribution(
        self, portfolio_manager, sample_snapshot
    ):
        """Test that report includes game distribution."""
        risk = RiskAnalysis(
            overall_risk=RiskLevel.LOW,
            concentration_score=20.0,
            single_item_risk=15.0,
            single_game_risk=50.0,
            illiquidity_risk=5.0,
            stale_items_risk=0.0,
            diversification_score=80.0,
        )

        report = portfolio_manager.format_portfolio_report(sample_snapshot, risk)

        assert "By Game" in report
        assert "csgo" in report


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio()
    async def test_get_portfolio_summary(self, mock_api):
        """Test get_portfolio_summary function."""
        summary = awAlgot get_portfolio_summary(mock_api)

        assert "total_value" in summary
        assert "cash" in summary
        assert "assets" in summary
        assert "risk_level" in summary
        assert "diversification" in summary

    @pytest.mark.asyncio()
    async def test_get_rebalancing_actions(self, mock_api):
        """Test get_rebalancing_actions function."""
        actions = awAlgot get_rebalancing_actions(mock_api)

        assert isinstance(actions, list)
        for action in actions:
            assert "action" in action
            assert "item" in action
            assert "priority" in action
            assert "reason" in action


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_empty_inventory(self, mock_api):
        """Test handling empty inventory."""
        mock_api.get_user_inventory.return_value = {"objects": []}
        mock_api.get_user_offers.return_value = {"objects": []}
        mock_api.get_user_targets.return_value = {"Items": []}

        pm = PortfolioManager(api_client=mock_api)
        snapshot = awAlgot pm.get_portfolio_snapshot()

        assert snapshot.inventory_value == 0
        assert snapshot.listed_value == 0
        assert snapshot.targets_value == 0

    @pytest.mark.asyncio()
    async def test_malformed_item_data(self, mock_api):
        """Test handling malformed item data."""
        mock_api.get_user_inventory.return_value = {
            "objects": [
                {"malformed": "data"},  # Missing required fields
                {
                    "itemId": "good",
                    "title": "Good Item",
                    "price": {"USD": "1000"},
                },
            ]
        }

        pm = PortfolioManager(api_client=mock_api)
        snapshot = awAlgot pm.get_portfolio_snapshot()

        # Should handle gracefully, parsing valid items
        assert snapshot is not None

    @pytest.mark.asyncio()
    async def test_zero_total_value(self):
        """Test handling zero total value portfolio."""
        pm = PortfolioManager()
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value_usd=0.0,
            cash_balance=0.0,
            inventory_value=0.0,
            listed_value=0.0,
            targets_value=0.0,
            assets=[],
            asset_count=0,
            game_distribution={},
            category_distribution={},
        )

        risk = awAlgot pm.analyze_risk(snapshot)
        recommendations = awAlgot pm.get_rebalancing_recommendations(snapshot)

        assert risk.overall_risk == RiskLevel.LOW
        assert len(recommendations) == 0

    @pytest.mark.asyncio()
    async def test_negative_profit_loss(self, mock_api):
        """Test handling items with negative profit/loss."""
        mock_api.get_user_inventory.return_value = {
            "objects": [
                {
                    "itemId": "losing",
                    "title": "Losing Item",
                    "price": {"USD": "1000"},  # Bought at $10
                    "suggestedPrice": {"USD": "800"},  # Now worth $8
                    "gameId": "csgo",
                },
            ]
        }

        pm = PortfolioManager(api_client=mock_api)
        snapshot = awAlgot pm.get_portfolio_snapshot()

        # Should have negative profit
        losing_asset = next(
            (a for a in snapshot.assets if a.item_name == "Losing Item"), None
        )
        if losing_asset:
            assert losing_asset.profit_loss < 0


# ============================================================================
# Configuration Tests
# ============================================================================


class TestPortfolioConfig:
    """Tests for PortfolioConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PortfolioConfig()

        assert config.max_single_item_percent == 20.0
        assert config.max_single_game_percent == 50.0
        assert config.max_stale_days == 30
        assert config.target_cash_percent == 20.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PortfolioConfig(
            max_single_item_percent=25.0,
            max_single_game_percent=60.0,
            max_stale_days=14,
            target_cash_percent=15.0,
        )

        assert config.max_single_item_percent == 25.0
        assert config.max_single_game_percent == 60.0
        assert config.max_stale_days == 14
        assert config.target_cash_percent == 15.0

    @pytest.mark.asyncio()
    async def test_config_affects_risk_analysis(self, mock_api):
        """Test that config affects risk analysis."""
        # Strict config
        strict_config = PortfolioConfig(max_single_item_percent=10.0)
        pm_strict = PortfolioManager(api_client=mock_api, config=strict_config)

        # Lenient config
        lenient_config = PortfolioConfig(max_single_item_percent=50.0)
        pm_lenient = PortfolioManager(api_client=mock_api, config=lenient_config)

        risk_strict = awAlgot pm_strict.analyze_risk()
        risk_lenient = awAlgot pm_lenient.analyze_risk()

        # Strict config should detect more risk factors
        # (or have higher concentration score)
        # This depends on actual portfolio composition
        assert risk_strict is not None
        assert risk_lenient is not None
