"""Tests for PerformanceMonitor module."""

import asyncio
import time

import pytest

from src.utils.performance_monitor import (
    PerformanceMetrics,
    PerformanceMonitor,
    RequestMetric,
    get_performance_summary,
    global_monitor,
    slow_request_alert,
)


class TestRequestMetric:
    """Tests for RequestMetric dataclass."""

    def test_request_metric_creation(self):
        """Test creating a request metric."""
        metric = RequestMetric(
            function_name="test_func",
            execution_time=1.5,
            timestamp=time.time(),
            success=True,
            args_summary="args=2",
        )

        assert metric.function_name == "test_func"
        assert metric.execution_time == 1.5
        assert metric.success is True

    def test_request_metric_with_error(self):
        """Test request metric with error."""
        metric = RequestMetric(
            function_name="failed_func",
            execution_time=0.5,
            timestamp=time.time(),
            success=False,
            error_message="Connection timeout",
        )

        assert metric.success is False
        assert metric.error_message == "Connection timeout"


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_empty_metrics(self):
        """Test empty metrics initialization."""
        metrics = PerformanceMetrics()

        assert metrics.total_requests == 0
        assert metrics.average_time == 0.0
        assert metrics.success_rate == 0.0

    def test_metrics_calculations(self):
        """Test metrics calculations."""
        metrics = PerformanceMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            total_time=50.0,
            min_time=0.1,
            max_time=2.0,
            slow_requests=3,
        )

        assert metrics.average_time == 0.5  # 50/100
        assert metrics.success_rate == 95.0  # 95/100 * 100

    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = PerformanceMetrics(
            total_requests=10,
            successful_requests=9,
            failed_requests=1,
            total_time=5.0,
        )

        data = metrics.to_dict()

        assert "total_requests" in data
        assert "success_rate_percent" in data
        assert data["total_requests"] == 10


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create fresh monitor instance."""
        return PerformanceMonitor(slow_threshold=1.0, alert_on_slow=False)

    def test_record_request(self, monitor):
        """Test recording a request."""
        monitor.record(
            func_name="test_api",
            execution_time=0.5,
            success=True,
        )

        metrics = monitor.get_metrics("test_api")
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1

    def test_record_multiple_requests(self, monitor):
        """Test recording multiple requests."""
        for i in range(5):
            monitor.record(
                func_name="multi_api",
                execution_time=0.1 * (i + 1),
                success=True,
            )

        metrics = monitor.get_metrics("multi_api")
        assert metrics.total_requests == 5
        assert metrics.min_time == 0.1
        assert metrics.max_time == 0.5

    def test_record_failed_request(self, monitor):
        """Test recording failed request."""
        monitor.record(
            func_name="failing_api",
            execution_time=1.0,
            success=False,
            error_message="API Error",
        )

        metrics = monitor.get_metrics("failing_api")
        assert metrics.failed_requests == 1
        assert metrics.success_rate == 0.0

    def test_slow_request_detection(self, monitor):
        """Test slow request detection."""
        # Record normal request
        monitor.record("normal", 0.5, success=True)

        # Record slow request (>1.0 threshold)
        monitor.record("slow", 1.5, success=True)

        metrics = monitor.get_metrics("slow")
        assert metrics.slow_requests == 1

    def test_get_slow_requests(self, monitor):
        """Test getting list of slow requests."""
        monitor.record("func1", 0.5, success=True)
        monitor.record("func1", 1.5, success=True)  # Slow
        monitor.record("func2", 2.0, success=True)  # Slow

        slow = monitor.get_slow_requests()
        assert len(slow) == 2
        # Should be sorted by execution time (descending)
        assert slow[0].execution_time >= slow[1].execution_time

    def test_get_recent_history(self, monitor):
        """Test getting recent history."""
        for i in range(15):
            monitor.record("history_test", 0.1 * i, success=True)

        history = monitor.get_recent_history("history_test", limit=5)
        assert len(history) == 5

    def test_reset_specific_function(self, monitor):
        """Test resetting metrics for specific function."""
        monitor.record("func_a", 1.0, success=True)
        monitor.record("func_b", 1.0, success=True)

        monitor.reset("func_a")

        assert monitor.get_metrics("func_a").total_requests == 0
        assert monitor.get_metrics("func_b").total_requests == 1

    def test_reset_all(self, monitor):
        """Test resetting all metrics."""
        monitor.record("func_a", 1.0, success=True)
        monitor.record("func_b", 1.0, success=True)

        monitor.reset()

        assert monitor.get_metrics("func_a").total_requests == 0
        assert monitor.get_metrics("func_b").total_requests == 0

    def test_get_all_metrics(self, monitor):
        """Test getting all metrics."""
        monitor.record("api_1", 0.5, success=True)
        monitor.record("api_2", 1.0, success=True)

        all_metrics = monitor.get_all_metrics()

        assert "api_1" in all_metrics
        assert "api_2" in all_metrics


class TestPerformanceMonitorDecorator:
    """Tests for @monitor.track decorator."""

    @pytest.fixture
    def monitor(self):
        """Create fresh monitor instance."""
        return PerformanceMonitor(slow_threshold=1.0, alert_on_slow=False)

    def test_track_sync_function(self, monitor):
        """Test tracking sync function."""

        @monitor.track
        def sync_func():
            time.sleep(0.1)
            return "result"

        result = sync_func()

        assert result == "result"
        metrics = monitor.get_metrics("sync_func")
        assert metrics.total_requests == 1
        assert metrics.total_time > 0

    @pytest.mark.asyncio
    async def test_track_async_function(self, monitor):
        """Test tracking async function."""

        @monitor.track
        async def async_func():
            await asyncio.sleep(0.1)
            return "async_result"

        result = await async_func()

        assert result == "async_result"
        metrics = monitor.get_metrics("async_func")
        assert metrics.total_requests == 1

    def test_track_function_with_exception(self, monitor):
        """Test tracking function that raises exception."""

        @monitor.track
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        metrics = monitor.get_metrics("failing_func")
        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1


class TestSlowRequestAlertDecorator:
    """Tests for @slow_request_alert decorator."""

    def test_slow_request_alert_sync(self, caplog):
        """Test slow request alert for sync function."""

        @slow_request_alert(threshold=0.05)
        def slow_func():
            time.sleep(0.1)
            return "done"

        result = slow_func()
        assert result == "done"
        # Alert should be logged (check logs)

    @pytest.mark.asyncio
    async def test_slow_request_alert_async(self, caplog):
        """Test slow request alert for async function."""

        @slow_request_alert(threshold=0.05)
        async def slow_async_func():
            await asyncio.sleep(0.1)
            return "done"

        result = await slow_async_func()
        assert result == "done"


class TestGetPerformanceSummary:
    """Tests for get_performance_summary function."""

    def test_get_performance_summary(self):
        """Test getting performance summary."""
        # Reset global monitor
        global_monitor.reset()

        # Record some metrics
        global_monitor.record("test_api", 0.5, success=True)
        global_monitor.record("test_api", 1.0, success=True)

        summary = get_performance_summary()

        assert "metrics_by_function" in summary
        assert "total_slow_requests" in summary
        assert "slowest_requests" in summary
