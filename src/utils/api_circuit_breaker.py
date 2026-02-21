import time
import asyncio
import logging
from functools import wraps
from typing import Optional, Callable, Any

# Configure logger
logger = logging.getLogger("dmarket_bot.circuit_breaker")

class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and refusing requests."""
    def __init__(self, reset_time: float):
        self.reset_time = reset_time
        remaining = max(0, reset_time - time.time())
        super().__init__(f"Circuit Breaker is OPEN. Retry in {remaining:.2f}s")

class CircuitBreaker:
    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._open_until = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self):
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        async with self._lock:
            if self._state == self.STATE_OPEN:
                if time.time() >= self._open_until:
                    logger.info("Circuit Breaker entering HALF-OPEN state.")
                    self._state = self.STATE_HALF_OPEN
                else:
                    raise CircuitBreakerOpen(self._open_until)

        try:
            result = await func(*args, **kwargs)
            if self._state != self.STATE_CLOSED:
                await self._reset()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise

    async def _reset(self):
        async with self._lock:
            if self._state != self.STATE_CLOSED:
                logger.info("Circuit Breaker recovered. Resetting to CLOSED.")
                self._state = self.STATE_CLOSED
                self._failure_count = 0
                self._open_until = 0.0

    async def _record_failure(self, error: Exception):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            retry_after = self._parse_retry_after(error)
            
            if retry_after:
                logger.warning(f"429 Detected. Circuit Breaker opening for {retry_after}s.")
                self._state = self.STATE_OPEN
                self._open_until = time.time() + retry_after
                return

            if self._state == self.STATE_HALF_OPEN or self._failure_count >= self.failure_threshold:
                if self._state != self.STATE_OPEN:
                    logger.warning(f"Circuit Breaker OPENING due to {self._failure_count} failures.")
                    self._state = self.STATE_OPEN
                    self._open_until = time.time() + self.recovery_timeout

    def _parse_retry_after(self, error: Exception) -> Optional[int]:
        try:
            headers = getattr(error, 'headers', None)
            if not headers and hasattr(error, 'response'):
                 headers = getattr(error.response, 'headers', None)

            if headers:
                retry_val = headers.get("Retry-After") or headers.get("retry-after")
                if retry_val:
                    return int(retry_val)
            
            status = getattr(error, 'status', None)
            if status == 429:
                return self.recovery_timeout
        except (ValueError, AttributeError):
            pass
        return None

def circuit_breaker_decorator(failure_threshold: int = 3, recovery_timeout: int = 60):
    cb = CircuitBreaker(failure_threshold, recovery_timeout)
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await cb.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Alias required by other modules
call_with_circuit_breaker = circuit_breaker_decorator()
