"""Unit tests for smart_notifications handlers module.

This module tests src/telegram_bot/smart_notifications/handlers.py covering:
- handle_notification_callback function
- register_notification_handlers function

Target: 18+ tests to achieve 70%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Module path constant for patching
HANDLERS_MODULE = "src.telegram_bot.smart_notifications.handlers"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture()
def mock_update():
    """Fixture providing a mocked Update object."""
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = ""
    update.callback_query.answer = AsyncMock()
    update.callback_query.from_user.id = 12345
    update.callback_query.message.text = "Test notification message"
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    return update


@pytest.fixture()
def mock_context():
    """Fixture providing a mocked ContextTypes."""
    context = MagicMock()
    context.bot_data = {}
    return context


@pytest.fixture()
def mock_api():
    """Fixture providing a mocked DMarketAPI."""
    api = MagicMock()
    api.get_item_offers = AsyncMock(return_value={"objects": []})
    api.get_market_items = AsyncMock(return_value={"objects": []})
    return api


@pytest.fixture()
def mock_application():
    """Fixture providing a mocked Application."""
    application = MagicMock()
    application.bot_data = {}
    application.add_handler = MagicMock()
    application.bot = MagicMock()
    return application


@pytest.fixture()
def sample_item_data():
    """Fixture providing sample item data."""
    return {
        "itemId": "item_abc",
        "title": "AK-47 | Redline (Field-Tested)",
        "price": {"USD": "2000"},
        "suggestedPrice": {"USD": "2500"},
        "gameId": "csgo",
    }


# =============================================================================
# Tests for handle_notification_callback
# =============================================================================


class TestHandleNotificationCallback:
    """Tests for handle_notification_callback function."""

    @pytest.mark.asyncio()
    async def test_callback_with_no_query(self, mock_context):
        """Test that callback returns early if no query exists."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        update = MagicMock()
        update.callback_query = None

        await handle_notification_callback(update, mock_context)
        # Should return early without any errors

    @pytest.mark.asyncio()
    async def test_callback_with_no_data(self, mock_context):
        """Test that callback returns early if query has no data."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = None

        await handle_notification_callback(update, mock_context)
        # Should return early without any errors

    @pytest.mark.asyncio()
    async def test_callback_answers_query(self, mock_update, mock_context):
        """Test that callback answers the query."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "unknown_action"

        await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_disable_alert_success(self, mock_update, mock_context):
        """Test successful alert disable."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "disable_alert:alert_123"

        with patch(
            f"{HANDLERS_MODULE}.deactivate_alert", new=AsyncMock(return_value=True)
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Alert has been disabled" in call_args.kwargs.get("text", "")

    @pytest.mark.asyncio()
    async def test_disable_alert_failure(self, mock_update, mock_context):
        """Test failed alert disable."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "disable_alert:alert_123"

        with patch(
            f"{HANDLERS_MODULE}.deactivate_alert", new=AsyncMock(return_value=False)
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_reply_markup.assert_called_once()

    @pytest.mark.asyncio()
    async def test_track_item_no_api(self, mock_update, mock_context):
        """Test track_item callback when API is not available."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_123:csgo"
        mock_context.bot_data = {}  # No dmarket_api

        await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "API not available" in call_args.kwargs.get("text", "")

    @pytest.mark.asyncio()
    async def test_track_item_item_not_found(self, mock_update, mock_context, mock_api):
        """Test track_item callback when item is not found."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_123:csgo"
        mock_context.bot_data = {"dmarket_api": mock_api}

        with patch(
            f"{HANDLERS_MODULE}.get_item_by_id", new=AsyncMock(return_value=None)
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Item not found" in call_args.kwargs.get("text", "")

    @pytest.mark.asyncio()
    async def test_track_item_success(
        self, mock_update, mock_context, mock_api, sample_item_data
    ):
        """Test successful track_item callback."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_abc:csgo"
        mock_context.bot_data = {"dmarket_api": mock_api}

        with (
            patch(
                f"{HANDLERS_MODULE}.get_item_by_id",
                new=AsyncMock(return_value=sample_item_data),
            ),
            patch(f"{HANDLERS_MODULE}.get_item_price", return_value=20.0),
            patch(
                f"{HANDLERS_MODULE}.create_alert",
                new=AsyncMock(return_value="alert_id"),
            ),
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Alerts created" in call_args.kwargs.get("text", "")

    @pytest.mark.asyncio()
    async def test_track_item_error_handling(self, mock_update, mock_context, mock_api):
        """Test track_item callback error handling."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_123:csgo"
        mock_context.bot_data = {"dmarket_api": mock_api}

        with patch(
            f"{HANDLERS_MODULE}.get_item_by_id",
            new=AsyncMock(side_effect=Exception("API Error")),
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Error creating alert" in call_args.kwargs.get("text", "")

    @pytest.mark.asyncio()
    async def test_track_item_default_game(
        self, mock_update, mock_context, mock_api, sample_item_data
    ):
        """Test track_item with default game (csgo)."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_abc"  # No game specified
        mock_context.bot_data = {"dmarket_api": mock_api}

        with (
            patch(
                f"{HANDLERS_MODULE}.get_item_by_id",
                new=AsyncMock(return_value=sample_item_data),
            ),
            patch(f"{HANDLERS_MODULE}.get_item_price", return_value=20.0),
            patch(
                f"{HANDLERS_MODULE}.create_alert",
                new=AsyncMock(return_value="alert_id"),
            ),
        ):
            await handle_notification_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_with_empty_message_text(self, mock_context):
        """Test callback with empty message text."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "disable_alert:alert_123"
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.id = 12345
        update.callback_query.message.text = None
        update.callback_query.edit_message_text = AsyncMock()

        with patch(
            f"{HANDLERS_MODULE}.deactivate_alert", new=AsyncMock(return_value=True)
        ):
            await handle_notification_callback(update, mock_context)

        update.callback_query.edit_message_text.assert_called_once()


# =============================================================================
# Tests for register_notification_handlers
# =============================================================================


class TestRegisterNotificationHandlers:
    """Tests for register_notification_handlers function."""

    def test_register_handlers_with_api(self, mock_application, mock_api):
        """Test handler registration with API available."""
        from src.telegram_bot.smart_notifications.handlers import (
            register_notification_handlers,
        )

        mock_application.bot_data = {"dmarket_api": mock_api}

        with (
            patch(f"{HANDLERS_MODULE}.asyncio.create_task") as mock_create_task,
            patch(f"{HANDLERS_MODULE}.start_notification_checker", new=AsyncMock()),
        ):
            register_notification_handlers(mock_application)

        mock_application.add_handler.assert_called_once()
        mock_create_task.assert_called_once()

    def test_register_handlers_without_api(self, mock_application):
        """Test handler registration without API."""
        from src.telegram_bot.smart_notifications.handlers import (
            register_notification_handlers,
        )

        mock_application.bot_data = {}  # No dmarket_api

        with patch(f"{HANDLERS_MODULE}.asyncio.create_task") as mock_create_task:
            register_notification_handlers(mock_application)

        mock_application.add_handler.assert_called_once()
        mock_create_task.assert_not_called()

    def test_register_handlers_with_notification_queue(
        self, mock_application, mock_api
    ):
        """Test handler registration with notification queue."""
        from src.telegram_bot.smart_notifications.handlers import (
            register_notification_handlers,
        )

        notification_queue = MagicMock()
        mock_application.bot_data = {
            "dmarket_api": mock_api,
            "notification_queue": notification_queue,
        }

        with (
            patch(f"{HANDLERS_MODULE}.asyncio.create_task") as mock_create_task,
            patch(f"{HANDLERS_MODULE}.start_notification_checker", new=AsyncMock()),
        ):
            register_notification_handlers(mock_application)

        mock_application.add_handler.assert_called_once()
        mock_create_task.assert_called_once()

    def test_callback_handler_pattern(self, mock_application):
        """Test that callback handler is registered with correct pattern."""
        from src.telegram_bot.smart_notifications.handlers import (
            register_notification_handlers,
        )

        mock_application.bot_data = {}

        register_notification_handlers(mock_application)

        mock_application.add_handler.assert_called_once()
        call_args = mock_application.add_handler.call_args
        handler = call_args[0][0]
        # Check it's a CallbackQueryHandler
        assert hasattr(handler, "pattern")


# =============================================================================
# Edge Cases
# =============================================================================


class TestHandlerEdgeCases:
    """Edge case tests for handlers module."""

    @pytest.mark.asyncio()
    async def test_callback_with_message_without_text_attribute(self, mock_context):
        """Test callback when message doesn't have text attribute."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "disable_alert:alert_123"
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.id = 12345
        update.callback_query.message = MagicMock(spec=[])  # No text attribute
        update.callback_query.edit_message_text = AsyncMock()

        with patch(
            f"{HANDLERS_MODULE}.deactivate_alert", new=AsyncMock(return_value=True)
        ):
            await handle_notification_callback(update, mock_context)

    @pytest.mark.asyncio()
    async def test_track_item_with_special_characters(
        self, mock_update, mock_context, mock_api
    ):
        """Test track_item with special characters in item ID."""
        from src.telegram_bot.smart_notifications.handlers import (
            handle_notification_callback,
        )

        mock_update.callback_query.data = "track_item:item_abc-123_!@#:csgo"
        mock_context.bot_data = {"dmarket_api": mock_api}

        with patch(
            f"{HANDLERS_MODULE}.get_item_by_id", new=AsyncMock(return_value=None)
        ):
            await handle_notification_callback(mock_update, mock_context)
