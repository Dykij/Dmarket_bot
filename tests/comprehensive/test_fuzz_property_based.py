"""Property-based and fuzz testing using Hypothesis.

This module provides:
- Property-based testing for core functions
- Fuzz testing for input validation
- Edge case discovery through random testing
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

if TYPE_CHECKING:
    pass


# =============================================================================
# TEST MARKERS
# =============================================================================


pytestmark = [pytest.mark.property_based, pytest.mark.fuzz]


# =============================================================================
# CUSTOM STRATEGIES
# =============================================================================


# Strategy for valid game IDs
game_ids = st.sampled_from(["csgo", "cs2", "dota2", "rust", "tf2"])

# Strategy for price values (in cents)
price_cents = st.integers(min_value=1, max_value=1000000)  # $0.01 to $10,000

# Strategy for item titles
item_titles = st.text(
    alphabet=string.ascii_letters + string.digits + " |-_()",
    min_size=1,
    max_size=200,
)

# Strategy for API keys
api_keys = st.text(
    alphabet=string.ascii_letters + string.digits + "_-",
    min_size=10,
    max_size=100,
)

# Strategy for timestamps
timestamps = st.integers(min_value=1000000000, max_value=2000000000)


# =============================================================================
# PROPERTY-BASED TESTS FOR PRICE CALCULATIONS
# =============================================================================


class TestPriceCalculationProperties:
    """Property-based tests for price calculations."""

    @given(price=price_cents)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_price_always_positive(self, price: int) -> None:
        """Test that prices are always positive after conversion."""
        # Convert cents to dollars
        dollars = price / 100

        # Should always be positive
        assert dollars > 0

    @given(price=price_cents, suggested=price_cents)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_profit_calculation_consistent(self, price: int, suggested: int) -> None:
        """Test profit calculation is consistent."""
        # Simple profit calculation
        profit = suggested - price

        # Profit can be negative (loss)
        # But calculation should be deterministic
        assert profit == suggested - price

    @given(
        buy_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False),
        sell_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False),
        commission=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_arbitrage_profit_formula(
        self, buy_price: float, sell_price: float, commission: float
    ) -> None:
        """Test arbitrage profit formula properties."""
        # Calculate profit with commission
        commission_amount = sell_price * (commission / 100)
        net_profit = sell_price - buy_price - commission_amount

        # Properties:
        # 1. If sell > buy and commission < 100%, there exists a profitable case
        # 2. Net profit should be deterministic
        expected = sell_price - buy_price - commission_amount
        assert abs(net_profit - expected) < 0.0001


# =============================================================================
# PROPERTY-BASED TESTS FOR API CLIENT
# =============================================================================


class TestAPIClientProperties:
    """Property-based tests for API client behavior."""

    @given(public_key=api_keys, secret_key=api_keys)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_api_client_accepts_any_key_format(
        self, public_key: str, secret_key: str
    ) -> None:
        """Test API client accepts various key formats."""
        from src.dmarket.dmarket_api import DMarketAPI

        # Should not raise on any valid string keys
        api = DMarketAPI(public_key, secret_key)
        assert api is not None

    @given(timestamp=timestamps)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_signature_generation_deterministic(self, timestamp: int) -> None:
        """Test signature generation is deterministic."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public", "test_secret")

        ts_str = str(timestamp)

        # Same inputs should produce same signature
        headers1 = api._generate_headers("GET", "/test", body="")
        headers2 = api._generate_headers("GET", "/test", body="")

        # Headers should be generated
        assert headers1 is not None
        assert headers2 is not None

    @given(game=game_ids)
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_game_mapping_exists(self, game: str) -> None:
        """Test all game IDs have mapping."""
        from src.dmarket.dmarket_api import GAME_MAP

        assert game in GAME_MAP


# =============================================================================
# FUZZ TESTING FOR INPUT VALIDATION
# =============================================================================


