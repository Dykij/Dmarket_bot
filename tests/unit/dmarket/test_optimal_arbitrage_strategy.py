"""Tests for Optimal Arbitrage Strategy."""


import pytest

from src.dmarket.optimal_arbitrage_strategy import (
    ArbitrageOpportunity,
    MarketFees,
    OptimalArbitrageStrategy,
    RiskLevel,
    StrategySettings,
    TradeLockStrategy,
    create_strategy,
)


class TestMarketFees:
    """Tests for MarketFees dataclass."""

    def test_default_fees(self):
        """Test default market fees."""
        fees = MarketFees()
        assert fees.dmarket == 0.05
        assert fees.waxpeer == 0.06
        assert fees.steam == 0.15

    def test_custom_fees(self):
        """Test custom market fees."""
        fees = MarketFees(dmarket=0.04, waxpeer=0.05)
        assert fees.dmarket == 0.04
        assert fees.waxpeer == 0.05


class TestStrategySettings:
    """Tests for StrategySettings dataclass."""

    def test_default_settings(self):
        """Test default strategy settings."""
        settings = StrategySettings()
        assert settings.min_roi_percent == 10.0
        assert settings.target_roi_percent == 15.0
        assert settings.min_price == 1.0
        assert settings.max_price == 500.0
        assert settings.min_liquidity_score == 0.3
        assert settings.max_risk_level == RiskLevel.MEDIUM
        assert "csgo" in settings.enabled_games
        assert "dota2" in settings.enabled_games

    def test_custom_settings(self):
        """Test custom strategy settings."""
        settings = StrategySettings(
            min_roi_percent=20.0,
            max_price=1000.0,
            lock_strategy=TradeLockStrategy.INSTANT_ONLY,
        )
        assert settings.min_roi_percent == 20.0
        assert settings.max_price == 1000.0
        assert settings.lock_strategy == TradeLockStrategy.INSTANT_ONLY


class TestArbitrageOpportunity:
    """Tests for ArbitrageOpportunity dataclass."""

    def test_opportunity_creation(self):
        """Test creating an arbitrage opportunity."""
        opp = ArbitrageOpportunity(
            item_id="test123",
            item_name="AK-47 | Redline",
            game="csgo",
            buy_price=10.0,
            sell_price=12.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=2.0,
            net_profit=1.28,
            roi_percent=12.8,
            fees_pAlgod=0.72,
        )
        assert opp.item_id == "test123"
        assert opp.buy_price == 10.0
        assert opp.net_profit == 1.28

    def test_opportunity_with_float(self):
        """Test opportunity with float value."""
        opp = ArbitrageOpportunity(
            item_id="test123",
            item_name="AK-47 | Redline (FT)",
            game="csgo",
            buy_price=10.0,
            sell_price=12.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=2.0,
            net_profit=1.28,
            roi_percent=12.8,
            fees_pAlgod=0.72,
            float_value=0.15,
        )
        assert opp.float_value == 0.15

    def test_opportunity_with_trade_lock(self):
        """Test opportunity with trade lock."""
        opp = ArbitrageOpportunity(
            item_id="test123",
            item_name="Test Item",
            game="csgo",
            buy_price=10.0,
            sell_price=12.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=2.0,
            net_profit=1.28,
            roi_percent=12.8,
            fees_pAlgod=0.72,
            has_trade_lock=True,
            lock_days=7,
        )
        assert opp.has_trade_lock is True
        assert opp.lock_days == 7


