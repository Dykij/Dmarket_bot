"""
incident_manager.py — Production Incident Tracking & Alerting.

v15.7: Tracks trading incidents for post-mortem analysis and real-time alerting.

Incident types:
- API failures (timeout, 5xx, auth errors)
- Price crashes (sudden drops >10%)
- Drawdown events (balance < peak × 85%)
- Circuit breaker trips
- Rate limit hits (429 responses)
- Trade execution failures

Integration:
- Called from error handlers throughout the codebase
- Stats available via /healthz endpoint
- Critical incidents trigger Telegram alerts via notifier
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("IncidentManager")


class Severity(str, Enum):
    """Incident severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IncidentType(str, Enum):
    """Types of tracked incidents."""
    API_FAILURE = "api_failure"
    API_TIMEOUT = "api_timeout"
    API_AUTH_ERROR = "api_auth_error"
    RATE_LIMIT = "rate_limit"
    PRICE_CRASH = "price_crash"
    DRAWDOWN_EVENT = "drawdown_event"
    CIRCUIT_BREAKER = "circuit_breaker"
    TRADE_FAILURE = "trade_failure"
    ORACLE_FAILURE = "oracle_failure"
    DB_ERROR = "db_error"
    NETWORK_ERROR = "network_error"


@dataclass
class Incident:
    """A single incident record."""
    incident_type: str
    severity: str
    title: str
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    resolved: bool = False
    resolved_at: float = 0.0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp if self.timestamp > 0 else 0.0

    @property
    def age_minutes(self) -> float:
        return self.age_seconds / 60.0


