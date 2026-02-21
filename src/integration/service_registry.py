"""Service Registry for dependency injection.

This module provides a centralized registry for all bot services,
enabling loose coupling and easier testing.

Usage:
    ```python
    from src.integration.service_registry import ServiceRegistry

    registry = ServiceRegistry()
    registry.register("dmarket_api", dmarket_api)
    registry.register("analytics", analytics)

    # Get service
    api = registry.get("dmarket_api")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable


logger = structlog.get_logger(__name__)

T = TypeVar("T")


class ServiceStatus(StrEnum):
    """Service lifecycle status."""

    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceInfo:
    """Information about a registered service."""

    name: str
    instance: Any
    status: ServiceStatus = ServiceStatus.REGISTERED
    depends_on: list[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    error: Exception | None = None


class ServiceRegistry:
    """Centralized service registry with dependency management.

    Features:
    - Service registration and discovery
    - Dependency tracking
    - Lifecycle management
    - Circular dependency detection
    """

    def __init__(self) -> None:
        """Initialize service registry."""
        self._services: dict[str, ServiceInfo] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = asyncio.Lock()
        self._started = False

        logger.info("ServiceRegistry initialized")

    def register(
        self,
        name: str,
        service: Any,
        depends_on: list[str] | None = None,
    ) -> None:
        """Register a service.

        Args:
            name: Service identifier
            service: Service instance
            depends_on: List of service names this service depends on
        """
        if name in self._services:
            logger.warning(
                "service_already_registered",
                name=name,
                replacing=True,
            )

        self._services[name] = ServiceInfo(
            name=name,
            instance=service,
            depends_on=depends_on or [],
        )

        logger.debug("service_registered", name=name)

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Any],
        depends_on: list[str] | None = None,
    ) -> None:
        """Register a service factory for lazy initialization.

        Args:
            name: Service identifier
            factory: Callable that creates the service
            depends_on: List of service names this service depends on
        """
        self._factories[name] = factory

        # Create placeholder service info
        self._services[name] = ServiceInfo(
            name=name,
            instance=None,
            status=ServiceStatus.UNREGISTERED,
            depends_on=depends_on or [],
        )

        logger.debug("service_factory_registered", name=name)

    def get(self, name: str) -> Any:
        """Get a service by name.

        Args:
            name: Service identifier

        Returns:
            Service instance

        Raises:
            KeyError: If service not found
        """
        if name not in self._services:
            raise KeyError(f"Service not found: {name}")

        service_info = self._services[name]

        # Lazy initialization from factory
        if service_info.instance is None and name in self._factories:
            logger.debug("lazy_initializing_service", name=name)
            service_info.instance = self._factories[name]()
            service_info.status = ServiceStatus.REGISTERED

        return service_info.instance

    def get_optional(self, name: str) -> Any | None:
        """Get a service by name, returning None if not found.

        Args:
            name: Service identifier

        Returns:
            Service instance or None
        """
        try:
            return self.get(name)
        except KeyError:
            return None

    def has(self, name: str) -> bool:
        """Check if a service is registered.

        Args:
            name: Service identifier

        Returns:
            True if service is registered
        """
        return name in self._services

    def unregister(self, name: str) -> None:
        """Unregister a service.

        Args:
            name: Service identifier
        """
        if name in self._services:
            del self._services[name]
            logger.debug("service_unregistered", name=name)

        if name in self._factories:
            del self._factories[name]

    def get_all(self) -> dict[str, Any]:
        """Get all registered services.

        Returns:
            Dictionary of service name to instance
        """
        return {
            name: info.instance
            for name, info in self._services.items()
            if info.instance is not None
        }

    def get_status(self, name: str) -> ServiceStatus:
        """Get service status.

        Args:
            name: Service identifier

        Returns:
            Service status
        """
        if name not in self._services:
            return ServiceStatus.UNREGISTERED
        return self._services[name].status

    def _get_start_order(self) -> list[str]:
        """Calculate service start order based on dependencies.

        Returns:
            Ordered list of service names

        Raises:
            ValueError: If circular dependency detected
        """
        visited = set()
        temp_visited = set()
        order = []

        def visit(name: str) -> None:
            if name in temp_visited:
                raise ValueError(f"Circular dependency detected: {name}")

            if name in visited:
                return

            temp_visited.add(name)

            if name in self._services:
                for dep in self._services[name].depends_on:
                    if dep in self._services:
                        visit(dep)

            temp_visited.remove(name)
            visited.add(name)
            order.append(name)

        for name in self._services:
            if name not in visited:
                visit(name)

        return order

    async def start_all(self) -> dict[str, bool]:
        """Start all services in dependency order.

        Returns:
            Dictionary of service name to success status
        """
        async with self._lock:
            results = {}

            try:
                start_order = self._get_start_order()
            except ValueError as e:
                logger.exception("dependency_error", error=str(e))
                return {"__error__": str(e)}

            for name in start_order:
                service_info = self._services.get(name)
                if not service_info or not service_info.instance:
                    results[name] = True
                    continue

                try:
                    service_info.status = ServiceStatus.INITIALIZING

                    # Check if service has start method
                    if hasattr(service_info.instance, "start"):
                        if asyncio.iscoroutinefunction(service_info.instance.start):
                            await service_info.instance.start()
                        else:
                            service_info.instance.start()

                    service_info.status = ServiceStatus.RUNNING
                    service_info.started_at = datetime.now(UTC)
                    results[name] = True

                    logger.info("service_started", name=name)

                except Exception as e:
                    service_info.status = ServiceStatus.ERROR
                    service_info.error = e
                    results[name] = False

                    logger.exception(
                        "service_start_failed",
                        name=name,
                        error=str(e),
                    )

            self._started = True
            return results

    async def stop_all(self) -> dict[str, bool]:
        """Stop all services in reverse dependency order.

        Returns:
            Dictionary of service name to success status
        """
        async with self._lock:
            results = {}

            try:
                stop_order = list(reversed(self._get_start_order()))
            except ValueError:
                stop_order = list(self._services.keys())

            for name in stop_order:
                service_info = self._services.get(name)
                if not service_info or not service_info.instance:
                    results[name] = True
                    continue

                try:
                    service_info.status = ServiceStatus.STOPPING

                    # Check if service has stop method
                    if hasattr(service_info.instance, "stop"):
                        if asyncio.iscoroutinefunction(service_info.instance.stop):
                            await service_info.instance.stop()
                        else:
                            service_info.instance.stop()

                    service_info.status = ServiceStatus.STOPPED
                    service_info.stopped_at = datetime.now(UTC)
                    results[name] = True

                    logger.info("service_stopped", name=name)

                except Exception as e:
                    service_info.error = e
                    results[name] = False

                    logger.exception(
                        "service_stop_failed",
                        name=name,
                        error=str(e),
                    )

            self._started = False
            return results

    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary of all services.

        Returns:
            Dictionary with service health information
        """
        total = len(self._services)
        running = sum(
            1 for s in self._services.values() if s.status == ServiceStatus.RUNNING
        )
        errored = sum(
            1 for s in self._services.values() if s.status == ServiceStatus.ERROR
        )

        return {
            "total_services": total,
            "running": running,
            "errored": errored,
            "stopped": total - running - errored,
            "is_started": self._started,
            "services": {
                name: {
                    "status": info.status.value,
                    "started_at": (
                        info.started_at.isoformat() if info.started_at else None
                    ),
                    "error": str(info.error) if info.error else None,
                }
                for name, info in self._services.items()
            },
        }
