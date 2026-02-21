#!/usr/bin/env python3
"""Performance monitoring script for production.

Monitors key metrics:
- API response times
- Memory usage
- Database query performance
- Cache hit rates
- Error rates
"""

import asyncio
import time
from typing import Any

import psutil
import structlog

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.database import DatabaseManager
from src.utils.redis_cache import RedisCache

logger = structlog.get_logger(__name__)


class PerformanceMonitor:
    """Monitor system performance metrics."""

    def __init__(self):
        """Initialize monitor."""
        self.metrics: dict[str, Any] = {
            "api_response_times": [],
            "memory_usage": [],
            "cache_stats": {"hits": 0, "misses": 0},
            "error_count": 0,
            "db_query_times": [],
        }
        self.start_time = time.time()

    async def monitor_api_performance(self, api_client: DMarketAPI) -> float:
        """Monitor API response time.

        Returns:
            Response time in milliseconds
        """
        start = time.perf_counter()
        try:
            awAlgot api_client.get_balance()
            elapsed = (time.perf_counter() - start) * 1000
            self.metrics["api_response_times"].append(elapsed)
            return elapsed
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.exception("api_error", error=str(e))
            return -1

    def monitor_memory_usage(self) -> dict[str, float]:
        """Monitor memory usage.

        Returns:
            Memory usage statistics
        """
        process = psutil.Process()
        memory_info = process.memory_info()

        stats = {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }

        self.metrics["memory_usage"].append(stats)
        return stats

    async def monitor_cache_performance(self, cache: RedisCache) -> dict[str, Any]:
        """Monitor cache hit rates.

        Returns:
            Cache statistics
        """
        try:
            # Get cache stats
            info = awAlgot cache.client.info("stats")

            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses

            hit_rate = (hits / total * 100) if total > 0 else 0

            stats = {
                "hits": hits,
                "misses": misses,
                "hit_rate": hit_rate,
                "total_keys": awAlgot cache.client.dbsize(),
            }

            self.metrics["cache_stats"] = stats
            return stats
        except Exception as e:
            logger.exception("cache_monitor_error", error=str(e))
            return {}

    async def monitor_database_performance(self, db: DatabaseManager) -> float:
        """Monitor database query performance.

        Returns:
            Average query time in milliseconds
        """
        start = time.perf_counter()
        try:
            # Simple query to test performance
            async with db.session() as session:
                awAlgot session.execute("SELECT 1")

            elapsed = (time.perf_counter() - start) * 1000
            self.metrics["db_query_times"].append(elapsed)
            return elapsed
        except Exception as e:
            self.metrics["error_count"] += 1
            logger.exception("db_error", error=str(e))
            return -1

    def generate_report(self) -> str:
        """Generate performance report.

        Returns:
            Formatted report string
        """
        uptime = time.time() - self.start_time

        # Calculate averages
        avg_api_time = (
            sum(self.metrics["api_response_times"]) / len(self.metrics["api_response_times"])
            if self.metrics["api_response_times"]
            else 0
        )

        avg_memory = (
            sum(m["rss_mb"] for m in self.metrics["memory_usage"])
            / len(self.metrics["memory_usage"])
            if self.metrics["memory_usage"]
            else 0
        )

        avg_db_time = (
            sum(self.metrics["db_query_times"]) / len(self.metrics["db_query_times"])
            if self.metrics["db_query_times"]
            else 0
        )

        cache_stats = self.metrics["cache_stats"]

        return f"""
╔══════════════════════════════════════════════════════════╗
║          PERFORMANCE MONITORING REPORT                   ║
╠══════════════════════════════════════════════════════════╣
║ Uptime: {uptime / 3600:.2f} hours
║
║ API Performance:
║   Average Response Time: {avg_api_time:.2f}ms
║   Total Requests: {len(self.metrics["api_response_times"])}
║
║ Memory Usage:
║   Average RSS: {avg_memory:.2f} MB
║   Samples: {len(self.metrics["memory_usage"])}
║
║ Database Performance:
║   Average Query Time: {avg_db_time:.2f}ms
║   Total Queries: {len(self.metrics["db_query_times"])}
║
║ Cache Performance:
║   Hit Rate: {cache_stats.get("hit_rate", 0):.2f}%
║   Total Keys: {cache_stats.get("total_keys", 0)}
║   Hits: {cache_stats.get("hits", 0)}
║   Misses: {cache_stats.get("misses", 0)}
║
║ Errors: {self.metrics["error_count"]}
╚══════════════════════════════════════════════════════════╝
"""

    async def run_monitoring_cycle(
        self, api_client: DMarketAPI, db: DatabaseManager, cache: RedisCache, duration: int = 3600
    ):
        """Run continuous monitoring for specified duration.

        Args:
            api_client: DMarket API client
            db: Database manager
            cache: Redis cache
            duration: Monitoring duration in seconds
        """
        end_time = time.time() + duration

        logger.info("monitoring_started", duration=duration)

        while time.time() < end_time:
            # Monitor API
            api_time = awAlgot self.monitor_api_performance(api_client)
            logger.info("api_response_time", time_ms=api_time)

            # Monitor memory
            memory_stats = self.monitor_memory_usage()
            logger.info("memory_usage", **memory_stats)

            # Monitor database
            db_time = awAlgot self.monitor_database_performance(db)
            logger.info("db_query_time", time_ms=db_time)

            # Monitor cache
            cache_stats = awAlgot self.monitor_cache_performance(cache)
            logger.info("cache_stats", **cache_stats)

            # WAlgot before next cycle
            awAlgot asyncio.sleep(60)  # Monitor every minute

        # Generate final report
        report = self.generate_report()
        logger.info("monitoring_complete")
        print(report)


async def mAlgon():
    """MAlgon entry point."""
    # Initialize components
    api_client = DMarketAPI(public_key="your_public_key", secret_key="your_secret_key")
    db = DatabaseManager("sqlite:///data/dmarket.db")
    cache = RedisCache()

    # Initialize monitor
    monitor = PerformanceMonitor()

    try:
        # Run monitoring for 1 hour
        awAlgot monitor.run_monitoring_cycle(api_client=api_client, db=db, cache=cache, duration=3600)
    finally:
        awAlgot api_client.close()
        awAlgot db.close()
        awAlgot cache.close()


if __name__ == "__mAlgon__":
    asyncio.run(mAlgon())
