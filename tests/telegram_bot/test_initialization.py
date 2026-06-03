"""Unit tests for src/telegram_bot/initialization.py module.

Tests for bot initialization, configuration, signal handling, and handler registration.
"""

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default_level_info(self):
        """Test setup_logging uses INFO level by default."""
        from src.telegram_bot.initialization import setup_logging

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_logger.handlers = []

            setup_logging()

            # Root logger should be set to INFO level
            mock_logger.setLevel.assert_called()

    def test_setup_logging_custom_level(self):
        """Test setup_logging with custom log level."""
        from src.telegram_bot.initialization import setup_logging

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_logger.handlers = []

            setup_logging(log_level=logging.DEBUG)

            # Check that setLevel was called (may be called multiple times)
            mock_logger.setLevel.assert_called()
            # Verify DEBUG level was set at some point
            call_args = [call[0][0] for call in mock_logger.setLevel.call_args_list]
            assert logging.DEBUG in call_args or mock_logger.setLevel.call_args[0][0] == logging.DEBUG

    def test_setup_logging_with_log_file(self, tmp_path):
        """Test setup_logging creates file handler when log_file is specified."""
        from src.telegram_bot.initialization import setup_logging

        log_file = str(tmp_path / "test.log")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_logger.handlers = []

            setup_logging(log_file=log_file)

            # Check that addHandler was called for file handler
            assert mock_logger.addHandler.called

    def test_setup_logging_with_error_log_file(self, tmp_path):
        """Test setup_logging creates error file handler."""
        from src.telegram_bot.initialization import setup_logging

        error_log = str(tmp_path / "errors.log")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_logger.handlers = []

            setup_logging(error_log_file=error_log)

            # Multiple handlers should be added
            assert mock_logger.addHandler.call_count >= 1

    def test_setup_logging_clears_existing_handlers(self):
        """Test setup_logging removes existing handlers."""
        from src.telegram_bot.initialization import setup_logging

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_handler = MagicMock()
            mock_logger.handlers = [mock_handler]
            mock_get_logger.return_value = mock_logger

            setup_logging()

            mock_logger.removeHandler.assert_called_once_with(mock_handler)

    def test_setup_logging_with_custom_formatter(self):
        """Test setup_logging uses custom formatter when provided."""
        from src.telegram_bot.initialization import setup_logging

        custom_formatter = logging.Formatter("%(message)s")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            mock_logger.handlers = []

            setup_logging(formatter=custom_formatter)

            # Should use the custom formatter
            assert mock_logger.addHandler.called


