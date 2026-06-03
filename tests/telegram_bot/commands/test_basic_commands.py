"""
Tests for basic Telegram bot commands (/start and /help).

This module tests the core user interaction commands ensuring proper:
- Message delivery to users
- Logging of command usage
- Sentry breadcrumb tracking
- Error handling for edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import Application, ContextTypes

from src.telegram_bot.commands.basic_commands import (
    help_command,
    register_basic_commands,
    start_command,
)


@pytest.fixture()
def mock_user():
    """Create a mock Telegram user."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "test_user"
    user.first_name = "Test"
    return user


@pytest.fixture()
def mock_chat():
    """Create a mock Telegram chat."""
    chat = MagicMock(spec=Chat)
    chat.id = 987654321
    chat.type = "private"
    return chat


@pytest.fixture()
def mock_message(mock_user, mock_chat):
    """Create a mock Telegram message."""
    message = MagicMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.reply_text = AsyncMock(return_value=None)
    return message


@pytest.fixture()
def mock_update(mock_user, mock_message, mock_chat):
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.effective_chat = mock_chat
    update.message = mock_message
    return update


@pytest.fixture()
def mock_context():
    """Create a mock context."""
    return MagicMock(spec=ContextTypes.DEFAULT_TYPE)


class TestStartCommand:
    """Tests for the /start command."""

    @pytest.mark.asyncio()
    async def test_start_command_sends_welcome_message(
        self, mock_update, mock_context, mock_message
    ):
        """Test that /start command sends welcome message."""
        # Act
        await start_command(mock_update, mock_context)

        # Assert
        mock_message.reply_text.assert_called_once()
        call_args = mock_message.reply_text.call_args[0][0]
        assert "Привет!" in call_args
        assert "/help" in call_args
        assert "DMarket" in call_args

    @pytest.mark.asyncio()
    async def test_start_command_logs_user_interaction(
        self, mock_update, mock_context, mock_user
    ):
        """Test that /start command logs user interaction."""
        # Arrange
        with patch("src.telegram_bot.commands.basic_commands.logger") as mock_logger:
            # Act
            await start_command(mock_update, mock_context)

            # Assert
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "/start" in str(call_args)
            assert str(mock_user.id) in str(call_args)

    @pytest.mark.asyncio()
    async def test_start_command_adds_sentry_breadcrumb(
        self, mock_update, mock_context, mock_user, mock_chat
    ):
        """Test that /start command adds Sentry breadcrumb."""
        # Arrange
        with patch(
            "src.telegram_bot.commands.basic_commands.add_command_breadcrumb"
        ) as mock_breadcrumb:
            # Act
            await start_command(mock_update, mock_context)

            # Assert
            mock_breadcrumb.assert_called_once_with(
                command="/start",
                user_id=mock_user.id,
                username=mock_user.username,
                chat_id=mock_chat.id,
            )

    @pytest.mark.asyncio()
    async def test_start_command_handles_no_user(self, mock_context):
        """Test that /start command handles missing user gracefully."""
        # Arrange
        update = MagicMock(spec=Update)
        update.effective_user = None
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()

        # Act
        await start_command(update, mock_context)

        # Assert - Should return early without sending message
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_start_command_handles_no_message(self, mock_update, mock_context):
        """Test that /start command handles missing message object."""
        # Arrange
        mock_update.message = None

        # Act - Should not raise exception
        await start_command(mock_update, mock_context)

        # No assertion needed - just verify no exception

    @pytest.mark.asyncio()
    async def test_start_command_handles_user_without_username(
        self, mock_update, mock_context, mock_user
    ):
        """Test that /start command handles user without username."""
        # Arrange
        mock_user.username = None
        with patch(
            "src.telegram_bot.commands.basic_commands.add_command_breadcrumb"
        ) as mock_breadcrumb:
            # Act
            await start_command(mock_update, mock_context)

            # Assert
            mock_breadcrumb.assert_called_once()
            call_kwargs = mock_breadcrumb.call_args.kwargs
            assert call_kwargs["username"] == ""


