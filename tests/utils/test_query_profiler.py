"""Tests for Query Profiler module.

Based on SkillsMP recommendations for testing database utilities.
"""


import pytest


class TestQueryStats:
    """Tests for QueryStats dataclass."""

    def test_initial_values(self):
        """Test initial statistics values."""
        from src.utils.query_profiler import QueryStats

        # Act
        stats = QueryStats()

        # Assert
        assert stats.count == 0
        assert stats.total_time_ms == 0.0
        assert stats.min_time_ms == float("inf")
        assert stats.max_time_ms == 0.0
        assert stats.last_query == ""

    def test_avg_time_ms_empty(self):
        """Test average time with no queries."""
        from src.utils.query_profiler import QueryStats

        # Act
        stats = QueryStats()

        # Assert
        assert stats.avg_time_ms == 0.0

    def test_record_single_query(self):
        """Test recording a single query."""
        from src.utils.query_profiler import QueryStats

        # Arrange
        stats = QueryStats()

        # Act
        stats.record(10.5, "SELECT * FROM users")

        # Assert
        assert stats.count == 1
        assert stats.total_time_ms == 10.5
        assert stats.min_time_ms == 10.5
        assert stats.max_time_ms == 10.5
        assert "SELECT" in stats.last_query

    def test_record_multiple_queries(self):
        """Test recording multiple queries."""
        from src.utils.query_profiler import QueryStats

        # Arrange
        stats = QueryStats()

        # Act
        stats.record(5.0, "SELECT 1")
        stats.record(15.0, "SELECT 2")
        stats.record(10.0, "SELECT 3")

        # Assert
        assert stats.count == 3
        assert stats.total_time_ms == 30.0
        assert stats.min_time_ms == 5.0
        assert stats.max_time_ms == 15.0
        assert stats.avg_time_ms == 10.0


