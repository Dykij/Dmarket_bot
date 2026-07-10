"""
api_circuit_breaker.py — Circuit breaker pattern for API calls.
"""

import time
from typing import Any, Callable


class CircuitBreaker:
    """Base circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "closed"

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half-open"
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    def can_execute(self) -> bool:
        return self.state in ("closed", "half-open")


class APICircuitBreaker(CircuitBreaker):
    """Circuit breaker specifically for API calls."""

    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60.0
    EXPECTED_EXCEPTION = Exception

    def __init__(
        self,
        name: str = "api",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ) -> None:
        super().__init__(failure_threshold, recovery_timeout, expected_exception)
        self.name = name

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function through the circuit breaker."""
        if not self.can_execute():
            raise RuntimeError(f"Circuit breaker is {self.state}")
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception:
            self.record_failure()
            raise


async def call_with_circuit_breaker(
    func: Callable,
    *args: Any,
    breaker: APICircuitBreaker | None = None,
    **kwargs: Any,
) -> Any:
    """Call a function through a circuit breaker."""
    if breaker is None:
        breaker = dmarket_api_breaker
    return await breaker.call(func, *args, **kwargs)


# Global instances
dmarket_api_breaker = APICircuitBreaker(
    name="dmarket_api",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception,
)
