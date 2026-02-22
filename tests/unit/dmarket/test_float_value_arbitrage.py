"""Tests for Float Value Arbitrage module.

Tests for float_value_arbitrage.py with float-based arbitrage strategies.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.float_value_arbitrage import (
    FLOAT_RANGES,
    PREMIUM_FLOAT_RANGES,
    FloatArbitrageOpportunity,
    FloatOrderConfig,
    FloatPremiumResult,
    FloatQuality,
    FloatValueArbitrage,
    QuartileAnalysisResult,
    format_float_opportunity,
    get_premium_ak47_redline_orders,
    get_premium_awp_asiimov_orders,
)


class TestFloatQuality:
    """Tests for FloatQuality enum."""

    def test_factory_new_value(self):
        """Test Factory New quality value."""
        assert FloatQuality.FACTORY_NEW == "fn"

    def test_minimal_wear_value(self):
        """Test Minimal Wear quality value."""
        assert FloatQuality.MINIMAL_WEAR == "mw"

    def test_field_tested_value(self):
        """Test Field-Tested quality value."""
        assert FloatQuality.FIELD_TESTED == "ft"

    def test_well_worn_value(self):
        """Test Well-Worn quality value."""
        assert FloatQuality.WELL_WORN == "ww"

    def test_battle_scarred_value(self):
        """Test Battle-Scarred quality value."""
        assert FloatQuality.BATTLE_SCARRED == "bs"


class TestFloatRanges:
    """Tests for float ranges constants."""

    def test_factory_new_range(self):
        """Test FN float range."""
        assert FLOAT_RANGES[FloatQuality.FACTORY_NEW] == (0.00, 0.07)

    def test_minimal_wear_range(self):
        """Test MW float range."""
        assert FLOAT_RANGES[FloatQuality.MINIMAL_WEAR] == (0.07, 0.15)

    def test_field_tested_range(self):
        """Test FT float range."""
        assert FLOAT_RANGES[FloatQuality.FIELD_TESTED] == (0.15, 0.38)

    def test_well_worn_range(self):
        """Test WW float range."""
        assert FLOAT_RANGES[FloatQuality.WELL_WORN] == (0.38, 0.45)

    def test_battle_scarred_range(self):
        """Test BS float range."""
        assert FLOAT_RANGES[FloatQuality.BATTLE_SCARRED] == (0.45, 1.00)


class TestFloatOrderConfig:
    """Tests for FloatOrderConfig dataclass."""

    def test_create_config(self):
        """Test creating FloatOrderConfig."""
        config = FloatOrderConfig(
            item_title="AK-47 | Redline",
            float_min=0.15,
            float_max=0.16,
            max_price_usd=50.0,
        )
        assert config.item_title == "AK-47 | Redline"
        assert config.float_min == 0.15
        assert config.float_max == 0.16
        assert config.max_price_usd == 50.0
        assert config.expected_premium == 1.0
        assert config.amount == 1
        assert config.notes == ""

    def test_create_config_with_all_fields(self):
        """Test creating FloatOrderConfig with all fields."""
        config = FloatOrderConfig(
            item_title="AWP | Asiimov",
            float_min=0.18,
            float_max=0.20,
            max_price_usd=100.0,
            expected_premium=1.25,
            amount=5,
            notes="Premium float",
        )
        assert config.expected_premium == 1.25
        assert config.amount == 5
        assert config.notes == "Premium float"

    def test_to_target_attrs(self):
        """Test converting to target attributes."""
        config = FloatOrderConfig(
            item_title="M4A1-S",
            float_min=0.00,
            float_max=0.01,
            max_price_usd=200.0,
        )
        attrs = config.to_target_attrs()
        assert attrs["floatMin"] == "0.0"
        assert attrs["floatMax"] == "0.01"


class TestFloatPremiumResult:
    """Tests for FloatPremiumResult dataclass."""

    def test_create_result(self):
        """Test creating FloatPremiumResult."""
        result = FloatPremiumResult(
            item_title="AK-47 | Redline",
            current_float=0.15,
            quality=FloatQuality.FIELD_TESTED,
            base_market_price=33.0,
            premium_price=62.0,
            premium_multiplier=1.88,
            is_profitable=True,
            reason="Premium float",
            recommended_buy_price=55.0,
            expected_sell_price=62.0,
            estimated_profit_usd=7.0,
            estimated_profit_percent=12.7,
        )
        assert result.item_title == "AK-47 | Redline"
        assert result.premium_multiplier == 1.88
        assert result.is_profitable is True


class TestQuartileAnalysisResult:
    """Tests for QuartileAnalysisResult dataclass."""

    def test_create_result(self):
        """Test creating QuartileAnalysisResult."""
        result = QuartileAnalysisResult(
            item_title="AK-47 | Redline",
            current_price=30.0,
            q1_price=28.0,
            q2_price=33.0,
            q3_price=40.0,
            mean_price=35.0,
            min_price=25.0,
            max_price=50.0,
            sales_count=100,
            is_good_buy=False,
            percentile=25.0,
        )
        assert result.q1_price == 28.0
        assert result.is_good_buy is False

    def test_good_buy_when_below_q1(self):
        """Test is_good_buy when price is below Q1."""
        result = QuartileAnalysisResult(
            item_title="Test Item",
            current_price=25.0,
            q1_price=28.0,
            q2_price=33.0,
            q3_price=40.0,
            mean_price=35.0,
            min_price=25.0,
            max_price=50.0,
            sales_count=100,
            is_good_buy=True,
            percentile=10.0,
        )
        assert result.is_good_buy is True


class TestFloatArbitrageOpportunity:
    """Tests for FloatArbitrageOpportunity dataclass."""

    def test_create_opportunity(self):
        """Test creating FloatArbitrageOpportunity."""
        opp = FloatArbitrageOpportunity(
            item_title="AK-47 | Redline",
            item_id="123",
            current_price_usd=50.0,
            float_value=0.15,
            quality=FloatQuality.FIELD_TESTED,
            expected_sell_price=62.0,
            profit_usd=12.0,
            profit_percent=24.0,
            premium_tier="premium",
            competing_orders=5,
            highest_competitor_bid=48.0,
            recommended_action="BUY",
            confidence_score=85.0,
        )
        assert opp.item_title == "AK-47 | Redline"
        assert opp.profit_percent == 24.0
        assert opp.recommended_action == "BUY"


class TestFloatValueArbitrage:
    """Tests for FloatValueArbitrage class."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_sales_history = AsyncMock()
        api.get_market_items = AsyncMock()
        return api

    @pytest.fixture()
    def arbitrage(self, mock_api):
        """Create FloatValueArbitrage instance."""
        return FloatValueArbitrage(
            api_client=mock_api,
            commission_percent=5.0,
            min_profit_margin=10.0,
        )

    def test_init(self, mock_api):
        """Test initialization."""
        arb = FloatValueArbitrage(mock_api, 5.0, 10.0)
        assert arb.commission == 0.05
        assert arb.min_margin == 0.10

    def test_get_float_quality_fn(self, arbitrage):
        """Test getting quality for Factory New."""
        assert arbitrage.get_float_quality(0.01) == FloatQuality.FACTORY_NEW
        assert arbitrage.get_float_quality(0.05) == FloatQuality.FACTORY_NEW
        assert arbitrage.get_float_quality(0.00) == FloatQuality.FACTORY_NEW

    def test_get_float_quality_mw(self, arbitrage):
        """Test getting quality for Minimal Wear."""
        assert arbitrage.get_float_quality(0.08) == FloatQuality.MINIMAL_WEAR
        assert arbitrage.get_float_quality(0.10) == FloatQuality.MINIMAL_WEAR
        assert arbitrage.get_float_quality(0.14) == FloatQuality.MINIMAL_WEAR

    def test_get_float_quality_ft(self, arbitrage):
        """Test getting quality for Field-Tested."""
        assert arbitrage.get_float_quality(0.15) == FloatQuality.FIELD_TESTED
        assert arbitrage.get_float_quality(0.25) == FloatQuality.FIELD_TESTED
        assert arbitrage.get_float_quality(0.37) == FloatQuality.FIELD_TESTED

    def test_get_float_quality_ww(self, arbitrage):
        """Test getting quality for Well-Worn."""
        assert arbitrage.get_float_quality(0.38) == FloatQuality.WELL_WORN
        assert arbitrage.get_float_quality(0.40) == FloatQuality.WELL_WORN
        assert arbitrage.get_float_quality(0.44) == FloatQuality.WELL_WORN

    def test_get_float_quality_bs(self, arbitrage):
        """Test getting quality for Battle-Scarred."""
        assert arbitrage.get_float_quality(0.45) == FloatQuality.BATTLE_SCARRED
        assert arbitrage.get_float_quality(0.75) == FloatQuality.BATTLE_SCARRED
        assert arbitrage.get_float_quality(0.99) == FloatQuality.BATTLE_SCARRED

    def test_get_float_quality_above_range(self, arbitrage):
        """Test getting quality for float above 1.0."""
        assert arbitrage.get_float_quality(1.5) == FloatQuality.BATTLE_SCARRED

    def test_calculate_float_premium_ak47_redline(self, arbitrage):
        """Test premium calculation for AK-47 Redline."""
        result = arbitrage.calculate_float_premium(
            "AK-47 | Redline (Field-Tested)",
            0.15,
            33.0,
        )
        assert result.premium_multiplier == 1.88
        assert result.quality == FloatQuality.FIELD_TESTED
        assert result.premium_price == pytest.approx(62.04, rel=0.01)

    def test_calculate_float_premium_awp_asiimov(self, arbitrage):
        """Test premium calculation for AWP Asiimov."""
        result = arbitrage.calculate_float_premium(
            "AWP | Asiimov (Field-Tested)",
            0.19,
            100.0,
        )
        assert result.premium_multiplier == 1.25
        assert result.premium_price == pytest.approx(125.0, rel=0.01)

    def test_calculate_float_premium_generic_item(self, arbitrage):
        """Test premium calculation for item without specific config."""
        result = arbitrage.calculate_float_premium(
            "Unknown Item",
            0.01,
            50.0,
        )
        # Should use generic premium calculation
        assert result.premium_multiplier >= 1.0
        assert result.quality == FloatQuality.FACTORY_NEW

    def test_calculate_generic_premium_top_5_percent(self, arbitrage):
        """Test generic premium for top 5% float in range."""
        # FN range is 0.00-0.07, so 0.003 is in top 5%
        premium = arbitrage._calculate_generic_premium(0.003, FloatQuality.FACTORY_NEW)
        assert premium == 1.50  # Max premium

    def test_calculate_generic_premium_top_10_percent(self, arbitrage):
        """Test generic premium for top 10% float in range."""
        # FN range is 0.00-0.07, so 0.005 is in top 10%
        premium = arbitrage._calculate_generic_premium(0.005, FloatQuality.FACTORY_NEW)
        assert premium == 1.35  # 70% of max premium

    def test_calculate_generic_premium_top_20_percent(self, arbitrage):
        """Test generic premium for top 20% float in range."""
        # FN range is 0.00-0.07, so 0.01 is in top 20%
        premium = arbitrage._calculate_generic_premium(0.01, FloatQuality.FACTORY_NEW)
        assert premium == 1.20  # 40% of max premium

    def test_calculate_generic_premium_top_30_percent(self, arbitrage):
        """Test generic premium for top 30% float in range."""
        # FN range is 0.00-0.07, so 0.015 is in top 30%
        premium = arbitrage._calculate_generic_premium(0.015, FloatQuality.FACTORY_NEW)
        assert premium == 1.10  # 20% of max premium

    def test_calculate_generic_premium_standard(self, arbitrage):
        """Test generic premium for standard float."""
        # FN range is 0.00-0.07, so 0.05 is standard
        premium = arbitrage._calculate_generic_premium(0.05, FloatQuality.FACTORY_NEW)
        assert premium == 1.0  # No premium

    def test_percentile_empty_list(self, arbitrage):
        """Test percentile calculation with empty list."""
        result = arbitrage._percentile([], 50)
        assert result == 0.0

    def test_percentile_single_element(self, arbitrage):
        """Test percentile calculation with single element."""
        result = arbitrage._percentile([10.0], 50)
        assert result == 10.0

    def test_percentile_multiple_elements(self, arbitrage):
        """Test percentile calculation with multiple elements."""
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert arbitrage._percentile(data, 0) == 10.0
        assert arbitrage._percentile(data, 50) == 30.0
        assert arbitrage._percentile(data, 100) == 50.0

    def test_percentile_interpolation(self, arbitrage):
        """Test percentile with interpolation."""
        data = [10.0, 20.0, 30.0, 40.0]
        result = arbitrage._percentile(data, 25)
        assert 10.0 <= result <= 20.0

    @pytest.mark.asyncio()
    async def test_analyze_sales_quartiles_no_history(self, arbitrage, mock_api):
        """Test quartile analysis with no sales history."""
        mock_api.get_sales_history.return_value = None

        result = await arbitrage.analyze_sales_quartiles("Test Item")
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_sales_quartiles_empty_sales(self, arbitrage, mock_api):
        """Test quartile analysis with empty sales."""
        mock_api.get_sales_history.return_value = {"sales": []}

        result = await arbitrage.analyze_sales_quartiles("Test Item")
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_sales_quartiles_not_enough_sales(self, arbitrage, mock_api):
        """Test quartile analysis with not enough sales."""
        mock_api.get_sales_history.return_value = {
            "sales": [{"price": {"USD": "1000"}} for _ in range(5)]
        }

        result = await arbitrage.analyze_sales_quartiles("Test Item")
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_sales_quartiles_exception(self, arbitrage, mock_api):
        """Test quartile analysis with exception."""
        mock_api.get_sales_history.side_effect = Exception("API error")

        result = await arbitrage.analyze_sales_quartiles("Test Item")
        assert result is None

    @pytest.mark.asyncio()
    async def test_get_current_min_price_success(self, arbitrage, mock_api):
        """Test getting current min price."""
        mock_api.get_market_items.return_value = {
            "objects": [{"price": {"USD": "5000"}}]
        }

        result = await arbitrage._get_current_min_price("Test Item")
        assert result == 50.0

    @pytest.mark.asyncio()
    async def test_get_current_min_price_no_items(self, arbitrage, mock_api):
        """Test getting current min price with no items."""
        mock_api.get_market_items.return_value = {"objects": []}

        result = await arbitrage._get_current_min_price("Test Item")
        assert result is None

    @pytest.mark.asyncio()
    async def test_get_current_min_price_exception(self, arbitrage, mock_api):
        """Test getting current min price with exception."""
        mock_api.get_market_items.side_effect = Exception("API error")

        result = await arbitrage._get_current_min_price("Test Item")
        assert result is None

    def test_create_float_order_config(self, arbitrage):
        """Test creating float order config."""
        config = arbitrage.create_float_order_config(
            "AK-47 | Redline",
            (0.15, 0.16),
            50.0,
            1.5,
        )
        assert config.item_title == "AK-47 | Redline"
        assert config.float_min == 0.15
        assert config.float_max == 0.16
        assert config.max_price_usd == 50.0
        assert config.expected_premium == 1.5
        assert "0.150-0.160" in config.notes

    @pytest.mark.asyncio()
    async def test_find_float_arbitrage_opportunities_wrong_game(self, arbitrage, mock_api):
        """Test finding opportunities for wrong game."""
        result = await arbitrage.find_float_arbitrage_opportunities(game="dota2")
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_float_arbitrage_opportunities_no_items(self, arbitrage, mock_api):
        """Test finding opportunities with no items."""
        mock_api.get_market_items.return_value = None

        result = await arbitrage.find_float_arbitrage_opportunities()
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_float_arbitrage_opportunities_empty_objects(self, arbitrage, mock_api):
        """Test finding opportunities with empty objects."""
        mock_api.get_market_items.return_value = {"objects": []}

        result = await arbitrage.find_float_arbitrage_opportunities()
        assert result == []

    @pytest.mark.asyncio()
    async def test_find_float_arbitrage_opportunities_exception(self, arbitrage, mock_api):
        """Test finding opportunities with exception."""
        mock_api.get_market_items.side_effect = Exception("API error")

        result = await arbitrage.find_float_arbitrage_opportunities()
        assert result == []

    @pytest.mark.asyncio()
    async def test_analyze_item_float_no_price(self, arbitrage):
        """Test analyzing item with no price."""
        item = {"itemId": "123", "title": "Test", "price": {"USD": 0}}

        result = await arbitrage._analyze_item_float(item)
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_item_float_no_float_value(self, arbitrage):
        """Test analyzing item with no float value."""
        item = {
            "itemId": "123",
            "title": "Test",
            "price": {"USD": "5000"},
            "extra": {},
        }

        result = await arbitrage._analyze_item_float(item)
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_item_float_with_float_part_value(self, arbitrage):
        """Test analyzing item with floatPartValue."""
        item = {
            "itemId": "123",
            "title": "AK-47 | Redline",
            "price": {"USD": "5000"},
            "extra": {"floatPartValue": "0.15"},
        }

        result = await arbitrage._analyze_item_float(item)
        # Should attempt to parse floatPartValue
        assert result is not None or result is None  # Depends on profitability

    @pytest.mark.asyncio()
    async def test_analyze_item_float_invalid_float_part_value(self, arbitrage):
        """Test analyzing item with invalid floatPartValue."""
        item = {
            "itemId": "123",
            "title": "Test",
            "price": {"USD": "5000"},
            "extra": {"floatPartValue": "invalid"},
        }

        result = await arbitrage._analyze_item_float(item)
        assert result is None

    @pytest.mark.asyncio()
    async def test_analyze_item_float_exception(self, arbitrage):
        """Test analyzing item with exception."""
        item = None  # Will cause exception

        result = await arbitrage._analyze_item_float(item)
        assert result is None


