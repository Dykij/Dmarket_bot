"""Unit tests for smart_notifications alerts module.

This module tests src/telegram_bot/smart_notifications/alerts.py covering:
- create_alert function
- deactivate_alert function
- get_user_alerts function

Target: 12+ tests to achieve 70%+ coverage
"""

from datetime import datetime
from unittest.mock import patch

import pytest

# Module path constant for patching
ALERTS_MODULE = "src.telegram_bot.smart_notifications.alerts"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture()
def reset_alerts():
    """Fixture to reset alerts state before and after each test."""
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
def sample_user_preferences():
    """Fixture providing sample user preferences."""
    return {
        "12345": {
            "chat_id": 12345,
            "notifications_enabled": True,
        }
    }


@pytest.fixture()
def sample_alerts():
    """Fixture providing sample active alerts."""
    return {
        "12345": [
            {
                "id": "alert_123",
                "user_id": "12345",
                "type": "price_alert",
                "item_id": "item_abc",
                "item_name": "AK-47 | Redline",
                "game": "csgo",
                "conditions": {"price": 25.0, "direction": "below"},
                "one_time": False,
                "created_at": 1700000000.0,
                "last_triggered": None,
                "trigger_count": 0,
                "active": True,
            }
        ]
    }


# =============================================================================
# Tests for create_alert
# =============================================================================


class TestCreateAlert:
    """Tests for create_alert function."""

    @pytest.mark.asyncio()
    async def test_create_alert_success(self, reset_alerts, sample_user_preferences):
        """Test successful alert creation."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert

        prefs_module._user_preferences.update(sample_user_preferences)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            alert_id = await create_alert(
                user_id=12345,
                alert_type="price_alert",
                item_id="item_abc",
                item_name="AK-47 | Redline",
                game="csgo",
                conditions={"price": 25.0, "direction": "below"},
            )

        assert alert_id is not None
        assert len(alert_id) > 0

    @pytest.mark.asyncio()
    async def test_create_alert_for_new_user(self, reset_alerts):
        """Test alert creation for a new user (auto-registers)."""
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import (
            get_active_alerts,
        )

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            alert_id = await create_alert(
                user_id=99999,
                alert_type="price_alert",
            )

        assert alert_id is not None
        alerts = get_active_alerts()
        assert "99999" in alerts
        assert len(alerts["99999"]) == 1

    @pytest.mark.asyncio()
    async def test_create_alert_with_all_parameters(
        self, reset_alerts, sample_user_preferences
    ):
        """Test alert creation with all parameters."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            alert_id = await create_alert(
                user_id=12345,
                alert_type="trend_alert",
                item_id="item_xyz",
                item_name="AWP | Dragon Lore",
                game="dota2",
                conditions={"trend": "up", "threshold": 5.0},
                one_time=True,
            )

        alerts = get_active_alerts()
        assert "12345" in alerts

        created_alert = alerts["12345"][0]
        assert created_alert["id"] == alert_id
        assert created_alert["type"] == "trend_alert"
        assert created_alert["item_id"] == "item_xyz"
        assert created_alert["item_name"] == "AWP | Dragon Lore"
        assert created_alert["game"] == "dota2"
        assert created_alert["one_time"] is True
        assert created_alert["active"] is True

    @pytest.mark.asyncio()
    async def test_create_alert_default_values(
        self, reset_alerts, sample_user_preferences
    ):
        """Test alert creation with default values."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            await create_alert(
                user_id=12345,
                alert_type="price_alert",
            )

        alerts = get_active_alerts()
        created_alert = alerts["12345"][0]

        assert created_alert["game"] == "csgo"  # Default value
        assert created_alert["conditions"] == {}
        assert created_alert["one_time"] is False
        assert created_alert["item_id"] is None
        assert created_alert["item_name"] is None

    @pytest.mark.asyncio()
    async def test_create_multiple_alerts(self, reset_alerts, sample_user_preferences):
        """Test creating multiple alerts for the same user."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            alert_id1 = await create_alert(user_id=12345, alert_type="price_alert")
            alert_id2 = await create_alert(user_id=12345, alert_type="trend_alert")
            alert_id3 = await create_alert(user_id=12345, alert_type="market_alert")

        alerts = get_active_alerts()
        assert len(alerts["12345"]) == 3
        assert alert_id1 != alert_id2 != alert_id3


# =============================================================================
# Tests for deactivate_alert
# =============================================================================


