"""Tests for Canonical Logging module.

Based on SkillsMP recommendations for testing logging utilities.
"""

import pytest

from src.utils.canonical_logging import (
    CanonicalLogEntry,
    CanonicalLogManager,
    canonical_log_processor,
    get_canonical_log_manager,
)


class TestCanonicalLogEntry:
    """Tests for CanonicalLogEntry dataclass."""

    def test_initial_values(self):
        """Test initial entry values."""
        # Act
        entry = CanonicalLogEntry()

        # Assert
        assert entry.request_id is None
        assert entry.user_id is None
        assert entry.operation is None
        assert entry.db_queries == 0
        assert entry.cache_hits == 0
        assert entry.errors == 0

    def test_increment_counter(self):
        """Test incrementing counters."""
        # Arrange
        entry = CanonicalLogEntry()

        # Act
        entry.increment("db_queries")
        entry.increment("db_queries")
        entry.increment("api_calls", 3)

        # Assert
        assert entry.db_queries == 2
        assert entry.api_calls == 3

    def test_add_extra(self):
        """Test adding extra fields."""
        # Arrange
        entry = CanonicalLogEntry()

        # Act
        entry.add_extra("item_id", "item_123")
        entry.add_extra("profit", 15.5)

        # Assert
        assert entry.extra["item_id"] == "item_123"
        assert entry.extra["profit"] == 15.5

    def test_duration_calculation(self):
        """Test duration calculation."""
        # Arrange
        import time

        entry = CanonicalLogEntry()

        # Act
        time.sleep(0.01)  # 10ms
        entry.end_time = time.perf_counter()

        # Assert
        assert entry.duration_ms >= 10

    def test_to_dict(self):
        """Test conversion to dictionary."""
        # Arrange
        entry = CanonicalLogEntry(
            request_id="req-123",
            user_id=456,
            operation="test_op",
        )
        entry.db_queries = 5
        entry.add_extra("custom", "value")
        entry.end_time = entry.start_time + 0.1  # 100ms

        # Act
        result = entry.to_dict()

        # Assert
        assert result["request_id"] == "req-123"
        assert result["user_id"] == 456
        assert result["operation"] == "test_op"
        assert result["db_queries"] == 5
        assert result["custom"] == "value"
        assert "duration_ms" in result

    def test_to_dict_excludes_zero_values(self):
        """Test that zero values are excluded from dict."""
        # Arrange
        entry = CanonicalLogEntry(operation="test")

        # Act
        result = entry.to_dict()

        # Assert
        assert "db_queries" not in result  # 0 excluded
        assert "cache_hits" not in result  # 0 excluded
        assert "operation" in result  # non-zero included


class TestCanonicalLogManager:
    """Tests for CanonicalLogManager class."""

    @pytest.fixture
    def manager(self):
        """Create canonical log manager."""
        return CanonicalLogManager()

    def test_operation_context_manager(self, manager):
        """Test operation context manager."""
        # Act
        with manager.operation("test_operation", user_id=123) as entry:
            entry.db_queries = 5
            entry.add_extra("items_processed", 10)

        # Assert - entry was populated
        assert entry.operation == "test_operation"
        assert entry.user_id == 123
        assert entry.db_queries == 5
        assert entry.extra["items_processed"] == 10

    def test_operation_with_error(self, manager):
        """Test operation context manager with error."""
        # Act & Assert
        with pytest.raises(ValueError), manager.operation("failing_op") as entry:
            raise ValueError("Test error")

        # Assert - error was recorded
        assert entry.errors == 1
        assert entry.extra["error"] == "Test error"
        assert entry.extra["error_type"] == "ValueError"

    def test_operation_timing(self, manager):
        """Test that timing is recorded."""
        import time

        # Act
        with manager.operation("timed_op") as entry:
            time.sleep(0.01)  # 10ms

        # Assert
        assert entry.duration_ms >= 10

    def test_operation_with_request_id(self, manager):
        """Test operation with request ID."""
        # Act
        with manager.operation("op", request_id="req-456") as entry:
            pass

        # Assert
        assert entry.request_id == "req-456"


class TestCanonicalLogProcessor:
    """Tests for canonical_log_processor function."""

    def test_processor_adds_context(self):
        """Test that processor adds canonical context."""
        from src.utils.canonical_logging import _canonical_context

        # Arrange
        event_dict: dict = {"event": "test_event"}
        _canonical_context.set({
            "request_id": "req-789",
            "user_id": 123,
            "operation": "test_op",
        })

        # Act
        result = canonical_log_processor(None, "info", event_dict)

        # Assert
        assert result["request_id"] == "req-789"
        assert result["user_id"] == 123
        assert result["operation"] == "test_op"

        # Cleanup
        _canonical_context.set({})

    def test_processor_preserves_existing_fields(self):
        """Test that processor preserves existing fields."""
        from src.utils.canonical_logging import _canonical_context

        # Arrange
        event_dict: dict = {
            "event": "test_event",
            "request_id": "existing-id",  # Should not be overwritten
        }
        _canonical_context.set({"request_id": "new-id"})

        # Act
        result = canonical_log_processor(None, "info", event_dict)

        # Assert - existing value preserved
        assert result["request_id"] == "existing-id"

        # Cleanup
        _canonical_context.set({})

    def test_processor_handles_empty_context(self):
        """Test processor with empty context."""
        from src.utils.canonical_logging import _canonical_context

        # Arrange
        event_dict: dict = {"event": "test_event"}
        _canonical_context.set({})

        # Act
        result = canonical_log_processor(None, "info", event_dict)

        # Assert - original dict unchanged
        assert result == {"event": "test_event"}


class TestGetCanonicalLogManager:
    """Tests for get_canonical_log_manager function."""

    def test_singleton_creation(self):
        """Test singleton is created."""
        from src.utils import canonical_logging as module

        # Reset singleton
        module._canonical_manager = None

        # Act
        manager1 = get_canonical_log_manager()
        manager2 = get_canonical_log_manager()

        # Assert
        assert manager1 is manager2
