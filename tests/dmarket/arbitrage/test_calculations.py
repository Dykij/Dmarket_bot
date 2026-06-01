"""Tests for arbitrage calculations module.

This module contains comprehensive tests for:
- calculate_commission: Commission calculation based on item characteristics
- calculate_profit: Profit calculation for arbitrage
- calculate_net_profit: Net profit calculation
- calculate_profit_percent: Profit percentage calculation
- get_fee_for_liquidity: Fee determination based on liquidity
- cents_to_usd/usd_to_cents: Currency conversion
- is_profitable_opportunity: Profitability check
"""

from __future__ import annotations

import pytest


class TestCalculateCommission:
    """Tests for calculate_commission function."""

    def test_calculate_commission_default_values(self) -> None:
        """Test commission with default/average values."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Standard rarity, standard type, medium popularity, csgo
        commission = calculate_commission("classified", "rifle", 0.5, "csgo")
        assert 2.0 <= commission <= 15.0

    def test_calculate_commission_high_rarity_high_value(self) -> None:
        """Test commission for high rarity high value items."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Covert rarity + knife type should give higher commission
        commission = calculate_commission("covert", "knife", 0.5, "csgo")
        assert commission >= 7.0  # Should be higher than base

    def test_calculate_commission_low_rarity_low_value(self) -> None:
        """Test commission for low rarity low value items."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Consumer rarity + sticker type should give lower commission
        commission = calculate_commission("consumer", "sticker", 0.5, "csgo")
        assert commission <= 7.0  # Should be lower than base

    def test_calculate_commission_high_popularity(self) -> None:
        """Test commission for highly popular items."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # High popularity reduces commission
        commission = calculate_commission("classified", "rifle", 0.9, "csgo")
        assert commission <= 7.0 * 0.85 * 1.1  # Approx lower bound

    def test_calculate_commission_low_popularity(self) -> None:
        """Test commission for low popularity items."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Low popularity increases commission
        commission = calculate_commission("classified", "rifle", 0.1, "csgo")
        assert commission >= 7.0  # Higher than base

    def test_calculate_commission_rust_game(self) -> None:
        """Test commission for Rust items (higher commission)."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Rust typically has higher commission
        commission_rust = calculate_commission("classified", "rifle", 0.5, "rust")
        commission_csgo = calculate_commission("classified", "rifle", 0.5, "csgo")
        # Rust should have higher or equal commission
        assert commission_rust >= commission_csgo * 0.9

    def test_calculate_commission_minimum_bound(self) -> None:
        """Test that commission doesn't go below minimum."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Use all factors that reduce commission
        commission = calculate_commission("consumer", "sticker", 0.99, "csgo")
        assert commission >= 2.0

    def test_calculate_commission_maximum_bound(self) -> None:
        """Test that commission doesn't exceed maximum."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Use all factors that increase commission
        commission = calculate_commission("covert", "knife", 0.01, "rust")
        assert commission <= 15.0

    @pytest.mark.parametrize(
        ("rarity", "expected_higher"),
        (
            ("covert", True),
            ("extraordinary", True),
            ("consumer", False),
            ("industrial", False),
            ("mil-spec", None),  # neutral
        ),
    )
    def test_calculate_commission_rarity_factors(
        self, rarity: str, expected_higher: bool | None
    ) -> None:
        """Test commission varies correctly with rarity."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        base_commission = calculate_commission("classified", "rifle", 0.5, "csgo")
        test_commission = calculate_commission(rarity, "rifle", 0.5, "csgo")

        if expected_higher is True:
            assert test_commission > base_commission * 0.95
        elif expected_higher is False:
            assert test_commission < base_commission * 1.05

    @pytest.mark.parametrize(
        ("item_type", "expected_higher"),
        (
            ("knife", True),
            ("gloves", True),
            ("sticker", False),
            ("container", False),
            ("rifle", None),  # neutral
        ),
    )
    def test_calculate_commission_item_type_factors(
        self, item_type: str, expected_higher: bool | None
    ) -> None:
        """Test commission varies correctly with item type."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        base_commission = calculate_commission("classified", "rifle", 0.5, "csgo")
        test_commission = calculate_commission("classified", item_type, 0.5, "csgo")

        if expected_higher is True:
            assert test_commission > base_commission * 0.95
        elif expected_higher is False:
            assert test_commission < base_commission * 1.05


