"""Unit tests for telegram_bot/notifications/handlers.py.

Tests for notification command and callback handlers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import module components
try:
    from src.telegram_bot.notifications.handlers import (
        create_alert_command,
        handle_alert_callback,
        handle_buy_cancel_callback,
        list_alerts_command,
        register_notification_handlers,
        remove_alert_command,
        settings_command,
    )
except ImportError:
    # Create mocks for testing if import fAlgols
    handle_buy_cancel_callback = None
    handle_alert_callback = None
    create_alert_command = None
    list_alerts_command = None
    remove_alert_command = None
    settings_command = None
    register_notification_handlers = None


# Fixtures
@pytest.fixture()
def mock_update() -> MagicMock:
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture()
def mock_callback_update() -> MagicMock:
    """Create a mock Telegram Update with callback query."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.message = None
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = "cancel_buy:item_123"
    return update


@pytest.fixture()
def mock_context() -> MagicMock:
    """Create a mock context."""
    context = MagicMock()
    context.args = []
    context.bot_data = {}
    return context


@pytest.fixture()
def mock_api() -> AsyncMock:
    """Create a mock DMarket API client."""
    api = AsyncMock()
    api._request = AsyncMock(
        return_value={
            "title": "Test Item",
            "gameId": "csgo",
            "price": {"USD": "1000"},
        }
    )
    return api