class TestOptimalArbitrageStrategy:  # noqa: PLR0904
    """Tests for OptimalArbitrageStrategy class."""

    @pytest.fixture()
    def strategy(self):
        """Create a test strategy."""
        return OptimalArbitrageStrategy()

    @pytest.fixture()
    def conservative_strategy(self):
        """Create a conservative strategy."""
        return create_strategy("conservative")

    def test_strategy_initialization(self, strategy):
        """Test strategy initializes correctly."""
        assert strategy.settings is not None
        assert strategy.fees is not None
        assert strategy.stats["total_scans"] == 0
        assert strategy.dAlgoly_trades == 0

    def test_calculate_net_profit(self, strategy):
        """Test net profit calculation."""
        gross, net, fees = strategy.calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
        )
        assert gross == 20.0
        # Waxpeer fee is 6%: 120 * 0.06 = 7.2
        assert fees == pytest.approx(7.2, 0.01)
        # Net = 20 - 7.2 = 12.8
        assert net == pytest.approx(12.8, 0.01)

    def test_calculate_roi(self, strategy):
        """Test ROI calculation."""
        roi = strategy.calculate_roi(buy_price=100.0, net_profit=15.0)
        assert roi == 15.0

    def test_calculate_roi_zero_price(self, strategy):
        """Test ROI with zero buy price."""
        roi = strategy.calculate_roi(buy_price=0, net_profit=10.0)
        assert roi == 0.0

    def test_assess_risk_level_very_low(self, strategy):
        """Test very low risk assessment."""
        risk = strategy.assess_risk_level(
            roi_percent=25.0,
            liquidity_score=0.8,
            sales_per_day=3.0,
        )
        assert risk == RiskLevel.VERY_LOW

    def test_assess_risk_level_low(self, strategy):
        """Test low risk assessment."""
        risk = strategy.assess_risk_level(
            roi_percent=16.0,
            liquidity_score=0.6,
            sales_per_day=1.5,
        )
        assert risk == RiskLevel.LOW

    def test_assess_risk_level_medium(self, strategy):
        """Test medium risk assessment."""
        risk = strategy.assess_risk_level(
            roi_percent=12.0,
            liquidity_score=0.4,
            sales_per_day=0.8,
        )
        assert risk == RiskLevel.MEDIUM

    def test_assess_risk_level_high(self, strategy):
        """Test high risk assessment."""
        risk = strategy.assess_risk_level(
            roi_percent=7.0,
            liquidity_score=0.2,
            sales_per_day=0.2,
        )
        assert risk == RiskLevel.HIGH

    def test_assess_risk_level_very_high(self, strategy):
        """Test very high risk assessment."""
        risk = strategy.assess_risk_level(
            roi_percent=3.0,
            liquidity_score=0.1,
            sales_per_day=0.1,
        )
        assert risk == RiskLevel.VERY_HIGH

    def test_calculate_opportunity_score(self, strategy):
        """Test opportunity score calculation."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=100.0,
            sell_price=120.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=20.0,
            net_profit=12.8,
            roi_percent=12.8,
            fees_pAlgod=7.2,
            liquidity_score=0.6,
            risk_level=RiskLevel.MEDIUM,
        )
        score = strategy.calculate_opportunity_score(opp)
        assert 0 <= score <= 100
        assert score > 0  # Should have some score

    def test_calculate_opportunity_score_with_float_bonus(self, strategy):
        """Test score with float value bonus."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=100.0,
            sell_price=120.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=20.0,
            net_profit=12.8,
            roi_percent=12.8,
            fees_pAlgod=7.2,
            liquidity_score=0.6,
            risk_level=RiskLevel.MEDIUM,
            float_value=0.01,  # Very low float
        )
        score_with_float = strategy.calculate_opportunity_score(opp)

        opp.float_value = 0.3  # High float
        score_without_float = strategy.calculate_opportunity_score(opp)

        assert score_with_float > score_without_float  # Float bonus applied

    def test_filter_opportunity_valid(self, strategy):
        """Test filtering a valid opportunity."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=50.0,
            sell_price=60.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=10.0,
            net_profit=6.4,
            roi_percent=12.8,
            fees_pAlgod=3.6,
            liquidity_score=0.5,
            sales_per_day=1.0,
            days_to_sell=7.0,
            risk_level=RiskLevel.MEDIUM,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is True
        assert not reason

    def test_filter_opportunity_low_roi(self, strategy):
        """Test filtering opportunity with low ROI."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=100.0,
            sell_price=105.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=5.0,
            net_profit=2.0,
            roi_percent=2.0,  # Below min 10%
            fees_pAlgod=3.0,
            liquidity_score=0.5,
            risk_level=RiskLevel.HIGH,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "ROI" in reason

    def test_filter_opportunity_high_roi_scam_protection(self, strategy):
        """Test filtering opportunity with suspiciously high ROI."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=10.0,
            sell_price=20.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=10.0,
            net_profit=9.0,
            roi_percent=90.0,  # Above max 50% - possible scam
            fees_pAlgod=1.0,
            liquidity_score=0.5,
            risk_level=RiskLevel.LOW,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "scam" in reason.lower()

    def test_filter_opportunity_low_liquidity(self, strategy):
        """Test filtering opportunity with low liquidity."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=50.0,
            sell_price=60.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=10.0,
            net_profit=6.4,
            roi_percent=12.8,
            fees_pAlgod=3.6,
            liquidity_score=0.1,  # Below min 0.3
            sales_per_day=0.1,
            risk_level=RiskLevel.HIGH,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "Liquidity" in reason

    def test_filter_opportunity_trade_lock(self, conservative_strategy):
        """Test filtering opportunity with trade lock in conservative mode."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=50.0,
            sell_price=60.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=10.0,
            net_profit=6.4,
            roi_percent=15.0,
            fees_pAlgod=3.6,
            liquidity_score=0.6,
            sales_per_day=2.0,
            risk_level=RiskLevel.LOW,
            has_trade_lock=True,  # Has lock
            lock_days=7,
        )
        is_valid, reason = conservative_strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "lock" in reason.lower()

    def test_find_best_opportunities(self, strategy):
        """Test finding best opportunities."""
        opportunities = []
        for i in range(10):
            opp = ArbitrageOpportunity(
                item_id=f"test{i}",
                item_name=f"Item {i}",
                game="csgo",
                buy_price=50.0,
                sell_price=60.0 + i,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                gross_profit=10.0 + i,
                net_profit=6.0 + i * 0.5,
                roi_percent=12.0 + i,
                fees_pAlgod=4.0,
                liquidity_score=0.5,
                sales_per_day=1.0,
                days_to_sell=7.0,
                risk_level=RiskLevel.MEDIUM,
            )
            # Calculate score for each opportunity
            opp.opportunity_score = strategy.calculate_opportunity_score(opp)
            opportunities.append(opp)

        best = strategy.find_best_opportunities(opportunities, top_n=5)
        assert len(best) == 5
        # Should be sorted by score (higher score first)
        assert best[0].opportunity_score >= best[-1].opportunity_score

    def test_find_best_opportunities_diversification(self, strategy):
        """Test diversification in best opportunities."""
        # Create 10 opportunities with same name
        opportunities = [
            ArbitrageOpportunity(
                item_id=f"test{i}",
                item_name="Same Item",  # All same name
                game="csgo",
                buy_price=50.0,
                sell_price=60.0,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                gross_profit=10.0,
                net_profit=6.4,
                roi_percent=12.8,
                fees_pAlgod=3.6,
                liquidity_score=0.5,
                sales_per_day=1.0,
                days_to_sell=7.0,
                risk_level=RiskLevel.MEDIUM,
            )
            for i in range(10)
        ]

        best = strategy.find_best_opportunities(opportunities, top_n=10)
        # Should only get 3 due to diversification
        assert len(best) == 3

    def test_record_trade(self, strategy):
        """Test recording a trade."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Test Item",
            game="csgo",
            buy_price=50.0,
            sell_price=60.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=10.0,
            net_profit=6.4,
            roi_percent=12.8,
            fees_pAlgod=3.6,
        )

        strategy.record_trade(opp)

        assert strategy.dAlgoly_trades == 1
        assert strategy.dAlgoly_spend == 50.0
        assert strategy.stats["trades_executed"] == 1
        assert strategy.stats["total_profit"] == 6.4
        assert len(strategy.trade_history) == 1

    def test_reset_dAlgoly_limits(self, strategy):
        """Test resetting dAlgoly limits."""
        strategy.dAlgoly_trades = 50
        strategy.dAlgoly_spend = 500.0

        strategy.reset_dAlgoly_limits()

        assert strategy.dAlgoly_trades == 0
        assert strategy.dAlgoly_spend == 0.0

    def test_get_statistics(self, strategy):
        """Test getting statistics."""
        stats = strategy.get_statistics()
        assert "total_scans" in stats
        assert "opportunities_found" in stats
        assert "trades_executed" in stats
        assert "dAlgoly_trades" in stats
        assert "dAlgoly_spend" in stats

    def test_analyze_item_valid(self, strategy):
        """Test analyzing a valid item."""
        item = {
            "itemId": "test123",
            "title": "AK-47 | Redline",
            "gameId": "csgo",
            "price": {"USD": "5000"},  # $50 in cents
            "floatValue": 0.15,
            "extra": {"pAlgontSeed": 123},
            "salesHistory": [1, 2, 3, 4, 5],
        }
        sell_price = 60.0

        opp = strategy.analyze_item(item, "dmarket", "waxpeer", sell_price)

        assert opp is not None
        assert opp.item_id == "test123"
        assert opp.buy_price == 50.0
        assert opp.sell_price == 60.0
        assert opp.float_value == 0.15
        assert opp.roi_percent > 0

    def test_analyze_item_invalid_price(self, strategy):
        """Test analyzing item with invalid price."""
        item = {
            "itemId": "test123",
            "title": "Test Item",
            "price": {"USD": "0"},  # Zero price
        }
        opp = strategy.analyze_item(item, "dmarket", "waxpeer", 60.0)
        assert opp is None

    def test_analyze_item_no_profit(self, strategy):
        """Test analyzing item with no profit."""
        item = {
            "itemId": "test123",
            "title": "Test Item",
            "price": {"USD": "10000"},  # $100
        }
        # Sell price lower than buy = no profit
        opp = strategy.analyze_item(item, "dmarket", "waxpeer", 90.0)
        assert opp is None


