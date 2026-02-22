"""Tests for Advanced Order System module.

Tests for the advanced order system (CS Float-style Advanced Buy Orders).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.advanced_order_system import (
    BLUE_GEM_PATTERNS,
    DOPPLER_PREMIUMS,
    AdvancedOrder,
    AdvancedOrderFilter,
    AdvancedOrderManager,
    DopplerPhase,
    OrderTemplate,
    PatternType,
    create_doppler_order,
    create_float_order,
    create_pattern_order,
    create_sticker_order,
)


class TestDopplerPhase:
    """Tests for DopplerPhase enum."""

    def test_phase_1_value(self):
        """Test Phase 1 value."""
        assert DopplerPhase.PHASE_1 == "Phase 1"

    def test_phase_2_value(self):
        """Test Phase 2 value."""
        assert DopplerPhase.PHASE_2 == "Phase 2"

    def test_phase_3_value(self):
        """Test Phase 3 value."""
        assert DopplerPhase.PHASE_3 == "Phase 3"

    def test_phase_4_value(self):
        """Test Phase 4 value."""
        assert DopplerPhase.PHASE_4 == "Phase 4"

    def test_ruby_value(self):
        """Test Ruby value."""
        assert DopplerPhase.RUBY == "Ruby"

    def test_sapphire_value(self):
        """Test Sapphire value."""
        assert DopplerPhase.SAPPHIRE == "Sapphire"

    def test_black_pearl_value(self):
        """Test Black Pearl value."""
        assert DopplerPhase.BLACK_PEARL == "Black Pearl"

    def test_emerald_value(self):
        """Test Emerald value."""
        assert DopplerPhase.EMERALD == "Emerald"


class TestPatternType:
    """Tests for PatternType enum."""

    def test_blue_gem_value(self):
        """Test Blue Gem value."""
        assert PatternType.CASE_HARDENED_BLUE == "blue_gem"

    def test_gold_gem_value(self):
        """Test Gold Gem value."""
        assert PatternType.CASE_HARDENED_GOLD == "gold_gem"

    def test_max_fade_value(self):
        """Test Max Fade value."""
        assert PatternType.FADE_MAX == "max_fade"

    def test_fire_ice_value(self):
        """Test Fire & Ice value."""
        assert PatternType.MARBLE_FIRE_ICE == "fire_ice"


class TestBlueGemPatterns:
    """Tests for Blue Gem pattern constants."""

    def test_ak47_patterns_exist(self):
        """Test AK-47 Blue Gem patterns exist."""
        assert "AK-47 | Case Hardened" in BLUE_GEM_PATTERNS
        assert 661 in BLUE_GEM_PATTERNS["AK-47 | Case Hardened"]
        assert 670 in BLUE_GEM_PATTERNS["AK-47 | Case Hardened"]

    def test_five_seven_patterns_exist(self):
        """Test Five-SeveN Blue Gem patterns exist."""
        assert "Five-SeveN | Case Hardened" in BLUE_GEM_PATTERNS
        assert 690 in BLUE_GEM_PATTERNS["Five-SeveN | Case Hardened"]

    def test_karambit_patterns_exist(self):
        """Test Karambit Blue Gem patterns exist."""
        assert "Karambit | Case Hardened" in BLUE_GEM_PATTERNS
        assert 387 in BLUE_GEM_PATTERNS["Karambit | Case Hardened"]

    def test_bayonet_patterns_exist(self):
        """Test Bayonet Blue Gem patterns exist."""
        assert "Bayonet | Case Hardened" in BLUE_GEM_PATTERNS


class TestDopplerPremiums:
    """Tests for Doppler premium multipliers."""

    def test_ruby_premium(self):
        """Test Ruby has highest standard premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.RUBY] == 5.0

    def test_sapphire_premium(self):
        """Test Sapphire premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.SAPPHIRE] == 4.5

    def test_black_pearl_premium(self):
        """Test Black Pearl premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.BLACK_PEARL] == 3.0

    def test_emerald_premium(self):
        """Test Emerald has highest premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.EMERALD] == 6.0

    def test_phase_2_premium(self):
        """Test Phase 2 (Pink Galaxy) premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.PHASE_2] == 1.15

    def test_phase_4_premium(self):
        """Test Phase 4 (Blue) premium."""
        assert DOPPLER_PREMIUMS[DopplerPhase.PHASE_4] == 1.10

    def test_phase_1_base(self):
        """Test Phase 1 has base price."""
        assert DOPPLER_PREMIUMS[DopplerPhase.PHASE_1] == 1.0

    def test_phase_3_below_base(self):
        """Test Phase 3 is below base price."""
        assert DOPPLER_PREMIUMS[DopplerPhase.PHASE_3] == 0.95


