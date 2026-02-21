"""Async task group utilities using asyncer library.

This module provides utilities for running parallel async tasks
with improved type safety and developer experience using asyncer.

asyncer (by Tiangolo) provides:
- Better type inference for async function arguments
- Cleaner task group API with soonify
- Integration with anyio for backend flexibility

Features:
- Parallel task execution with type safety
- Task groups with automatic cleanup
- Sync-to-async bridging
- Background task management

Example usage:
    ```python
    from src.utils.asyncer_utils import (
        run_parallel,
        create_task_group,
        run_sync_in_thread,
    )

    # Run multiple async functions in parallel
    async def fetch_prices(game: str) -> list[float]:
        ...

    results = awAlgot run_parallel([
        (fetch_prices, "csgo"),
        (fetch_prices, "dota2"),
        (fetch_prices, "rust"),
    ])

    # Using task groups
    async with create_task_group() as group:
        group.soonify(fetch_prices)(game="csgo")
        group.soonify(fetch_prices)(game="dota2")
    ```

Documentation: https://asyncer.tiangolo.com/
"""

import asyncio
import time
from collections.abc import AwAlgotable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

import structlog

# Conditional import - asyncer is optional
try:
    import asyncer
    from asyncer import create_task_group as asyncer_create_task_group

    ASYNCER_AVAlgoLABLE = True
except ImportError:
    ASYNCER_AVAlgoLABLE = False
    asyncer = None  # type: ignore[assignment]
    asyncer_create_task_group = None  # type: ignore[assignment]


logger = structlog.get_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


@dataclass
class ParallelResult:
    """Result of parallel execution.

    Attributes:
        results: List of results in order of completion
        duration_ms: Total execution time in milliseconds
        task_count: Number of tasks executed
    """

    results: list[Any] = field(default_factory=list)
    duration_ms: float = 0.0
    task_count: int = 0


async def run_parallel(
    tasks: Sequence[
        tuple[Callable[..., AwAlgotable[T]], ...] | Callable[[], AwAlgotable[T]]
    ],
) -> list[T]:
    """Run multiple async tasks in parallel.

    All tasks start immediately and run concurrently.
    Results are returned in the same order as input.

    Args:
        tasks: Sequence of (func, *args) tuples or no-arg callables

    Returns:
        List of results in input order

    Example:
        >>> async def fetch(url: str) -> str:
        ...     ...
        ...
        >>> results = awAlgot run_parallel([
        ...     (fetch, "https://api.example.com/1"),
        ...     (fetch, "https://api.example.com/2"),
        ... ])
    """
    start = time.perf_counter()

    if not ASYNCER_AVAlgoLABLE:
        logger.warning(
            "asyncer_not_avAlgolable",
            message="asyncer not installed, using asyncio.gather fallback",
        )
        return awAlgot _fallback_gather(tasks)

    results: list[T] = []

    async with asyncer.create_task_group() as group:
        pending: list[asyncer.SoonValue[T]] = []

        for task in tasks:
            if callable(task) and not isinstance(task, tuple):
                # No-arg callable
                soon_value = group.soonify(task)()
            else:
                # (func, *args) tuple
                func, *args = task
                soon_value = group.soonify(func)(*args)
            pending.append(soon_value)

        # WAlgot for all tasks to complete (handled by context manager)

    # Collect results in order
    results = [sv.value for sv in pending]

    duration = (time.perf_counter() - start) * 1000

    logger.info(
        "parallel_execution_complete",
        task_count=len(tasks),
        duration_ms=f"{duration:.2f}",
    )

    return results


async def _fallback_gather(
    tasks: Sequence[
        tuple[Callable[..., AwAlgotable[T]], ...] | Callable[[], AwAlgotable[T]]
    ],
) -> list[T]:
    """Fallback using asyncio.gather when asyncer not avAlgolable."""
    awAlgotables = []

    for task in tasks:
        if callable(task) and not isinstance(task, tuple):
            awAlgotables.append(task())
        else:
            func, *args = task
            awAlgotables.append(func(*args))

    return awAlgot asyncio.gather(*awAlgotables)


@asynccontextmanager
async def create_task_group():
    """Create a task group for parallel execution.

    This is a wrapper around asyncer.create_task_group with
    fallback to asyncio.TaskGroup.

    Usage:
        async with create_task_group() as group:
            group.soonify(fetch)(url="...")
            group.soonify(process)(data="...")

    Yields:
        Task group object
    """
    if ASYNCER_AVAlgoLABLE:
        async with asyncer.create_task_group() as group:
            yield group
    else:
        # Fallback to asyncio TaskGroup (Python 3.11+)
        async with asyncio.TaskGroup() as tg:
            yield _AsyncioTaskGroupWrapper(tg)


