"""Bottleneck and edge-case tests for DMarket Bot core subsystems.

Covers:
  1. Microstructure function edge cases (zero, negative, empty inputs)
  2. Validator boundary conditions
  3. CS2Cap model invariants
  4. Rate limit / quota simulation
  5. Database stress pattern (rapid writes)
"""

from __future__ import annotations

import dataclasses
import math
import sqlite3
import time

import pytest

from src.analysis.microstructure import (
    composite_buy_score,
    compute_vpin,
    compute_vwap,
    kyle_lambda,
    queue_imbalance,
    roll_effective_spread,
    simple_obi,
    smart_reprice_signal,
    stoikov_micro_price,
)
from src.api.cs2cap_oracle import (
    BATCH_MAX_ITEMS,
    BidsSnapshot,
    CrossMarketData,
    PriceSnapshot,
)
from src.risk.price_validator import (
    PriceValidationError,
    validate_arbitrage_profit,
    validate_volatility,
)
from src.db.price_history import price_db


# ══════════════════════════════════════════════════════════════════════
# 1. MICROSTRUCTURE EDGE CASES
# ══════════════════════════════════════════════════════════════════════


class TestStoikovMicroPriceEdge:
    """Edge cases for stoikov_micro_price (zero/negative spread)."""

    def test_zero_spread_returns_mid(self):
        result = stoikov_micro_price(mid_price=10.0, spread=0.0, obi=0.8)
        assert result == 10.0

    def test_negative_spread_returns_mid(self):
        result = stoikov_micro_price(mid_price=10.0, spread=-0.5, obi=0.8)
        assert result == 10.0

    def test_zero_mid_price_zero_spread(self):
        result = stoikov_micro_price(mid_price=0.0, spread=0.0, obi=1.0)
        assert result == 0.0

    def test_max_buyer_pressure(self):
        result = stoikov_micro_price(mid_price=100.0, spread=10.0, obi=1.0)
        assert result == pytest.approx(100.0 + 0.35 * 10.0 * 1.0)

    def test_max_seller_pressure(self):
        result = stoikov_micro_price(mid_price=100.0, spread=10.0, obi=-1.0)
        assert result == pytest.approx(100.0 + 0.35 * 10.0 * (-1.0))


class TestSimpleOBIEdge:
    """Edge cases for simple_obi (zero counts, zero prices)."""

    def test_both_counts_zero_returns_zero(self):
        result = simple_obi(best_bid=10.0, best_ask=10.0, bid_count=0, ask_count=0)
        assert result == 0.0

    def test_both_prices_zero_or_none(self):
        result = simple_obi(best_bid=0.0, best_ask=0.0, bid_count=5, ask_count=5)
        assert result == 0.0

    def test_bid_count_zero_ask_count_positive(self):
        result = simple_obi(best_bid=10.0, best_ask=10.0, bid_count=0, ask_count=5)
        assert result == -1.0

    def test_ask_count_zero_bid_count_positive(self):
        result = simple_obi(best_bid=10.0, best_ask=10.0, bid_count=5, ask_count=0)
        assert result == 1.0

    def test_best_bid_none_uses_fallback(self):
        result = simple_obi(best_bid=0.0, best_ask=10.0, bid_count=3, ask_count=3)
        assert -1.0 <= result <= 1.0


class TestQueueImbalanceEdge:
    """Edge cases for queue_imbalance (zero ask_count)."""

    def test_zero_ask_count_returns_none(self):
        result = queue_imbalance(bid_count=10, ask_count=0)
        assert result is None

    def test_zero_bid_count_ok(self):
        result = queue_imbalance(bid_count=0, ask_count=10)
        assert result == 0.0

    def test_both_zero_returns_none(self):
        result = queue_imbalance(bid_count=0, ask_count=0)
        assert result is None

    def test_large_numbers(self):
        result = queue_imbalance(bid_count=10000, ask_count=1)
        assert result == 10000.0

    def test_fractional_ratio(self):
        result = queue_imbalance(bid_count=1, ask_count=3)
        assert result == pytest.approx(0.3333, abs=0.001)


