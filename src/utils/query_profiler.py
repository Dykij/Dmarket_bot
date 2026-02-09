"""SQL Query profiling utilities.

This module provides query profiling capabilities for SQLAlchemy,
enabling performance monitoring and optimization of database queries.

Based on SkillsMP PostgreSQL/SQLAlchemy recommendations.
"""

import logging
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Constants for query truncation
QUERY_STATS_TRUNCATE_LENGTH = 200
SLOW_QUERY_TRUNCATE_LENGTH = 500


@dataclass
class QueryStats:
    """Statistics for a single query type."""

    count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    last_query: str = ""

    @property
    def avg_time_ms(self) -> float:
        """Calculate average query time."""
        if self.count == 0:
            return 0.0
        return self.total_time_ms / self.count

    def record(self, time_ms: float, query: str) -> None:
        """Record a query execution."""
        self.count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        self.last_query = query[:QUERY_STATS_TRUNCATE_LENGTH]


@dataclass
class ProfilerReport:
    """Profiler statistics report."""

    total_queries: int = 0
    total_time_ms: float = 0.0
    slow_queries: list[tuple[str, float]] = field(default_factory=list)
    queries_by_table: dict[str, QueryStats] = field(default_factory=dict)
    queries_by_type: dict[str, QueryStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "total_queries": self.total_queries,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.total_time_ms / max(1, self.total_queries), 2),
            "slow_queries_count": len(self.slow_queries),
            "slowest_query_ms": max((q[1] for q in self.slow_queries), default=0),
            "queries_by_type": {
                k: {
                    "count": v.count,
                    "total_ms": round(v.total_time_ms, 2),
                    "avg_ms": round(v.avg_time_ms, 2),
                }
                for k, v in self.queries_by_type.items()
            },
        }


