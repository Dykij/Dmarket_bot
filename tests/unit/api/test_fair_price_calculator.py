"""Unit tests for FairPriceCalculator (src/api/fair_price_calculator.py)."""

from __future__ import annotations

import pytest

from src.api.fair_price_calculator import FairPriceCalculator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def calc():
    return FairPriceCalculator()


# ---------------------------------------------------------------------------
# Tests — calculate median
# ---------------------------------------------------------------------------

class TestCalculateMedian:
    """Tests for FairPriceCalculator.calculate median logic."""

    def test_three_sources(self, calc):
        """3 prices → median of middle value."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 12.0, "c": 14.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.fair_price == 12.0
        assert result.source_count == 3
        assert result.confidence == "high"

    def test_two_sources(self, calc):
        """2 prices → median = average of two."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 14.0},
            volumes={"a": 50, "b": 50},
        )
        assert result.fair_price == 12.0
        assert result.confidence == "medium"

    def test_single_source(self, calc):
        """1 price → that price is the median."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0},
            volumes={"a": 10},
        )
        assert result.fair_price == 10.0
        assert result.confidence == "low"


# ---------------------------------------------------------------------------
# Tests — outlier removal
# ---------------------------------------------------------------------------

class TestOutlierRemoval:
    """Tests for outlier detection and removal."""

    def test_high_outlier_removed(self, calc):
        """prices [10, 12, 100] → min 'a' (10) is outlier.

        Algorithm checks min first: others={b:12,c:100}, median=56.
        10 < 56*0.3=16.8? Yes → remove 'a'.
        Remaining median of [12, 100] = 56.
        """
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 12.0, "c": 100.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.outlier_removed == "a"
        assert result.fair_price == 56.0  # median of [12, 100]

    def test_low_outlier_removed(self, calc):
        """prices [0.5, 12, 14] → 0.5 is outlier.

        Algorithm: checks min (0.5) vs median of others [12,14]=13
        → 0.5 < 13*0.3=3.9? Yes → remove 'a'.
        """
        result = calc.calculate(
            title="Test Item",
            prices={"a": 0.5, "b": 12.0, "c": 14.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.outlier_removed == "a"
        assert result.fair_price == 13.0  # median of [12, 14]

    def test_no_outlier_close_prices(self, calc):
        """prices [10, 11, 12] → no outlier removed."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 11.0, "c": 12.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.outlier_removed is None
        assert result.fair_price == 11.0


# ---------------------------------------------------------------------------
# Tests — insufficient sources
# ---------------------------------------------------------------------------

class TestInsufficientSources:
    def test_no_valid_prices(self, calc):
        """All zero prices → has_enough_sources=False, fair_price=0."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 0.0, "b": 0.0},
        )
        assert result.fair_price == 0.0
        assert result.source_count == 0
        assert result.confidence == "none"

    def test_empty_prices(self, calc):
        """Empty prices dict → fair_price=0."""
        result = calc.calculate(title="Test Item", prices={})
        assert result.fair_price == 0.0
        assert result.source_count == 0


# ---------------------------------------------------------------------------
# Tests — all same price
# ---------------------------------------------------------------------------

class TestAllSamePrice:
    def test_all_equal(self, calc):
        """All sources agree on same price → no outlier, that price."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 15.0, "b": 15.0, "c": 15.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.fair_price == 15.0
        assert result.outlier_removed is None


# ---------------------------------------------------------------------------
# Tests — zero prices filtered
# ---------------------------------------------------------------------------

class TestZeroPricesFiltered:
    def test_zeros_excluded(self, calc):
        """Zero prices are excluded from calculation."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 0.0, "c": 14.0},
            volumes={"a": 100, "b": 100, "c": 100},
        )
        assert result.source_count == 2
        assert result.fair_price == 12.0

    def test_all_zeros(self, calc):
        """All zeros → fair_price=0, confidence=none."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 0.0, "b": 0.0},
        )
        assert result.fair_price == 0.0
        assert result.confidence == "none"


# ---------------------------------------------------------------------------
# Tests — sell price & margin
# ---------------------------------------------------------------------------

class TestSellPrice:
    def test_margin_tier_very_liquid(self, calc):
        """Volume ≥ 100 → 3% margin."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 12.0, "c": 14.0},
            volumes={"a": 50, "b": 30, "c": 30},
        )
        assert result.margin_pct == 3.0
        assert result.sell_price == pytest.approx(12.0 * 1.03)

    def test_margin_tier_low_liquidity(self, calc):
        """Volume < 5 → 15% margin."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0, "b": 12.0, "c": 14.0},
            volumes={"a": 1, "b": 1, "c": 1},
        )
        assert result.margin_pct == 15.0

    def test_min_margin_over_buy_price(self, calc):
        """Sell price ≥ buy_price * 1.03."""
        result = calc.calculate(
            title="Test Item",
            prices={"a": 10.0},
            volumes={"a": 0},
            dmarket_buy_price=20.0,
        )
        assert result.sell_price >= 20.0 * 1.03


# ---------------------------------------------------------------------------
# Tests — to_dict
# ---------------------------------------------------------------------------

class TestToDict:
    def test_rounding(self, calc):
        """to_dict rounds prices to 2 decimals."""
        result = calc.calculate(
            title="Test",
            prices={"a": 10.123, "b": 12.456},
            volumes={"a": 10, "b": 10},
        )
        d = result.to_dict()
        assert d["fair_price"] == round(result.fair_price, 2)
        assert d["sell_price"] == round(result.sell_price, 2)
