"""Tests for Skill Profiler module.

Enhanced test suite following SkillsMP.com best practices:
- Parameterized tests for edge cases
- Statistical validation for metrics
- Error injection for resilience testing
- Boundary condition testing
- Performance validation tests
"""

import asyncio

import pytest

from src.utils.skill_profiler import (
    ProfileResult,
    SkiModeletrics,
    SkillProfiler,
    get_profiler,
    profile_skill,
    reset_profiler,
)


@pytest.fixture()
def profiler():
    """Create a fresh profiler instance."""
    reset_profiler()
    return SkillProfiler(enable_memory_tracking=False)


class TestSkiModeletrics:
    """Test cases for SkiModeletrics dataclass."""

    def test_metrics_initialization(self):
        """Test metrics default initialization."""
        metrics = SkiModeletrics(skill_name="test_skill")

        assert metrics.skill_name == "test_skill"
        assert metrics.total_executions == 0
        assert metrics.latency_avg_ms == 0.0
        assert metrics.throughput_per_sec == 0.0

    def test_metrics_to_dict(self):
        """Test conversion to dictionary."""
        metrics = SkiModeletrics(
            skill_name="test_skill",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            latency_avg_ms=25.5,
        )

        result = metrics.to_dict()

        assert result["skill_name"] == "test_skill"
        assert result["total_executions"] == 100
        assert result["success_rate"] == 95.0
        assert result["latency_avg_ms"] == 25.5


class TestSkillProfiler:
    """Test cases for SkillProfiler."""

    def test_profiler_initialization(self, profiler):
        """Test profiler initialization."""
        assert len(profiler.skills_metrics) == 0
        assert profiler.max_samples == 10000

    def test_record_execution(self, profiler):
        """Test recording execution manually."""
        result = profiler.record(
            skill_name="test_skill",
            latency_ms=50.0,
            success=True,
            items_count=10,
        )

        assert isinstance(result, ProfileResult)
        assert result.skill_name == "test_skill"
        assert result.success is True
        assert result.latency_ms == 50.0

        # Check metrics updated
        metrics = profiler.get_skill_metrics("test_skill")
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["items_processed"] == 10

    def test_record_multiple_executions(self, profiler):
        """Test recording multiple executions updates stats."""
        profiler.record("skill", latency_ms=10.0, success=True)
        profiler.record("skill", latency_ms=20.0, success=True)
        profiler.record("skill", latency_ms=30.0, success=False)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["total_executions"] == 3
        assert metrics["successful_executions"] == 2
        assert metrics["failed_executions"] == 1
        assert metrics["latency_avg_ms"] == 20.0

    def test_context_manager_success(self, profiler):
        """Test synchronous context manager on success."""
        with profiler.profile("test_skill", "process", items_count=5):
            _ = sum(range(1000))  # Some work

        metrics = profiler.get_skill_metrics("test_skill")
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["items_processed"] == 5
        assert metrics["latency_avg_ms"] > 0

    def test_context_manager_failure(self, profiler):
        """Test synchronous context manager on failure."""
        with pytest.raises(ValueError), profiler.profile("test_skill"):
            raise ValueError("Test error")

        metrics = profiler.get_skill_metrics("test_skill")
        assert metrics["failed_executions"] == 1

    @pytest.mark.asyncio()
    async def test_async_context_manager_success(self, profiler):
        """Test async context manager on success."""
        async with profiler.aprofile("async_skill", "analyze"):
            await asyncio.sleep(0.01)

        metrics = profiler.get_skill_metrics("async_skill")
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["latency_avg_ms"] >= 10.0  # At least 10ms

    @pytest.mark.asyncio()
    async def test_async_context_manager_failure(self, profiler):
        """Test async context manager on failure."""
        with pytest.raises(RuntimeError):
            async with profiler.aprofile("async_skill"):
                raise RuntimeError("Async error")

        metrics = profiler.get_skill_metrics("async_skill")
        assert metrics["failed_executions"] == 1


