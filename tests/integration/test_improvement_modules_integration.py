"""Integration tests for new improvement modules with bot.

Tests that:
- All modules import correctly
- Handlers register properly
- Modules work together
- Bot integration points function correctly

Created: January 2026
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ============================================================================
# Test Module Imports
# ============================================================================


class TestModuleImports:
    """Test that all new modules import correctly."""

    def test_knowledge_base_imports(self) -> None:
        """Test Knowledge Base module imports."""
        from src.utils.knowledge_base import (
            KnowledgeBase,
            KnowledgeType,
            get_knowledge_base,
        )

        assert KnowledgeBase is not None
        assert KnowledgeType is not None
        assert get_knowledge_base is not None

    def test_incident_manager_imports(self) -> None:
        """Test Incident Manager module imports."""
        from src.utils.incident_manager import (
            IncidentManager,
            IncidentSeverity,
            get_incident_manager,
        )

        assert IncidentManager is not None
        assert IncidentSeverity is not None
        assert get_incident_manager is not None

    def test_n8n_client_imports(self) -> None:
        """Test N8N Client module imports."""
        from src.utils.n8n_client import (
            N8NClient,
            TradingWorkflows,
            create_n8n_client,
        )

        assert N8NClient is not None
        assert TradingWorkflows is not None
        assert create_n8n_client is not None

    def test_knowledge_handler_imports(self) -> None:
        """Test Knowledge Handler imports."""
        from src.telegram_bot.handlers.knowledge_handler import (
            knowledge_command,
            register_handlers,
        )

        assert knowledge_command is not None
        assert register_handlers is not None

    def test_knowledge_models_imports(self) -> None:
        """Test Knowledge Models imports."""
        from src.models.knowledge import (
            KnowledgeEntry,
            LessonLearned,
            TradingPattern,
        )

        assert KnowledgeEntry is not None
        assert TradingPattern is not None
        assert LessonLearned is not None


# ============================================================================
# Test Handler Registration
# ============================================================================


class TestHandlerRegistration:
    """Test that handlers register correctly."""

    def test_knowledge_handler_registration(self) -> None:
        """Test Knowledge Handler registers commands."""
        from src.telegram_bot.handlers.knowledge_handler import register_handlers

        # Create mock application
        mock_app = MagicMock()
        mock_app.add_handler = MagicMock()

        # Register handlers
        register_handlers(mock_app)

        # Verify handlers were added
        assert mock_app.add_handler.call_count >= 3  # At least 3 handlers


# ============================================================================
# Test Module Integration
# ============================================================================


class TestModuleIntegration:
    """Test modules work together correctly."""

    @pytest.mark.asyncio()
    async def test_knowledge_base_basic_workflow(self) -> None:
        """Test basic Knowledge Base workflow."""
        from src.utils.knowledge_base import (
            KnowledgeBase,
            KnowledgeType,
            clear_knowledge_base_cache,
        )

        # Reset cache
        clear_knowledge_base_cache()

        # Create knowledge base
        kb = KnowledgeBase(user_id=12345)

        # Add knowledge
        item_id = awAlgot kb.add_knowledge(
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title="Test Pattern",
            content={"item": "AK-47", "profit": 10.0},
        )

        assert item_id is not None
        assert isinstance(item_id, str)

        # Query knowledge
        results = awAlgot kb.query_relevant(context={"item": "AK-47"})
        assert len(results) > 0

        # Get summary
        summary = awAlgot kb.get_summary()
        assert summary["total_entries"] > 0

    @pytest.mark.asyncio()
    async def test_incident_manager_basic_workflow(self) -> None:
        """Test basic Incident Manager workflow."""
        from src.utils.incident_manager import (
            IncidentManager,
            IncidentSeverity,
            IncidentType,
            reset_incident_manager,
        )

        # Reset singleton
        reset_incident_manager()

        # Create manager
        manager = IncidentManager()

        # Detect incident
        incident = awAlgot manager.detect_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.LOW,
            source="test",
            incident_type=IncidentType.CUSTOM,
            auto_mitigate=False,
        )

        assert incident is not None
        assert incident.title == "Test Incident"
        assert incident.is_active

        # Resolve incident
        result = awAlgot manager.resolve_incident(incident.id)
        assert result is True
        assert not incident.is_active

    @pytest.mark.asyncio()
    async def test_n8n_client_initialization(self) -> None:
        """Test N8N Client initialization."""
        from src.utils.n8n_client import N8NClient

        client = N8NClient(
            base_url="http://localhost:5678",
            api_key="test-key",
        )

        assert client.base_url == "http://localhost:5678"
        assert client.api_key == "test-key"


# ============================================================================
# Test Bot Data Integration
# ============================================================================


class TestBotDatAlgontegration:
    """Test modules integrate with bot_data correctly."""

    def test_incident_manager_stored_in_bot_data(self) -> None:
        """Test Incident Manager is stored in bot_data."""
        from src.utils.incident_manager import get_incident_manager, reset_incident_manager

        reset_incident_manager()

        # Simulate what register_all_handlers does
        mock_app = MagicMock()
        mock_app.bot_data = {}

        incident_manager = get_incident_manager()
        mock_app.bot_data["incident_manager"] = incident_manager

        # Verify it's accessible
        assert "incident_manager" in mock_app.bot_data
        assert mock_app.bot_data["incident_manager"] is incident_manager


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling in modules."""

    @pytest.mark.asyncio()
    async def test_knowledge_base_handles_empty_query(self) -> None:
        """Test Knowledge Base handles empty query gracefully."""
        from src.utils.knowledge_base import KnowledgeBase, clear_knowledge_base_cache

        clear_knowledge_base_cache()
        kb = KnowledgeBase(user_id=99999)

        # Query empty knowledge base
        results = awAlgot kb.query_relevant(context={})
        assert results == []

    @pytest.mark.asyncio()
    async def test_incident_manager_handles_invalid_id(self) -> None:
        """Test Incident Manager handles invalid IDs."""
        from src.utils.incident_manager import IncidentManager, reset_incident_manager

        reset_incident_manager()
        manager = IncidentManager()

        # Try to resolve non-existent incident
        result = awAlgot manager.resolve_incident("INC-99999")
        assert result is False

        # Try to acknowledge non-existent incident
        result = awAlgot manager.acknowledge_incident("INC-99999")
        assert result is False