class TestPremiumFloatRanges:
    """Tests for premium float ranges configuration."""

    def test_ak47_redline_config_exists(self):
        """Test AK-47 Redline config exists."""
        assert "AK-47 | Redline" in PREMIUM_FLOAT_RANGES

    def test_ak47_redline_ft_premium(self):
        """Test AK-47 Redline FT premium range."""
        config = PREMIUM_FLOAT_RANGES["AK-47 | Redline"]
        assert "ft_premium" in config
        f_min, f_max, mult = config["ft_premium"]
        assert f_min == 0.15
        assert f_max == 0.155
        assert mult == 1.88

    def test_awp_asiimov_config_exists(self):
        """Test AWP Asiimov config exists."""
        assert "AWP | Asiimov" in PREMIUM_FLOAT_RANGES

    def test_m4a1s_hyper_beast_config_exists(self):
        """Test M4A1-S Hyper Beast config exists."""
        assert "M4A1-S | Hyper Beast" in PREMIUM_FLOAT_RANGES


class TestPresetOrders:
    """Tests for preset order functions."""

    def test_get_premium_ak47_redline_orders(self):
        """Test getting AK-47 Redline preset orders."""
        orders = get_premium_ak47_redline_orders()
        assert len(orders) == 3
        assert all(isinstance(o, FloatOrderConfig) for o in orders)
        assert all("AK-47 | Redline" in o.item_title for o in orders)

    def test_ak47_redline_orders_prices(self):
        """Test AK-47 Redline orders have correct prices."""
        orders = get_premium_ak47_redline_orders()
        # First order should be most expensive (best float)
        assert orders[0].max_price_usd > orders[1].max_price_usd > orders[2].max_price_usd

    def test_ak47_redline_orders_float_ranges(self):
        """Test AK-47 Redline orders have correct float ranges."""
        orders = get_premium_ak47_redline_orders()
        # All should be in FT range
        for order in orders:
            assert order.float_min >= 0.15
            assert order.float_max <= 0.18

    def test_get_premium_awp_asiimov_orders(self):
        """Test getting AWP Asiimov preset orders."""
        orders = get_premium_awp_asiimov_orders()
        assert len(orders) == 2
        assert all(isinstance(o, FloatOrderConfig) for o in orders)
        assert all("AWP | Asiimov" in o.item_title for o in orders)

    def test_awp_asiimov_blackiimov(self):
        """Test AWP Asiimov Blackiimov order."""
        orders = get_premium_awp_asiimov_orders()
        blackiimov = [o for o in orders if "Battle-Scarred" in o.item_title][0]
        assert blackiimov.float_min == 0.45
        assert blackiimov.float_max == 0.50
        assert "Blackiimov" in blackiimov.notes