class TestLatencyPercentiles:
    """Test cases for latency percentile calculations."""

    def test_percentile_calculation(self, profiler):
        """Test latency percentiles are calculated correctly."""
        # Add 100 samples with known latencies
        for i in range(100):
            profiler.record("skill", latency_ms=float(i), success=True)

        metrics = profiler.get_skill_metrics("skill")

        # P50 should be around 50
        assert 45 <= metrics["latency_p50_ms"] <= 55
        # P95 should be around 95
        assert 90 <= metrics["latency_p95_ms"] <= 99
        # P99 should be around 99
        assert 95 <= metrics["latency_p99_ms"] <= 99

    def test_min_max_latency(self, profiler):
        """Test min/max latency tracking."""
        profiler.record("skill", latency_ms=10.0, success=True)
        profiler.record("skill", latency_ms=50.0, success=True)
        profiler.record("skill", latency_ms=100.0, success=True)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["latency_min_ms"] == 10.0
        assert metrics["latency_max_ms"] == 100.0


class TestThroughput:
    """Test cases for throughput calculation."""

    def test_throughput_calculation(self, profiler):
        """Test throughput is calculated correctly."""
        # 100 items in 100ms = 1000 items/sec
        profiler.record("skill", latency_ms=100.0, success=True, items_count=100)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["throughput_per_sec"] == 1000.0

    def test_throughput_multiple_executions(self, profiler):
        """Test throughput with multiple executions."""
        # 10 items in 100ms = 100/sec
        # 20 items in 200ms = 100/sec
        # Total: 30 items in 300ms = 100 items/sec
        profiler.record("skill", latency_ms=100.0, success=True, items_count=10)
        profiler.record("skill", latency_ms=200.0, success=True, items_count=20)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["throughput_per_sec"] == 100.0


class TestBottleneckDetection:
    """Test cases for bottleneck detection."""

    def test_high_latency_bottleneck(self, profiler):
        """Test detection of high latency bottleneck."""
        # Add slow executions
        for _ in range(10):
            profiler.record("slow_skill", latency_ms=200.0, success=True)

        bottlenecks = profiler.identify_bottlenecks(latency_threshold_ms=100.0)

        assert len(bottlenecks) >= 1
        assert any(b["skill_name"] == "slow_skill" for b in bottlenecks)
        assert any(b["issue"] == "high_latency" for b in bottlenecks)

    def test_high_failure_rate_bottleneck(self, profiler):
        """Test detection of high failure rate bottleneck."""
        # Add mostly failed executions
        for _ in range(5):
            profiler.record("failing_skill", latency_ms=10.0, success=True)
        for _ in range(10):
            profiler.record("failing_skill", latency_ms=10.0, success=False)

        bottlenecks = profiler.identify_bottlenecks()

        assert any(b["issue"] == "high_failure_rate" for b in bottlenecks)


class TestSummary:
    """Test cases for profiler summary."""

    def test_get_summary(self, profiler):
        """Test getting profiler summary."""
        profiler.record("skill1", latency_ms=10.0, success=True)
        profiler.record("skill2", latency_ms=20.0, success=True)
        profiler.record("skill2", latency_ms=30.0, success=False)

        summary = profiler.get_summary()

        assert summary["total_skills_profiled"] == 2
        assert summary["total_executions"] == 3
        assert summary["total_successes"] == 2
        assert "skill1" in summary["skills"]
        assert "skill2" in summary["skills"]

    def test_get_all_metrics(self, profiler):
        """Test getting metrics for all skills."""
        profiler.record("skill1", latency_ms=10.0, success=True)
        profiler.record("skill2", latency_ms=20.0, success=True)

        all_metrics = profiler.get_all_metrics()

        assert "skill1" in all_metrics
        assert "skill2" in all_metrics
        assert all_metrics["skill1"]["total_executions"] == 1


class TestResetMetrics:
    """Test cases for resetting metrics."""

    def test_reset_single_skill(self, profiler):
        """Test resetting metrics for a single skill."""
        profiler.record("skill1", latency_ms=10.0, success=True)
        profiler.record("skill2", latency_ms=20.0, success=True)

        profiler.reset_metrics("skill1")

        metrics1 = profiler.get_skill_metrics("skill1")
        metrics2 = profiler.get_skill_metrics("skill2")

        assert metrics1["total_executions"] == 0
        assert metrics2["total_executions"] == 1

    def test_reset_all_metrics(self, profiler):
        """Test resetting all metrics."""
        profiler.record("skill1", latency_ms=10.0, success=True)
        profiler.record("skill2", latency_ms=20.0, success=True)

        profiler.reset_metrics()

        assert len(profiler.skills_metrics) == 0


