"""Tests for asyncer_utils module.

Tests cover:
- run_parallel function
- create_task_group context manager
- run_sync_in_thread function
- run_with_timeout function
- run_first_completed function
- run_all_settled function
- Fallback behavior when asyncer not avAlgolable
"""

import asyncio
import time

import pytest

from src.utils.asyncer_utils import (
    ASYNCER_AVAlgoLABLE,
    ParallelResult,
    create_task_group,
    get_asyncer_status,
    run_all_settled,
    run_first_completed,
    run_parallel,
    run_sync_in_thread,
    run_with_timeout,
)


class TestParallelResult:
    """Tests for ParallelResult class."""

    def test_default_result(self):
        """Test default result values."""
        result = ParallelResult()

        assert result.results == []
        assert result.duration_ms == 0.0
        assert result.task_count == 0

    def test_custom_result(self):
        """Test custom result values."""
        result = ParallelResult(
            results=[1, 2, 3],
            duration_ms=150.5,
            task_count=3,
        )

        assert result.results == [1, 2, 3]
        assert result.duration_ms == 150.5
        assert result.task_count == 3


class TestRunParallel:
    """Tests for run_parallel function."""

    @pytest.mark.asyncio
    async def test_run_parallel_with_tuples(self):
        """Test parallel execution with (func, *args) tuples."""
        async def double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        results = await run_parallel([
            (double, 1),
            (double, 2),
            (double, 3),
        ])

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_run_parallel_with_callables(self):
        """Test parallel execution with no-arg callables."""
        async def get_value() -> int:
            await asyncio.sleep(0.01)
            return 42

        results = await run_parallel([
            get_value,
            get_value,
        ])

        assert results == [42, 42]

    @pytest.mark.asyncio
    async def test_run_parallel_is_concurrent(self):
        """Test that tasks actually run in parallel."""
        async def slow_task(x: int) -> int:
            await asyncio.sleep(0.1)
            return x

        start = time.perf_counter()
        results = await run_parallel([
            (slow_task, 1),
            (slow_task, 2),
            (slow_task, 3),
        ])
        duration = time.perf_counter() - start

        assert sorted(results) == [1, 2, 3]
        # Should take ~0.1s, not ~0.3s
        assert duration < 0.25

    @pytest.mark.asyncio
    async def test_run_parallel_empty(self):
        """Test with empty input."""
        results = await run_parallel([])
        assert results == []


class TestCreateTaskGroup:
    """Tests for create_task_group context manager."""

    @pytest.mark.asyncio
    async def test_task_group_basic(self):
        """Test basic task group usage."""
        results = []

        async def add_result(x: int) -> None:
            await asyncio.sleep(0.01)
            results.append(x)

        async with create_task_group() as group:
            group.soonify(add_result)(x=1)
            group.soonify(add_result)(x=2)
            group.soonify(add_result)(x=3)

        assert sorted(results) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_task_group_with_return_values(self):
        """Test task group capturing return values."""
        async def double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        async with create_task_group() as group:
            soon1 = group.soonify(double)(x=1)
            soon2 = group.soonify(double)(x=2)

        assert soon1.value == 2
        assert soon2.value == 4


class TestRunSyncInThread:
    """Tests for run_sync_in_thread function."""

    @pytest.mark.asyncio
    async def test_run_sync_basic(self):
        """Test running sync function in thread."""
        def compute(x: int, y: int) -> int:
            return x + y

        result = await run_sync_in_thread(compute, 1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_run_sync_with_kwargs(self):
        """Test with keyword arguments."""
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = await run_sync_in_thread(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    @pytest.mark.asyncio
    async def test_run_sync_doesnt_block(self):
        """Test that sync function doesn't block event loop."""
        import time as sync_time

        def blocking_task() -> str:
            sync_time.sleep(0.1)
            return "done"

        # Create a parallel async task
        async def quick_task() -> str:
            return "quick"

        # Both should complete roughly at the same time
        start = time.perf_counter()
        results = await asyncio.gather(
            run_sync_in_thread(blocking_task),
            quick_task(),
        )
        duration = time.perf_counter() - start

        assert results == ["done", "quick"]
        # The quick task should have completed almost immediately
        assert duration < 0.2


class TestRunWithTimeout:
    """Tests for run_with_timeout function."""

    @pytest.mark.asyncio
    async def test_completes_before_timeout(self):
        """Test function that completes before timeout."""
        async def quick() -> str:
            await asyncio.sleep(0.01)
            return "success"

        result = await run_with_timeout(quick, timeout=1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_returns_default(self):
        """Test timeout returns default value."""
        async def slow() -> str:
            await asyncio.sleep(1.0)
            return "success"

        result = await run_with_timeout(
            slow,
            timeout=0.05,
            default="timed out",
        )
        assert result == "timed out"

    @pytest.mark.asyncio
    async def test_timeout_returns_none_by_default(self):
        """Test timeout returns None when no default specified."""
        async def slow() -> str:
            await asyncio.sleep(1.0)
            return "success"

        result = await run_with_timeout(slow, timeout=0.05)
        assert result is None


class TestRunFirstCompleted:
    """Tests for run_first_completed function."""

    @pytest.mark.asyncio
    async def test_returns_first_completed(self):
        """Test returns result of first completed task."""
        async def fast() -> str:
            await asyncio.sleep(0.01)
            return "fast"

        async def slow() -> str:
            await asyncio.sleep(1.0)
            return "slow"

        idx, result = await run_first_completed([fast, slow])

        assert idx == 0
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_cancels_remaining_tasks(self):
        """Test that remaining tasks are cancelled."""
        cancelled = False

        async def fast() -> str:
            return "fast"

        async def slow() -> str:
            nonlocal cancelled
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "slow"

        await run_first_completed([fast, slow])

        # Give time for cancellation
        await asyncio.sleep(0.05)
        assert cancelled


class TestRunAllSettled:
    """Tests for run_all_settled function."""

    @pytest.mark.asyncio
    async def test_collects_all_results(self):
        """Test collecting both successes and failures."""
        async def succeed() -> str:
            return "success"

        async def fail() -> str:
            raise ValueError("failed")

        outcomes = await run_all_settled([succeed, fail, succeed])

        assert len(outcomes) == 3
        assert outcomes[0] == (True, "success")
        assert outcomes[1][0] is False
        assert isinstance(outcomes[1][1], ValueError)
        assert outcomes[2] == (True, "success")

    @pytest.mark.asyncio
    async def test_all_success(self):
        """Test when all tasks succeed."""
        async def succeed(x: int) -> int:
            return x

        outcomes = await run_all_settled([
            lambda: succeed(1),
            lambda: succeed(2),
        ])

        assert all(success for success, _ in outcomes)
        assert [result for _, result in outcomes] == [1, 2]


class TestAsyncerStatus:
    """Tests for get_asyncer_status function."""

    def test_status_structure(self):
        """Test status response structure."""
        status = get_asyncer_status()

        assert "avAlgolable" in status
        assert "description" in status
        assert "features" in status
        assert isinstance(status["features"], list)

    def test_avAlgolability_flag(self):
        """Test avAlgolability flag matches import."""
        status = get_asyncer_status()
        assert status["avAlgolable"] == ASYNCER_AVAlgoLABLE


class TestAsyncerAvAlgolability:
    """Tests for ASYNCER_AVAlgoLABLE constant."""

    def test_asyncer_avAlgolability_constant(self):
        """Test that avAlgolability constant is boolean."""
        assert isinstance(ASYNCER_AVAlgoLABLE, bool)