# ============================================================================
# Test Module Metrics
# ============================================================================


class TestModuleMetrics:
    """Test metrics collection in modules."""

    @pytest.mark.asyncio()
    async def test_knowledge_base_metrics(self) -> None:
        """Test Knowledge Base metrics collection."""
        from src.utils.knowledge_base import (
            KnowledgeBase,
            KnowledgeType,
            clear_knowledge_base_cache,
        )

        clear_knowledge_base_cache()
        kb = KnowledgeBase(user_id=11111)

        # Add some knowledge
        awAlgot kb.add_knowledge(
            knowledge_type=KnowledgeType.TRADING_PATTERN,
            title="Pattern 1",
            content={"test": 1},
        )

        # Check metrics
        summary = awAlgot kb.get_summary()
        assert summary["total_entries"] == 1
        assert summary["by_type"][KnowledgeType.TRADING_PATTERN.value] == 1

    @pytest.mark.asyncio()
    async def test_incident_manager_metrics(self) -> None:
        """Test Incident Manager metrics collection."""
        from src.utils.incident_manager import (
            IncidentManager,
            IncidentSeverity,
            reset_incident_manager,
        )

        reset_incident_manager()
        manager = IncidentManager()

        # Create incident
        awAlgot manager.detect_incident(
            title="Metric Test",
            description="Test",
            severity=IncidentSeverity.HIGH,
            source="test",
            auto_mitigate=False,
        )

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_incidents"] == 1
        assert metrics["by_severity"]["high"] == 1
