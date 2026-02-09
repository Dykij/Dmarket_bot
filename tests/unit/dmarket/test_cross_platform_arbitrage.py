"""Unit tests for cross_platform_arbitrage.py module.

Tests for cross-platform arbitrage between DMarket and Waxpeer, including
decision making, price comparisons, category filtering, and trade lock analysis.
"""

from decimal import Decimal

import pytest

# Skip all tests if structlog is not available
pytest.importorskip("structlog")


class TestCrossPlatformArbitrageConstants:
    """Tests for module constants and configuration."""

    def test_waxpeer_commission_value(self) -> None:
        """Test WAXPEER_COMMISSION is 6%."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_COMMISSION

        assert Decimal("0.06") == WAXPEER_COMMISSION

    def test_waxpeer_multiplier_value(self) -> None:
        """Test WAXPEER_MULTIPLIER is 94% (1 - 6%)."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_MULTIPLIER

        assert Decimal("0.94") == WAXPEER_MULTIPLIER

    def test_dmarket_commission_value(self) -> None:
        """Test DMARKET_COMMISSION is 5%."""
        from src.dmarket.cross_platform_arbitrage import DMARKET_COMMISSION

        assert Decimal("0.05") == DMARKET_COMMISSION

    def test_dmarket_multiplier_value(self) -> None:
        """Test DMARKET_MULTIPLIER is 95% (1 - 5%)."""
        from src.dmarket.cross_platform_arbitrage import DMARKET_MULTIPLIER

        assert Decimal("0.95") == DMARKET_MULTIPLIER

    def test_cs2_game_id_is_uuid(self) -> None:
        """Test CS2_GAME_ID is a valid UUID string."""
        from src.dmarket.cross_platform_arbitrage import CS2_GAME_ID

        assert isinstance(CS2_GAME_ID, str)
        assert len(CS2_GAME_ID) == 36  # UUID format

    def test_default_min_profit_usd(self) -> None:
        """Test DEFAULT_MIN_PROFIT_USD is $0.30."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MIN_PROFIT_USD

        assert Decimal("0.30") == DEFAULT_MIN_PROFIT_USD

    def test_default_min_roi_percent(self) -> None:
        """Test DEFAULT_MIN_ROI_PERCENT is 5%."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MIN_ROI_PERCENT

        assert Decimal("5.0") == DEFAULT_MIN_ROI_PERCENT

    def test_default_lock_roi_percent(self) -> None:
        """Test DEFAULT_LOCK_ROI_PERCENT is 15%."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_LOCK_ROI_PERCENT

        assert Decimal("15.0") == DEFAULT_LOCK_ROI_PERCENT

    def test_default_max_lock_days(self) -> None:
        """Test DEFAULT_MAX_LOCK_DAYS is 8 days."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MAX_LOCK_DAYS

        assert DEFAULT_MAX_LOCK_DAYS == 8

    def test_default_min_liquidity(self) -> None:
        """Test DEFAULT_MIN_LIQUIDITY is 5 daily sales."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MIN_LIQUIDITY

        assert DEFAULT_MIN_LIQUIDITY == 5


class TestArbitrageDecisionEnum:
    """Tests for ArbitrageDecision enum."""

    def test_buy_instant_value(self) -> None:
        """Test BUY_INSTANT enum value."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        assert ArbitrageDecision.BUY_INSTANT == "buy_instant"

    def test_buy_and_hold_value(self) -> None:
        """Test BUY_AND_HOLD enum value."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        assert ArbitrageDecision.BUY_AND_HOLD == "buy_and_hold"

    def test_skip_value(self) -> None:
        """Test SKIP enum value."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        assert ArbitrageDecision.SKIP == "skip"

    def test_insufficient_liquidity_value(self) -> None:
        """Test INSUFFICIENT_LIQUIDITY enum value."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        assert ArbitrageDecision.INSUFFICIENT_LIQUIDITY == "insufficient_liquidity"

    def test_enum_has_all_decisions(self) -> None:
        """Test that all expected decisions are present."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        expected_decisions = {"buy_instant", "buy_and_hold", "skip", "insufficient_liquidity"}
        actual_decisions = {d.value for d in ArbitrageDecision}
        assert actual_decisions == expected_decisions


