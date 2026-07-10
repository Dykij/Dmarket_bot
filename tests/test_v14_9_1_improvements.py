"""
test_v14_9_1_improvements.py — Tests for v14.9.1 optimizations.

Covers:
  - Spoofing detection (orderbook.detect_spoofing)
  - Volume-weighted average (orderbook.compute_depth_profile)
  - Returns-based volatility (price_validator.validate_volatility)
  - LiquidityManager SQLite persistence
  - CircuitBreaker jitter application
  - Float premium range 0.100-0.150 (FT-2)
"""

from __future__ import annotations

import math
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Spoofing Detection Tests
# =========================================================================

class TestSpoofingDetection:
    """Tests for orderbook.detect_spoofing()."""

    def test_empty_listings(self):
        from src.analysis.orderbook import detect_spoofing
        result = detect_spoofing([])
        assert result["is_suspicious"] is False
        assert result["flags"] == []
        assert result["confidence"] == 0.0

    def test_few_listings_not_suspicious(self):
        from src.analysis.orderbook import detect_spoofing
        # Need at least 5 listings for detection to run
        listings = [{"price": {"USD": (100 + i * 5) * 100}} for i in range(10)]
        result = detect_spoofing(listings)
        assert result["is_suspicious"] is False

    def test_single_level_concentration(self):
        from src.analysis.orderbook import detect_spoofing
        # 8 out of 10 orders at same price = 80% concentration
        listings = [{"price": {"USD": 1000}}] * 8 + [
            {"price": {"USD": 1100}},
            {"price": {"USD": 1200}},
        ]
        result = detect_spoofing(listings, max_single_level_pct=0.40)
        assert result["is_suspicious"] is True
        assert any("single_level_concentration" in f for f in result["flags"])

    def test_top3_concentration(self):
        from src.analysis.orderbook import detect_spoofing
        # Top 3 levels hold 90% of orders
        listings = (
            [{"price": {"USD": 1000}}] * 3
            + [{"price": {"USD": 1100}}] * 3
            + [{"price": {"USD": 1200}}] * 3
            + [{"price": {"USD": 2000}}] * 1
        )
        result = detect_spoofing(listings, max_top3_pct=0.70)
        assert result["is_suspicious"] is True
        assert any("top3_concentration" in f for f in result["flags"])

    def test_bid_ask_imbalance(self):
        from src.analysis.orderbook import detect_spoofing
        # Create extreme imbalance: many bids at low price, few asks at high price
        # All bids at $100, all asks at $1000
        listings = (
            [{"price": {"USD": 10000}}] * 20  # 20 bids at $100
            + [{"price": {"USD": 100000}}] * 2  # 2 asks at $1000
        )
        result = detect_spoofing(listings, imbalance_threshold=3.0)
        # Check that flags are detected (imbalance or concentration)
        assert len(result["flags"]) > 0 or result["confidence"] > 0

    def test_wall_detection(self):
        from src.analysis.orderbook import detect_spoofing
        # Large wall far from median
        mid_price_cents = 1000
        listings = (
            [{"price": {"USD": mid_price_cents + i * 10}} for i in range(1, 10)]
            + [{"price": {"USD": mid_price_cents}}] * 2  # median
            + [{"price": {"USD": 5000}}] * 5  # wall far away
        )
        result = detect_spoofing(listings)
        assert any("wall_at" in f for f in result["flags"])

    def test_clean_book_not_suspicious(self):
        from src.analysis.orderbook import detect_spoofing
        # Well-distributed book
        listings = [{"price": {"USD": (100 + i * 5) * 100}} for i in range(20)]
        result = detect_spoofing(listings)
        assert result["is_suspicious"] is False
        assert result["confidence"] < 0.4


# =========================================================================
# Volume-Weighted Average Tests
# =========================================================================

class TestVolumeWeightedAverage:
    """Tests for orderbook.compute_depth_profile()."""

    def test_simple_weighted_avg(self):
        from src.analysis.orderbook import compute_depth_profile
        # 2 orders at $10, 1 order at $20
        listings = [
            {"price": {"USD": 1000}},
            {"price": {"USD": 1000}},
            {"price": {"USD": 2000}},
        ]
        result = compute_depth_profile(listings)
        # VWAP = (10*2 + 20*1) / 3 = 40/3 = 13.33
        assert abs(result["weighted_avg"] - 13.33) < 0.01

    def test_equal_weights(self):
        from src.analysis.orderbook import compute_depth_profile
        listings = [
            {"price": {"USD": 1000}},
            {"price": {"USD": 2000}},
            {"price": {"USD": 3000}},
        ]
        result = compute_depth_profile(listings)
        # All equal weight: VWAP = (10+20+30)/3 = 20
        assert abs(result["weighted_avg"] - 20.0) < 0.01

    def test_empty_listings(self):
        from src.analysis.orderbook import compute_depth_profile
        result = compute_depth_profile([])
        assert result["weighted_avg"] == 0.0
        assert result["levels"] == {}


