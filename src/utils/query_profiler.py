"""
query_profiler.py — SQL query performance profiling.
"""

from dataclasses import dataclass, field
from typing import Any


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
        return self.total_time_ms / max(self.count, 1)

    def record(self, time_ms: float, query: str) -> None:
        self.count += 1
        self.total_time_ms += time_ms
        self.min_time_ms = min(self.min_time_ms, time_ms)
        self.max_time_ms = max(self.max_time_ms, time_ms)
        self.last_query = query


@dataclass
class ProfilerReport:
    """Profiling report."""
    total_queries: int = 0
    total_time_ms: float = 0.0
    slow_queries: list[tuple[str, float]] = field(default_factory=list)
    queries_by_type: dict[str, QueryStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        avg = self.total_time_ms / max(self.total_queries, 1)
        slowest = max((t for _, t in self.slow_queries), default=0.0)
        return {
            "total_queries": self.total_queries,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": avg,
            "slow_queries_count": len(self.slow_queries),
            "slowest_query_ms": slowest,
            "queries_by_type": {k: {
                "count": v.count,
                "avg_ms": round(v.avg_time_ms, 2),
                "max_ms": round(v.max_time_ms, 2),
            } for k, v in self.queries_by_type.items()},
        }


class QueryProfiler:
    """Profiles SQL query performance."""

    def __init__(self, slow_threshold_ms: float = 100.0, max_slow_queries: int = 100) -> None:
        self.slow_threshold_ms = slow_threshold_ms
        self._max_slow_queries = max_slow_queries
        self._queries_by_type: dict[str, QueryStats] = {}
        self._slow_queries: list[tuple[str, float]] = []
        self._enabled = False
        self._total_queries = 0
        self._total_time_ms = 0.0
        self._engine: Any = None

    def enable(self, engine: Any = None) -> None:
        """Enable query profiling. Requires engine."""
        if engine is None:
            raise ValueError("Engine is required")
        self._engine = engine
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def _record_query(self, query: str, duration_ms: float, params: Any = None) -> None:
        """Record a query execution."""
        self._total_queries += 1
        self._total_time_ms += duration_ms
        query_type = self._extract_query_type(query)
        if query_type not in self._queries_by_type:
            self._queries_by_type[query_type] = QueryStats()
        self._queries_by_type[query_type].record(duration_ms, query)
        if duration_ms >= self.slow_threshold_ms:
            self._record_slow_query(query, duration_ms)

    def record_query(self, query: str, duration_ms: float, params: Any = None) -> None:
        """Public alias for _record_query."""
        self._record_query(query, duration_ms, params)

    def _record_slow_query(self, query: str, duration_ms: float) -> None:
        """Record a slow query."""
        self._slow_queries.append((query, duration_ms))
        if len(self._slow_queries) > self._max_slow_queries:
            self._slow_queries = sorted(
                self._slow_queries, key=lambda x: x[1], reverse=True
            )[:self._max_slow_queries]

    def get_report(self) -> ProfilerReport:
        return ProfilerReport(
            total_queries=self._total_queries,
            total_time_ms=self._total_time_ms,
            slow_queries=list(self._slow_queries),
            queries_by_type=dict(self._queries_by_type),
        )

    def reset(self) -> None:
        self._queries_by_type.clear()
        self._slow_queries.clear()
        self._total_queries = 0
        self._total_time_ms = 0.0

    @staticmethod
    def _extract_query_type(query: str) -> str:
        stripped = query.strip().upper()
        for qtype in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            if stripped.startswith(qtype):
                return qtype
        return "OTHER"

    @staticmethod
    def _extract_table_name(query: str) -> str:
        stripped = query.strip().upper()
        parts = stripped.split()
        try:
            if parts[0] == "SELECT":
                for i, p in enumerate(parts):
                    if p == "FROM" and i + 1 < len(parts):
                        return parts[i + 1].lower().strip('"`')
            elif parts[0] == "INSERT":
                for i, p in enumerate(parts):
                    if p == "INTO" and i + 1 < len(parts):
                        return parts[i + 1].lower().strip('"`')
            elif parts[0] == "UPDATE":
                if len(parts) > 1:
                    return parts[1].lower().strip('"`')
            elif parts[0] == "DELETE":
                for i, p in enumerate(parts):
                    if p == "FROM" and i + 1 < len(parts):
                        return parts[i + 1].lower().strip('"`')
        except (IndexError, ValueError):
            pass
        return "unknown"


_profiler: QueryProfiler | None = None


def get_query_profiler() -> QueryProfiler:
    global _profiler
    if _profiler is None:
        _profiler = QueryProfiler()
    return _profiler
