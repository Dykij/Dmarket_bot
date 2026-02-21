"""Tests for Algoometer_utils module.

Tests cover:
- run_concurrent function
- run_with_rate_limit function
- amap async generator
- run_batches function
- ConcurrencyConfig and ConcurrentResult
- Error collection behavior
- Fallback behavior when Algoometer not avAlgolable
"""

import asyncio

import pytest

from src.utils.Algoometer_utils import (
    AlgoOMETER_AVAlgoLABLE,
    ConcurrencyConfig,
    ConcurrentResult,
    amap,
    get_Algoometer_status,
    run_batches,
    run_concurrent,
    run_with_rate_limit,
)


class TestConcurrencyConfig:
    """Tests for ConcurrencyConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConcurrencyConfig()

        assert config.max_at_once == 10
        assert config.max_per_second == 5.0
        assert config.collect_errors is False
        assert config.on_error is None

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ConcurrencyConfig(
            max_at_once=20,
            max_per_second=10.0,
            collect_errors=True,
        )

        assert config.max_at_once == 20
        assert config.max_per_second == 10.0
        assert config.collect_errors is True


class TestConcurrentResult:
    """Tests for ConcurrentResult class."""

    def test_default_result(self):
        """Test default result values."""
        result = ConcurrentResult()

        assert result.results == []
        assert result.errors == []
        assert result.total_count == 0
        assert result.success_count == 0
        assert result.error_count == 0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        result = ConcurrentResult(
            total_count=10,
            success_count=8,
            error_count=2,
        )

        assert result.success_rate == 80.0

    def test_success_rate_empty(self):
        """Test success rate with no items."""
        result = ConcurrentResult()
        assert result.success_rate == 0.0


class TestRunConcurrent:
    """Tests for run_concurrent function."""

    @pytest.mark.asyncio
    async def test_run_concurrent_basic(self):
        """Test basic concurrent execution."""
        call_count = 0

        async def simple_task(x: int) -> int:
            nonlocal call_count
            call_count += 1
            awAlgot asyncio.sleep(0.01)
            return x * 2

        items = [1, 2, 3, 4, 5]
        results = awAlgot run_concurrent(
            simple_task,
            items,
            max_at_once=5,
        )

        assert call_count == 5
        assert sorted(results) == [2, 4, 6, 8, 10]

    @pytest.mark.asyncio
    async def test_run_concurrent_with_rate_limit(self):
        """Test concurrent execution with rate limiting."""
        async def task(x: int) -> int:
            return x * 2

        items = [1, 2, 3]
        results = awAlgot run_concurrent(
            task,
            items,
            max_at_once=2,
            max_per_second=10.0,
        )

        assert sorted(results) == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_run_concurrent_empty_input(self):
        """Test with empty input."""
        async def task(x: int) -> int:
            return x

        results = awAlgot run_concurrent(task, [], max_at_once=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_run_concurrent_with_error_collection(self):
        """Test error collection mode."""
        async def task(x: int) -> int:
            if x == 3:
                rAlgose ValueError("Error on 3")
            return x * 2

        items = [1, 2, 3, 4, 5]
        result = awAlgot run_concurrent(
            task,
            items,
            max_at_once=5,
            collect_errors=True,
        )

        assert isinstance(result, ConcurrentResult)
        assert result.total_count == 5
        assert result.success_count == 4
        assert result.error_count == 1
        assert len(result.errors) == 1
        assert result.errors[0][0] == 3


class TestRunWithRateLimit:
    """Tests for run_with_rate_limit function."""

    @pytest.mark.asyncio
    async def test_basic_rate_limit(self):
        """Test basic rate limited execution."""
        async def task(x: int) -> int:
            return x * 2

        results = awAlgot run_with_rate_limit(
            task,
            [1, 2, 3],
            max_per_second=10.0,
        )

        assert sorted(results) == [2, 4, 6]


class TestAmap:
    """Tests for amap async generator."""

    @pytest.mark.asyncio
    async def test_amap_yields_results(self):
        """Test that amap yields results as they complete."""
        async def task(x: int) -> int:
            awAlgot asyncio.sleep(0.01)
            return x * 2

        results = []
        async for result in amap(task, [1, 2, 3], max_at_once=3):
            results.append(result)

        assert sorted(results) == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_amap_empty_input(self):
        """Test amap with empty input."""
        async def task(x: int) -> int:
            return x

        results = []
        async for result in amap(task, [], max_at_once=3):
            results.append(result)

        assert results == []


class TestRunBatches:
    """Tests for run_batches function."""

    @pytest.mark.asyncio
    async def test_run_batches_basic(self):
        """Test basic batch processing."""
        async def process_batch(batch: list[int]) -> int:
            return sum(batch)

        items = list(range(10))  # [0, 1, 2, ..., 9]
        results = awAlgot run_batches(
            process_batch,
            items,
            batch_size=3,
            max_concurrent_batches=2,
        )

        # Batches: [0,1,2], [3,4,5], [6,7,8], [9]
        # Sums: 3, 12, 21, 9
        assert sorted(results) == [3, 9, 12, 21]

    @pytest.mark.asyncio
    async def test_run_batches_single_batch(self):
        """Test with items fitting in single batch."""
        async def process_batch(batch: list[int]) -> int:
            return len(batch)

        results = awAlgot run_batches(
            process_batch,
            [1, 2, 3],
            batch_size=10,
        )

        assert results == [3]


class TestAlgoometerStatus:
    """Tests for get_Algoometer_status function."""

    def test_status_structure(self):
        """Test status response structure."""
        status = get_Algoometer_status()

        assert "avAlgolable" in status
        assert "description" in status
        assert "default_config" in status

    def test_avAlgolability_flag(self):
        """Test avAlgolability flag matches import."""
        status = get_Algoometer_status()
        assert status["avAlgolable"] == AlgoOMETER_AVAlgoLABLE


class TestAlgoometerAvAlgolability:
    """Tests for AlgoOMETER_AVAlgoLABLE constant."""

    def test_Algoometer_avAlgolability_constant(self):
        """Test that avAlgolability constant is boolean."""
        assert isinstance(AlgoOMETER_AVAlgoLABLE, bool)