class TestProfileSkillDecorator:
    """Test cases for @profile_skill decorator."""

    @pytest.mark.asyncio()
    async def test_async_function_decorator(self):
        """Test decorator on async function."""
        reset_profiler()

        @profile_skill("decorated_async_skill")
        async def async_function():
            await asyncio.sleep(0.01)
            return "async_result"

        result = await async_function()

        assert result == "async_result"

        profiler = get_profiler()
        metrics = profiler.get_skill_metrics("decorated_async_skill")
        assert metrics["total_executions"] == 1

    def test_sync_function_decorator(self):
        """Test decorator on sync function."""
        reset_profiler()

        @profile_skill("decorated_sync_skill")
        def sync_function():
            return "sync_result"

        result = sync_function()

        assert result == "sync_result"

        profiler = get_profiler()
        metrics = profiler.get_skill_metrics("decorated_sync_skill")
        assert metrics["total_executions"] == 1


class TestGlobalProfiler:
    """Test cases for global profiler instance."""

    def test_get_profiler_creates_singleton(self):
        """Test get_profiler returns singleton."""
        reset_profiler()

        p1 = get_profiler()
        p2 = get_profiler()

        assert p1 is p2

    def test_reset_profiler(self):
        """Test reset clears global instance."""
        p1 = get_profiler()
        p1.record("skill", latency_ms=10.0, success=True)

        reset_profiler()
        p2 = get_profiler()

        assert p1 is not p2
        assert len(p2.skills_metrics) == 0


# =============================================================================
# ADVANCED TESTS - Based on SkillsMP.com best practices
# =============================================================================


class TestParameterizedLatency:
    """Parameterized tests for latency recording."""

    @pytest.mark.parametrize("latency_ms", (
        0.0,  # Zero latency
        1.0,  # 1ms
        100.0,  # 100ms
        1000.0,  # 1 second
        10000.0,  # 10 seconds
    ))
    def test_various_latency_values(self, profiler, latency_ms):
        """Test recording various latency values."""
        profiler.record("skill", latency_ms=latency_ms, success=True)

        metrics = profiler.get_skill_metrics("skill")
        assert abs(metrics["latency_avg_ms"] - latency_ms) < 0.01
        assert abs(metrics["latency_min_ms"] - latency_ms) < 0.01
        assert abs(metrics["latency_max_ms"] - latency_ms) < 0.01

    @pytest.mark.parametrize("items_count", (
        0,  # Zero items
        1,  # Single item
        10,
        100,
        1000,
        1000000,  # Million items
    ))
    def test_various_item_counts(self, profiler, items_count):
        """Test recording various item counts."""
        profiler.record("skill", latency_ms=100.0, success=True, items_count=items_count)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["items_processed"] == items_count


class TestStatisticalValidation:
    """Statistical validation for metrics calculations."""

    def test_mean_calculation_accuracy(self, profiler):
        """Test that mean is calculated correctly."""
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        expected_mean = sum(latencies) / len(latencies)

        for lat in latencies:
            profiler.record("skill", latency_ms=lat, success=True)

        metrics = profiler.get_skill_metrics("skill")
        assert abs(metrics["latency_avg_ms"] - expected_mean) < 0.01

    def test_percentile_with_known_distribution(self, profiler):
        """Test percentiles with known uniform distribution."""
        # Record 0-99 to have predictable percentiles
        for i in range(100):
            profiler.record("skill", latency_ms=float(i), success=True)

        metrics = profiler.get_skill_metrics("skill")

        # For uniform 0-99: p50 ≈ 50, p95 ≈ 95, p99 ≈ 99
        assert 48 <= metrics["latency_p50_ms"] <= 52
        assert 93 <= metrics["latency_p95_ms"] <= 97
        assert 97 <= metrics["latency_p99_ms"] <= 99

    def test_percentile_with_outliers(self, profiler):
        """Test percentile calculation with outliers."""
        # 99 normal values, 1 extreme outlier
        for i in range(99):
            profiler.record("skill", latency_ms=10.0, success=True)
        profiler.record("skill", latency_ms=10000.0, success=True)  # Outlier

        metrics = profiler.get_skill_metrics("skill")

        # p50 should not be affected much by single outlier
        assert metrics["latency_p50_ms"] == 10.0
        # p99 should capture the outlier
        assert metrics["latency_p99_ms"] == 10000.0

    def test_success_rate_calculation(self, profiler):
        """Test success rate percentage calculation."""
        # 75 successes, 25 failures = 75% success rate
        for _ in range(75):
            profiler.record("skill", latency_ms=10.0, success=True)
        for _ in range(25):
            profiler.record("skill", latency_ms=10.0, success=False)

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["success_rate"] == 75.0


