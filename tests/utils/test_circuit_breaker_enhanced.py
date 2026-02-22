"""Tests for enhanced API Circuit Breaker (Roadmap Task #10).

Focused on functional testing of per-endpoint circuit breakers,
fallback strategies, and Prometheus metrics integration.

Run with:
    pytest tests/utils/test_circuit_breaker_enhanced.py -v
"""

import asyncio
from unittest.mock import MagicMock

import httpx
import pytest
from circuitbreaker import CircuitBreakerError

from src.utils.api_circuit_breaker import (
    EndpointType,
    call_with_circuit_breaker,
    get_circuit_breaker,
    get_circuit_breaker_stats,
    reset_all_circuit_breakers,
    reset_circuit_breaker,
)


class TestEndpointTypes:
    """Test that different endpoint types exist and are independent."""

    def test_all_endpoint_types_avAlgolable(self):
        """Test all endpoint types can be retrieved."""
        endpoints = [
            EndpointType.MARKET,
            EndpointType.TARGETS,
            EndpointType.BALANCE,
            EndpointType.INVENTORY,
            EndpointType.TRADING,
        ]

        for endpoint_type in endpoints:
            breaker = get_circuit_breaker(endpoint_type)
            assert breaker is not None
            assert breaker._name.startswith("dmarket_")

    def test_breakers_are_singleton_per_endpoint(self):
        """Test that same breaker instance is returned for same endpoint."""
        breaker1 = get_circuit_breaker(EndpointType.MARKET)
        breaker2 = get_circuit_breaker(EndpointType.MARKET)

        assert breaker1 is breaker2


class TestCircuitBreakerCalls:
    """Test circuit breaker call protection."""

    @pytest.mark.asyncio()
    async def test_successful_call_returns_result(self):
        """Test successful API call returns correct result."""
        reset_circuit_breaker(EndpointType.MARKET)

        async def mock_api_call():
            return {"status": "success", "data": [1, 2, 3]}

        result = await call_with_circuit_breaker(
            mock_api_call,
            endpoint_type=EndpointType.MARKET,
        )

        assert result["status"] == "success"
        assert len(result["data"]) == 3

    @pytest.mark.asyncio()
    async def test_failed_call_raises_original_exception(self):
        """Test that failed calls raise the original exception."""
        reset_circuit_breaker(EndpointType.MARKET)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        with pytest.raises(httpx.HTTPStatusError):
            await call_with_circuit_breaker(
                mock_failing_call,
                endpoint_type=EndpointType.MARKET,
            )

    @pytest.mark.asyncio()
    async def test_fallback_executes_when_circuit_open(self):
        """Test fallback is executed when circuit breaker is open."""
        reset_circuit_breaker(EndpointType.MARKET)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        async def fallback():
            return {"status": "fallback", "data": []}

        # Trigger enough failures to open circuit (market has threshold of 5)
        for _ in range(6):
            try:
                await call_with_circuit_breaker(
                    mock_failing_call,
                    endpoint_type=EndpointType.MARKET,
                )
            except (httpx.HTTPStatusError, CircuitBreakerError):
                pass
            await asyncio.sleep(0.01)

        # Circuit should be open now, fallback should execute
        result = await call_with_circuit_breaker(
            mock_failing_call,
            endpoint_type=EndpointType.MARKET,
            fallback=fallback,
        )

        assert result["status"] == "fallback"
        assert result["data"] == []

    @pytest.mark.asyncio()
    async def test_no_fallback_raises_circuit_breaker_error(self):
        """Test that open circuit without fallback raises CircuitBreakerError."""
        reset_circuit_breaker(EndpointType.TARGETS)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        # Trigger failures (targets has threshold of 3)
        for _ in range(4):
            try:
                await call_with_circuit_breaker(
                    mock_failing_call,
                    endpoint_type=EndpointType.TARGETS,
                )
            except (httpx.HTTPStatusError, CircuitBreakerError):
                pass
            await asyncio.sleep(0.01)

        # Should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await call_with_circuit_breaker(
                mock_failing_call,
                endpoint_type=EndpointType.TARGETS,
            )


