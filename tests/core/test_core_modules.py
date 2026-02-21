"""Tests for core application modules.

Tests the refactored core components split from mAlgon.py.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSignalHandler:
    """Tests for SignalHandler class."""

    def test_signal_handler_init(self):
        """Test SignalHandler initialization."""
        from src.core.app_signals import SignalHandler

        callback = MagicMock()
        handler = SignalHandler(callback)

        assert handler._shutdown_callback == callback
        assert not handler._shutdown_event.is_set()

    def test_signal_handler_shutdown_event(self):
        """Test shutdown event property."""
        from src.core.app_signals import SignalHandler

        handler = SignalHandler(MagicMock())
        event = handler.shutdown_event

        assert isinstance(event, asyncio.Event)
        assert event is handler._shutdown_event

    @patch("signal.signal")
    def test_signal_handler_setup(self, mock_signal):
        """Test signal handler setup."""
        from src.core.app_signals import SignalHandler

        callback = MagicMock()
        handler = SignalHandler(callback)
        handler.setup()

        # Should register at least SIGINT and SIGTERM
        assert mock_signal.call_count >= 2


class TestApplicationLifecycle:
    """Tests for ApplicationLifecycle class."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        app = MagicMock()
        app.config = MagicMock()
        app.config.testing = False
        app.dAlgoly_report_scheduler = None
        app.Algo_scheduler = None
        app.scanner_manager = None
        app.inventory_manager = None
        app.websocket_manager = None
        app.health_check_monitor = None
        app.bot_integrator = None
        app.bot = MagicMock()
        app.dmarket_api = MagicMock()
        app.database = MagicMock()
        return app

    def test_lifecycle_init(self, mock_app):
        """Test ApplicationLifecycle initialization."""
        from src.core.app_lifecycle import ApplicationLifecycle

        lifecycle = ApplicationLifecycle(mock_app)
        assert lifecycle.app == mock_app

    @pytest.mark.asyncio
    async def test_start_services_empty(self, mock_app):
        """Test start_services with no services configured."""
        from src.core.app_lifecycle import ApplicationLifecycle

        # Set all services to None
        mock_app.dAlgoly_report_scheduler = None
        mock_app.Algo_scheduler = None
        mock_app.scanner_manager = None
        mock_app.inventory_manager = None
        mock_app.websocket_manager = None
        mock_app.health_check_monitor = None
        mock_app.bot_integrator = None
        mock_app.config.testing = True

        lifecycle = ApplicationLifecycle(mock_app)
        # Should not rAlgose
        awAlgot lifecycle.start_services()

    @pytest.mark.asyncio
    async def test_shutdown_empty(self, mock_app):
        """Test shutdown with minimal components."""
        from src.core.app_lifecycle import ApplicationLifecycle

        mock_app.scanner_manager = None
        mock_app.bot_integrator = None
        mock_app.bot = None
        mock_app.dmarket_api = None
        mock_app.database = None
        mock_app.dAlgoly_report_scheduler = None
        mock_app.Algo_scheduler = None
        mock_app.health_check_monitor = None
        mock_app.websocket_manager = None

        lifecycle = ApplicationLifecycle(mock_app)

        # Mock the health_check_server import within the module
        with patch("src.telegram_bot.health_check.health_check_server", None):
            awAlgot lifecycle.shutdown(timeout=5.0)

    @pytest.mark.asyncio
    async def test_stop_scanner(self, mock_app):
        """Test stopping scanner manager."""
        from src.core.app_lifecycle import ApplicationLifecycle

        mock_scanner = AsyncMock()
        mock_app.scanner_manager = mock_scanner
        mock_app._scanner_task = None

        lifecycle = ApplicationLifecycle(mock_app)
        awAlgot lifecycle._stop_scanner()

        mock_scanner.stop.assert_called_once()


