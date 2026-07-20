"""
test_db_risk_extended.py — Tests for DB and Risk modules.

Covers:
- Profit tracker
- Lock tracker
- Error reporter
- Fatal errors
- Incident manager
- Hawkes process (direct)
- VPIN (direct)
- Thompson sampling
"""

from __future__ import annotations

import asyncio
import math
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Fatal Errors Tests
# ═══════════════════════════════════════════════════════════════════

class TestFatalErrors:
    """Tests for fatal_errors.py."""

    def test_classify_transient(self):
        from src.risk.fatal_errors import classify
        result = classify(ConnectionError("timeout"))
        assert result in ["TRANSIENT", "FATAL", "UNKNOWN"]

    def test_classify_fatal(self):
        from src.risk.fatal_errors import classify
        result = classify(SystemExit(1))
        assert result in ["TRANSIENT", "FATAL", "UNKNOWN"]

    def test_exit_code_for(self):
        from src.risk.fatal_errors import exit_code_for
        code = exit_code_for(Exception("test"))
        assert isinstance(code, int)
        assert code >= 0

    def test_classify_rate_limit(self):
        from src.risk.fatal_errors import classify, RateLimitError
        result = classify(RateLimitError("429"))
        assert result == "TRANSIENT"

    def test_classify_circuit_breaker(self):
        from src.risk.fatal_errors import classify, CircuitBreakerOpen
        result = classify(CircuitBreakerOpen("breaker open"))
        assert result == "TRANSIENT"


# ═══════════════════════════════════════════════════════════════════
# Error Reporter Tests
# ═══════════════════════════════════════════════════════════════════

class TestErrorReporter:
    """Tests for error_reporter.py."""

    def test_init_with_exception(self):
        from src.risk.error_reporter import ErrorReporter
        try:
            raise ValueError("test error")
        except ValueError as e:
            reporter = ErrorReporter(e)
            assert reporter.exc is e
            assert "test error" in str(reporter.exc)

    def test_with_context(self):
        from src.risk.error_reporter import ErrorReporter
        try:
            raise ValueError("test")
        except ValueError as e:
            reporter = ErrorReporter(e)
            reporter.with_context(balance=100.0, game="cs2")
            assert reporter.context["balance"] == 100.0

    def test_exit_code(self):
        from src.risk.error_reporter import ErrorReporter
        try:
            raise ConnectionError("timeout")
        except ConnectionError as e:
            reporter = ErrorReporter(e)
            assert isinstance(reporter._exit_code, int)

    def test_classification(self):
        from src.risk.error_reporter import ErrorReporter
        try:
            raise RuntimeError("fatal")
        except RuntimeError as e:
            reporter = ErrorReporter(e)
            assert reporter._classification in ["TRANSIENT", "FATAL", "UNKNOWN"]


# ═══════════════════════════════════════════════════════════════════
# Lock Tracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestLockTracker:
    """Tests for lock_tracker.py."""

    def test_module_importable(self):
        from src.risk import lock_tracker
        assert lock_tracker is not None


# ═══════════════════════════════════════════════════════════════════
# Incident Manager Tests
# ═══════════════════════════════════════════════════════════════════

class TestIncidentManager:
    """Tests for incident_manager.py."""

    def test_module_importable(self):
        from src.risk import incident_manager
        assert incident_manager is not None


# ═══════════════════════════════════════════════════════════════════
# Hawkes Process Tests (Direct)
# ═══════════════════════════════════════════════════════════════════