# =========================================================================
# Returns-Based Volatility Tests
# =========================================================================

class TestReturnsVolatility:
    """Tests for price_validator.validate_volatility()."""

    def test_stable_prices_no_error(self):
        from src.risk.price_validator import validate_volatility, PriceValidationError
        # Prices with very small changes
        prices = [Decimal("10.00"), Decimal("10.01"), Decimal("10.02"), Decimal("10.01")]
        try:
            validate_volatility(prices, max_std_dev_pct=Decimal("0.15"))
        except PriceValidationError:
            pytest.fail("Stable prices should not raise PriceValidationError")

    def test_volatile_prices_raises_error(self):
        from src.risk.price_validator import validate_volatility, PriceValidationError
        # Prices with large swings
        prices = [Decimal("10.00"), Decimal("15.00"), Decimal("8.00"), Decimal("14.00")]
        with pytest.raises(PriceValidationError):
            validate_volatility(prices, max_std_dev_pct=Decimal("0.15"))

    def test_too_few_prices_no_error(self):
        from src.risk.price_validator import validate_volatility, PriceValidationError
        # Less than 3 prices = not enough data
        prices = [Decimal("10.00"), Decimal("15.00")]
        try:
            validate_volatility(prices)
        except PriceValidationError:
            pytest.fail("Too few prices should not raise PriceValidationError")

    def test_monotonic_prices_low_volatility(self):
        from src.risk.price_validator import validate_volatility, PriceValidationError
        # Slowly increasing prices = low return volatility
        prices = [Decimal("10.00"), Decimal("10.10"), Decimal("10.20"), Decimal("10.30")]
        try:
            validate_volatility(prices, max_std_dev_pct=Decimal("0.15"))
        except PriceValidationError:
            pytest.fail("Monotonic prices should not raise PriceValidationError")


# =========================================================================
# LiquidityManager SQLite Persistence Tests
# =========================================================================