class TestComputeVWAPEdge:
    """Edge cases for compute_vwap (empty sales, zero weights)."""

    def test_empty_sales_list_returns_zeros(self):
        vwap, total, std = compute_vwap([])
        assert vwap == 0.0
        assert total == 0
        assert std == 0.0

    def test_single_sale(self):
        sales = [{"price": 15.0, "amount": 2}]
        vwap, total, std = compute_vwap(sales)
        assert vwap == 15.0
        assert total == 2
        assert std == 0.0

    def test_all_zero_amounts(self):
        sales = [{"price": 10.0, "amount": 0}, {"price": 20.0, "amount": 0}]
        vwap, total, std = compute_vwap(sales)
        assert vwap == 0.0
        assert total == 0
        assert std == 0.0

    def test_zero_prices(self):
        sales = [{"price": 0.0, "amount": 5}, {"price": 0.0, "amount": 5}]
        vwap, total, std = compute_vwap(sales)
        assert vwap == 0.0
        assert total == 10
        assert std == 0.0


class TestComputeVPINEdge:
    """Edge cases for compute_vpin (insufficient data)."""

    def test_empty_sales_returns_none(self):
        result = compute_vpin([])
        assert result is None

    def test_insufficient_sales_for_buckets(self):
        sales = [{"price": 10.0, "amount": 1}] * 5
        result = compute_vpin(sales, n_buckets=8)
        assert result is None

    def test_zero_volume_returns_none(self):
        sales = [{"price": 10.0, "amount": 0}] * 20
        result = compute_vpin(sales, n_buckets=8)
        assert result is None

    def test_minimum_viable_data(self):
        sales = [{"price": 10.0, "amount": 10}] * 16
        result = compute_vpin(sales, n_buckets=8)
        assert result is not None
        assert 0.0 <= result <= 1.0


class TestKyleLambdaEdge:
    """Edge cases for kyle_lambda (empty sales, zero quantities)."""

    def test_empty_sales_returns_none(self):
        result = kyle_lambda([])
        assert result is None

    def test_two_sales_returns_none(self):
        sales = [{"price": 10.0}, {"price": 12.0}]
        result = kyle_lambda(sales)
        assert result is None

    def test_all_zero_prices(self):
        sales = [{"price": 0.0}, {"price": 0.0}, {"price": 0.0}, {"price": 0.0}]
        result = kyle_lambda(sales)
        assert result is None

    def test_zero_quantities_skipped(self):
        sales = [{"price": 10.0, "amount": 0}, {"price": 12.0, "amount": 0},
                 {"price": 9.0, "amount": 0}, {"price": 11.0, "amount": 0}]
        result = kyle_lambda(sales)
        assert result is None


class TestRollEffectiveSpreadEdge:
    """Edge cases for roll_effective_spread (few prices)."""

    def test_two_prices_returns_none(self):
        result = roll_effective_spread([10.0, 10.1])
        assert result is None

    def test_three_prices_returns_none(self):
        result = roll_effective_spread([10.0, 10.1, 10.2])
        assert result is None

    def test_empty_list_returns_none(self):
        result = roll_effective_spread([])
        assert result is None

    def test_constant_prices(self):
        result = roll_effective_spread([10.0, 10.0, 10.0, 10.0])
        assert result is None  # zero covariance -> no spread

    def test_trending_up(self):
        result = roll_effective_spread([10.0, 10.1, 10.2, 10.3, 10.4])
        assert result is None  # positive covariance -> no spread


