"""Tests for telegram_bot.notifications.handlers module.

This module tests notification handlers:
- handle_buy_cancel_callback
- handle_alert_callback
- create_alert_command
- list_alerts_command
- remove_alert_command
- settings_command
- register_notification_handlers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test handle_buy_cancel_callback function
# =============================================================================


class TestHandleBuyCancelCallback:
    """Tests for handle_buy_cancel_callback function."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock update with callback query."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "cancel_buy:item_123"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    @pytest.mark.asyncio()
    async def test_handle_buy_cancel_callback_success(
        self, mock_update: MagicMock
    ) -> None:
        """Test successful buy cancellation."""
        from src.telegram_bot.notifications.handlers import handle_buy_cancel_callback

        await handle_buy_cancel_callback(mock_update, MagicMock())

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "отменена" in call_args[0][0].lower() or "item_123" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_handle_buy_cancel_no_query(self) -> None:
        """Test handle_buy_cancel_callback with no query."""
        update = MagicMock()
        update.callback_query = None

        from src.telegram_bot.notifications.handlers import handle_buy_cancel_callback

        # Should return early without error
        await handle_buy_cancel_callback(update, MagicMock())

    @pytest.mark.asyncio()
    async def test_handle_buy_cancel_wrong_prefix(self) -> None:
        """Test handle_buy_cancel_callback with wrong prefix."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "wrong_prefix:item_123"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        from src.telegram_bot.notifications.handlers import handle_buy_cancel_callback

        await handle_buy_cancel_callback(update, MagicMock())

        # Should not edit message
        update.callback_query.edit_message_text.assert_not_called()


# =============================================================================
# Test handle_alert_callback function
# =============================================================================


class TestHandleAlertCallback:
    """Tests for handle_alert_callback function."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock update with callback query."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "disable_alert:alert_001"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        return update

    @pytest.mark.asyncio()
    async def test_handle_alert_callback_success(self, mock_update: MagicMock) -> None:
        """Test successful alert disabling."""
        with patch(
            "src.telegram_bot.notifications.handlers.remove_price_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            from src.telegram_bot.notifications.handlers import handle_alert_callback

            await handle_alert_callback(mock_update, MagicMock())

            mock_update.callback_query.answer.assert_called_once()
            mock_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_update.callback_query.edit_message_text.call_args
            assert "🔕" in call_args[0][0] or "отключено" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_handle_alert_callback_not_found(
        self, mock_update: MagicMock
    ) -> None:
        """Test alert callback when alert not found."""
        with patch(
            "src.telegram_bot.notifications.handlers.remove_price_alert",
            new_callable=AsyncMock,
            return_value=False,
        ):
            from src.telegram_bot.notifications.handlers import handle_alert_callback

            await handle_alert_callback(mock_update, MagicMock())

            call_args = mock_update.callback_query.edit_message_text.call_args
            assert "❌" in call_args[0][0] or "не удалось" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_handle_alert_callback_no_query(self) -> None:
        """Test handle_alert_callback with no query."""
        update = MagicMock()
        update.callback_query = None

        from src.telegram_bot.notifications.handlers import handle_alert_callback

        # Should return early without error
        await handle_alert_callback(update, MagicMock())

    @pytest.mark.asyncio()
    async def test_handle_alert_callback_no_user(self) -> None:
        """Test handle_alert_callback with no effective user."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "disable_alert:alert_001"
        update.callback_query.answer = AsyncMock()
        update.effective_user = None

        from src.telegram_bot.notifications.handlers import handle_alert_callback

        # Should return early without error
        await handle_alert_callback(update, MagicMock())


# =============================================================================
# Test list_alerts_command function
# =============================================================================


class TestListAlertsCommand:
    """Tests for list_alerts_command function."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock update for command."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.mark.asyncio()
    async def test_list_alerts_command_with_alerts(
        self, mock_update: MagicMock
    ) -> None:
        """Test list_alerts_command with existing alerts."""
        mock_alerts = [
            {
                "id": "alert_1",
                "title": "Test Item",
                "type": "price_drop",
                "threshold": 10.0,
            }
        ]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            from src.telegram_bot.notifications.handlers import list_alerts_command

            await list_alerts_command(mock_update, MagicMock())

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Test Item" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_list_alerts_command_empty(self, mock_update: MagicMock) -> None:
        """Test list_alerts_command with no alerts."""
        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            from src.telegram_bot.notifications.handlers import list_alerts_command

            await list_alerts_command(mock_update, MagicMock())

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "нет" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_list_alerts_command_no_user(self) -> None:
        """Test list_alerts_command with no effective user."""
        update = MagicMock()
        update.effective_user = None
        update.message = MagicMock()

        from src.telegram_bot.notifications.handlers import list_alerts_command

        # Should return early without error
        await list_alerts_command(update, MagicMock())


# =============================================================================
# Test remove_alert_command function
# =============================================================================


class TestRemoveAlertCommand:
    """Tests for remove_alert_command function."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock update for command."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.mark.asyncio()
    async def test_remove_alert_command_success(self, mock_update: MagicMock) -> None:
        """Test successful alert removal."""
        context = MagicMock()
        context.args = ["1"]

        mock_alerts = [
            {"id": "alert_1", "title": "Test Item"},
        ]

        with (
            patch(
                "src.telegram_bot.notifications.handlers.get_user_alerts",
                new_callable=AsyncMock,
                return_value=mock_alerts,
            ),
            patch(
                "src.telegram_bot.notifications.handlers.remove_price_alert",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            from src.telegram_bot.notifications.handlers import remove_alert_command

            await remove_alert_command(mock_update, context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert (
                "удалено" in call_args[0][0].lower() or "Test Item" in call_args[0][0]
            )

    @pytest.mark.asyncio()
    async def test_remove_alert_command_no_args(self, mock_update: MagicMock) -> None:
        """Test remove_alert_command with no arguments."""
        context = MagicMock()
        context.args = []

        from src.telegram_bot.notifications.handlers import remove_alert_command

        await remove_alert_command(mock_update, context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "формат" in call_args[0][0].lower() or "номер" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_remove_alert_command_invalid_number(
        self, mock_update: MagicMock
    ) -> None:
        """Test remove_alert_command with invalid number."""
        context = MagicMock()
        context.args = ["abc"]

        from src.telegram_bot.notifications.handlers import remove_alert_command

        await remove_alert_command(mock_update, context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "число" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_remove_alert_command_out_of_range(
        self, mock_update: MagicMock
    ) -> None:
        """Test remove_alert_command with out of range number."""
        context = MagicMock()
        context.args = ["5"]

        mock_alerts = [
            {"id": "alert_1", "title": "Test Item"},
        ]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            from src.telegram_bot.notifications.handlers import remove_alert_command

            await remove_alert_command(mock_update, context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "неверный" in call_args[0][0].lower()


# =============================================================================
# Test settings_command function
# =============================================================================


class TestSettingsCommand:
    """Tests for settings_command function."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock update for command."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.mark.asyncio()
    async def test_settings_command_show_settings(self, mock_update: MagicMock) -> None:
        """Test settings_command shows current settings."""
        context = MagicMock()
        context.args = []

        mock_storage = MagicMock()
        mock_storage._alerts = {
            "12345": {
                "alerts": [],
                "settings": {
                    "enabled": True,
                    "language": "ru",
                    "min_interval": 3600,
                    "quiet_hours": {"start": 23, "end": 8},
                    "max_alerts_per_day": 10,
                },
            }
        }

        with patch(
            "src.telegram_bot.notifications.handlers.get_storage",
            return_value=mock_storage,
        ):
            from src.telegram_bot.notifications.handlers import settings_command

            await settings_command(mock_update, context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "настройки" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_settings_command_update_settings(
        self, mock_update: MagicMock
    ) -> None:
        """Test settings_command updates settings."""
        context = MagicMock()
        context.args = ["enabled=false"]

        mock_storage = MagicMock()
        mock_storage._alerts = {
            "12345": {
                "alerts": [],
                "settings": {
                    "enabled": True,
                    "language": "ru",
                    "min_interval": 3600,
                    "quiet_hours": {"start": 23, "end": 8},
                    "max_alerts_per_day": 10,
                },
            }
        }

        with (
            patch(
                "src.telegram_bot.notifications.handlers.get_storage",
                return_value=mock_storage,
            ),
            patch(
                "src.telegram_bot.notifications.handlers.update_user_settings",
                new_callable=AsyncMock,
            ),
        ):
            from src.telegram_bot.notifications.handlers import settings_command

            await settings_command(mock_update, context)

            # Check settings were updated
            assert mock_storage._alerts["12345"]["settings"]["enabled"] is False


# =============================================================================
# Test register_notification_handlers function
# =============================================================================


class TestRegisterNotificationHandlers:
    """Tests for register_notification_handlers function."""

    def test_register_notification_handlers(self) -> None:
        """Test registering notification handlers."""
        mock_application = MagicMock()
        mock_application.add_handler = MagicMock()
        mock_application.bot = MagicMock()
        mock_application.bot_data = {"dmarket_api": MagicMock()}

        with (
            patch(
                "src.telegram_bot.notifications.handlers.load_user_alerts",
            ),
            patch(
                "asyncio.create_task",
            ),
        ):
            from src.telegram_bot.notifications.handlers import (
                register_notification_handlers,
            )

            register_notification_handlers(mock_application)

            # Should add multiple handlers
            assert mock_application.add_handler.call_count >= 4

    def test_register_notification_handlers_no_api(self) -> None:
        """Test registering handlers without API."""
        mock_application = MagicMock()
        mock_application.add_handler = MagicMock()
        mock_application.bot = MagicMock()
        mock_application.bot_data = {}

        with patch(
            "src.telegram_bot.notifications.handlers.load_user_alerts",
        ):
            from src.telegram_bot.notifications.handlers import (
                register_notification_handlers,
            )

            # Should not raise error
            register_notification_handlers(mock_application)


# =============================================================================
# Module exports test
# =============================================================================


class TestHandlersModuleExports:
    """Tests for module exports."""

    def test_module_has_handle_buy_cancel_callback(self) -> None:
        """Test handle_buy_cancel_callback is exported."""
        from src.telegram_bot.notifications.handlers import handle_buy_cancel_callback

        assert callable(handle_buy_cancel_callback)

    def test_module_has_handle_alert_callback(self) -> None:
        """Test handle_alert_callback is exported."""
        from src.telegram_bot.notifications.handlers import handle_alert_callback

        assert callable(handle_alert_callback)

    def test_module_has_list_alerts_command(self) -> None:
        """Test list_alerts_command is exported."""
        from src.telegram_bot.notifications.handlers import list_alerts_command

        assert callable(list_alerts_command)

    def test_module_has_remove_alert_command(self) -> None:
        """Test remove_alert_command is exported."""
        from src.telegram_bot.notifications.handlers import remove_alert_command

        assert callable(remove_alert_command)

    def test_module_has_settings_command(self) -> None:
        """Test settings_command is exported."""
        from src.telegram_bot.notifications.handlers import settings_command

        assert callable(settings_command)

    def test_module_has_register_notification_handlers(self) -> None:
        """Test register_notification_handlers is exported."""
        from src.telegram_bot.notifications.handlers import (
            register_notification_handlers,
        )

        assert callable(register_notification_handlers)