class TestStrategyPresets:
    """Tests for strategy presets."""

    def test_create_conservative_strategy(self):
        """Test creating conservative strategy."""
        strategy = create_strategy("conservative")
        assert strategy.settings.min_roi_percent == 15.0
        assert strategy.settings.max_risk_level == RiskLevel.LOW
        assert strategy.settings.lock_strategy == TradeLockStrategy.INSTANT_ONLY

    def test_create_balanced_strategy(self):
        """Test creating balanced strategy."""
        strategy = create_strategy("balanced")
        assert strategy.settings.min_roi_percent == 10.0
        assert strategy.settings.max_risk_level == RiskLevel.MEDIUM

    def test_create_aggressive_strategy(self):
        """Test creating aggressive strategy."""
        strategy = create_strategy("aggressive")
        assert strategy.settings.min_roi_percent == 7.0
        assert strategy.settings.max_risk_level == RiskLevel.HIGH
        assert strategy.settings.max_lock_days == 7

    def test_create_high_value_strategy(self):
        """Test creating high value strategy."""
        strategy = create_strategy("high_value")
        assert strategy.settings.min_price == 50.0
        assert strategy.settings.max_price == 1000.0
        assert strategy.settings.float_premium_enabled is True

    def test_create_scalper_strategy(self):
        """Test creating scalper strategy."""
        strategy = create_strategy("scalper")
        assert strategy.settings.min_roi_percent == 5.0
        assert strategy.settings.max_price == 20.0
        assert strategy.settings.max_dAlgoly_trades == 200

    def test_create_unknown_preset_fallback(self):
        """Test creating strategy with unknown preset falls back to balanced."""
        strategy = create_strategy("unknown_preset")
        assert strategy.settings.min_roi_percent == 10.0  # Balanced default


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_levels_exist(self):
        """Test all risk levels exist."""
        assert RiskLevel.VERY_LOW.value == "very_low"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.VERY_HIGH.value == "very_high"