class IncidentManager:
    """
    Tracks and manages trading incidents.

    Provides:
    - Incident recording with severity classification
    - Rate-limited Telegram alerts (no spam)
    - Incident statistics for /healthz
    - Post-mortem data for analysis
    """

    def __init__(
        self,
        notifier: Any = None,
        max_incidents: int = 200,
        alert_cooldown_seconds: float = 300.0,  # 5 min between alerts
    ) -> None:
        self._notifier = notifier
        self._max_incidents = max_incidents
        self._alert_cooldown = alert_cooldown_seconds
        self._incidents: deque[Incident] = deque(maxlen=max_incidents)
        self._last_alert_ts: dict[str, float] = {}  # type -> last alert time
        self._stats = {
            "total_incidents": 0,
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "alerts_sent": 0,
            "alerts_suppressed": 0,
        }

    def bind(self, notifier: Any) -> None:
        """Late-bind notifier dependency."""
        self._notifier = notifier

    # ----------------------------------------------------------------
    # Incident Recording
    # ----------------------------------------------------------------

    def record(
        self,
        incident_type: str,
        severity: str,
        title: str,
        description: str = "",
        details: dict[str, Any] | None = None,
        alert: bool = True,
    ) -> Incident:
        """
        Record an incident.

        Args:
            incident_type: IncidentType value
            severity: Severity value (info, warning, critical)
            title: short title for the incident
            description: detailed description
            details: additional context (item_id, price, error message, etc.)
            alert: whether to send Telegram alert (rate-limited)

        Returns:
            The created Incident
        """
        now = time.time()
        incident = Incident(
            incident_type=incident_type,
            severity=severity,
            title=title,
            description=description,
            details=details or {},
            timestamp=now,
        )

        self._incidents.append(incident)
        self._stats["total_incidents"] += 1

        if severity == Severity.CRITICAL:
            self._stats["critical_count"] += 1
        elif severity == Severity.WARNING:
            self._stats["warning_count"] += 1
        else:
            self._stats["info_count"] += 1

        # Log
        log_msg = f"[Incident] {severity.upper()}: {title}"
        if description:
            log_msg += f" — {description}"

        if severity == Severity.CRITICAL:
            logger.error(log_msg)
        elif severity == Severity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Alert (rate-limited)
        if alert and severity in (Severity.CRITICAL, Severity.WARNING):
            self._send_alert(incident)

        return incident

    def record_api_failure(
        self,
        endpoint: str,
        status_code: int,
        error_message: str = "",
    ) -> Incident:
        """Record an API failure incident."""
        if status_code == 429:
            return self.record(
                IncidentType.RATE_LIMIT, Severity.WARNING,
                f"Rate limited: {endpoint}",
                f"HTTP 429 on {endpoint}",
                {"endpoint": endpoint, "status": status_code},
            )
        elif status_code == 401 or status_code == 403:
            return self.record(
                IncidentType.API_AUTH_ERROR, Severity.CRITICAL,
                f"Auth error: {endpoint}",
                f"HTTP {status_code} on {endpoint}",
                {"endpoint": endpoint, "status": status_code},
            )
        elif status_code >= 500:
            return self.record(
                IncidentType.API_FAILURE, Severity.WARNING,
                f"Server error: {endpoint}",
                f"HTTP {status_code} on {endpoint}: {error_message}",
                {"endpoint": endpoint, "status": status_code},
            )
        else:
            return self.record(
                IncidentType.API_FAILURE, Severity.INFO,
                f"API error: {endpoint}",
                f"HTTP {status_code} on {endpoint}",
                {"endpoint": endpoint, "status": status_code},
            )

    def record_price_crash(
        self,
        title: str,
        old_price: float,
        new_price: float,
        pct_change: float,
    ) -> Incident:
        """Record a price crash incident."""
        return self.record(
            IncidentType.PRICE_CRASH, Severity.WARNING,
            f"Price crash: {title}",
            f"Price dropped {pct_change:.1f}% (${old_price:.2f} → ${new_price:.2f})",
            {"title": title, "old_price": old_price, "new_price": new_price, "pct_change": pct_change},
        )

    def record_drawdown(
        self,
        current_balance: float,
        peak_balance: float,
        drawdown_pct: float,
    ) -> Incident:
        """Record a drawdown event."""
        severity = Severity.CRITICAL if drawdown_pct > 15 else Severity.WARNING
        return self.record(
            IncidentType.DRAWDOWN_EVENT, severity,
            f"Drawdown: {drawdown_pct:.1f}%",
            f"Balance ${current_balance:.2f} < peak ${peak_balance:.2f} × {100 - drawdown_pct:.0f}%",
            {"current": current_balance, "peak": peak_balance, "drawdown_pct": drawdown_pct},
        )

    def record_circuit_breaker(
        self,
        component: str,
        state: str,
        reason: str = "",
    ) -> Incident:
        """Record a circuit breaker state change."""
        return self.record(
            IncidentType.CIRCUIT_BREAKER, Severity.WARNING,
            f"Circuit breaker {state}: {component}",
            reason,
            {"component": component, "state": state},
        )

    def record_trade_failure(
        self,
        title: str,
        error: str,
        price: float = 0.0,
    ) -> Incident:
        """Record a trade execution failure."""
        return self.record(
            IncidentType.TRADE_FAILURE, Severity.WARNING,
            f"Trade failed: {title}",
            error,
            {"title": title, "error": error, "price": price},
        )

    # ----------------------------------------------------------------
    # Alert Management
    # ----------------------------------------------------------------

    def _send_alert(self, incident: Incident) -> None:
        """Send a Telegram alert (rate-limited by incident type)."""
        now = time.time()
        last_ts = self._last_alert_ts.get(incident.incident_type, 0.0)

        if now - last_ts < self._alert_cooldown:
            self._stats["alerts_suppressed"] += 1
            return

        self._last_alert_ts[incident.incident_type] = now
        self._stats["alerts_sent"] += 1

        if self._notifier is not None:
            try:
                import asyncio
                # Try to send alert (may fail if not in async context)
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(
                        self._notifier.error(
                            error_type="incident",
                            error_message=f"[{incident.severity.upper()}] {incident.title}",
                            context=incident.description,
                        )
                    )
            except Exception as e:
                logger.debug(f"[IncidentManager] Alert send failed: {e}")

    # ----------------------------------------------------------------
    # Query & Stats
    # ----------------------------------------------------------------

    def get_recent_incidents(self, count: int = 20) -> list[Incident]:
        """Get the most recent incidents."""
        return list(self._incidents)[-count:]

    def get_incidents_by_type(self, incident_type: str) -> list[Incident]:
        """Get all incidents of a specific type."""
        return [i for i in self._incidents if i.incident_type == incident_type]

    def get_incidents_by_severity(self, severity: str) -> list[Incident]:
        """Get all incidents of a specific severity."""
        return [i for i in self._incidents if i.severity == severity]

    def get_unresolved_count(self) -> int:
        """Count of unresolved incidents."""
        return len([i for i in self._incidents if not i.resolved])

    def get_stats(self) -> dict[str, Any]:
        """Get incident manager statistics."""
        now = time.time()
        # Count incidents in last hour
        last_hour = len([
            i for i in self._incidents
            if now - i.timestamp < 3600
        ])
        last_day = len([
            i for i in self._incidents
            if now - i.timestamp < 86400
        ])

        return {
            **self._stats,
            "active_incidents": len(self._incidents),
            "last_hour": last_hour,
            "last_day": last_day,
            "by_type": {
                t.value: len(self.get_incidents_by_type(t.value))
                for t in IncidentType
            },
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        stats = self.get_stats()
        lines = [
            f"IncidentManager: {stats['total_incidents']} total, "
            f"{stats['last_hour']} in last hour",
            f"  Critical: {stats['critical_count']}, "
            f"Warning: {stats['warning_count']}, "
            f"Info: {stats['info_count']}",
            f"  Alerts sent: {stats['alerts_sent']}, "
            f"suppressed: {stats['alerts_suppressed']}",
        ]
        for t in IncidentType:
            count = stats["by_type"].get(t.value, 0)
            if count > 0:
                lines.append(f"  {t.value}: {count}")
        return "\n".join(lines)
