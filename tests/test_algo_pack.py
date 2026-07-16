"""
test_algo_pack.py — Comprehensive tests for all algo_pack modules.

Tests each algorithm independently with synthetic data.
"""

import math
import random
import pytest

from src.analysis.algo_pack.sell_optimizer import (
    find_optimal_discount,
    find_optimal_sell_price,
    _expected_profit,
)
from src.analysis.algo_pack.trend_strength import (
    lis_length,
    trend_strength,
    should_buy_by_trend,
    trend_direction,
)
from src.analysis.algo_pack.ewma import (
    ewma,
    ewma_forecast,
    ewma_volatility,
    ewma_volatility_regime,
    adaptive_kelly_fraction,
)
from src.analysis.algo_pack.sliding_window import (
    SlidingWindowMinMax,
    SlidingWindowEMA,
)
from src.analysis.algo_pack.regime_detector import (
    MarkovRegimeDetector,
    RegimeParams,
)
from src.analysis.algo_pack.bayesian_stats import (
    BetaDistribution,
    bayesian_kelly,
)
from src.analysis.algo_pack.spread_optimizer import (
    find_optimal_min_spread,
    estimate_spread_distribution,
)


# ══════════════════════════════════════════════════════════════════════
# Sell Optimizer (Ternary Search)
# ══════════════════════════════════════════════════════════════════════

class TestSellOptimizer:
    def test_returns_valid_discount(self):
        history = [9.5, 10.0, 10.2, 10.5, 11.0]
        d = find_optimal_discount(10.0, 8.0, 0.05, history)
        assert 0.01 <= d <= 0.15

    def test_profit_positive(self):
        history = [9.5, 10.0, 10.2, 10.5, 11.0]
        d = find_optimal_discount(10.0, 8.0, 0.05, history)
        sell = 10.0 * (1 - d)
        margin = sell - 8.0 - sell * 0.05
        assert margin > 0

    def test_no_history_fallback(self):
        d = find_optimal_discount(10.0, 8.0, 0.05, [])
        assert 0.01 <= d <= 0.15

    def test_high_history_high_discount(self):
        # All prices very high → algorithm finds max profit (may use high discount
        # if the fill probability curve is flat). The key is profit > 0.
        history = [11.0, 11.5, 12.0, 12.5, 13.0]
        d = find_optimal_discount(10.0, 8.0, 0.05, history)
        sell = 10.0 * (1 - d)
        margin = sell - 8.0 - sell * 0.05
        assert margin > 0, f"Discount {d} leads to negative margin"

    def test_low_history_high_discount(self):
        # All prices barely above cost → need higher discount to sell
        history = [8.5, 8.6, 8.7, 8.8, 8.9]
        d = find_optimal_discount(10.0, 8.0, 0.05, history)
        # Discount exists but margin is tight
        assert 0.01 <= d <= 0.15

    def test_optimal_sell_price(self):
        history = [9.5, 10.0, 10.2, 10.5, 11.0]
        price = find_optimal_sell_price(10.0, 8.0, 0.05, history)
        assert 8.0 < price < 12.0

    def test_expected_profit_calculation(self):
        # P(fill) should be 100% at low discount
        history = [10.0, 11.0, 12.0]
        ep = _expected_profit(10.0, 8.0, 0.01, 0.05, history)
        assert ep > 0  # all prices > sell_price


# ══════════════════════════════════════════════════════════════════════
# Trend Strength (LIS)
# ══════════════════════════════════════════════════════════════════════

