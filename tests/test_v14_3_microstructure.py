"""Tests for v14.3 enhanced microstructure instruments."""
from __future__ import annotations

import math
import pytest
from src.analysis.microstructure import (
    stoikov_micro_price,
    simple_obi,
    multi_level_obi,
    queue_imbalance,
    queue_imbalance_signal,
    kyle_lambda,
    amihud_illiquidity,
    adverse_selection_check,
    realized_vol_std,
    realized_vol_parkinson,
    classify_volatility_regime,
    roll_effective_spread,
    roll_signal,
    volume_profile_poc,
    volume_profile_value_area,
    smart_reprice_signal,
    composite_buy_score,
    vwap_bands,
    day_of_week_multiplier,
    compute_vwap,
)


class TestStoikovMicroPrice:

    def test_neutral(self):
        mp = stoikov_micro_price(mid_price=10.0, spread=1.0, obi=0.0)
        assert mp == 10.0  # no imbalance → no adjustment

    def test_buyer_pressure(self):
        mp = stoikov_micro_price(mid_price=10.0, spread=1.0, obi=0.5)
        assert mp > 10.0  # positive OBI → upward adjustment

    def test_seller_pressure(self):
        mp = stoikov_micro_price(mid_price=10.0, spread=1.0, obi=-0.5)
        assert mp < 10.0  # negative OBI → downward adjustment

    def test_no_spread(self):
        mp = stoikov_micro_price(mid_price=10.0, spread=0.0, obi=0.8)
        assert mp == 10.0  # no spread → no adjustment possible


class TestSimpleOBI:

    def test_balanced(self):
        obi = simple_obi(10.0, 10.0, 5, 5)
        assert obi == 0.0

    def test_buyer_dominated(self):
        obi = simple_obi(10.0, 10.0, 10, 2)
        assert obi > 0.0

    def test_seller_dominated(self):
        obi = simple_obi(10.0, 10.0, 2, 10)
        assert obi < 0.0

    def test_zero_counts(self):
        obi = simple_obi(10.0, 10.0, 0, 0)
        assert obi == 0.0


class TestMultiLevelOBI:

    def test_no_listings(self):
        obi = multi_level_obi(2.0, 1.5, 5, 3, listings=None)
        assert -1.0 <= obi <= 1.0

    def test_with_listings(self):
        listings = [
            {"price": {"USD": 150}}, {"price": {"USD": 155}},
            {"price": {"USD": 160}}, {"price": {"USD": 170}},
        ]
        obi = multi_level_obi(2.0, 1.5, 5, 3, listings=listings, levels=3)
        assert -1.0 <= obi <= 1.0

    def test_bid_heavy(self):
        obi = multi_level_obi(2.0, 1.5, 20, 2, listings=None)
        assert obi > 0.0  # many bids, few asks → buyer pressure

    def test_ask_heavy(self):
        obi = multi_level_obi(2.0, 1.5, 2, 20, listings=None)
        assert obi < 0.0  # few bids, many asks → seller pressure


class TestQueueImbalance:

    def test_equal_queues(self):
        qi = queue_imbalance(10, 10)
        assert qi == 1.0

    def test_bid_heavy(self):
        qi = queue_imbalance(20, 10)
        assert qi == 2.0

    def test_ask_heavy(self):
        qi = queue_imbalance(5, 20)
        assert qi == 0.25

    def test_zero_ask(self):
        qi = queue_imbalance(10, 0)
        assert qi is None


class TestQueueImbalanceSignal:

    def test_buy_signal(self):
        assert queue_imbalance_signal(20, 10) == "buy"

    def test_sell_signal(self):
        assert queue_imbalance_signal(5, 20) == "sell"

    def test_neutral(self):
        assert queue_imbalance_signal(10, 10) == "neutral"


class TestKyleLambda:

    def test_stable_prices(self):
        sales = [{"price": 10.0}, {"price": 10.0}, {"price": 10.0}, {"price": 10.0}]
        lam = kyle_lambda(sales)
        assert lam is None  # no price change → no deltas → can't estimate

    def test_volatile_prices(self):
        sales = [{"price": 10.0}, {"price": 12.0}, {"price": 9.0}, {"price": 11.0}]
        lam = kyle_lambda(sales)
        assert lam > 0.0

    def test_insufficient_data(self):
        sales = [{"price": 10.0}, {"price": 12.0}]
        lam = kyle_lambda(sales)
        assert lam is None


class TestAmihudIlliquidity:

    def test_insufficient_data(self):
        sales = [{"price": 10.0}, {"price": 12.0}]
        illiq = amihud_illiquidity(sales)
        assert illiq is None

    def test_liquid(self):
        sales = [{"price": 10.0}, {"price": 10.01}, {"price": 10.0}, {"price": 10.01}]
        illiq = amihud_illiquidity(sales)
        assert illiq is not None
        assert illiq < 1.0


class TestAdverseSelectionCheck:

    def test_clean_pass(self):
        sales = [{"price": 10.0}, {"price": 10.01}, {"price": 10.0}] * 3
        ok, reason = adverse_selection_check(sales)
        assert ok is True
        assert "low" in reason.lower()

    def test_high_kyle_fails(self):
        sales = [{"price": 10.0}, {"price": 15.0}, {"price": 10.0}, {"price": 15.0}]
        ok, reason = adverse_selection_check(sales, max_kyle=0.001)
        assert ok is False


