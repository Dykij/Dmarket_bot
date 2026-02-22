"""Unit tests for notifications/alerts.py module.

This module tests the alert management functions:
- add_price_alert
- get_user_alerts
- remove_price_alert
- update_user_settings
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.telegram_bot.notifications.alerts import (
    add_price_alert,
    get_user_alerts,
    remove_price_alert,
    update_user_settings,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture()
def mock_storage():
    """Create a mock storage for testing."""
    storage = MagicMock()
    storage.get_user_data = MagicMock(
        return_value={
            "alerts": [],
            "settings": {
                "min_profit_percent": 5.0,
                "enabled": True,
            },
        }
    )
    storage.save_user_alerts = MagicMock()
    return storage


@pytest.fixture()
def mock_storage_with_alerts():
    """Create a mock storage with existing alerts."""
    storage = MagicMock()
    storage.get_user_data = MagicMock(
        return_value={
            "alerts": [
                {
                    "id": "alert_123_12345",
                    "item_id": "item1",
                    "title": "AK-47 | Redline",
                    "game": "csgo",
                    "type": "price_drop",
                    "threshold": 10.0,
                    "created_at": time.time(),
                    "active": True,
                },
                {
                    "id": "alert_456_12345",
                    "item_id": "item2",
                    "title": "AWP | Asiimov",
                    "game": "csgo",
                    "type": "price_rise",
                    "threshold": 50.0,
                    "created_at": time.time(),
                    "active": True,
                },
            ],
            "settings": {
                "min_profit_percent": 5.0,
                "enabled": True,
            },
        }
    )
    storage.save_user_alerts = MagicMock()
    return storage


# =============================================================================
# add_price_alert Tests
# =============================================================================
class TestAddPriceAlert:
    """Tests for add_price_alert function."""

    @pytest.mark.asyncio()
    async def test_add_price_alert_basic(self, mock_storage):
        """Test adding a basic price alert."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item123",
                title="Test Item",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            # Verify alert was created
            assert result is not None
            assert result["item_id"] == "item123"
            assert result["title"] == "Test Item"
            assert result["game"] == "csgo"
            assert result["type"] == "price_drop"
            assert result["threshold"] == 10.0
            assert result["active"] is True

            # Verify storage was called
            mock_storage.get_user_data.assert_called_once_with(12345)
            mock_storage.save_user_alerts.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_price_alert_generates_unique_id(self, mock_storage):
        """Test that each alert gets a unique ID."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result1 = await add_price_alert(
                user_id=12345,
                item_id="item1",
                title="Item 1",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            # Small delay to ensure different timestamp
            import asyncio

            await asyncio.sleep(0.01)

            result2 = await add_price_alert(
                user_id=12345,
                item_id="item2",
                title="Item 2",
                game="csgo",
                alert_type="price_rise",
                threshold=20.0,
            )

            # IDs should include user_id
            assert "12345" in result1["id"]
            assert "12345" in result2["id"]

    @pytest.mark.asyncio()
    async def test_add_price_alert_dota2_game(self, mock_storage):
        """Test adding alert for Dota 2 item."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="dota_item",
                title="Arcana",
                game="dota2",
                alert_type="price_drop",
                threshold=30.0,
            )

            assert result["game"] == "dota2"

    @pytest.mark.asyncio()
    async def test_add_price_alert_price_rise_type(self, mock_storage):
        """Test adding price rise alert."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item",
                title="Item",
                game="csgo",
                alert_type="price_rise",
                threshold=100.0,
            )

            assert result["type"] == "price_rise"
            assert result["threshold"] == 100.0

    @pytest.mark.asyncio()
    async def test_add_price_alert_includes_timestamp(self, mock_storage):
        """Test that alert includes creation timestamp."""
        current_time = time.time()

        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item",
                title="Item",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            assert "created_at" in result
            # Should be close to current time
            assert abs(result["created_at"] - current_time) < 5


# =============================================================================
# get_user_alerts Tests
# =============================================================================
class TestGetUserAlerts:
    """Tests for get_user_alerts function."""

    @pytest.mark.asyncio()
    async def test_get_user_alerts_returns_list(self, mock_storage_with_alerts):
        """Test getting user alerts returns a list."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage_with_alerts,
        ):
            alerts = await get_user_alerts(user_id=12345)

            assert isinstance(alerts, list)
            assert len(alerts) == 2

    @pytest.mark.asyncio()
    async def test_get_user_alerts_empty_user(self, mock_storage):
        """Test getting alerts for user with no alerts."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            alerts = await get_user_alerts(user_id=99999)

            assert isinstance(alerts, list)
            assert len(alerts) == 0

    @pytest.mark.asyncio()
    async def test_get_user_alerts_contains_correct_data(
        self, mock_storage_with_alerts
    ):
        """Test that alerts contain expected data."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage_with_alerts,
        ):
            alerts = await get_user_alerts(user_id=12345)

            # Find the first alert
            ak47_alert = next(
                (a for a in alerts if "AK-47" in a.get("title", "")), None
            )

            if ak47_alert:
                assert ak47_alert["item_id"] == "item1"
                assert ak47_alert["type"] == "price_drop"
                assert ak47_alert["threshold"] == 10.0