class TestInitializeBot:
    """Tests for initialize_bot function."""

    @pytest.mark.asyncio()
    async def test_initialize_bot_raises_without_token(self):
        """Test initialize_bot raises ValueError when token is empty."""
        from src.telegram_bot.initialization import initialize_bot

        with pytest.raises(ValueError, match="Не указан токен"):
            await initialize_bot("")

    @pytest.mark.asyncio()
    async def test_initialize_bot_raises_with_none_token(self):
        """Test initialize_bot raises ValueError when token is None."""
        from src.telegram_bot.initialization import initialize_bot

        with pytest.raises((ValueError, TypeError)):
            await initialize_bot(None)

    @pytest.mark.asyncio()
    async def test_initialize_bot_with_valid_token(self):
        """Test initialize_bot creates application with valid token."""
        from src.telegram_bot.initialization import initialize_bot

        with (
            patch("src.telegram_bot.initialization.ApplicationBuilder") as mock_builder,
            patch("src.telegram_bot.initialization.profile_manager") as mock_profiles,
            patch("src.telegram_bot.initialization.configure_admin_ids") as mock_admin,
            patch("src.telegram_bot.initialization.setup_error_handler"),
            patch("src.telegram_bot.initialization.register_global_exception_handlers"),
            patch("src.telegram_bot.initialization.setup_signal_handlers"),
        ):
            mock_profiles.get_admin_ids.return_value = set()
            mock_admin.return_value = [123]

            mock_app = MagicMock()
            mock_builder.return_value.token.return_value.concurrent_updates.return_value.connection_pool_size.return_value.build.return_value = (
                mock_app
            )

            result = await initialize_bot("test_token", setup_persistence=False)

            assert result == mock_app
            mock_builder.return_value.token.assert_called_once_with("test_token")

    @pytest.mark.asyncio()
    async def test_initialize_bot_with_persistence(self):
        """Test initialize_bot creates persistence when enabled."""
        from src.telegram_bot.initialization import initialize_bot

        with (
            patch("src.telegram_bot.initialization.ApplicationBuilder") as mock_builder,
            patch(
                "telegram.ext.PicklePersistence"
            ) as mock_persistence,
            patch("src.telegram_bot.initialization.profile_manager") as mock_profiles,
            patch("src.telegram_bot.initialization.configure_admin_ids") as mock_admin,
            patch("src.telegram_bot.initialization.setup_error_handler"),
            patch("src.telegram_bot.initialization.register_global_exception_handlers"),
            patch("src.telegram_bot.initialization.setup_signal_handlers"),
        ):
            mock_profiles.get_admin_ids.return_value = set()
            mock_admin.return_value = []

            mock_app = MagicMock()
            builder_chain = MagicMock()
            builder_chain.token.return_value = builder_chain
            builder_chain.concurrent_updates.return_value = builder_chain
            builder_chain.connection_pool_size.return_value = builder_chain
            builder_chain.persistence.return_value = builder_chain
            builder_chain.build.return_value = mock_app
            mock_builder.return_value = builder_chain

            await initialize_bot("test_token", setup_persistence=True)

            mock_persistence.assert_called_once()

    @pytest.mark.asyncio()
    async def test_initialize_bot_uses_admin_ids_from_profiles(self):
        """Test initialize_bot gets admin IDs from profile manager."""
        from src.telegram_bot.initialization import initialize_bot

        with (
            patch("src.telegram_bot.initialization.ApplicationBuilder") as mock_builder,
            patch("src.telegram_bot.initialization.profile_manager") as mock_profiles,
            patch("src.telegram_bot.initialization.configure_admin_ids") as mock_admin,
            patch(
                "src.telegram_bot.initialization.setup_error_handler"
            ) as mock_setup_error,
            patch("src.telegram_bot.initialization.register_global_exception_handlers"),
            patch("src.telegram_bot.initialization.setup_signal_handlers"),
        ):
            mock_profiles.get_admin_ids.return_value = {123, 456}
            mock_admin.return_value = []

            mock_app = MagicMock()
            mock_builder.return_value.token.return_value.concurrent_updates.return_value.connection_pool_size.return_value.build.return_value = (
                mock_app
            )

            await initialize_bot("test_token", setup_persistence=False)

            # Admin IDs from profiles should be used
            mock_setup_error.assert_called_once()
            call_args = mock_setup_error.call_args
            assert 123 in call_args[0][1] or 456 in call_args[0][1]


class TestSetupBotCommands:
    """Tests for setup_bot_commands function."""

    @pytest.mark.asyncio()
    async def test_setup_bot_commands_registers_english_commands(self):
        """Test setup_bot_commands registers English commands."""
        from src.telegram_bot.initialization import setup_bot_commands

        mock_bot = AsyncMock()

        await setup_bot_commands(mock_bot)

        # Should call set_my_commands with language_code="en"
        calls = [
            call
            for call in mock_bot.set_my_commands.call_args_list
            if call[1].get("language_code") == "en"
        ]
        assert len(calls) == 1

    @pytest.mark.asyncio()
    async def test_setup_bot_commands_registers_russian_commands(self):
        """Test setup_bot_commands registers Russian commands."""
        from src.telegram_bot.initialization import setup_bot_commands

        mock_bot = AsyncMock()

        await setup_bot_commands(mock_bot)

        # Should call set_my_commands with language_code="ru"
        calls = [
            call
            for call in mock_bot.set_my_commands.call_args_list
            if call[1].get("language_code") == "ru"
        ]
        assert len(calls) == 1

    @pytest.mark.asyncio()
    async def test_setup_bot_commands_registers_default_commands(self):
        """Test setup_bot_commands registers default commands."""
        from src.telegram_bot.initialization import setup_bot_commands

        mock_bot = AsyncMock()

        await setup_bot_commands(mock_bot)

        # Should also call without language_code for default
        assert mock_bot.set_my_commands.call_count >= 3

    @pytest.mark.asyncio()
    async def test_setup_bot_commands_handles_api_error(self):
        """Test setup_bot_commands handles API errors gracefully."""
        from src.telegram_bot.initialization import setup_bot_commands

        mock_bot = AsyncMock()
        mock_bot.set_my_commands.side_effect = Exception("API Error")

        # Should not raise
        await setup_bot_commands(mock_bot)

    @pytest.mark.asyncio()
    async def test_setup_bot_commands_includes_standard_commands(self):
        """Test setup_bot_commands includes standard bot commands."""
        from src.telegram_bot.initialization import setup_bot_commands

        mock_bot = AsyncMock()

        await setup_bot_commands(mock_bot)

        # Check that commands include standard ones (only basic commands are registered)
        first_call = mock_bot.set_my_commands.call_args_list[0]
        commands = first_call[0][0]
        command_names = [cmd.command for cmd in commands]

        assert "start" in command_names
        assert "help" in command_names
        assert "settings" in command_names
        # Note: balance and other commands are accessed via menu buttons, not registered as bot commands