class TestCompositeBuyScoreEdge:
    """Edge cases for composite_buy_score (all-zero inputs)."""

    def test_all_zero_inputs(self):
        score, comps = composite_buy_score(
            best_ask=0.0, best_bid=0.0,
            ask_count=0, bid_count=0,
            obi=0.0, ofi=0,
            cvd=0.0, vpin_val=0.0,
            vwap_discount=0.0, adverse_pass=False, vol_regime="low",
        )
        assert isinstance(score, float)
        assert isinstance(comps, dict)
        for k, v in comps.items():
            assert 0.0 <= v <= 1.0, f"{k}={v} out of [0,1]"

    def test_best_ask_zero_does_not_crash(self):
        score, _ = composite_buy_score(
            best_ask=0.0, best_bid=5.0,
            ask_count=10, bid_count=10,
            obi=0.5, ofi=5,
            cvd=3.0, vpin_val=0.2,
            vwap_discount=0.05, adverse_pass=True, vol_regime="medium",
            kyle_lam=0.02,
        )
        assert isinstance(score, float)

    def test_kyle_lam_none(self):
        score, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.05,
            ask_count=10, bid_count=10,
            obi=0.0, ofi=0,
            cvd=0.0, vpin_val=0.5,
            vwap_discount=0.0, adverse_pass=True, vol_regime="medium",
            kyle_lam=None,
        )
        assert comps["kyle"] == 0.5
        assert isinstance(score, float)

    def test_kyle_lam_zero(self):
        score, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.05,
            ask_count=10, bid_count=10,
            obi=0.0, ofi=0,
            cvd=0.0, vpin_val=0.5,
            vwap_discount=0.0, adverse_pass=True, vol_regime="medium",
            kyle_lam=0.0,
        )
        assert comps["kyle"] == 0.5  # kyle_lam=0 is falsy, falls to 0.5
        assert isinstance(score, float)

    def test_unknown_vol_regime(self):
        score, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.05,
            ask_count=10, bid_count=10,
            obi=0.0, ofi=0,
            cvd=0.0, vpin_val=0.5,
            vwap_discount=0.0, adverse_pass=True, vol_regime="unknown",
            kyle_lam=0.03,
        )
        assert comps["vol_regime"] == 0.5
        assert isinstance(score, float)


class TestSmartRepriceEdge:
    """Edge cases for smart_reprice_signal (zero counts)."""

    def test_zero_current_bid_count_returns_cancel(self):
        sig, price = smart_reprice_signal(
            current_bid_count=0, current_ask_count=10,
            prev_bid_count=5, prev_ask_count=10,
            listed_price=5.0, best_bid=4.5, best_ask=5.5,
        )
        assert sig == "cancel"
        assert price is None

    def test_zero_current_ask_count_returns_cancel(self):
        sig, price = smart_reprice_signal(
            current_bid_count=10, current_ask_count=0,
            prev_bid_count=5, prev_ask_count=10,
            listed_price=5.0, best_bid=4.5, best_ask=5.5,
        )
        assert sig == "cancel"
        assert price is None

    def test_both_current_counts_zero_returns_cancel(self):
        sig, price = smart_reprice_signal(
            current_bid_count=0, current_ask_count=0,
            prev_bid_count=5, prev_ask_count=10,
            listed_price=5.0, best_bid=4.5, best_ask=5.5,
        )
        assert sig == "cancel"
        assert price is None

    def test_large_ofi_negative_cancel(self):
        sig, price = smart_reprice_signal(
            current_bid_count=5, current_ask_count=50,  # qi = 0.1
            prev_bid_count=80, prev_ask_count=30,        # ofi = (5-80) - (50-30) = -95
            listed_price=5.0, best_bid=4.0, best_ask=6.0,
        )
        assert sig == "cancel"

    def test_mild_ofi_drop_signal(self):
        sig, price = smart_reprice_signal(
            current_bid_count=8, current_ask_count=15,
            prev_bid_count=15, prev_ask_count=10,
            listed_price=5.0, best_bid=4.9, best_ask=5.1,
        )
        assert sig in ("drop", "keep", "cancel")
        if sig == "drop":
            assert price is not None
            assert price < 5.0

    def test_strong_ofi_positive_boost_signal(self):
        sig, price = smart_reprice_signal(
            current_bid_count=30, current_ask_count=5,  # qi = 6 > 2.0
            prev_bid_count=10, prev_ask_count=10,         # ofi = (30-10) - (5-10) = 25 > 10
            listed_price=5.0, best_bid=5.5, best_ask=4.5,
        )
        assert sig == "boost"
        assert price is not None
        assert price > 4.5