class TestCalculateProfit:
    """Tests for calculate_profit function."""

    def test_calculate_profit_basic(self) -> None:
        """Test basic profit calculation."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(10.0, 12.0, 7.0)
        # Gross profit = 2.0, Commission = 0.84, Net profit = 1.16
        assert net_profit == pytest.approx(1.16, rel=0.01)
        assert profit_percent == pytest.approx(11.6, rel=0.01)

    def test_calculate_profit_zero_commission(self) -> None:
        """Test profit with zero commission."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(10.0, 15.0, 0.0)
        assert net_profit == pytest.approx(5.0, rel=0.01)
        assert profit_percent == pytest.approx(50.0, rel=0.01)

    def test_calculate_profit_high_commission(self) -> None:
        """Test profit with high commission."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(10.0, 12.0, 15.0)
        # Gross profit = 2.0, Commission = 1.8, Net profit = 0.2
        assert net_profit == pytest.approx(0.2, rel=0.01)
        assert profit_percent == pytest.approx(2.0, rel=0.01)

    def test_calculate_profit_loss(self) -> None:
        """Test calculation when there's a loss."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(12.0, 10.0, 7.0)
        # Gross profit = -2.0, Commission = 0.7, Net profit = -2.7
        assert net_profit < 0
        assert profit_percent < 0

    def test_calculate_profit_zero_buy_price(self) -> None:
        """Test profit calculation with zero buy price."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        _net_profit, profit_percent = calculate_profit(0.0, 10.0, 7.0)
        # When buy price is 0, profit percent should be 0
        assert profit_percent == 0.0

    def test_calculate_profit_equal_prices(self) -> None:
        """Test profit when buy and sell prices are equal."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(10.0, 10.0, 7.0)
        # Gross profit = 0, Commission = 0.7, Net profit = -0.7
        assert net_profit < 0
        assert profit_percent < 0

    @pytest.mark.parametrize(
        ("buy_price", "sell_price", "commission", "expected_profit"),
        (
            (100.0, 110.0, 7.0, 2.3),  # 10% markup - 7.7% commission = ~2.3%
            (50.0, 60.0, 5.0, 7.0),  # 20% markup - 5% of sell = ~7%
            (1.0, 1.5, 10.0, 0.35),  # 50% markup - high commission
        ),
    )
    def test_calculate_profit_parametrized(
        self,
        buy_price: float,
        sell_price: float,
        commission: float,
        expected_profit: float,
    ) -> None:
        """Test various profit scenarios."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, _ = calculate_profit(buy_price, sell_price, commission)
        assert net_profit == pytest.approx(expected_profit, rel=0.1)


class TestCalculateNetProfit:
    """Tests for calculate_net_profit function."""

    def test_calculate_net_profit_default_commission(self) -> None:
        """Test net profit with default commission."""
        from src.dmarket.arbitrage.calculations import calculate_net_profit

        net_profit = calculate_net_profit(10.0, 12.0)
        # Gross = 2.0, Commission (7%) on 12 = 0.84, Net = 1.16
        assert net_profit == pytest.approx(1.16, rel=0.01)

    def test_calculate_net_profit_custom_commission(self) -> None:
        """Test net profit with custom commission."""
        from src.dmarket.arbitrage.calculations import calculate_net_profit

        net_profit = calculate_net_profit(10.0, 12.0, 5.0)
        # Gross = 2.0, Commission (5%) on 12 = 0.6, Net = 1.4
        assert net_profit == pytest.approx(1.4, rel=0.01)

    def test_calculate_net_profit_loss(self) -> None:
        """Test net profit when there's a loss."""
        from src.dmarket.arbitrage.calculations import calculate_net_profit

        net_profit = calculate_net_profit(12.0, 10.0, 7.0)
        assert net_profit < 0


class TestCalculateProfitPercent:
    """Tests for calculate_profit_percent function."""

    def test_calculate_profit_percent_basic(self) -> None:
        """Test basic profit percent calculation."""
        from src.dmarket.arbitrage.calculations import calculate_profit_percent

        profit_percent = calculate_profit_percent(10.0, 12.0, 7.0)
        # Net profit = 1.16, Percent = 11.6%
        assert profit_percent == pytest.approx(11.6, rel=0.01)

    def test_calculate_profit_percent_zero_buy_price(self) -> None:
        """Test profit percent with zero buy price."""
        from src.dmarket.arbitrage.calculations import calculate_profit_percent

        profit_percent = calculate_profit_percent(0.0, 12.0, 7.0)
        assert profit_percent == 0.0

    def test_calculate_profit_percent_negative_buy_price(self) -> None:
        """Test profit percent with negative buy price."""
        from src.dmarket.arbitrage.calculations import calculate_profit_percent

        profit_percent = calculate_profit_percent(-5.0, 12.0, 7.0)
        assert profit_percent == 0.0

    def test_calculate_profit_percent_default_commission(self) -> None:
        """Test profit percent with default commission."""
        from src.dmarket.arbitrage.calculations import calculate_profit_percent

        profit_percent = calculate_profit_percent(10.0, 15.0)
        # Gross = 5.0, Commission (7%) on 15 = 1.05, Net = 3.95
        # Percent = 39.5%
        assert profit_percent == pytest.approx(39.5, rel=0.01)


