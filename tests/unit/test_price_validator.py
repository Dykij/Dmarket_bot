"""Tests for price_validator.py — strict price sanity checks."""

from __future__ import annotations

import math

import pytest

from src.risk.price_validator import (
    PriceValidationError,
    validate_arbitrage_profit,
    validate_price,
    validate_slippage,
    validate_volatility,
)


class TestValidatePrice:

    def test_valid_price(self):
        assert validate_price(10.5) == 10.5

    def test_string_price(self):
        assert validate_price("15.99") == 15.99

    def test_int_price(self):
        assert validate_price(10) == 10.0

    def test_nan_raises(self):
        with pytest.raises(PriceValidationError, match="NaN"):
            validate_price(float("nan"))

    def test_inf_raises(self):
        with pytest.raises(PriceValidationError, match="Inf"):
            validate_price(float("inf"))

    def test_negative_raises(self):
        with pytest.raises(PriceValidationError, match="negative"):
            validate_price(-1.0)

    def test_below_floor_raises(self):
        with pytest.raises(PriceValidationError, match="below floor"):
            validate_price(0.01)

    def test_above_ceiling_raises(self):
        with pytest.raises(PriceValidationError, match="above ceiling"):
            validate_price(100000.0)

    def test_invalid_string_raises(self):
        with pytest.raises(PriceValidationError, match="not a valid number"):
            validate_price("abc")

    def test_none_raises(self):
        with pytest.raises(PriceValidationError, match="not a valid number"):
            validate_price(None)

    def test_boundary_floor(self):
        assert validate_price(0.10) == 0.10

    def test_boundary_ceiling(self):
        assert validate_price(50000.0) == 50000.0

    def test_custom_label(self):
        with pytest.raises(PriceValidationError, match="sell_price"):
            validate_price(-1.0, label="sell_price")


class TestValidateArbitrageProfit:

    def test_profitable_trade(self):
        margin = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=15.0,
            fee_markup=0.05, buy_fee_markup=0.05,
            min_profit_margin=0.05, lock_days=0,
        )
        assert margin > 0

    def test_loss_trade_raises(self):
        with pytest.raises(PriceValidationError, match="LOSS"):
            validate_arbitrage_profit(
                buy_price=15.0, expected_sell_price=10.0,
            )

    def test_zero_buy_raises(self):
        with pytest.raises(PriceValidationError, match="must be > 0"):
            validate_arbitrage_profit(
                buy_price=0.0, expected_sell_price=10.0,
            )

    def test_insufficient_margin_raises(self):
        # Trade is profitable but margin too low after TVM penalty
        with pytest.raises(PriceValidationError, match="Insufficient"):
            validate_arbitrage_profit(
                buy_price=10.0, expected_sell_price=13.0,
                fee_markup=0.05, min_profit_margin=0.50,
                lock_days=7,
            )

    def test_tvm_penalty_applied(self):
        # Same trade, different lock periods — longer lock = lower margin
        margin_0 = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=15.0,
            lock_days=0, min_profit_margin=0.0,
        )
        margin_30 = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=15.0,
            lock_days=30, min_profit_margin=0.0,
        )
        assert margin_0 > margin_30

    def test_custom_fee_markup(self):
        margin = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=12.0,
            fee_markup=0.02, buy_fee_markup=0.02,
            min_profit_margin=0.0, lock_days=0,
        )
        assert margin > 0


class TestValidateSlippage:

    def test_no_slippage(self):
        validate_slippage(10.0, 10.0)  # Should not raise

    def test_within_tolerance(self):
        validate_slippage(10.0, 10.01, max_slippage_pct=0.02)

    def test_exceeds_tolerance_raises(self):
        with pytest.raises(PriceValidationError, match="Slippage Exceeded"):
            validate_slippage(10.0, 10.5, max_slippage_pct=0.02)

    def test_zero_market_price_raises(self):
        with pytest.raises(PriceValidationError, match="invalid"):
            validate_slippage(10.0, 0.0)

    def test_zero_target_price_raises(self):
        with pytest.raises(PriceValidationError, match="invalid"):
            validate_slippage(0.0, 10.0)


class TestValidateVolatility:

    def test_stable_prices_pass(self):
        validate_volatility([10.0, 10.1, 10.0, 10.1, 10.0])

    def test_volatile_prices_raises(self):
        with pytest.raises(PriceValidationError, match="High Volatility"):
            validate_volatility([10.0, 15.0, 5.0, 20.0, 3.0])

    def test_too_few_prices_passes(self):
        validate_volatility([10.0, 10.1])  # < 3 prices, no check

    def test_empty_list_passes(self):
        validate_volatility([])

    def test_two_prices_passes(self):
        validate_volatility([10.0, 10.1])
