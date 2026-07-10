"""Retry decorator."""
import functools
from typing import Any, Callable


def retry_on_failure(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable:
    """Decorator for async functions that retries on NetworkError."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            import asyncio
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        wait = min(min_wait * (2 ** attempt), max_wait)
                        await asyncio.sleep(wait)
            raise last_exc  # type: ignore
        return wrapper
    return decorator