class TestDeactivateAlert:
    """Tests for deactivate_alert function."""

    @pytest.mark.asyncio()
    async def test_deactivate_alert_success(self, reset_alerts, sample_alerts):
        """Test successful alert deactivation."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import deactivate_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._active_alerts.update(sample_alerts)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            result = await deactivate_alert(12345, "alert_123")

        assert result is True
        alerts = get_active_alerts()
        assert alerts["12345"][0]["active"] is False

    @pytest.mark.asyncio()
    async def test_deactivate_alert_not_found(self, reset_alerts, sample_alerts):
        """Test deactivating a non-existent alert."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import deactivate_alert

        prefs_module._active_alerts.update(sample_alerts)

        result = await deactivate_alert(12345, "nonexistent_alert")

        assert result is False

    @pytest.mark.asyncio()
    async def test_deactivate_alert_user_not_found(self, reset_alerts):
        """Test deactivating alert for a non-existent user."""
        from src.telegram_bot.smart_notifications.alerts import deactivate_alert

        result = await deactivate_alert(99999, "alert_123")

        assert result is False

    @pytest.mark.asyncio()
    async def test_deactivate_correct_alert_multiple(self, reset_alerts):
        """Test deactivating the correct alert when user has multiple."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import deactivate_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        multiple_alerts = {
            "12345": [
                {"id": "alert_1", "active": True},
                {"id": "alert_2", "active": True},
                {"id": "alert_3", "active": True},
            ]
        }
        prefs_module._active_alerts.update(multiple_alerts)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            result = await deactivate_alert(12345, "alert_2")

        assert result is True
        alerts = get_active_alerts()
        assert alerts["12345"][0]["active"] is True
        assert alerts["12345"][1]["active"] is False  # Only this one deactivated
        assert alerts["12345"][2]["active"] is True


# =============================================================================
# Tests for get_user_alerts
# =============================================================================


class TestGetUserAlerts:
    """Tests for get_user_alerts function."""

    @pytest.mark.asyncio()
    async def test_get_user_alerts_success(self, reset_alerts, sample_alerts):
        """Test getting user's active alerts."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import get_user_alerts

        prefs_module._active_alerts.update(sample_alerts)

        alerts = await get_user_alerts(12345)

        assert len(alerts) == 1
        assert alerts[0]["id"] == "alert_123"

    @pytest.mark.asyncio()
    async def test_get_user_alerts_empty(self, reset_alerts):
        """Test getting alerts for user with no alerts."""
        from src.telegram_bot.smart_notifications.alerts import get_user_alerts

        alerts = await get_user_alerts(99999)

        assert alerts == []

    @pytest.mark.asyncio()
    async def test_get_user_alerts_only_active(self, reset_alerts):
        """Test that only active alerts are returned."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import get_user_alerts

        mixed_alerts = {
            "12345": [
                {"id": "active_1", "active": True},
                {"id": "inactive_1", "active": False},
                {"id": "active_2", "active": True},
            ]
        }
        prefs_module._active_alerts.update(mixed_alerts)

        alerts = await get_user_alerts(12345)

        assert len(alerts) == 2
        assert all(a["active"] for a in alerts)
        assert any(a["id"] == "active_1" for a in alerts)
        assert any(a["id"] == "active_2" for a in alerts)
        assert not any(a["id"] == "inactive_1" for a in alerts)


# =============================================================================
# Edge Cases
# =============================================================================


class TestAlertEdgeCases:
    """Edge case tests for alerts module."""

    @pytest.mark.asyncio()
    async def test_create_alert_uuid_uniqueness(
        self, reset_alerts, sample_user_preferences
    ):
        """Test that each alert gets a unique ID."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert

        prefs_module._user_preferences.update(sample_user_preferences)

        alert_ids = set()
        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            for _ in range(100):
                alert_id = await create_alert(user_id=12345, alert_type="price_alert")
                alert_ids.add(alert_id)

        # All 100 IDs should be unique
        assert len(alert_ids) == 100

    @pytest.mark.asyncio()
    async def test_create_alert_with_special_characters(
        self, reset_alerts, sample_user_preferences
    ):
        """Test creating alert with special characters in item name."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        special_name = "★ Karambit | 虎紋 ★ (Factory New) 🔥"

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            await create_alert(
                user_id=12345,
                alert_type="price_alert",
                item_name=special_name,
            )

        alerts = get_active_alerts()
        assert alerts["12345"][0]["item_name"] == special_name

    @pytest.mark.asyncio()
    async def test_alert_timestamp_set(self, reset_alerts, sample_user_preferences):
        """Test that created_at timestamp is set."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        before = datetime.now().timestamp()

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            await create_alert(user_id=12345, alert_type="price_alert")

        after = datetime.now().timestamp()

        alerts = get_active_alerts()
        created_at = alerts["12345"][0]["created_at"]

        assert before <= created_at <= after

    @pytest.mark.asyncio()
    async def test_alert_initial_state(self, reset_alerts, sample_user_preferences):
        """Test that alert has correct initial state."""
        import src.telegram_bot.smart_notifications.preferences as prefs_module
        from src.telegram_bot.smart_notifications.alerts import create_alert
        from src.telegram_bot.smart_notifications.preferences import get_active_alerts

        prefs_module._user_preferences.update(sample_user_preferences)

        with patch(f"{ALERTS_MODULE}.save_user_preferences"):
            await create_alert(user_id=12345, alert_type="price_alert")

        alerts = get_active_alerts()
        created_alert = alerts["12345"][0]

        assert created_alert["last_triggered"] is None
        assert created_alert["trigger_count"] == 0
        assert created_alert["active"] is True
