"""Tests for Unified Strategy System module.

Tests for the unified strategy system for finding items.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.unified_strategy_system import (
    GAME_EMOJIS,
    GAME_NAMES,
    SUPPORTED_GAMES,
    ActionType,
    OpportunityScore,
    OpportunityStatus,
    RiskLevel,
    StrategyConfig,
    StrategyType,
    UnifiedOpportunity,
    UnifiedStrategyManager,
    get_game_specific_config,
    get_strategy_config_preset,
)


class TestStrategyType:
    """Tests for StrategyType enum."""

    def test_cross_platform_arbitrage(self):
        """Test cross platform arbitrage value."""
        assert StrategyType.CROSS_PLATFORM_ARBITRAGE == "cross_platform"

    def test_intramarket_arbitrage(self):
        """Test intramarket arbitrage value."""
        assert StrategyType.INTRAMARKET_ARBITRAGE == "intramarket"

    def test_float_value_arbitrage(self):
        """Test float value arbitrage value."""
        assert StrategyType.FLOAT_VALUE_ARBITRAGE == "float_value"

    def test_pattern_phase_arbitrage(self):
        """Test pattern phase arbitrage value."""
        assert StrategyType.PATTERN_PHASE_ARBITRAGE == "pattern_phase"

    def test_target_system(self):
        """Test target system value."""
        assert StrategyType.TARGET_SYSTEM == "target_system"

    def test_smart_market_finder(self):
        """Test smart market finder value."""
        assert StrategyType.SMART_MARKET_FINDER == "smart_market"

    def test_enhanced_scanner(self):
        """Test enhanced scanner value."""
        assert StrategyType.ENHANCED_SCANNER == "enhanced_scanner"

    def test_trending_items(self):
        """Test trending items value."""
        assert StrategyType.TRENDING_ITEMS == "trending_items"

    def test_quick_flip(self):
        """Test quick flip value."""
        assert StrategyType.QUICK_FLIP == "quick_flip"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_very_low(self):
        """Test very low risk level."""
        assert RiskLevel.VERY_LOW == "very_low"

    def test_low(self):
        """Test low risk level."""
        assert RiskLevel.LOW == "low"

    def test_medium(self):
        """Test medium risk level."""
        assert RiskLevel.MEDIUM == "medium"

    def test_high(self):
        """Test high risk level."""
        assert RiskLevel.HIGH == "high"

    def test_very_high(self):
        """Test very high risk level."""
        assert RiskLevel.VERY_HIGH == "very_high"


class TestOpportunityStatus:
    """Tests for OpportunityStatus enum."""

    def test_active(self):
        """Test active status."""
        assert OpportunityStatus.ACTIVE == "active"

    def test_expired(self):
        """Test expired status."""
        assert OpportunityStatus.EXPIRED == "expired"

    def test_purchased(self):
        """Test purchased status."""
        assert OpportunityStatus.PURCHASED == "purchased"

    def test_fAlgoled(self):
        """Test fAlgoled status."""
        assert OpportunityStatus.FAlgoLED == "fAlgoled"

    def test_pending(self):
        """Test pending status."""
        assert OpportunityStatus.PENDING == "pending"


class TestActionType:
    """Tests for ActionType enum."""

    def test_buy_now(self):
        """Test buy now action."""
        assert ActionType.BUY_NOW == "buy_now"

    def test_create_target(self):
        """Test create target action."""
        assert ActionType.CREATE_TARGET == "create_target"

    def test_watch(self):
        """Test watch action."""
        assert ActionType.WATCH == "watch"

    def test_create_advanced_order(self):
        """Test create advanced order action."""
        assert ActionType.CREATE_ADVANCED_ORDER == "create_advanced_order"

    def test_skip(self):
        """Test skip action."""
        assert ActionType.SKIP == "skip"


class TestOpportunityScore:
    """Tests for OpportunityScore dataclass."""

    def test_create_score(self):
        """Test creating opportunity score."""
        score = OpportunityScore(
            profit_score=80,
            liquidity_score=70,
            risk_score=30,
            confidence_score=75,
            time_score=60,
        )
        assert score.profit_score == 80
        assert score.liquidity_score == 70
        assert score.risk_score == 30
        assert score.confidence_score == 75
        assert score.time_score == 60

    def test_total_score_calculation(self):
        """Test total score calculation with weights."""
        score = OpportunityScore(
            profit_score=100,
            liquidity_score=100,
            risk_score=0,  # 100 - 0 = 100 after inversion
            confidence_score=100,
            time_score=100,
        )
        # All 100 should give total = 100
        assert score.total_score == pytest.approx(100, rel=0.01)

    def test_total_score_zero(self):
        """Test total score with all zeros."""
        score = OpportunityScore(
            profit_score=0,
            liquidity_score=0,
            risk_score=100,  # Will be 0 after inversion
            confidence_score=0,
            time_score=0,
        )
        assert score.total_score == pytest.approx(0, rel=0.01)

    def test_total_score_mixed(self):
        """Test total score with mixed values."""
        score = OpportunityScore(
            profit_score=80,  # 0.30 * 80 = 24
            liquidity_score=60,  # 0.25 * 60 = 15
            risk_score=40,  # 0.20 * (100-40) = 12
            confidence_score=70,  # 0.15 * 70 = 10.5
            time_score=50,  # 0.10 * 50 = 5
        )
        # Total should be around 66.5
        assert score.total_score == pytest.approx(66.5, rel=0.01)


class TestUnifiedOpportunity:
    """Tests for UnifiedOpportunity dataclass."""

    def test_create_opportunity(self):
        """Test creating unified opportunity."""
        score = OpportunityScore(
            profit_score=70,
            liquidity_score=60,
            risk_score=30,
            confidence_score=80,
            time_score=65,
        )
        opp = UnifiedOpportunity(
            id="item_123",
            title="AK-47 | Redline",
            game="csgo",
            strategy_type=StrategyType.INTRAMARKET_ARBITRAGE,
            action_type=ActionType.BUY_NOW,
            buy_price=Decimal("50.00"),
            sell_price=Decimal("60.00"),
            profit_usd=Decimal("10.00"),
            profit_percent=Decimal("20.0"),
            score=score,
            risk_level=RiskLevel.LOW,
        )
        assert opp.id == "item_123"
        assert opp.title == "AK-47 | Redline"
        assert opp.game == "csgo"
        assert opp.buy_price == Decimal("50.00")

    def test_opportunity_default_values(self):
        """Test opportunity default values."""
        score = OpportunityScore(
            profit_score=70,
            liquidity_score=60,
            risk_score=30,
            confidence_score=80,
            time_score=65,
        )
        opp = UnifiedOpportunity(
            id="test",
            title="Test",
            game="csgo",
            strategy_type=StrategyType.INTRAMARKET_ARBITRAGE,
            action_type=ActionType.BUY_NOW,
            buy_price=Decimal("10"),
            sell_price=Decimal("12"),
            profit_usd=Decimal("2"),
            profit_percent=Decimal("20"),
            score=score,
            risk_level=RiskLevel.LOW,
        )
        assert opp.status == OpportunityStatus.ACTIVE
        assert opp.trade_lock_days == 0
        assert opp.source_platform == "dmarket"
        assert opp.metadata == {}
        assert opp.notes == []

    def test_opportunity_to_dict(self):
        """Test opportunity to_dict method."""
        score = OpportunityScore(
            profit_score=70,
            liquidity_score=60,
            risk_score=30,
            confidence_score=80,
            time_score=65,
        )
        opp = UnifiedOpportunity(
            id="item_123",
            title="AK-47 | Redline",
            game="csgo",
            strategy_type=StrategyType.CROSS_PLATFORM_ARBITRAGE,
            action_type=ActionType.BUY_NOW,
            buy_price=Decimal("50.00"),
            sell_price=Decimal("60.00"),
            profit_usd=Decimal("10.00"),
            profit_percent=Decimal("20.0"),
            score=score,
            risk_level=RiskLevel.LOW,
            float_value=0.15,
            pattern_id=661,
        )
        d = opp.to_dict()
        assert d["id"] == "item_123"
        assert d["title"] == "AK-47 | Redline"
        assert d["game"] == "csgo"
        assert d["strategy_type"] == "cross_platform"
        assert d["action_type"] == "buy_now"
        assert d["buy_price"] == 50.00
        assert d["sell_price"] == 60.00
        assert d["float_value"] == 0.15
        assert d["pattern_id"] == 661

    def test_opportunity_with_metadata(self):
        """Test opportunity with metadata."""
        score = OpportunityScore(
            profit_score=70,
            liquidity_score=60,
            risk_score=30,
            confidence_score=80,
            time_score=65,
        )
        opp = UnifiedOpportunity(
            id="test",
            title="Test",
            game="csgo",
            strategy_type=StrategyType.FLOAT_VALUE_ARBITRAGE,
            action_type=ActionType.BUY_NOW,
            buy_price=Decimal("10"),
            sell_price=Decimal("15"),
            profit_usd=Decimal("5"),
            profit_percent=Decimal("50"),
            score=score,
            risk_level=RiskLevel.MEDIUM,
            metadata={"float_quality": "premium", "wear": "FN"},
            notes=["Premium float", "Very low wear"],
        )
        assert opp.metadata["float_quality"] == "premium"
        assert "Premium float" in opp.notes


class TestStrategyConfig:
    """Tests for StrategyConfig dataclass."""

    def test_create_default_config(self):
        """Test creating default config."""
        config = StrategyConfig()
        assert config.game == "csgo"
        assert config.min_price == Decimal("1.0")
        assert config.max_price == Decimal("100.0")
        assert config.min_profit_percent == Decimal("5.0")
        assert config.limit == 50

    def test_create_config_with_values(self):
        """Test creating config with custom values."""
        config = StrategyConfig(
            game="dota2",
            min_price=Decimal("5.0"),
            max_price=Decimal("50.0"),
            min_profit_percent=Decimal("10.0"),
            limit=30,
        )
        assert config.game == "dota2"
        assert config.min_price == Decimal("5.0")
        assert config.max_price == Decimal("50.0")
        assert config.limit == 30

    def test_config_with_float_filters(self):
        """Test config with float filters."""
        config = StrategyConfig(
            float_min=0.0,
            float_max=0.07,
        )
        assert config.float_min == 0.0
        assert config.float_max == 0.07

    def test_config_with_pattern_filters(self):
        """Test config with pattern filters."""
        config = StrategyConfig(
            pattern_ids=[661, 670, 321],
            phases=["Ruby", "Sapphire"],
        )
        assert 661 in config.pattern_ids
        assert "Ruby" in config.phases

    def test_config_to_dict(self):
        """Test config to_dict method."""
        config = StrategyConfig(
            game="tf2",
            min_price=Decimal("2.0"),
            max_price=Decimal("30.0"),
            max_risk_level=RiskLevel.MEDIUM,
        )
        d = config.to_dict()
        assert d["game"] == "tf2"
        assert d["min_price"] == 2.0
        assert d["max_price"] == 30.0
        assert d["max_risk_level"] == "medium"


class TestGetStrategyConfigPreset:
    """Tests for get_strategy_config_preset function."""

    def test_boost_preset(self):
        """Test boost preset."""
        config = get_strategy_config_preset("boost")
        assert config.min_price == Decimal("0.50")
        assert config.max_price == Decimal("3.00")
        assert config.max_trade_lock_days == 0
        assert config.limit == 100

    def test_standard_preset(self):
        """Test standard preset."""
        config = get_strategy_config_preset("standard")
        assert config.min_price == Decimal("3.00")
        assert config.max_price == Decimal("15.00")
        assert config.max_trade_lock_days == 3

    def test_medium_preset(self):
        """Test medium preset."""
        config = get_strategy_config_preset("medium")
        assert config.min_price == Decimal("15.00")
        assert config.max_price == Decimal("50.00")

    def test_advanced_preset(self):
        """Test advanced preset."""
        config = get_strategy_config_preset("advanced")
        assert config.min_price == Decimal("50.00")
        assert config.max_price == Decimal("200.00")

    def test_pro_preset(self):
        """Test pro preset."""
        config = get_strategy_config_preset("pro")
        assert config.min_price == Decimal("200.00")
        assert config.max_price == Decimal("10000.00")
        assert config.max_risk_level == RiskLevel.HIGH

    def test_float_premium_preset(self):
        """Test float premium preset."""
        config = get_strategy_config_preset("float_premium")
        assert config.float_min == 0.0
        assert config.float_max == 0.18
        assert config.min_profit_percent == Decimal("20.0")

    def test_instant_arb_preset(self):
        """Test instant arbitrage preset."""
        config = get_strategy_config_preset("instant_arb")
        assert config.max_trade_lock_days == 0
        assert config.min_dAlgoly_sales == 5

    def test_investment_preset(self):
        """Test investment preset."""
        config = get_strategy_config_preset("investment")
        assert config.min_profit_percent == Decimal("15.0")
        assert config.max_risk_level == RiskLevel.HIGH

    def test_unknown_preset_returns_default(self):
        """Test unknown preset returns default config."""
        config = get_strategy_config_preset("unknown_preset")
        default = StrategyConfig()
        assert config.game == default.game
        assert config.min_price == default.min_price


class TestGetGameSpecificConfig:
    """Tests for get_game_specific_config function."""

    def test_csgo_config(self):
        """Test CS:GO specific config."""
        config = get_game_specific_config("csgo", "standard")
        assert config.game == "csgo"
        assert config.min_profit_percent == Decimal("5.0")
        assert config.min_dAlgoly_sales == 3
        assert config.limit == 50

    def test_dota2_config(self):
        """Test Dota 2 specific config."""
        config = get_game_specific_config("dota2", "standard")
        assert config.game == "dota2"
        assert config.min_profit_percent == Decimal("7.0")
        assert config.min_dAlgoly_sales == 2
        assert config.limit == 30
        assert config.max_price <= Decimal("100.0")

    def test_tf2_config(self):
        """Test TF2 specific config."""
        config = get_game_specific_config("tf2", "standard")
        assert config.game == "tf2"
        assert config.min_profit_percent == Decimal("8.0")
        assert config.min_dAlgoly_sales == 1
        assert config.limit == 20
        assert config.max_price <= Decimal("50.0")

    def test_rust_config(self):
        """Test Rust specific config."""
        config = get_game_specific_config("rust", "standard")
        assert config.game == "rust"
        assert config.min_profit_percent == Decimal("6.0")
        assert config.min_dAlgoly_sales == 2
        assert config.limit == 30

    def test_unknown_game_uses_defaults(self):
        """Test unknown game uses default adjustments."""
        config = get_game_specific_config("unknown_game", "standard")
        assert config.game == "unknown_game"

    def test_game_config_with_boost_preset(self):
        """Test game config with boost preset."""
        config = get_game_specific_config("csgo", "boost")
        assert config.min_price == Decimal("0.50")
        assert config.max_price == Decimal("3.00")


class TestSupportedGamesConstants:
    """Tests for game-related constants."""

    def test_supported_games(self):
        """Test supported games list."""
        assert "csgo" in SUPPORTED_GAMES
        assert "dota2" in SUPPORTED_GAMES
        assert "tf2" in SUPPORTED_GAMES
        assert "rust" in SUPPORTED_GAMES
        assert len(SUPPORTED_GAMES) == 4

    def test_game_emojis(self):
        """Test game emojis exist."""
        assert GAME_EMOJIS["csgo"] == "🔫"
        assert GAME_EMOJIS["dota2"] == "⚔️"
        assert GAME_EMOJIS["tf2"] == "🎩"
        assert GAME_EMOJIS["rust"] == "🏚️"

    def test_game_names(self):
        """Test game display names."""
        assert GAME_NAMES["csgo"] == "CS:GO / CS2"
        assert GAME_NAMES["dota2"] == "Dota 2"
        assert GAME_NAMES["tf2"] == "Team Fortress 2"
        assert GAME_NAMES["rust"] == "Rust"


class TestUnifiedStrategyManager:
    """Tests for UnifiedStrategyManager class."""

    @pytest.fixture()
    def mock_dmarket_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.fixture()
    def mock_waxpeer_api(self):
        """Create mock Waxpeer API."""
        api = MagicMock()
        api.get_items = AsyncMock(return_value={"success": True, "items": []})
        return api

    @pytest.fixture()
    def strategy_manager(self, mock_dmarket_api, mock_waxpeer_api):
        """Create strategy manager instance."""
        return UnifiedStrategyManager(mock_dmarket_api, mock_waxpeer_api)

    def test_init(self, mock_dmarket_api, mock_waxpeer_api):
        """Test manager initialization."""
        manager = UnifiedStrategyManager(mock_dmarket_api, mock_waxpeer_api)
        assert manager.dmarket_api is mock_dmarket_api
        assert manager.waxpeer_api is mock_waxpeer_api

    def test_list_strategies(self, strategy_manager):
        """Test listing strategies."""
        strategies = strategy_manager.list_strategies()
        assert len(strategies) > 0
        assert all("type" in s for s in strategies)
        assert all("name" in s for s in strategies)
        assert all("description" in s for s in strategies)

    def test_get_strategy(self, strategy_manager):
        """Test getting strategy by type."""
        strategy = strategy_manager.get_strategy(StrategyType.CROSS_PLATFORM_ARBITRAGE)
        assert strategy is not None
        assert strategy.strategy_type == StrategyType.CROSS_PLATFORM_ARBITRAGE

    def test_get_strategy_not_found(self, strategy_manager):
        """Test getting non-existent strategy returns None."""
        # Force non-existent strategy type
        strategy_manager._strategies = {}
        strategy = strategy_manager.get_strategy(StrategyType.CROSS_PLATFORM_ARBITRAGE)
        assert strategy is None

    def test_get_float_value_strategy(self, strategy_manager):
        """Test getting float value strategy."""
        strategy = strategy_manager.get_strategy(StrategyType.FLOAT_VALUE_ARBITRAGE)
        assert strategy is not None
        assert strategy.strategy_type == StrategyType.FLOAT_VALUE_ARBITRAGE

    def test_get_intramarket_strategy(self, strategy_manager):
        """Test getting intramarket strategy."""
        strategy = strategy_manager.get_strategy(StrategyType.INTRAMARKET_ARBITRAGE)
        assert strategy is not None
        assert strategy.strategy_type == StrategyType.INTRAMARKET_ARBITRAGE

    def test_get_smart_market_strategy(self, strategy_manager):
        """Test getting smart market finder strategy."""
        strategy = strategy_manager.get_strategy(StrategyType.SMART_MARKET_FINDER)
        assert strategy is not None
        assert strategy.strategy_type == StrategyType.SMART_MARKET_FINDER

    def test_strategies_have_required_properties(self, strategy_manager):
        """Test all strategies have required properties."""
        for strategy_type, strategy in strategy_manager._strategies.items():
            assert hasattr(strategy, "strategy_type")
            assert hasattr(strategy, "name")
            assert hasattr(strategy, "description")
            assert strategy.name != ""
            assert strategy.description != ""

    def test_strategies_have_validate_config(self, strategy_manager):
        """Test all strategies have validate_config method."""
        config = StrategyConfig()
        for strategy in strategy_manager._strategies.values():
            # Should not rAlgose and should return bool
            result = strategy.validate_config(config)
            assert isinstance(result, bool)

    def test_strategies_have_default_config(self, strategy_manager):
        """Test all strategies have get_default_config method."""
        for strategy in strategy_manager._strategies.values():
            config = strategy.get_default_config()
            assert isinstance(config, StrategyConfig)


class TestPresetComparison:
    """Tests comparing different presets."""

    def test_boost_has_lowest_min_price(self):
        """Test boost preset has lowest min price."""
        boost = get_strategy_config_preset("boost")
        standard = get_strategy_config_preset("standard")
        assert boost.min_price < standard.min_price

    def test_pro_has_highest_prices(self):
        """Test pro preset has highest price range."""
        pro = get_strategy_config_preset("pro")
        advanced = get_strategy_config_preset("advanced")
        assert pro.min_price >= advanced.max_price

    def test_instant_arb_has_no_lock(self):
        """Test instant arbitrage has zero lock days."""
        instant = get_strategy_config_preset("instant_arb")
        investment = get_strategy_config_preset("investment")
        assert instant.max_trade_lock_days == 0
        assert investment.max_trade_lock_days > 0

    def test_float_premium_has_float_filters(self):
        """Test float premium has float filters set."""
        float_preset = get_strategy_config_preset("float_premium")
        standard = get_strategy_config_preset("standard")
        assert float_preset.float_min is not None
        assert float_preset.float_max is not None
        assert standard.float_min is None


class TestGameConfigComparison:
    """Tests comparing game-specific configs."""

    def test_csgo_has_most_items(self):
        """Test CS:GO config has highest limit."""
        csgo = get_game_specific_config("csgo", "standard")
        dota2 = get_game_specific_config("dota2", "standard")
        tf2 = get_game_specific_config("tf2", "standard")
        assert csgo.limit >= dota2.limit
        assert csgo.limit >= tf2.limit

    def test_csgo_has_lowest_profit_requirement(self):
        """Test CS:GO has lowest profit requirement."""
        csgo = get_game_specific_config("csgo", "standard")
        dota2 = get_game_specific_config("dota2", "standard")
        tf2 = get_game_specific_config("tf2", "standard")
        assert csgo.min_profit_percent <= dota2.min_profit_percent
        assert csgo.min_profit_percent <= tf2.min_profit_percent

    def test_tf2_has_lowest_dAlgoly_sales_requirement(self):
        """Test TF2 has lowest dAlgoly sales requirement."""
        tf2 = get_game_specific_config("tf2", "standard")
        csgo = get_game_specific_config("csgo", "standard")
        assert tf2.min_dAlgoly_sales <= csgo.min_dAlgoly_sales