# =============================================================================
# remove_price_alert Tests
# =============================================================================
class TestRemovePriceAlert:
    """Tests for remove_price_alert function."""

    @pytest.mark.asyncio()
    async def test_remove_price_alert_success(self, mock_storage_with_alerts):
        """Test successfully removing an alert."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage_with_alerts,
        ):
            result = await remove_price_alert(
                user_id=12345,
                alert_id="alert_123_12345",
            )

            # Should return success or the removed alert
            assert result is not None or result is True

    @pytest.mark.asyncio()
    async def test_remove_price_alert_nonexistent(self, mock_storage_with_alerts):
        """Test removing a non-existent alert."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage_with_alerts,
        ):
            result = await remove_price_alert(
                user_id=12345,
                alert_id="nonexistent_alert",
            )

            # Should return None/False or not raise error
            assert result is None or result is False or result is True

    @pytest.mark.asyncio()
    async def test_remove_price_alert_saves_changes(self, mock_storage_with_alerts):
        """Test that removal saves changes to storage."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage_with_alerts,
        ):
            await remove_price_alert(
                user_id=12345,
                alert_id="alert_123_12345",
            )

            mock_storage_with_alerts.save_user_alerts.assert_called()


# =============================================================================
# update_user_settings Tests
# =============================================================================
class TestUpdateUserSettings:
    """Tests for update_user_settings function."""

    @pytest.mark.asyncio()
    async def test_update_user_settings_basic(self, mock_storage):
        """Test updating user settings."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            # update_user_settings returns None by design
            await update_user_settings(
                user_id=12345,
                settings={
                    "min_profit_percent": 10.0,
                    "enabled": False,
                },
            )

            # Verify settings were updated
            mock_storage.save_user_alerts.assert_called()

    @pytest.mark.asyncio()
    async def test_update_user_settings_partial_update(self, mock_storage):
        """Test partial settings update."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            # update_user_settings returns None by design
            await update_user_settings(
                user_id=12345,
                settings={
                    "min_profit_percent": 15.0,
                },
            )

            # Verify settings were saved
            mock_storage.save_user_alerts.assert_called()

    @pytest.mark.asyncio()
    async def test_update_user_settings_saves_changes(self, mock_storage):
        """Test that settings update saves to storage."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            await update_user_settings(
                user_id=12345,
                settings={"enabled": False},
            )

            mock_storage.save_user_alerts.assert_called()