# ══════════════════════════════════════════════════════════════════════
# 2. VALIDATOR EDGE CASES
# ══════════════════════════════════════════════════════════════════════


class TestValidateArbitrageProfitEdge:
    """Boundary conditions for validate_arbitrage_profit."""

    def test_profitable_trade_passes(self):
        margin = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=15.0, fee_markup=0.05,
            min_profit_margin=0.05, lock_days=7, penalty_per_day=0.005,
        )
        assert margin > 0

    def test_zero_buy_price_raises_zero_division(self):
        with pytest.raises(ZeroDivisionError):
            validate_arbitrage_profit(buy_price=0.0, expected_sell_price=10.0)

    def test_negative_buy_price_raises(self):
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit(buy_price=-1.0, expected_sell_price=10.0)

    def test_negative_margin_raises(self):
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit(buy_price=10.0, expected_sell_price=9.0)

    def test_zero_sell_price_raises(self):
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit(buy_price=1.0, expected_sell_price=0.0)

    def test_insufficient_tvm_margin_raises(self):
        with pytest.raises(PriceValidationError, match="Insufficient TVM-Adjusted"):
            validate_arbitrage_profit(
                buy_price=10.0, expected_sell_price=10.6, fee_markup=0.05,
                min_profit_margin=0.05, lock_days=7, penalty_per_day=0.005,
            )

    def test_exact_breakeven_raises(self):
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit(
                buy_price=10.0, expected_sell_price=10.0, fee_markup=0.0,
                min_profit_margin=0.0,
            )

    def test_min_margin_zero_with_tvm_adjustment(self):
        margin = validate_arbitrage_profit(
            buy_price=10.0, expected_sell_price=12.0, fee_markup=0.05,
            min_profit_margin=0.0, lock_days=0, penalty_per_day=0.0,
        )
        assert margin == pytest.approx(0.14, abs=0.01)  # (12*0.95 - 10)/10 = 0.14

    def test_high_lock_days_eats_margin(self):
        with pytest.raises(PriceValidationError, match="Insufficient TVM-Adjusted"):
            validate_arbitrage_profit(
                buy_price=10.0, expected_sell_price=20.0, fee_markup=0.05,
                min_profit_margin=0.10, lock_days=365, penalty_per_day=0.005,
            )


class TestValidateVolatilityEdge:
    """Edge cases for validate_volatility."""

    def test_empty_price_list_does_not_raise(self):
        validate_volatility([])

    def test_single_price_does_not_raise(self):
        validate_volatility([10.0])

    def test_zero_mean_does_not_raise(self):
        validate_volatility([0.0, 0.0, 0.0])

    def test_low_volatility_passes(self):
        validate_volatility([10.0, 10.1, 10.0, 10.1, 10.0])

    def test_high_volatility_raises(self):
        with pytest.raises(PriceValidationError, match="High Volatility Detected"):
            validate_volatility([1.0, 100.0, 1.0, 100.0], max_std_dev_pct=0.15)

    def test_custom_max_std_dev_pct(self):
        prices = [10.0, 12.0, 10.0, 12.0]
        with pytest.raises(PriceValidationError):
            validate_volatility(prices, max_std_dev_pct=0.01)
        validate_volatility(prices, max_std_dev_pct=0.50)


# ══════════════════════════════════════════════════════════════════════
# 3. CS2CAP MODEL INVARIANTS
# ══════════════════════════════════════════════════════════════════════


