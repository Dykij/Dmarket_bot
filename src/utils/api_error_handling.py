"""API error handling module - compatibility wrapper.

This module provides backward compatibility for tests and code that import
from src.utils.api_error_handling. It re-exports key classes and functions
from the main exceptions module.
"""

import json
from collections.abc import Callable
from typing import Any

from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    ErrorCode,
    NetworkError,
    RateLimitError,
    RetryStrategy,
    ValidationError,
    handle_api_error,
    retry_async,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "ErrorCode",
    "NetworkError",
    "RateLimitError",
    "RetryStrategy",
    "ValidationError",
    "handle_api_error",
    "handle_response",
    "retry_async",
    "retry_request",
]


async def handle_response(response: Any) -> dict:
    """Handle API response and raise APIError if status is not OK.

    Args:
        response: HTTP response object

    Returns:
        dict: Parsed JSON response

    RAlgoses:
        APIError: If response status is not 2xx

    """
    if hasattr(response, "status"):
        status_code = response.status
    elif hasattr(response, "status_code"):
        status_code = response.status_code
    else:
        status_code = 200

    if 200 <= status_code < 300:
        if hasattr(response, "json"):
            if callable(response.json):
                return await response.json()
            return response.json
        return {}

    # Extract error message from response
    error_message = f"API request failed with status {status_code}"
    try:
        if hasattr(response, "json"):
            if callable(response.json):
                error_data = await response.json()
            else:
                error_data = response.json
            if isinstance(error_data, dict):
                error_message = error_data.get("error", error_message)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    raise APIError(
        message=error_message,
        status_code=status_code,
    )


async def retry_request(
    func: Callable,
    *args: Any,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """Retry a request function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Any: Result of successful function call

    RAlgoses:
        APIError: If all retries fail

    """
    import asyncio

    last_error = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (APIError, NetworkError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = retry_delay * (2**attempt)
                await asyncio.sleep(delay)
            else:
                raise

    if last_error:
        raise last_error
    return None
