"""Unit tests for float_value_arbitrage.py v15.4 features.

Tests: ultra-high float, float rank premiums, trade-up fodder detection,
and trade-up output float estimation.
"""

from __future__ import annotations

import pytest

from src.dmarket.float_value_arbitrage import FloatValueArbitrage, FloatPremiumResult


# =====================================================================
# Float Tier Premiums
# =====================================================================


class TestFloatTiers:
    """Tests for float-based premium tiers."""

    @pytest.mark.parametrize(
        ("float_val", "expected_mult", "expected_tier"),
        [
            (0.00005, 2.50, "FN-0000"),
            (0.0005, 1.80, "FN-000"),
            (0.003, 1.40, "FN-00"),
            (0.008, 1.25, "FN-0"),
            (0.02, 1.20, "FN-1"),
            (0.05, 1.08, "FN"),
            (0.075, 1.08, "MW-0"),
            (0.09, 1.05, "MW"),
            (0.12, 1.03, "FT-high"),
            (0.16, 1.15, "FT-0"),
            (0.385, 1.08, "WW-0"),
            (0.455, 1.10, "BS-0"),
            (0.96, 1.30, "BS-dirty"),
            (0.9995, 2.00, "BS-max"),
        ],
    )
    def test_float_tier_classification(
        self, float_val: float, expected_mult: float, expected_tier: str
    ) -> None:
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", float_val, 10.0)
        assert result.premium_multiplier == pytest.approx(expected_mult)
        assert result.tier == expected_tier

    def test_ultra_high_float(self) -> None:
        """0.9995 = 2.0x BS-max tier."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AWP | Safari Mesh", 0.9995, 5.0)
        assert result.premium_multiplier == pytest.approx(2.00)
        assert result.tier == "BS-max"

    def test_normal_float_no_premium(self) -> None:
        """Float 0.3 (mid-range, not round) should have no special tier."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", 0.3, 10.0)
        assert result.premium_multiplier == pytest.approx(1.0)
        assert result.tier == "normal"


# =====================================================================
# Round Float Premium
# =====================================================================


class TestRoundFloat:
    """Tests for collector round-float bonuses."""

    @pytest.mark.parametrize("round_val", [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875])
    def test_round_float_bonus(self, round_val: float) -> None:
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", round_val, 10.0)
        assert result.premium_multiplier >= 1.15

    def test_round_float_overrides_normal_tier(self) -> None:
        """0.5 is in normal tier but round float should boost to 1.15."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", 0.5, 10.0)
        assert result.premium_multiplier == pytest.approx(1.15)
        assert "round" in result.tier


# =====================================================================
# Float Rank Premium (v15.4)
# =====================================================================


class TestFloatRankPremium:
    """Tests for CSFloat rank-based premiums."""

    @pytest.mark.parametrize(
        ("rank", "expected_mult"),
        [
            (1, 3.00),
            (2, 2.20),   # _get_rank_multiplier: rank<=3 → 2.20
            (3, 2.20),
            (4, 1.80),   # rank<=5 → 1.80
            (5, 1.80),
            (7, 1.50),   # rank<=10 → 1.50
            (10, 1.50),
            (15, 1.30),  # rank<=20 → 1.30
            (20, 1.30),
            (30, 1.15),  # rank<=50 → 1.15
            (50, 1.15),
            (75, 1.05),  # rank<=100 → 1.05
            (100, 1.05),
        ],
    )
    def test_float_rank_multipliers(self, rank: int, expected_mult: float) -> None:
        # Use non-round float 0.3 to avoid round float bonus interfering
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", 0.3, 10.0, float_rank=rank)
        assert result.premium_multiplier == pytest.approx(expected_mult)
        assert f"rank-#{rank}" in result.tier

    def test_float_rank_1(self) -> None:
        """Rank #1 = 3.0x."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AWP | Dragon Lore", 0.0, 1000.0, float_rank=1)
        assert result.premium_multiplier == pytest.approx(3.00)

    def test_float_rank_3(self) -> None:
        """Rank #3 = 2.2x."""
        fva = FloatValueArbitrage()
        # Use non-round float to avoid interference
        result = fva.calculate_float_premium("AWP | Dragon Lore", 0.3, 1000.0, float_rank=3)
        assert result.premium_multiplier == pytest.approx(2.20)

    def test_float_rank_10(self) -> None:
        """Rank #10 = 1.5x."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AWP | Dragon Lore", 0.3, 1000.0, float_rank=10)
        assert result.premium_multiplier == pytest.approx(1.50)

    def test_float_rank_100(self) -> None:
        """Rank #100 = 1.05x."""
        fva = FloatValueArbitrage()
        # Use non-round float to avoid round float bonus overriding rank
        result = fva.calculate_float_premium("AK-47 | Redline", 0.3, 10.0, float_rank=100)
        assert result.premium_multiplier == pytest.approx(1.05)

    def test_float_rank_0_unknown(self) -> None:
        """Rank 0 = no rank bonus (use float tier instead)."""
        fva = FloatValueArbitrage()
        result = fva.calculate_float_premium("AK-47 | Redline", 0.3, 10.0, float_rank=0)
        assert result.premium_multiplier == pytest.approx(1.0)  # normal tier
        assert "rank" not in result.tier

    def test_rank_overrides_lower_tier(self) -> None:
        """Rank premium should override a lower float tier."""
        fva = FloatValueArbitrage()
        # Float 0.3 → normal (1.0x), but rank #1 → 3.0x
        result = fva.calculate_float_premium("AK-47 | Redline", 0.3, 10.0, float_rank=1)
        assert result.premium_multiplier == pytest.approx(3.00)

    def test_higher_tier_not_overridden_by_lower_rank(self) -> None:
        """If float tier is higher than rank tier, keep the higher one."""
        fva = FloatValueArbitrage()
        # Float 0.00005 → FN-0000 (2.5x), rank #100 → 1.05x
        result = fva.calculate_float_premium("AWP | Dragon Lore", 0.00005, 1000.0, float_rank=100)
        assert result.premium_multiplier == pytest.approx(2.50)


