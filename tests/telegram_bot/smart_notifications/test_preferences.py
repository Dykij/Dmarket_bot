"""Unit tests for smart_notifications preferences module.

This module tests src/telegram_bot/smart_notifications/preferences.py covering:
- get_user_preferences function
- get_active_alerts function
- load_user_preferences function
- save_user_preferences function
- register_user function
- update_user_preferences function
- get_user_prefs function

Target: 15+ tests to achieve 70%+ coverage
"""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Module path constant for patching
PREFERENCES_MODULE = "src.telegram_bot.smart_notifications.preferences"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture()
def reset_preferences():
    """Fixture to reset preferences state before and after each test."""
    import src.telegram_bot.smart_notifications.preferences as prefs_module

    # Save original state
    original_user_prefs = prefs_module._user_preferences.copy()
    original_alerts = prefs_module._active_alerts.copy()

    # Clear state for test
    prefs_module._user_preferences.clear()
    prefs_module._active_alerts.clear()

    yield

    # Restore original state
    prefs_module._user_preferences = original_user_prefs
    prefs_module._active_alerts = original_alerts


@pytest.fixture()
def sample_preferences():
    """Fixture providing sample user preferences."""
    return {
        "12345": {
            "chat_id": 12345,
            "notifications_enabled": True,
            "digest_enabled": True,
            "digest_frequency": "daily",
            "registered_at": 1700000000.0,
        }
    }


@pytest.fixture()
def sample_alerts():
    """Fixture providing sample active alerts."""
    return {
        "12345": [
            {
                "id": "alert_123",
                "active": True,
                "type": "price_alert",
                "item_id": "item_abc",
            }
        ]
    }


# =============================================================================
# Tests for get_user_preferences
# =============================================================================


class TestGetUserPreferences:
    """Tests for get_user_preferences function."""

    def test_get_user_preferences_empty(self, reset_preferences):
        """Test getting empty user preferences."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
        )

        result = get_user_preferences()
        assert result == {}

    def test_get_user_preferences_with_data(
        self, reset_preferences, sample_preferences
    ):
        """Test getting user preferences with existing data."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
        )

        prefs_module._user_preferences.update(sample_preferences)

        result = get_user_preferences()
        assert result == sample_preferences
        assert "12345" in result


# =============================================================================
# Tests for get_active_alerts
# =============================================================================


class TestGetActiveAlerts:
    """Tests for get_active_alerts function."""

    def test_get_active_alerts_empty(self, reset_preferences):
        """Test getting empty active alerts."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
        )

        result = get_active_alerts()
        assert result == {}

    def test_get_active_alerts_with_data(self, reset_preferences, sample_alerts):
        """Test getting active alerts with existing data."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
        )

        prefs_module._active_alerts.update(sample_alerts)

        result = get_active_alerts()
        assert result == sample_alerts
        assert "12345" in result


# =============================================================================
# Tests for load_user_preferences
# =============================================================================


class TestLoadUserPreferences:
    """Tests for load_user_preferences function."""

    def test_load_preferences_file_not_exists(self, reset_preferences):
        """Test loading preferences when file doesn't exist."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
            get_user_preferences,
            load_user_preferences,
        )

        with patch(f"{PREFERENCES_MODULE}.SMART_ALERTS_FILE") as mock_file:
            mock_file.exists.return_value = False
            load_user_preferences()

        # Should not crash and should keep empty state
        assert get_user_preferences() == {}
        assert get_active_alerts() == {}

    def test_load_preferences_success(
        self, reset_preferences, sample_preferences, sample_alerts
    ):
        """Test successful preferences loading."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
            get_user_preferences,
            load_user_preferences,
        )

        data = {
            "user_preferences": sample_preferences,
            "active_alerts": sample_alerts,
        }

        with patch(f"{PREFERENCES_MODULE}.SMART_ALERTS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=json.dumps(data))):
                load_user_preferences()

        assert get_user_preferences() == sample_preferences
        assert get_active_alerts() == sample_alerts

    def test_load_preferences_json_decode_error(self, reset_preferences):
        """Test loading preferences with invalid JSON."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
            get_user_preferences,
            load_user_preferences,
        )

        with patch(f"{PREFERENCES_MODULE}.SMART_ALERTS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", mock_open(read_data="invalid json {")):
                load_user_preferences()

        # Should handle error and reset to empty state
        assert get_user_preferences() == {}
        assert get_active_alerts() == {}

    def test_load_preferences_os_error(self, reset_preferences):
        """Test loading preferences with OS error."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            load_user_preferences,
        )

        with patch(f"{PREFERENCES_MODULE}.SMART_ALERTS_FILE") as mock_file:
            mock_file.exists.return_value = True
            with patch("builtins.open", side_effect=OSError("File not accessible")):
                load_user_preferences()

        # Should handle error
        assert get_user_preferences() == {}


# =============================================================================
# Tests for save_user_preferences
# =============================================================================