class TestAdvancedOrderFilter:
    """Tests for AdvancedOrderFilter dataclass."""

    def test_create_empty_filter(self):
        """Test creating empty filter."""
        filt = AdvancedOrderFilter()
        assert filt.float_min is None
        assert filt.float_max is None
        assert filt.phase is None

    def test_create_float_filter(self):
        """Test creating filter with float range."""
        filt = AdvancedOrderFilter(float_min=0.15, float_max=0.16)
        assert filt.float_min == 0.15
        assert filt.float_max == 0.16

    def test_create_doppler_filter(self):
        """Test creating filter with Doppler phase."""
        filt = AdvancedOrderFilter(phase=DopplerPhase.RUBY)
        assert filt.phase == DopplerPhase.RUBY

    def test_create_pattern_filter(self):
        """Test creating filter with paint seed."""
        filt = AdvancedOrderFilter(paint_seed=661)
        assert filt.paint_seed == 661

    def test_create_patterns_filter(self):
        """Test creating filter with multiple paint seeds."""
        filt = AdvancedOrderFilter(paint_seeds=[661, 670, 321])
        assert filt.paint_seeds == [661, 670, 321]

    def test_create_stattrak_filter(self):
        """Test creating filter with StatTrak."""
        filt = AdvancedOrderFilter(stat_trak=True)
        assert filt.stat_trak is True

    def test_create_souvenir_filter(self):
        """Test creating filter with Souvenir."""
        filt = AdvancedOrderFilter(souvenir=True)
        assert filt.souvenir is True

    def test_to_target_attrs_float(self):
        """Test converting float filter to target attrs."""
        filt = AdvancedOrderFilter(float_min=0.15, float_max=0.16)
        attrs = filt.to_target_attrs()
        assert attrs["floatMin"] == "0.15"
        assert attrs["floatMax"] == "0.16"

    def test_to_target_attrs_paint_seed(self):
        """Test converting paint seed filter to target attrs."""
        filt = AdvancedOrderFilter(paint_seed=661)
        attrs = filt.to_target_attrs()
        assert attrs["paintSeed"] == 661

    def test_to_target_attrs_paint_seeds(self):
        """Test converting paint seeds filter to target attrs."""
        filt = AdvancedOrderFilter(paint_seeds=[661, 670])
        attrs = filt.to_target_attrs()
        assert attrs["paintSeed"] == [661, 670]

    def test_to_target_attrs_phase(self):
        """Test converting Doppler phase filter to target attrs."""
        filt = AdvancedOrderFilter(phase=DopplerPhase.RUBY)
        attrs = filt.to_target_attrs()
        assert attrs["phase"] == "Ruby"

    def test_to_target_attrs_stattrak(self):
        """Test converting StatTrak filter to target attrs."""
        filt = AdvancedOrderFilter(stat_trak=True)
        attrs = filt.to_target_attrs()
        assert attrs["isStatTrak"] is True

    def test_to_target_attrs_souvenir(self):
        """Test converting Souvenir filter to target attrs."""
        filt = AdvancedOrderFilter(souvenir=True)
        attrs = filt.to_target_attrs()
        assert attrs["isSouvenir"] is True

    def test_to_target_attrs_empty(self):
        """Test converting empty filter to target attrs."""
        filt = AdvancedOrderFilter()
        attrs = filt.to_target_attrs()
        assert attrs == {}

    def test_count_conditions_empty(self):
        """Test counting conditions for empty filter."""
        filt = AdvancedOrderFilter()
        assert filt.count_conditions() == 0

    def test_count_conditions_float(self):
        """Test counting conditions with float range."""
        filt = AdvancedOrderFilter(float_min=0.15, float_max=0.16)
        assert filt.count_conditions() == 2

    def test_count_conditions_paint_seed(self):
        """Test counting conditions with paint seed."""
        filt = AdvancedOrderFilter(paint_seed=661)
        assert filt.count_conditions() == 1

    def test_count_conditions_paint_seeds(self):
        """Test counting conditions with multiple paint seeds."""
        filt = AdvancedOrderFilter(paint_seeds=[661, 670, 321])
        assert filt.count_conditions() == 3

    def test_count_conditions_phase(self):
        """Test counting conditions with phase."""
        filt = AdvancedOrderFilter(phase=DopplerPhase.RUBY)
        assert filt.count_conditions() == 1

    def test_count_conditions_combined(self):
        """Test counting combined conditions."""
        filt = AdvancedOrderFilter(
            float_min=0.00,
            float_max=0.01,
            phase=DopplerPhase.RUBY,
            stat_trak=True,
        )
        assert filt.count_conditions() == 4


