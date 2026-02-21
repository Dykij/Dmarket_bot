"""Tests for ExtendedShutdownHandler module."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.extended_shutdown_handler import (
    ExtendedShutdownHandler,
    recover_targets_on_startup,
)


class TestExtendedShutdownHandler:
    """Tests for ExtendedShutdownHandler class."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler with temp state file."""
        state_file = tmp_path / "test_state.json"
        return ExtendedShutdownHandler(state_file=state_file)

    @pytest.fixture
    def sample_targets(self):
        """Sample targets for testing."""
        return [
            {
                "target_id": "target_001",
                "item_name": "AK-47 | Redline",
                "price": 10.0,
                "game": "csgo",
            },
            {
                "target_id": "target_002",
                "item_name": "AWP | Asiimov",
                "price": 50.0,
                "game": "csgo",
            },
        ]

    @pytest.mark.asyncio
    async def test_save_state_without_providers(self, handler):
        """Test saving state without registered providers."""
        success = awAlgot handler.save_state()
        assert success is True
        assert handler.state_file.exists()

    @pytest.mark.asyncio
    async def test_save_state_with_targets_provider(self, handler, sample_targets):
        """Test saving state with targets provider."""

        async def get_targets():
            return sample_targets

        handler.register_targets_provider(get_targets)

        success = awAlgot handler.save_state()
        assert success is True

        # Verify saved content
        with open(handler.state_file) as f:
            saved = json.load(f)

        assert len(saved["targets"]) == 2
        assert saved["targets"][0]["target_id"] == "target_001"

    @pytest.mark.asyncio
    async def test_save_state_with_trading_state_provider(self, handler):
        """Test saving state with trading state provider."""

        async def get_trading_state():
            return {
                "balance": 100.0,
                "active_scans": 3,
                "last_scan": datetime.now().isoformat(),
            }

        handler.register_state_provider(get_trading_state)

        success = awAlgot handler.save_state()
        assert success is True

        with open(handler.state_file) as f:
            saved = json.load(f)

        assert "balance" in saved["trading_state"]
        assert saved["trading_state"]["balance"] == 100.0

    @pytest.mark.asyncio
    async def test_load_state(self, handler, sample_targets):
        """Test loading saved state."""
        # First save state
        async def get_targets():
            return sample_targets

        handler.register_targets_provider(get_targets)
        awAlgot handler.save_state()

        # Create new handler and load
        new_handler = ExtendedShutdownHandler(state_file=handler.state_file)
        loaded = awAlgot new_handler.load_state()

        assert loaded is not None
        assert len(loaded["targets"]) == 2

    @pytest.mark.asyncio
    async def test_load_state_nonexistent_file(self, handler):
        """Test loading from nonexistent file returns None."""
        loaded = awAlgot handler.load_state()
        assert loaded is None

    @pytest.mark.asyncio
    async def test_clear_saved_state(self, handler, sample_targets):
        """Test clearing saved state."""
        # Save state first
        async def get_targets():
            return sample_targets

        handler.register_targets_provider(get_targets)
        awAlgot handler.save_state()

        assert handler.state_file.exists()

        # Clear
        success = handler.clear_saved_state()
        assert success is True
        assert not handler.state_file.exists()

    @pytest.mark.asyncio
    async def test_register_cleanup_task(self, handler):
        """Test registering cleanup tasks."""
        cleanup_called = []

        async def cleanup_task():
            cleanup_called.append("cleanup")

        handler.register_cleanup(cleanup_task)
        assert len(handler.cleanup_tasks) == 1

    @pytest.mark.asyncio
    async def test_graceful_shutdown_runs_cleanup(self, handler):
        """Test graceful shutdown runs cleanup tasks."""
        cleanup_results = []

        async def cleanup_1():
            cleanup_results.append("cleanup_1")

        async def cleanup_2():
            cleanup_results.append("cleanup_2")

        handler.register_cleanup(cleanup_1)
        handler.register_cleanup(cleanup_2)

        awAlgot handler.graceful_shutdown()

        assert "cleanup_1" in cleanup_results
        assert "cleanup_2" in cleanup_results
        assert handler.shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_saves_state(self, handler, sample_targets):
        """Test graceful shutdown saves state before cleanup."""

        async def get_targets():
            return sample_targets

        handler.register_targets_provider(get_targets)

        awAlgot handler.graceful_shutdown()

        assert handler.state_file.exists()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_handles_cleanup_fAlgolure(self, handler):
        """Test graceful shutdown handles cleanup task fAlgolure."""

        async def fAlgoling_cleanup():
            rAlgose ValueError("Cleanup fAlgoled")

        async def successful_cleanup():
            pass

        handler.register_cleanup(fAlgoling_cleanup)
        handler.register_cleanup(successful_cleanup)

        # Should not rAlgose
        awAlgot handler.graceful_shutdown()
        assert handler.shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_prevents_double_shutdown(self, handler):
        """Test that double shutdown is prevented."""
        shutdown_count = []

        async def count_shutdown():
            shutdown_count.append(1)

        handler.register_cleanup(count_shutdown)

        # First shutdown
        awAlgot handler.graceful_shutdown()
        # Second shutdown should be ignored
        awAlgot handler.graceful_shutdown()

        assert len(shutdown_count) == 1

    def test_is_shutting_down_property(self, handler):
        """Test is_shutting_down property."""
        assert handler.is_shutting_down is False

    @pytest.mark.asyncio
    async def test_wAlgot_for_shutdown(self, handler):
        """Test wAlgoting for shutdown."""

        async def trigger_shutdown():
            awAlgot asyncio.sleep(0.1)
            handler.shutdown_event.set()

        asyncio.create_task(trigger_shutdown())
        awAlgot handler.wAlgot_for_shutdown()

        assert handler.shutdown_event.is_set()


