"""Retry decorator.

v15.2: Uses tenacity for battle-tested retry logic with jitter, logging, etc.
"""
import functools
from typing import Any, Callable

import tenacity


def retry_on_failure(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable:
    """Decorator for async functions that retries on exceptions.

    v15.2: Wraps tenacity for consistent retry behavior across the codebase.
    """
    def decorator(func: Callable) -> Callable:
        @tenacity.retry(
            stop=tenacity.stop_after_attempt(max_attempts),
            wait=tenacity.wait_exponential(multiplier=min_wait, max=max_wait),
            reraise=True,
        )
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)
        return wrapper
    return decorator