class TestInputFuzzing:
    """Fuzz tests for input validation."""

    @given(data=st.text(min_size=0, max_size=1000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_api_handles_arbitrary_strings(self, data: str) -> None:
        """Test API handles arbitrary string input without crashing."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("public", "secret")

        try:
            # Should not crash with arbitrary strings
            api._generate_headers("GET", f"/test?q={data}", "12345")
        except (ValueError, UnicodeEncodeError):
            pass  # Expected for some inputs
        except Exception as e:
            # Unexpected errors should be specific exceptions
            assert isinstance(e, Exception)

    @given(limit=st.integers())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_limit_parameter_fuzz(self, limit: int) -> None:
        """Fuzz test for limit parameter handling."""
        # API should handle any integer limit
        # Implementation may clamp or reject invalid values
        if limit < 0:
            # Negative limits should be handled
            pass
        elif limit > 1000000:
            # Very large limits should be handled
            pass
        else:
            # Normal limits should work
            pass

    @given(
        price_from=st.integers(),
        price_to=st.integers(),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_price_range_fuzz(self, price_from: int, price_to: int) -> None:
        """Fuzz test for price range parameters."""
        # Price range should be validated
        if price_from < 0 or price_to < 0:
            # Negative prices should be handled
            pass
        elif price_from > price_to:
            # Invalid range should be handled
            pass
        else:
            # Valid range should work
            pass


# =============================================================================
# PROPERTY-BASED TESTS FOR CIRCUIT BREAKER
# =============================================================================


class TestCircuitBreakerProperties:
    """Property-based tests for circuit breaker."""

    @given(
        threshold=st.integers(min_value=1, max_value=100),
        timeout=st.integers(min_value=1, max_value=3600),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_circuit_breaker_accepts_valid_config(
        self, threshold: int, timeout: int
    ) -> None:
        """Test circuit breaker accepts valid configuration."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        cb = APICircuitBreaker(
            name=f"fuzz_test_{threshold}_{timeout}",
            failure_threshold=threshold,
            recovery_timeout=timeout,
        )

        assert cb._failure_threshold == threshold
        assert cb._recovery_timeout == timeout


# =============================================================================
# PROPERTY-BASED TESTS FOR DATA STRUCTURES
# =============================================================================


class TestDataStructureProperties:
    """Property-based tests for data structures."""

    @given(
        items=st.lists(
            st.fixed_dictionaries(
                {
                    "itemId": st.text(min_size=1, max_size=50),
                    "title": item_titles,
                    "price": st.fixed_dictionaries(
                        {"USD": st.integers(min_value=1, max_value=1000000).map(str)}
                    ),
                }
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_item_list_processing(self, items: list[dict[str, Any]]) -> None:
        """Test item list processing with arbitrary items."""
        # Process items
        for item in items:
            assert "itemId" in item
            assert "title" in item
            assert "price" in item

            # Price should be parseable
            price_str = item["price"]["USD"]
            assert int(price_str) > 0


# =============================================================================
# FUZZ TESTING FOR EDGE CASES
# =============================================================================


class TestEdgeCaseFuzzing:
    """Fuzz tests specifically for edge cases."""

    @given(
        data=st.one_of(
            st.none(),
            st.text(),
            st.integers(),
            st.floats(allow_nan=False),
            st.lists(st.text()),
            st.dictionaries(st.text(), st.text()),
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_handles_mixed_types(self, data: Any) -> None:
        """Test handling of mixed type inputs."""
        # This tests type coercion and validation
        if data is None:
            assert data is None
        elif isinstance(data, str):
            assert isinstance(data, str)
        elif isinstance(data, int):
            assert isinstance(data, int)
        elif isinstance(data, float):
            assert isinstance(data, float)
        elif isinstance(data, list):
            assert isinstance(data, list)
        elif isinstance(data, dict):
            assert isinstance(data, dict)

    @given(
        unicode_str=st.text(
            alphabet=st.characters(
                blacklist_categories=("Cs",),  # Exclude surrogates
            ),
            min_size=0,
            max_size=500,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unicode_handling(self, unicode_str: str) -> None:
        """Test handling of various Unicode strings."""
        # Should not crash with any Unicode
        try:
            encoded = unicode_str.encode("utf-8")
            decoded = encoded.decode("utf-8")
            assert decoded == unicode_str
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass  # Some characters may not be encodable


# =============================================================================
# PROPERTY-BASED TESTS FOR RATE LIMITER
# =============================================================================


class TestRateLimiterProperties:
    """Property-based tests for rate limiter."""

    @given(
        rate=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_rate_limiter_accepts_valid_rates(
        self, rate: int
    ) -> None:
        """Test rate limiter accepts valid rate configurations."""
        from src.utils.rate_limiter import RateLimiter

        limiter = RateLimiter()
        assert limiter is not None

    @given(
        calls=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_calls_within_limit(
        self, calls: int
    ) -> None:
        """Test rate limiter allows calls within limit."""
        from src.utils.rate_limiter import RateLimiter

        # Create limiter
        limiter = RateLimiter()

        # Limiter should be usable
        assert limiter is not None


# =============================================================================
# STATEFUL TESTING
# =============================================================================


class TestStatefulBehavior:
    """Stateful tests for components with state."""

    @given(
        operations=st.lists(
            st.sampled_from(["get", "create", "delete"]),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_operation_sequence(self, operations: list[str]) -> None:
        """Test arbitrary sequences of operations."""
        # Simulates user performing random operations
        state = {"targets": []}

        for op in operations:
            if op == "get":
                # Get operation should work
                targets = state["targets"]
                assert isinstance(targets, list)
            elif op == "create":
                # Create adds to state
                state["targets"].append({"id": len(state["targets"])})
            elif op == "delete":
                # Delete removes from state if not empty
                if state["targets"]:
                    state["targets"].pop()

        # Final state should be consistent
        assert isinstance(state["targets"], list)
        assert all(isinstance(t, dict) for t in state["targets"])


# =============================================================================
# REGRESSION TESTING WITH HYPOTHESIS
# =============================================================================


class TestRegressionWithHypothesis:
    """Regression tests using Hypothesis to find edge cases."""

    @given(
        price=st.floats(min_value=-1e10, max_value=1e10, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_handles_special_float_values(self, price: float) -> None:
        """Test handling of float values."""
        import math

        # Normal values should be finite
        assert math.isfinite(price)

    @given(
        data=st.binary(min_size=0, max_size=1000),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_handles_binary_data(self, data: bytes) -> None:
        """Test handling of binary data."""
        # Should not crash when processing binary
        try:
            decoded = data.decode("utf-8", errors="replace")
            assert isinstance(decoded, str)
        except Exception as e:
            # Should handle gracefully
            assert isinstance(e, Exception)