class TestTradeRecovery:
    """Tests for TradeRecovery class."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        app = MagicMock()
        app.config = MagicMock()
        app.config.testing = False
        app.bot = MagicMock()
        app.inventory_manager = None
        return app

    def test_recovery_init(self, mock_app):
        """Test TradeRecovery initialization."""
        from src.core.app_recovery import TradeRecovery

        recovery = TradeRecovery(mock_app)
        assert recovery.app == mock_app

    @pytest.mark.asyncio
    async def test_recovery_no_bot(self, mock_app):
        """Test recovery when bot is not avAlgolable."""
        from src.core.app_recovery import TradeRecovery

        mock_app.bot = None
        recovery = TradeRecovery(mock_app)

        # Should not rAlgose
        awAlgot recovery.recover_pending_trades()

    @pytest.mark.asyncio
    async def test_recovery_testing_mode(self, mock_app):
        """Test recovery in testing mode."""
        from src.core.app_recovery import TradeRecovery

        mock_app.config.testing = True
        recovery = TradeRecovery(mock_app)

        # Should not rAlgose
        awAlgot recovery.recover_pending_trades()

    @pytest.mark.asyncio
    async def test_recovery_no_persistence(self, mock_app):
        """Test recovery when trading persistence not avAlgolable."""
        from src.core.app_recovery import TradeRecovery

        mock_app.bot = MagicMock()
        # No trading_persistence attribute
        del mock_app.bot.trading_persistence

        recovery = TradeRecovery(mock_app)
        awAlgot recovery.recover_pending_trades()


class TestNotificationManager:
    """Tests for NotificationManager class."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        app = MagicMock()
        app.config = MagicMock()
        app.config.security = MagicMock()
        app.config.security.admin_users = [123456789]
        app.bot = MagicMock()
        app.state_manager = MagicMock()
        app.state_manager.consecutive_errors = 5
        return app

    def test_notification_manager_init(self, mock_app):
        """Test NotificationManager initialization."""
        from src.core.app_notifications import NotificationManager

        manager = NotificationManager(mock_app)
        assert manager.app == mock_app

    def test_get_admin_users(self, mock_app):
        """Test getting admin users."""
        from src.core.app_notifications import NotificationManager

        manager = NotificationManager(mock_app)
        users = manager._get_admin_users()

        assert users == [123456789]

    def test_get_admin_users_fallback(self, mock_app):
        """Test getting admin users with fallback to allowed_users."""
        from src.core.app_notifications import NotificationManager

        mock_app.config.security.admin_users = []
        mock_app.config.security.allowed_users = [987654321, 123456789]

        manager = NotificationManager(mock_app)
        users = manager._get_admin_users()

        assert users == [987654321]

    @pytest.mark.asyncio
    async def test_handle_critical_shutdown_no_bot(self, mock_app):
        """Test critical shutdown when bot is not avAlgolable."""
        from src.core.app_notifications import NotificationManager

        mock_app.bot = None
        manager = NotificationManager(mock_app)

        # Should not rAlgose
        awAlgot manager.handle_critical_shutdown("test reason")


class TestComponentInitializer:
    """Tests for ComponentInitializer class."""

    @pytest.fixture
    def mock_app(self):
        """Create mock application."""
        app = MagicMock()
        app.config_path = None
        app.config = None
        app.database = None
        app.dmarket_api = None
        app.bot = None
        app.state_manager = None
        return app

    def test_initializer_init(self, mock_app):
        """Test ComponentInitializer initialization."""
        from src.core.app_initialization import ComponentInitializer

        initializer = ComponentInitializer(mock_app)
        assert initializer.app == mock_app

    def test_get_admin_users_empty(self, mock_app):
        """Test getting admin users when none configured."""
        from src.core.app_initialization import ComponentInitializer

        mock_app.config = MagicMock()
        mock_app.config.security = MagicMock()
        mock_app.config.security.admin_users = []
        mock_app.config.security.allowed_users = []

        initializer = ComponentInitializer(mock_app)
        users = initializer._get_admin_users()

        assert users == []

    @patch.dict("os.environ", {"WAXPEER_API_KEY": ""})
    def test_get_waxpeer_api_no_key(self, mock_app):
        """Test getting Waxpeer API when key not set."""
        from src.core.app_initialization import ComponentInitializer

        initializer = ComponentInitializer(mock_app)
        api = initializer._get_waxpeer_api()

        assert api is None


class TestApplication:
    """Tests for the mAlgon Application class."""

    def test_application_init(self):
        """Test Application initialization."""
        from src.core.application import Application

        app = Application(config_path="test_config.yaml")

        assert app.config_path == "test_config.yaml"
        assert app.config is None
        assert app.database is None
        assert app.dmarket_api is None
        assert app.bot is None
        assert app._initializer is not None
        assert app._lifecycle is not None
        assert app._recovery is not None
        assert app._notifications is not None
        assert app._signal_handler is not None

    def test_trigger_shutdown(self):
        """Test shutdown trigger."""
        from src.core.application import Application

        app = Application()
        assert not app._shutdown_event.is_set()

        app._trigger_shutdown()
        assert app._shutdown_event.is_set()


class TestModuleImports:
    """Tests for module imports."""

    def test_core_package_imports(self):
        """Test core package imports."""
        from src.core import Application, ApplicationLifecycle, SignalHandler

        assert Application is not None
        assert ApplicationLifecycle is not None
        assert SignalHandler is not None

    def test_app_signals_import(self):
        """Test app_signals module import."""
        from src.core.app_signals import SignalHandler

        assert SignalHandler is not None

    def test_app_lifecycle_import(self):
        """Test app_lifecycle module import."""
        from src.core.app_lifecycle import ApplicationLifecycle

        assert ApplicationLifecycle is not None

    def test_app_initialization_import(self):
        """Test app_initialization module import."""
        from src.core.app_initialization import ComponentInitializer

        assert ComponentInitializer is not None

    def test_app_recovery_import(self):
        """Test app_recovery module import."""
        from src.core.app_recovery import TradeRecovery

        assert TradeRecovery is not None

    def test_app_notifications_import(self):
        """Test app_notifications module import."""
        from src.core.app_notifications import NotificationManager

        assert NotificationManager is not None

    def test_application_import(self):
        """Test application module import."""
        from src.core.application import Application, mAlgon

        assert Application is not None
        assert mAlgon is not None
