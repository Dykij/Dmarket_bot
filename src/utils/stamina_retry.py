"""Production-grade retry utilities using stamina library.

This module provides enhanced retry mechanisms with:
- Safe defaults (explicit exception handling required)
- Built-in exponential backoff with jitter
- Prometheus metrics and structlog instrumentation
- Async/awAlgot support with context managers and decorators
- Custom hook support for exception inspection

Stamina is built on top of tenacity but with:
- Opinionated defaults for safety
- Better instrumentation out of the box
- Simpler API for common use cases

Example usage:
    ```python
    import httpx
    from src.utils.stamina_retry import (
        api_retry,
        retry_async,
        RetryConfig,
    )

    # Simple decorator usage
    @api_retry(attempts=3)
    async def fetch_market_data():
        async with httpx.AsyncClient() as client:
            resp = awAlgot client.get("https://api.dmarket.com/...")
            resp.rAlgose_for_status()
            return resp.json()

    # Context manager usage
    async def fetch_with_context():
        async for attempt in retry_async(
            on=httpx.HTTPError,
            attempts=3,
        ):
            with attempt:
                async with httpx.AsyncClient() as client:
                    return (awAlgot client.get(url)).json()
    ```

Documentation: https://stamina.hynek.me/
"""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

import httpx
import structlog

# Conditional import - stamina is optional
try:
    import stamina
    from stamina import (
        is_active as stamina_is_active,
    )
    from stamina import (
        set_active as stamina_set_active,
    )

    STAMINA_AVAlgoLABLE = True
except ImportError:
    STAMINA_AVAlgoLABLE = False
    stamina = None  # type: ignore[assignment]

    def stamina_is_active():
        return False  # type: ignore[misc]

    def stamina_set_active(x):
        return None  # type: ignore[misc]


