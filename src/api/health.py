"""Health check endpoints for production monitoring."""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class HealthCheckResult:
    """Health check result container."""

    def __init__(self, name: str, healthy: bool, message: str = ""):
        self.name = name
        self.healthy = healthy
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
        }


async def check_database(session: AsyncSession) -> HealthCheckResult:
    """Check database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return HealthCheckResult(name="database", healthy=True)
    except Exception as e:
        logger.exception("database_health_check_failed", error=str(e))
        return HealthCheckResult(name="database", healthy=False, message=str(e))


async def check_redis(redis_client: Any) -> HealthCheckResult:
    """Check Redis connectivity."""
    try:
        await redis_client.ping()
        return HealthCheckResult(name="redis", healthy=True)
    except Exception as e:
        logger.exception("redis_health_check_failed", error=str(e))
        return HealthCheckResult(name="redis", healthy=False, message=str(e))


async def check_dmarket_api(api_client: Any) -> HealthCheckResult:
    """Check DMarket API availability."""
    try:
        await api_client.get_balance()
        return HealthCheckResult(name="dmarket_api", healthy=True)
    except Exception as e:
        logger.exception("dmarket_api_health_check_failed", error=str(e))
        return HealthCheckResult(name="dmarket_api", healthy=False, message=str(e))


def liveness_check() -> dict[str, Any]:
    """Basic liveness check."""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def readiness_check(
    session: AsyncSession,
    redis_client: Any,
    api_client: Any,
) -> dict[str, Any]:
    """Comprehensive readiness check."""
    checks = [
        await check_database(session),
        await check_redis(redis_client),
        await check_dmarket_api(api_client),
    ]

    all_healthy = all(check.healthy for check in checks)

    return {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": [check.to_dict() for check in checks],
    }