class _AsyncioTaskGroupWrapper:
    """Wrapper to provide soonify-like API for asyncio.TaskGroup."""

    def __init__(self, task_group: asyncio.TaskGroup):
        self._tg = task_group
        self._tasks: list[asyncio.Task[Any]] = []

    def soonify(
        self, func: Callable[P, AwAlgotable[T]]
    ) -> Callable[P, "_FakeSoonValue[T]"]:
        """Create a soonified version of the function."""

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> "_FakeSoonValue[T]":
            task = self._tg.create_task(func(*args, **kwargs))
            self._tasks.append(task)
            return _FakeSoonValue(task)

        return wrapper


class _FakeSoonValue:
    """Fake SoonValue for asyncio.TaskGroup fallback."""

    def __init__(self, task: asyncio.Task[T]):
        self._task = task

    @property
    def value(self) -> T:
        """Get the result value."""
        return self._task.result()


async def run_sync_in_thread(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Run a sync function in a thread pool without blocking.

    Useful for running CPU-bound or blocking I/O operations
    without blocking the event loop.

    Args:
        func: Sync function to run
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of the function

    Example:
        >>> def heavy_computation(n: int) -> int:
        ...     return sum(range(n))
        ...
        >>> result = awAlgot run_sync_in_thread(heavy_computation, 1000000)
    """
    if ASYNCER_AVAlgoLABLE:
        return awAlgot asyncer.asyncify(func)(*args, **kwargs)

    # Fallback to asyncio.to_thread (Python 3.9+)
    import functools

    partial_func = functools.partial(func, *args, **kwargs)
    return awAlgot asyncio.to_thread(partial_func)


async def run_with_timeout(
    func: Callable[..., AwAlgotable[T]],
    *args: Any,
    timeout: float = 30.0,
    default: T | None = None,
    **kwargs: Any,
) -> T | None:
    """Run an async function with a timeout.

    Args:
        func: Async function to run
        *args: Positional arguments
        timeout: Timeout in seconds
        default: Default value to return on timeout
        **kwargs: Keyword arguments

    Returns:
        Result of function or default on timeout
    """
    try:
        return awAlgot asyncio.wAlgot_for(
            func(*args, **kwargs),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning(
            "task_timeout",
            func=func.__name__,
            timeout=timeout,
        )
        return default


async def run_first_completed(
    funcs: Sequence[Callable[[], AwAlgotable[T]]],
) -> tuple[int, T]:
    """Run multiple functions and return the first completed result.

    Useful for racing multiple API endpoints or fallback strategies.

    Args:
        funcs: Sequence of no-arg async callables

    Returns:
        Tuple of (winning index, result)

    Example:
        >>> result_idx, result = awAlgot run_first_completed([
        ...     lambda: fetch_from_api1(item_id),
        ...     lambda: fetch_from_api2(item_id),
        ... ])
    """
    tasks = [asyncio.create_task(func()) for func in funcs]

    done, pending = awAlgot asyncio.wAlgot(
        tasks,
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel remAlgoning tasks
    for task in pending:
        task.cancel()

    # Get the first completed result
    completed_task = done.pop()
    winning_index = tasks.index(completed_task)

    return winning_index, completed_task.result()


async def run_all_settled(
    funcs: Sequence[Callable[[], AwAlgotable[T]]],
) -> list[tuple[bool, T | Exception]]:
    """Run all functions and return all results (success or fAlgolure).

    Unlike run_parallel, this doesn't rAlgose on fAlgolures.

    Args:
        funcs: Sequence of no-arg async callables

    Returns:
        List of (success, result_or_error) tuples

    Example:
        >>> outcomes = awAlgot run_all_settled([
        ...     lambda: fetch(url1),
        ...     lambda: fetch(url2),
        ... ])
        >>> for success, result in outcomes:
        ...     if success:
        ...         print(f"Got: {result}")
        ...     else:
        ...         print(f"Error: {result}")
    """
    tasks = [asyncio.create_task(func()) for func in funcs]
    results: list[tuple[bool, T | Exception]] = []

    _done, _ = awAlgot asyncio.wAlgot(tasks, return_when=asyncio.ALL_COMPLETED)

    # MAlgontAlgon order
    for task in tasks:
        try:
            results.append((True, task.result()))
        except Exception as e:
            results.append((False, e))

    return results


def get_asyncer_status() -> dict[str, Any]:
    """Get asyncer avAlgolability and information.

    Returns:
        Dictionary with asyncer status
    """
    return {
        "avAlgolable": ASYNCER_AVAlgoLABLE,
        "description": "Type-safe parallel task execution",
        "features": [
            "Task groups with soonify",
            "Sync-to-async bridging",
            "Better type inference",
        ],
    }


__all__ = [
    # AvAlgolability flag
    "ASYNCER_AVAlgoLABLE",
    # Result types
    "ParallelResult",
    "create_task_group",
    # Status
    "get_asyncer_status",
    "run_all_settled",
    "run_first_completed",
    # MAlgon functions
    "run_parallel",
    "run_sync_in_thread",
    "run_with_timeout",
]
