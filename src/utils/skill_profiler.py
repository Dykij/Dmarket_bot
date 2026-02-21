"""Skill Performance Profiler - Performance tracking for ML/AI modules.

This module provides performance profiling for ML/AI skills:
- Execution time tracking
- Memory usage monitoring
- Throughput calculation
- Latency percentiles (p50, p95, p99)
- Automatic bottleneck detection

Based on SkillsMP.com performance profiling recommendations.

Usage:
    ```python
    from src.utils.skill_profiler import profile_skill, get_profiler

    # Using decorator
    @profile_skill("ai-arbitrage-predictor")
    async def predict_opportunities(items):
        ...

    # Using context manager
    profiler = get_profiler()
    with profiler.profile("price_prediction"):
        result = await predictor.predict(item)

    # Get metrics
    metrics = profiler.get_skill_metrics("ai-arbitrage-predictor")
    print(f"P99 Latency: {metrics['latency_p99_ms']}ms")
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections import deque
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class SkillMetrics:
    """Performance metrics for a skill."""

    skill_name: str

    # Execution counts
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0

    # Latency (in milliseconds)
    latency_samples: list[float] = field(default_factory=list)
    latency_min_ms: float = 0.0
    latency_max_ms: float = 0.0
    latency_avg_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0

    # Throughput
    throughput_per_sec: float = 0.0
    items_processed: int = 0

    # Memory (bytes)
    memory_peak_bytes: int = 0
    memory_avg_bytes: int = 0

    # Time tracking
    first_execution: datetime | None = None
    last_execution: datetime | None = None
    total_execution_time_ms: float = 0.0

    # Recent samples for rolling metrics
    _recent_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": round(
                self.successful_executions / max(1, self.total_executions) * 100, 2
            ),
            "latency_min_ms": round(self.latency_min_ms, 2),
            "latency_max_ms": round(self.latency_max_ms, 2),
            "latency_avg_ms": round(self.latency_avg_ms, 2),
            "latency_p50_ms": round(self.latency_p50_ms, 2),
            "latency_p95_ms": round(self.latency_p95_ms, 2),
            "latency_p99_ms": round(self.latency_p99_ms, 2),
            "throughput_per_sec": round(self.throughput_per_sec, 2),
            "items_processed": self.items_processed,
            "memory_peak_bytes": self.memory_peak_bytes,
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
            "first_execution": (
                self.first_execution.isoformat() if self.first_execution else None
            ),
            "last_execution": (
                self.last_execution.isoformat() if self.last_execution else None
            ),
        }


@dataclass
class ProfileResult:
    """Result of a single profiling session."""

    skill_name: str
    operation: str
    success: bool
    latency_ms: float
    items_count: int = 1
    memory_bytes: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SkillProfiler:
    """Performance profiler for ML/AI skills.

    Features:
    - Decorator and context manager API
    - Latency percentiles calculation
    - Throughput tracking
    - Memory monitoring (if psutil available)
    - Automatic metric aggregation

    Attributes:
        skills_metrics: Dictionary of skill name to SkillMetrics
        enable_memory_tracking: Whether to track memory usage
    """

    # Thresholds for warnings
    LATENCY_WARNING_MS = 100.0
    LATENCY_CRITICAL_MS = 500.0
    MEMORY_WARNING_BYTES = 500 * 1024 * 1024  # 500MB

    def __init__(
        self,
        enable_memory_tracking: bool = True,
        max_samples: int = 10000,
    ) -> None:
        """Initialize the profiler.

        Args:
            enable_memory_tracking: Track memory usage (requires psutil)
            max_samples: Maximum latency samples to keep per skill
        """
        self.enable_memory_tracking = enable_memory_tracking
        self.max_samples = max_samples

        self.skills_metrics: dict[str, SkillMetrics] = {}

        # Check psutil availability
        self._psutil_available = False
        if enable_memory_tracking:
            try:
                import psutil  # noqa: F401

                self._psutil_available = True
            except ImportError:
                logger.warning(
                    "psutil not available, memory tracking disabled. "
                    "Install with: pip install psutil"
                )

        logger.info(
            "skill_profiler_initialized",
            memory_tracking=self._psutil_available,
        )

    def _get_or_create_metrics(self, skill_name: str) -> SkillMetrics:
        """Get or create metrics for a skill."""
        if skill_name not in self.skills_metrics:
            self.skills_metrics[skill_name] = SkillMetrics(skill_name=skill_name)
        return self.skills_metrics[skill_name]

    def _get_memory_usage(self) -> int:
        """Get current process memory usage in bytes."""
        if not self._psutil_available:
            return 0

        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss
        except Exception:
            return 0

    def _update_metrics(
        self,
        metrics: SkillMetrics,
        latency_ms: float,
        success: bool,
        items_count: int,
        memory_bytes: int,
    ) -> None:
        """Update metrics with new execution data."""
        now = datetime.now(UTC)

        # Update counters
        metrics.total_executions += 1
        if success:
            metrics.successful_executions += 1
        else:
            metrics.failed_executions += 1

        # Update time tracking
        if metrics.first_execution is None:
            metrics.first_execution = now
        metrics.last_execution = now
        metrics.total_execution_time_ms += latency_ms

        # Update latency samples
        metrics._recent_latencies.append(latency_ms)
        metrics.latency_samples.append(latency_ms)
        if len(metrics.latency_samples) > self.max_samples:
            metrics.latency_samples = metrics.latency_samples[-self.max_samples :]

        # Calculate latency statistics
        samples = list(metrics._recent_latencies)
        if samples:
            metrics.latency_min_ms = min(samples)
            metrics.latency_max_ms = max(samples)
            metrics.latency_avg_ms = statistics.mean(samples)

            sorted_samples = sorted(samples)
            n = len(sorted_samples)
            # Calculate percentiles properly, handling edge cases
            metrics.latency_p50_ms = sorted_samples[min(int(n * 0.5), n - 1)]
            metrics.latency_p95_ms = sorted_samples[min(int(n * 0.95), n - 1)]
            metrics.latency_p99_ms = sorted_samples[min(int(n * 0.99), n - 1)]

        # Update throughput
        metrics.items_processed += items_count
        if metrics.total_execution_time_ms > 0:
            metrics.throughput_per_sec = metrics.items_processed / (
                metrics.total_execution_time_ms / 1000
            )

        # Update memory
        metrics.memory_peak_bytes = max(metrics.memory_peak_bytes, memory_bytes)

        # Log warnings for slow operations
        if latency_ms > self.LATENCY_CRITICAL_MS:
            logger.warning(
                "skill_execution_slow",
                skill_name=metrics.skill_name,
                latency_ms=round(latency_ms, 2),
                threshold_ms=self.LATENCY_CRITICAL_MS,
            )

    def record(
        self,
        skill_name: str,
        latency_ms: float,
        success: bool = True,
        items_count: int = 1,
        memory_bytes: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ProfileResult:
        """Record a profiling result manually.

        Args:
            skill_name: Name of the skill
            latency_ms: Execution latency in milliseconds
            success: Whether execution was successful
            items_count: Number of items processed
            memory_bytes: Memory used in bytes
            metadata: Additional metadata

        Returns:
            ProfileResult with recorded data
        """
        metrics = self._get_or_create_metrics(skill_name)
        self._update_metrics(metrics, latency_ms, success, items_count, memory_bytes)

        return ProfileResult(
            skill_name=skill_name,
            operation="manual",
            success=success,
            latency_ms=latency_ms,
            items_count=items_count,
            memory_bytes=memory_bytes,
            metadata=metadata or {},
        )

    @contextmanager
    def profile(
        self,
        skill_name: str,
        operation: str = "execute",
        items_count: int = 1,
    ):
        """Context manager for profiling synchronous code.

        Args:
            skill_name: Name of the skill
            operation: Operation name for logging
            items_count: Number of items being processed

        Yields:
            None

        Example:
            >>> with profiler.profile("price_predictor", "batch_predict", items_count=100):
            ...     result = predictor.batch_predict(items)
        """
        metrics = self._get_or_create_metrics(skill_name)
        memory_before = self._get_memory_usage()
        start_time = time.perf_counter()

        try:
            yield
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            memory_after = self._get_memory_usage()
            memory_used = max(0, memory_after - memory_before)

            self._update_metrics(metrics, elapsed_ms, success, items_count, memory_used)

            logger.debug(
                "skill_profiled",
                skill_name=skill_name,
                operation=operation,
                latency_ms=round(elapsed_ms, 2),
                success=success,
                items=items_count,
            )

    @asynccontextmanager
    async def aprofile(
        self,
        skill_name: str,
        operation: str = "execute",
        items_count: int = 1,
    ):
        """Async context manager for profiling asynchronous code.

        Args:
            skill_name: Name of the skill
            operation: Operation name for logging
            items_count: Number of items being processed

        Yields:
            None

        Example:
            >>> async with profiler.aprofile("ai_coordinator", "analyze"):
            ...     result = await ai.analyze_item(item)
        """
        metrics = self._get_or_create_metrics(skill_name)
        memory_before = self._get_memory_usage()
        start_time = time.perf_counter()
        success = False  # Default to False, set True on successful completion

        try:
            yield
            success = True
        except BaseException:
            success = False
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            memory_after = self._get_memory_usage()
            memory_used = max(0, memory_after - memory_before)

            self._update_metrics(metrics, elapsed_ms, success, items_count, memory_used)

            logger.debug(
                "skill_profiled_async",
                skill_name=skill_name,
                operation=operation,
                latency_ms=round(elapsed_ms, 2),
                success=success,
                items=items_count,
            )

    def get_skill_metrics(self, skill_name: str) -> dict[str, Any] | None:
        """Get metrics for a specific skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Metrics dictionary or None if not found
        """
        metrics = self.skills_metrics.get(skill_name)
        return metrics.to_dict() if metrics else None

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all skills.

        Returns:
            Dictionary mapping skill names to their metrics
        """
        return {
            name: metrics.to_dict() for name, metrics in self.skills_metrics.items()
        }

    def get_summary(self) -> dict[str, Any]:
        """Get profiler summary.

        Returns:
            Summary with aggregate statistics
        """
        total_executions = sum(m.total_executions for m in self.skills_metrics.values())
        total_successes = sum(
            m.successful_executions for m in self.skills_metrics.values()
        )

        all_latencies = []
        for m in self.skills_metrics.values():
            all_latencies.extend(list(m._recent_latencies))

        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0

        slowest_skill = None
        slowest_latency = 0.0
        for name, m in self.skills_metrics.items():
            if m.latency_avg_ms > slowest_latency:
                slowest_latency = m.latency_avg_ms
                slowest_skill = name

        return {
            "total_skills_profiled": len(self.skills_metrics),
            "total_executions": total_executions,
            "total_successes": total_successes,
            "success_rate": (
                round(total_successes / max(1, total_executions) * 100, 2)
            ),
            "avg_latency_ms": round(avg_latency, 2),
            "slowest_skill": slowest_skill,
            "slowest_skill_latency_ms": round(slowest_latency, 2),
            "skills": list(self.skills_metrics.keys()),
        }

    def identify_bottlenecks(
        self,
        latency_threshold_ms: float = 100.0,
    ) -> list[dict[str, Any]]:
        """Identify performance bottlenecks.

        Args:
            latency_threshold_ms: Latency threshold for bottleneck

        Returns:
            List of bottleneck details
        """
        bottlenecks = []

        for name, metrics in self.skills_metrics.items():
            if metrics.latency_p95_ms > latency_threshold_ms:
                bottlenecks.append(
                    {
                        "skill_name": name,
                        "issue": "high_latency",
                        "latency_p95_ms": round(metrics.latency_p95_ms, 2),
                        "latency_p99_ms": round(metrics.latency_p99_ms, 2),
                        "threshold_ms": latency_threshold_ms,
                        "recommendation": (
                            f"Consider optimizing {name} or adding caching"
                        ),
                    }
                )

            if (
                metrics.total_executions > 10
                and metrics.failed_executions / metrics.total_executions > 0.1
            ):
                bottlenecks.append(
                    {
                        "skill_name": name,
                        "issue": "high_failure_rate",
                        "failure_rate": round(
                            metrics.failed_executions / metrics.total_executions * 100,
                            2,
                        ),
                        "recommendation": f"Investigate failures in {name}",
                    }
                )

            if metrics.memory_peak_bytes > self.MEMORY_WARNING_BYTES:
                bottlenecks.append(
                    {
                        "skill_name": name,
                        "issue": "high_memory_usage",
                        "memory_peak_mb": round(
                            metrics.memory_peak_bytes / (1024 * 1024), 2
                        ),
                        "threshold_mb": round(
                            self.MEMORY_WARNING_BYTES / (1024 * 1024), 2
                        ),
                        "recommendation": f"Optimize memory usage in {name}",
                    }
                )

        return bottlenecks

    def reset_metrics(self, skill_name: str | None = None) -> None:
        """Reset metrics for a skill or all skills.

        Args:
            skill_name: Name of skill to reset, or None for all
        """
        if skill_name:
            if skill_name in self.skills_metrics:
                self.skills_metrics[skill_name] = SkillMetrics(skill_name=skill_name)
        else:
            self.skills_metrics.clear()


# Global profiler instance
_profiler: SkillProfiler | None = None


def get_profiler() -> SkillProfiler:
    """Get or create global profiler instance.

    Returns:
        SkillProfiler instance
    """
    global _profiler
    if _profiler is None:
        _profiler = SkillProfiler()
    return _profiler


def reset_profiler() -> None:
    """Reset global profiler instance."""
    global _profiler
    _profiler = None


def profile_skill(
    skill_name: str,
    operation: str = "execute",
) -> Callable[[F], F]:
    """Decorator for profiling skill functions.

    Args:
        skill_name: Name of the skill
        operation: Operation name for logging

    Returns:
        Decorated function

    Example:
        >>> @profile_skill("ai-arbitrage-predictor")
        ... async def predict_opportunities(items):
        ...     return await predictor.predict(items)
    """

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                profiler = get_profiler()
                async with profiler.aprofile(skill_name, operation):
                    return await func(*args, **kwargs)

            return async_wrapper  # type: ignore

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            profiler = get_profiler()
            with profiler.profile(skill_name, operation):
                return func(*args, **kwargs)

        return sync_wrapper  # type: ignore

    return decorator
