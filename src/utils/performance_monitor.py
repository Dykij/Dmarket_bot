"""Performance monitoring utilities for tracking slow requests and API performance.

This module provides:
- PerformanceMonitor: Tracks execution times and identifies slow operations
- slow_request_alert: Decorator for alerting on slow requests
- PerformanceMetrics: Aggregated performance statistics
"""

import asyncio
import functools
import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)
sync_logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RequestMetric:
    """Single request performance metric."""

    function_name: str
    execution_time: float
    timestamp: float
    success: bool
    args_summary: str = ""
    error_message: str | None = None


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    slow_requests: int = 0

    @property
    def average_time(self) -> float:
        """Calculate average execution time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_time / self.total_requests

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate_percent": round(self.success_rate, 2),
            "total_time_seconds": round(self.total_time, 3),
            "average_time_seconds": round(self.average_time, 3),
            "min_time_seconds": round(self.min_time, 3) if self.min_time != float("inf") else 0,
            "max_time_seconds": round(self.max_time, 3),
            "slow_requests": self.slow_requests,
        }


@dataclass
class PerformanceMonitor:
    """Monitor and track API performance metrics.

    Features:
    - Track execution times per function
    - Identify slow requests (>threshold)
    - Aggregate statistics
    - Alert on performance degradation

    Usage:
        monitor = PerformanceMonitor(slow_threshold=5.0)

        @monitor.track
        async def api_call():
            ...

        # Get metrics
        metrics = monitor.get_metrics("api_call")
        print(f"Average time: {metrics.average_time}s")
    """

    slow_threshold: float = 5.0  # Seconds
    max_history: int = 1000
    alert_on_slow: bool = True
    _metrics: dict[str, PerformanceMetrics] = field(default_factory=dict)
    _history: dict[str, deque] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize metrics storage."""
        self._metrics = {}
        self._history = {}

    def _ensure_function_tracked(self, func_name: str) -> None:
        """Ensure function has metrics initialized."""
        if func_name not in self._metrics:
            self._metrics[func_name] = PerformanceMetrics()
            self._history[func_name] = deque(maxlen=self.max_history)

    def record(
        self,
        func_name: str,
        execution_time: float,
        success: bool = True,
        args_summary: str = "",
        error_message: str | None = None,
    ) -> None:
        """Record a request metric.

        Args:
            func_name: Name of the function/operation
            execution_time: Execution time in seconds
            success: Whether the request succeeded
            args_summary: Summary of arguments (for debugging)
            error_message: Error message if failed
        """
        self._ensure_function_tracked(func_name)

        metric = RequestMetric(
            function_name=func_name,
            execution_time=execution_time,
            timestamp=time.time(),
            success=success,
            args_summary=args_summary,
            error_message=error_message,
        )

        # Update aggregated metrics
        stats = self._metrics[func_name]
        stats.total_requests += 1
        stats.total_time += execution_time

        if success:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1

        stats.min_time = min(stats.min_time, execution_time)

        stats.max_time = max(stats.max_time, execution_time)

        is_slow = execution_time > self.slow_threshold
        if is_slow:
            stats.slow_requests += 1

            if self.alert_on_slow:
                logger.warning(
                    "slow_request_detected",
                    function=func_name,
                    execution_time=round(execution_time, 3),
                    threshold=self.slow_threshold,
                    args=args_summary,
                )

        # Add to history
        self._history[func_name].append(metric)

        # Log performance
        logger.debug(
            "request_recorded",
            function=func_name,
            execution_time=round(execution_time, 3),
            success=success,
            is_slow=is_slow,
        )

    def get_metrics(self, func_name: str) -> PerformanceMetrics:
        """Get aggregated metrics for a function.

        Args:
            func_name: Name of the function

        Returns:
            PerformanceMetrics for the function
        """
        self._ensure_function_tracked(func_name)
        return self._metrics[func_name]

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all tracked functions.

        Returns:
            Dictionary of function names to metrics
        """
        return {name: metrics.to_dict() for name, metrics in self._metrics.items()}

    def get_slow_requests(self, func_name: str | None = None) -> list[RequestMetric]:
        """Get list of slow requests.

        Args:
            func_name: Optional filter by function name

        Returns:
            List of slow RequestMetric objects
        """
        slow = []

        if func_name:
            if func_name in self._history:
                slow = [
                    m for m in self._history[func_name] if m.execution_time > self.slow_threshold
                ]
        else:
            for history in self._history.values():
                slow.extend(m for m in history if m.execution_time > self.slow_threshold)

        return sorted(slow, key=lambda m: m.execution_time, reverse=True)

    def get_recent_history(self, func_name: str, limit: int = 10) -> list[RequestMetric]:
        """Get recent request history for a function.

        Args:
            func_name: Name of the function
            limit: Maximum number of records to return

        Returns:
            List of recent RequestMetric objects
        """
        if func_name not in self._history:
            return []

        history = list(self._history[func_name])
        return history[-limit:]

    def reset(self, func_name: str | None = None) -> None:
        """Reset metrics.

        Args:
            func_name: Optional function name to reset (resets all if None)
        """
        if func_name:
            if func_name in self._metrics:
                self._metrics[func_name] = PerformanceMetrics()
                self._history[func_name].clear()
        else:
            self._metrics.clear()
            self._history.clear()

        logger.info("performance_metrics_reset", function=func_name or "all")

    def track(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to track function performance.

        Usage:
            @monitor.track
            async def my_api_call():
                ...
        """
        func_name = func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                # Create args summary (avoid including sensitive data)
                args_summary = f"args={len(args)}, kwargs={list(kwargs.keys())}"

                start_time = time.time()
                success = True
                error_message = None

                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    execution_time = time.time() - start_time
                    self.record(
                        func_name=func_name,
                        execution_time=execution_time,
                        success=success,
                        args_summary=args_summary,
                        error_message=error_message,
                    )

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            args_summary = f"args={len(args)}, kwargs={list(kwargs.keys())}"

            start_time = time.time()
            success = True
            error_message = None

            try:
                return func(*args, **kwargs)
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                execution_time = time.time() - start_time
                self.record(
                    func_name=func_name,
                    execution_time=execution_time,
                    success=success,
                    args_summary=args_summary,
                    error_message=error_message,
                )

        return sync_wrapper  # type: ignore[return-value]