class TestBidsSnapshotHasData:
    """Edge cases for BidsSnapshot.has_data."""

    def test_max_bid_zero_returns_false(self):
        snap = BidsSnapshot(hash_name="test_item", max_bid=0.0)
        assert snap.has_data is False

    def test_max_bid_positive_returns_true(self):
        snap = BidsSnapshot(hash_name="test_item", max_bid=5.0)
        assert snap.has_data is True

    def test_max_bid_negative_returns_false(self):
        snap = BidsSnapshot(hash_name="test_item", max_bid=-1.0)
        assert snap.has_data is False

    def test_default_has_data_false(self):
        snap = BidsSnapshot(hash_name="default_item")
        assert snap.has_data is False


class TestPriceSnapshotLiquidityScore:
    """Tests for PriceSnapshot.liquidity_score calculation."""

    def test_zero_quantity_zero_score(self):
        snap = PriceSnapshot(hash_name="item", total_quantity=0)
        assert snap.liquidity_score == 0.0

    def test_half_capacity_score(self):
        snap = PriceSnapshot(hash_name="item", total_quantity=50)
        assert snap.liquidity_score == 0.5

    def test_capacity_score(self):
        snap = PriceSnapshot(hash_name="item", total_quantity=100)
        assert snap.liquidity_score == 1.0

    def test_above_capacity_capped_at_one(self):
        snap = PriceSnapshot(hash_name="item", total_quantity=500)
        assert snap.liquidity_score == 1.0

    def test_has_data_when_min_price_zero(self):
        snap = PriceSnapshot(hash_name="item", min_price=0.0)
        assert snap.has_data is False

    def test_has_data_when_min_price_positive(self):
        snap = PriceSnapshot(hash_name="item", min_price=0.01)
        assert snap.has_data is True

    def test_provider_quantities_contribute_to_total(self):
        snap = PriceSnapshot(
            hash_name="item",
            provider_quantities={"buff163": 10, "skinport": 7},
        )
        assert snap.total_quantity == 0  # not auto-summed
        assert isinstance(snap.liquidity_score, float)


class TestCrossMarketDataPostInit:
    """Tests for CrossMarketData.__post_init__ auto-population."""

    def test_global_min_ask_populated_from_provider_prices(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            provider_prices={"buff163": 15.0, "skinport": 12.0, "csfloat": 18.0},
        )
        assert data.global_min_ask == 12.0

    def test_global_max_bid_populated_from_buy_orders(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            buy_orders={"buff163": 10.0, "csfloat": 11.5, "skinport": 9.0},
        )
        assert data.global_max_bid == 11.5

    def test_both_populated_simultaneously(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            provider_prices={"buff163": 15.0, "csfloat": 14.0},
            buy_orders={"buff163": 10.0, "csfloat": 11.0},
        )
        assert data.global_min_ask == 14.0
        assert data.global_max_bid == 11.0

    def test_explicit_values_not_overwritten(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            global_min_ask=20.0,
            global_max_bid=5.0,
            provider_prices={"buff163": 15.0},
            buy_orders={"buff163": 10.0},
        )
        assert data.global_min_ask == 20.0
        assert data.global_max_bid == 5.0

    def test_empty_provider_prices_min_ask_zero(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            provider_prices={},
        )
        assert data.global_min_ask == 0.0

    def test_empty_buy_orders_max_bid_zero(self):
        data = CrossMarketData(
            hash_name="AK-47 | Redline",
            buy_orders={},
        )
        assert data.global_max_bid == 0.0

    def test_defaults_unchanged_with_no_data(self):
        data = CrossMarketData(hash_name="test")
        assert data.global_min_ask == 0.0
        assert data.global_max_bid == 0.0
        assert data.sales_count == 0
        assert data.avg_sale_price == 0.0
        assert data.liquidity_score == 0.0


class TestBatchMaxItems:
    """Verify BATCH_MAX_ITEMS constant."""

    def test_batch_max_items_is_100(self):
        assert BATCH_MAX_ITEMS == 100

    def test_batch_max_items_is_integer(self):
        assert isinstance(BATCH_MAX_ITEMS, int)

    def test_batch_max_items_positive(self):
        assert BATCH_MAX_ITEMS > 0


