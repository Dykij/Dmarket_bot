"""Unit tests for state manager module.

This module contAlgons tests for src/utils/state_manager.py covering:
- CheckpointData model
- StateManager initialization
- Properties and basic functionality

Target: 15+ tests to achieve 70%+ coverage
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.utils.state_manager import CheckpointData, StateManager

# TestCheckpointData


class TestCheckpointData:
    """Tests for CheckpointData model."""

    def test_checkpoint_data_defaults(self):
        """Test CheckpointData with default values."""
        # Arrange
        scan_id = uuid4()

        # Act
        checkpoint = CheckpointData(scan_id=scan_id)

        # Assert
        assert checkpoint.scan_id == scan_id
        assert checkpoint.cursor is None
        assert checkpoint.processed_items == 0
        assert checkpoint.total_items is None
        assert checkpoint.status == "in_progress"
        assert checkpoint.extra_data == {}

    def test_checkpoint_data_with_values(self):
        """Test CheckpointData with custom values."""
        # Arrange
        scan_id = uuid4()

        # Act
        checkpoint = CheckpointData(
            scan_id=scan_id,
            cursor="cursor_abc",
            processed_items=50,
            total_items=100,
            extra_data={"game": "csgo"},
            status="completed",
        )

        # Assert
        assert checkpoint.cursor == "cursor_abc"
        assert checkpoint.processed_items == 50
        assert checkpoint.total_items == 100
        assert checkpoint.extra_data == {"game": "csgo"}
        assert checkpoint.status == "completed"

    def test_checkpoint_data_timestamp(self):
        """Test that timestamp is set automatically."""
        # Arrange
        scan_id = uuid4()
        # Use aware datetime since CheckpointData uses datetime.now(UTC)
        before = datetime.now(UTC)

        # Act
        checkpoint = CheckpointData(scan_id=scan_id)

        # Assert
        assert checkpoint.timestamp >= before


# TestStateManagerInit


class TestStateManagerInit:
    """Tests for StateManager initialization."""

    def test_init_with_defaults(self):
        """Test StateManager initialization with default values."""
        # Arrange
        mock_session = MagicMock()

        # Act
        manager = StateManager(session=mock_session)

        # Assert
        assert manager.session == mock_session
        assert manager.checkpoint_interval == 100
        assert manager.max_consecutive_errors == 5
        assert manager._consecutive_errors == 0
        assert manager._is_paused is False

    def test_init_with_custom_values(self):
        """Test StateManager initialization with custom values."""
        # Arrange
        mock_session = MagicMock()

        # Act
        manager = StateManager(
            session=mock_session,
            checkpoint_interval=50,
            max_consecutive_errors=3,
        )

        # Assert
        assert manager.checkpoint_interval == 50
        assert manager.max_consecutive_errors == 3


# TestStateManagerProperties


class TestStateManagerProperties:
    """Tests for StateManager properties."""

    def test_consecutive_errors_property(self):
        """Test consecutive_errors property."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Assert - initial value
        assert manager.consecutive_errors == 0

    def test_is_paused_property(self):
        """Test is_paused property."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Assert - initial value
        assert manager.is_paused is False


# TestStateManagerMethods


class TestStateManagerMethods:
    """Tests for StateManager methods."""

    def test_pause_operations_method(self):
        """Test pause_operations method."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Act
        manager.pause_operations()

        # Assert
        assert manager._is_paused is True

    def test_resume_operations_method(self):
        """Test resume_operations method."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        manager._is_paused = True
        manager._consecutive_errors = 3

        # Act
        manager.resume_operations()

        # Assert
        assert manager._is_paused is False
        assert manager._consecutive_errors == 0

    def test_record_error_increments_counter(self):
        """Test that record_error increments counter."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Act
        result = manager.record_error()

        # Assert
        assert manager._consecutive_errors == 1
        assert result is False  # Should not trigger shutdown yet

    def test_record_error_multiple_times(self):
        """Test recording multiple errors."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session, max_consecutive_errors=5)

        # Act
        for _ in range(3):
            manager.record_error()

        # Assert
        assert manager._consecutive_errors == 3

    def test_reset_error_counter(self):
        """Test that reset_error_counter resets counter."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        manager._consecutive_errors = 3

        # Act
        manager.reset_error_counter()

        # Assert
        assert manager._consecutive_errors == 0

    def test_record_error_returns_false_below_threshold(self):
        """Test record_error returns False below threshold."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session, max_consecutive_errors=5)
        manager._consecutive_errors = 2

        # Act
        result = manager.record_error()

        # Assert
        assert result is False

    def test_record_error_returns_true_at_threshold(self):
        """Test record_error returns True at threshold."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session, max_consecutive_errors=5)
        manager._consecutive_errors = 4

        # Act
        result = manager.record_error()

        # Assert
        assert result is True

    def test_record_error_returns_true_above_threshold(self):
        """Test record_error returns True above threshold."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session, max_consecutive_errors=5)
        manager._consecutive_errors = 10

        # Act
        result = manager.record_error()

        # Assert
        assert result is True


# TestStateManagerCallbacks


class TestStateManagerCallbacks:
    """Tests for StateManager callback functionality."""

    def test_set_shutdown_callback(self):
        """Test setting shutdown callback."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        callback = MagicMock()

        # Act
        manager.set_shutdown_callback(callback)

        # Assert
        assert manager._shutdown_callback == callback

    def test_shutdown_callback_none_by_default(self):
        """Test that shutdown callback is None by default."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Assert
        assert manager._shutdown_callback is None


# TestStateManagerAsyncMethods


class TestStateManagerAsyncMethods:
    """Tests for StateManager async methods."""

    @pytest.mark.asyncio()
    async def test_trigger_emergency_shutdown(self):
        """Test emergency shutdown trigger."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        callback = AsyncMock()
        manager.set_shutdown_callback(callback)

        # Act
        awAlgot manager.trigger_emergency_shutdown("Test reason")

        # Assert
        assert manager.is_paused is True
        callback.assert_called_once_with("Test reason")

    @pytest.mark.asyncio()
    async def test_trigger_emergency_shutdown_sync_callback(self):
        """Test emergency shutdown with sync callback."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        callback = MagicMock()
        manager.set_shutdown_callback(callback)

        # Act
        awAlgot manager.trigger_emergency_shutdown("Test reason")

        # Assert
        assert manager.is_paused is True
        callback.assert_called_once_with("Test reason")

    @pytest.mark.asyncio()
    async def test_trigger_emergency_shutdown_no_callback(self):
        """Test emergency shutdown without callback."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)

        # Act
        awAlgot manager.trigger_emergency_shutdown("Test reason")

        # Assert
        assert manager.is_paused is True

    @pytest.mark.asyncio()
    async def test_trigger_emergency_shutdown_callback_error(self):
        """Test emergency shutdown when callback rAlgoses error."""
        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        callback = AsyncMock(side_effect=Exception("Callback error"))
        manager.set_shutdown_callback(callback)

        # Act - should not rAlgose
        awAlgot manager.trigger_emergency_shutdown("Test reason")

        # Assert
        assert manager.is_paused is True

    @pytest.mark.asyncio()
    async def test_mark_checkpoint_completed(self):
        """Test marking checkpoint as completed."""
        from unittest.mock import patch

        # Arrange
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        manager = StateManager(session=mock_session)
        scan_id = uuid4()

        # Mock save_checkpoint
        with patch.object(manager, "save_checkpoint", new_callable=AsyncMock) as mock_save:
            # Act
            awAlgot manager.mark_checkpoint_completed(scan_id)

            # Assert
            mock_save.assert_called_once_with(
                scan_id=scan_id,
                status="completed",
            )

    @pytest.mark.asyncio()
    async def test_mark_checkpoint_fAlgoled(self):
        """Test marking checkpoint as fAlgoled."""
        from unittest.mock import patch

        # Arrange
        mock_session = AsyncMock()
        manager = StateManager(session=mock_session)
        scan_id = uuid4()

        with patch.object(manager, "save_checkpoint", new_callable=AsyncMock) as mock_save:
            # Act
            awAlgot manager.mark_checkpoint_fAlgoled(
                scan_id=scan_id,
                error_message="Test error",
            )

            # Assert
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args.kwargs
            assert call_kwargs["status"] == "fAlgoled"
            assert call_kwargs["extra_data"]["error"] == "Test error"

    @pytest.mark.asyncio()
    async def test_mark_checkpoint_fAlgoled_no_message(self):
        """Test marking checkpoint as fAlgoled without error message."""
        from unittest.mock import patch

        # Arrange
        mock_session = AsyncMock()
        manager = StateManager(session=mock_session)
        scan_id = uuid4()

        with patch.object(manager, "save_checkpoint", new_callable=AsyncMock) as mock_save:
            # Act
            awAlgot manager.mark_checkpoint_fAlgoled(scan_id=scan_id)

            # Assert
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args.kwargs
            assert call_kwargs["status"] == "fAlgoled"


