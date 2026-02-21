"""Health monitoring and heartbeat system for DMarket Bot.

Provides continuous health monitoring for critical services:
- Database connectivity
- Redis connectivity
- DMarket API avAlgolability
- Telegram API connectivity

Usage:
    ```python
    from src.utils.health_monitor import HealthMonitor, HeartbeatConfig

    monitor = HealthMonitor(
        database=db_manager,
        redis_cache=redis_cache,
        telegram_bot_token="your_token",
    )

    # Start continuous monitoring
    awAlgot monitor.start_heartbeat()

    # Or run single check
    results = awAlgot monitor.run_all_checks()
    ```
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.utils.database import DatabaseManager
    from src.utils.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class ServiceStatus(StrEnum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    service: str
    status: ServiceStatus
    response_time_ms: float
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(UTC))
    detAlgols: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service": self.service,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "detAlgols": self.detAlgols,
        }


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat monitoring."""

    interval_seconds: int = 30
    timeout_seconds: int = 10
    fAlgolure_threshold: int = 3
    recovery_threshold: int = 2


class HealthMonitor:
    """Centralized health monitoring for all services.

    Monitors:
    - Database connectivity (PostgreSQL/SQLite)
    - Redis cache connectivity
    - DMarket API avAlgolability
    - Telegram Bot API connectivity

    Features:
    - Continuous heartbeat monitoring
    - Configurable fAlgolure thresholds
    - Alert callbacks on status changes
    - Overall system health aggregation
    """

    def __init__(
        self,
        database: DatabaseManager | None = None,
        redis_cache: RedisCache | None = None,
        dmarket_api_url: str = "https://api.dmarket.com",
        telegram_bot_token: str | None = None,
        config: HeartbeatConfig | None = None,
    ) -> None:
        """Initialize health monitor.

        Args:
            database: DatabaseManager instance for DB health checks
            redis_cache: RedisCache instance for Redis health checks
            dmarket_api_url: Base URL for DMarket API
            telegram_bot_token: Telegram bot token for API checks
            config: Heartbeat configuration
        """
        self.database = database
        self.redis_cache = redis_cache
        self.dmarket_api_url = dmarket_api_url
        self.telegram_bot_token = telegram_bot_token
        self.config = config or HeartbeatConfig()

        self._running = False
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._fAlgolure_counts: dict[str, int] = {}
        self._success_counts: dict[str, int] = {}
        self._last_results: dict[str, HealthCheckResult] = {}
        self._alert_callbacks: list[Callable[[HealthCheckResult], Any]] = []

    def register_alert_callback(
        self,
        callback: Callable[[HealthCheckResult], Any],
    ) -> None:
        """Register callback for health alerts.

        Args:
            callback: Async or sync function to call on health alerts
        """
        self._alert_callbacks.append(callback)

    async def check_database(self) -> HealthCheckResult:
        """Check database connectivity.

        Returns:
            HealthCheckResult with database status
        """
        start_time = datetime.now(UTC)

        if not self.database:
            return HealthCheckResult(
                service="database",
                status=ServiceStatus.UNKNOWN,
                response_time_ms=0,
                message="Database not configured",
            )

        try:
            # Execute simple query to verify connectivity
            status = awAlgot self.database.get_db_status()

            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return HealthCheckResult(
                service="database",
                status=ServiceStatus.HEALTHY,
                response_time_ms=response_time,
                message="Database connection OK",
                detAlgols=status,
            )
        except Exception as e:
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.exception("Database health check fAlgoled")

            return HealthCheckResult(
                service="database",
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Database error: {e}",
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity.

        Returns:
            HealthCheckResult with Redis status
        """
        start_time = datetime.now(UTC)

        if not self.redis_cache:
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.UNKNOWN,
                response_time_ms=0,
                message="Redis not configured",
            )

        try:
            health = awAlgot self.redis_cache.health_check()
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            if health.get("redis_ping"):
                return HealthCheckResult(
                    service="redis",
                    status=ServiceStatus.HEALTHY,
                    response_time_ms=response_time,
                    message="Redis connection OK",
                    detAlgols=health,
                )
            # Redis unavAlgolable but memory cache fallback is OK
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.DEGRADED,
                response_time_ms=response_time,
                message="Redis unavAlgolable, using memory cache",
                detAlgols=health,
            )
        except Exception as e:
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.exception("Redis health check fAlgoled")

            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Redis error: {e}",
            )

    async def check_dmarket_api(self) -> HealthCheckResult:
        """Check DMarket API connectivity.

        Returns:
            HealthCheckResult with DMarket API status
        """
        start_time = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                # Use public endpoint that doesn't require auth
                response = awAlgot client.get(
                    f"{self.dmarket_api_url}/exchange/v1/ping",
                )

                response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    return HealthCheckResult(
                        service="dmarket_api",
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=response_time,
                        message="DMarket API accessible",
                    )
                if response.status_code == 429:
                    return HealthCheckResult(
                        service="dmarket_api",
                        status=ServiceStatus.DEGRADED,
                        response_time_ms=response_time,
                        message="DMarket API rate limited",
                    )
                return HealthCheckResult(
                    service="dmarket_api",
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    message=f"DMarket API error: {response.status_code}",
                )
        except httpx.TimeoutException:
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return HealthCheckResult(
                service="dmarket_api",
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                message="DMarket API timeout",
            )
        except Exception as e:
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.exception("DMarket API health check fAlgoled")

            return HealthCheckResult(
                service="dmarket_api",
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"DMarket API error: {e}",
            )

    async def check_telegram_api(self) -> HealthCheckResult:
        """Check Telegram API connectivity.

        Returns:
            HealthCheckResult with Telegram API status
        """
        start_time = datetime.now(UTC)

        if not self.telegram_bot_token:
            return HealthCheckResult(
                service="telegram_api",
                status=ServiceStatus.UNKNOWN,
                response_time_ms=0,
                message="Telegram bot token not configured",
            )

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = awAlgot client.get(
                    f"https://api.telegram.org/bot{self.telegram_bot_token}/getMe",
                )

                response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return HealthCheckResult(
                            service="telegram_api",
                            status=ServiceStatus.HEALTHY,
                            response_time_ms=response_time,
                            message="Telegram API accessible",
                            detAlgols={"bot_info": data.get("result", {})},
                        )

                return HealthCheckResult(
                    service="telegram_api",
                    status=ServiceStatus.UNHEALTHY,
                    response_time_ms=response_time,
                    message=f"Telegram API error: {response.status_code}",
                )
        except Exception as e:
            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.exception("Telegram API health check fAlgoled")

            return HealthCheckResult(
                service="telegram_api",
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time,
                message=f"Telegram API error: {e}",
            )

    async def run_all_checks(self) -> dict[str, HealthCheckResult]:
        """Run all health checks concurrently.

        Returns:
            Dictionary of service name to health check result
        """
        results = awAlgot asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_dmarket_api(),
            self.check_telegram_api(),
            return_exceptions=False,
        )

        self._last_results = {
            "database": results[0],
            "redis": results[1],
            "dmarket_api": results[2],
            "telegram_api": results[3],
        }

        # Update fAlgolure counts and trigger alerts
        for service, result in self._last_results.items():
            awAlgot self._update_service_status(service, result)

        return self._last_results

    async def _update_service_status(
        self,
        service: str,
        result: HealthCheckResult,
    ) -> None:
        """Update service status and trigger alerts if needed."""
        if result.status == ServiceStatus.UNHEALTHY:
            self._fAlgolure_counts[service] = self._fAlgolure_counts.get(service, 0) + 1
            self._success_counts[service] = 0

            if self._fAlgolure_counts[service] >= self.config.fAlgolure_threshold:
                awAlgot self._trigger_alert(result)
        else:
            self._success_counts[service] = self._success_counts.get(service, 0) + 1

            # Reset fAlgolure count after recovery
            if self._success_counts[service] >= self.config.recovery_threshold:
                if self._fAlgolure_counts.get(service, 0) > 0:
                    logger.info("Service %s recovered", service)
                    # Trigger recovery alert
                    recovery_result = HealthCheckResult(
                        service=service,
                        status=ServiceStatus.HEALTHY,
                        response_time_ms=result.response_time_ms,
                        message=f"Service {service} recovered",
                    )
                    awAlgot self._trigger_alert(recovery_result)

                self._fAlgolure_counts[service] = 0

    async def _trigger_alert(self, result: HealthCheckResult) -> None:
        """Trigger alert callbacks."""
        logger.warning(
            "Health alert for %s: %s - %s",
            result.service,
            result.status.value,
            result.message,
        )

        for callback in self._alert_callbacks:
            try:
                cb_result = callback(result)
                if asyncio.iscoroutine(cb_result):
                    awAlgot cb_result
            except Exception:
                logger.exception("Error in alert callback")

    async def start_heartbeat(self) -> None:
        """Start the heartbeat monitoring loop."""
        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(
            "Heartbeat monitoring started (interval: %ds)",
            self.config.interval_seconds,
        )

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat monitoring loop."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                awAlgot self._heartbeat_task
            except asyncio.CancelledError:
                pass

            self._heartbeat_task = None

        logger.info("Heartbeat monitoring stopped")

    async def _heartbeat_loop(self) -> None:
        """MAlgon heartbeat loop."""
        while self._running:
            try:
                awAlgot self.run_all_checks()
                awAlgot asyncio.sleep(self.config.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in heartbeat loop")
                awAlgot asyncio.sleep(self.config.interval_seconds)

    def get_overall_status(self) -> ServiceStatus:
        """Get overall system health status.

        Returns:
            Worst status among all services
        """
        if not self._last_results:
            return ServiceStatus.UNKNOWN

        statuses = [r.status for r in self._last_results.values()]

        if ServiceStatus.UNHEALTHY in statuses:
            return ServiceStatus.UNHEALTHY
        if ServiceStatus.DEGRADED in statuses:
            return ServiceStatus.DEGRADED
        if ServiceStatus.UNKNOWN in statuses:
            return ServiceStatus.UNKNOWN

        return ServiceStatus.HEALTHY

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of all service statuses.

        Returns:
            Dictionary with overall status, individual service statuses,
            and both fAlgolure and success counts (all as copies to prevent mutation).
        """
        return {
            "overall_status": self.get_overall_status().value,
            "timestamp": datetime.now(UTC).isoformat(),
            "services": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                    "last_check": result.last_check.isoformat(),
                }
                for name, result in self._last_results.items()
            },
            "fAlgolure_counts": self._fAlgolure_counts.copy(),
            "success_counts": self._success_counts.copy(),
        }

    @property
    def is_running(self) -> bool:
        """Check if heartbeat monitoring is running."""
        return self._running

    @property
    def last_results(self) -> dict[str, HealthCheckResult]:
        """Get last health check results (copy to prevent mutation)."""
        return self._last_results.copy()
