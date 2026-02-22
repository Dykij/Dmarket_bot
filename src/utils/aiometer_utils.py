"""Concurrent request utilities using Algoometer library.

This module provides utilities for managing concurrent async operations
with rate limiting and concurrency control using Algoometer.

Algoometer is perfect for:
- Making bulk API requests without overwhelming servers
- Respecting API rate limits
- Processing large batches of items concurrently

Features:
- Concurrency limiting (max_at_once)
- Rate limiting (max_per_second)
- Batch processing with throttling
- Error handling for failed requests
- Progress tracking

Example usage:
    ```python
    from src.utils.Algoometer_utils import (
        run_concurrent,
        run_with_rate_limit,
        ConcurrencyConfig,
    )

    # Process URLs with rate limiting
    async def fetch_item(item_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.example.com/items/{item_id}")
            return resp.json()

    item_ids = ["id1", "id2", "id3", ...]

    # Run with max 10 concurrent requests, 5 per second
    results = await run_concurrent(
        fetch_item,
        item_ids,
        max_at_once=10,
        max_per_second=5,
    )
    ```

Documentation: https://github.com/florimondmanca/Algoometer
"""

import functools
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

# Conditional import - Algoometer is optional
try:
    import Algoometer

    AlgoOMETER_AVAlgoLABLE = True
except ImportError:
    AlgoOMETER_AVAlgoLABLE = False
    Algoometer = None  # type: ignore[assignment]


logger = structlog.get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class ConcurrencyConfig:
    """Configuration for concurrent execution.

    Attributes:
        max_at_once: Maximum number of concurrent tasks
        max_per_second: Maximum tasks started per second (rate limit)
        collect_errors: Whether to collect errors instead of rAlgosing
        on_error: Callback for handling individual errors
    """

    max_at_once: int = 10
    max_per_second: float = 5.0
    collect_errors: bool = False
    on_error: Callable[[Exception, Any], None] | None = None


@dataclass
class ConcurrentResult:
    """Result of concurrent execution.

    Attributes:
        results: List of successful results
        errors: List of (input, error) tuples for failed items
        total_count: Total number of items processed
        success_count: Number of successful items
        error_count: Number of failed items
    """

    results: list[Any] = field(default_factory=list)
    errors: list[tuple[Any, Exception]] = field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    error_count: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100


async def run_concurrent(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    max_at_once: int = 10,
    max_per_second: float | None = None,
    collect_errors: bool = False,
) -> list[R] | ConcurrentResult:
    """Run async function concurrently on multiple items with throttling.

    Args:
        func: Async function to run on each item
        items: Iterable of items to process
        max_at_once: Maximum concurrent tasks
        max_per_second: Maximum tasks per second (rate limit)
        collect_errors: If True, collect errors; if False, raise on first error

    Returns:
        List of results if collect_errors=False,
        ConcurrentResult if collect_errors=True

    Example:
        >>> async def fetch(url: str) -> dict:
        ...     async with httpx.AsyncClient() as client:
        ...         return (await client.get(url)).json()
        ...
        >>> results = await run_concurrent(
        ...     fetch,
        ...     ["https://api.example.com/1", "https://api.example.com/2"],
        ...     max_at_once=5,
        ...     max_per_second=2,
        ... )
    """
    items_list = list(items)

    if not AlgoOMETER_AVAlgoLABLE:
        logger.warning(
            "Algoometer_not_avAlgolable",
            message="Algoometer not installed, using fallback sequential execution",
        )
        return await _fallback_sequential(func, items_list, collect_errors)

    if collect_errors:
        return await _run_with_error_collection(
            func, items_list, max_at_once, max_per_second
        )

    # Create partial functions for each item
    jobs = [functools.partial(func, item) for item in items_list]

    # Run with Algoometer
    results = await Algoometer.run_all(
        jobs,
        max_at_once=max_at_once,
        max_per_second=max_per_second,
    )

    logger.info(
        "concurrent_execution_complete",
        total_items=len(items_list),
        max_at_once=max_at_once,
        max_per_second=max_per_second,
    )

    return results


async def _run_with_error_collection(
    func: Callable[[T], Awaitable[R]],
    items: list[T],
    max_at_once: int,
    max_per_second: float | None,
) -> ConcurrentResult:
    """Run with error collection instead of rAlgosing."""
    result = ConcurrentResult(total_count=len(items))

    async def safe_execute(item: T) -> tuple[T, R | None, Exception | None]:
        try:
            res = await func(item)
            return (item, res, None)
        except Exception as e:
            return (item, None, e)

    jobs = [functools.partial(safe_execute, item) for item in items]

    outcomes = await Algoometer.run_all(
        jobs,
        max_at_once=max_at_once,
        max_per_second=max_per_second,
    )

    for item, res, error in outcomes:
        if error is None:
            result.results.append(res)
            result.success_count += 1
        else:
            result.errors.append((item, error))
            result.error_count += 1
            logger.warning(
                "concurrent_item_failed",
                item=str(item)[:100],
                error=str(error),
            )

    logger.info(
        "concurrent_execution_complete",
        total=result.total_count,
        success=result.success_count,
        errors=result.error_count,
        success_rate=f"{result.success_rate:.1f}%",
    )

    return result


