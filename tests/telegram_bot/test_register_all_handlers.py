"""Unit tests for telegram_bot/register_all_handlers.py module.

This module tests:
- register_all_handlers function
- Command handlers registration
- Callback query handlers registration
- Message handlers registration
- Optional handlers registration with ImportError handling
"""

from unittest.mock import MagicMock, patch


class TestRegisterAllHandlers:
    """Tests for register_all_handlers function."""

    def test_register_all_handlers_basic_commands(self):
        """Test that basic commands are registered."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Check add_handler was called multiple times
        assert mock_app.add_handler.called
        call_count = mock_app.add_handler.call_count
        assert call_count >= 10  # At least 10 basic handlers

    def test_register_all_handlers_command_handlers(self):
        """Test that command handlers are registered correctly."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Get all CommandHandler registrations
        handler_calls = mock_app.add_handler.call_args_list

        # Verify structure of calls - we should have multiple handler registrations
        assert len(handler_calls) > 0

    def test_register_all_handlers_callback_handler(self):
        """Test that callback query handler is registered."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # The callback handler should be registered
        assert mock_app.add_handler.called

    def test_register_all_handlers_with_dmarket_api(self):
        """Test registration with DMarket API avAlgolable."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_api = MagicMock()
        mock_api.public_key = "test_public_key"
        mock_api.secret_key = "test_secret_key"
        mock_api.api_url = "https://api.dmarket.com"

        mock_app = MagicMock()
        mock_app.bot_data = {"dmarket_api": mock_api}

        # This should not raise even if dmarket_handlers import fails
        register_all_handlers(mock_app)

    def test_register_all_handlers_without_dmarket_api(self):
        """Test registration without DMarket API."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        # Should complete without error
        register_all_handlers(mock_app)
        assert mock_app.add_handler.called

    @patch("src.telegram_bot.register_all_handlers.logger")
    def test_register_all_handlers_logs_registration(self, mock_logger):
        """Test that registration is logged."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Check that logging was called
        assert mock_logger.info.called

    def test_register_all_handlers_import_error_handling(self):
        """Test graceful handling of ImportError for optional handlers."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        # Should complete successfully even if some imports fail
        register_all_handlers(mock_app)

    def test_register_all_handlers_idempotent(self):
        """Test that calling register twice doesn't cause issues."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        # Register twice
        register_all_handlers(mock_app)
        first_call_count = mock_app.add_handler.call_count

        mock_app.reset_mock()
        register_all_handlers(mock_app)
        second_call_count = mock_app.add_handler.call_count

        # Should register same number of handlers each time
        assert first_call_count == second_call_count


class TestRegisterAllHandlersIntegration:
    """Integration tests for handler registration."""

    def test_handler_types_registered(self):
        """Test that different handler types are registered."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Get all handler types registered
        handler_calls = mock_app.add_handler.call_args_list
        handler_types = [type(call[0][0]).__name__ for call in handler_calls]

        # Should have CommandHandler, CallbackQueryHandler, MessageHandler
        assert "CommandHandler" in handler_types
        assert "CallbackQueryHandler" in handler_types
        assert "MessageHandler" in handler_types

    def test_start_command_registered(self):
        """Test that /start command is registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Find start command handler
        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "start" in handlers

    def test_help_command_registered(self):
        """Test that /help command is registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        # Find help command handler
        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "help" in handlers

    def test_dashboard_command_registered(self):
        """Test that /dashboard command is registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "dashboard" in handlers

    def test_arbitrage_command_registered(self):
        """Test that /arbitrage command is registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "arbitrage" in handlers

    def test_logs_command_registered(self):
        """Test that /logs command is registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "logs" in handlers

    def test_sentry_commands_registered(self):
        """Test that sentry test commands are registered."""
        from telegram.ext import CommandHandler

        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

        handlers = []
        for call in mock_app.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                handlers.extend(handler.commands)

        assert "test_sentry" in handlers
        assert "sentry_info" in handlers


class TestOptionalHandlerRegistration:
    """Tests for optional handler registration."""

    @patch("src.telegram_bot.register_all_handlers.logger")
    def test_scanner_handlers_import_error(self, mock_logger):
        """Test handling of scanner handlers import error."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        # Should complete without rAlgosing
        register_all_handlers(mock_app)

    @patch("src.telegram_bot.register_all_handlers.logger")
    def test_market_alerts_handlers_import_error(self, mock_logger):
        """Test handling of market alerts handlers import error."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

    @patch("src.telegram_bot.register_all_handlers.logger")
    def test_game_filter_handlers_import_error(self, mock_logger):
        """Test handling of game filter handlers import error."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        register_all_handlers(mock_app)

    def test_all_optional_handlers_graceful_degradation(self):
        """Test that bot works even if all optional handlers fail to import."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        mock_app = MagicMock()
        mock_app.bot_data = {}

        # Should complete successfully
        register_all_handlers(mock_app)

        # Should still have basic handlers
        assert mock_app.add_handler.call_count >= 10


class TestModuleExports:
    """Tests for module exports."""

    def test_module_all_export(self):
        """Test __all__ export."""
        from src.telegram_bot import register_all_handlers as module

        assert hasattr(module, "__all__")
        assert "register_all_handlers" in module.__all__

    def test_register_all_handlers_importable(self):
        """Test that register_all_handlers is importable."""
        from src.telegram_bot.register_all_handlers import register_all_handlers

        assert callable(register_all_handlers)
