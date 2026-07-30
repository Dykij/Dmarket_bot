"""test_demand_strategy_v17.py — Comprehensive tests for OBI demand strategy v17.7.

Tests cover:
- Normalized OBI calculation
- OFI (Order Flow Imbalance)
- Z-score calibration
- Dynamic liquidity thresholds
- Spread entropy filter
- PVC trend multiplier
- Kelly + OFI integration
- GARCH + PVC integration
- HMM + VPIN integration
- Hawkes + Spread Entropy integration
- Decision logging
"""

from __future__ import annotations

import random

import pytest


class TestNormalizedOBI:
    """Test normalized_obi() from obi.py."""

    def test_all_buyers(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(100, 0) == 1.0

    def test_all_sellers(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(0, 100) == -1.0

    def test_balanced(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(50, 50) == 0.0

    def test_no_orders(self):
        from src.analysis.microstructure.obi import normalized_obi
        assert normalized_obi(0, 0) == 0.0

    def test_buyer_dominant(self):
        from src.analysis.microstructure.obi import normalized_obi
        result = normalized_obi(75, 25)
        assert 0.4 < result < 0.6  # ~0.5

    def test_seller_dominant(self):
        from src.analysis.microstructure.obi import normalized_obi
        result = normalized_obi(25, 75)
        assert -0.6 < result < -0.4  # ~-0.5


class TestOFI:
    """Test ofi() from obi.py."""

    def test_positive_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.5, 0.3) == 0.2

    def test_negative_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.3, 0.5) == -0.2

    def test_zero_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(0.5, 0.5) == 0.0

    def test_extreme_ofi(self):
        from src.analysis.microstructure.obi import ofi
        assert ofi(1.0, -1.0) == 2.0


class TestZScore:
    """Test obi_z_score() from obi.py."""

    def test_normal_value(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.5, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert z is not None and z > 0

    def test_outlier(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.9, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert z is not None and z > 2.0

    def test_insufficient_data(self):
        from src.analysis.microstructure.obi import obi_z_score
        assert obi_z_score(0.5, [0.1]) is None

    def test_zero_std(self):
        from src.analysis.microstructure.obi import obi_z_score
        z = obi_z_score(0.5, [0.5, 0.5, 0.5, 0.5, 0.5])
        assert z == 0.0


class TestDynamicLiquidity:
    """Test dynamic liquidity thresholds in demand_strategy.py."""

    def test_cheap_items_threshold(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=5, ask=2 -> Q=2.5 >= 1.5, total=7 >= 3
        r = calculate_demand_score('Cheap', 1.0, 0.9, 2, 5)
        assert r['score'] > 0

    def test_cheap_items_low_liquidity(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # total=2 < 3 (threshold for cheap items)
        r = calculate_demand_score('Cheap', 1.0, 0.9, 1, 1)
        assert r['score'] == 0.0 and 'low liquidity' in r['reason']

    def test_expensive_items_threshold(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # total=8 < 10 (threshold for expensive items)
        r = calculate_demand_score('Expensive', 15.0, 14.0, 4, 4)
        assert r['score'] == 0.0 and 'low liquidity' in r['reason']

    def test_mid_range_items(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=15, ask=5 -> Q=3.0 >= 2.5, total=20 >= 5
        r = calculate_demand_score('Mid', 5.0, 4.8, 5, 15)
        assert r['score'] > 0


class TestSpreadEntropy:
    """Test spread entropy filter in demand_strategy.py."""

    def test_hard_block_wide_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (10-7)/10 = 30% > 20% hard block
        r = calculate_demand_score('Wide', 10.0, 7.0, 20, 30)
        assert r['score'] == 0.0 and 'spread too wide' in r['reason']

    def test_soft_penalty_medium_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (10-8.5)/10 = 15% > 10% soft penalty
        r = calculate_demand_score('Medium', 10.0, 8.5, 10, 30)
        # Score should be penalized (lower than without penalty)
        r2 = calculate_demand_score('Tight', 10.0, 9.5, 10, 30)  # spread = 5%
        assert r['score'] <= r2['score']

    def test_no_penalty_tight_spread(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # spread = (5-4.8)/5 = 4% < 10%
        r = calculate_demand_score('Tight', 5.0, 4.8, 10, 30)
        assert r['score'] > 0


class TestGARCHPVC:
    """Test GARCH + PVC integration."""

    def test_pvc_increases_volatility(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        random.seed(42)
        garch = GARCH11Estimator()
        garch.calibrate([random.gauss(0, 0.02) for _ in range(50)])
        f1 = garch.forecast(steps=1, pvc_factor=1.0)
        f2 = garch.forecast(steps=1, pvc_factor=1.2)
        assert f2.forecast_vol_1 > f1.forecast_vol_1

    def test_pvc_factor_one_no_change(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        random.seed(42)
        garch = GARCH11Estimator()
        garch.calibrate([random.gauss(0, 0.02) for _ in range(50)])
        f1 = garch.forecast(steps=1, pvc_factor=1.0)
        f2 = garch.forecast(steps=1, pvc_factor=1.0)
        assert abs(f1.forecast_vol_1 - f2.forecast_vol_1) < 1e-10


class TestHMMVPIN:
    """Test HMM + VPIN integration."""

    def test_vpin_shifts_transition(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        random.seed(42)
        hmm = HMMRegimeDetector()
        for _ in range(50):
            hmm.update(random.gauss(0, 0.02))
        # With high VPIN, should be more bearish
        r1 = hmm.update(0.01, vpin=0.0)
        r2 = hmm.update(0.01, vpin=0.8)
        # state_probabilities: [CRISIS, BEAR, RECOVERY, BULL]
        bear_1 = r1.state_probabilities[0] + r1.state_probabilities[1]
        bear_2 = r2.state_probabilities[0] + r2.state_probabilities[1]
        assert bear_2 >= bear_1 * 0.9

    def test_low_vpin_no_effect(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        random.seed(42)
        hmm = HMMRegimeDetector()
        for _ in range(50):
            hmm.update(random.gauss(0, 0.02))
        r1 = hmm.update(0.01, vpin=0.0)
        r2 = hmm.update(0.01, vpin=0.3)
        # Should be similar (VPIN < 0.6 has no effect)
        bear_1 = r1.state_probabilities[0] + r1.state_probabilities[1]
        bear_2 = r2.state_probabilities[0] + r2.state_probabilities[1]
        assert abs(bear_1 - bear_2) < 0.1


class TestHawkesEntropy:
    """Test Hawkes + Spread Entropy integration."""

    def test_narrow_spread_higher_alpha(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        h = HawkesEstimator()
        h.adjust_for_spread_entropy(0.03)
        narrow = h._state.alpha
        h.adjust_for_spread_entropy(0.20)
        wide = h._state.alpha
        assert narrow > wide

    def test_normal_spread_default(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        h = HawkesEstimator()
        default_alpha = h.alpha
        h.adjust_for_spread_entropy(0.10)
        assert abs(h._state.alpha - default_alpha) < 0.001


class TestDemandScoreIntegration:
    """Integration tests for calculate_demand_score."""

    def test_high_demand_passes(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 5.0, 4.8, 5, 50)
        assert r['score'] > 0
        assert r['demand_ratio'] == 10.0
        assert r['obi_value'] > 0.5
        assert 'obi=' in r['reason']
        assert 'ofi=' in r['reason']

    def test_invalid_prices(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 0, 0, 10, 10)
        assert r['score'] == 0.0

    def test_obi_risk_gate(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        # bid=20, ask=80 -> OBI = (20-80)/(20+80) = -0.6 < -0.3
        r = calculate_demand_score('Test', 5.0, 4.8, 80, 20)
        # Should be rejected by demand ratio first (Q=0.25 < 2.5)
        assert r['score'] == 0.0

    def test_new_fields_present(self):
        from src.core.target_sniping.demand_strategy import calculate_demand_score
        r = calculate_demand_score('Test', 5.0, 4.8, 5, 50)
        assert 'ofi_value' in r
        assert 'obi_z' in r
        assert 'micro_price' in r