# Global performance monitor instance
global_monitor = PerformanceMonitor(slow_threshold=5.0)


def slow_request_alert(threshold: float = 5.0) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to alert on slow requests.

    Args:
        threshold: Time in seconds to consider a request slow

    Usage:
        @slow_request_alert(threshold=3.0)
        async def api_call():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func_name = func.__name__

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                start_time = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    execution_time = time.time() - start_time
                    if execution_time > threshold:
                        logger.warning(
                            "slow_request_alert",
                            function=func_name,
                            execution_time=round(execution_time, 3),
                            threshold=threshold,
                        )

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                if execution_time > threshold:
                    sync_logger.warning(
                        "Slow request alert: %s took %.3fs (threshold: %.3fs)",
                        func_name,
                        execution_time,
                        threshold,
                    )

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def get_performance_summary() -> dict[str, Any]:
    """Get summary of all tracked performance metrics.

    Returns:
        Dictionary with performance summary
    """
    metrics = global_monitor.get_all_metrics()
    slow_requests = global_monitor.get_slow_requests()

    return {
        "metrics_by_function": metrics,
        "total_slow_requests": len(slow_requests),
        "slowest_requests": [
            {
                "function": req.function_name,
                "execution_time": round(req.execution_time, 3),
                "timestamp": req.timestamp,
            }
            for req in slow_requests[:10]  # Top 10 slowest
        ],
    }