class TestCircuitBreakerStats:
    """Test circuit breaker statistics."""

    def test_stats_avAlgolable_for_initialized_breakers(self):
        """Test stats are avAlgolable for all initialized breakers."""
        # Initialize some breakers
        get_circuit_breaker(EndpointType.MARKET)
        get_circuit_breaker(EndpointType.TARGETS)

        stats = get_circuit_breaker_stats()

        assert "market" in stats
        assert "targets" in stats

    def test_stats_contain_required_fields(self):
        """Test that stats contain all required fields."""
        get_circuit_breaker(EndpointType.MARKET)
        stats = get_circuit_breaker_stats()

        assert "market" in stats
        market_stats = stats["market"]

        assert "state" in market_stats
        assert "failure_count" in market_stats
        assert "last_failure" in market_stats
        assert "config" in market_stats


class TestCircuitBreakerReset:
    """Test manual circuit breaker reset functionality."""

    @pytest.mark.asyncio()
    async def test_reset_single_breaker_changes_state(self):
        """Test that resetting a breaker changes its state to closed."""
        reset_circuit_breaker(EndpointType.BALANCE)
        breaker = get_circuit_breaker(EndpointType.BALANCE)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        # Trigger enough failures to open circuit (balance has threshold of 3)
        for _ in range(4):
            try:
                await call_with_circuit_breaker(
                    mock_failing_call,
                    endpoint_type=EndpointType.BALANCE,
                )
            except (httpx.HTTPStatusError, CircuitBreakerError):
                pass
            await asyncio.sleep(0.01)

        # Verify breaker is open or has failures
        assert breaker.failure_count > 0 or breaker.state == "open"

        # Reset should close it
        reset_circuit_breaker(EndpointType.BALANCE)
        
        # State should be closed after reset
        assert breaker.state == "closed"

    @pytest.mark.asyncio()
    async def test_reset_all_breakers_affects_multiple(self):
        """Test that reset_all affects all circuit breakers."""
        # Initialize and reset all first
        for endpoint_type in [EndpointType.MARKET, EndpointType.TARGETS, EndpointType.BALANCE]:
            reset_circuit_breaker(endpoint_type)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        # Trigger failures on multiple breakers
        breakers = []
        for endpoint_type in [EndpointType.MARKET, EndpointType.TARGETS, EndpointType.BALANCE]:
            breaker = get_circuit_breaker(endpoint_type)
            for _ in range(6):  # Trigger enough failures
                try:
                    await call_with_circuit_breaker(
                        mock_failing_call,
                        endpoint_type=endpoint_type,
                    )
                except (httpx.HTTPStatusError, CircuitBreakerError):
                    pass
                await asyncio.sleep(0.01)
            breakers.append(breaker)

        # Reset all
        reset_all_circuit_breakers()

        # All should be closed
        for breaker in breakers:
            assert breaker.state == "closed"


class TestDifferentEndpointBehavior:
    """Test that different endpoints behave independently."""

    @pytest.mark.asyncio()
    async def test_market_failure_does_not_affect_targets(self):
        """Test that failures in market endpoint don't affect targets endpoint."""
        reset_circuit_breaker(EndpointType.MARKET)
        reset_circuit_breaker(EndpointType.TARGETS)

        async def mock_failing_call():
            raise httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

        # FAlgol market endpoint multiple times
        for _ in range(6):
            try:
                await call_with_circuit_breaker(
                    mock_failing_call,
                    endpoint_type=EndpointType.MARKET,
                )
            except (httpx.HTTPStatusError, CircuitBreakerError):
                pass
            await asyncio.sleep(0.01)

        # Market should be affected
        market_breaker = get_circuit_breaker(EndpointType.MARKET)
        market_state = market_breaker.state

        # Targets should still be in good state
        targets_breaker = get_circuit_breaker(EndpointType.TARGETS)
        targets_state = targets_breaker.state

        # They should be different
        assert market_state == "open"
        assert targets_state == "closed"


class TestPrometheusMetricsIntegration:
    """Test basic Prometheus metrics integration."""

    @pytest.mark.asyncio()
    async def test_metrics_functions_dont_crash(self):
        """Test that metrics tracking doesn't cause crashes."""
        reset_circuit_breaker(EndpointType.MARKET)

        async def mock_api_call():
            return {"success": True}

        # Should not raise even if prometheus module missing
        result = await call_with_circuit_breaker(
            mock_api_call,
            endpoint_type=EndpointType.MARKET,
        )

        assert result["success"] is True