class TestProfilerReport:
    """Tests for ProfilerReport dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from src.utils.query_profiler import ProfilerReport, QueryStats

        # Arrange
        stats = QueryStats()
        stats.record(10.0, "SELECT 1")
        stats.record(20.0, "SELECT 2")

        report = ProfilerReport(
            total_queries=2,
            total_time_ms=30.0,
            slow_queries=[("SELECT slow", 100.0)],
            queries_by_type={"SELECT": stats},
        )

        # Act
        result = report.to_dict()

        # Assert
        assert result["total_queries"] == 2
        assert result["total_time_ms"] == 30.0
        assert result["avg_time_ms"] == 15.0
        assert result["slow_queries_count"] == 1
        assert result["slowest_query_ms"] == 100.0
        assert "SELECT" in result["queries_by_type"]


class TestQueryProfiler:
    """Tests for QueryProfiler class."""

    @pytest.fixture
    def profiler(self):
        """Create profiler without engine."""
        from src.utils.query_profiler import QueryProfiler

        return QueryProfiler(slow_threshold_ms=50.0)

    def test_extract_query_type_select(self, profiler):
        """Test extracting SELECT query type."""
        # Act
        result = profiler._extract_query_type("SELECT * FROM users WHERE id = 1")

        # Assert
        assert result == "SELECT"

    def test_extract_query_type_insert(self, profiler):
        """Test extracting INSERT query type."""
        # Act
        result = profiler._extract_query_type("INSERT INTO users (name) VALUES ('test')")

        # Assert
        assert result == "INSERT"

    def test_extract_query_type_update(self, profiler):
        """Test extracting UPDATE query type."""
        # Act
        result = profiler._extract_query_type("UPDATE users SET name = 'test'")

        # Assert
        assert result == "UPDATE"

    def test_extract_query_type_delete(self, profiler):
        """Test extracting DELETE query type."""
        # Act
        result = profiler._extract_query_type("DELETE FROM users WHERE id = 1")

        # Assert
        assert result == "DELETE"

    def test_extract_query_type_other(self, profiler):
        """Test extracting unknown query type."""
        # Act
        result = profiler._extract_query_type("EXPLAlgoN SELECT * FROM users")

        # Assert
        assert result == "OTHER"

    def test_extract_table_name_select(self, profiler):
        """Test extracting table from SELECT."""
        # Act
        result = profiler._extract_table_name("SELECT * FROM users WHERE id = 1")

        # Assert
        assert result == "users"

    def test_extract_table_name_insert(self, profiler):
        """Test extracting table from INSERT."""
        # Act
        result = profiler._extract_table_name("INSERT INTO orders (id) VALUES (1)")

        # Assert
        assert result == "orders"

    def test_extract_table_name_update(self, profiler):
        """Test extracting table from UPDATE."""
        # Act
        result = profiler._extract_table_name("UPDATE products SET price = 100")

        # Assert
        assert result == "products"

    def test_extract_table_name_delete(self, profiler):
        """Test extracting table from DELETE."""
        # Act
        result = profiler._extract_table_name("DELETE FROM logs WHERE created < NOW()")

        # Assert
        assert result == "logs"

    def test_record_query_updates_stats(self, profiler):
        """Test that recording updates statistics."""
        # Act
        profiler._record_query("SELECT * FROM users", 10.0)
        profiler._record_query("SELECT * FROM users", 20.0)

        # Assert
        assert profiler._total_queries == 2
        assert profiler._total_time_ms == 30.0
        assert "SELECT" in profiler._queries_by_type
        assert profiler._queries_by_type["SELECT"].count == 2

    def test_record_slow_query(self, profiler):
        """Test slow query recording."""
        # Act - query above threshold
        profiler._record_query("SELECT slow FROM big_table", 100.0)

        # Assert
        assert len(profiler._slow_queries) == 1
        assert profiler._slow_queries[0][1] == 100.0

    def test_record_query_not_slow(self, profiler):
        """Test fast query not recorded as slow."""
        # Act - query below threshold
        profiler._record_query("SELECT fast FROM small_table", 10.0)

        # Assert
        assert len(profiler._slow_queries) == 0

    def test_get_report(self, profiler):
        """Test generating report."""
        # Arrange
        profiler._record_query("SELECT * FROM users", 10.0)
        profiler._record_query("INSERT INTO logs VALUES (1)", 5.0)

        # Act
        report = profiler.get_report()

        # Assert
        assert report.total_queries == 2
        assert report.total_time_ms == 15.0
        assert "SELECT" in report.queries_by_type
        assert "INSERT" in report.queries_by_type

    def test_reset(self, profiler):
        """Test resetting statistics."""
        # Arrange
        profiler._record_query("SELECT 1", 10.0)
        profiler._record_slow_query("SELECT slow", 100.0)

        # Act
        profiler.reset()

        # Assert
        assert profiler._total_queries == 0
        assert profiler._total_time_ms == 0.0
        assert len(profiler._slow_queries) == 0
        assert len(profiler._queries_by_type) == 0

    def test_enable_without_engine_raises(self, profiler):
        """Test enabling without engine raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Engine is required"):
            profiler.enable()

    def test_max_slow_queries_limit(self, profiler):
        """Test that slow queries are limited."""
        # Arrange
        profiler._max_slow_queries = 3

        # Act - add 5 slow queries
        for i in range(5):
            profiler._record_slow_query(f"SELECT {i}", 100.0 + i)

        # Assert - only 3 kept (slowest)
        assert len(profiler._slow_queries) == 3


class TestGetQueryProfiler:
    """Tests for get_query_profiler function."""

    def test_singleton_creation(self):
        """Test singleton is created."""
        from src.utils import query_profiler

        # Reset singleton
        query_profiler._profiler = None

        # Act
        p1 = query_profiler.get_query_profiler()
        p2 = query_profiler.get_query_profiler()

        # Assert
        assert p1 is p2