class QueryProfiler:
    """SQL query profiler for SQLAlchemy.

    Features:
    - Automatic query timing via SQLAlchemy events
    - Slow query detection and logging
    - Statistics aggregation by table and query type
    - Context manager for scoped profiling

    Example:
        >>> profiler = QueryProfiler(engine, slow_threshold_ms=100)
        >>> profiler.enable()
        >>>
        >>> # ... run queries ...
        >>>
        >>> report = profiler.get_report()
        >>> print(f"Total queries: {report.total_queries}")
        >>> print(f"Slow queries: {len(report.slow_queries)}")
    """

    def __init__(
        self,
        engine: Engine | None = None,
        slow_threshold_ms: float = 100.0,
        log_slow_queries: bool = True,
        max_slow_queries: int = 100,
    ):
        """Initialize query profiler.

        Args:
            engine: SQLAlchemy engine to profile
            slow_threshold_ms: Threshold for slow query detection (default: 100ms)
            log_slow_queries: Whether to log slow queries (default: True)
            max_slow_queries: Max slow queries to store (default: 100)
        """
        self._engine = engine
        self._slow_threshold_ms = slow_threshold_ms
        self._log_slow_queries = log_slow_queries
        self._max_slow_queries = max_slow_queries
        self._enabled = False

        # Statistics storage
        self._total_queries = 0
        self._total_time_ms = 0.0
        self._slow_queries: list[tuple[str, float]] = []
        self._queries_by_table: dict[str, QueryStats] = defaultdict(QueryStats)
        self._queries_by_type: dict[str, QueryStats] = defaultdict(QueryStats)

        # Query start times (connection ID -> start time)
        self._query_start_times: dict[int, tuple[float, str]] = {}

    def enable(self, engine: Engine | None = None) -> None:
        """Enable query profiling.

        Args:
            engine: SQLAlchemy engine (optional if provided in constructor)
        """
        if engine:
            self._engine = engine

        if self._engine is None:
            raise ValueError("Engine is required")

        if not self._enabled:
            event.listen(self._engine, "before_cursor_execute", self._before_execute)
            event.listen(self._engine, "after_cursor_execute", self._after_execute)
            self._enabled = True
            logger.info("Query profiler enabled")

    def disable(self) -> None:
        """Disable query profiling."""
        if self._enabled and self._engine:
            event.remove(self._engine, "before_cursor_execute", self._before_execute)
            event.remove(self._engine, "after_cursor_execute", self._after_execute)
            self._enabled = False
            logger.info("Query profiler disabled")

    def _before_execute(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Called before query execution."""
        conn_id = id(conn)
        self._query_start_times[conn_id] = (time.perf_counter(), statement)

    def _after_execute(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        """Called after query execution."""
        conn_id = id(conn)
        start_data = self._query_start_times.pop(conn_id, None)

        if start_data is None:
            return

        start_time, original_statement = start_data
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        self._record_query(original_statement, elapsed_ms)

    def _record_query(self, statement: str, elapsed_ms: float) -> None:
        """Record query statistics."""
        self._total_queries += 1
        self._total_time_ms += elapsed_ms

        # Extract query type (SELECT, INSERT, UPDATE, DELETE, etc.)
        query_type = self._extract_query_type(statement)
        self._queries_by_type[query_type].record(elapsed_ms, statement)

        # Extract table name
        table_name = self._extract_table_name(statement)
        if table_name:
            self._queries_by_table[table_name].record(elapsed_ms, statement)

        # Check for slow queries
        if elapsed_ms >= self._slow_threshold_ms:
            self._record_slow_query(statement, elapsed_ms)

    def _record_slow_query(self, statement: str, elapsed_ms: float) -> None:
        """Record a slow query."""
        if len(self._slow_queries) >= self._max_slow_queries:
            # Remove fastest slow query to make room
            self._slow_queries.sort(key=lambda x: x[1])
            self._slow_queries.pop(0)

        self._slow_queries.append((statement[:SLOW_QUERY_TRUNCATE_LENGTH], elapsed_ms))

        if self._log_slow_queries:
            logger.warning(
                "Slow query detected",
                extra={
                    "elapsed_ms": round(elapsed_ms, 2),
                    "query": statement[:QUERY_STATS_TRUNCATE_LENGTH],
                },
            )

    def _extract_query_type(self, statement: str) -> str:
        """Extract query type from statement."""
        statement = statement.strip().upper()
        for query_type in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"):
            if statement.startswith(query_type):
                return query_type
        return "OTHER"

    def _extract_table_name(self, statement: str) -> str | None:
        """Extract primary table name from statement."""
        statement = statement.strip().upper()

        # Simple extraction based on common patterns
        if statement.startswith("SELECT"):
            # Look for FROM clause
            if " FROM " in statement:
                parts = statement.split(" FROM ")[1].split()
                if parts:
                    return parts[0].strip("(),").lower()
        elif statement.startswith("INSERT"):
            if " INTO " in statement:
                parts = statement.split(" INTO ")[1].split()
                if parts:
                    return parts[0].strip("(),").lower()
        elif statement.startswith("UPDATE"):
            parts = statement.split()[1:]
            if parts:
                return parts[0].strip("(),").lower()
        elif statement.startswith("DELETE"):
            if " FROM " in statement:
                parts = statement.split(" FROM ")[1].split()
                if parts:
                    return parts[0].strip("(),").lower()

        return None

    def get_report(self) -> ProfilerReport:
        """Get profiling report.

        Returns:
            ProfilerReport with statistics
        """
        return ProfilerReport(
            total_queries=self._total_queries,
            total_time_ms=self._total_time_ms,
            slow_queries=list(self._slow_queries),
            queries_by_table=dict(self._queries_by_table),
            queries_by_type=dict(self._queries_by_type),
        )

    def reset(self) -> None:
        """Reset all statistics."""
        self._total_queries = 0
        self._total_time_ms = 0.0
        self._slow_queries.clear()
        self._queries_by_table.clear()
        self._queries_by_type.clear()
        logger.info("Query profiler statistics reset")

    def log_summary(self) -> None:
        """Log profiling summary."""
        report = self.get_report()
        logger.info(
            "Query profiler summary",
            extra={
                "total_queries": report.total_queries,
                "total_time_ms": round(report.total_time_ms, 2),
                "slow_queries": len(report.slow_queries),
                "queries_by_type": {
                    k: v.count for k, v in report.queries_by_type.items()
                },
            },
        )

    @contextmanager
    def profile_block(self, name: str = "unnamed") -> Generator[ProfilerReport, None, None]:
        """Profile a block of code.

        Args:
            name: Block name for logging

        Yields:
            ProfilerReport for the block

        Example:
            >>> with profiler.profile_block("user_queries"):
            ...     # queries here
            ...     pass
        """
        self.reset()
        start_time = time.perf_counter()

        yield self.get_report()

        elapsed = time.perf_counter() - start_time
        report = self.get_report()
        logger.info(
            f"Profile block '{name}' completed",
            extra={
                "block_name": name,
                "elapsed_s": round(elapsed, 3),
                "queries": report.total_queries,
                "query_time_ms": round(report.total_time_ms, 2),
            },
        )


# Singleton instance
_profiler: QueryProfiler | None = None


def get_query_profiler(
    engine: Engine | None = None,
    slow_threshold_ms: float = 100.0,
) -> QueryProfiler:
    """Get or create global query profiler.

    Args:
        engine: SQLAlchemy engine
        slow_threshold_ms: Slow query threshold

    Returns:
        QueryProfiler instance
    """
    global _profiler
    if _profiler is None:
        _profiler = QueryProfiler(
            engine=engine,
            slow_threshold_ms=slow_threshold_ms,
        )
    return _profiler