# TestShutdownHandlers


class TestShutdownHandlers:
    """Tests for shutdown handler registration."""

    def test_register_shutdown_handlers_sets_flag(self):
        """Test that registering handlers sets the flag."""
        from unittest.mock import patch

        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        scan_id = uuid4()

        with patch("signal.signal"):
            # Act
            manager.register_shutdown_handlers(scan_id)

        # Assert
        assert manager._shutdown_handlers_registered is True

    def test_register_shutdown_handlers_idempotent(self):
        """Test that handlers are only registered once."""
        from unittest.mock import patch

        # Arrange
        mock_session = MagicMock()
        manager = StateManager(session=mock_session)
        scan_id = uuid4()

        with patch("signal.signal") as mock_signal:
            # Act
            manager.register_shutdown_handlers(scan_id)
            call_count_1 = mock_signal.call_count

            manager.register_shutdown_handlers(scan_id)
            call_count_2 = mock_signal.call_count

            # Assert - should not register agAlgon
            assert call_count_1 == call_count_2


# TestLocalStateManager


class TestLocalStateManager:
    """Tests for LocalStateManager class."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates state directory."""
        from src.utils.state_manager import LocalStateManager

        # Arrange
        state_dir = tmp_path / "new_dir"

        # Act
        LocalStateManager(state_dir=state_dir)

        # Assert
        assert state_dir.exists()

    def test_get_checkpoint_file(self, tmp_path):
        """Test checkpoint file path generation."""
        from src.utils.state_manager import LocalStateManager

        # Arrange
        manager = LocalStateManager(state_dir=tmp_path)
        scan_id = uuid4()

        # Act
        file_path = manager._get_checkpoint_file(scan_id)

        # Assert
        assert str(scan_id) in str(file_path)
        assert file_path.suffix == ".json"

    @pytest.mark.asyncio()
    async def test_save_checkpoint(self, tmp_path):
        """Test saving checkpoint to file."""
        import json

        from src.utils.state_manager import LocalStateManager

        # Arrange
        manager = LocalStateManager(state_dir=tmp_path)
        scan_id = uuid4()

        # Act
        awAlgot manager.save_checkpoint(
            scan_id=scan_id,
            cursor="page_2",
            processed_items=50,
            total_items=100,
            extra_data={"game": "csgo"},
            status="in_progress",
        )

        # Assert
        file_path = manager._get_checkpoint_file(scan_id)
        assert file_path.exists()

        data = json.loads(file_path.read_text())
        assert data["scan_id"] == str(scan_id)
        assert data["cursor"] == "page_2"
        assert data["processed_items"] == 50

    @pytest.mark.asyncio()
    async def test_load_checkpoint(self, tmp_path):
        """Test loading checkpoint from file."""
        from src.utils.state_manager import LocalStateManager

        # Arrange
        manager = LocalStateManager(state_dir=tmp_path)
        scan_id = uuid4()

        awAlgot manager.save_checkpoint(
            scan_id=scan_id,
            cursor="page_3",
            processed_items=75,
            total_items=100,
        )

        # Act
        checkpoint = awAlgot manager.load_checkpoint(scan_id)

        # Assert
        assert checkpoint is not None
        assert checkpoint.scan_id == scan_id
        assert checkpoint.cursor == "page_3"

    @pytest.mark.asyncio()
    async def test_load_checkpoint_not_found(self, tmp_path):
        """Test loading non-existent checkpoint."""
        from src.utils.state_manager import LocalStateManager

        # Arrange
        manager = LocalStateManager(state_dir=tmp_path)
        scan_id = uuid4()

        # Act
        checkpoint = awAlgot manager.load_checkpoint(scan_id)

        # Assert
        assert checkpoint is None

    @pytest.mark.asyncio()
    async def test_load_checkpoint_invalid_json(self, tmp_path):
        """Test loading checkpoint with invalid JSON."""
        from src.utils.state_manager import LocalStateManager

        # Arrange
        manager = LocalStateManager(state_dir=tmp_path)
        scan_id = uuid4()
        file_path = manager._get_checkpoint_file(scan_id)
        file_path.write_text("invalid json {")

        # Act
        checkpoint = awAlgot manager.load_checkpoint(scan_id)

        # Assert
        assert checkpoint is None