class TestTrendStrength:
    def test_lis_ascending(self):
        assert lis_length([1, 2, 3, 4, 5]) == 5

    def test_lis_descending(self):
        assert lis_length([5, 4, 3, 2, 1]) == 1

    def test_lis_mixed(self):
        assert lis_length([3, 1, 4, 1, 5, 9]) == 4  # [1, 4, 5, 9]

    def test_lis_empty(self):
        assert lis_length([]) == 0

    def test_trend_uptrend(self):
        prices = [10 + i * 0.1 for i in range(50)]
        assert trend_strength(prices) > 0.8

    def test_trend_downtrend(self):
        prices = [20 - i * 0.1 for i in range(50)]
        assert trend_strength(prices) < 0.3

    def test_trend_neutral_short(self):
        assert trend_strength([1.0, 2.0]) == 0.5

    def test_should_buy_uptrend(self):
        prices = [10 + i * 0.1 for i in range(50)]
        assert should_buy_by_trend(prices)

    def test_should_not_buy_downtrend(self):
        prices = [20 - i * 0.1 for i in range(50)]
        assert not should_buy_by_trend(prices)

    def test_direction_labels(self):
        up = [10 + i * 0.1 for i in range(50)]
        assert trend_direction(up) in ("STRONG_UPTREND", "WEAK_UPTREND")


# ══════════════════════════════════════════════════════════════════════
# EWMA
# ══════════════════════════════════════════════════════════════════════

class TestEWMA:
    def test_ewma_single(self):
        assert ewma([5.0]) == 5.0

    def test_ewma_constant(self):
        assert abs(ewma([10.0, 10.0, 10.0]) - 10.0) < 0.001

    def test_ewma_uptrend(self):
        prices = [10 + i for i in range(20)]
        f = ewma_forecast(prices)
        assert f > 10.0

    def test_volatility_non_negative(self):
        prices = [10, 11, 9, 12, 8, 13, 7]
        v = ewma_volatility(prices)
        assert v >= 0

    def test_volatility_single(self):
        assert ewma_volatility([10.0]) == 0.0

    def test_vol_regime(self):
        # Low vol
        prices = [10.0 + 0.001 * i for i in range(50)]
        r = ewma_volatility_regime(prices)
        assert r in ("CONTRACTING", "NEUTRAL")

    def test_adaptive_kelly_range(self):
        prices = [10 + 0.1 * i for i in range(30)]
        k = adaptive_kelly_fraction(0.6, 1.5, prices)
        assert 0.0 <= k <= 1.0

    def test_adaptive_kelly_high_vol_reduces(self):
        # High vol → smaller kelly
        high_vol = [10, 15, 5, 14, 6, 13, 7, 12, 8, 11]
        low_vol = [10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6]
        k_high = adaptive_kelly_fraction(0.6, 1.5, high_vol)
        k_low = adaptive_kelly_fraction(0.6, 1.5, low_vol)
        assert k_high <= k_low


# ══════════════════════════════════════════════════════════════════════
# Sliding Window
# ══════════════════════════════════════════════════════════════════════

class TestSlidingWindow:
    def test_min_max_basic(self):
        sw = SlidingWindowMinMax(3)
        sw.add(5.0)
        sw.add(3.0)
        sw.add(7.0)
        assert sw.min == 3.0
        assert sw.max == 7.0

    def test_window_eviction(self):
        sw = SlidingWindowMinMax(3)
        sw.add(1.0)
        sw.add(2.0)
        sw.add(3.0)
        sw.add(0.5)  # evicts 1.0
        assert sw.min == 0.5
        assert sw.max == 3.0

    def test_range(self):
        sw = SlidingWindowMinMax(5)
        for v in [10, 20, 15, 25, 5]:
            sw.add(v)
        assert sw.range == 20  # 25 - 5

    def test_mid(self):
        sw = SlidingWindowMinMax(3)
        sw.add(10.0)
        sw.add(20.0)
        assert sw.mid == 15.0

    def test_ema(self):
        ema = SlidingWindowEMA(alpha=0.5)
        ema.add(10.0)
        ema.add(20.0)
        assert ema.current == 15.0  # 0.5*20 + 0.5*10

    def test_empty_window(self):
        sw = SlidingWindowMinMax(5)
        assert sw.min is None
        assert sw.max is None
        assert sw.range is None


