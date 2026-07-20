"""
test_financial_instruments.py — Tests for financial algorithms and risk modules.

Covers:
- Bayesian Stats (Beta CDF, Kelly, credible intervals)
- HMM Regime (transition matrix update, state detection)
- Circuit Breaker Manager (state machine, persistence)
- Dynamic Fee Manager (tier lookup, caching)
- Risk Manager (double-halve prevention, drawdown freeze)
- Price Validator (fee handling, slippage)
"""

from __future__ import annotations

import math
import time
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Bayesian Stats Tests
# ═══════════════════════════════════════════════════════════════════

class TestBetaDistribution:
    """Tests for BetaDistribution in bayesian_stats.py."""

    def test_initial_prior(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution()
        assert dist.alpha == 2.0
        assert dist.beta == 2.0
        assert abs(dist.mean - 0.5) < 1e-10

    def test_update_single(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution()
        dist.update(won=True)
        assert dist.alpha == 3.0
        assert dist.beta == 2.0
        assert dist.mean > 0.5

    def test_update_batch(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution()
        dist.update_batch(wins=10, losses=5)
        assert dist.alpha == 12.0
        assert dist.beta == 7.0

    def test_mode_requires_alpha_beta_gt_1(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=0.5, beta=0.5)
        # When alpha or beta <= 1, mode falls back to mean
        assert dist.mode == dist.mean

    def test_variance_decreases_with_more_data(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist_small = BetaDistribution(alpha=3, beta=3)
        dist_large = BetaDistribution(alpha=30, beta=30)
        assert dist_large.variance < dist_small.variance

    def test_credible_interval_contains_mean(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=22, beta=12)  # ~0.65 win rate
        lo, hi = dist.credible_interval(0.95)
        assert lo < dist.mean < hi

    def test_credible_interval_narrows_with_data(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist_small = BetaDistribution(alpha=3, beta=3)
        dist_large = BetaDistribution(alpha=30, beta=30)
        lo_s, hi_s = dist_small.credible_interval(0.95)
        lo_l, hi_l = dist_large.credible_interval(0.95)
        assert (hi_l - lo_l) < (hi_s - lo_s)

    def test_beta_cdf_accuracy_small_params(self):
        """Test that the improved Beta CDF is accurate for small alpha/beta."""
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=2, beta=2)
        # For Beta(2,2), CDF(0.5) should be exactly 0.5 (symmetric)
        cdf_05 = dist._beta_cdf(0.5)
        assert abs(cdf_05 - 0.5) < 0.01, f"Beta(2,2) CDF(0.5) = {cdf_05}, expected ~0.5"

    def test_beta_cdf_boundaries(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=5, beta=5)
        assert dist._beta_cdf(0.0) == 0.0
        assert dist._beta_cdf(1.0) == 1.0

    def test_beta_cdf_large_params(self):
        """Test Beta CDF for large alpha/beta (uses normal approximation)."""
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=100, beta=100)
        # Symmetric around 0.5
        assert abs(dist._beta_cdf(0.5) - 0.5) < 0.01

    def test_conservative_estimate_below_mean(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution
        dist = BetaDistribution(alpha=22, beta=12)
        conservative = dist.conservative_estimate(0.80)
        assert conservative < dist.mean

    def test_bayesian_kelly_non_negative(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution, bayesian_kelly
        dist = BetaDistribution(alpha=22, beta=12)
        kelly = bayesian_kelly(dist, win_loss_ratio=1.5)
        assert kelly >= 0.0

    def test_bayesian_kelly_zero_for_bad_odds(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution, bayesian_kelly
        dist = BetaDistribution(alpha=5, beta=20)  # ~20% win rate
        kelly = bayesian_kelly(dist, win_loss_ratio=0.5)  # Bad W/L ratio
        assert kelly == 0.0

    def test_confidence_weighted_kelly_crisis_zero(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution, confidence_weighted_kelly
        dist = BetaDistribution(alpha=22, beta=12)
        kelly = confidence_weighted_kelly(dist, 1.5, hmm_state="CRISIS")
        assert kelly == 0.0  # CRISIS = no buys

    def test_confidence_weighted_kelly_bull_higher(self):
        from src.analysis.algo_pack.bayesian_stats import BetaDistribution, confidence_weighted_kelly
        dist = BetaDistribution(alpha=22, beta=12)
        kelly_bear = confidence_weighted_kelly(dist, 1.5, hmm_state="BEAR")
        kelly_bull = confidence_weighted_kelly(dist, 1.5, hmm_state="BULL")
        assert kelly_bull > kelly_bear


# ═══════════════════════════════════════════════════════════════════
# HMM Regime Tests
# ═══════════════════════════════════════════════════════════════════

class TestHMMRegime:
    """Tests for HMM Regime Detection."""

    def test_initial_params(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        hmm = HMMRegimeDetector()
        assert len(hmm.params.means) == 4
        assert len(hmm.params.stds) == 4
        assert len(hmm.params.transition) == 4

    def test_transition_rows_sum_to_one(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        hmm = HMMRegimeDetector()
        for row in hmm.params.transition:
            assert abs(sum(row) - 1.0) < 1e-10

    def test_update_returns_regime_result(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        hmm = HMMRegimeDetector()
        # Feed some returns
        import random
        random.seed(42)
        for _ in range(60):
            result = hmm.update(random.gauss(0.001, 0.02))
        assert result is not None
        assert hasattr(result, "state_probabilities")
        assert hasattr(result, "transition_recommendation")

    def test_state_probs_sum_to_one(self):
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        hmm = HMMRegimeDetector()
        import random
        random.seed(42)
        for _ in range(60):
            result = hmm.update(random.gauss(0.001, 0.02))
        assert abs(sum(result.state_probabilities) - 1.0) < 0.01

    def test_transition_matrix_stochastic_after_update(self):
        """Test that transition matrix remains stochastic after M-step."""
        from src.analysis.algo_pack.hmm_regime import HMMRegimeDetector
        hmm = HMMRegimeDetector()
        import random
        random.seed(42)
        # Feed enough data to trigger calibration
        for _ in range(100):
            hmm.update(random.gauss(0.001, 0.02))
        # Check rows still sum to 1
        for row in hmm.params.transition:
            assert abs(sum(row) - 1.0) < 0.01, f"Row sum = {sum(row)}, expected ~1.0"


# ═══════════════════════════════════════════════════════════════════
# Circuit Breaker Manager Tests
# ═══════════════════════════════════════════════════════════════════

class TestCircuitBreakerManager:
    """Tests for CircuitBreakerManager."""

    def test_default_components_created(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager
        mgr = CircuitBreakerManager()
        mgr._initialized = True  # Skip DB load
        for name in ["dmarket_api", "oracle", "sqlite", "telegram"]:
            mgr._breakers[name] = mgr.DEFAULT_COMPONENTS[name]
        status = mgr.get_status()
        assert "dmarket_api" in status
        assert "oracle" in status

    def test_is_available_default_true(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager
        mgr = CircuitBreakerManager()
        mgr._initialized = True
        assert mgr.is_available("unknown_component") is True

    def test_record_failure_opens_circuit(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager, ComponentBreaker
        mgr = CircuitBreakerManager()
        mgr._initialized = True
        mgr._breakers["test"] = ComponentBreaker(name="test", fail_threshold=3)
        # Override _save_to_db to be a no-op
        mgr._save_to_db = lambda: None

        for _ in range(3):
            mgr.record_failure("test", Exception("test error"))
        assert mgr.is_available("test") is False

    def test_record_success_closes_circuit(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager, ComponentBreaker
        mgr = CircuitBreakerManager()
        mgr._initialized = True
        mgr._breakers["test"] = ComponentBreaker(name="test", fail_threshold=3)
        mgr._save_to_db = lambda: None

        for _ in range(3):
            mgr.record_failure("test", Exception("test error"))
        assert mgr.is_available("test") is False

        # Manually set to HALF_OPEN (simulating cooldown elapsed)
        mgr._breakers["test"].state = mgr._breakers["test"].state.HALF_OPEN
        mgr.record_success("test")
        assert mgr.is_available("test") is True

    def test_reset_component(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager, ComponentBreaker
        mgr = CircuitBreakerManager()
        mgr._initialized = True
        mgr._breakers["test"] = ComponentBreaker(name="test", fail_threshold=3)
        mgr._save_to_db = lambda: None

        for _ in range(3):
            mgr.record_failure("test", Exception("test error"))
        mgr.reset("test")
        assert mgr.is_available("test") is True

    def test_unavailable_list(self):
        from src.risk.circuit_breaker_manager import CircuitBreakerManager, ComponentBreaker
        mgr = CircuitBreakerManager()
        mgr._initialized = True
        mgr._breakers["test"] = ComponentBreaker(name="test", fail_threshold=2)
        mgr._save_to_db = lambda: None

        for _ in range(2):
            mgr.record_failure("test", Exception("test error"))
        unavailable = mgr.get_unavailable()
        assert "test" in unavailable


# ═══════════════════════════════════════════════════════════════════
# Dynamic Fee Manager Tests
# ═══════════════════════════════════════════════════════════════════

class TestDynamicFeeManager:
    """Tests for DynamicFeeManager."""

    @pytest.mark.asyncio
    async def test_get_sell_fee_tier_lookup(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        # Override API fetch to always return None (async)
        async def mock_fetch(*a, **kw):
            return None
        mgr._fetch_fee_from_api = mock_fetch

        # $5 item should be in 5% tier
        fee = await mgr.get_sell_fee(price_usd=5.0)
        assert abs(fee - 0.05) < 0.001

    @pytest.mark.asyncio
    async def test_get_sell_fee_low_price_tier(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        async def mock_fetch(*a, **kw):
            return None
        mgr._fetch_fee_from_api = mock_fetch

        # $0.50 item should be in 10% tier
        fee = await mgr.get_sell_fee(price_usd=0.50)
        assert abs(fee - 0.10) < 0.001

    @pytest.mark.asyncio
    async def test_get_buy_fee_always_zero(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        fee = await mgr.get_buy_fee(price_usd=10.0)
        assert fee == 0.0

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        from src.risk.dynamic_fee import DynamicFeeManager, FeeCacheEntry
        mgr = DynamicFeeManager()
        mgr._cache["sell_test"] = FeeCacheEntry(fee_pct=5.0, cached_at=time.time())
        fee = await mgr.get_sell_fee(item_id="test", price_usd=10.0)
        assert abs(fee - 0.05) < 0.001

    @pytest.mark.asyncio
    async def test_cache_expired_refreshes(self):
        from src.risk.dynamic_fee import DynamicFeeManager, FeeCacheEntry
        mgr = DynamicFeeManager()
        mgr._cache["sell_test"] = FeeCacheEntry(
            fee_pct=99.0, cached_at=time.time() - 7200, ttl=3600
        )
        async def mock_fetch(*a, **kw):
            return None
        mgr._fetch_fee_from_api = mock_fetch
        fee = await mgr.get_sell_fee(item_id="test", price_usd=10.0)
        # Should have refreshed from tier lookup
        assert abs(fee - 0.05) < 0.001

    def test_update_fee_tiers(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        mgr.update_fee_tiers([
            {"min_price": 0, "max_price": 100, "sell_fee_pct": 3.0},
        ])
        assert mgr._fee_tiers[0].sell_fee_pct == 3.0

    def test_clear_cache(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        mgr._cache["test"] = MagicMock()
        mgr.clear_cache()
        assert len(mgr._cache) == 0

    def test_get_stats(self):
        from src.risk.dynamic_fee import DynamicFeeManager
        mgr = DynamicFeeManager()
        stats = mgr.get_stats()
        assert "cached_entries" in stats
        assert "fee_tiers" in stats


# ═══════════════════════════════════════════════════════════════════
# Risk Manager Tests
# ═══════════════════════════════════════════════════════════════════

class TestRiskManager:
    """Tests for RiskManager."""

    def test_consecutive_loss_no_double_halve(self):
        """Test that consecutive loss reduction + soft halt don't double-halve."""
        from src.risk.risk_manager import RiskManager
        rm = RiskManager()
        rm._consecutive_losses = 3
        rm._current_drawdown_pct = 6.0  # Above soft halt threshold
        rm.soft_halt_drawdown_pct = 5.0
        rm.max_drawdown_pct = 15.0

        # Mock _maybe_roll_day to be a no-op
        rm._maybe_roll_day = lambda: None

        result = rm.pre_trade_check(
            proposed_size_usd=10.0,
            current_equity_usd=100.0,
            game_id="cs2",
            item_title="test",
        )

        # Should be halved ONCE (50%), not twice (25%)
        if result.allowed:
            assert result.adjusted_size_usd >= 4.5  # ~50% of 10, not ~25%

    def test_drawdown_freeze_blocks_buys(self):
        from src.risk.risk_manager import RiskManager
        rm = RiskManager()
        # Set peak equity high, current equity low to create 16% drawdown
        rm._peak_equity = 120.0  # Peak was $120
        # current_equity_usd=100 → drawdown = (120-100)/120 = 16.67%
        rm.max_drawdown_pct = 20.0  # Set higher than current to isolate freeze

        rm._maybe_roll_day = lambda: None

        # Mock the Config to enable drawdown freeze
        with patch("src.risk.risk_manager._is_drawdown_freeze_enabled", return_value=True), \
             patch("src.risk.risk_manager._get_drawdown_freeze_threshold", return_value=15.0):
            result = rm.pre_trade_check(
                proposed_size_usd=5.0,
                current_equity_usd=100.0,
                game_id="cs2",
                item_title="test",
            )
        # Should be blocked by drawdown freeze
        assert result.allowed is False


# ═══════════════════════════════════════════════════════════════════
# Price Validator Tests
# ═══════════════════════════════════════════════════════════════════

class TestPriceValidator:
    """Tests for price_validator.py."""

    def test_validate_price_normal(self):
        from src.risk.price_validator import validate_price
        assert validate_price(10.0) == 10.0

    def test_validate_price_negative_rejected(self):
        from src.risk.price_validator import validate_price, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_price(-1.0)

    def test_validate_price_nan_rejected(self):
        from src.risk.price_validator import validate_price, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_price(float("nan"))

    def test_validate_price_inf_rejected(self):
        from src.risk.price_validator import validate_price, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_price(float("inf"))

    def test_validate_price_below_floor(self):
        from src.risk.price_validator import validate_price, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_price(0.01)

    def test_validate_arbitrage_profit_positive(self):
        from src.risk.price_validator import validate_arbitrage_profit
        # Buy $10, sell $15, 5% fees each side
        margin = validate_arbitrage_profit(
            buy_price=10.0,
            expected_sell_price=15.0,
            fee_markup=0.05,
            buy_fee_markup=0.05,
            min_profit_margin=0.05,
            lock_days=0,
        )
        assert margin > 0

    def test_validate_arbitrage_profit_loss_blocked(self):
        from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_arbitrage_profit(
                buy_price=10.0,
                expected_sell_price=10.0,  # Same price = loss after fees
                fee_markup=0.05,
                buy_fee_markup=0.05,
            )

    def test_validate_slippage_within_bounds(self):
        from src.risk.price_validator import validate_slippage
        validate_slippage(10.0, 10.1, max_slippage_pct=0.02)

    def test_validate_slippage_exceeded(self):
        from src.risk.price_validator import validate_slippage, PriceValidationError
        with pytest.raises(PriceValidationError):
            validate_slippage(10.0, 12.0, max_slippage_pct=0.02)

    def test_validate_volatility_high(self):
        from src.risk.price_validator import validate_volatility, PriceValidationError
        prices = [10.0, 12.0, 8.0, 15.0, 5.0, 20.0, 3.0]
        with pytest.raises(PriceValidationError):
            validate_volatility(prices, max_std_dev_pct=0.10)

    def test_validate_volatility_low_passes(self):
        from src.risk.price_validator import validate_volatility
        prices = [10.0, 10.1, 10.0, 10.1, 10.0]
        validate_volatility(prices, max_std_dev_pct=0.15)


# ═══════════════════════════════════════════════════════════════════
# GARCH Tests
# ═══════════════════════════════════════════════════════════════════

class TestGARCH:
    """Tests for GARCH(1,1) volatility forecasting."""

    def test_calibration_with_sufficient_data(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        import random
        random.seed(42)
        returns = [random.gauss(0, 0.02) for _ in range(100)]
        estimator = GARCH11Estimator()
        params = estimator.calibrate(returns)
        assert params.converged is True
        assert params.alpha > 0
        assert params.beta > 0
        assert params.alpha + params.beta < 1.0

    def test_calibration_insufficient_data(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        returns = [0.01, -0.01, 0.02]
        estimator = GARCH11Estimator()
        params = estimator.calibrate(returns)
        # Should return default params (not converged)
        assert params.converged is False

    def test_online_update(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        import random
        random.seed(42)
        returns = [random.gauss(0, 0.02) for _ in range(100)]
        estimator = GARCH11Estimator()
        estimator.calibrate(returns)
        old_vol = estimator.params.current_vol
        estimator.update(0.10)  # Large return
        assert estimator.params.current_vol != old_vol

    def test_volatility_regime_in_forecast(self):
        from src.analysis.algo_pack.garch import GARCH11Estimator
        import random
        random.seed(42)
        returns = [random.gauss(0, 0.02) for _ in range(100)]
        estimator = GARCH11Estimator()
        estimator.calibrate(returns)
        forecast = estimator.forecast(steps=5)
        assert forecast is not None
        assert hasattr(forecast, "vol_regime")
        assert forecast.vol_regime in ["extreme", "high", "normal", "low"]


# ═══════════════════════════════════════════════════════════════════
# Concentration Risk Tests
# ═══════════════════════════════════════════════════════════════════

class TestConcentrationRisk:
    """Tests for concentration_risk.py."""

    def test_extract_weapon_type(self):
        from src.risk.concentration_risk import ConcentrationRiskManager
        cr = ConcentrationRiskManager.__new__(ConcentrationRiskManager)
        assert cr._extract_collection("AK-47 | Redline (Field-Tested)") == "AK-47"
        assert cr._extract_collection("Karambit | Doppler (Factory New)") == "Karambit"

    def test_extract_full_title_for_cases(self):
        from src.risk.concentration_risk import ConcentrationRiskManager
        cr = ConcentrationRiskManager.__new__(ConcentrationRiskManager)
        assert cr._extract_collection("Operation Bravo Case") == "Operation Bravo Case"

    def test_classify_category(self):
        from src.risk.concentration_risk import ConcentrationRiskManager
        cr = ConcentrationRiskManager.__new__(ConcentrationRiskManager)
        cr.CATEGORIES = {
            "knife": ["karambit", "butterfly"],
            "rifle": ["ak-47", "m4a4"],
        }
        assert cr._classify_category("Karambit | Doppler") == "knife"
        assert cr._classify_category("AK-47 | Redline") == "rifle"


# ═══════════════════════════════════════════════════════════════════
# Sliding Window Tests
# ═══════════════════════════════════════════════════════════════════

class TestSlidingWindow:
    """Tests for sliding_window.py."""

    def test_min_max_basic(self):
        from src.analysis.algo_pack.sliding_window import SlidingWindowMinMax
        window = SlidingWindowMinMax(window_size=3)
        window.add(1)
        window.add(3)
        window.add(2)
        assert window.min == 1
        assert window.max == 3
        assert window.range == 2

    def test_min_max_expiration(self):
        from src.analysis.algo_pack.sliding_window import SlidingWindowMinMax
        window = SlidingWindowMinMax(window_size=3)
        window.add(1)
        window.add(3)
        window.add(2)
        window.add(5)  # Expires value 1
        assert window.min == 2
        assert window.max == 5

    def test_empty_window(self):
        from src.analysis.algo_pack.sliding_window import SlidingWindowMinMax
        window = SlidingWindowMinMax(window_size=3)
        assert window.min is None
        assert window.max is None


# ═══════════════════════════════════════════════════════════════════
# Trend Strength Tests
# ═══════════════════════════════════════════════════════════════════

class TestTrendStrength:
    """Tests for trend_strength.py."""

    def test_perfect_uptrend(self):
        from src.analysis.algo_pack.trend_strength import trend_strength
        prices = list(range(1, 51))  # 1 to 50
        strength = trend_strength(prices, window=50)
        assert strength == 1.0

    def test_perfect_downtrend(self):
        from src.analysis.algo_pack.trend_strength import trend_strength
        prices = list(range(50, 0, -1))  # 50 to 1
        strength = trend_strength(prices, window=50)
        # LIS of strictly decreasing sequence = 1 element
        # strength = 1/50 = 0.02
        assert strength < 0.1  # Very low = strong downtrend

    def test_empty_prices(self):
        from src.analysis.algo_pack.trend_strength import trend_strength
        # Empty prices returns 0.5 (neutral, not enough data)
        assert trend_strength([]) == 0.5

    def test_short_prices(self):
        from src.analysis.algo_pack.trend_strength import trend_strength
        assert trend_strength([1, 2]) == 0.5  # Too short, returns neutral