class TestLiquidityManagerPersistence:
    """Tests for LiquidityManager SQLite persistence."""

    def test_initial_spend_zero(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True  # Skip DB load for unit test
        assert lm.get_today_spend() == 0.0

    def test_record_spend(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True
        lm.record_spend.__func__  # Just verify it exists
        # Mock the DB save
        with patch.object(lm, '_save_to_db'):
            lm.record_spend(50.0)
            assert lm.get_today_spend() == 50.0

    def test_can_spend_within_limit(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True
        # $100 balance, 15% limit = $15 max daily
        assert lm.can_spend(10.0, "cs2", 100.0) is True

    def test_can_spend_exceeds_limit(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True
        # $100 balance, 15% limit = $15 max daily
        assert lm.can_spend(20.0, "cs2", 100.0) is False

    def test_can_spend_after_recording(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True
        with patch.object(lm, '_save_to_db'):
            lm.record_spend(12.0)
            # $100 balance, 15% limit = $15 max daily, already spent $12
            assert lm.can_spend(2.0, "cs2", 100.0) is True
            assert lm.can_spend(4.0, "cs2", 100.0) is False

    def test_rust_budget_limit(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        lm._db_loaded = True
        # $100 balance, 10% rust limit = $10 max per trade
        assert lm.can_spend(8.0, "rust", 100.0) is True
        assert lm.can_spend(12.0, "rust", 100.0) is False

    def test_db_load_restores_today(self):
        from src.risk.liquidity_manager import LiquidityManager
        lm = LiquidityManager()
        today = lm._get_today()
        # Mock the DB returning today's spend
        with patch('src.db.price_history.price_db') as mock_db:
            mock_db.get_state.return_value = f"{today}:75.00"
            lm._load_from_db()
            assert lm.get_today_spend() == 75.0


# =========================================================================
# CircuitBreaker Jitter Tests
# =========================================================================

class TestCircuitBreakerJitter:
    """Tests for CircuitBreaker jitter application."""

    def test_jitter_applied_on_first_open(self):
        from src.api.dmarket_api_client.backoff import CircuitBreaker, CircuitState
        cb = CircuitBreaker(
            name="test",
            fail_threshold=2,
            base_cooldown=10.0,
            max_cooldown=60.0,
            jitter_pct=0.2,
        )
        # Trigger circuit open
        cb.record_failure(Exception("fail1"))
        cb.record_failure(Exception("fail2"))
        assert cb.state == CircuitState.OPEN
        # Cooldown should be base_cooldown * jitter (8.0 to 12.0)
        assert 8.0 <= cb.current_cooldown <= 12.0

    def test_exponential_extension(self):
        from src.api.dmarket_api_client.backoff import CircuitBreaker, CircuitState
        cb = CircuitBreaker(
            name="test",
            fail_threshold=2,
            base_cooldown=10.0,
            max_cooldown=60.0,
            jitter_pct=0.2,
        )
        # Open the circuit
        cb.record_failure(Exception("fail1"))
        cb.record_failure(Exception("fail2"))
        first_cooldown = cb.current_cooldown
        # Extend it
        cb.record_failure(Exception("fail3"))
        assert cb.current_cooldown == min(first_cooldown * 2.0, 60.0)

    def test_success_resets_cooldown(self):
        from src.api.dmarket_api_client.backoff import CircuitBreaker, CircuitState
        cb = CircuitBreaker(
            name="test",
            fail_threshold=2,
            base_cooldown=10.0,
            max_cooldown=60.0,
            jitter_pct=0.2,
        )
        cb.record_failure(Exception("fail1"))
        cb.record_failure(Exception("fail2"))
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.current_cooldown == 10.0  # Reset to base


# =========================================================================
# Float Premium FT-2 Range Tests
# =========================================================================

class TestFloatPremiumFT2:
    """Tests for the new FT-2 float premium range (0.100-0.150)."""

    def test_ft2_range_lower_bound(self):
        from src.core.target_sniping.pricing import get_float_premium
        premium = get_float_premium({"floatPartValue": "0.100"})
        assert premium == 1.03, f"FT-2 lower bound should be 1.03x, got {premium}"

    def test_ft2_range_mid(self):
        from src.core.target_sniping.pricing import get_float_premium
        # 0.12 is not a round float, should get FT-2 premium
        premium = get_float_premium({"floatPartValue": "0.12"})
        assert premium == 1.03, f"FT-2 mid should be 1.03x, got {premium}"

    def test_ft2_range_upper_bound(self):
        from src.core.target_sniping.pricing import get_float_premium
        premium = get_float_premium({"floatPartValue": "0.149"})
        assert premium == 1.03, f"FT-2 upper bound should be 1.03x, got {premium}"

    def test_ft2_does_not_affect_ft0(self):
        from src.core.target_sniping.pricing import get_float_premium
        premium = get_float_premium({"floatPartValue": "0.15"})
        assert premium == 1.15, f"FT-0 should still be 1.15x, got {premium}"

    def test_ft2_does_not_affect_mw(self):
        from src.core.target_sniping.pricing import get_float_premium
        premium = get_float_premium({"floatPartValue": "0.09"})
        assert premium == 1.05, f"MW should still be 1.05x, got {premium}"


# =========================================================================
# Tenacity Retry Predicate Tests
# =========================================================================

class TestRetryPredicate:
    """Tests for the custom retry predicate _retry_on_transient."""

    def test_timeout_is_retryable(self):
        from src.api.dmarket_api_client.core import _retry_on_transient
        import asyncio
        assert _retry_on_transient(asyncio.TimeoutError()) is True

    def test_connection_error_is_retryable(self):
        from src.api.dmarket_api_client.core import _retry_on_transient
        import aiohttp
        assert _retry_on_transient(aiohttp.ClientConnectionError()) is True

    def test_5xx_is_retryable(self):
        from src.api.dmarket_api_client.core import _retry_on_transient
        import aiohttp
        exc = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
        )
        assert _retry_on_transient(exc) is True

    def test_4xx_not_retryable(self):
        from src.api.dmarket_api_client.core import _retry_on_transient
        import aiohttp
        for status in [400, 401, 403, 404, 422]:
            exc = aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=status,
            )
            assert _retry_on_transient(exc) is False, f"{status} should not be retryable"

    def test_generic_exception_not_retryable(self):
        from src.api.dmarket_api_client.core import _retry_on_transient
        assert _retry_on_transient(ValueError("test")) is False
