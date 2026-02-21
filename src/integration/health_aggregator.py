"""Health Aggregator for unified health monitoring.

This module provides aggregated health monitoring for all bot components,
enabling a single source of truth for system health.

Usage:
    ```python
    from src.integration.health_aggregator import HealthAggregator

    aggregator = HealthAggregator()
    aggregator.register_component("dmarket_api", api_instance)
    aggregator.register_component("scanner", scanner_instance)

    # Get overall health
    health = await aggregator.check_health()
    print(f"Status: {health.status}")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable


logger = structlog.get_logger(__name__)


class HealthStatus(StrEnum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(UTC))
    response_time_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0

    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}


@dataclass
class SystemHealth:
    """Aggregated system health."""

    status: HealthStatus
    components: dict[str, ComponentHealth]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    uptime_seconds: float = 0.0
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "components": {
                name: {
                    "status": comp.status.value,
                    "message": comp.message,
                    "last_check": comp.last_check.isoformat(),
                    "response_time_ms": comp.response_time_ms,
                    "consecutive_failures": comp.consecutive_failures,
                    "details": comp.details,
                }
                for name, comp in self.components.items()
            },
            "summary": {
                "total": len(self.components),
                "healthy": sum(
                    1
                    for c in self.components.values()
                    if c.status == HealthStatus.HEALTHY
                ),
                "degraded": sum(
                    1
                    for c in self.components.values()
                    if c.status == HealthStatus.DEGRADED
                ),
                "unhealthy": sum(
                    1
                    for c in self.components.values()
                    if c.status in {HealthStatus.UNHEALTHY, HealthStatus.CRITICAL}
                ),
            },
        }


class HealthAggregator:
    """Aggregated health monitoring for all bot components.

    Features:
    - Component registration
    - Periodic health checks
    - Status aggregation
    - Alert thresholds
    - Health history
    """

    def __init__(
        self,
        check_interval_seconds: float = 60.0,
        failure_threshold: int = 3,
        degraded_threshold_ms: float = 1000.0,
    ) -> None:
        """Initialize health aggregator.

        Args:
            check_interval_seconds: Interval between health checks
            failure_threshold: Failures before marking unhealthy
            degraded_threshold_ms: Response time threshold for degraded
        """
        self._components: dict[str, Any] = {}
        self._health_cache: dict[str, ComponentHealth] = {}
        self._check_interval = check_interval_seconds
        self._failure_threshold = failure_threshold
        self._degraded_threshold_ms = degraded_threshold_ms

        self._start_time = datetime.now(UTC)
        self._running = False
        self._check_task: asyncio.Task | None = None

        # Custom health check functions
        self._custom_checks: dict[str, Callable[[], bool | dict]] = {}

        logger.info(
            "HealthAggregator initialized",
            check_interval=check_interval_seconds,
            failure_threshold=failure_threshold,
        )

    def register_component(
        self,
        name: str,
        component: Any,
        custom_check: Callable[[], bool | dict] | None = None,
    ) -> None:
        """Register a component for health monitoring.

        Args:
            name: Component name
            component: Component instance
            custom_check: Optional custom health check function
        """
        self._components[name] = component
        self._health_cache[name] = ComponentHealth(name=name)

        if custom_check:
            self._custom_checks[name] = custom_check

        logger.debug("component_registered", name=name)

    def unregister_component(self, name: str) -> None:
        """Unregister a component.

        Args:
            name: Component name
        """
        self._components.pop(name, None)
        self._health_cache.pop(name, None)
        self._custom_checks.pop(name, None)

        logger.debug("component_unregistered", name=name)

    async def check_component_health(self, name: str) -> ComponentHealth:
        """Check health of a single component.

        Args:
            name: Component name

        Returns:
            ComponentHealth object
        """
        if name not in self._components:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Component not registered",
            )

        component = self._components[name]
        start_time = datetime.now(UTC)

        try:
            # Use custom check if available
            if name in self._custom_checks:
                result = self._custom_checks[name]()
                if asyncio.iscoroutine(result):
                    result = await result

                if isinstance(result, bool):
                    status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    details = {}
                else:
                    status = HealthStatus(result.get("status", "healthy"))
                    details = result.get("details", {})

            # Check for standard health check method
            elif hasattr(component, "health_check"):
                if asyncio.iscoroutinefunction(component.health_check):
                    result = await component.health_check()
                else:
                    result = component.health_check()

                if isinstance(result, bool):
                    status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    details = {}
                else:
                    status = HealthStatus(result.get("status", "healthy"))
                    details = result.get("details", {})

            # Check for is_running attribute
            elif hasattr(component, "is_running"):
                is_running = component.is_running
                if callable(is_running):
                    is_running = is_running()
                status = HealthStatus.HEALTHY if is_running else HealthStatus.UNHEALTHY
                details = {"is_running": is_running}

            # Check for connected attribute (APIs)
            elif hasattr(component, "connected"):
                is_connected = component.connected
                if callable(is_connected):
                    is_connected = is_connected()
                status = (
                    HealthStatus.HEALTHY if is_connected else HealthStatus.UNHEALTHY
                )
                details = {"connected": is_connected}

            # Default: assume healthy if no check available
            else:
                status = HealthStatus.HEALTHY
                details = {"note": "No health check available"}

            response_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            # Check for degraded (slow response)
            if (
                status == HealthStatus.HEALTHY
                and response_time > self._degraded_threshold_ms
            ):
                status = HealthStatus.DEGRADED

            health = ComponentHealth(
                name=name,
                status=status,
                message=(
                    "OK"
                    if status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}
                    else "Check failed"
                ),
                last_check=datetime.now(UTC),
                response_time_ms=response_time,
                details=details,
                consecutive_failures=0,
            )

        except Exception as e:
            # Handle check failures
            prev_health = self._health_cache.get(name)
            failures = (prev_health.consecutive_failures if prev_health else 0) + 1

            status = (
                HealthStatus.CRITICAL
                if failures >= self._failure_threshold
                else HealthStatus.UNHEALTHY
            )

            health = ComponentHealth(
                name=name,
                status=status,
                message=str(e),
                last_check=datetime.now(UTC),
                response_time_ms=0.0,
                details={"error": str(e)},
                consecutive_failures=failures,
            )

            logger.warning(
                "component_health_check_failed",
                name=name,
                error=str(e),
                failures=failures,
            )

        self._health_cache[name] = health
        return health

    async def check_health(self) -> SystemHealth:
        """Check health of all registered components.

        Returns:
            SystemHealth object
        """
        component_health = {}

        for name in self._components:
            health = await self.check_component_health(name)
            component_health[name] = health

        # Calculate overall status
        if not component_health:
            overall_status = HealthStatus.UNKNOWN
        else:
            statuses = [h.status for h in component_health.values()]

            if HealthStatus.CRITICAL in statuses:
                overall_status = HealthStatus.CRITICAL
            elif all(s == HealthStatus.HEALTHY for s in statuses):
                overall_status = HealthStatus.HEALTHY
            elif any(s == HealthStatus.UNHEALTHY for s in statuses):
                overall_status = HealthStatus.UNHEALTHY
            elif any(s == HealthStatus.DEGRADED for s in statuses):
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.UNKNOWN

        uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        return SystemHealth(
            status=overall_status,
            components=component_health,
            uptime_seconds=uptime,
        )

    async def start(self) -> None:
        """Start periodic health checks."""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())

        logger.info("HealthAggregator started")

    async def stop(self) -> None:
        """Stop periodic health checks."""
        self._running = False

        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None

        logger.info("HealthAggregator stopped")

    async def _check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await self.check_health()
            except Exception as e:
                logger.exception("health_check_loop_error", error=str(e))

            await asyncio.sleep(self._check_interval)

    def get_component_health(self, name: str) -> ComponentHealth | None:
        """Get cached health for a component.

        Args:
            name: Component name

        Returns:
            ComponentHealth or None
        """
        return self._health_cache.get(name)

    def get_unhealthy_components(self) -> list[str]:
        """Get list of unhealthy components.

        Returns:
            List of component names
        """
        return [
            name
            for name, health in self._health_cache.items()
            if health.status in {HealthStatus.UNHEALTHY, HealthStatus.CRITICAL}
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get aggregator statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "running": self._running,
            "components_count": len(self._components),
            "check_interval": self._check_interval,
            "failure_threshold": self._failure_threshold,
            "uptime_seconds": (datetime.now(UTC) - self._start_time).total_seconds(),
            "components": list(self._components.keys()),
        }