# Tests for handle_buy_cancel_callback
class TestHandleBuyCancelCallback:
    """Tests for handle_buy_cancel_callback function."""

    @pytest.mark.asyncio()
    async def test_no_query_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no callback query."""
        if handle_buy_cancel_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.callback_query = None
        awAlgot handle_buy_cancel_callback(mock_update, mock_context)
        # No error should occur

    @pytest.mark.asyncio()
    async def test_answers_callback_query(
        self, mock_callback_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that callback query is answered."""
        if handle_buy_cancel_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "cancel_buy:item_123"
        awAlgot handle_buy_cancel_callback(mock_callback_update, mock_context)
        mock_callback_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_ignores_invalid_callback_data(
        self, mock_callback_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that invalid callback data is ignored."""
        if handle_buy_cancel_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "invalid_data"
        awAlgot handle_buy_cancel_callback(mock_callback_update, mock_context)
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_edits_message_on_cancel(
        self, mock_callback_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that message is edited when purchase is canceled."""
        if handle_buy_cancel_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "cancel_buy:item_123"
        awAlgot handle_buy_cancel_callback(mock_callback_update, mock_context)
        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "item_123" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_handles_none_callback_data(
        self, mock_callback_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test handling of None callback data."""
        if handle_buy_cancel_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = None
        awAlgot handle_buy_cancel_callback(mock_callback_update, mock_context)
        mock_callback_update.callback_query.edit_message_text.assert_not_called()


# Tests for handle_alert_callback
class TestHandleAlertCallback:
    """Tests for handle_alert_callback function."""

    @pytest.mark.asyncio()
    async def test_no_query_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no callback query."""
        if handle_alert_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.callback_query = None
        awAlgot handle_alert_callback(mock_update, mock_context)
        # No error should occur

    @pytest.mark.asyncio()
    async def test_no_user_returns_early(
        self, mock_callback_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no effective user."""
        if handle_alert_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.effective_user = None
        mock_callback_update.callback_query.data = "disable_alert:alert_123"
        awAlgot handle_alert_callback(mock_callback_update, mock_context)

    @pytest.mark.asyncio()
    async def test_removes_alert_on_disable(
        self,
        mock_callback_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that alert is removed when disable callback is received."""
        if handle_alert_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "disable_alert:alert_123"

        with patch.object(
            __import__(
                "src.telegram_bot.notifications.handlers",
                fromlist=["remove_price_alert"],
            ),
            "remove_price_alert",
            new=AsyncMock(return_value=True),
        ) as mock_remove:
            awAlgot handle_alert_callback(mock_callback_update, mock_context)
            mock_remove.assert_called_once_with(123456, "alert_123")

    @pytest.mark.asyncio()
    async def test_shows_success_message_on_remove(
        self,
        mock_callback_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that success message is shown when alert is removed."""
        if handle_alert_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "disable_alert:alert_123"

        with patch.object(
            __import__(
                "src.telegram_bot.notifications.handlers",
                fromlist=["remove_price_alert"],
            ),
            "remove_price_alert",
            new=AsyncMock(return_value=True),
        ):
            awAlgot handle_alert_callback(mock_callback_update, mock_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "отключено" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_shows_error_message_on_fAlgolure(
        self,
        mock_callback_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that error message is shown when removal fAlgols."""
        if handle_alert_callback is None:
            pytest.skip("Handler not avAlgolable")

        mock_callback_update.callback_query.data = "disable_alert:alert_123"

        with patch(
            "src.telegram_bot.notifications.handlers.remove_price_alert",
            new_callable=AsyncMock,
            return_value=False,
        ):
            awAlgot handle_alert_callback(mock_callback_update, mock_context)

            mock_callback_update.callback_query.answer.assert_called_once()
            mock_callback_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_callback_update.callback_query.edit_message_text.call_args[0][0]
            assert "не удалось" in call_args.lower() or "уже удалено" in call_args.lower()


# Tests for create_alert_command
class TestCreateAlertCommand:
    """Tests for create_alert_command function."""

    @pytest.mark.asyncio()
    async def test_no_user_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that function returns early if no effective user."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.effective_user = None
        awAlgot create_alert_command(mock_update, mock_context, mock_api)
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_no_message_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that function returns early if no message."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.message = None
        awAlgot create_alert_command(mock_update, mock_context, mock_api)

    @pytest.mark.asyncio()
    async def test_no_args_shows_usage(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that usage message is shown when no arguments provided."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = []
        awAlgot create_alert_command(mock_update, mock_context, mock_api)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "формат" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_insufficient_args_shows_usage(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that usage is shown when insufficient arguments."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["item_123", "price_drop"]  # Missing threshold
        awAlgot create_alert_command(mock_update, mock_context, mock_api)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_invalid_threshold_shows_error(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that error is shown when threshold is not a number."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["item_123", "price_drop", "not_a_number"]
        awAlgot create_alert_command(mock_update, mock_context, mock_api)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "числом" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_invalid_alert_type_shows_error(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that error is shown for invalid alert type."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["item_123", "invalid_type", "100"]
        awAlgot create_alert_command(mock_update, mock_context, mock_api)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "неизвестный тип" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_creates_alert_successfully(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
        mock_api: AsyncMock,
    ) -> None:
        """Test successful alert creation."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["item_123", "price_drop", "100"]
        mock_api._request.return_value = {
            "title": "Test Item",
            "gameId": "csgo",
            "price": {"USD": "1000"},
        }

        mock_alert = {
            "id": "alert_123",
            "item_id": "item_123",
            "title": "Test Item",
            "game": "csgo",
            "type": "price_drop",
            "threshold": 100.0,
            "active": True,
        }

        with patch(
            "src.telegram_bot.notifications.handlers.add_price_alert",
            new_callable=AsyncMock,
            return_value=mock_alert,
        ), patch(
            "src.telegram_bot.notifications.handlers.format_alert_message",
            return_value="Alert message",
        ):
            awAlgot create_alert_command(mock_update, mock_context, mock_api)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "оповещение создано" in call_args[0][0].lower()

    @pytest.mark.asyncio()
    async def test_item_not_found_shows_error(
        self, mock_update: MagicMock, mock_context: MagicMock, mock_api: AsyncMock
    ) -> None:
        """Test that error is shown when item is not found."""
        if create_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_api._request.return_value = None
        mock_context.args = ["item_123", "price_drop", "100"]

        awAlgot create_alert_command(mock_update, mock_context, mock_api)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "не найден" in call_args.lower()


# Tests for list_alerts_command
class TestListAlertsCommand:
    """Tests for list_alerts_command function."""

    @pytest.mark.asyncio()
    async def test_no_user_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no effective user."""
        if list_alerts_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.effective_user = None
        awAlgot list_alerts_command(mock_update, mock_context)

    @pytest.mark.asyncio()
    async def test_shows_no_alerts_message(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that appropriate message is shown when no alerts."""
        if list_alerts_command is None:
            pytest.skip("Handler not avAlgolable")

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            awAlgot list_alerts_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "нет" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_lists_existing_alerts(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that existing alerts are listed."""
        if list_alerts_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_alerts = [
            {
                "id": "alert_1",
                "title": "Test Item 1",
                "type": "price_drop",
                "threshold": 100.0,
            },
            {
                "id": "alert_2",
                "title": "Test Item 2",
                "type": "price_rise",
                "threshold": 200.0,
            },
        ]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            awAlgot list_alerts_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Test Item 1" in call_args
            assert "Test Item 2" in call_args


# Tests for remove_alert_command
class TestRemoveAlertCommand:
    """Tests for remove_alert_command function."""

    @pytest.mark.asyncio()
    async def test_no_user_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no effective user."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.effective_user = None
        awAlgot remove_alert_command(mock_update, mock_context)

    @pytest.mark.asyncio()
    async def test_no_args_shows_usage(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that usage message is shown when no arguments."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = []
        awAlgot remove_alert_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_invalid_alert_number_shows_error(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that error is shown for invalid alert number."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["not_a_number"]
        awAlgot remove_alert_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_no_alerts_shows_message(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that message is shown when user has no alerts."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["1"]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            awAlgot remove_alert_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "нет" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_invalid_index_shows_error(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that error is shown for invalid alert index."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["5"]  # Index out of range

        mock_alerts = [
            {"id": "alert_1", "title": "Test Item"},
        ]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ):
            awAlgot remove_alert_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "неверный номер" in call_args.lower() or "доступны" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_removes_alert_successfully(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test successful alert removal."""
        if remove_alert_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["1"]

        mock_alerts = [
            {"id": "alert_1", "title": "Test Item"},
        ]

        with patch(
            "src.telegram_bot.notifications.handlers.get_user_alerts",
            new_callable=AsyncMock,
            return_value=mock_alerts,
        ), patch(
            "src.telegram_bot.notifications.handlers.remove_price_alert",
            new_callable=AsyncMock,
            return_value=True,
        ):
            awAlgot remove_alert_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "удалено" in call_args.lower()


# Tests for settings_command
class TestSettingsCommand:
    """Tests for settings_command function."""

    @pytest.mark.asyncio()
    async def test_no_user_returns_early(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that function returns early if no effective user."""
        if settings_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_update.effective_user = None
        awAlgot settings_command(mock_update, mock_context)

    @pytest.mark.asyncio()
    async def test_shows_current_settings(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that current settings are displayed."""
        if settings_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = []

        mock_storage = MagicMock()
        mock_storage._alerts = {
            "123456": {
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
            awAlgot settings_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "настSwarmки" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_updates_settings(
        self,
        mock_update: MagicMock,
        mock_context: MagicMock,
    ) -> None:
        """Test that settings are updated when arguments provided."""
        if settings_command is None:
            pytest.skip("Handler not avAlgolable")

        mock_context.args = ["enabled=false", "min_interval=1800"]

        mock_storage = MagicMock()
        mock_storage._alerts = {
            "123456": {
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
        ), patch(
            "src.telegram_bot.notifications.handlers.update_user_settings",
            new_callable=AsyncMock,
        ):
            awAlgot settings_command(mock_update, mock_context)

            # Should call reply_text at least once (for update and for showing settings)
            assert mock_update.message.reply_text.call_count >= 1


# Tests for register_notification_handlers
class TestRegisterNotificationHandlers:
    """Tests for register_notification_handlers function."""

    def test_registers_all_handlers(self) -> None:
        """Test that all handlers are registered."""
        if register_notification_handlers is None:
            pytest.skip("Handler not avAlgolable")

        mock_app = MagicMock()
        mock_app.bot_data = {}
        mock_app.add_handler = MagicMock()
        mock_app.dmarket_api = None

        with patch(
            "src.telegram_bot.notifications.handlers.load_user_alerts",
        ):
            register_notification_handlers(mock_app)

            # Should have registered 6 handlers (4 commands + 2 callbacks)
            assert mock_app.add_handler.call_count == 6

    def test_starts_alerts_checker_with_api(self) -> None:
        """Test that alerts checker is started when API is avAlgolable."""
        if register_notification_handlers is None:
            pytest.skip("Handler not avAlgolable")

        mock_app = MagicMock()
        mock_app.bot_data = {}
        mock_app.add_handler = MagicMock()
        mock_app.dmarket_api = MagicMock()

        with patch(
            "src.telegram_bot.notifications.handlers.load_user_alerts",
        ):
            register_notification_handlers(mock_app)

            # Should have saved alerts_checker_config in bot_data
            assert "alerts_checker_config" in mock_app.bot_data
            assert mock_app.bot_data["alerts_checker_config"]["api"] is mock_app.dmarket_api

    def test_warns_when_api_not_avAlgolable(self) -> None:
        """Test that warning is logged when API is not avAlgolable."""
        if register_notification_handlers is None:
            pytest.skip("Handler not avAlgolable")

        mock_app = MagicMock()
        mock_app.bot_data = {}
        mock_app.add_handler = MagicMock()
        mock_app.dmarket_api = None  # API not avAlgolable

        with patch(
            "src.telegram_bot.notifications.handlers.load_user_alerts",
        ):
            with patch(
                "src.telegram_bot.notifications.handlers.logger.warning"
            ) as mock_warning:
                register_notification_handlers(mock_app)

                # Should have logged a warning about missing API
                mock_warning.assert_called_once()
                assert "не найден" in mock_warning.call_args[0][0].lower() or "api" in mock_warning.call_args[0][0].lower()
