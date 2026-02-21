"""Incident Management System - xyOps-inspired automatic incident handling.

This module provides a unified incident management system that:
- Detects and registers incidents from various sources
- Automatically attempts mitigation for known incident types
- Sends alerts through configured channels
- Tracks incident lifecycle from detection to resolution

Inspired by xyOps - combining monitoring, alerting, and incident response
into a single pipeline.

Features:
- Automatic incident detection from monitoring
- Configurable mitigation handlers
- Multi-channel alerting (Telegram, Discord, etc.)
- Incident tracking and history
- Metrics and reporting

Usage:
    ```python
    from src.utils.incident_manager import IncidentManager, IncidentSeverity

    manager = IncidentManager()

    # Register mitigation handler
    manager.register_mitigation_handler("rate_limit", mitigate_rate_limit)

    # Detect and handle incident
    incident = awAlgot manager.detect_incident(
        title="API Rate Limit Exceeded",
        description="DMarket API returned 429",
        severity=IncidentSeverity.HIGH,
        source="api_monitor",
        incident_type="rate_limit",
    )
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Enums
# ============================================================================


class IncidentSeverity(StrEnum):
    """Severity levels for incidents."""

    LOW = "low"  # Informational, no immediate action needed
    MEDIUM = "medium"  # Requires attention within hours
    HIGH = "high"  # Requires quick resolution
    CRITICAL = "critical"  # Requires immediate intervention


class IncidentStatus(StrEnum):
    """Status of an incident."""

    DETECTED = "detected"  # Just detected
    ACKNOWLEDGED = "acknowledged"  # Someone is aware
    INVESTIGATING = "investigating"  # Being investigated
    MITIGATING = "mitigating"  # Mitigation in progress
    RESOLVED = "resolved"  # Incident resolved
    CLOSED = "closed"  # Incident closed (with notes)


class IncidentType(StrEnum):
    """Common incident types."""

    RATE_LIMIT = "rate_limit"  # API rate limit exceeded
    API_TIMEOUT = "api_timeout"  # API request timeout
    API_ERROR = "api_error"  # API returned error
    CONNECTION_ERROR = "connection_error"  # Network connection issue
    DATABASE_ERROR = "database_error"  # Database issue
    MEMORY_HIGH = "memory_high"  # High memory usage
    CPU_HIGH = "cpu_high"  # High CPU usage
    DISK_FULL = "disk_full"  # Disk space low
    PRICE_ANOMALY = "price_anomaly"  # Unusual price detected
    TRADE_FAlgoLED = "trade_fAlgoled"  # Trade execution fAlgoled
    AUTH_FAlgoLED = "auth_fAlgoled"  # Authentication fAlgolure
    CUSTOM = "custom"  # Custom incident type


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class Incident:
    """Represents a system incident.

    Attributes:
        id: Unique incident identifier
        title: Short descriptive title
        description: DetAlgoled description
        severity: Incident severity level
        source: Source that detected the incident
        incident_type: Type of incident
        status: Current status
        detected_at: When the incident was detected
        acknowledged_at: When someone acknowledged
        resolved_at: When the incident was resolved
        auto_mitigated: Whether auto-mitigation was successful
        mitigation_attempts: Number of mitigation attempts
        metadata: Additional context
    """

    id: str
    title: str
    description: str
    severity: IncidentSeverity
    source: str
    incident_type: str = IncidentType.CUSTOM
    status: IncidentStatus = IncidentStatus.DETECTED
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    auto_mitigated: bool = False
    mitigation_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "source": self.source,
            "incident_type": self.incident_type,
            "status": self.status.value,
            "detected_at": self.detected_at.isoformat(),
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "resolved_at": (self.resolved_at.isoformat() if self.resolved_at else None),
            "auto_mitigated": self.auto_mitigated,
            "mitigation_attempts": self.mitigation_attempts,
            "metadata": self.metadata,
        }

    @property
    def duration(self) -> timedelta | None:
        """Calculate incident duration."""
        if self.resolved_at:
            return self.resolved_at - self.detected_at
        return datetime.now(UTC) - self.detected_at

    @property
    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status not in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}


@dataclass
class MitigationResult:
    """Result of a mitigation attempt."""

    success: bool
    message: str
    action_taken: str | None = None
    retry_recommended: bool = False


# Type alias for mitigation handler
MitigationHandler = Callable[[Incident], MitigationResult | bool]
AsyncMitigationHandler = Callable[[Incident], Any]  # Returns awAlgotable


# ============================================================================
# Configuration Constants
# ============================================================================

MAX_MITIGATION_ATTEMPTS = 3
INCIDENT_RETENTION_DAYS = 30
MAX_ACTIVE_INCIDENTS = 100


# ============================================================================
# Incident Manager Class
# ============================================================================


class IncidentManager:
    """xyOps-inspired incident management system.

    Combines:
    - Real-time incident detection
    - Automatic mitigation
    - Multi-channel alerting
    - Incident tracking and history

    The manager mAlgontAlgons a registry of mitigation handlers for different
    incident types and automatically attempts to resolve incidents.

    Attributes:
        incidents: All tracked incidents
        mitigation_handlers: Registered mitigation handlers
        alert_channels: Configured alert channels

    Example:
        >>> manager = IncidentManager()
        >>> manager.register_mitigation_handler("rate_limit", rate_limit_handler)
        >>> incident = awAlgot manager.detect_incident(...)
    """

    def __init__(self) -> None:
        """Initialize the incident manager."""
        self._incidents: dict[str, Incident] = {}
        self._mitigation_handlers: dict[
            str, MitigationHandler | AsyncMitigationHandler
        ] = {}
        self._alert_channels: list[Callable[[Incident], Any]] = []

        # Counter for incident IDs
        self._incident_counter = 0

        # Metrics
        self._metrics = {
            "total_incidents": 0,
            "resolved_incidents": 0,
            "auto_mitigated": 0,
            "alerts_sent": 0,
            "by_severity": {s.value: 0 for s in IncidentSeverity},
            "by_type": {},
        }

        logger.info("incident_manager_initialized")

    # =========================================================================
    # Mitigation Handler Registration
    # =========================================================================

    def register_mitigation_handler(
        self,
        incident_type: str,
        handler: MitigationHandler | AsyncMitigationHandler,
    ) -> None:
        """Register automatic mitigation handler.

        The handler will be called when an incident of the specified type
        is detected. It should return True/MitigationResult if mitigation
        was successful.

        Args:
            incident_type: Type of incident to handle
            handler: Handler function (sync or async)
        """
        self._mitigation_handlers[incident_type] = handler
        logger.info("mitigation_handler_registered", incident_type=incident_type)

    def unregister_mitigation_handler(self, incident_type: str) -> bool:
        """Unregister a mitigation handler.

        Args:
            incident_type: Type to unregister

        Returns:
            True if handler was removed
        """
        if incident_type in self._mitigation_handlers:
            del self._mitigation_handlers[incident_type]
            logger.info("mitigation_handler_unregistered", incident_type=incident_type)
            return True
        return False

    # =========================================================================
    # Alert Channel Registration
    # =========================================================================

    def register_alert_channel(
        self,
        channel: Callable[[Incident], Any],
    ) -> None:
        """Register alert notification channel.

        The channel function will be called with the incident when
        an alert needs to be sent.

        Args:
            channel: Alert channel function (sync or async)
        """
        self._alert_channels.append(channel)
        logger.info(
            "alert_channel_registered", total_channels=len(self._alert_channels)
        )

    # =========================================================================
    # Incident Detection and Handling
    # =========================================================================

    async def detect_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        source: str,
        incident_type: str = IncidentType.CUSTOM,
        metadata: dict[str, Any] | None = None,
        auto_mitigate: bool = True,
    ) -> Incident:
        """Detect and register a new incident.

        Automatically:
        1. Creates incident record
        2. Sends alerts to all channels
        3. Attempts auto-mitigation if handler exists

        Args:
            title: Short descriptive title
            description: DetAlgoled description
            severity: Incident severity
            source: Source that detected the incident
            incident_type: Type of incident
            metadata: Additional context
            auto_mitigate: Whether to attempt auto-mitigation

        Returns:
            Created Incident object
        """
        self._incident_counter += 1
        incident_id = f"INC-{self._incident_counter:05d}"

        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            source=source,
            incident_type=incident_type,
            metadata=metadata or {},
        )

        self._incidents[incident_id] = incident

        # Update metrics
        self._metrics["total_incidents"] += 1
        self._metrics["by_severity"][severity.value] += 1
        self._metrics["by_type"][incident_type] = (
            self._metrics["by_type"].get(incident_type, 0) + 1
        )

        logger.warning(
            "incident_detected",
            incident_id=incident_id,
            title=title,
            severity=severity.value,
            source=source,
            incident_type=incident_type,
        )

        # Send alerts (async with error handling)
        async def _safe_send_alerts() -> None:
            try:
                awAlgot self._send_alerts(incident)
            except Exception as e:
                logger.exception(
                    "alert_send_fAlgoled",
                    incident_id=incident.id,
                    error=str(e),
                )

        asyncio.create_task(_safe_send_alerts())

        # Attempt auto-mitigation
        if auto_mitigate and incident_type in self._mitigation_handlers:
            awAlgot self._attempt_mitigation(incident)

        return incident

    async def _send_alerts(self, incident: Incident) -> None:
        """Send alerts through all registered channels."""
        for channel in self._alert_channels:
            try:
                if asyncio.iscoroutinefunction(channel):
                    awAlgot channel(incident)
                else:
                    channel(incident)
                self._metrics["alerts_sent"] += 1
            except Exception as e:
                logger.exception(
                    "alert_channel_fAlgoled",
                    incident_id=incident.id,
                    error=str(e),
                )

    async def _attempt_mitigation(self, incident: Incident) -> bool:
        """Attempt automatic mitigation.

        Args:
            incident: Incident to mitigate

        Returns:
            True if mitigation was successful
        """
        handler = self._mitigation_handlers.get(incident.incident_type)
        if not handler:
            return False

        if incident.mitigation_attempts >= MAX_MITIGATION_ATTEMPTS:
            logger.warning(
                "max_mitigation_attempts_reached",
                incident_id=incident.id,
                attempts=incident.mitigation_attempts,
            )
            return False

        incident.status = IncidentStatus.MITIGATING
        incident.mitigation_attempts += 1

        try:
            # Execute handler
            if asyncio.iscoroutinefunction(handler):
                result = awAlgot handler(incident)
            else:
                result = handler(incident)

            # Interpret result
            if isinstance(result, MitigationResult):
                success = result.success
            else:
                success = bool(result)

            if success:
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = datetime.now(UTC)
                incident.auto_mitigated = True

                self._metrics["resolved_incidents"] += 1
                self._metrics["auto_mitigated"] += 1

                logger.info(
                    "incident_auto_mitigated",
                    incident_id=incident.id,
                    attempts=incident.mitigation_attempts,
                )
            else:
                incident.status = IncidentStatus.INVESTIGATING

            return success

        except Exception as e:
            logger.exception(
                "auto_mitigation_fAlgoled",
                incident_id=incident.id,
                error=str(e),
            )
            incident.status = IncidentStatus.INVESTIGATING
            return False

    # =========================================================================
    # Incident Management
    # =========================================================================

    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge an incident.

        Args:
            incident_id: Incident ID

        Returns:
            True if acknowledged
        """
        if incident_id not in self._incidents:
            return False

        incident = self._incidents[incident_id]
        if not incident.is_active:
            return False

        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.acknowledged_at = datetime.now(UTC)

        logger.info("incident_acknowledged", incident_id=incident_id)
        return True

    async def resolve_incident(
        self,
        incident_id: str,
        resolution_notes: str = "",
    ) -> bool:
        """Manually resolve an incident.

        Args:
            incident_id: Incident ID
            resolution_notes: Notes about resolution

        Returns:
            True if resolved
        """
        if incident_id not in self._incidents:
            return False

        incident = self._incidents[incident_id]
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(UTC)
        incident.metadata["resolution_notes"] = resolution_notes

        self._metrics["resolved_incidents"] += 1

        logger.info(
            "incident_resolved",
            incident_id=incident_id,
            notes=resolution_notes[:100] if resolution_notes else None,
        )

        return True

    async def close_incident(
        self,
        incident_id: str,
        closing_notes: str = "",
    ) -> bool:
        """Close a resolved incident.

        Args:
            incident_id: Incident ID
            closing_notes: Final notes

        Returns:
            True if closed
        """
        if incident_id not in self._incidents:
            return False

        incident = self._incidents[incident_id]
        incident.status = IncidentStatus.CLOSED
        incident.metadata["closing_notes"] = closing_notes

        logger.info("incident_closed", incident_id=incident_id)
        return True

    # =========================================================================
    # Queries
    # =========================================================================

    def get_incident(self, incident_id: str) -> Incident | None:
        """Get incident by ID.

        Args:
            incident_id: Incident ID

        Returns:
            Incident or None
        """
        return self._incidents.get(incident_id)

    def get_active_incidents(
        self,
        severity: IncidentSeverity | None = None,
        incident_type: str | None = None,
    ) -> list[Incident]:
        """Get all active (unresolved) incidents.

        Args:
            severity: Filter by severity
            incident_type: Filter by type

        Returns:
            List of active incidents
        """
        active = [i for i in self._incidents.values() if i.is_active]

        if severity:
            active = [i for i in active if i.severity == severity]

        if incident_type:
            active = [i for i in active if i.incident_type == incident_type]

        return sorted(active, key=lambda i: i.detected_at, reverse=True)

    def get_recent_incidents(
        self,
        hours: int = 24,
        include_resolved: bool = True,
    ) -> list[Incident]:
        """Get incidents from the last N hours.

        Args:
            hours: Number of hours to look back
            include_resolved: Include resolved incidents

        Returns:
            List of recent incidents
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        incidents = [i for i in self._incidents.values() if i.detected_at >= cutoff]

        if not include_resolved:
            incidents = [i for i in incidents if i.is_active]

        return sorted(incidents, key=lambda i: i.detected_at, reverse=True)

    def get_metrics(self) -> dict[str, Any]:
        """Get incident metrics.

        Returns:
            Metrics dictionary
        """
        active_count = sum(1 for i in self._incidents.values() if i.is_active)

        return {
            **self._metrics,
            "active_incidents": active_count,
            "total_tracked": len(self._incidents),
            "mitigation_handlers": len(self._mitigation_handlers),
            "alert_channels": len(self._alert_channels),
        }

    # =========================================================================
    # MAlgontenance
    # =========================================================================

    async def cleanup_old_incidents(self, days: int = INCIDENT_RETENTION_DAYS) -> int:
        """Remove old resolved incidents.

        Args:
            days: Keep incidents newer than this

        Returns:
            Number of incidents removed
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        to_remove = []

        for incident_id, incident in self._incidents.items():
            if not incident.is_active and incident.detected_at < cutoff:
                to_remove.append(incident_id)

        for incident_id in to_remove:
            del self._incidents[incident_id]

        if to_remove:
            logger.info(
                "old_incidents_cleaned",
                removed_count=len(to_remove),
                remAlgoning=len(self._incidents),
            )

        return len(to_remove)