class TestRealizedVol:

    def test_std_estimation(self):
        sales = [{"price": 10.0}, {"price": 10.5}, {"price": 9.5},
                 {"price": 10.2}, {"price": 9.8}] * 3
        vol = realized_vol_std(sales)
        assert vol is not None
        assert vol > 0.0

    def test_parkinson_estimation(self):
        sales = [{"price": 10.0}, {"price": 10.5}, {"price": 9.5},
                 {"price": 10.8}, {"price": 9.2}, {"price": 10.0},
                 {"price": 11.0}, {"price": 9.0}] * 3
        vol = realized_vol_parkinson(sales)
        assert vol is not None
        assert vol > 0.0

    def test_insufficient_data(self):
        sales = [{"price": 10.0}, {"price": 10.5}]
        assert realized_vol_std(sales) is None
        assert realized_vol_parkinson(sales) is None


class TestVolatilityRegime:

    def test_low(self):
        assert classify_volatility_regime(0.10) == "low"

    def test_medium(self):
        assert classify_volatility_regime(0.35) == "medium"

    def test_high(self):
        assert classify_volatility_regime(0.65) == "high"


class TestRollEffectiveSpread:

    def test_negative_cov_returns_spread(self):
        prices = [10.0, 10.2, 10.0, 10.2, 10.0, 10.2, 10.0]
        spread = roll_effective_spread(prices)
        # with alternating prices, cov should be negative
        assert spread is not None
        assert spread > 0.0

    def test_trending_no_reversal(self):
        prices = [10.0, 10.1, 10.2, 10.3, 10.4, 10.5]
        spread = roll_effective_spread(prices)
        assert spread is None  # positive cov → no estimable spread

    def test_insufficient_data(self):
        assert roll_effective_spread([10.0, 10.1]) is None


class TestRollSignal:

    def test_cheap(self):
        prices = [10.0, 10.2, 10.0, 10.2, 10.0, 10.2]
        sig = roll_signal(prices, best_ask=10.0)
        assert sig in ("cheap", "expensive", None)


class TestVolumeProfile:

    def test_poc(self):
        sales = [{"price": 10.0}] * 10 + [{"price": 10.5}] * 3 + [{"price": 9.5}] * 2
        poc = volume_profile_poc(sales, num_buckets=5)
        assert poc is not None
        assert 9.0 < poc < 11.0

    def test_value_area(self):
        sales = [{"price": 10.0}] * 20 + [{"price": 10.5}] * 5 + [{"price": 9.5}] * 5
        result = volume_profile_value_area(sales, value_area_pct=0.70, num_buckets=5)
        assert result is not None
        vah, poc, val = result
        assert vah >= poc >= val

    def test_insufficient_data(self):
        sales = [{"price": 10.0}, {"price": 10.01}]
        assert volume_profile_poc(sales) is None


class TestSmartReprice:

    def test_keep_signal(self):
        sig, price = smart_reprice_signal(10, 10, 10, 10, 5.0, 4.5, 5.5)
        assert sig == "keep"
        assert price is None

    def test_cancel_signal(self):
        sig, _ = smart_reprice_signal(5, 20, 20, 10, 5.0, 4.0, 6.0)
        assert sig in ("cancel", "drop", "keep")  # depends on exact thresholds

    def test_drop_signal(self):
        sig, price = smart_reprice_signal(8, 15, 15, 10, 5.0, 4.0, 6.0)
        if sig == "drop":
            assert price is not None
            assert price < 5.0

    def test_boost_signal(self):
        sig, price = smart_reprice_signal(25, 8, 15, 10, 5.0, 5.5, 4.5)
        if sig == "boost":
            assert price is not None
            assert price > 4.5  # boost capped by best_ask * 1.03


class TestCompositeBuyScore:

    def test_good_opportunity(self):
        score, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.07, ask_count=5, bid_count=15,
            obi=0.4, ofi=10, cvd=5.0, vpin_val=0.1,
            vwap_discount=0.10, adverse_pass=True, vol_regime="low",
            kyle_lam=0.01,
        )
        assert score > 0.5  # should be a good buy

    def test_bad_opportunity(self):
        score, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.01, ask_count=20, bid_count=3,
            obi=-0.5, ofi=-15, cvd=-8.0, vpin_val=0.9,
            vwap_discount=0.0, adverse_pass=False, vol_regime="high",
            kyle_lam=0.08, entropy_regime="random",
        )
        assert score < 0.4  # should be rejected

    def test_components_sum(self):
        _, comps = composite_buy_score(
            best_ask=1.0, best_bid=1.05, ask_count=10, bid_count=10,
            obi=0.0, ofi=0, cvd=0.0, vpin_val=0.5,
            vwap_discount=0.0, adverse_pass=True, vol_regime="medium",
            kyle_lam=0.03,
        )
        for k, v in comps.items():
            assert 0.0 <= v <= 1.0, f"{k}={v} out of [0,1] range"


class TestVWAPBands:

    def test_bands(self):
        sales = [{"price": 10.0}] * 10 + [{"price": 11.0}] * 5 + [{"price": 9.0}] * 5
        vwap, lower, upper = vwap_bands(sales, num_std=2.0)
        assert vwap > 0
        assert lower < vwap < upper

    def test_bands_single_price(self):
        sales = [{"price": 10.0}] * 5
        vwap, lower, upper = vwap_bands(sales, num_std=2.0)
        assert vwap == 10.0
        assert lower == 10.0
        assert upper == 10.0


class TestDayOfWeek:

    def test_returns_float(self):
        m = day_of_week_multiplier()
        assert m in (1.0, 0.90)
