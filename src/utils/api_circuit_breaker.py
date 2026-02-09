from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypeVar

import httpx
from circuitbreaker import CircuitBreaker, CircuitBreakerError  # type: ignore
from structlog import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class EndpointType(StrEnum):
    """Types of API endpoints with different reliability requirements."""

    MARKET = "market"  # Market data - high volume, tolerate failures
    TARGETS = "targets"  # Buy orders - critical, low tolerance
    BALANCE = "balance"  # Balance checks - medium priority
    INVENTORY = "inventory"  # Inventory - medium priority
    TRADING = "trading"  # Trading operations - critical


class APICircuitBreaker(CircuitBreaker):
    """Circuit breaker for API calls with configurable thresholds.

    Roadmap Task #10: Per-endpoint circuit breakers with custom config.
    """

    # Default configuration
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60
    EXPECTED_EXCEPTION = httpx.HTTPError

    def __init__(
        self,
        name: str | None = None,
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
        expected_exception: type[Exception] | tuple[type[Exception], ...] | None = None,
    ):
        """Initialize circuit breaker with custom or default config.

        Args:
            name: Circuit breaker identifier
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception types to count as failures
        """
        super().__init__(
            name=name,
            failure_threshold=failure_threshold or self.FAILURE_THRESHOLD,
            recovery_timeout=recovery_timeout or self.RECOVERY_TIMEOUT,
            expected_exception=expected_exception or self.EXPECTED_EXCEPTION,
        )
        self._state_change_callback = self._on_state_change

    def _on_state_change(
        self,
        cb: "CircuitBreaker",
        old_state: str,
        new_state: str,
    ) -> None:
        """Log state changes and update metrics.

        Args:
            cb: Circuit breaker instance
            old_state: Previous state (closed, open, half_open)
            new_state: New state
        """
        logger.warning(
            "circuit_breaker_state_change",
            circuit=cb.name,
            old_state=str(old_state),
            new_state=str(new_state),
        )

        # Update Prometheus metrics
        try:
            from src.utils.prometheus_metrics import (
                track_circuit_breaker_state,
                track_circuit_breaker_state_change,
            )

            endpoint_name = cb.name or "unknown"
            track_circuit_breaker_state(endpoint_name, str(new_state))
            track_circuit_breaker_state_change(
                endpoint_name,
                str(old_state),
                str(new_state),
            )
        except ImportError:
            pass  # Prometheus not available


# Per-endpoint circuit breaker configurations
ENDPOINT_CONFIGS = {
    EndpointType.MARKET: {
        "failure_threshold": 5,  # Higher tolerance for market data
        "recovery_timeout": 60,  # Quick recovery (1 min)
        "expected_exception": (httpx.HTTPError, httpx.TimeoutException),
    },
    EndpointType.TARGETS: {
        "failure_threshold": 3,  # Low tolerance for critical operations
        "recovery_timeout": 120,  # Slower recovery (2 min)
        "expected_exception": httpx.HTTPError,
    },
    EndpointType.BALANCE: {
        "failure_threshold": 4,
        "recovery_timeout": 90,
        "expected_exception": httpx.HTTPError,
    },
    EndpointType.INVENTORY: {
        "failure_threshold": 4,
        "recovery_timeout": 90,
        "expected_exception": httpx.HTTPError,
    },
    EndpointType.TRADING: {
        "failure_threshold": 2,  # Very low tolerance for trading
        "recovery_timeout": 180,  # Long recovery (3 min)
        "expected_exception": httpx.HTTPError,
    },
}


# Create per-endpoint circuit breaker instances
_circuit_breakers: dict[str, APICircuitBreaker] = {}


def get_circuit_breaker(endpoint_type: EndpointType) -> APICircuitBreaker:
    """Get or create a circuit breaker for the given endpoint type.

    Args:
        endpoint_type: Type of endpoint

    Returns:
        Configured circuit breaker instance
    """
    endpoint_name = endpoint_type.value

    if endpoint_name not in _circuit_breakers:
        config = ENDPOINT_CONFIGS[endpoint_type]
        _circuit_breakers[endpoint_name] = APICircuitBreaker(
            name=f"dmarket_{endpoint_name}",
            **config,
        )
        logger.info(
            "created_circuit_breaker",
            endpoint=endpoint_name,
            config=config,
        )

    return _circuit_breakers[endpoint_name]