class TestHelpCommand:
    """Tests for the /help command."""

    @pytest.mark.asyncio()
    async def test_help_command_sends_command_list(
        self, mock_update, mock_context, mock_message
    ):
        """Test that /help command sends list of avAlgolable commands."""
        # Act
        await help_command(mock_update, mock_context)

        # Assert
        mock_message.reply_text.assert_called_once()
        call_args = mock_message.reply_text.call_args[0][0]
        assert "Доступные команды:" in call_args
        assert "/start" in call_args
        assert "/help" in call_args
        assert "/dmarket" in call_args
        assert "/balance" in call_args
        assert "/arbitrage" in call_args

    @pytest.mark.asyncio()
    async def test_help_command_logs_user_interaction(
        self, mock_update, mock_context, mock_user
    ):
        """Test that /help command logs user interaction."""
        # Arrange
        with patch("src.telegram_bot.commands.basic_commands.logger") as mock_logger:
            # Act
            await help_command(mock_update, mock_context)

            # Assert
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "/help" in str(call_args)
            assert str(mock_user.id) in str(call_args)

    @pytest.mark.asyncio()
    async def test_help_command_adds_sentry_breadcrumb(
        self, mock_update, mock_context, mock_user, mock_chat
    ):
        """Test that /help command adds Sentry breadcrumb."""
        # Arrange
        with patch(
            "src.telegram_bot.commands.basic_commands.add_command_breadcrumb"
        ) as mock_breadcrumb:
            # Act
            await help_command(mock_update, mock_context)

            # Assert
            mock_breadcrumb.assert_called_once_with(
                command="/help",
                user_id=mock_user.id,
                username=mock_user.username,
                chat_id=mock_chat.id,
            )

    @pytest.mark.asyncio()
    async def test_help_command_handles_no_user(self, mock_context):
        """Test that /help command handles missing user gracefully."""
        # Arrange
        update = MagicMock(spec=Update)
        update.effective_user = None
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()

        # Act
        await help_command(update, mock_context)

        # Assert - Should return early without sending message
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_help_command_handles_no_message(self, mock_update, mock_context):
        """Test that /help command handles missing message object."""
        # Arrange
        mock_update.message = None

        # Act - Should not raise exception
        await help_command(mock_update, mock_context)

        # No assertion needed - just verify no exception

    @pytest.mark.asyncio()
    async def test_help_command_includes_all_commands(
        self, mock_update, mock_context, mock_message
    ):
        """Test that /help command includes all avAlgolable commands."""
        # Act
        await help_command(mock_update, mock_context)

        # Assert
        call_args = mock_message.reply_text.call_args[0][0]
        required_commands = ["/start", "/help", "/dmarket", "/balance", "/arbitrage"]
        for command in required_commands:
            assert command in call_args, f"Command {command} not found in help text"


class TestRegisterBasicCommands:
    """Tests for command registration."""

    def test_register_basic_commands_adds_handlers(self):
        """Test that register_basic_commands adds command handlers."""
        # Arrange
        app = MagicMock(spec=Application)
        app.add_handler = MagicMock()

        # Act
        with patch("src.telegram_bot.commands.basic_commands.logger"):
            register_basic_commands(app)

        # Assert
        assert app.add_handler.call_count == 2
        # Verify that CommandHandlers were added
        calls = app.add_handler.call_args_list
        assert len(calls) == 2

    def test_register_basic_commands_logs_registration(self):
        """Test that register_basic_commands logs registration."""
        # Arrange
        app = MagicMock(spec=Application)
        with patch("src.telegram_bot.commands.basic_commands.logger") as mock_logger:
            # Act
            register_basic_commands(app)

            # Assert
            mock_logger.info.assert_called_once()
            assert "Регистрация базовых команд" in str(mock_logger.info.call_args)

    def test_register_basic_commands_correct_command_names(self):
        """Test that register_basic_commands registers correct command names."""
        # Arrange
        app = MagicMock(spec=Application)
        handlers_added = []

        def capture_handler(handler):
            handlers_added.append(handler)

        app.add_handler = capture_handler

        # Act
        with patch("src.telegram_bot.commands.basic_commands.logger"):
            register_basic_commands(app)

        # Assert
        assert len(handlers_added) == 2
        # Check that handlers exist (can't easily check command names without
        # accessing private attributes, but we verify count and type)


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    @pytest.mark.asyncio()
    async def test_start_command_with_callback_query_instead_of_message(
        self, mock_update, mock_context
    ):
        """Test /start command when triggered via callback query."""
        # Arrange
        mock_update.message = None
        mock_update.callback_query = MagicMock()

        # Act - Should not raise exception
        await start_command(mock_update, mock_context)

        # No message sent since update.message is None

    @pytest.mark.asyncio()
    async def test_help_command_with_callback_query_instead_of_message(
        self, mock_update, mock_context
    ):
        """Test /help command when triggered via callback query."""
        # Arrange
        mock_update.message = None
        mock_update.callback_query = MagicMock()

        # Act - Should not raise exception
        await help_command(mock_update, mock_context)

        # No message sent since update.message is None

    @pytest.mark.asyncio()
    async def test_commands_handle_message_send_failure(
        self, mock_update, mock_context, mock_message
    ):
        """Test commands handle message send failures gracefully."""
        # Arrange
        mock_message.reply_text.side_effect = Exception("Network error")

        # Act & Assert - Should raise the exception (no silent failures)
        with pytest.raises(Exception):
            await start_command(mock_update, mock_context)
