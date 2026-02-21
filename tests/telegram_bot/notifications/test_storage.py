"""Unit tests for notifications/storage.py module.

This module tests the AlertStorage class and storage functions:
- AlertStorage singleton pattern
- load_user_alerts
- save_user_alerts
- get_storage
- get_user_data
- get_cached_price
- set_cached_price
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.telegram_bot.notifications.storage import (
    AlertStorage,
    get_storage,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture()
def reset_singleton():
    """Reset AlertStorage singleton before and after each test."""
    AlertStorage._instance = None
    AlertStorage._initialized = False
    yield
    AlertStorage._instance = None
    AlertStorage._initialized = False


@pytest.fixture()
def temp_alerts_file(tmp_path):
    """Create a temporary alerts file."""
    alerts_file = tmp_path / "user_alerts.json"
    alerts_file.write_text("{}")
    return alerts_file


@pytest.fixture()
def sample_user_data():
    """Sample user data for testing."""
    return {
        "12345": {
            "alerts": [
                {
                    "id": "alert_1_12345",
                    "item_id": "item1",
                    "title": "Test Item",
                    "game": "csgo",
                    "type": "price_drop",
                    "threshold": 10.0,
                    "active": True,
                }
            ],
            "settings": {
                "enabled": True,
                "min_profit_percent": 5.0,
            },
        },
        "67890": {
            "alerts": [],
            "settings": {
                "enabled": False,
            },
        },
    }


# =============================================================================
# AlertStorage Singleton Tests
# =============================================================================
class TestAlertStorageSingleton:
    """Tests for AlertStorage singleton pattern."""

    def test_singleton_returns_same_instance(self, reset_singleton):
        """Test that AlertStorage returns the same instance."""
        storage1 = AlertStorage()
        storage2 = AlertStorage()

        assert storage1 is storage2

    def test_singleton_initialized_once(self, reset_singleton):
        """Test that AlertStorage is initialized only once."""
        storage1 = AlertStorage()
        original_alerts = storage1._user_alerts

        storage2 = AlertStorage()

        assert storage2._user_alerts is original_alerts

    def test_get_storage_returns_singleton(self, reset_singleton):
        """Test that get_storage returns AlertStorage singleton."""
        storage1 = get_storage()
        storage2 = get_storage()

        assert storage1 is storage2
        assert isinstance(storage1, AlertStorage)


# =============================================================================
# AlertStorage Initialization Tests
# =============================================================================
class TestAlertStorageInit:
    """Tests for AlertStorage initialization."""

    def test_init_creates_empty_user_alerts(self, reset_singleton):
        """Test that initialization creates empty user_alerts dict."""
        storage = AlertStorage()

        assert storage._user_alerts == {}

    def test_init_sets_alerts_file_path(self, reset_singleton):
        """Test that initialization sets alerts file path."""
        storage = AlertStorage()

        assert isinstance(storage._alerts_file, Path)
        assert "user_alerts.json" in str(storage._alerts_file)

    def test_init_creates_empty_prices_cache(self, reset_singleton):
        """Test that initialization creates empty prices cache."""
        storage = AlertStorage()

        assert storage._current_prices_cache == {}


# =============================================================================
# AlertStorage Properties Tests
# =============================================================================
class TestAlertStorageProperties:
    """Tests for AlertStorage properties."""

    def test_user_alerts_property(self, reset_singleton):
        """Test user_alerts property returns correct dict."""
        storage = AlertStorage()
        storage._user_alerts = {"test": "data"}

        assert storage.user_alerts == {"test": "data"}

    def test_alerts_file_property(self, reset_singleton):
        """Test alerts_file property returns correct path."""
        storage = AlertStorage()

        assert storage.alerts_file == storage._alerts_file

    def test_prices_cache_property(self, reset_singleton):
        """Test prices_cache property returns correct dict."""
        storage = AlertStorage()
        storage._current_prices_cache = {"item1": {"price": 10.0}}

        assert storage.prices_cache == {"item1": {"price": 10.0}}


# =============================================================================
# load_user_alerts Tests
# =============================================================================
class TestLoadUserAlerts:
    """Tests for load_user_alerts function and method."""

    def test_load_from_existing_file(self, reset_singleton, sample_user_data, tmp_path):
        """Test loading alerts from existing file."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "user_alerts.json"

        # Write sample data
        storage._alerts_file.write_text(json.dumps(sample_user_data))

        storage.load_user_alerts()

        assert "12345" in storage._user_alerts
        assert len(storage._user_alerts["12345"]["alerts"]) == 1

    def test_load_from_nonexistent_file(self, reset_singleton, tmp_path):
        """Test loading when file doesn't exist."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "nonexistent.json"

        storage.load_user_alerts()

        # Should not rAlgose error, alerts should remAlgon empty
        assert storage._user_alerts == {}

    def test_load_preserves_reference(
        self, reset_singleton, sample_user_data, tmp_path
    ):
        """Test that load preserves dictionary reference."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "user_alerts.json"
        storage._alerts_file.write_text(json.dumps(sample_user_data))

        original_ref = storage._user_alerts
        storage.load_user_alerts()

        # Should update in place, preserving reference
        assert storage._user_alerts is original_ref

    def test_load_with_invalid_json(self, reset_singleton, tmp_path):
        """Test loading with invalid JSON file."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "invalid.json"
        storage._alerts_file.write_text("{ invalid json }")

        # Should handle error gracefully
        try:
            storage.load_user_alerts()
        except json.JSONDecodeError:
            pass  # Expected behavior


# =============================================================================
# save_user_alerts Tests
# =============================================================================
class TestSaveUserAlerts:
    """Tests for save_user_alerts function and method."""

    def test_save_creates_file(self, reset_singleton, tmp_path):
        """Test that save creates alerts file."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "new_alerts.json"
        storage._user_alerts = {"12345": {"alerts": []}}

        # Ensure parent directory exists
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)

        storage.save_user_alerts()

        assert storage._alerts_file.exists()

    def test_save_writes_correct_data(
        self, reset_singleton, sample_user_data, tmp_path
    ):
        """Test that save writes correct data to file."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "alerts.json"
        storage._user_alerts = sample_user_data

        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)
        storage.save_user_alerts()

        # Read back and verify
        saved_data = json.loads(storage._alerts_file.read_text())
        assert saved_data == sample_user_data

    def test_save_handles_unicode(self, reset_singleton, tmp_path):
        """Test that save handles unicode characters."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "unicode_alerts.json"
        storage._user_alerts = {
            "12345": {
                "alerts": [
                    {
                        "title": "Тестовый предмет 测试项目",
                        "type": "price_drop",
                    }
                ]
            }
        }

        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)
        storage.save_user_alerts()

        # Read back and verify
        saved_data = json.loads(storage._alerts_file.read_text(encoding="utf-8"))
        assert "Тестовый предмет" in saved_data["12345"]["alerts"][0]["title"]