# ══════════════════════════════════════════════════════════════════════
# 4. RATE LIMIT / QUOTA SIMULATION
# ══════════════════════════════════════════════════════════════════════


class TestQuotaSimulation:
    """Simulate CS2Cap quota states without external API calls."""

    QUOTA_LIMIT = 50000  # Starter tier

    def _simulate_quota_usage(self, used: int) -> float:
        """Return usage percentage for given used count."""
        return used / self.QUOTA_LIMIT

    def test_80_percent_usage_is_40000(self):
        pct = self._simulate_quota_usage(40000)
        assert pct == pytest.approx(0.80)

    def test_95_percent_usage_is_47500(self):
        pct = self._simulate_quota_usage(47500)
        assert pct == pytest.approx(0.95)

    def test_100_percent_usage_is_50000(self):
        pct = self._simulate_quota_usage(50000)
        assert pct == pytest.approx(1.00)

    def test_over_quota_usage(self):
        pct = self._simulate_quota_usage(55000)
        assert pct > 1.0

    def test_zero_usage(self):
        pct = self._simulate_quota_usage(0)
        assert pct == 0.0


class TestAdaptiveDelayLogic:
    """Simulate the adaptive delay logic from CS2CapOracle._throttle."""

    def _compute_adaptive_delay(self, rate_remaining: int | None, current_delay: float) -> float:
        """Reproduce the throttle logic from CS2CapOracle._throttle."""
        if rate_remaining is not None:
            if rate_remaining < 5:
                return max(current_delay, 5.0)
            elif rate_remaining < 10:
                return max(current_delay, 2.0)
        return current_delay

    def test_no_header_no_change(self):
        assert self._compute_adaptive_delay(None, 1.0) == 1.0

    def test_remaining_below_5_boosts_to_5(self):
        assert self._compute_adaptive_delay(3, 1.0) == 5.0
        assert self._compute_adaptive_delay(0, 1.0) == 5.0
        assert self._compute_adaptive_delay(4, 2.0) == 5.0

    def test_remaining_below_5_preserves_higher_delay(self):
        assert self._compute_adaptive_delay(2, 7.0) == 7.0

    def test_remaining_below_10_boosts_to_2(self):
        assert self._compute_adaptive_delay(6, 1.0) == 2.0
        assert self._compute_adaptive_delay(8, 1.5) == 2.0

    def test_remaining_below_10_preserves_higher_delay(self):
        assert self._compute_adaptive_delay(7, 3.0) == 3.0

    def test_remaining_10_or_above_no_change(self):
        assert self._compute_adaptive_delay(10, 1.0) == 1.0
        assert self._compute_adaptive_delay(50, 1.0) == 1.0

    def test_delay_decay_on_success(self):
        """After a successful request, delay decays: max(delay * 0.98, 1.0)."""
        delay = 5.0
        for _ in range(3):
            delay = max(delay * 0.98, 1.0)
        assert delay < 5.0
        assert delay >= 1.0

    def test_delay_never_below_one(self):
        delay = 1.001
        delay = max(delay * 0.98, 1.0)
        assert delay >= 1.0

    def test_429_backoff_doubles_capped_at_30(self):
        delay = 1.0
        delay = min(delay * 2.0, 30.0)
        assert delay == 2.0

        delay = min(delay * 2.0, 30.0)
        assert delay == 4.0

        delay = min(delay * 2.0, 30.0)
        assert delay == 8.0

        # Jump to edge
        delay = min(16.0 * 2.0, 30.0)
        assert delay == 30.0

        delay = min(30.0 * 2.0, 30.0)
        assert delay == 30.0