class TestTradeLockStrategy:
    """Tests for TradeLockStrategy enum."""

    def test_lock_strategies_exist(self):
        """Test all lock strategies exist."""
        assert TradeLockStrategy.INSTANT_ONLY.value == "instant_only"
        assert TradeLockStrategy.SHORT_LOCK.value == "short_lock"
        assert TradeLockStrategy.INVESTMENT.value == "investment"


class TestOpportunityScoreBonuses:
    """Tests for opportunity score bonus calculations."""

    def test_score_with_rare_doppler_phase(self):
        """Test score bonus for rare Doppler phases (Ruby, Sapphire, Black Pearl)."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test123",
            item_name="Karambit Doppler (FN)",
            game="csgo",
            buy_price=500.0,
            sell_price=600.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=100.0,
            net_profit=64.0,
            roi_percent=12.8,
            fees_pAlgod=36.0,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            phase="Ruby",  # Rare phase
        )
        score = strategy.calculate_opportunity_score(opp)
        # Should have bonus for Ruby phase
        assert score > 50

    def test_score_with_sapphire_phase(self):
        """Test score bonus for Sapphire phase."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test456",
            item_name="Bayonet Doppler (FN)",
            game="csgo",
            buy_price=400.0,
            sell_price=480.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=80.0,
            net_profit=51.2,
            roi_percent=12.8,
            fees_pAlgod=28.8,
            liquidity_score=0.7,
            risk_level=RiskLevel.LOW,
            phase="Sapphire",
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50

    def test_score_with_black_pearl_phase(self):
        """Test score bonus for Black Pearl phase."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test789",
            item_name="Flip Knife Doppler (FN)",
            game="csgo",
            buy_price=300.0,
            sell_price=360.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=60.0,
            net_profit=38.4,
            roi_percent=12.8,
            fees_pAlgod=21.6,
            liquidity_score=0.7,
            risk_level=RiskLevel.LOW,
            phase="Black Pearl",
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50

    def test_score_with_blue_gem_pattern_661(self):
        """Test score bonus for Blue Gem pattern #661."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test_bg_661",
            item_name="AK-47 | Case Hardened (FT)",
            game="csgo",
            buy_price=1000.0,
            sell_price=1200.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=200.0,
            net_profit=128.0,
            roi_percent=12.8,
            fees_pAlgod=72.0,
            liquidity_score=0.6,
            risk_level=RiskLevel.MEDIUM,
            pattern_id=661,  # Famous Blue Gem pattern
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50

    def test_score_with_blue_gem_pattern_670(self):
        """Test score bonus for Blue Gem pattern #670."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test_bg_670",
            item_name="AK-47 | Case Hardened (MW)",
            game="csgo",
            buy_price=1500.0,
            sell_price=1800.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=300.0,
            net_profit=192.0,
            roi_percent=12.8,
            fees_pAlgod=108.0,
            liquidity_score=0.8,  # Higher liquidity for better score
            risk_level=RiskLevel.LOW,  # Lower risk for better score
            pattern_id=670,
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50

    def test_score_with_blue_gem_pattern_321(self):
        """Test score bonus for Blue Gem pattern #321."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test_bg_321",
            item_name="AK-47 | Case Hardened (FT)",
            game="csgo",
            buy_price=800.0,
            sell_price=960.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=160.0,
            net_profit=102.4,
            roi_percent=12.8,
            fees_pAlgod=57.6,
            liquidity_score=0.6,
            risk_level=RiskLevel.MEDIUM,
            pattern_id=321,
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50

    def test_score_with_blue_gem_pattern_387(self):
        """Test score bonus for Blue Gem pattern #387 (Karambit)."""
        strategy = OptimalArbitrageStrategy()
        opp = ArbitrageOpportunity(
            item_id="test_bg_387",
            item_name="Karambit | Case Hardened (FT)",
            game="csgo",
            buy_price=2000.0,
            sell_price=2400.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=400.0,
            net_profit=256.0,
            roi_percent=12.8,
            fees_pAlgod=144.0,
            liquidity_score=0.8,  # Higher liquidity for better score
            risk_level=RiskLevel.LOW,  # Lower risk for better score
            pattern_id=387,
        )
        score = strategy.calculate_opportunity_score(opp)
        assert score > 50


