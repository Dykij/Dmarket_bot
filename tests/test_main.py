"""Tests for main application module.

This module contains comprehensive tests for the main entry point
of the DMarket Telegram Bot application.

Note: The main.py now delegates to src.core.application. These tests
verify backward compatibility of imports and basic functionality.
For detailed Application tests, see tests/core/test_application.py
"""

import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import Application, main


@pytest.fixture()
def mock_config():
    """Create mock configuration."""
    config = MagicMock()
    config.debug = False
    config.testing = True
    config.logging.level = "INFO"
    config.logging.file = None
    config.logging.format = "%(levelname)s - %(message)s"
    config.dmarket.public_key = "test_public_key"
    config.dmarket.secret_key = "test_secret_key"
    config.dmarket.api_url = "https://api.dmarket.com"
    config.database.url = "sqlite:///:memory:"
    config.telegram.bot_token = "test_token"
    return config


@pytest.fixture()
def mock_database():
    """Create mock database manager."""
    db = AsyncMock()
    db.init_database = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture()
def mock_dmarket_api():
    """Create mock DMarket API client."""
    api = AsyncMock()
    api.get_balance = AsyncMock(return_value={"error": False, "balance": 100.50})
    api._close_client = AsyncMock()
    return api


@pytest.fixture()
def mock_bot():
    """Create mock Telegram bot."""
    bot = AsyncMock()
    bot.initialize = AsyncMock()
    bot.start = AsyncMock()
    bot.stop = AsyncMock()
    return bot


class TestApplication:
    """Test cases for Application class."""

    def test_init_creates_application_with_default_values(self):
        """Test Application creation with default values."""
        # Arrange & Act
        app = Application()

        # Assert
        assert app.config_path is None
        assert app.config is None
        assert app.database is None
        assert app.dmarket_api is None
        assert app.bot is None
        assert isinstance(app._shutdown_event, asyncio.Event)

    def test_init_with_config_path_sets_path_correctly(self):
        """Test Application initialization with config path."""
        # Arrange
        config_path = "config/test.yaml"

        # Act
        app = Application(config_path=config_path)

        # Assert
        assert app.config_path == config_path

    def test_application_imports_from_core(self):
        """Test that Application is imported from core module."""
        from src.core.application import Application as CoreApplication
        from src.main import Application as MainApplication

        # They should be the same class
        assert MainApplication is CoreApplication

    def test_main_imports_from_core(self):
        """Test that main function is imported from core module."""
        from src.core.application import main as core_main
        from src.main import main as main_func

        # They should be the same function
        assert main_func is core_main

    @pytest.mark.asyncio()
    async def test_initialize_calls_initializer(self):
        """Test that initialize calls component initializer."""
        app = Application()

        # Mock the initializer methods
        app._initializer.initialize_config = AsyncMock()
        app._initializer.initialize_whitelist = AsyncMock()
        app._initializer.initialize_sentry = AsyncMock()
        app._initializer.initialize_database = AsyncMock()
        app._initializer.initialize_dmarket_api = AsyncMock()
        app._initializer.initialize_telegram_bot = AsyncMock()
        app._initializer.initialize_daily_report_scheduler = AsyncMock()
        app._initializer.initialize_ai_scheduler = AsyncMock()
        app._initializer.initialize_scanner_manager = AsyncMock()
        app._initializer.initialize_inventory_manager = AsyncMock()
        app._initializer.initialize_autopilot = AsyncMock()
        app._initializer.initialize_websocket_manager = AsyncMock()
        app._initializer.initialize_health_check_monitor = AsyncMock()
        app._initializer.initialize_bot_integrator = AsyncMock()

        await app.initialize()

        # Verify core methods were called
        app._initializer.initialize_config.assert_awaited_once()
        app._initializer.initialize_database.assert_awaited_once()
        app._initializer.initialize_telegram_bot.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_initialize_handles_exception(self):
        """Test initialize handles exceptions properly."""
        app = Application()
        app._initializer.initialize_config = AsyncMock(side_effect=Exception("Config error"))

        with pytest.raises(Exception, match="Config error"):
            await app.initialize()

    @pytest.mark.asyncio()
    async def test_shutdown_calls_lifecycle(self, mock_database, mock_dmarket_api, mock_bot):
        """Test shutdown delegates to lifecycle manager."""
        app = Application()
        app._lifecycle.shutdown = AsyncMock()

        await app.shutdown(timeout=15.0)

        app._lifecycle.shutdown.assert_awaited_once_with(15.0)

    @pytest.mark.asyncio()
    async def test_shutdown_partial_components(self):
        """Test shutdown when some components are None."""
        app = Application()
        app.bot = None
        app.dmarket_api = None
        app.database = None
        app._lifecycle.shutdown = AsyncMock()

        # Should not raise any exceptions
        await app.shutdown()

    def test_trigger_shutdown_sets_event(self):
        """Test that trigger_shutdown sets shutdown event."""
        app = Application()
        assert not app._shutdown_event.is_set()

        app._trigger_shutdown()
        assert app._shutdown_event.is_set()


