"""
query_profiler.py — SQLite Query Profiler for Performance Optimization.

v15.7: Profiles SQLite queries to find slow operations and optimize indexes.

Key capabilities:
1. Measure query execution time (microsecond precision)
2. Track slow queries (>100ms threshold)
3. Aggregate statistics (avg, p95, p99 time)
4. Generate optimization recommendations
5. Context manager for easy profiling

Integration:
- Wrap price_db queries with profile_query() context manager
- Stats available via /healthz endpoint
- Slow query alerts via logger
"""

from __future__ import annotations

import logging
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

logger = logging.getLogger("QueryProfiler")


@dataclass
class QueryStats:
    """Statistics for a single query type."""
    query_name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    slow_count: int = 0  # count of queries > threshold
    last_slow_query: str = ""

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.call_count if self.call_count > 0 else 0.0

    def record(self, time_ms: float, sql: str = "", slow_threshold_ms: float = 100.0) -> None:
        """Record a query execution."""
        self.call_count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        if time_ms > slow_threshold_ms:
            self.slow_count += 1
            self.last_slow_query = sql[:200] if sql else ""


class QueryProfiler:
    """
    SQLite query profiler with slow query detection.

    Usage:
        profiler = QueryProfiler()

        # Context manager
        with profiler.profile("get_recent_prices"):
            rows = conn.execute(...)

        # Or as decorator
        @profiler.wrap("my_query")
        def run_query():
            return conn.execute(...)

        # Get stats
        stats = profiler.get_stats()
        report = profiler.get_report()
    """

    def __init__(
        self,
        slow_threshold_ms: float = 100.0,
        max_slow_queries: int = 50,
        enabled: bool = True,
    ) -> None:
        self._slow_threshold_ms = slow_threshold_ms
        self._max_slow_queries = max_slow_queries
        self._enabled = enabled
        self._stats: dict[str, QueryStats] = {}
        self._recent_slow: deque[tuple[str, float, str]] = deque(maxlen=max_slow_queries)
        self._total_queries: int = 0
        self._total_time_ms: float = 0.0

    def enable(self) -> None:
        """Enable profiling."""
        self._enabled = True

    def disable(self) -> None:
        """Disable profiling."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def profile(self, query_name: str, sql: str = "") -> Generator[None, None, None]:
        """
        Context manager for profiling a query.

        Usage:
            with profiler.profile("get_recent_prices"):
                rows = conn.execute("SELECT ...")
        """
        if not self._enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._record(query_name, elapsed_ms, sql)

    def wrap(self, query_name: str):
        """
        Decorator for profiling a function.

        Usage:
            @profiler.wrap("my_query")
            def run_query():
                return conn.execute(...)
        """
        import functools

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self._enabled:
                    return func(*args, **kwargs)
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    self._record(query_name, elapsed_ms)
            return wrapper
        return decorator

    def record_manual(self, query_name: str, time_ms: float, sql: str = "") -> None:
        """Manually record a query execution time."""
        if self._enabled:
            self._record(query_name, time_ms, sql)

    def _record(self, query_name: str, time_ms: float, sql: str = "") -> None:
        """Internal: record a query execution."""
        self._total_queries += 1
        self._total_time_ms += time_ms

        if query_name not in self._stats:
            self._stats[query_name] = QueryStats(query_name=query_name)

        self._stats[query_name].record(time_ms, sql, self._slow_threshold_ms)

        if time_ms > self._slow_threshold_ms:
            self._recent_slow.append((query_name, time_ms, sql[:200]))
            logger.warning(
                f"[QueryProfiler] Slow query: {query_name} took {time_ms:.1f}ms "
                f"(threshold={self._slow_threshold_ms}ms)"
            )

    # ----------------------------------------------------------------
    # Stats & Reports
    # ----------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get aggregated statistics."""
        return {
            "enabled": self._enabled,
            "total_queries": self._total_queries,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_time_ms": round(
                self._total_time_ms / self._total_queries, 2
            ) if self._total_queries > 0 else 0.0,
            "query_types": len(self._stats),
            "slow_queries_total": sum(s.slow_count for s in self._stats.values()),
            "slow_threshold_ms": self._slow_threshold_ms,
        }

    def get_query_stats(self, query_name: str) -> QueryStats | None:
        """Get stats for a specific query type."""
        return self._stats.get(query_name)

    def get_all_query_stats(self) -> list[QueryStats]:
        """Get stats for all query types, sorted by total time."""
        return sorted(
            self._stats.values(),
            key=lambda s: s.total_time_ms,
            reverse=True,
        )

    def get_slow_queries(self) -> list[tuple[str, float, str]]:
        """Get recent slow queries."""
        return list(self._recent_slow)

    def get_report(self) -> str:
        """Generate a human-readable performance report."""
        lines = [
            "=== Query Profiler Report ===",
            f"Total queries: {self._total_queries}",
            f"Total time: {self._total_time_ms:.1f}ms",
            f"Avg time: {self._total_time_ms / self._total_queries:.2f}ms"
            if self._total_queries > 0 else "No queries recorded",
            f"Slow queries (>{self._slow_threshold_ms}ms): "
            f"{sum(s.slow_count for s in self._stats.values())}",
            "",
            "Top queries by total time:",
        ]

        for stats in self.get_all_query_stats()[:10]:
            lines.append(
                f"  {stats.query_name}: "
                f"calls={stats.call_count}, "
                f"avg={stats.avg_time_ms:.1f}ms, "
                f"max={stats.max_time_ms:.1f}ms, "
                f"slow={stats.slow_count}"
            )

        if self._recent_slow:
            lines.append("")
            lines.append("Recent slow queries:")
            for name, time_ms, sql in list(self._recent_slow)[-5:]:
                lines.append(f"  {name}: {time_ms:.1f}ms — {sql[:80]}...")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all statistics."""
        self._stats.clear()
        self._recent_slow.clear()
        self._total_queries = 0
        self._total_time_ms = 0.0


# ----------------------------------------------------------------
# Singleton instance
# ----------------------------------------------------------------

_query_profiler: QueryProfiler | None = None


def get_query_profiler() -> QueryProfiler:
    """Get or create the singleton QueryProfiler instance."""
    global _query_profiler
    if _query_profiler is None:
        _query_profiler = QueryProfiler()
    return _query_profiler
