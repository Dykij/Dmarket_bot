"""Unit tests for FairPriceCalculator.

Covers: calculate (median, outlier removal, margin tiers, confidence,
min-margin enforcement), FairPriceResult.to_dict, edge cases.
"""

from __future__ import annotations

import pytest

from src.api.fair_price_calculator import FairPriceCalculator, FairPriceResult


@pytest.fixture()
def calc():
    return FairPriceCalculator()


# =====================================================================
# FairPriceResult
# =====================================================================


class TestFairPriceResult:
    """Tests for the result dataclass."""

    def test_to_dict_rounds_prices(self):
        r = FairPriceResult(
            title="Item",
            fair_price=12.345,
            sell_price=13.000,
            sources={"a": 12.345},
            source_count=1,
            outlier_removed=None,
            margin_pct=5.0,
            volume_total=100,
            confidence="low",
        )
        d = r.to_dict()
        assert d["fair_price"] == 12.35
        assert d["sell_price"] == 13.0
        assert d["sources"]["a"] == 12.35

    def test_to_dict_all_fields(self):
        r = FairPriceResult(
            title="AK",
            fair_price=10.0,
            sell_price=11.0,
            sources={"s1": 10.0, "s2": 11.0},
            source_count=2,
            outlier_removed="s3",
            margin_pct=10.0,
            volume_total=50,
            confidence="medium",
        )
        d = r.to_dict()
        assert d["title"] == "AK"
        assert d["source_count"] == 2
        assert d["outlier_removed"] == "s3"
        assert d["confidence"] == "medium"


# =====================================================================
# calculate — Basic Cases
# =====================================================================


class TestCalculateBasic:
    """Tests for basic price calculation."""

    def test_single_source(self, calc: FairPriceCalculator):
        """Single source returns that price as fair_price."""
        r = calc.calculate("Item", prices={"marketcsgo": 30.0})
        assert r.fair_price == pytest.approx(30.0)
        assert r.source_count == 1
        assert r.confidence == "low"

    def test_two_sources_median(self, calc: FairPriceCalculator):
        """Two sources: median = average of two values."""
        r = calc.calculate("Item", prices={"a": 10.0, "b": 20.0})
        assert r.fair_price == pytest.approx(15.0)
        assert r.source_count == 2
        assert r.confidence == "medium"

    def test_three_sources_median(self, calc: FairPriceCalculator):
        """Three sources: median is middle value."""
        r = calc.calculate(
            "Item", prices={"a": 10.0, "b": 30.0, "c": 20.0}
        )
        assert r.fair_price == pytest.approx(20.0)
        assert r.source_count == 3
        assert r.confidence == "high"

    def test_four_sources_with_outlier_removal(self, calc: FairPriceCalculator):
        """Four sources: outlier removed if >2x median of others."""
        r = calc.calculate(
            "Item",
            prices={"a": 10.0, "b": 11.0, "c": 12.0, "d": 100.0},
        )
        # d=100 is >2x median of others (~11), so removed
        assert r.outlier_removed == "d"
        assert r.fair_price == pytest.approx(11.0)

    def test_five_sources_low_outlier(self, calc: FairPriceCalculator):
        """Low outlier removed if <0.3x median of others."""
        r = calc.calculate(
            "Item",
            prices={"a": 1.0, "b": 10.0, "c": 11.0, "d": 12.0, "e": 13.0},
        )
        # a=1 is <0.3x median of others (~11.5), so removed
        assert r.outlier_removed == "a"


# =====================================================================
# calculate — Margin Tiers
# =====================================================================