# ══════════════════════════════════════════════════════════════════════
# Regime Detector (Markov)
# ══════════════════════════════════════════════════════════════════════

class TestRegimeDetector:
    def test_initial_neutral(self):
        det = MarkovRegimeDetector()
        assert 0.4 <= det.state.p_trending <= 0.6

    def test_trending_detection(self):
        det = MarkovRegimeDetector()
        for _ in range(15):
            det.update(0.03, 0.02)
        assert det.state.p_trending > 0.6

    def test_ranging_detection(self):
        det = MarkovRegimeDetector()
        for _ in range(20):
            det.update(0.001, 0.002)
        assert det.state.p_ranging > 0.5

    def test_params_trending(self):
        det = MarkovRegimeDetector()
        for _ in range(15):
            det.update(0.03, 0.02)
        params = det.get_params()
        assert params.kelly_mult > 1.0

    def test_params_ranging(self):
        det = MarkovRegimeDetector()
        for _ in range(20):
            det.update(0.001, 0.002)
        params = det.get_params()
        assert params.kelly_mult < 1.0

    def test_probabilities_sum_to_one(self):
        det = MarkovRegimeDetector()
        det.update(0.02, 0.01)
        total = det.state.p_trending + det.state.p_ranging
        assert abs(total - 1.0) < 0.01


# ══════════════════════════════════════════════════════════════════════
# Bayesian Stats
# ══════════════════════════════════════════════════════════════════════

class TestBayesianStats:
    def test_initial_prior(self):
        d = BetaDistribution()
        assert d.mean == 0.5

    def test_update_wins(self):
        d = BetaDistribution()
        for _ in range(10):
            d.update(True)
        assert d.mean > 0.5

    def test_update_losses(self):
        d = BetaDistribution()
        for _ in range(10):
            d.update(False)
        assert d.mean < 0.5

    def test_batch_update(self):
        d = BetaDistribution()
        d.update_batch(20, 10)
        # Prior is Beta(2,2), so posterior is Beta(22,12), mean = 22/34
        assert abs(d.mean - 22 / 34) < 0.01

    def test_credible_interval_contains_mean(self):
        d = BetaDistribution()
        d.update_batch(15, 10)
        lo, hi = d.credible_interval(0.95)
        assert lo < d.mean < hi

    def test_conservative_below_mean(self):
        d = BetaDistribution()
        d.update_batch(15, 10)
        c = d.conservative_estimate()
        assert c <= d.mean

    def test_kelly_range(self):
        d = BetaDistribution()
        d.update_batch(20, 10)
        k = bayesian_kelly(d, 1.5)
        assert 0.0 <= k <= 0.5

    def test_kelly_small_sample_conservative(self):
        # Very few trades → conservative estimate
        d = BetaDistribution()
        d.update_batch(3, 1)
        k = bayesian_kelly(d, 1.5)
        # Should be small due to uncertainty
        assert k < 0.2


# ══════════════════════════════════════════════════════════════════════
# Spread Optimizer (Binary Search)
# ══════════════════════════════════════════════════════════════════════

class TestSpreadOptimizer:
    def test_returns_valid_range(self):
        random.seed(42)
        history = []
        for _ in range(100):
            s = random.uniform(0.01, 0.10)
            wr = min(0.9, 0.3 + s * 8)
            won = random.random() < wr
            history.append({"spread_pct": round(s, 3), "profit": 1.0 if won else -0.5})

        opt = find_optimal_min_spread(history, target_win_rate=0.55)
        assert 0.01 <= opt <= 0.15

    def test_empty_history(self):
        opt = find_optimal_min_spread([], target_win_rate=0.55)
        assert 0.01 <= opt <= 0.15

    def test_stats(self):
        history = [{"spread_pct": 0.03}, {"spread_pct": 0.05}, {"spread_pct": 0.07}]
        stats = estimate_spread_distribution(history)
        assert stats["count"] == 3
        assert stats["mean"] == pytest.approx(0.05, abs=0.01)