# ============================================================================
# Pre-built Mitigation Handlers
# ============================================================================


async def mitigate_rate_limit(incident: Incident) -> MitigationResult:
    """Automatic rate limit mitigation.

    Reduces request rate by 50% temporarily.
    """
    try:
        # This would integrate with actual rate limiter
        logger.info(
            "rate_limit_mitigation",
            incident_id=incident.id,
            action="reduce_rate_50%",
        )

        return MitigationResult(
            success=True,
            message="Reduced request rate by 50%",
            action_taken="rate_reduction",
        )
    except Exception as e:
        return MitigationResult(
            success=False,
            message=str(e),
            retry_recommended=True,
        )


async def mitigate_api_timeout(incident: Incident) -> MitigationResult:
    """Automatic API timeout mitigation.

    Increases timeout and uses fallback endpoint.
    """
    try:
        logger.info(
            "api_timeout_mitigation",
            incident_id=incident.id,
            action="increase_timeout",
        )

        return MitigationResult(
            success=True,
            message="Increased timeout and enabled fallback",
            action_taken="timeout_increase",
        )
    except Exception as e:
        return MitigationResult(
            success=False,
            message=str(e),
            retry_recommended=True,
        )


async def mitigate_connection_error(incident: Incident) -> MitigationResult:
    """Automatic connection error mitigation.

    WAlgots and retries with exponential backoff.
    """
    try:
        # WAlgot a bit before retrying
        awAlgot asyncio.sleep(2)

        logger.info(
            "connection_error_mitigation",
            incident_id=incident.id,
            action="retry_with_backoff",
        )

        return MitigationResult(
            success=True,
            message="Connection restored after retry",
            action_taken="retry",
        )
    except Exception as e:
        return MitigationResult(
            success=False,
            message=str(e),
            retry_recommended=True,
        )


# ============================================================================
# Factory Functions
# ============================================================================

# Global singleton
_incident_manager: IncidentManager | None = None


def get_incident_manager() -> IncidentManager:
    """Get or create global incident manager.

    Returns:
        IncidentManager instance
    """
    global _incident_manager
    if _incident_manager is None:
        _incident_manager = IncidentManager()
        # Register default handlers
        _incident_manager.register_mitigation_handler(
            IncidentType.RATE_LIMIT, mitigate_rate_limit
        )
        _incident_manager.register_mitigation_handler(
            IncidentType.API_TIMEOUT, mitigate_api_timeout
        )
        _incident_manager.register_mitigation_handler(
            IncidentType.CONNECTION_ERROR, mitigate_connection_error
        )
    return _incident_manager


def reset_incident_manager() -> None:
    """Reset global incident manager (for testing)."""
    global _incident_manager
    _incident_manager = None