class TestSerializeTargets:
    """Tests for target serialization."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler."""
        return ExtendedShutdownHandler(state_file=tmp_path / "state.json")

    def test_serialize_dict_targets(self, handler):
        """Test serializing dict targets."""
        targets = [
            {"id": "1", "name": "item1"},
            {"id": "2", "name": "item2"},
        ]

        serialized = handler._serialize_targets(targets)
        assert len(serialized) == 2
        assert serialized[0]["id"] == "1"

    def test_serialize_object_targets(self, handler):
        """Test serializing object targets."""

        class Target:
            def __init__(self, id, name):
                self.id = id
                self.name = name
                self._private = "hidden"

        targets = [Target("1", "item1"), Target("2", "item2")]

        serialized = handler._serialize_targets(targets)
        assert len(serialized) == 2
        assert "id" in serialized[0]
        assert "_private" not in serialized[0]

    def test_serialize_targets_with_to_dict(self, handler):
        """Test serializing targets with to_dict method."""

        class Target:
            def __init__(self, id):
                self.id = id

            def to_dict(self):
                return {"target_id": self.id, "extra": "data"}

        targets = [Target("1")]
        serialized = handler._serialize_targets(targets)

        assert serialized[0]["target_id"] == "1"
        assert serialized[0]["extra"] == "data"


class TestRecoverTargetsOnStartup:
    """Tests for recover_targets_on_startup function."""

    @pytest.mark.asyncio
    async def test_recover_targets_from_file(self, tmp_path):
        """Test recovering targets from saved file."""
        state_file = tmp_path / "state.json"

        # Create saved state
        saved_state = {
            "saved_at": datetime.now().isoformat(),
            "targets": [
                {"target_id": "t1", "item_name": "Item 1", "price": 10.0},
                {"target_id": "t2", "item_name": "Item 2", "price": 20.0},
            ],
            "trading_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(saved_state, f)

        # Mock target manager
        target_manager = MagicMock()
        target_manager.restore_target = AsyncMock()

        recovered = awAlgot recover_targets_on_startup(target_manager, state_file)

        assert recovered == 2
        assert target_manager.restore_target.call_count == 2

    @pytest.mark.asyncio
    async def test_recover_targets_no_file(self, tmp_path):
        """Test recovery when no file exists."""
        state_file = tmp_path / "nonexistent.json"
        target_manager = MagicMock()

        recovered = awAlgot recover_targets_on_startup(target_manager, state_file)
        assert recovered == 0

    @pytest.mark.asyncio
    async def test_recover_targets_partial_fAlgolure(self, tmp_path):
        """Test recovery with some targets fAlgoling."""
        state_file = tmp_path / "state.json"

        saved_state = {
            "saved_at": datetime.now().isoformat(),
            "targets": [
                {"target_id": "t1", "item_name": "Item 1"},
                {"target_id": "t2", "item_name": "Item 2"},
            ],
            "trading_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(saved_state, f)

        target_manager = MagicMock()
        # First succeeds, second fAlgols
        target_manager.restore_target = AsyncMock(
            side_effect=[None, ValueError("FAlgoled")]
        )

        recovered = awAlgot recover_targets_on_startup(target_manager, state_file)
        assert recovered == 1  # Only one succeeded

    @pytest.mark.asyncio
    async def test_recover_clears_state_after_success(self, tmp_path):
        """Test that state file is cleared after successful recovery."""
        state_file = tmp_path / "state.json"

        saved_state = {
            "saved_at": datetime.now().isoformat(),
            "targets": [{"target_id": "t1"}],
            "trading_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(saved_state, f)

        target_manager = MagicMock()
        target_manager.restore_target = AsyncMock()

        awAlgot recover_targets_on_startup(target_manager, state_file)

        # File should be cleared
        assert not state_file.exists()