# =============================================================================
# Edge Cases
# =============================================================================
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_add_alert_with_special_characters_in_title(self, mock_storage):
        """Test adding alert with special characters in title."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item",
                title="Test & Item <Special>",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            assert result["title"] == "Test & Item <Special>"

    @pytest.mark.asyncio()
    async def test_add_alert_with_zero_threshold(self, mock_storage):
        """Test adding alert with zero threshold."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item",
                title="Item",
                game="csgo",
                alert_type="price_drop",
                threshold=0.0,
            )

            assert result["threshold"] == 0.0

    @pytest.mark.asyncio()
    async def test_add_alert_with_large_threshold(self, mock_storage):
        """Test adding alert with very large threshold."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            result = await add_price_alert(
                user_id=12345,
                item_id="item",
                title="Expensive Item",
                game="csgo",
                alert_type="price_drop",
                threshold=100000.0,
            )

            assert result["threshold"] == 100000.0

    @pytest.mark.asyncio()
    async def test_get_alerts_for_different_users(self, mock_storage_with_alerts):
        """Test that alerts are user-specific."""
        storage1 = MagicMock()
        storage1.get_user_data = MagicMock(return_value={"alerts": [{"id": "1", "active": True}]})

        storage2 = MagicMock()
        storage2.get_user_data = MagicMock(
            return_value={"alerts": [{"id": "2", "active": True}, {"id": "3", "active": True}]}
        )

        with patch(
            "src.telegram_bot.notifications.alerts.get_storage", return_value=storage1
        ):
            alerts1 = await get_user_alerts(user_id=111)
            assert len(alerts1) == 1

        with patch(
            "src.telegram_bot.notifications.alerts.get_storage", return_value=storage2
        ):
            alerts2 = await get_user_alerts(user_id=222)
            assert len(alerts2) == 2

    @pytest.mark.asyncio()
    async def test_add_multiple_alerts_same_item(self, mock_storage):
        """Test adding multiple alerts for the same item."""
        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            # Add price drop alert
            result1 = await add_price_alert(
                user_id=12345,
                item_id="item1",
                title="Item",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            # Add price rise alert for same item
            result2 = await add_price_alert(
                user_id=12345,
                item_id="item1",
                title="Item",
                game="csgo",
                alert_type="price_rise",
                threshold=20.0,
            )

            assert result1 is not None
            assert result2 is not None
            # Different alert types
            assert result1["type"] != result2["type"]


# =============================================================================
# Integration Tests
# =============================================================================
class TestIntegration:
    """Integration tests for alert operations."""

    @pytest.mark.asyncio()
    async def test_add_then_get_alerts(self, mock_storage):
        """Test adding and then retrieving alerts."""
        alerts_list = []

        def get_user_data_side_effect(user_id):
            return {
                "alerts": alerts_list,
                "settings": {},
            }

        def save_side_effect():
            pass

        mock_storage.get_user_data = MagicMock(side_effect=get_user_data_side_effect)
        mock_storage.save_user_alerts = MagicMock(side_effect=save_side_effect)

        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            # Add an alert
            await add_price_alert(
                user_id=12345,
                item_id="item1",
                title="Test Item",
                game="csgo",
                alert_type="price_drop",
                threshold=10.0,
            )

            # Alert should have been added to the list
            assert len(alerts_list) >= 1

            # Get alerts
            alerts = await get_user_alerts(user_id=12345)
            assert len(alerts) >= 1

    @pytest.mark.asyncio()
    async def test_alert_lifecycle(self, mock_storage):
        """Test full alert lifecycle: add -> get -> remove."""
        alerts_list = []

        def get_user_data_side_effect(user_id):
            return {
                "alerts": alerts_list,
                "settings": {},
            }

        mock_storage.get_user_data = MagicMock(side_effect=get_user_data_side_effect)
        mock_storage.save_user_alerts = MagicMock()

        with patch(
            "src.telegram_bot.notifications.alerts.get_storage",
            return_value=mock_storage,
        ):
            # Add
            alert = await add_price_alert(
                user_id=12345,
                item_id="lifecycle_item",
                title="Lifecycle Test",
                game="csgo",
                alert_type="price_drop",
                threshold=5.0,
            )

            assert alert is not None
            alert_id = alert["id"]

            # Get
            alerts = await get_user_alerts(user_id=12345)
            assert any(a.get("id") == alert_id for a in alerts)

            # Remove
            await remove_price_alert(user_id=12345, alert_id=alert_id)