# =====================================================================
# Trade-Up Fodder Detection
# =====================================================================


class TestTradeUpFodder:
    """Tests for trade-up fodder detection."""

    def test_is_trade_up_fodder_fn(self) -> None:
        """0.005 in Factory New range = True."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.005, "Factory New") is True

    def test_is_trade_up_fodder_mw(self) -> None:
        """0.075 in Minimal Wear range = True."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.075, "Minimal Wear") is True

    def test_is_trade_up_fodder_ft(self) -> None:
        """0.16 in Field-Tested range = True."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.16, "Field-Tested") is True

    def test_is_trade_up_fodder_ww(self) -> None:
        """0.385 in Well-Worn range = True."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.385, "Well-Worn") is True

    def test_is_trade_up_fodder_bs(self) -> None:
        """0.455 in Battle-Scarred range = True."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.455, "Battle-Scarred") is True

    def test_is_trade_up_fodder_normal(self) -> None:
        """0.5 not in any trade-up range = False."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.5, "Battle-Scarred") is False

    def test_is_trade_up_fodder_no_range(self) -> None:
        """No wear range specified = False."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.005) is False

    def test_is_trade_up_fodder_unknown_range(self) -> None:
        """Unknown wear range = False."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.005, "Unknown") is False

    def test_fn_boundary_exclusive(self) -> None:
        """0.01 is NOT in FN range (exclusive upper bound)."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.01, "Factory New") is False

    def test_fn_boundary_inclusive(self) -> None:
        """0.00 is in FN range (inclusive lower bound)."""
        assert FloatValueArbitrage.is_trade_up_fodder(0.0, "Factory New") is True


# =====================================================================
# Trade-Up Output Float Estimation
# =====================================================================


class TestTradeUpOutput:
    """Tests for trade-up contract float estimation."""

    def test_estimate_trade_up_output(self) -> None:
        """Verify the formula: (max - min) * (target_max - target_min) + target_min."""
        input_floats = [0.01, 0.02, 0.03]
        target_min = 0.00
        target_max = 0.07
        result = FloatValueArbitrage.estimate_trade_up_output_float(
            input_floats, target_min, target_max
        )
        expected = (0.03 - 0.01) * (0.07 - 0.00) + 0.00
        assert result == pytest.approx(expected)

    def test_estimate_trade_up_output_single_input(self) -> None:
        """Single input: max == min, output = target_min."""
        result = FloatValueArbitrage.estimate_trade_up_output_float([0.05], 0.0, 0.07)
        assert result == pytest.approx(0.0)

    def test_estimate_trade_up_output_empty(self) -> None:
        """Empty input returns 0."""
        assert FloatValueArbitrage.estimate_trade_up_output_float([], 0.0, 0.07) == pytest.approx(0.0)

    def test_estimate_trade_up_output_range(self) -> None:
        """Verify with a wider target range."""
        input_floats = [0.10, 0.20, 0.30, 0.40, 0.50]
        target_min = 0.15
        target_max = 0.38
        result = FloatValueArbitrage.estimate_trade_up_output_float(
            input_floats, target_min, target_max
        )
        expected = (0.50 - 0.10) * (0.38 - 0.15) + 0.15
        assert result == pytest.approx(expected)