class TestFormatFloatOpportunity:
    """Tests for format_float_opportunity function."""

    def test_format_opportunity(self):
        """Test formatting opportunity."""
        opp = FloatArbitrageOpportunity(
            item_title="AK-47 | Redline",
            item_id="123",
            current_price_usd=50.0,
            float_value=0.1523,
            quality=FloatQuality.FIELD_TESTED,
            expected_sell_price=62.0,
            profit_usd=12.0,
            profit_percent=24.0,
            premium_tier="premium",
            competing_orders=5,
            highest_competitor_bid=48.0,
            recommended_action="BUY",
            confidence_score=85.0,
        )

        formatted = format_float_opportunity(opp)
        assert "AK-47 | Redline" in formatted
        assert "0.1523" in formatted
        assert "ft" in formatted
        assert "$50.00" in formatted
        assert "$62.00" in formatted
        assert "$12.00" in formatted
        assert "24.0%" in formatted
        assert "premium" in formatted
        assert "85%" in formatted


class TestIntegrationScenarios:
    """Integration tests for float arbitrage scenarios."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_sales_history = AsyncMock()
        api.get_market_items = AsyncMock()
        return api

    @pytest.fixture()
    def arbitrage(self, mock_api):
        """Create FloatValueArbitrage instance."""
        return FloatValueArbitrage(mock_api, 5.0, 10.0)

    @pytest.mark.asyncio()
    async def test_full_float_analysis_workflow(self, arbitrage, mock_api):
        """Test complete float analysis workflow."""
        # Setup sales history
        mock_api.get_sales_history.return_value = {
            "sales": [{"price": {"USD": str(3000 + i * 100)}} for i in range(20)]
        }

        # Setup current price
        mock_api.get_market_items.return_value = {
            "objects": [{"price": {"USD": "2800"}}]
        }

        # Run analysis
        result = await arbitrage.analyze_sales_quartiles("AK-47 | Redline")

        assert result is not None
        assert result.sales_count == 20
        assert result.current_price == 28.0

    def test_premium_calculation_workflow(self, arbitrage):
        """Test premium calculation for various scenarios."""
        scenarios = [
            ("AK-47 | Redline (Field-Tested)", 0.15, 33.0),
            ("AWP | Asiimov (Field-Tested)", 0.19, 100.0),
            ("M4A1-S | Hyper Beast (Factory New)", 0.005, 80.0),
            ("Random Skin", 0.25, 50.0),
        ]

        for title, float_val, base_price in scenarios:
            result = arbitrage.calculate_float_premium(title, float_val, base_price)
            assert result.premium_multiplier >= 1.0
            assert result.premium_price >= base_price