class TestSaveUserPreferences:
    """Tests for save_user_preferences function."""

    def test_save_preferences_success(self, reset_preferences, sample_preferences):
        """Test successful preferences saving."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            save_user_preferences,
        )

        prefs_module._user_preferences.update(sample_preferences)

        mock_dir = MagicMock()
        mock_dir.exists.return_value = True

        with patch(f"{PREFERENCES_MODULE}.DATA_DIR", mock_dir):
            with patch("builtins.open", mock_open()):
                with patch("json.dump") as mock_json_dump:
                    save_user_preferences()
                    mock_json_dump.assert_called_once()

    def test_save_preferences_creates_directory(self, reset_preferences):
        """Test that save creates directory if not exists."""
        from src.telegram_bot.smart_notifications.preferences import (
            save_user_preferences,
        )

        mock_dir = MagicMock()
        mock_dir.exists.return_value = False

        with patch(f"{PREFERENCES_MODULE}.DATA_DIR", mock_dir):
            with patch("builtins.open", mock_open()):
                with patch("json.dump"):
                    save_user_preferences()

        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_save_preferences_os_error(self, reset_preferences):
        """Test save preferences with OS error."""
        from src.telegram_bot.smart_notifications.preferences import (
            save_user_preferences,
        )

        mock_dir = MagicMock()
        mock_dir.exists.return_value = True

        with patch(f"{PREFERENCES_MODULE}.DATA_DIR", mock_dir):
            with patch("builtins.open", side_effect=OSError("Cannot write")):
                # Should not raise exception
                save_user_preferences()


# =============================================================================
# Tests for register_user
# =============================================================================


class TestRegisterUser:
    """Tests for register_user function."""

    @pytest.mark.asyncio()
    async def test_register_new_user(self, reset_preferences):
        """Test registering a new user."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            register_user,
        )

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await register_user(12345)

        prefs = get_user_preferences()
        assert "12345" in prefs
        assert prefs["12345"]["chat_id"] == 12345

    @pytest.mark.asyncio()
    async def test_register_user_with_chat_id(self, reset_preferences):
        """Test registering a user with custom chat ID."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            register_user,
        )

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await register_user(12345, chat_id=67890)

        prefs = get_user_preferences()
        assert prefs["12345"]["chat_id"] == 67890

    @pytest.mark.asyncio()
    async def test_register_existing_user(self, reset_preferences, sample_preferences):
        """Test that re-registering an existing user doesn't overwrite data."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            register_user,
        )

        prefs_module._user_preferences.update(sample_preferences)

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await register_user(12345)

        prefs = get_user_preferences()
        # Should keep original data
        assert prefs["12345"] == sample_preferences["12345"]


# =============================================================================
# Tests for update_user_preferences
# =============================================================================


class TestUpdateUserPreferences:
    """Tests for update_user_preferences function."""

    @pytest.mark.asyncio()
    async def test_update_existing_user(self, reset_preferences, sample_preferences):
        """Test updating an existing user's preferences."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            update_user_preferences,
        )

        prefs_module._user_preferences.update(sample_preferences)

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await update_user_preferences(12345, {"digest_frequency": "weekly"})

        prefs = get_user_preferences()
        assert prefs["12345"]["digest_frequency"] == "weekly"

    @pytest.mark.asyncio()
    async def test_update_new_user(self, reset_preferences):
        """Test updating preferences for a new user (auto-registers)."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            update_user_preferences,
        )

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await update_user_preferences(99999, {"notifications_enabled": False})

        prefs = get_user_preferences()
        assert "99999" in prefs

    @pytest.mark.asyncio()
    async def test_update_nested_preferences(
        self, reset_preferences, sample_preferences
    ):
        """Test updating nested dictionary preferences."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            update_user_preferences,
        )

        # Add nested dict to preferences
        sample_preferences["12345"]["settings"] = {"theme": "dark"}
        prefs_module._user_preferences.update(sample_preferences)

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await update_user_preferences(12345, {"settings": {"theme": "light"}})

        prefs = get_user_preferences()
        assert prefs["12345"]["settings"]["theme"] == "light"


# =============================================================================
# Tests for get_user_prefs
# =============================================================================


class TestGetUserPrefs:
    """Tests for get_user_prefs function."""

    def test_get_existing_user_prefs(self, reset_preferences, sample_preferences):
        """Test getting preferences for an existing user."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_prefs,
        )

        prefs_module._user_preferences.update(sample_preferences)

        result = get_user_prefs(12345)
        assert result == sample_preferences["12345"]

    def test_get_nonexistent_user_prefs(self, reset_preferences):
        """Test getting preferences for a non-existent user."""
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_prefs,
        )

        result = get_user_prefs(99999)
        assert result == {}

    def test_get_user_prefs_type_conversion(
        self, reset_preferences, sample_preferences
    ):
        """Test that user_id is converted to string."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_prefs,
        )

        prefs_module._user_preferences.update(sample_preferences)

        # Test with int
        result1 = get_user_prefs(12345)
        assert result1 == sample_preferences["12345"]


# =============================================================================
# Edge Cases
# =============================================================================


class TestPreferencesEdgeCases:
    """Edge case tests for preferences module."""

    def test_preferences_with_special_characters(self, reset_preferences):
        """Test handling of special characters in preferences."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
        )

        special_prefs = {
            "12345": {
                "nickname": "User™ 日本語 🎮",
                "chat_id": 12345,
            }
        }
        prefs_module._user_preferences.update(special_prefs)

        result = get_user_preferences()
        assert result["12345"]["nickname"] == "User™ 日本語 🎮"

    @pytest.mark.asyncio()
    async def test_concurrent_updates(self, reset_preferences):
        """Test handling of concurrent preference updates."""
        import asyncio

        from src.telegram_bot.smart_notifications.preferences import (
            get_user_preferences,
            update_user_preferences,
        )

        with patch(f"{PREFERENCES_MODULE}.save_user_preferences"):
            await asyncio.gather(
                update_user_preferences(12345, {"key1": "value1"}),
                update_user_preferences(12346, {"key2": "value2"}),
                update_user_preferences(12347, {"key3": "value3"}),
            )

        prefs = get_user_preferences()
        assert "12345" in prefs
        assert "12346" in prefs
        assert "12347" in prefs