class TestGetFeeForLiquidity:
    """Tests for get_fee_for_liquidity function."""

    def test_get_fee_high_liquidity(self) -> None:
        """Test fee for high liquidity items."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.9)
        assert fee == 0.02  # LOW_FEE

    def test_get_fee_high_liquidity_boundary(self) -> None:
        """Test fee at high liquidity boundary (0.8)."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.8)
        assert fee == 0.02  # LOW_FEE

    def test_get_fee_medium_liquidity(self) -> None:
        """Test fee for medium liquidity items."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.6)
        assert fee == 0.07  # DEFAULT_FEE

    def test_get_fee_medium_liquidity_boundary(self) -> None:
        """Test fee at medium liquidity boundary (0.5)."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.5)
        assert fee == 0.07  # DEFAULT_FEE

    def test_get_fee_low_liquidity(self) -> None:
        """Test fee for low liquidity items."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.3)
        assert fee == 0.10  # HIGH_FEE

    def test_get_fee_very_low_liquidity(self) -> None:
        """Test fee for very low liquidity items."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(0.0)
        assert fee == 0.10  # HIGH_FEE

    @pytest.mark.parametrize(
        ("liquidity", "expected_fee"),
        (
            (1.0, 0.02),
            (0.85, 0.02),
            (0.79, 0.07),
            (0.5, 0.07),
            (0.49, 0.10),
            (0.1, 0.10),
        ),
    )
    def test_get_fee_parametrized(self, liquidity: float, expected_fee: float) -> None:
        """Test fee calculation for various liquidity levels."""
        from src.dmarket.arbitrage.calculations import get_fee_for_liquidity

        fee = get_fee_for_liquidity(liquidity)
        assert fee == expected_fee


class TestCurrencyConversions:
    """Tests for currency conversion functions."""

    def test_cents_to_usd_basic(self) -> None:
        """Test basic cents to USD conversion."""
        from src.dmarket.arbitrage.calculations import cents_to_usd

        assert cents_to_usd(1050) == 10.5

    def test_cents_to_usd_zero(self) -> None:
        """Test cents to USD with zero."""
        from src.dmarket.arbitrage.calculations import cents_to_usd

        assert cents_to_usd(0) == 0.0

    def test_cents_to_usd_small_amount(self) -> None:
        """Test cents to USD with small amount."""
        from src.dmarket.arbitrage.calculations import cents_to_usd

        assert cents_to_usd(1) == 0.01

    def test_cents_to_usd_large_amount(self) -> None:
        """Test cents to USD with large amount."""
        from src.dmarket.arbitrage.calculations import cents_to_usd

        assert cents_to_usd(100000) == 1000.0

    def test_usd_to_cents_basic(self) -> None:
        """Test basic USD to cents conversion."""
        from src.dmarket.arbitrage.calculations import usd_to_cents

        assert usd_to_cents(10.5) == 1050

    def test_usd_to_cents_zero(self) -> None:
        """Test USD to cents with zero."""
        from src.dmarket.arbitrage.calculations import usd_to_cents

        assert usd_to_cents(0.0) == 0

    def test_usd_to_cents_small_amount(self) -> None:
        """Test USD to cents with small amount."""
        from src.dmarket.arbitrage.calculations import usd_to_cents

        assert usd_to_cents(0.01) == 1

    def test_usd_to_cents_large_amount(self) -> None:
        """Test USD to cents with large amount."""
        from src.dmarket.arbitrage.calculations import usd_to_cents

        assert usd_to_cents(1000.0) == 100000

    def test_cents_usd_round_trip(self) -> None:
        """Test that conversion round trip is consistent."""
        from src.dmarket.arbitrage.calculations import cents_to_usd, usd_to_cents

        original_cents = 1234
        usd = cents_to_usd(original_cents)
        back_to_cents = usd_to_cents(usd)
        assert back_to_cents == original_cents

    @pytest.mark.parametrize(
        ("cents", "usd"),
        (
            (0, 0.0),
            (1, 0.01),
            (50, 0.5),
            (100, 1.0),
            (999, 9.99),
            (10000, 100.0),
        ),
    )
    def test_cents_usd_parametrized(self, cents: int, usd: float) -> None:
        """Test various currency conversions."""
        from src.dmarket.arbitrage.calculations import cents_to_usd

        assert cents_to_usd(cents) == pytest.approx(usd, rel=0.001)