class TestErrorScenarios:
    """Error scenario and edge case tests."""

    def test_get_nonexistent_skill_metrics(self, profiler):
        """Test getting metrics for non-existent skill returns None."""
        result = profiler.get_skill_metrics("nonexistent_skill")
        assert result is None

    def test_context_manager_with_exception_chain(self, profiler):
        """Test context manager handles exception chains."""
        with pytest.raises(RuntimeError), profiler.profile("skill"):
            try:
                raise ValueError("Inner")
            except ValueError as e:
                raise RuntimeError("Outer") from e

        metrics = profiler.get_skill_metrics("skill")
        assert metrics["failed_executions"] == 1

    @pytest.mark.asyncio()
    async def test_async_context_manager_cancellation(self, profiler):
        """Test async context manager handles task cancellation."""
        async def cancellable_task():
            async with profiler.aprofile("skill"):
                await asyncio.sleep(10)  # Will be cancelled

        task = asyncio.create_task(cancellable_task())
        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        reset_profiler()

        @profile_skill("test_skill")
        def my_function():
            """My docstring."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert "My docstring" in my_function.__doc__


class TestBoundaryConditions:
    """Boundary condition tests."""

    def test_single_sample_statistics(self, profiler):
        """Test statistics with single sample."""
        profiler.record("skill", latency_ms=42.0, success=True)

        metrics = profiler.get_skill_metrics("skill")

        # With single sample, all percentiles should equal the value
        assert metrics["latency_min_ms"] == 42.0
        assert metrics["latency_max_ms"] == 42.0
        assert metrics["latency_avg_ms"] == 42.0
        assert metrics["latency_p50_ms"] == 42.0
        assert metrics["latency_p95_ms"] == 42.0
        assert metrics["latency_p99_ms"] == 42.0

    def test_two_samples_statistics(self, profiler):
        """Test statistics with exactly two samples."""
        profiler.record("skill", latency_ms=10.0, success=True)
        profiler.record("skill", latency_ms=20.0, success=True)

        metrics = profiler.get_skill_metrics("skill")

        assert metrics["latency_min_ms"] == 10.0
        assert metrics["latency_max_ms"] == 20.0
        assert metrics["latency_avg_ms"] == 15.0

    def test_all_failures(self, profiler):
        """Test metrics when all executions fail."""
        for _ in range(10):
            profiler.record("skill", latency_ms=10.0, success=False)

        metrics = profiler.get_skill_metrics("skill")

        assert metrics["successful_executions"] == 0
        assert metrics["failed_executions"] == 10
        assert metrics["success_rate"] == 0.0

    def test_zero_latency_throughput(self, profiler):
        """Test throughput calculation with zero latency."""
        # Edge case: what happens with 0ms latency?
        profiler.record("skill", latency_ms=0.0, success=True, items_count=100)

        metrics = profiler.get_skill_metrics("skill")
        # Should handle gracefully (avoid division by zero)
        assert metrics["items_processed"] == 100


class TestHighVolumeMetrics:
    """High volume and stress tests for metrics."""

    def test_large_sample_count(self, profiler):
        """Test with large number of samples."""
        sample_count = 5000

        for i in range(sample_count):
            latency = float(i % 100)  # Varying latencies
            profiler.record("skill", latency_ms=latency, success=True)

        metrics = profiler.get_skill_metrics("skill")

        assert metrics["total_executions"] == sample_count
        assert metrics["successful_executions"] == sample_count

    def test_many_different_skills(self, profiler):
        """Test profiling many different skills."""
        skill_count = 100

        for i in range(skill_count):
            profiler.record(f"skill_{i}", latency_ms=float(i), success=True)

        all_metrics = profiler.get_all_metrics()

        assert len(all_metrics) == skill_count
        for i in range(skill_count):
            assert f"skill_{i}" in all_metrics

    def test_summary_with_many_skills(self, profiler):
        """Test summary calculation with many skills."""
        for i in range(50):
            for _ in range(10):
                profiler.record(f"skill_{i}", latency_ms=float(i * 10), success=True)

        summary = profiler.get_summary()

        assert summary["total_skills_profiled"] == 50
        assert summary["total_executions"] == 500


class TestBottleneckDetectionAdvanced:
    """Advanced bottleneck detection tests."""

    @pytest.mark.parametrize(("threshold_ms", "expected_bottlenecks"), (
        (1000.0, 0),  # Very high threshold - no bottlenecks
        (100.0, 1),   # Medium threshold - slow_skill is bottleneck
        (10.0, 2),    # Low threshold - both skills are bottlenecks
    ))
    def test_threshold_sensitivity(self, profiler, threshold_ms, expected_bottlenecks):
        """Test bottleneck detection with various thresholds."""
        # Fast skill: 5ms
        for _ in range(10):
            profiler.record("fast_skill", latency_ms=5.0, success=True)

        # Medium skill: 50ms
        for _ in range(10):
            profiler.record("medium_skill", latency_ms=50.0, success=True)

        # Slow skill: 200ms
        for _ in range(10):
            profiler.record("slow_skill", latency_ms=200.0, success=True)

        bottlenecks = profiler.identify_bottlenecks(latency_threshold_ms=threshold_ms)
        latency_bottlenecks = [b for b in bottlenecks if b["issue"] == "high_latency"]

        assert len(latency_bottlenecks) >= expected_bottlenecks

    def test_multiple_bottleneck_types(self, profiler):
        """Test detection of multiple bottleneck types simultaneously."""
        # Slow skill
        for _ in range(10):
            profiler.record("slow_skill", latency_ms=500.0, success=True)

        # FAlgoling skill
        for _ in range(3):
            profiler.record("failing_skill", latency_ms=10.0, success=True)
        for _ in range(10):
            profiler.record("failing_skill", latency_ms=10.0, success=False)

        bottlenecks = profiler.identify_bottlenecks(latency_threshold_ms=100.0)

        issues = [b["issue"] for b in bottlenecks]
        assert "high_latency" in issues
        assert "high_failure_rate" in issues


class TestDecoratorAdvanced:
    """Advanced decorator tests."""

    @pytest.mark.asyncio()
    async def test_decorated_async_with_exception(self):
        """Test decorator on async function that raises."""
        reset_profiler()

        @profile_skill("failing_async")
        async def failing_function():
            await asyncio.sleep(0.001)
            raise ValueError("Test failure")

        with pytest.raises(ValueError):
            await failing_function()

        profiler = get_profiler()
        metrics = profiler.get_skill_metrics("failing_async")
        assert metrics["failed_executions"] == 1

    def test_decorated_sync_with_exception(self):
        """Test decorator on sync function that raises."""
        reset_profiler()

        @profile_skill("failing_sync")
        def failing_function():
            raise RuntimeError("Sync failure")

        with pytest.raises(RuntimeError):
            failing_function()

        profiler = get_profiler()
        metrics = profiler.get_skill_metrics("failing_sync")
        assert metrics["failed_executions"] == 1

    @pytest.mark.asyncio()
    async def test_decorated_function_with_args(self):
        """Test decorator preserves function arguments."""
        reset_profiler()

        @profile_skill("with_args")
        async def function_with_args(a, b, c=None):
            return {"a": a, "b": b, "c": c}

        result = await function_with_args(1, 2, c=3)

        assert result == {"a": 1, "b": 2, "c": 3}

        profiler = get_profiler()
        metrics = profiler.get_skill_metrics("with_args")
        assert metrics["total_executions"] == 1