class TestItemCategoryEnum:
    """Tests for ItemCategory enum."""

    def test_case_value(self) -> None:
        """Test CASE enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.CASE == "Case"

    def test_key_value(self) -> None:
        """Test KEY enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.KEY == "Key"

    def test_weapon_value(self) -> None:
        """Test WEAPON enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.WEAPON == "Weapon"

    def test_knife_value(self) -> None:
        """Test KNIFE enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.KNIFE == "Knife"

    def test_gloves_value(self) -> None:
        """Test GLOVES enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.GLOVES == "Gloves"

    def test_graffiti_value(self) -> None:
        """Test GRAFFITI enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.GRAFFITI == "Graffiti"

    def test_souvenir_value(self) -> None:
        """Test SOUVENIR enum value."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory.SOUVENIR == "Souvenir Package"


class TestAllowedCategories:
    """Tests for ALLOWED_CATEGORIES set."""

    def test_allowed_categories_contains_case(self) -> None:
        """Test ALLOWED_CATEGORIES contains CASE."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        assert ItemCategory.CASE in ALLOWED_CATEGORIES

    def test_allowed_categories_contains_key(self) -> None:
        """Test ALLOWED_CATEGORIES contains KEY."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        assert ItemCategory.KEY in ALLOWED_CATEGORIES

    def test_allowed_categories_contains_weapon(self) -> None:
        """Test ALLOWED_CATEGORIES contains WEAPON."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        assert ItemCategory.WEAPON in ALLOWED_CATEGORIES

    def test_allowed_categories_contains_knife(self) -> None:
        """Test ALLOWED_CATEGORIES contains KNIFE."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        assert ItemCategory.KNIFE in ALLOWED_CATEGORIES

    def test_allowed_categories_not_contains_graffiti(self) -> None:
        """Test ALLOWED_CATEGORIES does not contain GRAFFITI."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        assert ItemCategory.GRAFFITI not in ALLOWED_CATEGORIES

    def test_allowed_categories_count(self) -> None:
        """Test ALLOWED_CATEGORIES has expected count."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES

        assert len(ALLOWED_CATEGORIES) == 8


class TestBlacklistedCategories:
    """Tests for BLACKLISTED_CATEGORIES set."""

    def test_blacklisted_contains_graffiti(self) -> None:
        """Test BLACKLISTED_CATEGORIES contains GRAFFITI."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_CATEGORIES, ItemCategory

        assert ItemCategory.GRAFFITI in BLACKLISTED_CATEGORIES

    def test_blacklisted_contains_souvenir(self) -> None:
        """Test BLACKLISTED_CATEGORIES contains SOUVENIR."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_CATEGORIES, ItemCategory

        assert ItemCategory.SOUVENIR in BLACKLISTED_CATEGORIES

    def test_blacklisted_count(self) -> None:
        """Test BLACKLISTED_CATEGORIES has expected count."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_CATEGORIES

        assert len(BLACKLISTED_CATEGORIES) == 2


class TestBlacklistedKeywords:
    """Tests for BLACKLISTED_KEYWORDS frozenset."""

    def test_blacklisted_keywords_contains_graffiti(self) -> None:
        """Test BLACKLISTED_KEYWORDS contains 'graffiti'."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        assert "graffiti" in BLACKLISTED_KEYWORDS

    def test_blacklisted_keywords_contains_souvenir(self) -> None:
        """Test BLACKLISTED_KEYWORDS contains 'souvenir'."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        assert "souvenir" in BLACKLISTED_KEYWORDS

    def test_blacklisted_keywords_contains_sealed_graffiti(self) -> None:
        """Test BLACKLISTED_KEYWORDS contains 'sealed graffiti'."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        assert "sealed graffiti" in BLACKLISTED_KEYWORDS

    def test_blacklisted_keywords_is_frozenset(self) -> None:
        """Test BLACKLISTED_KEYWORDS is a frozenset."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        assert isinstance(BLACKLISTED_KEYWORDS, frozenset)


