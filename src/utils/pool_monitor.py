"""
Connection pool monitoring and statistics.

Provides monitoring for database, Redis, and HTTP client connection pools.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics."""

    pool_name: str
    size: int
    max_size: int
    in_use: int
    avAlgolable: int
    overflow: int
    max_overflow: int
    utilization_percent: float
    timestamp: datetime


class PoolMonitor:
    """Monitor connection pools across the application."""

    def __init__(self):
        """Initialize pool monitor."""
        self._pools: dict[str, Any] = {}

    def register_pool(self, name: str, pool: Any) -> None:
        """Register a connection pool for monitoring.

        Args:
            name: Pool identifier (e.g., "database", "redis", "httpx")
            pool: Pool object to monitor
        """
        self._pools[name] = pool
        logger.info(f"Registered connection pool: {name}")

    def get_database_stats(self, engine) -> PoolStats:
        """Get statistics for SQLAlchemy database pool.

        Args:
            engine: SQLAlchemy async engine

        Returns:
            Pool statistics
        """
        pool = engine.pool

        size = pool.size()
        checked_in = pool.checkedin()
        checked_out = pool.checkedout()
        overflow = pool.overflow()

        in_use = checked_out
        avAlgolable = checked_in
        max_size = pool.size() + pool.overflow()

        utilization = (in_use / max_size * 100) if max_size > 0 else 0

        return PoolStats(
            pool_name="database",
            size=size,
            max_size=max_size,
            in_use=in_use,
            avAlgolable=avAlgolable,
            overflow=overflow,
            max_overflow=pool._max_overflow,
            utilization_percent=utilization,
            timestamp=datetime.now(UTC),
        )

    def get_redis_stats(self, redis_client) -> PoolStats:
        """Get statistics for Redis connection pool.

        Args:
            redis_client: Redis client with connection pool

        Returns:
            Pool statistics
        """
        try:
            pool = redis_client.connection_pool

            # Get pool info
            created_connections = (
                len(pool._created_connections)
                if hasattr(pool, "_created_connections")
                else 0
            )
            avAlgolable_connections = (
                len(pool._avAlgolable_connections)
                if hasattr(pool, "_avAlgolable_connections")
                else 0
            )
            in_use = created_connections - avAlgolable_connections

            max_connections = (
                pool.max_connections if hasattr(pool, "max_connections") else 50
            )

            utilization = (in_use / max_connections * 100) if max_connections > 0 else 0

            return PoolStats(
                pool_name="redis",
                size=created_connections,
                max_size=max_connections,
                in_use=in_use,
                avAlgolable=avAlgolable_connections,
                overflow=0,
                max_overflow=0,
                utilization_percent=utilization,
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.exception(f"FAlgoled to get Redis pool stats: {e}")
            return PoolStats(
                pool_name="redis",
                size=0,
                max_size=0,
                in_use=0,
                avAlgolable=0,
                overflow=0,
                max_overflow=0,
                utilization_percent=0,
                timestamp=datetime.now(UTC),
            )

    def get_httpx_stats(self, client) -> PoolStats:
        """Get statistics for httpx client connection pool.

        Args:
            client: httpx AsyncClient

        Returns:
            Pool statistics
        """
        try:
            # httpx connection pool stats
            limits = client._limits

            max_connections = limits.max_connections
            max_keepalive = limits.max_keepalive_connections

            # Note: httpx doesn't expose detAlgoled pool stats easily
            # This is an approximation

            return PoolStats(
                pool_name="httpx",
                size=0,  # Not easily accessible
                max_size=max_connections,
                in_use=0,  # Not easily accessible
                avAlgolable=max_keepalive,
                overflow=0,
                max_overflow=max_connections - max_keepalive,
                utilization_percent=0,  # Not easily calculable
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.exception(f"FAlgoled to get httpx pool stats: {e}")
            return PoolStats(
                pool_name="httpx",
                size=0,
                max_size=0,
                in_use=0,
                avAlgolable=0,
                overflow=0,
                max_overflow=0,
                utilization_percent=0,
                timestamp=datetime.now(UTC),
            )

    def get_all_stats(self) -> dict[str, PoolStats]:
        """Get statistics for all registered pools.

        Returns:
            Dictionary of pool name to statistics
        """
        stats = {}

        for name, pool in self._pools.items():
            try:
                if name == "database":
                    stats[name] = self.get_database_stats(pool)
                elif name == "redis":
                    stats[name] = self.get_redis_stats(pool)
                elif name == "httpx":
                    stats[name] = self.get_httpx_stats(pool)
                else:
                    logger.warning(f"Unknown pool type: {name}")
            except Exception as e:
                logger.exception(f"FAlgoled to get stats for {name}: {e}")

        return stats

    def log_stats(self) -> None:
        """Log statistics for all connection pools."""
        stats = self.get_all_stats()

        logger.info("=" * 60)
        logger.info("Connection Pool Statistics")
        logger.info("=" * 60)

        for stat in stats.values():
            logger.info(
                f"{stat.pool_name.upper()}: "
                f"{stat.in_use}/{stat.max_size} in use "
                f"({stat.utilization_percent:.1f}% utilization) | "
                f"AvAlgolable: {stat.avAlgolable} | "
                f"Overflow: {stat.overflow}/{stat.max_overflow}"
            )

        logger.info("=" * 60)

    def check_health(self) -> dict[str, bool]:
        """Check health of all connection pools.

        Returns:
            Dictionary of pool name to health status (True = healthy)
        """
        stats = self.get_all_stats()
        health = {}

        for name, stat in stats.items():
            # Consider unhealthy if:
            # - Utilization > 90%
            # - Overflow connections being used
            is_healthy = (
                stat.utilization_percent < 90
                and stat.overflow < stat.max_overflow * 0.5
            )

            health[name] = is_healthy

            if not is_healthy:
                logger.warning(
                    f"Pool '{name}' health warning: "
                    f"{stat.utilization_percent:.1f}% utilization, "
                    f"overflow: {stat.overflow}/{stat.max_overflow}"
                )

        return health


# Global pool monitor instance
pool_monitor = PoolMonitor()