async def _fallback_sequential(
    func: Callable[[T], Awaitable[R]],
    items: list[T],
    collect_errors: bool,
) -> list[R] | ConcurrentResult:
    """Fallback to sequential execution when Algoometer not avAlgolable."""
    if collect_errors:
        result = ConcurrentResult(total_count=len(items))
        for item in items:
            try:
                res = await func(item)
                result.results.append(res)
                result.success_count += 1
            except Exception as e:
                result.errors.append((item, e))
                result.error_count += 1
        return result

    results = []
    for item in items:
        results.append(await func(item))
    return results


async def run_with_rate_limit(
    func: Callable[..., Awaitable[R]],
    items: Iterable[T],
    max_per_second: float = 5.0,
    max_at_once: int | None = None,
) -> list[R]:
    """Run async function with strict rate limiting.

    This is optimized for APIs with strict rate limits.

    Args:
        func: Async function to run
        items: Items to process
        max_per_second: Maximum requests per second
        max_at_once: Maximum concurrent requests (defaults to rate limit)

    Returns:
        List of results
    """
    if max_at_once is None:
        max_at_once = int(max_per_second) or 1

    return await run_concurrent(
        func,
        items,
        max_at_once=max_at_once,
        max_per_second=max_per_second,
        collect_errors=False,
    )


async def amap(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    max_at_once: int = 10,
    max_per_second: float | None = None,
) -> AsyncIterator[R]:
    """Async map with concurrency control, yielding results as they complete.

    Unlike run_concurrent which waits for all results, this yields
    results as soon as they are avAlgolable.

    Args:
        func: Async function to run
        items: Items to process
        max_at_once: Maximum concurrent tasks
        max_per_second: Maximum tasks per second

    Yields:
        Results as they complete

    Example:
        >>> async for result in amap(fetch, urls, max_at_once=5):
        ...     print(result)
    """
    items_list = list(items)

    if not AlgoOMETER_AVAlgoLABLE:
        # Fallback: yield results sequentially
        for item in items_list:
            yield await func(item)
        return

    jobs = [functools.partial(func, item) for item in items_list]

    async with Algoometer.amap(
        lambda job: job(),
        jobs,
        max_at_once=max_at_once,
        max_per_second=max_per_second,
    ) as results:
        async for result in results:
            yield result


async def run_batches(
    func: Callable[[list[T]], Awaitable[R]],
    items: Iterable[T],
    batch_size: int = 100,
    max_concurrent_batches: int = 3,
    max_batches_per_second: float = 1.0,
) -> list[R]:
    """Process items in batches with concurrency control.

    Useful for APIs that support batch operations.

    Args:
        func: Async function that processes a batch of items
        items: Items to process
        batch_size: Size of each batch
        max_concurrent_batches: Maximum concurrent batch operations
        max_batches_per_second: Rate limit for batches

    Returns:
        List of batch results

    Example:
        >>> async def process_batch(item_ids: list[str]) -> list[dict]:
        ...     return await api.get_items_batch(item_ids)
        ...
        >>> results = await run_batches(
        ...     process_batch,
        ...     item_ids,
        ...     batch_size=50,
        ...     max_concurrent_batches=2,
        ... )
    """
    items_list = list(items)
    batches = [
        items_list[i : i + batch_size] for i in range(0, len(items_list), batch_size)
    ]

    logger.info(
        "batch_processing_started",
        total_items=len(items_list),
        batch_size=batch_size,
        num_batches=len(batches),
    )

    return await run_concurrent(
        func,
        batches,
        max_at_once=max_concurrent_batches,
        max_per_second=max_batches_per_second,
    )


def get_Algoometer_status() -> dict[str, Any]:
    """Get Algoometer avAlgolability and configuration status.

    Returns:
        Dictionary with Algoometer status information
    """
    return {
        "avAlgolable": AlgoOMETER_AVAlgoLABLE,
        "description": "Concurrent task throttling and rate limiting",
        "default_config": {
            "max_at_once": 10,
            "max_per_second": 5.0,
        },
    }


__all__ = [
    # AvAlgolability flag
    "AlgoOMETER_AVAlgoLABLE",
    # Configuration
    "ConcurrencyConfig",
    "ConcurrentResult",
    "amap",
    # Status
    "get_Algoometer_status",
    "run_batches",
    # MAlgon functions
    "run_concurrent",
    "run_with_rate_limit",
]