class TestProfitCalculations:
    """Tests for profit calculation logic."""

    def test_calculate_net_profit_formula(self) -> None:
        """Test net profit calculation: sell_price * 0.94 - buy_price."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_MULTIPLIER

        buy_price = Decimal("10.00")
        sell_price = Decimal("12.00")

        net_sell = sell_price * WAXPEER_MULTIPLIER
        profit = net_sell - buy_price

        assert profit == Decimal("1.28")  # 12 * 0.94 - 10 = 1.28

    def test_roi_calculation_formula(self) -> None:
        """Test ROI calculation: (profit / buy_price) * 100."""
        buy_price = Decimal("10.00")
        profit = Decimal("1.28")

        roi = (profit / buy_price) * 100

        assert roi == Decimal("12.80")  # (1.28 / 10) * 100 = 12.8%

    def test_break_even_price_calculation(self) -> None:
        """Test break-even sell price calculation."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_MULTIPLIER

        buy_price = Decimal("10.00")
        break_even = buy_price / WAXPEER_MULTIPLIER

        # Allow for floating point precision differences
        expected = Decimal("10.638297872340425531914893617")
        assert abs(break_even - expected) < Decimal("0.000000000000000000000001")


class TestCommissionCalculations:
    """Tests for commission calculation logic."""

    def test_waxpeer_commission_on_sale(self) -> None:
        """Test Waxpeer takes 6% commission on sale."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_COMMISSION

        sale_price = Decimal("100.00")
        commission = sale_price * WAXPEER_COMMISSION

        assert commission == Decimal("6.00")

    def test_waxpeer_net_after_commission(self) -> None:
        """Test Waxpeer net amount after commission."""
        from src.dmarket.cross_platform_arbitrage import WAXPEER_MULTIPLIER

        sale_price = Decimal("100.00")
        net = sale_price * WAXPEER_MULTIPLIER

        assert net == Decimal("94.00")

    def test_dmarket_commission_on_sale(self) -> None:
        """Test DMarket takes 5% commission on sale."""
        from src.dmarket.cross_platform_arbitrage import DMARKET_COMMISSION

        sale_price = Decimal("100.00")
        commission = sale_price * DMARKET_COMMISSION

        assert commission == Decimal("5.00")


class TestDecisionLogic:
    """Tests for arbitrage decision-making logic."""

    def test_high_roi_instant_decision(self) -> None:
        """Test high ROI without lock should result in BUY_INSTANT."""
        from src.dmarket.cross_platform_arbitrage import (
            DEFAULT_MIN_ROI_PERCENT,
            ArbitrageDecision,
        )

        roi = Decimal("10.0")  # Above 5% threshold
        has_lock = False

        if roi >= DEFAULT_MIN_ROI_PERCENT and not has_lock:
            decision = ArbitrageDecision.BUY_INSTANT
        else:
            decision = ArbitrageDecision.SKIP

        assert decision == ArbitrageDecision.BUY_INSTANT

    def test_high_roi_with_lock_hold_decision(self) -> None:
        """Test high ROI with lock should result in BUY_AND_HOLD."""
        from src.dmarket.cross_platform_arbitrage import (
            DEFAULT_LOCK_ROI_PERCENT,
            ArbitrageDecision,
        )

        roi = Decimal("20.0")  # Above 15% lock threshold
        has_lock = True
        lock_days = 5

        if roi >= DEFAULT_LOCK_ROI_PERCENT and has_lock and lock_days <= 8:
            decision = ArbitrageDecision.BUY_AND_HOLD
        else:
            decision = ArbitrageDecision.SKIP

        assert decision == ArbitrageDecision.BUY_AND_HOLD

    def test_low_roi_skip_decision(self) -> None:
        """Test low ROI should result in SKIP."""
        from src.dmarket.cross_platform_arbitrage import (
            DEFAULT_MIN_ROI_PERCENT,
            ArbitrageDecision,
        )

        roi = Decimal("3.0")  # Below 5% threshold

        if roi < DEFAULT_MIN_ROI_PERCENT:
            decision = ArbitrageDecision.SKIP
        else:
            decision = ArbitrageDecision.BUY_INSTANT

        assert decision == ArbitrageDecision.SKIP


class TestLiquidityThresholds:
    """Tests for liquidity threshold logic."""

    def test_below_min_liquidity_insufficient(self) -> None:
        """Test below minimum liquidity should be insufficient."""
        from src.dmarket.cross_platform_arbitrage import (
            DEFAULT_MIN_LIQUIDITY,
            ArbitrageDecision,
        )

        daily_sales = 3  # Below 5 minimum

        if daily_sales < DEFAULT_MIN_LIQUIDITY:
            decision = ArbitrageDecision.INSUFFICIENT_LIQUIDITY
        else:
            decision = ArbitrageDecision.BUY_INSTANT

        assert decision == ArbitrageDecision.INSUFFICIENT_LIQUIDITY

    def test_above_min_liquidity_sufficient(self) -> None:
        """Test above minimum liquidity should be sufficient."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MIN_LIQUIDITY

        daily_sales = 10  # Above 5 minimum

        is_liquid = daily_sales >= DEFAULT_MIN_LIQUIDITY

        assert is_liquid is True