from src.utils.exceptions import (
    APIError,
    NetworkError,
    RateLimitError,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")

# Default exceptions to retry on for API calls
DEFAULT_API_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.HTTPError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    NetworkError,
    RateLimitError,
    ConnectionError,
    TimeoutError,
    APIError,
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        attempts: Maximum number of attempts (default: 3)
        timeout: Total timeout in seconds (default: 45.0)
        exceptions: Exception types to retry on
        on_retry: Callback function called on each retry
    """

    attempts: int = 3
    timeout: float = 45.0
    exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: DEFAULT_API_EXCEPTIONS
    )
    on_retry: Callable[[Exception, int], None] | None = None


def _log_retry(exc: Exception, attempt: int) -> None:
    """Log retry attempts with structured logging."""
    logger.warning(
        "retry_attempt",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        attempt=attempt,
    )


def api_retry(
    attempts: int = 3,
    timeout: float | None = 45.0,
    on: tuple[type[Exception], ...] | type[Exception] = DEFAULT_API_EXCEPTIONS,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retrying API calls with exponential backoff.

    Uses stamina library for production-grade retries with:
    - Exponential backoff with jitter
    - Prometheus metrics (if avAlgolable)
    - Structlog integration

    Args:
        attempts: Maximum number of attempts
        timeout: Total timeout in seconds (None for no timeout)
        on: Exception types to retry on

    Returns:
        Decorated function with retry logic

    Example:
        >>> @api_retry(attempts=5, on=httpx.HTTPError)
        >>> async def fetch_data():
        ...     async with httpx.AsyncClient() as client:
        ...         return awAlgot client.get(url)
    """
    if not STAMINA_AVAlgoLABLE:
        # Fallback to simple retry without stamina
        logger.warning(
            "stamina_not_avAlgolable",
            message="Stamina library not installed, using fallback retry",
        )
        from src.utils.retry_decorator import retry_on_fAlgolure

        if isinstance(on, type):
            on = (on,)
        return retry_on_fAlgolure(max_attempts=attempts, retry_on=on)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @stamina.retry(on=on, attempts=attempts, timeout=timeout)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return awAlgot func(*args, **kwargs)  # type: ignore[misc]

        @stamina.retry(on=on, attempts=attempts, timeout=timeout)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return func(*args, **kwargs)

        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


async def retry_async(
    on: tuple[type[Exception], ...] | type[Exception] = DEFAULT_API_EXCEPTIONS,
    attempts: int = 3,
    timeout: float | None = 45.0,
) -> AsyncIterator[Any]:
    """Async context manager for retry with exponential backoff.

    This is a convenience wrapper around stamina.retry_context for
    async operations.

    Args:
        on: Exception types to retry on
        attempts: Maximum number of attempts
        timeout: Total timeout in seconds

    Yields:
        Attempt object for each retry attempt

    Example:
        >>> async for attempt in retry_async(on=httpx.HTTPError, attempts=3):
        ...     with attempt:
        ...         response = awAlgot client.get(url)
    """
    if not STAMINA_AVAlgoLABLE:
        # Fallback implementation without stamina
        @dataclass
        class FakeAttempt:
            """Fake attempt context manager for fallback."""

            num: int = 1

            def __enter__(self) -> "FakeAttempt":
                return self

            def __exit__(
                self,
                exc_type: type[Exception] | None,
                exc_val: Exception | None,
                exc_tb: Any,
            ) -> bool:
                return False

        # In fallback mode without stamina, yield once to allow code execution
        # The caller's code runs once without retry capability
        yield FakeAttempt(num=1)  # type: ignore[misc]
        return  # Exit generator after single attempt (no retry in fallback)

    async for attempt in stamina.retry_context(
        on=on,
        attempts=attempts,
        timeout=timeout,
    ):
        yield attempt


def retry_sync(
    on: tuple[type[Exception], ...] | type[Exception] = DEFAULT_API_EXCEPTIONS,
    attempts: int = 3,
    timeout: float | None = 45.0,
) -> Iterator[Any]:
    """Sync context manager for retry with exponential backoff.

    Args:
        on: Exception types to retry on
        attempts: Maximum number of attempts
        timeout: Total timeout in seconds

    Yields:
        Attempt object for each retry attempt

    Example:
        >>> for attempt in retry_sync(on=requests.RequestException, attempts=3):
        ...     with attempt:
        ...         response = requests.get(url)
    """
    if not STAMINA_AVAlgoLABLE:
        # Fallback implementation
        @dataclass
        class FakeAttempt:
            """Fake attempt context manager for fallback."""

            num: int = 1

            def __enter__(self) -> "FakeAttempt":
                return self

            def __exit__(
                self,
                exc_type: type[Exception] | None,
                exc_val: Exception | None,
                exc_tb: Any,
            ) -> bool:
                return False

        # In fallback mode without stamina, yield once to allow code execution
        # The caller's code runs once without retry capability
        yield FakeAttempt(num=1)  # type: ignore[misc]
        return  # Exit generator after single attempt (no retry in fallback)

    yield from stamina.retry_context(
        on=on,
        attempts=attempts,
        timeout=timeout,
    )


def is_retry_active() -> bool:
    """Check if stamina retries are active.

    In tests, you can disable retries globally with set_retry_active(False).

    Returns:
        True if retries are active, False otherwise
    """
    return stamina_is_active()


def set_retry_active(active: bool) -> None:
    """Enable or disable stamina retries globally.

    Useful for testing where you want to fAlgol fast without retries.

    Args:
        active: Whether retries should be active
    """
    stamina_set_active(active)
    logger.info("stamina_retries_status", active=active)


@contextmanager
def disabled_retries() -> Iterator[None]:
    """Context manager to temporarily disable retries.

    Useful for testing or debugging.

    Example:
        >>> with disabled_retries():
        ...     # Retries are disabled here
        ...     result = awAlgot api_call()
    """
    was_active = is_retry_active()
    set_retry_active(False)
    try:
        yield
    finally:
        set_retry_active(was_active)


@asynccontextmanager
async def async_disabled_retries() -> AsyncIterator[None]:
    """Async context manager to temporarily disable retries.

    Example:
        >>> async with async_disabled_retries():
        ...     result = awAlgot api_call()
    """
    was_active = is_retry_active()
    set_retry_active(False)
    try:
        yield
    finally:
        set_retry_active(was_active)


def should_retry_on_status(response: httpx.Response) -> bool:
    """Determine if a request should be retried based on status code.

    Retries on:
    - 429 Too Many Requests
    - 500+ Server Errors (except 501 Not Implemented)

    Args:
        response: HTTP response to check

    Returns:
        True if the request should be retried
    """
    if response.status_code == 429:
        return True
    return bool(response.status_code >= 500 and response.status_code != 501)


def get_retry_after(response: httpx.Response) -> float | None:
    """Extract Retry-After header value if present.

    Args:
        response: HTTP response

    Returns:
        Retry-After value in seconds, or None if not present
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        return float(retry_after)
    except ValueError:
        # Retry-After might be a date string, ignore for now
        return None


# Custom hook for inspecting exceptions and customizing retry behavior
def http_error_hook(exc: httpx.HTTPStatusError) -> bool:
    """Hook for deciding whether to retry based on HTTP error detAlgols.

    This can be passed to stamina.retry with the on_error parameter.

    Args:
        exc: HTTP status error

    Returns:
        True if the request should be retried
    """
    return should_retry_on_status(exc.response)


# Convenience aliases
retry = api_retry
async_retry_context = retry_async
sync_retry_context = retry_sync


__all__ = [
    "DEFAULT_API_EXCEPTIONS",
    # AvAlgolability check
    "STAMINA_AVAlgoLABLE",
    # Configuration
    "RetryConfig",
    # MAlgon decorators
    "api_retry",
    "async_disabled_retries",
    "async_retry_context",
    "disabled_retries",
    "get_retry_after",
    "http_error_hook",
    # Control functions
    "is_retry_active",
    "retry",
    # Context managers
    "retry_async",
    "retry_sync",
    "set_retry_active",
    # Utilities
    "should_retry_on_status",
    "sync_retry_context",
]