# =============================================================================
# get_user_data Tests
# =============================================================================
class TestGetUserData:
    """Tests for get_user_data method."""

    def test_get_existing_user_data(self, reset_singleton, sample_user_data):
        """Test getting data for existing user."""
        storage = AlertStorage()
        storage._user_alerts = sample_user_data

        user_data = storage.get_user_data(12345)

        assert user_data is not None
        assert len(user_data["alerts"]) == 1
        assert user_data["settings"]["enabled"] is True

    def test_get_nonexistent_user_creates_default(self, reset_singleton):
        """Test that getting non-existent user creates default data."""
        storage = AlertStorage()
        storage._user_alerts = {}

        user_data = storage.get_user_data(99999)

        # Should create default user data
        assert user_data is not None
        assert "alerts" in user_data
        assert "settings" in user_data

    def test_get_user_data_returns_reference(self, reset_singleton, sample_user_data):
        """Test that get_user_data returns reference (not copy)."""
        storage = AlertStorage()
        storage._user_alerts = sample_user_data

        user_data = storage.get_user_data(12345)
        user_data["alerts"].append({"id": "new_alert"})

        # Should modify original
        assert len(storage._user_alerts["12345"]["alerts"]) == 2


# =============================================================================
# Price Cache Tests
# =============================================================================
class TestPriceCache:
    """Tests for price caching methods."""

    def test_get_cached_price_existing(self, reset_singleton):
        """Test getting existing cached price."""
        storage = AlertStorage()
        storage._current_prices_cache = {
            "csgo:item1": {
                "price": 10.0,
                "timestamp": time.time(),
            }
        }

        cached = storage.get_cached_price("csgo:item1")

        assert cached is not None
        assert cached["price"] == 10.0

    def test_get_cached_price_nonexistent(self, reset_singleton):
        """Test getting non-existent cached price."""
        storage = AlertStorage()
        storage._current_prices_cache = {}

        cached = storage.get_cached_price("csgo:nonexistent")

        assert cached is None

    def test_set_cached_price(self, reset_singleton):
        """Test setting cached price."""
        storage = AlertStorage()
        storage._current_prices_cache = {}

        storage.set_cached_price("csgo:item1", 15.50, time.time())

        assert "csgo:item1" in storage._current_prices_cache
        assert storage._current_prices_cache["csgo:item1"]["price"] == 15.50
        assert "timestamp" in storage._current_prices_cache["csgo:item1"]

    def test_cache_update_overwrites(self, reset_singleton):
        """Test that setting cache overwrites old value."""
        storage = AlertStorage()
        storage._current_prices_cache = {
            "csgo:item1": {
                "price": 10.0,
                "timestamp": time.time() - 100,
            }
        }

        storage.set_cached_price("csgo:item1", 12.0, time.time())

        assert storage._current_prices_cache["csgo:item1"]["price"] == 12.0