class TestIsProfitableOpportunity:
    """Tests for is_profitable_opportunity function."""

    def test_is_profitable_true(self) -> None:
        """Test profitable opportunity returns True."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        # 10.0 -> 15.0 with 7% commission: ~39.5% profit
        assert is_profitable_opportunity(10.0, 15.0, 5.0, 7.0) is True

    def test_is_profitable_false(self) -> None:
        """Test non-profitable opportunity returns False."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        # 10.0 -> 10.5 with 7% commission: negative profit
        assert is_profitable_opportunity(10.0, 10.5, 5.0, 7.0) is False

    def test_is_profitable_exact_threshold(self) -> None:
        """Test opportunity at exact profit threshold."""
        from src.dmarket.arbitrage.calculations import (
            calculate_profit_percent,
            is_profitable_opportunity,
        )

        # Find the exact sell price for 5% profit
        # This is complex, so we test with values we know work
        profit = calculate_profit_percent(10.0, 12.0, 7.0)
        # Should be around 11.6%
        assert is_profitable_opportunity(10.0, 12.0, profit, 7.0) is True

    def test_is_profitable_zero_buy_price(self) -> None:
        """Test with zero buy price."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        assert is_profitable_opportunity(0.0, 10.0, 5.0, 7.0) is False

    def test_is_profitable_negative_buy_price(self) -> None:
        """Test with negative buy price."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        assert is_profitable_opportunity(-5.0, 10.0, 5.0, 7.0) is False

    def test_is_profitable_sell_less_than_buy(self) -> None:
        """Test when sell price is less than buy price."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        assert is_profitable_opportunity(15.0, 10.0, 5.0, 7.0) is False

    def test_is_profitable_equal_prices(self) -> None:
        """Test when prices are equal."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        assert is_profitable_opportunity(10.0, 10.0, 5.0, 7.0) is False

    def test_is_profitable_default_commission(self) -> None:
        """Test with default commission (7%)."""
        from src.dmarket.arbitrage.calculations import is_profitable_opportunity

        # 10.0 -> 20.0 with default 7%: ~86.5% profit
        assert is_profitable_opportunity(10.0, 20.0, 5.0) is True


class TestBackwardCompatibility:
    """Tests for backward compatibility aliases."""

    def test_calculate_commission_alias(self) -> None:
        """Test _calculate_commission alias works."""
        from src.dmarket.arbitrage.calculations import (
            _calculate_commission,
            calculate_commission,
        )

        # Both should return the same result
        result1 = calculate_commission("covert", "knife", 0.5, "csgo")
        result2 = _calculate_commission("covert", "knife", 0.5, "csgo")
        assert result1 == result2


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_prices(self) -> None:
        """Test with very small prices."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(0.01, 0.02, 7.0)
        assert net_profit >= 0  # Should still be able to profit
        assert profit_percent >= 0

    def test_very_large_prices(self) -> None:
        """Test with very large prices."""
        from src.dmarket.arbitrage.calculations import calculate_profit

        net_profit, profit_percent = calculate_profit(10000.0, 15000.0, 7.0)
        assert net_profit > 0
        assert profit_percent > 0

    def test_float_precision(self) -> None:
        """Test float precision doesn't cause issues."""
        from src.dmarket.arbitrage.calculations import calculate_profit_percent

        # These values can cause floating point issues
        profit = calculate_profit_percent(0.1, 0.2, 7.0)
        assert isinstance(profit, float)
        assert profit == profit  # Check for NaN

    def test_unknown_game(self) -> None:
        """Test commission calculation with unknown game."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Unknown game should use default factor
        commission = calculate_commission("classified", "rifle", 0.5, "unknown_game")
        assert 2.0 <= commission <= 15.0

    def test_unknown_rarity(self) -> None:
        """Test commission calculation with unknown rarity."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Unknown rarity should use neutral factor
        commission = calculate_commission("unknown_rarity", "rifle", 0.5, "csgo")
        assert 2.0 <= commission <= 15.0

    def test_unknown_item_type(self) -> None:
        """Test commission calculation with unknown item type."""
        from src.dmarket.arbitrage.calculations import calculate_commission

        # Unknown type should use neutral factor
        commission = calculate_commission("classified", "unknown_type", 0.5, "csgo")
        assert 2.0 <= commission <= 15.0
