"""Tests for src/core/application module.

Tests for the main Application class and its lifecycle management.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestApplication:
    """Tests for Application class."""

    def test_application_init(self):
        """Test Application initialization."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application(config_path="/path/to/config.yaml")

            assert app.config_path == "/path/to/config.yaml"
            assert app.config is None
            assert app.database is None
            assert app.bot is None
            assert app._shutdown_event is not None

    def test_application_init_without_config(self):
        """Test Application initialization without config path."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()

            assert app.config_path is None

    def test_trigger_shutdown(self):
        """Test trigger_shutdown sets shutdown event."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()
            assert not app._shutdown_event.is_set()

            app._trigger_shutdown()
            assert app._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_initialize_calls_initializer(self):
        """Test initialize calls component initializer methods."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()

            # Mock all initializer methods
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

            # Verify all methods were called
            app._initializer.initialize_config.assert_awaited_once()
            app._initializer.initialize_database.assert_awaited_once()
            app._initializer.initialize_telegram_bot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_handles_exception(self):
        """Test initialize handles exceptions properly."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()
            app._initializer.initialize_config = AsyncMock(
                side_effect=Exception("Config error")
            )

            with pytest.raises(Exception, match="Config error"):
                await app.initialize()

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test graceful shutdown."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()
            app._lifecycle.shutdown = AsyncMock()

            await app.shutdown(timeout=10.0)

            app._lifecycle.shutdown.assert_awaited_once_with(10.0)

    @pytest.mark.asyncio
    async def test_handle_critical_shutdown(self):
        """Test critical shutdown handling."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            from src.core.application import Application

            app = Application()
            app._notifications.handle_critical_shutdown = AsyncMock()

            await app._handle_critical_shutdown("Test reason")

            app._notifications.handle_critical_shutdown.assert_awaited_once_with(
                "Test reason"
            )


class TestMain:
    """Tests for main entry point."""

    @pytest.mark.asyncio
    async def test_main_creates_application(self):
        """Test main creates and runs application."""
        with patch.dict("sys.modules", {"telegram.ext": MagicMock()}):
            with patch("sys.argv", ["main.py"]):
                with patch("src.core.application.Application") as mock_app_class:
                    mock_app = MagicMock()
                    mock_app.run = AsyncMock()
                    mock_app_class.return_value = mock_app

                    from src.core.application import main

                    await main()

                    mock_app.run.assert_awaited_once()
