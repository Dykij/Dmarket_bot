"""Unit tests for src/telegram_bot/smart_notifications/ module.

Tests for smart notification functionality including:
- Constants
- User preferences
- Throttling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSmartNotificationsConstants:
    """Tests for smart notification constants."""

    def test_notification_types_defined(self):
        """Test notification types are defined."""
        from src.telegram_bot.smart_notifications.constants import NOTIFICATION_TYPES

        assert isinstance(NOTIFICATION_TYPES, dict)
        assert "market_opportunity" in NOTIFICATION_TYPES
        assert "price_alert" in NOTIFICATION_TYPES

    def test_default_user_preferences_defined(self):
        """Test default user preferences are defined."""
        from src.telegram_bot.smart_notifications.constants import (
            DEFAULT_USER_PREFERENCES,
        )

        assert isinstance(DEFAULT_USER_PREFERENCES, dict)
        assert "enabled" in DEFAULT_USER_PREFERENCES
        assert "notifications" in DEFAULT_USER_PREFERENCES

    def test_default_cooldown_defined(self):
        """Test default cooldowns are defined."""
        from src.telegram_bot.smart_notifications.constants import DEFAULT_COOLDOWN

        assert isinstance(DEFAULT_COOLDOWN, dict)
        assert "price_alert" in DEFAULT_COOLDOWN
        assert DEFAULT_COOLDOWN["price_alert"] > 0


class TestSmartNotificationsUtils:
    """Tests for utility functions."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api._request = AsyncMock()
        return api

    @pytest.mark.asyncio()
    async def test_get_market_data_for_items_success(self, mock_api):
        """Test successful market data retrieval."""
        from src.telegram_bot.smart_notifications.utils import get_market_data_for_items

        mock_api._request = AsyncMock(
            return_value={
                "items": [
                    {"itemId": "item_1", "price": {"USD": "1000"}, "title": "Item 1"},
                    {"itemId": "item_2", "price": {"USD": "2000"}, "title": "Item 2"},
                ]
            }
        )

        result = await get_market_data_for_items(mock_api, ["item_1", "item_2"], "csgo")

        assert "item_1" in result
        assert "item_2" in result
        assert result["item_1"]["title"] == "Item 1"

    @pytest.mark.asyncio()
    async def test_get_market_data_for_items_empty_ids(self, mock_api):
        """Test with empty item IDs list."""
        from src.telegram_bot.smart_notifications.utils import get_market_data_for_items

        result = await get_market_data_for_items(mock_api, [], "csgo")

        assert result == {}
        mock_api._request.assert_not_called()

    @pytest.mark.asyncio()
    async def test_get_market_data_for_items_api_error(self, mock_api):
        """Test handling of API error."""
        from src.telegram_bot.smart_notifications.utils import get_market_data_for_items
        from src.utils.exceptions import APIError

        mock_api._request = AsyncMock(side_effect=APIError("API Error"))

        result = await get_market_data_for_items(mock_api, ["item_1"], "csgo")

        assert result == {}

    @pytest.mark.asyncio()
    async def test_get_market_data_batching(self, mock_api):
        """Test that large item lists are processed in batches."""
        from src.telegram_bot.smart_notifications.utils import get_market_data_for_items

        # Create 100 item IDs (should require 2 batches of 50)
        item_ids = [f"item_{i}" for i in range(100)]

        mock_api._request = AsyncMock(return_value={"items": []})

        await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Should be called twice (2 batches)
        assert mock_api._request.call_count == 2


class TestSmartNotificationsPreferences:
    """Tests for user preferences management."""

    def test_get_user_preferences(self):
        """Test getting user preferences."""
        from src.telegram_bot.smart_notifications.preferences import (
            _user_preferences,
            get_user_preferences,
        )

        # Clear and set test data
        _user_preferences.clear()
        _user_preferences["123"] = {"enabled": True, "min_profit": 5.0}

        result = get_user_preferences()

        assert "123" in result
        assert result["123"]["enabled"] is True

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        from src.telegram_bot.smart_notifications.preferences import (
            _active_alerts,
            get_active_alerts,
        )

        # Clear and set test data
        _active_alerts.clear()
        _active_alerts["123"] = [
            {"type": "price_alert", "active": True, "item_id": "item_1"}
        ]

        result = get_active_alerts()

        assert "123" in result
        assert len(result["123"]) == 1

    def test_save_user_preferences_no_args(self):
        """Test saving all user preferences."""
        from src.telegram_bot.smart_notifications.preferences import (
            _user_preferences,
            save_user_preferences,
        )

        _user_preferences.clear()
        _user_preferences["456"] = {"enabled": True}

        # Should not raise (saves all preferences to file)
        save_user_preferences()

    def test_load_user_preferences_no_args(self):
        """Test loading all user preferences."""
        from src.telegram_bot.smart_notifications.preferences import (
            load_user_preferences,
        )

        # Should not raise (loads from file)
        load_user_preferences()


class TestSmartNotificationsThrottling:
    """Tests for notification throttling."""

    @pytest.mark.asyncio()
    async def test_should_throttle_notification(self):
        """Test throttling function exists and is callable."""
        from src.telegram_bot.smart_notifications.throttling import (
            should_throttle_notification,
        )

        assert callable(should_throttle_notification)

    @pytest.mark.asyncio()
    async def test_record_notification(self):
        """Test recording notification function exists."""
        from src.telegram_bot.smart_notifications.throttling import (
            record_notification,
        )

        assert callable(record_notification)