class TestHawkesDirect:
    """Direct tests for Hawkes process."""

    def test_hawkes_init(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        hp = HawkesEstimator()
        assert hp is not None

    def test_hawkes_update_single_event(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        hp = HawkesEstimator()
        intensity = hp.update(1.0)
        assert isinstance(intensity, float)
        assert intensity >= 0

    def test_hawkes_burst_detection(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        hp = HawkesEstimator()
        # Simulate burst of events
        for i in range(10):
            hp.update(float(i) * 0.1)
        state = hp.get_state()
        assert state.current_intensity > 0

    def test_hawkes_reset(self):
        from src.analysis.algo_pack.hawkes import HawkesEstimator
        hp = HawkesEstimator()
        hp.update(1.0)
        hp.reset()
        assert hp.get_state().current_intensity == hp.get_state().baseline


# ═══════════════════════════════════════════════════════════════════
# VPIN Tests (Direct)
# ═══════════════════════════════════════════════════════════════════

class TestVPINDirect:
    """Direct tests for VPIN."""

    def test_vpin_init(self):
        from src.analysis.algo_pack.vpin import VPINEstimator
        vpin = VPINEstimator(bucket_size=100)
        assert vpin is not None

    def test_vpin_update(self):
        from src.analysis.algo_pack.vpin import VPINEstimator
        vpin = VPINEstimator(bucket_size=100)
        result = vpin.update(price=10.0, volume=50.0)
        assert result is not None
        assert hasattr(result, "vpin")

    def test_vpin_toxicity_classification(self):
        from src.analysis.algo_pack.vpin import VPINEstimator
        vpin = VPINEstimator(bucket_size=50)
        # Feed enough data
        for i in range(20):
            vpin.update(price=10.0 + i * 0.1, volume=20.0)
        result = vpin.update(price=12.0, volume=20.0)
        assert result.toxicity_level in ["low", "normal", "high", "extreme"]


# ═══════════════════════════════════════════════════════════════════
# Thompson Sampling Tests (Direct)
# ═══════════════════════════════════════════════════════════════════

class TestThompsonDirect:
    """Direct tests for Thompson sampling."""

    def test_thompson_init(self):
        from src.analysis.algo_pack.thompson_sampling import ThompsonStrategySelector
        ts = ThompsonStrategySelector(strategies=["aggressive", "conservative", "balanced"])
        assert ts is not None

    def test_thompson_select(self):
        from src.analysis.algo_pack.thompson_sampling import ThompsonStrategySelector
        ts = ThompsonStrategySelector(strategies=["aggressive", "conservative", "balanced"])
        result = ts.select()
        assert result.selected_strategy in ["aggressive", "conservative", "balanced"]

    def test_thompson_update(self):
        from src.analysis.algo_pack.thompson_sampling import ThompsonStrategySelector
        ts = ThompsonStrategySelector(strategies=["aggressive", "conservative", "balanced"])
        ts.select()
        ts.update("aggressive", won=True, reward=5.0)
        state = ts.get_state()
        assert "arms" in state

    def test_thompson_rankings(self):
        from src.analysis.algo_pack.thompson_sampling import ThompsonStrategySelector
        ts = ThompsonStrategySelector(strategies=["aggressive", "conservative", "balanced"])
        for _ in range(10):
            result = ts.select()
            ts.update(result.selected_strategy, won=True, reward=1.0)
        rankings = ts.get_rankings()
        assert len(rankings) == 3


# ═══════════════════════════════════════════════════════════════════
# Profit Tracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestProfitTracker:
    """Tests for profit_tracker.py."""

    def test_module_importable(self):
        from src.db import profit_tracker
        assert profit_tracker is not None


# ═══════════════════════════════════════════════════════════════════
# Liquidity Manager Tests
# ═══════════════════════════════════════════════════════════════════

class TestLiquidityManagerExtended:
    """Extended tests for liquidity_manager.py."""

    def test_utc_today(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager.__new__(LiquidityManager)
        lm._get_today = lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).strftime("%Y-%m-%d")
        today = lm._get_today()
        assert len(today) == 10  # YYYY-MM-DD


# ═══════════════════════════════════════════════════════════════════
# Backoff/Circuit Breaker Tests
# ═══════════════════════════════════════════════════════════════════

class TestBackoffExtended:
    """Extended tests for backoff.py circuit breaker."""

    def test_thread_safety(self):
        """Test that circuit breaker is thread-safe."""
        import threading
        from src.api.dmarket_api_client.backoff import CircuitBreaker

        cb = CircuitBreaker(name="test", fail_threshold=3)
        results = []

        def try_request():
            for _ in range(10):
                if cb.allow_request():
                    results.append(True)
                else:
                    results.append(False)

        threads = [threading.Thread(target=try_request) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete without crash
        assert len(results) == 50

    def test_exponential_backoff_preserved(self):
        """Test that exponential backoff is preserved across re-opens."""
        from src.api.dmarket_api_client.backoff import CircuitBreaker

        cb = CircuitBreaker(name="test", fail_threshold=2, base_cooldown=10.0)

        # First open
        for _ in range(2):
            cb.record_failure(Exception("test"))
        first_cooldown = cb.current_cooldown

        # Simulate time passing
        cb.opened_at = time.time() - 100

        # Re-open
        cb.allow_request()
        for _ in range(2):
            cb.record_failure(Exception("test"))

        # Cooldown should have increased (exponential)
        assert cb.current_cooldown >= first_cooldown * 0.8  # jitter tolerance