class TestFilterOpportunityEdgeCases:
    """Tests for edge cases in filter_opportunity."""

    @pytest.fixture()
    def strategy_with_limits(self):
        """Create strategy with specific limits for testing."""
        settings = StrategySettings(
            min_price=5.0,
            max_price=100.0,
            max_single_trade=50.0,
            min_sales_per_day=1.0,
            max_days_to_sell=14,
            max_lock_days=3,
        )
        return OptimalArbitrageStrategy(settings=settings)

    def test_filter_rejects_price_below_min(self, strategy_with_limits):
        """Test filter rejects items below min price."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Cheap Item",
            game="csgo",
            buy_price=2.0,  # Below min_price of 5.0
            sell_price=3.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=1.0,
            net_profit=0.5,
            roi_percent=25.0,
            fees_pAlgod=0.5,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "min" in reason.lower()

    def test_filter_rejects_price_above_max(self, strategy_with_limits):
        """Test filter rejects items above max price."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Expensive Item",
            game="csgo",
            buy_price=150.0,  # Above max_price of 100.0
            sell_price=180.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=30.0,
            net_profit=19.2,
            roi_percent=12.8,
            fees_pAlgod=10.8,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "max" in reason.lower()

    def test_filter_rejects_exceeds_single_trade_max(self, strategy_with_limits):
        """Test filter rejects items exceeding max_single_trade."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Big Trade Item",
            game="csgo",
            buy_price=75.0,  # Above max_single_trade of 50.0 but below max_price
            sell_price=90.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=15.0,
            net_profit=9.6,
            roi_percent=12.8,
            fees_pAlgod=5.4,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "single trade" in reason.lower()

    def test_filter_rejects_low_sales_per_day(self, strategy_with_limits):
        """Test filter rejects items with low sales per day."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Low Volume Item",
            game="csgo",
            buy_price=20.0,
            sell_price=24.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=4.0,
            net_profit=2.56,
            roi_percent=12.8,
            fees_pAlgod=1.44,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            sales_per_day=0.5,  # Below min_sales_per_day of 1.0
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "sales" in reason.lower()

    def test_filter_rejects_too_long_to_sell(self, strategy_with_limits):
        """Test filter rejects items that take too long to sell."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Slow Seller",
            game="csgo",
            buy_price=20.0,
            sell_price=24.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=4.0,
            net_profit=2.56,
            roi_percent=12.8,
            fees_pAlgod=1.44,
            liquidity_score=0.3,
            risk_level=RiskLevel.LOW,
            sales_per_day=2.0,
            days_to_sell=20,  # Above max_days_to_sell of 14
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "days" in reason.lower()

    def test_filter_rejects_too_long_lock(self, strategy_with_limits):
        """Test filter rejects items with lock exceeding max_lock_days."""
        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Long Lock Item",
            game="csgo",
            buy_price=20.0,
            sell_price=24.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=4.0,
            net_profit=2.56,
            roi_percent=12.8,
            fees_pAlgod=1.44,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
            has_trade_lock=True,
            lock_days=7,  # Above max_lock_days of 3
        )
        is_valid, reason = strategy_with_limits.filter_opportunity(opp)
        assert is_valid is False
        assert "lock" in reason.lower()


class TestAnalyzeItemEdgeCases:
    """Tests for edge cases in analyze_item."""

    def test_analyze_item_with_exception(self):
        """Test analyze_item handles exceptions gracefully."""
        strategy = OptimalArbitrageStrategy()
        # Item with missing required data that will cause exception
        item = {
            # Missing 'price' key which will rAlgose KeyError/TypeError
        }
        result = strategy.analyze_item(item, "dmarket", "waxpeer", 100.0)
        assert result is None

    def test_analyze_item_with_invalid_price_format(self):
        """Test analyze_item handles invalid price format."""
        strategy = OptimalArbitrageStrategy()
        item = {
            "itemId": "test",
            "title": "Test",
            "price": {"USD": "invalid"},  # Not a valid number
        }
        result = strategy.analyze_item(item, "dmarket", "waxpeer", 100.0)
        assert result is None

    def test_analyze_item_with_default_sales_per_day(self):
        """Test analyze_item uses default sales_per_day when no history."""
        strategy = OptimalArbitrageStrategy()
        item = {
            "itemId": "test",
            "title": "Test Item",
            "price": {"USD": "10000"},  # $100
            # No salesHistory
        }
        opp = strategy.analyze_item(item, "dmarket", "waxpeer", 120.0)
        assert opp is not None
        assert opp.sales_per_day == 0.5  # Default value


class TestDAlgolyLimitsFiltering:
    """Tests for dAlgoly limits in filter_opportunity."""

    def test_filter_rejects_when_dAlgoly_trades_exceeded(self):
        """Test filter rejects when dAlgoly trade limit exceeded."""
        settings = StrategySettings(max_dAlgoly_trades=10)
        strategy = OptimalArbitrageStrategy(settings=settings)
        # Simulate having reached dAlgoly trades limit
        strategy.dAlgoly_trades = 10

        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Good Item",
            game="csgo",
            buy_price=20.0,
            sell_price=24.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=4.0,
            net_profit=2.56,
            roi_percent=12.8,
            fees_pAlgod=1.44,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "dAlgoly trades limit" in reason.lower()

    def test_filter_rejects_when_dAlgoly_spend_exceeded(self):
        """Test filter rejects when dAlgoly spend limit would be exceeded."""
        settings = StrategySettings(max_dAlgoly_spend=100.0)
        strategy = OptimalArbitrageStrategy(settings=settings)
        # Simulate having spent most of dAlgoly budget
        strategy.dAlgoly_spend = 90.0

        opp = ArbitrageOpportunity(
            item_id="test",
            item_name="Expensive Item",
            game="csgo",
            buy_price=20.0,  # Would exceed 100.0 limit
            sell_price=24.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=4.0,
            net_profit=2.56,
            roi_percent=12.8,
            fees_pAlgod=1.44,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )
        is_valid, reason = strategy.filter_opportunity(opp)
        assert is_valid is False
        assert "dAlgoly spend limit" in reason.lower()


class TestFindBestOpportunitiesLogging:
    """Tests for find_best_opportunities with rejected items logging."""

    def test_find_best_opportunities_logs_rejected(self):
        """Test that rejected opportunities are logged."""
        settings = StrategySettings(min_roi_percent=15.0)
        strategy = OptimalArbitrageStrategy(settings=settings)

        opportunities = [
            ArbitrageOpportunity(
                item_id="rejected",
                item_name="Low ROI Item",
                game="csgo",
                buy_price=10.0,
                sell_price=11.0,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                gross_profit=1.0,
                net_profit=0.28,
                roi_percent=2.8,  # Below 15% min
                fees_pAlgod=0.72,
                liquidity_score=0.8,
                risk_level=RiskLevel.LOW,
                sales_per_day=5.0,
                opportunity_score=30,
            ),
        ]

        result = strategy.find_best_opportunities(opportunities)
        assert len(result) == 0  # All rejected


class TestRecordTradeAverageROI:
    """Tests for record_trade with average ROI calculation."""

    def test_record_trade_updates_average_roi(self):
        """Test that recording trades updates average ROI correctly."""
        strategy = OptimalArbitrageStrategy()

        opp1 = ArbitrageOpportunity(
            item_id="trade1",
            item_name="Item 1",
            game="csgo",
            buy_price=10.0,
            sell_price=12.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=2.0,
            net_profit=1.28,
            roi_percent=12.8,
            fees_pAlgod=0.72,
        )

        opp2 = ArbitrageOpportunity(
            item_id="trade2",
            item_name="Item 2",
            game="csgo",
            buy_price=20.0,
            sell_price=25.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=5.0,
            net_profit=3.5,
            roi_percent=17.5,
            fees_pAlgod=1.5,
        )

        strategy.record_trade(opp1)
        assert strategy.stats["trades_executed"] == 1
        assert strategy.stats["total_profit"] == 1.28

        strategy.record_trade(opp2)
        assert strategy.stats["trades_executed"] == 2
        assert strategy.stats["total_profit"] == 1.28 + 3.5

        # Average ROI should be calculated
        expected_avg_roi = (1.28 + 3.5) / (10.0 + 20.0) * 100
        assert abs(strategy.stats["average_roi"] - expected_avg_roi) < 0.1