class TestSmartNotificationsSenders:
    """Tests for notification sending functions."""

    @pytest.fixture()
    def mock_bot(self):
        """Create mock Telegram Bot."""
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=MagicMock())
        return bot

    @pytest.fixture()
    def mock_notification_queue(self):
        """Create mock notification queue."""
        queue = MagicMock()
        queue.enqueue = AsyncMock()
        return queue

    @pytest.mark.asyncio()
    async def test_send_price_alert_notification(self, mock_bot):
        """Test sending price alert notification."""
        from src.telegram_bot.smart_notifications.senders import (
            send_price_alert_notification,
        )

        alert = {
            "item_name": "AK-47 | Redline",
            "item_id": "item_123",
            "game": "csgo",
            "conditions": {"price": 15.0, "condition": "below"},
        }
        item_data = {
            "itemId": "item_123",
            "title": "AK-47 | Redline",
            "price": {"USD": "1200"},
        }
        user_prefs = {"chat_id": 123456, "enabled": True}

        with patch(
            "src.telegram_bot.smart_notifications.senders.format_market_item",
            return_value="Item info",
        ), patch(
            "src.telegram_bot.smart_notifications.senders.record_notification"
        ):
            await send_price_alert_notification(
                mock_bot, 123456, alert, item_data, 12.0, user_prefs
            )

            mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_market_opportunity_notification(self, mock_bot):
        """Test sending market opportunity notification."""
        from src.telegram_bot.smart_notifications.senders import (
            send_market_opportunity_notification,
        )

        opportunity = {
            "item_name": "AWP | Asiimov",
            "buy_price": 50.0,
            "sell_price": 55.0,
            "profit": 3.5,
            "profit_percent": 7.0,
        }
        user_prefs = {"chat_id": 789012, "enabled": True}

        with patch(
            "src.telegram_bot.smart_notifications.senders.format_opportunities",
            return_value="Opportunity",
        ), patch(
            "src.telegram_bot.smart_notifications.senders.record_notification"
        ):
            await send_market_opportunity_notification(
                mock_bot, 789012, opportunity, user_prefs
            )

            mock_bot.send_message.assert_called_once()


class TestSmartNotificationsCheckers:
    """Tests for notification checker functions."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api._request = AsyncMock()
        return api

    @pytest.fixture()
    def mock_bot(self):
        """Create mock Telegram Bot."""
        bot = MagicMock()
        bot.send_message = AsyncMock(return_value=MagicMock())
        return bot

    @pytest.mark.asyncio()
    async def test_check_price_alerts_no_active_alerts(self, mock_api, mock_bot):
        """Test checking price alerts with no active alerts."""
        from src.telegram_bot.smart_notifications.checkers import check_price_alerts
        from src.telegram_bot.smart_notifications.preferences import (
            _active_alerts,
            _user_preferences,
        )

        _active_alerts.clear()
        _user_preferences.clear()

        # Should not raise
        await check_price_alerts(mock_api, mock_bot)

        # No API calls should be made
        mock_api._request.assert_not_called()

    @pytest.mark.asyncio()
    async def test_check_price_alerts_user_disabled(self, mock_api, mock_bot):
        """Test checking price alerts for disabled user."""
        from src.telegram_bot.smart_notifications.checkers import check_price_alerts
        from src.telegram_bot.smart_notifications.preferences import (
            _active_alerts,
            _user_preferences,
        )

        _active_alerts.clear()
        _user_preferences.clear()

        # Set up alert for disabled user
        _active_alerts["123"] = [
            {"type": "price_alert", "active": True, "item_id": "item_1", "game": "csgo"}
        ]
        _user_preferences["123"] = {"enabled": False}

        await check_price_alerts(mock_api, mock_bot)

        # Should skip disabled users
        mock_api._request.assert_not_called()


class TestSmartNotificationsAlerts:
    """Tests for alert management."""

    def test_import_alerts_module(self):
        """Test alerts module can be imported."""
        from src.telegram_bot.smart_notifications.alerts import (
            create_alert,
            deactivate_alert,
            get_user_alerts,
        )

        assert callable(create_alert)
        assert callable(deactivate_alert)
        assert callable(get_user_alerts)


class TestSmartNotificationsHandlers:
    """Tests for Telegram handlers."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context."""
        context = MagicMock()
        context.user_data = {}
        return context

    def test_import_handlers_module(self):
        """Test handlers module can be imported."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
            register_notification_handlers,
        )

        assert callable(handle_notification_callback)
        assert callable(register_notification_handlers)


class TestSmartNotificationsIntegration:
    """Integration tests for smart notifications."""

    def test_preferences_and_alerts_state(self):
        """Test preferences and alerts state management."""
        from src.telegram_bot.smart_notifications.preferences import (
            _active_alerts,
            _user_preferences,
            get_active_alerts,
            get_user_preferences,
        )

        # Clear state
        _active_alerts.clear()
        _user_preferences.clear()

        # Set up user preferences
        _user_preferences["integration_user"] = {
            "enabled": True,
            "min_profit": 5.0,
            "chat_id": 123456,
        }

        # Create alert
        _active_alerts["integration_user"] = [
            {
                "type": "price_alert",
                "active": True,
                "item_id": "test_item",
                "item_name": "Test Item",
                "game": "csgo",
                "conditions": {"price": 10.0, "condition": "below"},
            }
        ]

        # Verify preferences saved
        prefs = get_user_preferences()
        assert prefs.get("integration_user") is not None
        assert prefs["integration_user"]["enabled"] is True

        # Verify alerts saved
        alerts = get_active_alerts()
        assert alerts.get("integration_user") is not None
        assert len(alerts["integration_user"]) == 1
