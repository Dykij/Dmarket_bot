"""Global retry decorator with exponential backoff using tenacity.

This module provides a standardized retry mechanism for API calls and other
operations that may fail temporarily.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.exceptions import NetworkError, RateLimitError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_failure(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
    multiplier: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (
        NetworkError,
        ConnectionError,
        TimeoutError,
    ),
) -> Callable:
    """Decorator for retrying failed operations with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 2)
        max_wait: Maximum wait time between retries in seconds (default: 10)
        multiplier: Multiplier for exponential backoff (default: 1)
        retry_on: Tuple of exception types to retry on

    Returns:
        Decorated function with retry logic

    Example:
        >>> @retry_on_failure(max_attempts=5, min_wait=1, max_wait=30)
        >>> async def fetch_data():
        >>>     return await api_call()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            """Async wrapper for retry logic."""
            attempt = 0
            async for attempt_obj in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=multiplier, min=min_wait, max=max_wait
                ),
                retry=retry_if_exception_type(retry_on),
                reraise=True,
            ):
                with attempt_obj:
                    attempt += 1
                    try:
                        result = await func(*args, **kwargs)
                        if attempt > 1:
                            logger.info(
                                f"Operation succeeded on attempt {attempt}",
                                extra={
                                    "function": func.__name__,
                                    "attempt": attempt,
                                },
                            )
                        return result
                    except Exception as e:
                        logger.warning(
                            f"Retry attempt {attempt}/{max_attempts} failed for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        if attempt >= max_attempts:
                            logger.exception(
                                "All retry attempts exhausted for %s",
                                func.__name__,
                                extra={
                                    "function": func.__name__,
                                    "attempts": max_attempts,
                                    "final_error": str(e),
                                },
                            )
                        raise

            # This should never be reached due to reraise=True
            raise RuntimeError("All retry attempts exhausted without exception")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            """Sync wrapper for retry logic."""
            for attempt, attempt_obj in enumerate(
                retry(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(
                        multiplier=multiplier, min=min_wait, max=max_wait
                    ),
                    retry=retry_if_exception_type(retry_on),
                    reraise=True,
                )(lambda: func(*args, **kwargs)),
                start=1,
            ):
                try:
                    result = attempt_obj
                    if attempt > 1:
                        logger.info(
                            f"Operation succeeded on attempt {attempt}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                            },
                        )
                    return result
                except Exception as e:
                    logger.warning(
                        f"Retry attempt {attempt}/{max_attempts} failed for {func.__name__}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    )
                    if attempt >= max_attempts:
                        logger.exception(
                            "All retry attempts exhausted for %s",
                            func.__name__,
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "final_error": str(e),
                            },
                        )
                    raise

            # This should never be reached due to reraise=True
            raise RuntimeError("All retry attempts exhausted without exception")

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def retry_api_call(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
) -> Callable:
    """Specialized retry decorator for API calls.

    This decorator retries on NetworkError, RateLimitError, ConnectionError,
    and TimeoutError exceptions.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 2)
        max_wait: Maximum wait time between retries in seconds (default: 10)

    Returns:
        Decorated function with retry logic for API calls

    Example:
        >>> @retry_api_call(max_attempts=5)
        >>> async def get_market_items():
        >>>     return await dmarket_api.get_market_items()
    """
    return retry_on_failure(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        retry_on=(NetworkError, RateLimitError, ConnectionError, TimeoutError),
    )