class TestAdvancedOrder:
    """Tests for AdvancedOrder dataclass."""

    def test_create_order(self):
        """Test creating basic order."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=50.0,
        )
        assert order.item_title == "AK-47 | Redline"
        assert order.max_price_usd == 50.0
        assert order.game == "csgo"
        assert order.amount == 1

    def test_create_order_with_all_fields(self):
        """Test creating order with all fields."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            game="csgo",
            max_price_usd=50.0,
            amount=3,
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.16),
            expected_sell_price=62.0,
            notes="Premium float order",
        )
        assert order.amount == 3
        assert order.expected_sell_price == 62.0
        assert order.notes == "Premium float order"

    def test_calculate_expected_profit(self):
        """Test calculating expected profit."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=50.0,
            expected_sell_price=62.0,
        )
        # Profit = 62 * 0.95 - 50 = 58.9 - 50 = 8.9
        profit = order.calculate_expected_profit(commission=0.05)
        assert pytest.approx(profit, rel=0.01) == 8.9

    def test_calculate_expected_profit_no_sell_price(self):
        """Test calculating profit without expected sell price."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=50.0,
        )
        profit = order.calculate_expected_profit()
        assert profit == 0

    def test_calculate_roi(self):
        """Test calculating ROI."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=50.0,
            expected_sell_price=62.0,
        )
        # ROI = (8.9 / 50) * 100 = 17.8%
        roi = order.calculate_roi(commission=0.05)
        assert pytest.approx(roi, rel=0.01) == 17.8

    def test_calculate_roi_zero_price(self):
        """Test calculating ROI with zero price."""
        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=0,
            expected_sell_price=62.0,
        )
        roi = order.calculate_roi()
        assert roi == 0


class TestOrderTemplate:
    """Tests for OrderTemplate dataclass."""

    def test_create_template(self):
        """Test creating order template."""
        template = OrderTemplate(
            name="AK-47 Redline Premium",
            description="Best FT float",
            item_title="AK-47 | Redline (Field-Tested)",
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.155),
            base_price_usd=33.0,
            expected_premium_multiplier=1.88,
        )
        assert template.name == "AK-47 Redline Premium"
        assert template.base_price_usd == 33.0
        assert template.expected_premium_multiplier == 1.88

    def test_create_order_from_template(self):
        """Test creating order from template."""
        template = OrderTemplate(
            name="AK-47 Redline Premium",
            description="Best FT float",
            item_title="AK-47 | Redline (Field-Tested)",
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.155),
            base_price_usd=33.0,
            expected_premium_multiplier=1.88,
        )
        order = template.create_order()
        assert order.item_title == "AK-47 | Redline (Field-Tested)"
        assert order.max_price_usd == 33.0
        assert pytest.approx(order.expected_sell_price, rel=0.01) == 62.04
        assert "Template: AK-47 Redline Premium" in order.notes

    def test_create_order_with_custom_price(self):
        """Test creating order from template with custom price."""
        template = OrderTemplate(
            name="Test",
            description="Test",
            item_title="Test Item",
            filter=AdvancedOrderFilter(),
            base_price_usd=50.0,
            expected_premium_multiplier=1.5,
        )
        order = template.create_order(max_price_usd=60.0)
        assert order.max_price_usd == 60.0
        # Expected sell should still use base_price * multiplier
        assert order.expected_sell_price == 75.0


class TestAdvancedOrderManager:
    """Tests for AdvancedOrderManager class."""

    @pytest.fixture()
    def mock_target_manager(self):
        """Create mock target manager."""
        manager = MagicMock()
        manager.create_target = AsyncMock()
        manager.delete_target = AsyncMock()
        return manager

    @pytest.fixture()
    def order_manager(self, mock_target_manager):
        """Create AdvancedOrderManager instance."""
        return AdvancedOrderManager(mock_target_manager, commission=0.05)

    def test_init(self, mock_target_manager):
        """Test initialization."""
        manager = AdvancedOrderManager(mock_target_manager)
        assert manager.targets is mock_target_manager
        assert manager.commission == 0.05
        assert len(manager.templates) > 0

    def test_default_templates_loaded(self, order_manager):
        """Test default templates are loaded."""
        templates = order_manager.templates
        assert "ak47_redline_premium_ft" in templates
        assert "ak47_redline_good_ft" in templates
        assert "awp_asiimov_best_ft" in templates
        assert "awp_asiimov_blackiimov" in templates
        assert "karambit_doppler_ruby" in templates
        assert "karambit_doppler_sapphire" in templates
        assert "ak47_ch_blue_gem" in templates
        assert "ak47_kato14_holo" in templates

    def test_list_templates(self, order_manager):
        """Test listing templates."""
        templates = order_manager.list_templates()
        assert len(templates) > 0
        assert all("name" in t for t in templates)
        assert all("description" in t for t in templates)
        assert all("item" in t for t in templates)
        assert all("base_price" in t for t in templates)

    def test_get_active_orders_empty(self, order_manager):
        """Test getting active orders when none exist."""
        orders = order_manager.get_active_orders()
        assert orders == []

    @pytest.mark.asyncio()
    async def test_create_order_success(self, order_manager, mock_target_manager):
        """Test creating order successfully."""
        mock_target_manager.create_target.return_value = MagicMock(
            success=True,
            target_id="target_123",
        )

        order = AdvancedOrder(
            item_title="AK-47 | Redline",
            max_price_usd=50.0,
            filter=AdvancedOrderFilter(float_min=0.15, float_max=0.16),
        )

        result = await order_manager.create_order(order)

        assert result.success is True
        assert order.target_id == "target_123"
        assert order.is_active is True
        assert "target_123" in order_manager.active_orders

    @pytest.mark.asyncio()
    async def test_create_order_too_many_conditions(self, order_manager):
        """Test creating order with too many conditions."""
        # Create filter with > 10 conditions
        order = AdvancedOrder(
            item_title="Test",
            max_price_usd=50.0,
            filter=AdvancedOrderFilter(
                float_min=0.0,
                float_max=0.01,
                paint_seeds=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # 10 seeds
                stat_trak=True,  # +1
            ),
        )

        result = await order_manager.create_order(order)

        assert result.success is False
        assert "Too many" in result.message

    @pytest.mark.asyncio()
    async def test_create_from_template_success(self, order_manager, mock_target_manager):
        """Test creating order from template."""
        mock_target_manager.create_target.return_value = MagicMock(
            success=True,
            target_id="target_456",
        )

        result = await order_manager.create_from_template("ak47_redline_premium_ft")

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_create_from_template_not_found(self, order_manager):
        """Test creating order from non-existent template."""
        result = await order_manager.create_from_template("non_existent_template")
        assert result is None

    @pytest.mark.asyncio()
    async def test_cancel_order(self, order_manager, mock_target_manager):
        """Test cancelling order."""
        # First create an order
        mock_target_manager.create_target.return_value = MagicMock(
            success=True,
            target_id="target_789",
        )
        mock_target_manager.delete_target.return_value = True

        order = AdvancedOrder(
            item_title="Test",
            max_price_usd=50.0,
        )
        await order_manager.create_order(order)

        # Now cancel it
        result = await order_manager.cancel_order("target_789")

        assert result is True
        assert order_manager.active_orders["target_789"].is_active is False

    @pytest.mark.asyncio()
    async def test_cancel_order_not_found(self, order_manager):
        """Test cancelling non-existent order."""
        result = await order_manager.cancel_order("non_existent")
        assert result is False

    @pytest.mark.asyncio()
    async def test_cancel_all_orders(self, order_manager, mock_target_manager):
        """Test cancelling all orders."""
        mock_target_manager.create_target.return_value = MagicMock(
            success=True,
            target_id="target_1",
        )
        mock_target_manager.delete_target.return_value = True

        # Create multiple orders
        for i in range(3):
            mock_target_manager.create_target.return_value = MagicMock(
                success=True,
                target_id=f"target_{i}",
            )
            order = AdvancedOrder(
                item_title=f"Item {i}",
                max_price_usd=50.0,
            )
            await order_manager.create_order(order)

        # Cancel all
        cancelled = await order_manager.cancel_all_orders()
        assert cancelled == 3


class TestQuickCreateFunctions:
    """Tests for quick order creation functions."""

    def test_create_float_order(self):
        """Test creating float order."""
        order = create_float_order(
            "AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.155,
            max_price=55.0,
            expected_sell=62.0,
        )
        assert order.item_title == "AK-47 | Redline (Field-Tested)"
        assert order.max_price_usd == 55.0
        assert order.filter.float_min == 0.15
        assert order.filter.float_max == 0.155
        assert order.expected_sell_price == 62.0

    def test_create_float_order_without_expected_sell(self):
        """Test creating float order without expected sell price."""
        order = create_float_order(
            "Test Item",
            float_min=0.0,
            float_max=0.01,
            max_price=100.0,
        )
        assert order.expected_sell_price is None

    def test_create_doppler_order(self):
        """Test creating Doppler order."""
        order = create_doppler_order(
            "★ Karambit | Doppler (Factory New)",
            phase=DopplerPhase.RUBY,
            max_price=500.0,
        )
        assert order.item_title == "★ Karambit | Doppler (Factory New)"
        assert order.max_price_usd == 500.0
        assert order.filter.phase == DopplerPhase.RUBY
        # Expected sell = 500 * 5.0 = 2500
        assert order.expected_sell_price == 2500.0
        assert "Ruby" in order.notes

    def test_create_doppler_order_sapphire(self):
        """Test creating Doppler Sapphire order."""
        order = create_doppler_order(
            "★ Karambit | Doppler (Factory New)",
            phase=DopplerPhase.SAPPHIRE,
            max_price=500.0,
        )
        # Expected sell = 500 * 4.5 = 2250
        assert order.expected_sell_price == 2250.0

    def test_create_doppler_order_emerald(self):
        """Test creating Doppler Emerald order."""
        order = create_doppler_order(
            "★ Karambit | Gamma Doppler (Factory New)",
            phase=DopplerPhase.EMERALD,
            max_price=500.0,
        )
        # Expected sell = 500 * 6.0 = 3000
        assert order.expected_sell_price == 3000.0

    def test_create_pattern_order(self):
        """Test creating pattern order."""
        order = create_pattern_order(
            "AK-47 | Case Hardened (Field-Tested)",
            paint_seeds=[661, 670, 321],
            max_price=100.0,
            expected_premium=10.0,
        )
        assert order.item_title == "AK-47 | Case Hardened (Field-Tested)"
        assert order.max_price_usd == 100.0
        assert order.filter.paint_seeds == [661, 670, 321]
        # Expected sell = 100 * 10 = 1000
        assert order.expected_sell_price == 1000.0
        assert "661" in order.notes

    def test_create_pattern_order_default_premium(self):
        """Test creating pattern order with default premium."""
        order = create_pattern_order(
            "Test Item",
            paint_seeds=[123],
            max_price=50.0,
        )
        # Default premium is 2.0
        assert order.expected_sell_price == 100.0

    def test_create_sticker_order(self):
        """Test creating sticker order."""
        order = create_sticker_order(
            "AK-47",
            sticker_categories=["Katowice 2014"],
            max_price=100.0,
            holo=True,
            min_stickers=1,
        )
        assert order.item_title == "AK-47"
        assert order.max_price_usd == 100.0
        assert order.filter.sticker_filter is not None
        assert order.filter.sticker_filter.holo is True
        assert order.filter.sticker_filter.min_stickers == 1

    def test_create_sticker_order_no_holo(self):
        """Test creating sticker order without holo requirement."""
        order = create_sticker_order(
            "AWP",
            sticker_categories=["Cologne 2014"],
            max_price=50.0,
            holo=False,
        )
        assert order.filter.sticker_filter.holo is False


class TestIntegration:
    """Integration tests for Advanced Order System."""

    @pytest.fixture()
    def mock_target_manager(self):
        """Create mock target manager."""
        manager = MagicMock()
        manager.create_target = AsyncMock()
        manager.delete_target = AsyncMock()
        return manager

    @pytest.mark.asyncio()
    async def test_full_order_workflow(self, mock_target_manager):
        """Test complete order workflow."""
        mock_target_manager.create_target.return_value = MagicMock(
            success=True,
            target_id="order_123",
        )
        mock_target_manager.delete_target.return_value = True

        manager = AdvancedOrderManager(mock_target_manager)

        # 1. List templates
        templates = manager.list_templates()
        assert len(templates) > 0

        # 2. Create order from template
        result = await manager.create_from_template("ak47_redline_premium_ft")
        assert result.success is True

        # 3. Get active orders
        active = manager.get_active_orders()
        assert len(active) == 1

        # 4. Cancel order
        cancelled = await manager.cancel_all_orders()
        assert cancelled == 1

        # 5. Verify no active orders
        active = manager.get_active_orders()
        assert len(active) == 0

    @pytest.mark.asyncio()
    async def test_order_profit_calculation_workflow(self, mock_target_manager):
        """Test order profit calculation workflow."""
        manager = AdvancedOrderManager(mock_target_manager, commission=0.05)

        # Create order using quick function
        order = create_float_order(
            "AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.155,
            max_price=50.0,
            expected_sell=62.0,
        )

        # Calculate expected metrics
        profit = order.calculate_expected_profit(commission=0.05)
        roi = order.calculate_roi(commission=0.05)

        assert profit > 0
        assert roi > 10  # Should be profitable

    def test_template_ak47_redline_premium_roi(self, mock_target_manager):
        """Test AK-47 Redline Premium template ROI."""
        manager = AdvancedOrderManager(mock_target_manager)

        template = manager.templates["ak47_redline_premium_ft"]
        order = template.create_order()

        roi = order.calculate_roi(commission=0.05)
        # 33 * 1.88 * 0.95 - 33 = 58.89 - 33 = 25.89
        # ROI = 25.89 / 33 * 100 = 78.45%
        assert roi > 70  # Should have high ROI