class TestMarginTiers:
    """Tests for volume-based margin calculation."""

    def test_very_liquid_3pct(self, calc: FairPriceCalculator):
        """Volume >= 100 → 3% margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 150},
        )
        assert r.margin_pct == 3.0
        assert r.sell_price == pytest.approx(103.0)

    def test_liquid_5pct(self, calc: FairPriceCalculator):
        """Volume >= 50 → 5% margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 75},
        )
        assert r.margin_pct == 5.0

    def test_medium_7pct(self, calc: FairPriceCalculator):
        """Volume >= 20 → 7% margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 25},
        )
        assert r.margin_pct == 7.0

    def test_low_liquidity_10pct(self, calc: FairPriceCalculator):
        """Volume >= 5 → 10% margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 7},
        )
        assert r.margin_pct == 10.0

    def test_very_low_15pct(self, calc: FairPriceCalculator):
        """Volume < 5 → 15% margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 2},
        )
        assert r.margin_pct == 15.0

    def test_no_volumes_defaults_15pct(self, calc: FairPriceCalculator):
        """No volumes provided → 15% margin."""
        r = calc.calculate("Item", prices={"a": 100.0})
        assert r.margin_pct == 15.0


# =====================================================================
# calculate — Minimum Margin Enforcement
# =====================================================================


class TestMinMarginEnforcement:
    """Tests for dmarket_buy_price min-margin logic."""

    def test_sell_price_at_least_3pct_above_buy(self, calc: FairPriceCalculator):
        """Sell price >= buy_price * 1.03."""
        r = calc.calculate(
            "Item",
            prices={"a": 10.0},
            volumes={"a": 200},  # 3% margin → sell = 10.3
            dmarket_buy_price=20.0,  # min_sell = 20.6
        )
        assert r.sell_price == pytest.approx(20.6)

    def test_sell_price_not_forced_when_higher(self, calc: FairPriceCalculator):
        """Sell price stays when already above min margin."""
        r = calc.calculate(
            "Item",
            prices={"a": 100.0},
            volumes={"a": 200},  # 3% margin → sell = 103
            dmarket_buy_price=50.0,  # min_sell = 51.5
        )
        assert r.sell_price == pytest.approx(103.0)

    def test_no_buy_price_no_enforcement(self, calc: FairPriceCalculator):
        """Zero buy price → no min margin enforcement."""
        r = calc.calculate(
            "Item",
            prices={"a": 10.0},
            volumes={"a": 200},
            dmarket_buy_price=0.0,
        )
        assert r.sell_price == pytest.approx(10.3)


# =====================================================================
# calculate — Confidence
# =====================================================================


class TestConfidence:
    """Tests for confidence level assignment."""

    def test_high_confidence_3plus_sources(self, calc: FairPriceCalculator):
        r = calc.calculate("I", prices={"a": 10, "b": 11, "c": 12})
        assert r.confidence == "high"

    def test_medium_confidence_2_sources(self, calc: FairPriceCalculator):
        r = calc.calculate("I", prices={"a": 10, "b": 11})
        assert r.confidence == "medium"

    def test_low_confidence_1_source(self, calc: FairPriceCalculator):
        r = calc.calculate("I", prices={"a": 10})
        assert r.confidence == "low"


# =====================================================================
# calculate — Edge Cases
# =====================================================================


class TestEdgeCases:
    """Edge cases: empty input, zero prices, malformed data."""

    def test_all_zero_prices(self, calc: FairPriceCalculator):
        """All zero prices → fair_price=0, confidence=none."""
        r = calc.calculate("Item", prices={"a": 0, "b": 0})
        assert r.fair_price == 0.0
        assert r.sell_price == 0.0
        assert r.source_count == 0
        assert r.confidence == "none"

    def test_empty_prices_dict(self, calc: FairPriceCalculator):
        """Empty prices → zero result."""
        r = calc.calculate("Item", prices={})
        assert r.fair_price == 0.0
        assert r.source_count == 0
        assert r.confidence == "none"

    def test_negative_prices_filtered(self, calc: FairPriceCalculator):
        """Negative prices filtered out as invalid."""
        r = calc.calculate("Item", prices={"a": -5.0, "b": 10.0})
        assert r.source_count == 1
        assert r.fair_price == pytest.approx(10.0)

    def test_mixed_zero_and_valid(self, calc: FairPriceCalculator):
        """Zero prices filtered, valid prices used."""
        r = calc.calculate(
            "Item", prices={"a": 0, "b": 15.0, "c": 20.0}
        )
        assert r.source_count == 2
        assert r.fair_price == pytest.approx(17.5)

    def test_very_small_prices(self, calc: FairPriceCalculator):
        """Handles sub-cent prices."""
        r = calc.calculate("Item", prices={"a": 0.01, "b": 0.02})
        assert r.fair_price == pytest.approx(0.015)

    def test_very_large_prices(self, calc: FairPriceCalculator):
        """Handles high-value items."""
        r = calc.calculate("Item", prices={"a": 50000.0, "b": 55000.0})
        assert r.fair_price == pytest.approx(52500.0)

    def test_steam_source_no_double_adjustment(self, calc: FairPriceCalculator):
        """STEAM_ADJUSTMENT is 1.0 (no double adjustment)."""
        assert calc.STEAM_ADJUSTMENT == pytest.approx(1.0)
        r = calc.calculate("Item", prices={"steam": 100.0})
        assert r.fair_price == pytest.approx(100.0)

    def test_volume_total_across_sources(self, calc: FairPriceCalculator):
        """Volume summed from all valid sources."""
        r = calc.calculate(
            "Item",
            prices={"a": 10.0, "b": 20.0},
            volumes={"a": 100, "b": 50, "c": 999},
        )
        # Only a and b are valid price sources, but volume from all sources
        # in valid_prices dict (c not in valid, so only a+b)
        assert r.volume_total == 150

    def test_outlier_not_removed_when_close(self, calc: FairPriceCalculator):
        """Outlier not removed if within 2x/0.3x thresholds."""
        r = calc.calculate(
            "Item",
            prices={"a": 10.0, "b": 11.0, "c": 18.0},
        )
        # 18 is not >2x median(10,11)=10.5 → not removed
        assert r.outlier_removed is None
