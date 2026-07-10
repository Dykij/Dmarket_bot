"""
health.py — Health check endpoints for monitoring.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    healthy: bool = True
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
        }


async def check_database(session: Any) -> HealthCheckResult:
    """Check database connectivity."""
    try:
        await session.execute("SELECT 1")
        return HealthCheckResult(name="database", healthy=True)
    except Exception as e:
        return HealthCheckResult(name="database", healthy=False, message=str(e))


async def check_redis(redis_client: Any) -> HealthCheckResult:
    """Check Redis connectivity."""
    try:
        await redis_client.ping()
        return HealthCheckResult(name="redis", healthy=True)
    except Exception as e:
        return HealthCheckResult(name="redis", healthy=False, message=str(e))


async def check_dmarket_api(api_client: Any) -> HealthCheckResult:
    """Check DMarket API connectivity."""
    try:
        await api_client.get_balance()
        return HealthCheckResult(name="dmarket_api", healthy=True)
    except Exception as e:
        return HealthCheckResult(name="dmarket_api", healthy=False, message=str(e))


class DatabaseHealthCheck:
    def __init__(self, db_path: str = "bot.db") -> None:
        self.db_path = db_path

    async def check(self) -> HealthCheckResult:
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")
            conn.close()
            return HealthCheckResult(name="database", healthy=True)
        except Exception as e:
            return HealthCheckResult(name="database", healthy=False, message=str(e))


class RedisHealthCheck:
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self.redis_url = redis_url

    async def check(self) -> HealthCheckResult:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(self.redis_url)
            await r.ping()
            await r.close()
            return HealthCheckResult(name="redis", healthy=True)
        except Exception as e:
            return HealthCheckResult(name="redis", healthy=False, message=str(e))


class DMarketAPIHealthCheck:
    def __init__(self, api_client: Any = None) -> None:
        self.api = api_client

    async def check(self) -> HealthCheckResult:
        try:
            if self.api:
                await self.api.get_balance()
            return HealthCheckResult(name="dmarket_api", healthy=True)
        except Exception as e:
            return HealthCheckResult(name="dmarket_api", healthy=False, message=str(e))


class HealthCheckAggregator:
    def __init__(self) -> None:
        self._checks: list[Any] = []

    def add_check(self, check: Any) -> None:
        self._checks.append(check)

    async def run_all(self) -> dict[str, Any]:
        results = []
        all_healthy = True
        for check in self._checks:
            result = await check.check()
            results.append(result)
            if not result.healthy:
                all_healthy = False
        return {
            "healthy": all_healthy,
            "checks": [r.to_dict() for r in results],
        }