class TestSetupSignalHandlers:
    """Tests for setup_signal_handlers function."""

    def test_setup_signal_handlers_on_unix(self):
        """Test setup_signal_handlers registers handlers on Unix."""
        from src.telegram_bot.initialization import setup_signal_handlers

        mock_application = MagicMock()

        with (
            patch("platform.system", return_value="Linux"),
            patch("asyncio.get_event_loop") as mock_get_loop,
        ):
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            setup_signal_handlers(mock_application)

            # Should add signal handlers on Unix
            assert mock_loop.add_signal_handler.called

    def test_setup_signal_handlers_on_windows(self):
        """Test setup_signal_handlers skips handlers on Windows."""
        from src.telegram_bot.initialization import setup_signal_handlers

        mock_application = MagicMock()

        with (
            patch("platform.system", return_value="Windows"),
            patch("asyncio.get_event_loop") as mock_get_loop,
        ):
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            setup_signal_handlers(mock_application)

            # Should not add signal handlers on Windows
            mock_loop.add_signal_handler.assert_not_called()

    def test_setup_signal_handlers_handles_not_implemented_error(self):
        """Test setup_signal_handlers handles NotImplementedError."""
        from src.telegram_bot.initialization import setup_signal_handlers

        mock_application = MagicMock()

        with (
            patch("platform.system", return_value="Linux"),
            patch("asyncio.get_event_loop") as mock_get_loop,
        ):
            mock_loop = MagicMock()
            mock_loop.add_signal_handler.side_effect = NotImplementedError()
            mock_get_loop.return_value = mock_loop

            # Should not raise
            setup_signal_handlers(mock_application)


class TestRegisterHandlers:
    """Tests for register_handlers function."""

    def test_register_handlers_registers_command_handlers(self):
        """Test register_handlers registers command handlers."""
        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()
        command_handlers = {
            "start": MagicMock(),
            "help": MagicMock(),
        }

        register_handlers(mock_application, command_handlers=command_handlers)

        assert mock_application.add_handler.call_count == 2

    def test_register_handlers_registers_callback_handlers(self):
        """Test register_handlers registers callback query handlers."""
        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()
        callback_handlers = [
            ("^callback_1$", MagicMock()),
            ("^callback_2$", MagicMock()),
        ]

        register_handlers(mock_application, callback_handlers=callback_handlers)

        assert mock_application.add_handler.call_count == 2

    def test_register_handlers_registers_message_handlers(self):
        """Test register_handlers registers message handlers."""
        from telegram.ext import filters

        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()
        mock_handler = MagicMock()
        message_handlers = [
            (filters.TEXT & ~filters.COMMAND, mock_handler),
        ]

        register_handlers(mock_application, message_handlers=message_handlers)

        assert mock_application.add_handler.call_count == 1

    def test_register_handlers_registers_conversation_handlers(self):
        """Test register_handlers registers conversation handlers."""
        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()
        mock_conv_handler = MagicMock()
        conversation_handlers = [mock_conv_handler]

        register_handlers(mock_application, conversation_handlers=conversation_handlers)

        mock_application.add_handler.assert_called_once_with(mock_conv_handler)

    def test_register_handlers_with_all_handler_types(self):
        """Test register_handlers registers all handler types."""
        from telegram.ext import filters

        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()
        command_handlers = {"start": MagicMock()}
        callback_handlers = [("^cb$", MagicMock())]
        message_handlers = [(filters.TEXT, MagicMock())]
        conversation_handlers = [MagicMock()]

        register_handlers(
            mock_application,
            command_handlers=command_handlers,
            message_handlers=message_handlers,
            callback_handlers=callback_handlers,
            conversation_handlers=conversation_handlers,
        )

        assert mock_application.add_handler.call_count == 4

    def test_register_handlers_with_no_handlers(self):
        """Test register_handlers with no handlers does nothing."""
        from src.telegram_bot.initialization import register_handlers

        mock_application = MagicMock()

        register_handlers(mock_application)

        mock_application.add_handler.assert_not_called()


class TestInitializeServices:
    """Tests for initialize_services function."""

    @pytest.mark.asyncio()
    async def test_initialize_services_creates_api_client(self):
        """Test initialize_services creates DMarket API client."""
        from src.telegram_bot.initialization import initialize_services

        mock_application = MagicMock()
        mock_application.bot_data = {}

        with patch(
            "src.telegram_bot.initialization.create_api_client_from_env"
        ) as mock_create:
            mock_api = MagicMock()
            mock_create.return_value = mock_api

            await initialize_services(mock_application)

            assert mock_application.bot_data["dmarket_api"] == mock_api

    @pytest.mark.asyncio()
    async def test_initialize_services_handles_api_creation_error(self):
        """Test initialize_services handles API creation error."""
        from src.telegram_bot.initialization import initialize_services

        mock_application = MagicMock()
        mock_application.bot_data = {}

        with patch(
            "src.telegram_bot.initialization.create_api_client_from_env"
        ) as mock_create:
            mock_create.side_effect = Exception("API Error")

            # Should not raise
            await initialize_services(mock_application)

            # API should not be in bot_data
            assert "dmarket_api" not in mock_application.bot_data


