"""Advanced health check HTTP server for bot monitoring.

Provides comprehensive health checks for all dependencies:
- Database (PostgreSQL/SQLite)
- Redis cache
- DMarket API
- Telegram Bot API

Best practice for production deployments - allows external monitoring
and load balancers to check if bot is alive and all services are operational.

Roadmap Task #5: Health Check Endpoint
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from aiohttp import web

from src.utils.health_monitor import HealthMonitor, ServiceStatus

logger = logging.getLogger(__name__)


class HealthCheckServer:
    """Async HTTP server for comprehensive health checks.

    Provides endpoints:
    - GET /health - Overall health status with all checks
    - GET /ready - Kubernetes readiness probe
    - GET /live - Kubernetes liveness probe
    - GET /metrics - Detailed metrics
    """

    def __init__(
        self,
        host: str = "0.0.0.0",  # noqa: S104 - Required for Docker container networking
        port: int = 8080,
        bot_app: Any = None,
        db_manager: Any = None,
        redis_client: Any = None,
        dmarket_api: Any = None,
        health_monitor: HealthMonitor | None = None,
    ):
        """Initialize health check server.

        Args:
            host: Host to bind to
            port: Port to bind to
            bot_app: Telegram bot application instance
            db_manager: Database manager instance
            redis_client: Redis client instance
            dmarket_api: DMarket API client instance
        """
        self.host = host
        self.port = port
        self.bot_app = bot_app
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.dmarket_api = dmarket_api
        self.health_monitor = health_monitor

        # Status tracking
        self.start_time = time.time()
        self.version = "1.0.0"
        self.status = "starting"

        # Metrics
        self.total_updates = 0
        self.total_errors = 0
        self.last_update_time: float | None = None

        # aiohttp app
        self.app: web.Application | None = None
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start health check server."""
        try:
            # Create aiohttp application
            self.app = web.Application()

            # Register routes
            self.app.router.add_get("/health", self.handle_health)
            self.app.router.add_get("/ready", self.handle_ready)
            self.app.router.add_get("/live", self.handle_live)
            self.app.router.add_get("/metrics", self.handle_metrics)

            # Start server
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            self.status = "running"

            logger.info(
                f"✅ Health check server started on http://{self.host}:{self.port}"
            )
            logger.info(f"  - Health:  http://{self.host}:{self.port}/health")
            logger.info(f"  - Ready:   http://{self.host}:{self.port}/ready")
            logger.info(f"  - Live:    http://{self.host}:{self.port}/live")
            logger.info(f"  - Metrics: http://{self.host}:{self.port}/metrics")

        except Exception as e:
            logger.error(f"❌ Failed to start health check server: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop health check server."""
        if self.runner:
            logger.info("Stopping health check server...")
            self.status = "stopping"
            await self.runner.cleanup()
            logger.info("✅ Health check server stopped")

    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint - comprehensive health check.

        Checks:
        - Database connectivity
        - Redis connectivity
        - DMarket API avAlgolability
        - Telegram Bot API avAlgolability

        Returns:
            JSON response with status and check results
        """
        checks: dict[str, bool] = {}
        details: dict[str, dict[str, Any]] = {}
        overall_status: str | None = None

        if self.health_monitor:
            checks, details, overall_status = await self._get_health_monitor_results()

        missing_checks = {
            "database",
            "redis",
            "dmarket_api",
            "telegram_api",
        } - set(checks.keys())
        if missing_checks:
            legacy_checks = await self._run_legacy_checks(missing_checks)
            checks.update(legacy_checks)
            if overall_status is None:
                overall_status = (
                    "healthy" if all(legacy_checks.values()) else "unhealthy"
                )
            elif any(not value for value in legacy_checks.values()):
                overall_status = "unhealthy"

        if overall_status is None:
            overall_status = "healthy" if all(checks.values()) else "unhealthy"

        response_data = {
            "status": overall_status,
            "checks": checks,
            "uptime_seconds": int(time.time() - self.start_time),
            "version": self.version,
            "timestamp": datetime.now(UTC).isoformat() + "Z",
        }
        if details and any(details.values()):
            response_data["details"] = details

        status_code = 200 if overall_status != "unhealthy" else 503

        return web.json_response(response_data, status=status_code)

    async def _get_health_monitor_results(
        self,
    ) -> tuple[dict[str, bool], dict[str, dict[str, Any]], str]:
        """Build health response from HealthMonitor results.

        Returns:
            Tuple of (checks, details, overall_status).
        """
        results = await self.health_monitor.run_all_checks()
        overall_status = "healthy"
        checks: dict[str, bool] = {}
        details: dict[str, dict[str, Any]] = {}

        for name, result in results.items():
            checks[name] = result.status in {
                ServiceStatus.HEALTHY,
                ServiceStatus.DEGRADED,
            }
            details[name] = {
                "status": result.status.value,
                "message": result.message,
                "response_time_ms": result.response_time_ms,
            }

            if result.status == ServiceStatus.UNHEALTHY:
                overall_status = "unhealthy"
            elif (
                result.status == ServiceStatus.DEGRADED and overall_status == "healthy"
            ):
                overall_status = "degraded"

        return checks, details, overall_status

    async def _run_legacy_checks(self, check_names: set[str]) -> dict[str, bool]:
        """Run legacy dependency checks for missing services."""
        results: dict[str, bool] = {}
        if "database" in check_names:
            results["database"] = await self._check_database()
        if "redis" in check_names:
            results["redis"] = await self._check_redis()
        if "dmarket_api" in check_names:
            results["dmarket_api"] = await self._check_dmarket_api()
        if "telegram_api" in check_names:
            results["telegram_api"] = await self._check_telegram_api()
        return results

    async def handle_ready(self, request: web.Request) -> web.Response:
        """Handle /ready endpoint - Kubernetes readiness probe.

        Returns ready only if bot is running and critical services are up.
        """
        # Check critical services for readiness
        db_ok = await self._check_database()
        telegram_ok = await self._check_telegram_api()

        is_ready = self.status == "running" and db_ok and telegram_ok

        response_data = {
            "ready": is_ready,
            "status": self.status,
        }

        status_code = 200 if is_ready else 503

        return web.json_response(response_data, status=status_code)

    async def handle_live(self, request: web.Request) -> web.Response:
        """Handle /live endpoint - Kubernetes liveness probe.

        Returns alive if process is running (does not check dependencies).
        """
        response_data = {
            "alive": True,
            "status": self.status,
            "uptime_seconds": int(time.time() - self.start_time),
        }

        return web.json_response(response_data, status=200)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint - detailed metrics."""
        uptime_seconds = int(time.time() - self.start_time)

        response_data = {
            "status": self.status,
            "version": self.version,
            "uptime_seconds": uptime_seconds,
            "total_updates": self.total_updates,
            "total_errors": self.total_errors,
            "error_rate": (
                self.total_errors / self.total_updates
                if self.total_updates > 0
                else 0.0
            ),
            "last_update_time": (
                datetime.fromtimestamp(self.last_update_time).isoformat()
                if self.last_update_time
                else None
            ),
            "timestamp": datetime.now(UTC).isoformat() + "Z",
        }

        return web.json_response(response_data, status=200)

    async def _check_database(self) -> bool:
        """Check database connectivity.

        Returns:
            True if database is accessible
        """
        if not self.db_manager:
            logger.debug("Database manager not configured, skipping check")
            return True  # Not required if not configured

        try:
            # Try simple SELECT 1 query
            # Implementation depends on your DB manager
            if hasattr(self.db_manager, "execute_query"):
                await self.db_manager.execute_query("SELECT 1")
            elif hasattr(self.db_manager, "session"):
                # SQLAlchemy style
                async with self.db_manager.session() as session:
                    await session.execute("SELECT 1")
            else:
                logger.warning("Unknown database manager type, cannot check")
                return True

            return True
        except Exception as e:
            logger.exception(f"Database health check failed: {e}")
            return False

    async def _check_redis(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is accessible
        """
        if not self.redis_client:
            logger.debug("Redis client not configured, skipping check")
            return True  # Not required if not configured

        try:
            # Try PING command
            if hasattr(self.redis_client, "ping"):
                await self.redis_client.ping()
            else:
                logger.warning("Unknown Redis client type, cannot check")
                return True

            return True
        except Exception as e:
            logger.exception(f"Redis health check failed: {e}")
            return False

    async def _check_dmarket_api(self) -> bool:
        """Check DMarket API avAlgolability.

        Returns:
            True if DMarket API is accessible
        """
        if not self.dmarket_api:
            logger.debug("DMarket API not configured, skipping check")
            return True  # Not required if not configured

        try:
            # Try to get balance (simple read-only operation)
            if hasattr(self.dmarket_api, "get_balance"):
                result = await self.dmarket_api.get_balance()
                return not result.get("error", False)
            logger.warning("Unknown DMarket API type, cannot check")
            return True

        except Exception as e:
            logger.exception(f"DMarket API health check failed: {e}")
            return False

    async def _check_telegram_api(self) -> bool:
        """Check Telegram Bot API avAlgolability.

        Returns:
            True if Telegram API is accessible
        """
        if not self.bot_app:
            logger.debug("Bot app not configured, skipping check")
            return True  # Not required if not configured

        try:
            # Try getMe() call
            if hasattr(self.bot_app, "bot"):
                bot = self.bot_app.bot
                if hasattr(bot, "get_me"):
                    await bot.get_me()
                    return True

            logger.warning("Unknown bot app type, cannot check")
            return True

        except Exception as e:
            logger.exception(f"Telegram API health check failed: {e}")
            return False

    def update_metrics(
        self,
        updates_count: int = 0,
        errors_count: int = 0,
    ) -> None:
        """Update metrics.

        Args:
            updates_count: Number of updates to add
            errors_count: Number of errors to add
        """
        if updates_count > 0:
            self.total_updates += updates_count
            self.last_update_time = time.time()

        if errors_count > 0:
            self.total_errors += errors_count

    def set_status(self, status: str) -> None:
        """Set bot status.

        Args:
            status: Status ("starting", "running", "stopping", "error")
        """
        self.status = status
        logger.info(f"Health check status: {status}")


# Global health check server instance
health_check_server: HealthCheckServer | None = None


def get_health_check_server() -> HealthCheckServer | None:
    """Get global health check server instance."""
    return health_check_server


def init_health_check_server(
    host: str = "0.0.0.0",  # noqa: S104 - Required for Docker container networking
    port: int = 8080,
    **kwargs: Any,
) -> HealthCheckServer:
    """Initialize global health check server.

    Args:
        host: Host to bind to
        port: Port to bind to
        **kwargs: Additional arguments for HealthCheckServer

    Returns:
        HealthCheckServer instance
    """
    global health_check_server
    health_check_server = HealthCheckServer(host=host, port=port, **kwargs)
    return health_check_server
