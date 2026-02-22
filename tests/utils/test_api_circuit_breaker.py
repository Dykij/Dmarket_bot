"""Unit tests for api_circuit_breaker module.

This module contains tests for src/utils/api_circuit_breaker.py covering:
- APICircuitBreaker initialization
- Circuit breaker constants
- call_with_circuit_breaker function

Target: 20+ tests to achieve 70%+ coverage
"""

import httpx
import pytest

from src.utils.api_circuit_breaker import (
    APICircuitBreaker,
    _circuit_breakers,
    call_with_circuit_breaker,
    dmarket_api_breaker,
)


@pytest.fixture(autouse=True)
def reset_circuit_breakers_before_test():
    """Reset all circuit breakers before each test to ensure isolation."""
    # Clear the internal breaker storage
    _circuit_breakers.clear()
    # Reset the legacy dmarket_api_breaker
    try:
        dmarket_api_breaker._failure_count = 0
        dmarket_api_breaker._state = "closed"
    except AttributeError:
        pass  # Some implementations may differ
    yield
    # Cleanup after test
    _circuit_breakers.clear()


# TestAPICircuitBreakerInit


class TestAPICircuitBreakerInit:
    """Tests for APICircuitBreaker initialization."""

    def test_init_with_name(self):
        """Test initialization with name."""
        # Act
        breaker = APICircuitBreaker(name="test_api")

        # Assert
        assert breaker.name == "test_api"

    def test_init_without_name(self):
        """Test initialization without name."""
        # Act
        breaker = APICircuitBreaker()

        # Assert
        assert breaker is not None

    def test_failure_threshold_constant(self):
        """Test FAlgoLURE_THRESHOLD constant."""
        assert APICircuitBreaker.FAlgoLURE_THRESHOLD == 5

    def test_recovery_timeout_constant(self):
        """Test RECOVERY_TIMEOUT constant."""
        assert APICircuitBreaker.RECOVERY_TIMEOUT == 60

    def test_expected_exception_constant(self):
        """Test EXPECTED_EXCEPTION constant."""
        assert httpx.HTTPError == APICircuitBreaker.EXPECTED_EXCEPTION


# TestGlobalInstance


class TestGlobalInstance:
    """Tests for global circuit breaker instance."""

    def test_dmarket_api_breaker_exists(self):
        """Test that dmarket_api_breaker exists."""
        assert dmarket_api_breaker is not None

    def test_dmarket_api_breaker_name(self):
        """Test dmarket_api_breaker name."""
        assert dmarket_api_breaker.name == "dmarket_api"

    def test_dmarket_api_breaker_is_instance(self):
        """Test that dmarket_api_breaker is APICircuitBreaker instance."""
        assert isinstance(dmarket_api_breaker, APICircuitBreaker)


# TestCallWithCircuitBreaker


class TestCallWithCircuitBreaker:
    """Tests for call_with_circuit_breaker function."""

    @pytest.mark.asyncio()
    async def test_successful_call(self):
        """Test successful function call."""

        # Arrange
        async def success_func():
            return "success"

        # Act
        result = await call_with_circuit_breaker(success_func)

        # Assert
        assert result == "success"

    @pytest.mark.asyncio()
    async def test_call_with_args(self):
        """Test call with positional arguments."""

        # Arrange
        async def func_with_args(a, b):
            return a + b

        # Act
        result = await call_with_circuit_breaker(func_with_args, 1, 2)

        # Assert
        assert result == 3

    @pytest.mark.asyncio()
    async def test_call_with_kwargs(self):
        """Test call with keyword arguments."""

        # Arrange
        async def func_with_kwargs(name="default"):
            return f"hello {name}"

        # Act
        result = await call_with_circuit_breaker(func_with_kwargs, name="test")

        # Assert
        assert result == "hello test"

    @pytest.mark.asyncio()
    async def test_call_returns_value(self):
        """Test that call returns the function's return value."""
        # Arrange
        expected = {"key": "value", "count": 42}

        async def return_dict():
            return expected

        # Act
        result = await call_with_circuit_breaker(return_dict)

        # Assert
        assert result == expected


# TestEdgeCases


class TestCircuitBreakerEdgeCases:
    """Tests for edge cases."""

    def test_create_multiple_breakers(self):
        """Test creating multiple circuit breakers."""
        # Act
        breaker1 = APICircuitBreaker(name="api1")
        breaker2 = APICircuitBreaker(name="api2")

        # Assert
        assert breaker1.name == "api1"
        assert breaker2.name == "api2"
        assert breaker1 is not breaker2

    def test_breaker_inherits_from_circuit_breaker(self):
        """Test that APICircuitBreaker inherits properly."""
        # Arrange
        from circuitbreaker import CircuitBreaker

        # Act
        breaker = APICircuitBreaker(name="test")

        # Assert
        assert isinstance(breaker, CircuitBreaker)

    @pytest.mark.asyncio()
    async def test_call_async_function(self):
        """Test calling an async function."""

        # Arrange
        async def async_func():
            return "async result"

        # Act
        result = await call_with_circuit_breaker(async_func)

        # Assert
        assert result == "async result"

    @pytest.mark.asyncio()
    async def test_call_with_none_fallback(self):
        """Test call with fallback=None."""

        # Arrange
        async def success_func():
            return "success"

        # Act
        result = await call_with_circuit_breaker(success_func, fallback=None)

        # Assert
        assert result == "success"


# TestCircuitBreakerConfiguration


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configuration."""

    def test_custom_breaker_params(self):
        """Test that custom parameters are applied."""
        # Arrange & Act
        breaker = APICircuitBreaker(name="custom")

        # Assert - inherits class constants
        assert breaker._failure_threshold == APICircuitBreaker.FAlgoLURE_THRESHOLD
        assert breaker._recovery_timeout == APICircuitBreaker.RECOVERY_TIMEOUT

    def test_expected_exception_is_http_error(self):
        """Test that expected exception is httpx.HTTPError."""
        # Assert
        assert APICircuitBreaker.EXPECTED_EXCEPTION is httpx.HTTPError

    def test_failure_threshold_is_reasonable(self):
        """Test that failure threshold is reasonable."""
        # Assert - should be between 1 and 20
        assert 1 <= APICircuitBreaker.FAlgoLURE_THRESHOLD <= 20

    def test_recovery_timeout_is_reasonable(self):
        """Test that recovery timeout is reasonable."""
        # Assert - should be between 10 and 300 seconds
        assert 10 <= APICircuitBreaker.RECOVERY_TIMEOUT <= 300