class TestGetBotToken:
    """Tests for get_bot_token function."""

    def test_get_bot_token_returns_token_from_env(self):
        """Test get_bot_token returns token from environment."""
        from src.telegram_bot.initialization import get_bot_token

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token_123"}):
            token = get_bot_token()
            assert token == "test_token_123"

    def test_get_bot_token_raises_when_missing(self):
        """Test get_bot_token raises ValueError when token is missing."""
        from src.telegram_bot.initialization import get_bot_token

        with patch.dict(os.environ, {}, clear=True):
            # Remove TELEGRAM_BOT_TOKEN if it exists
            if "TELEGRAM_BOT_TOKEN" in os.environ:
                del os.environ["TELEGRAM_BOT_TOKEN"]

            with pytest.raises(ValueError, match="Не указан токен"):
                get_bot_token()


class TestSetupAndRunBot:
    """Tests for setup_and_run_bot function."""

    @pytest.mark.asyncio()
    async def test_setup_and_run_bot_creates_log_directory(self, tmp_path):
        """Test setup_and_run_bot creates logs directory."""
        from src.telegram_bot.initialization import setup_and_run_bot

        log_file = str(tmp_path / "logs" / "test.log")

        with (
            patch("src.telegram_bot.initialization.setup_logging"),
            patch(
                "src.telegram_bot.initialization.get_bot_token",
                return_value="test_token",
            ),
            patch("src.telegram_bot.initialization.initialize_bot") as mock_init,
            patch("src.telegram_bot.initialization.register_handlers"),
            patch("src.telegram_bot.initialization.start_bot") as mock_start,
            patch("os.makedirs") as mock_makedirs,
        ):
            mock_init.return_value = MagicMock()
            mock_start.side_effect = KeyboardInterrupt()

            try:
                await setup_and_run_bot(
                    token="test_token",
                    log_file=log_file,
                )
            except KeyboardInterrupt:
                pass

            mock_makedirs.assert_called_once_with("logs", exist_ok=True)

    @pytest.mark.asyncio()
    async def test_setup_and_run_bot_uses_provided_token(self):
        """Test setup_and_run_bot uses provided token."""
        from src.telegram_bot.initialization import setup_and_run_bot

        with (
            patch("src.telegram_bot.initialization.setup_logging"),
            patch("src.telegram_bot.initialization.initialize_bot") as mock_init,
            patch("src.telegram_bot.initialization.register_handlers"),
            patch("src.telegram_bot.initialization.start_bot") as mock_start,
            patch("os.makedirs"),
        ):
            mock_init.return_value = MagicMock()
            mock_start.side_effect = KeyboardInterrupt()

            try:
                await setup_and_run_bot(token="custom_token")
            except KeyboardInterrupt:
                pass

            mock_init.assert_called_once()
            assert mock_init.call_args[0][0] == "custom_token"

    @pytest.mark.asyncio()
    async def test_setup_and_run_bot_gets_token_from_env_when_none(self):
        """Test setup_and_run_bot gets token from environment when None."""
        from src.telegram_bot.initialization import setup_and_run_bot

        with (
            patch("src.telegram_bot.initialization.setup_logging"),
            patch(
                "src.telegram_bot.initialization.get_bot_token",
                return_value="env_token",
            ) as mock_get_token,
            patch("src.telegram_bot.initialization.initialize_bot") as mock_init,
            patch("src.telegram_bot.initialization.register_handlers"),
            patch("src.telegram_bot.initialization.start_bot") as mock_start,
            patch("os.makedirs"),
        ):
            mock_init.return_value = MagicMock()
            mock_start.side_effect = KeyboardInterrupt()

            try:
                await setup_and_run_bot(token=None)
            except KeyboardInterrupt:
                pass

            mock_get_token.assert_called_once()


class TestInitializeBotApplicationAlias:
    """Tests for initialize_bot_application alias."""

    def test_initialize_bot_application_is_alias(self):
        """Test initialize_bot_application is an alias for initialize_bot."""
        from src.telegram_bot.initialization import (
            initialize_bot,
            initialize_bot_application,
        )

        assert initialize_bot_application is initialize_bot
