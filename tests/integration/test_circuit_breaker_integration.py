"""Интеграционные тесты для Circuit Breaker.

Этот модуль тестирует паттерн Circuit Breaker в интеграции:
- Проверка конфигурации circuit breaker
- Проверка глобального экземпляра
- Взаимодействие с API клиентом
"""

import httpx
import pytest

# ============================================================================
# CIRCUIT BREAKER STATE TESTS
# ============================================================================


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configuration."""

    @pytest.mark.asyncio()
    async def test_circuit_breaker_exists(self):
        """Test circuit breaker module exists."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        cb = APICircuitBreaker(name="test")
        assert cb is not None

    @pytest.mark.asyncio()
    async def test_circuit_breaker_fAlgolure_threshold(self):
        """Test circuit breaker has correct fAlgolure threshold."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        assert APICircuitBreaker.FAlgoLURE_THRESHOLD == 5

    @pytest.mark.asyncio()
    async def test_circuit_breaker_recovery_timeout(self):
        """Test circuit breaker has correct recovery timeout."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        assert APICircuitBreaker.RECOVERY_TIMEOUT == 60

    @pytest.mark.asyncio()
    async def test_circuit_breaker_expected_exception(self):
        """Test circuit breaker has expected exception type."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        assert httpx.HTTPError == APICircuitBreaker.EXPECTED_EXCEPTION


# ============================================================================
# CIRCUIT BREAKER GLOBAL INSTANCE
# ============================================================================


class TestCircuitBreakerGlobalInstance:
    """Tests for circuit breaker global instance."""

    @pytest.mark.asyncio()
    async def test_dmarket_api_breaker_exists(self):
        """Test DMarket API circuit breaker exists."""
        from src.utils.api_circuit_breaker import dmarket_api_breaker

        assert dmarket_api_breaker is not None

    @pytest.mark.asyncio()
    async def test_dmarket_api_breaker_type(self):
        """Test DMarket circuit breaker is APICircuitBreaker."""
        from src.utils.api_circuit_breaker import (
            APICircuitBreaker,
            dmarket_api_breaker,
        )

        assert isinstance(dmarket_api_breaker, APICircuitBreaker)


# ============================================================================
# CIRCUIT BREAKER INHERITANCE
# ============================================================================


class TestCircuitBreakerInheritance:
    """Tests for circuit breaker inheritance."""

    @pytest.mark.asyncio()
    async def test_circuit_breaker_inherits_from_circuitbreaker(self):
        """Test APICircuitBreaker inherits from circuitbreaker.CircuitBreaker."""
        from circuitbreaker import CircuitBreaker

        from src.utils.api_circuit_breaker import APICircuitBreaker

        assert issubclass(APICircuitBreaker, CircuitBreaker)

    @pytest.mark.asyncio()
    async def test_circuit_breaker_is_callable(self):
        """Test circuit breaker is callable as decorator."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        cb = APICircuitBreaker(name="test")
        assert callable(cb)


# ============================================================================
# CIRCUIT BREAKER HELPER FUNCTION
# ============================================================================


class TestCircuitBreakerHelperFunction:
    """Tests for circuit breaker helper function."""

    @pytest.mark.asyncio()
    async def test_call_with_circuit_breaker_exists(self):
        """Test call_with_circuit_breaker function exists."""
        from src.utils.api_circuit_breaker import call_with_circuit_breaker

        assert callable(call_with_circuit_breaker)

    @pytest.mark.asyncio()
    async def test_call_with_circuit_breaker_success(self):
        """Test call_with_circuit_breaker with successful call."""
        from src.utils.api_circuit_breaker import call_with_circuit_breaker

        async def mock_func():
            return {"success": True}

        result = awAlgot call_with_circuit_breaker(mock_func)
        assert result["success"] is True