# Legacy global instance for backward compatibility
dmarket_api_breaker = APICircuitBreaker(name="dmarket_api")


async def call_with_circuit_breaker(
    func: Callable[..., Any],
    *args: Any,
    fallback: Callable[[], Awaitable[Any]] | None = None,
    endpoint_type: EndpointType = EndpointType.MARKET,
    **kwargs: Any,
) -> Any:
    """Call an async function with circuit breaker protection.

    Roadmap Task #10: Enhanced with per-endpoint breakers and fallback.

    Args:
        func: Async function to call
        fallback: Optional async callable to execute if circuit is open
        endpoint_type: Type of endpoint (determines circuit breaker config)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result or fallback result

    Raises:
        CircuitBreakerError: If circuit is open and no fallback provided
        Exception: Original exception if call fails

    Example:
        >>> async def get_market_data():
        ...     return await api.get_market_items("csgo")
        >>>
        >>> result = await call_with_circuit_breaker(
        ...     get_market_data,
        ...     endpoint_type=EndpointType.MARKET,
        ...     fallback=lambda: {"items": []},  # Empty result on failure
        ... )
    """
    breaker = get_circuit_breaker(endpoint_type)
    endpoint_name = f"dmarket_{endpoint_type.value}"

    @breaker
    async def _wrapper() -> Any:
        return await func(*args, **kwargs)

    try:
        result = await _wrapper()

        # Track successful call
        try:
            from src.utils.prometheus_metrics import track_circuit_breaker_call

            track_circuit_breaker_call(endpoint_name, "success")
        except ImportError:
            pass

        logger.debug(
            "circuit_breaker_call_success",
            endpoint=endpoint_type.value,
            state=breaker.state,
        )
        return result

    except CircuitBreakerError as e:
        # Track rejected call (circuit open)
        try:
            from src.utils.prometheus_metrics import track_circuit_breaker_call

            track_circuit_breaker_call(endpoint_name, "rejected")
        except ImportError:
            pass

        logger.exception(
            "circuit_breaker_open",
            endpoint=endpoint_type.value,
            error=str(e),
            state="open",
        )

        if fallback:
            logger.info(
                "executing_fallback",
                endpoint=endpoint_type.value,
            )
            return await fallback()
        raise

    except Exception as e:
        # Track failed call
        try:
            from src.utils.prometheus_metrics import (
                track_circuit_breaker_call,
                track_circuit_breaker_failure,
            )

            track_circuit_breaker_call(endpoint_name, "failure")
            track_circuit_breaker_failure(endpoint_name)
        except ImportError:
            pass

        logger.exception(
            "circuit_breaker_call_failed",
            endpoint=endpoint_type.value,
            error=str(e),
        )
        raise


def get_circuit_breaker_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all circuit breakers.

    Returns:
        Dictionary with stats per endpoint:
        - state: current state (closed, open, half_open)
        - failure_count: number of recent failures
        - last_failure_time: timestamp of last failure

    Example:
        >>> stats = get_circuit_breaker_stats()
        >>> print(stats["market"]["state"])
        'closed'
    """
    stats = {}

    for endpoint_name, breaker in _circuit_breakers.items():
        stats[endpoint_name] = {
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "last_failure": str(breaker.last_failure) if breaker.last_failure else None,
            "config": {
                "failure_threshold": breaker._failure_threshold,
                "recovery_timeout": breaker._recovery_timeout,
            },
        }

    return stats


def reset_circuit_breaker(endpoint_type: EndpointType) -> None:
    """Manually reset a circuit breaker to closed state.

    Use with caution - only for manual recovery after confirmed API fix.

    Args:
        endpoint_type: Type of endpoint to reset
    """
    breaker = get_circuit_breaker(endpoint_type)
    breaker.reset()
    logger.info(
        "circuit_breaker_manual_reset",
        endpoint=endpoint_type.value,
    )


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to closed state.

    Use with extreme caution - only for emergency recovery.
    """
    for endpoint_name, breaker in _circuit_breakers.items():
        breaker.reset()
        logger.warning(
            "circuit_breaker_emergency_reset",
            endpoint=endpoint_name,
        )