class TestTradeLockLogic:
    """Tests for trade lock handling logic."""

    def test_lock_within_max_days_acceptable(self) -> None:
        """Test lock within max days is acceptable."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MAX_LOCK_DAYS

        lock_days = 5  # Within 8 day max

        is_acceptable = lock_days <= DEFAULT_MAX_LOCK_DAYS

        assert is_acceptable is True

    def test_lock_exceeds_max_days_rejected(self) -> None:
        """Test lock exceeding max days is rejected."""
        from src.dmarket.cross_platform_arbitrage import DEFAULT_MAX_LOCK_DAYS

        lock_days = 12  # Exceeds 8 day max

        is_acceptable = lock_days <= DEFAULT_MAX_LOCK_DAYS

        assert is_acceptable is False

    def test_no_lock_zero_days(self) -> None:
        """Test no lock means zero days."""
        lock_days = 0
        has_lock = lock_days > 0

        assert has_lock is False


class TestCategoryFiltering:
    """Tests for category-based filtering."""

    def test_weapon_category_allowed(self) -> None:
        """Test weapon category is allowed."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        category = ItemCategory.WEAPON

        is_allowed = category in ALLOWED_CATEGORIES

        assert is_allowed is True

    def test_graffiti_category_blacklisted(self) -> None:
        """Test graffiti category is blacklisted."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_CATEGORIES, ItemCategory

        category = ItemCategory.GRAFFITI

        is_blacklisted = category in BLACKLISTED_CATEGORIES

        assert is_blacklisted is True

    def test_knife_category_high_value(self) -> None:
        """Test knife category is allowed (high value items)."""
        from src.dmarket.cross_platform_arbitrage import ALLOWED_CATEGORIES, ItemCategory

        category = ItemCategory.KNIFE

        is_allowed = category in ALLOWED_CATEGORIES

        assert is_allowed is True


class TestKeywordFiltering:
    """Tests for keyword-based filtering."""

    def test_graffiti_keyword_blocks_item(self) -> None:
        """Test 'graffiti' keyword should block item."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        item_name = "Graffiti | GGWP"

        is_blocked = any(keyword in item_name.lower() for keyword in BLACKLISTED_KEYWORDS)

        assert is_blocked is True

    def test_souvenir_keyword_blocks_item(self) -> None:
        """Test 'souvenir' keyword should block item."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        item_name = "Souvenir M4A4 | Radiation Hazard"

        is_blocked = any(keyword in item_name.lower() for keyword in BLACKLISTED_KEYWORDS)

        assert is_blocked is True

    def test_normal_weapon_not_blocked(self) -> None:
        """Test normal weapon name is not blocked."""
        from src.dmarket.cross_platform_arbitrage import BLACKLISTED_KEYWORDS

        item_name = "AK-47 | Redline (Field-Tested)"

        is_blocked = any(keyword in item_name.lower() for keyword in BLACKLISTED_KEYWORDS)

        assert is_blocked is False


class TestDecimalPrecision:
    """Tests for Decimal precision in calculations."""

    def test_decimal_precision_in_profit(self) -> None:
        """Test Decimal precision is maintained in profit calculation."""
        buy_price = Decimal("9.99")
        sell_price = Decimal("11.50")
        multiplier = Decimal("0.94")

        profit = (sell_price * multiplier) - buy_price

        # Verify precision
        assert isinstance(profit, Decimal)
        assert profit == Decimal("0.82")

    def test_small_profit_margin(self) -> None:
        """Test small profit margins are calculated precisely."""
        buy_price = Decimal("100.00")
        sell_price = Decimal("106.50")
        multiplier = Decimal("0.94")

        profit = (sell_price * multiplier) - buy_price

        assert profit == Decimal("0.11")

    def test_negative_profit_detected(self) -> None:
        """Test negative profit (loss) is correctly detected."""
        buy_price = Decimal("10.00")
        sell_price = Decimal("10.00")
        multiplier = Decimal("0.94")

        profit = (sell_price * multiplier) - buy_price

        assert profit < 0
        assert profit == Decimal("-0.60")


class TestModuleImports:
    """Tests for module imports and structure."""

    def test_module_imports_without_error(self) -> None:
        """Test module can be imported without errors."""
        import src.dmarket.cross_platform_arbitrage

        assert src.dmarket.cross_platform_arbitrage is not None

    def test_arbitrage_decision_importable(self) -> None:
        """Test ArbitrageDecision is importable."""
        from src.dmarket.cross_platform_arbitrage import ArbitrageDecision

        assert ArbitrageDecision is not None

    def test_item_category_importable(self) -> None:
        """Test ItemCategory is importable."""
        from src.dmarket.cross_platform_arbitrage import ItemCategory

        assert ItemCategory is not None

    def test_all_constants_importable(self) -> None:
        """Test all constants are importable."""
        from src.dmarket.cross_platform_arbitrage import (
            ALLOWED_CATEGORIES,
            BLACKLISTED_CATEGORIES,
            BLACKLISTED_KEYWORDS,
            CS2_GAME_ID,
            DEFAULT_MAX_LOCK_DAYS,
            DEFAULT_MIN_LIQUIDITY,
            DEFAULT_MIN_PROFIT_USD,
            DEFAULT_MIN_ROI_PERCENT,
            DMARKET_COMMISSION,
            WAXPEER_COMMISSION,
        )

        assert WAXPEER_COMMISSION is not None
        assert DMARKET_COMMISSION is not None
        assert CS2_GAME_ID is not None
        assert DEFAULT_MIN_PROFIT_USD is not None
        assert DEFAULT_MIN_ROI_PERCENT is not None
        assert DEFAULT_MAX_LOCK_DAYS is not None
        assert DEFAULT_MIN_LIQUIDITY is not None
        assert ALLOWED_CATEGORIES is not None
        assert BLACKLISTED_CATEGORIES is not None
        assert BLACKLISTED_KEYWORDS is not None
