"""Tests for Incident Manager module.

Tests cover:
- Incident detection and registration
- Automatic mitigation
- Alert channels
- Incident lifecycle management
- Metrics and queries

Created: January 2026
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.utils.incident_manager import (
    Incident,
    IncidentManager,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    MitigationResult,
    get_incident_manager,
    mitigate_api_timeout,
    mitigate_rate_limit,
    reset_incident_manager,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def incident_manager() -> IncidentManager:
    """Create a fresh incident manager for testing."""
    reset_incident_manager()
    return IncidentManager()


@pytest.fixture()
def sample_incident() -> Incident:
    """Create a sample incident."""
    return Incident(
        id="INC-00001",
        title="Test Incident",
        description="This is a test incident",
        severity=IncidentSeverity.MEDIUM,
        source="test",
        incident_type=IncidentType.API_ERROR,
    )


# ============================================================================
# Test Incident Data Class
# ============================================================================


class TestIncidentDataClass:
    """Test Incident data class."""

    def test_incident_creation(self, sample_incident: Incident) -> None:
        """Test incident is created with correct values."""
        assert sample_incident.id == "INC-00001"
        assert sample_incident.title == "Test Incident"
        assert sample_incident.severity == IncidentSeverity.MEDIUM
        assert sample_incident.status == IncidentStatus.DETECTED
        assert sample_incident.is_active is True

    def test_incident_to_dict(self, sample_incident: Incident) -> None:
        """Test incident to_dict conversion."""
        d = sample_incident.to_dict()

        assert d["id"] == "INC-00001"
        assert d["title"] == "Test Incident"
        assert d["severity"] == "medium"
        assert d["status"] == "detected"
        assert "detected_at" in d

    def test_incident_duration_unresolved(self, sample_incident: Incident) -> None:
        """Test duration calculation for unresolved incident."""
        duration = sample_incident.duration

        assert duration is not None
        assert duration.total_seconds() >= 0

    def test_incident_duration_resolved(self) -> None:
        """Test duration calculation for resolved incident."""
        detected = datetime.now(UTC) - timedelta(hours=2)
        resolved = datetime.now(UTC) - timedelta(hours=1)

        incident = Incident(
            id="INC-00002",
            title="Resolved",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            detected_at=detected,
            resolved_at=resolved,
        )

        duration = incident.duration
        assert duration is not None
        # Should be approximately 1 hour
        assert 3500 <= duration.total_seconds() <= 3700

    def test_incident_is_active(self) -> None:
        """Test is_active property."""
        incident = Incident(
            id="INC-00003",
            title="Active",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            status=IncidentStatus.INVESTIGATING,
        )
        assert incident.is_active is True

        incident.status = IncidentStatus.RESOLVED
        assert incident.is_active is False

        incident.status = IncidentStatus.CLOSED
        assert incident.is_active is False


# ============================================================================
# Test Incident Manager Initialization
# ============================================================================


class TestIncidentManagerInit:
    """Test incident manager initialization."""

    def test_init_creates_empty_state(self, incident_manager: IncidentManager) -> None:
        """Test manager initializes with empty state."""
        assert len(incident_manager._incidents) == 0
        assert len(incident_manager._mitigation_handlers) == 0
        assert len(incident_manager._alert_channels) == 0

    def test_init_metrics(self, incident_manager: IncidentManager) -> None:
        """Test initial metrics are zero."""
        metrics = incident_manager.get_metrics()

        assert metrics["total_incidents"] == 0
        assert metrics["resolved_incidents"] == 0
        assert metrics["auto_mitigated"] == 0


# ============================================================================
# Test Mitigation Handler Registration
# ============================================================================


class TestMitigationHandlerRegistration:
    """Test mitigation handler registration."""

    def test_register_handler(self, incident_manager: IncidentManager) -> None:
        """Test registering a mitigation handler."""

        async def my_handler(incident: Incident) -> bool:
            return True

        incident_manager.register_mitigation_handler("my_type", my_handler)

        assert "my_type" in incident_manager._mitigation_handlers

    def test_unregister_handler(self, incident_manager: IncidentManager) -> None:
        """Test unregistering a mitigation handler."""

        def handler(incident: Incident) -> bool:
            return True

        incident_manager.register_mitigation_handler("to_remove", handler)
        result = incident_manager.unregister_mitigation_handler("to_remove")

        assert result is True
        assert "to_remove" not in incident_manager._mitigation_handlers

    def test_unregister_nonexistent(self, incident_manager: IncidentManager) -> None:
        """Test unregistering non-existent handler."""
        result = incident_manager.unregister_mitigation_handler("nonexistent")
        assert result is False


# ============================================================================
# Test Alert Channel Registration
# ============================================================================


class TestAlertChannelRegistration:
    """Test alert channel registration."""

    def test_register_alert_channel(self, incident_manager: IncidentManager) -> None:
        """Test registering an alert channel."""
        alerts_received = []

        def alert_handler(incident: Incident) -> None:
            alerts_received.append(incident)

        incident_manager.register_alert_channel(alert_handler)

        assert len(incident_manager._alert_channels) == 1


# ============================================================================
# Test Incident Detection
# ============================================================================


class TestIncidentDetection:
    """Test incident detection."""

    @pytest.mark.asyncio()
    async def test_detect_incident_creates_record(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test detecting an incident creates a record."""
        incident = await incident_manager.detect_incident(
            title="Test Incident",
            description="This is a test",
            severity=IncidentSeverity.HIGH,
            source="test_source",
            incident_type=IncidentType.API_ERROR,
        )

        assert incident is not None
        assert incident.id == "INC-00001"
        assert incident.title == "Test Incident"
        assert incident.severity == IncidentSeverity.HIGH
        assert incident.id in incident_manager._incidents

    @pytest.mark.asyncio()
    async def test_detect_incident_increments_counter(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test incident IDs increment correctly."""
        inc1 = await incident_manager.detect_incident(
            title="First",
            description="First",
            severity=IncidentSeverity.LOW,
            source="test",
        )

        inc2 = await incident_manager.detect_incident(
            title="Second",
            description="Second",
            severity=IncidentSeverity.LOW,
            source="test",
        )

        assert inc1.id == "INC-00001"
        assert inc2.id == "INC-00002"

    @pytest.mark.asyncio()
    async def test_detect_incident_updates_metrics(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test detection updates metrics."""
        await incident_manager.detect_incident(
            title="High Severity",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            incident_type=IncidentType.RATE_LIMIT,
        )

        metrics = incident_manager.get_metrics()

        assert metrics["total_incidents"] == 1
        assert metrics["by_severity"]["high"] == 1
        assert metrics["by_type"].get("rate_limit", 0) == 1

    @pytest.mark.asyncio()
    async def test_detect_incident_with_metadata(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test incident with custom metadata."""
        incident = await incident_manager.detect_incident(
            title="With Metadata",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
            metadata={"error_code": 429, "endpoint": "/api/items"},
        )

        assert incident.metadata["error_code"] == 429
        assert incident.metadata["endpoint"] == "/api/items"


# ============================================================================
# Test Automatic Mitigation
# ============================================================================


class TestAutomaticMitigation:
    """Test automatic mitigation functionality."""

    @pytest.mark.asyncio()
    async def test_auto_mitigation_success(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test successful automatic mitigation."""

        async def successful_handler(incident: Incident) -> bool:
            return True

        incident_manager.register_mitigation_handler("test_type", successful_handler)

        incident = await incident_manager.detect_incident(
            title="Test",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
            incident_type="test_type",
        )

        # Give async task time to complete
        await asyncio.sleep(0.1)

        assert incident.status == IncidentStatus.RESOLVED
        assert incident.auto_mitigated is True
        assert incident.mitigation_attempts == 1

    @pytest.mark.asyncio()
    async def test_auto_mitigation_failure(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test failed automatic mitigation."""

        async def failing_handler(incident: Incident) -> bool:
            return False

        incident_manager.register_mitigation_handler("fail_type", failing_handler)

        incident = await incident_manager.detect_incident(
            title="Will Fail",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            incident_type="fail_type",
        )

        await asyncio.sleep(0.1)

        assert incident.status == IncidentStatus.INVESTIGATING
        assert incident.auto_mitigated is False

    @pytest.mark.asyncio()
    async def test_no_mitigation_without_handler(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test no mitigation attempted without handler."""
        incident = await incident_manager.detect_incident(
            title="No Handler",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            incident_type="unknown_type",
        )

        assert incident.mitigation_attempts == 0
        assert incident.status == IncidentStatus.DETECTED

    @pytest.mark.asyncio()
    async def test_disable_auto_mitigation(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test disabling auto-mitigation."""

        async def handler(incident: Incident) -> bool:
            return True

        incident_manager.register_mitigation_handler("skip_type", handler)

        incident = await incident_manager.detect_incident(
            title="Skip Mitigation",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            incident_type="skip_type",
            auto_mitigate=False,
        )

        assert incident.mitigation_attempts == 0


# ============================================================================
# Test Incident Lifecycle
# ============================================================================


class TestIncidentLifecycle:
    """Test incident lifecycle management."""

    @pytest.mark.asyncio()
    async def test_acknowledge_incident(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test acknowledging an incident."""
        incident = await incident_manager.detect_incident(
            title="To Acknowledge",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
            auto_mitigate=False,
        )

        result = await incident_manager.acknowledge_incident(incident.id)

        assert result is True
        assert incident.status == IncidentStatus.ACKNOWLEDGED
        assert incident.acknowledged_at is not None

    @pytest.mark.asyncio()
    async def test_resolve_incident(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test resolving an incident."""
        incident = await incident_manager.detect_incident(
            title="To Resolve",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            auto_mitigate=False,
        )

        result = await incident_manager.resolve_incident(
            incident.id,
            resolution_notes="Fixed manually",
        )

        assert result is True
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None
        assert incident.metadata["resolution_notes"] == "Fixed manually"

    @pytest.mark.asyncio()
    async def test_close_incident(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test closing an incident."""
        incident = await incident_manager.detect_incident(
            title="To Close",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            auto_mitigate=False,
        )

        await incident_manager.resolve_incident(incident.id)
        result = await incident_manager.close_incident(
            incident.id,
            closing_notes="All good",
        )

        assert result is True
        assert incident.status == IncidentStatus.CLOSED

    @pytest.mark.asyncio()
    async def test_operations_on_nonexistent(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test operations on non-existent incident."""
        assert await incident_manager.acknowledge_incident("fake") is False
        assert await incident_manager.resolve_incident("fake") is False
        assert await incident_manager.close_incident("fake") is False


# ============================================================================
# Test Queries
# ============================================================================


class TestQueries:
    """Test query methods."""

    @pytest.mark.asyncio()
    async def test_get_incident(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test getting incident by ID."""
        incident = await incident_manager.detect_incident(
            title="Get Me",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            auto_mitigate=False,
        )

        found = incident_manager.get_incident(incident.id)
        assert found is incident

    @pytest.mark.asyncio()
    async def test_get_nonexistent_incident(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test getting non-existent incident."""
        found = incident_manager.get_incident("INC-99999")
        assert found is None

    @pytest.mark.asyncio()
    async def test_get_active_incidents(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test getting active incidents."""
        inc1 = await incident_manager.detect_incident(
            title="Active 1",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            auto_mitigate=False,
        )

        inc2 = await incident_manager.detect_incident(
            title="Active 2",
            description="Test",
            severity=IncidentSeverity.MEDIUM,
            source="test",
            auto_mitigate=False,
        )

        await incident_manager.resolve_incident(inc1.id)

        active = incident_manager.get_active_incidents()

        assert len(active) == 1
        assert active[0].id == inc2.id

    @pytest.mark.asyncio()
    async def test_get_active_by_severity(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test filtering active incidents by severity."""
        await incident_manager.detect_incident(
            title="High",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            auto_mitigate=False,
        )

        await incident_manager.detect_incident(
            title="Low",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            auto_mitigate=False,
        )

        high_only = incident_manager.get_active_incidents(
            severity=IncidentSeverity.HIGH
        )

        assert len(high_only) == 1
        assert high_only[0].severity == IncidentSeverity.HIGH

    @pytest.mark.asyncio()
    async def test_get_recent_incidents(
        self, incident_manager: IncidentManager
    ) -> None:
        """Test getting recent incidents."""
        await incident_manager.detect_incident(
            title="Recent",
            description="Test",
            severity=IncidentSeverity.LOW,
            source="test",
            auto_mitigate=False,
        )

        recent = incident_manager.get_recent_incidents(hours=1)

        assert len(recent) == 1


# ============================================================================
# Test Pre-built Mitigation Handlers
# ============================================================================


class TestPrebuiltMitigationHandlers:
    """Test pre-built mitigation handlers."""

    @pytest.mark.asyncio()
    async def test_rate_limit_mitigation(self, sample_incident: Incident) -> None:
        """Test rate limit mitigation handler."""
        result = await mitigate_rate_limit(sample_incident)

        assert isinstance(result, MitigationResult)
        assert result.success is True
        assert "rate" in result.message.lower()

    @pytest.mark.asyncio()
    async def test_api_timeout_mitigation(self, sample_incident: Incident) -> None:
        """Test API timeout mitigation handler."""
        result = await mitigate_api_timeout(sample_incident)

        assert isinstance(result, MitigationResult)
        assert result.success is True


# ============================================================================
# Test Factory Functions
# ============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_get_incident_manager_creates_singleton(self) -> None:
        """Test get_incident_manager returns singleton."""
        reset_incident_manager()

        manager1 = get_incident_manager()
        manager2 = get_incident_manager()

        assert manager1 is manager2

    def test_get_incident_manager_has_default_handlers(self) -> None:
        """Test singleton has default handlers registered."""
        reset_incident_manager()

        manager = get_incident_manager()

        assert IncidentType.RATE_LIMIT in manager._mitigation_handlers
        assert IncidentType.API_TIMEOUT in manager._mitigation_handlers
        assert IncidentType.CONNECTION_ERROR in manager._mitigation_handlers

    def test_reset_incident_manager(self) -> None:
        """Test resetting creates new instance."""
        reset_incident_manager()
        manager1 = get_incident_manager()

        reset_incident_manager()
        manager2 = get_incident_manager()

        assert manager1 is not manager2