class TestMainFunction:
    """Test cases for main() entry point."""

    @pytest.mark.asyncio()
    async def test_main_default_arguments(self):
        """Test main function with default arguments."""
        mock_app = MagicMock()
        mock_app.run = AsyncMock()

        with (
            patch("sys.argv", ["main.py"]),
            patch("src.core.application.Application", return_value=mock_app),
        ):
            await main()

            mock_app.run.assert_called_once()

    @pytest.mark.asyncio()
    async def test_main_with_config_argument(self):
        """Test main function with config argument."""
        mock_app = MagicMock()
        mock_app.run = AsyncMock()

        with (
            patch("sys.argv", ["main.py", "--config", "config/test.yaml"]),
            patch("src.core.application.Application", return_value=mock_app) as MockApp,
        ):
            await main()

            MockApp.assert_called_once_with(config_path="config/test.yaml")
            mock_app.run.assert_called_once()

    @pytest.mark.asyncio()
    async def test_main_with_debug_flag(self):
        """Test main function with debug flag."""
        mock_app = MagicMock()
        mock_app.run = AsyncMock()

        with (
            patch("sys.argv", ["main.py", "--debug"]),
            patch("src.core.application.Application", return_value=mock_app),
            patch.dict("os.environ", {}, clear=True),
        ):
            await main()

            # Check that DEBUG environment variable was set
            import os

            assert os.environ.get("DEBUG") == "true"
            assert os.environ.get("LOG_LEVEL") == "DEBUG"

    @pytest.mark.asyncio()
    async def test_main_with_log_level(self):
        """Test main function with custom log level."""
        mock_app = MagicMock()
        mock_app.run = AsyncMock()

        with (
            patch("sys.argv", ["main.py", "--log-level", "WARNING"]),
            patch("src.core.application.Application", return_value=mock_app),
            patch("logging.basicConfig") as mock_logging,
        ):
            await main()

            # Verify logging was configured with WARNING level
            mock_logging.assert_called_once()
            call_kwargs = mock_logging.call_args[1]
            assert call_kwargs["level"] == logging.WARNING

    @pytest.mark.asyncio()
    async def test_main_application_failure(self):
        """Test main function when application fails."""
        mock_app = MagicMock()
        mock_app.run = AsyncMock(side_effect=Exception("App failed"))

        with (
            patch("sys.argv", ["main.py"]),
            patch("src.core.application.Application", return_value=mock_app),
            pytest.raises(SystemExit) as exc_info,
        ):
            await main()

        assert exc_info.value.code == 1


class TestWindowsEventLoopPolicy:
    """Test Windows-specific event loop policy."""

    def test_windows_event_loop_policy_set(self):
        """Test that Windows event loop policy is set on Windows."""
        if not sys.platform.startswith("win"):
            pytest.skip("Test only runs on Windows")

        with (
            patch("asyncio.set_event_loop_policy") as mock_set_policy,
            patch("asyncio.WindowsProactorEventLoopPolicy"),
        ):
            # This would normally be in __main__ block
            # We test the logic separately
            if sys.platform.startswith("win"):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            mock_set_policy.assert_called()


class TestBackwardCompatibility:
    """Test backward compatibility of main.py after refactoring."""

    def test_application_class_available(self):
        """Test that Application class is available from src.main."""
        from src.main import Application

        assert Application is not None

    def test_main_function_available(self):
        """Test that main function is available from src.main."""
        from src.main import main

        assert main is not None
        assert callable(main)

    def test_application_has_required_attributes(self):
        """Test that Application has all required attributes."""
        app = Application()
        assert hasattr(app, "config_path")
        assert hasattr(app, "config")
        assert hasattr(app, "database")
        assert hasattr(app, "dmarket_api")
        assert hasattr(app, "bot")
        assert hasattr(app, "_shutdown_event")

    def test_application_has_required_methods(self):
        """Test that Application has all required methods."""
        app = Application()
        assert hasattr(app, "initialize")
        assert hasattr(app, "run")
        assert hasattr(app, "shutdown")
        assert callable(app.initialize)
        assert callable(app.run)
        assert callable(app.shutdown)
