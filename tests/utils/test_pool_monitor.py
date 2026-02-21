"""Tests for pool_monitor module.

This module tests the PoolMonitor class for connection pool
monitoring and management.
"""

from unittest.mock import MagicMock

import pytest

from src.utils.pool_monitor import PoolMonitor, PoolStats


class TestPoolMonitor:
    """Tests for PoolMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create PoolMonitor instance."""
        return PoolMonitor()

    def test_init(self, monitor):
        """Test initialization."""
        assert monitor is not None
        assert hasattr(monitor, "_pools")
        assert isinstance(monitor._pools, dict)

    def test_register_pool(self, monitor):
        """Test registering connection pool."""
        pool = MagicMock()
        pool.size = 10

        monitor.register_pool("database", pool)

        assert "database" in monitor._pools

    def test_register_multiple_pools(self, monitor):
        """Test registering multiple pools."""
        pool1 = MagicMock()
        pool2 = MagicMock()

        monitor.register_pool("database", pool1)
        monitor.register_pool("redis", pool2)

        assert "database" in monitor._pools
        assert "redis" in monitor._pools
        assert len(monitor._pools) == 2

    def test_get_all_stats_empty(self, monitor):
        """Test getting stats with no registered pools."""
        stats = monitor.get_all_stats()
        assert stats == {}

    def test_get_all_stats_with_pools(self, monitor):
        """Test getting all pools stats."""
        # Mock database engine with pool
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 7
        pool.checkedout.return_value = 3
        pool.overflow.return_value = 0
        pool._max_overflow = 5
        engine.pool = pool

        monitor.register_pool("database", engine)

        stats = monitor.get_all_stats()

        assert "database" in stats
        assert isinstance(stats["database"], PoolStats)

    def test_check_health_empty(self, monitor):
        """Test health check with no pools."""
        health = monitor.check_health()
        assert health == {}

    def test_check_health_with_healthy_pool(self, monitor):
        """Test health check with healthy pool."""
        # Mock database engine with healthy pool
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 7
        pool.checkedout.return_value = 3
        pool.overflow.return_value = 0
        pool._max_overflow = 5
        engine.pool = pool

        monitor.register_pool("database", engine)

        health = monitor.check_health()

        assert "database" in health
        assert health["database"] is True

    def test_check_health_with_unhealthy_pool(self, monitor):
        """Test health check with unhealthy pool (high utilization)."""
        # Mock database engine with overutilized pool
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 0
        pool.checkedout.return_value = 10  # All connections in use
        pool.overflow.return_value = 4
        pool._max_overflow = 5
        engine.pool = pool

        monitor.register_pool("database", engine)

        health = monitor.check_health()

        assert "database" in health
        # Should be unhealthy due to high utilization and overflow
        assert health["database"] is False

    def test_log_stats(self, monitor, caplog):
        """Test logging stats."""
        # Mock database engine
        engine = MagicMock()
        pool = MagicMock()
        pool.size.return_value = 10
        pool.checkedin.return_value = 7
        pool.checkedout.return_value = 3
        pool.overflow.return_value = 0
        pool._max_overflow = 5
        engine.pool = pool

        monitor.register_pool("database", engine)

        # Should not rAlgose
        monitor.log_stats()


class TestPoolStats:
    """Tests for PoolStats dataclass."""

    def test_pool_stats_creation(self):
        """Test PoolStats creation."""
        from datetime import UTC, datetime

        stats = PoolStats(
            pool_name="database",
            size=10,
            max_size=15,
            in_use=3,
            avAlgolable=7,
            overflow=0,
            max_overflow=5,
            utilization_percent=20.0,
            timestamp=datetime.now(UTC),
        )

        assert stats.pool_name == "database"
        assert stats.size == 10
        assert stats.max_size == 15
        assert stats.in_use == 3
        assert stats.avAlgolable == 7
        assert stats.overflow == 0
        assert stats.max_overflow == 5
        assert stats.utilization_percent == 20.0


class TestGlobalPoolMonitor:
    """Tests for global pool_monitor instance."""

    def test_global_instance_exists(self):
        """Test that global pool_monitor instance exists."""
        from src.utils.pool_monitor import pool_monitor

        assert pool_monitor is not None
        assert isinstance(pool_monitor, PoolMonitor)
