"""Incident manager."""
import uuid
from enum import Enum
from typing import Any


class IncidentSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentType(Enum):
    CUSTOM = "custom"
    API_FAILURE = "api_failure"
    DB_ERROR = "db_error"
    TRADING_HALT = "trading_halt"


class Incident:
    def __init__(self, title: str, severity: IncidentSeverity, source: str,
                 incident_type: IncidentType | None = None) -> None:
        self.id = str(uuid.uuid4())
        self.title = title
        self.severity = severity
        self.source = source
        self.incident_type = incident_type
        self.is_active = True
        self.acknowledged = False


_incident_manager: Any = None


class IncidentManager:
    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}

    async def detect_incident(
        self, title: str, description: str, severity: IncidentSeverity,
        source: str, incident_type: IncidentType | None = None,
        auto_mitigate: bool = False,
    ) -> Incident:
        inc = Incident(title, severity, source, incident_type)
        self._incidents[inc.id] = inc
        return inc

    async def resolve_incident(self, incident_id: str) -> bool:
        inc = self._incidents.get(incident_id)
        if inc:
            inc.is_active = False
            return True
        return False

    async def acknowledge_incident(self, incident_id: str) -> bool:
        inc = self._incidents.get(incident_id)
        if inc:
            inc.acknowledged = True
            return True
        return False

    def get_metrics(self) -> dict:
        by_severity: dict[str, int] = {}
        for inc in self._incidents.values():
            s = inc.severity.value
            by_severity[s] = by_severity.get(s, 0) + 1
        return {"total_incidents": len(self._incidents), "by_severity": by_severity}


def get_incident_manager() -> IncidentManager:
    global _incident_manager
    if _incident_manager is None:
        _incident_manager = IncidentManager()
    return _incident_manager


def reset_incident_manager() -> None:
    global _incident_manager
    _incident_manager = None
