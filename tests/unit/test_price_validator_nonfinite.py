"""Regression tests: price_validator must reject NaN / +-Inf (fail-closed).

NaN compares False against everything, so `x <= 0` / `margin < min_margin`
checks silently passed it; before the fix validate_arbitrage_profit(nan, 10)
returned nan and validate_slippage(nan, 10) returned None (= "OK").
"""

from __future__ import annotations

import math

import pytest

from src.risk.price_validator import (
    PriceValidationError,
    validate_arbitrage_profit,
    validate_slippage,
    validate_volatility,
)

NAN = float("nan")
INF = float("inf")


class TestArbitrageNonFinite:
    @pytest.mark.parametrize("bad", [NAN, INF, -INF])
    def test_buy_price_non_finite_rejected(self, bad):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_arbitrage_profit(bad, 10.0)

    @pytest.mark.parametrize("bad", [NAN, INF, -INF])
    def test_sell_price_non_finite_rejected(self, bad):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_arbitrage_profit(10.0, bad)

    @pytest.mark.parametrize("kwarg", ["fee_markup", "buy_fee_markup", "min_profit_margin",
                                        "lock_days", "penalty_per_day"])
    @pytest.mark.parametrize("bad", [NAN, INF])
    def test_parameters_non_finite_rejected(self, kwarg, bad):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_arbitrage_profit(10.0, 20.0, **{kwarg: bad})

    def test_non_numeric_rejected(self):
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit("abc", 20.0)  # type: ignore[arg-type]

    def test_valid_trade_still_passes(self):
        margin = validate_arbitrage_profit(10.0, 20.0, fee_markup=0.05, lock_days=0)
        assert math.isfinite(margin)
        assert margin == pytest.approx(0.9)

    def test_zero_buy_price_message_unchanged(self):
        with pytest.raises(PriceValidationError, match="Buy price must be > 0"):
            validate_arbitrage_profit(0.0, 10.0)


class TestSlippageNonFinite:
    @pytest.mark.parametrize("target,market", [
        (NAN, 10.0), (10.0, NAN), (INF, 10.0), (10.0, INF), (-INF, 10.0),
    ])
    def test_non_finite_rejected(self, target, market):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_slippage(target, market)

    def test_nan_max_slippage_rejected(self):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_slippage(10.0, 10.0, max_slippage_pct=NAN)

    def test_valid_slippage_still_passes(self):
        assert validate_slippage(10.0, 10.1) is None

    def test_existing_zero_messages_unchanged(self):
        with pytest.raises(PriceValidationError, match="Market price is invalid"):
            validate_slippage(10.0, 0.0)
        with pytest.raises(PriceValidationError, match="Target price is invalid"):
            validate_slippage(0.0, 10.0)


class TestVolatilityNonFinite:
    @pytest.mark.parametrize("bad", [NAN, INF, -INF])
    def test_non_finite_in_series_rejected(self, bad):
        with pytest.raises(PriceValidationError, match="not a finite number"):
            validate_volatility([10.0, bad, 10.0, 10.0])

    def test_short_series_still_returns_none(self):
        assert validate_volatility([10.0, 10.0]) is None
        assert validate_volatility([]) is None

    def test_flat_series_still_passes(self):
        assert validate_volatility([10.0, 10.0, 10.0, 10.0]) is None