# =============================================================================
# Edge Cases
# =============================================================================
class TestStorageEdgeCases:
    """Tests for storage edge cases."""

    def test_empty_file(self, reset_singleton, tmp_path):
        """Test handling empty JSON file."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "empty.json"
        storage._alerts_file.write_text("")

        try:
            storage.load_user_alerts()
        except json.JSONDecodeError:
            pass  # Expected for empty file

    def test_large_user_data(self, reset_singleton, tmp_path):
        """Test handling large user data."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "large.json"

        # Create large dataset
        large_data = {}
        for i in range(1000):
            large_data[str(i)] = {
                "alerts": [{"id": f"alert_{j}"} for j in range(10)],
                "settings": {"enabled": True},
            }

        storage._user_alerts = large_data
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)
        storage.save_user_alerts()

        # Load back
        storage2 = AlertStorage()
        storage2._alerts_file = storage._alerts_file
        storage2.load_user_alerts()

        assert len(storage2._user_alerts) == 1000

    def test_concurrent_access(self, reset_singleton):
        """Test that singleton handles concurrent access."""
        import threading

        instances = []

        def get_instance():
            instances.append(AlertStorage())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

    def test_special_characters_in_user_id(self, reset_singleton):
        """Test handling special characters in user ID."""
        storage = AlertStorage()

        # User ID with string representation
        user_data = storage.get_user_data(-123)  # Negative user ID

        assert user_data is not None

    def test_nested_data_structure(self, reset_singleton, tmp_path):
        """Test handling deeply nested data."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "nested.json"

        nested_data = {
            "12345": {
                "alerts": [
                    {"id": "alert1", "metadata": {"nested": {"deep": {"value": 42}}}}
                ],
                "settings": {},
            }
        }

        storage._user_alerts = nested_data
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)
        storage.save_user_alerts()

        # Load back
        storage.load_user_alerts()

        assert (
            storage._user_alerts["12345"]["alerts"][0]["metadata"]["nested"]["deep"][
                "value"
            ]
            == 42
        )


# =============================================================================
# Integration Tests
# =============================================================================
class TestStorageIntegration:
    """Integration tests for storage module."""

    def test_full_crud_lifecycle(self, reset_singleton, tmp_path):
        """Test full CRUD lifecycle: Create, Read, Update, Delete."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "lifecycle.json"
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)

        # Create
        user_data = storage.get_user_data(12345)
        user_data["alerts"].append(
            {
                "id": "test_alert",
                "item_id": "item1",
                "type": "price_drop",
            }
        )
        storage.save_user_alerts()

        # Read
        storage.load_user_alerts()
        loaded_data = storage.get_user_data(12345)
        assert len(loaded_data["alerts"]) >= 1

        # Update
        loaded_data["alerts"][0]["type"] = "price_rise"
        storage.save_user_alerts()

        storage.load_user_alerts()
        updated_data = storage.get_user_data(12345)
        assert updated_data["alerts"][0]["type"] == "price_rise"

        # Delete
        updated_data["alerts"] = []
        storage.save_user_alerts()

        storage.load_user_alerts()
        deleted_data = storage.get_user_data(12345)
        assert len(deleted_data["alerts"]) == 0

    def test_multiple_users_isolation(self, reset_singleton, tmp_path):
        """Test that multiple users' data is isolated."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "multi_user.json"
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)

        # Create data for multiple users
        user1_data = storage.get_user_data(111)
        user1_data["alerts"].append({"id": "user1_alert"})

        user2_data = storage.get_user_data(222)
        user2_data["alerts"].append({"id": "user2_alert"})

        storage.save_user_alerts()
        storage.load_user_alerts()

        # Verify isolation
        assert storage.get_user_data(111)["alerts"][0]["id"] == "user1_alert"
        assert storage.get_user_data(222)["alerts"][0]["id"] == "user2_alert"

    def test_cache_and_alerts_coexistence(self, reset_singleton, tmp_path):
        """Test that cache and alerts can coexist."""
        storage = AlertStorage()
        storage._alerts_file = tmp_path / "coexist.json"
        storage._alerts_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up alerts
        user_data = storage.get_user_data(12345)
        user_data["alerts"].append({"id": "alert1"})
        storage.save_user_alerts()

        # Set up cache
        storage.set_cached_price("csgo:item1", 10.0, time.time())
        storage.set_cached_price("csgo:item2", 20.0, time.time())

        # Both should work independently
        assert len(storage.get_user_data(12345)["alerts"]) >= 1
        assert storage.get_cached_price("csgo:item1")["price"] == 10.0

        # Alerts save shouldn't affect cache
        storage.save_user_alerts()
        assert storage.get_cached_price("csgo:item1")["price"] == 10.0