class TestQuotaMonthlyTracking:
    """Simulate monthly quota tracking logic."""
    LIMIT = 50000

    def _check_quota_warnings(self, used: int) -> list[str]:
        """Simulate warning messages emitted at different thresholds."""
        warnings = []
        if used >= 40000:
            warnings.append(f"Monthly usage: {used}/50000 (80%)")
        if used >= 45000:
            warnings.append(f"Monthly usage: {used}/50000 (90%)")
        if used >= 50000:
            warnings.append("Quota exhausted")
        return warnings

    def test_no_warning_below_80_percent(self):
        assert len(self._check_quota_warnings(30000)) == 0

    def test_warning_at_80_percent(self):
        assert len(self._check_quota_warnings(40000)) == 1

    def test_both_warnings_at_90_percent(self):
        assert len(self._check_quota_warnings(45000)) == 2

    def test_exhaustion_at_100_percent(self):
        warnings = self._check_quota_warnings(50000)
        assert len(warnings) == 3
        assert "Quota exhausted" in warnings[-1]


# ══════════════════════════════════════════════════════════════════════
# 5. DATABASE STRESS PATTERN
# ══════════════════════════════════════════════════════════════════════


class TestDatabaseStressPattern:
    """Rapid consecutive writes to an in-memory DB to catch regressions."""

    RECORDS = 100
    MAX_SECONDS = 2.0  # 100 records should write well under 2 seconds

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory SQLite database with the price_history schema."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_name   TEXT    NOT NULL,
                price       REAL    NOT NULL,
                source      TEXT    NOT NULL DEFAULT 'cs2cap',
                recorded_at REAL    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_recorded ON price_history(recorded_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_name ON price_history(hash_name)"
        )
        yield conn
        conn.close()

    def _write_record(self, conn, hash_name: str, price: float, source: str) -> None:
        conn.execute(
            "INSERT INTO price_history (hash_name, price, source, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (hash_name, price, source, time.time()),
        )

    def test_100_rapid_writes(self, in_memory_db):
        conn = in_memory_db
        start = time.perf_counter()

        with conn:
            for i in range(self.RECORDS):
                self._write_record(
                    conn,
                    hash_name=f"item_{i % 10}",
                    price=10.0 + i * 0.01,
                    source="cs2cap",
                )

        elapsed = time.perf_counter() - start
        assert elapsed < self.MAX_SECONDS, (
            f"100 writes took {elapsed:.4f}s (max {self.MAX_SECONDS}s)"
        )

    def test_read_back_after_writes(self, in_memory_db):
        conn = in_memory_db
        with conn:
            for i in range(50):
                self._write_record(conn, "test_item", float(i), "cs2cap")

        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM price_history WHERE hash_name = ?",
            ("test_item",),
        ).fetchone()
        assert rows["cnt"] == 50

    def test_write_with_explicit_transaction(self, in_memory_db):
        conn = in_memory_db
        start = time.perf_counter()

        conn.execute("BEGIN")
        for i in range(self.RECORDS):
            self._write_record(conn, f"batched_{i % 5}", 5.0 + i * 0.1, "cs2cap")
        conn.commit()

        elapsed = time.perf_counter() - start
        row = conn.execute("SELECT COUNT(*) as cnt FROM price_history").fetchone()
        assert row["cnt"] == self.RECORDS
        assert elapsed < self.MAX_SECONDS

    def test_index_presence_does_not_slow_writes(self, in_memory_db):
        conn = in_memory_db
        # First batch to populate index
        with conn:
            for i in range(self.RECORDS):
                self._write_record(conn, f"idx_test_{i}", float(i), "cs2cap")

        # Second batch — index should not cause quadratic slowdown
        start = time.perf_counter()
        with conn:
            for i in range(self.RECORDS):
                self._write_record(conn, f"idx_test_{i}", float(i + self.RECORDS), "cs2cap")
        elapsed = time.perf_counter() - start

        # With index, 100 more writes should still be fast
        assert elapsed < self.MAX_SECONDS, (
            f"100 writes with populated index took {elapsed:.4f}s"
        )

    def test_price_db_singleton_exists(self):
        """Sanity check that the singleton is importable."""
        assert price_db is not None
        assert hasattr(price_db, "record_price")
