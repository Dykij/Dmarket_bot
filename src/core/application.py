"""
application.py — Main application class.
"""

import asyncio
from typing import Any

from src.core.app_initialization import ComponentInitializer
from src.core.app_lifecycle import ApplicationLifecycle
from src.core.app_notifications import NotificationManager
from src.core.app_recovery import TradeRecovery
from src.core.app_signals import SignalHandler


class Application:
    """Main application orchestrator."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path
        self.config: Any = None
        self._shutdown_event = asyncio.Event()
        self._signal_handler = SignalHandler(shutdown_callback=self._trigger_shutdown)
        self._lifecycle = ApplicationLifecycle(self)
        self._recovery = TradeRecovery(self)
        self._notifications = NotificationManager(bot=None, config=None)
        self._initializer = ComponentInitializer(config=None)

        # Optional components
        self.bot: Any = None
        self.dmarket_api: Any = None
        self.database: Any = None
        self.scanner_manager: Any = None
        self.daily_report_scheduler: Any = None
        self.Algo_scheduler: Any = None
        self.inventory_manager: Any = None
        self.websocket_manager: Any = None
        self.health_check_monitor: Any = None
        self.bot_integrator: Any = None

    async def initialize(self) -> None:
        """Initialize application components."""
        await self._initializer.initialize_config()
        await self._initializer.initialize_whitelist()
        await self._initializer.initialize_sentry()
        await self._initializer.initialize_database()
        await self._initializer.initialize_dmarket_api()
        await self._initializer.initialize_telegram_bot()
        await self._initializer.initialize_daily_report_scheduler()
        await self._initializer.initialize_Algo_scheduler()
        await self._initializer.initialize_scanner_manager()
        await self._initializer.initialize_inventory_manager()
        await self._initializer.initialize_autopilot()
        await self._initializer.initialize_websocket_manager()
        await self._initializer.initialize_health_check_monitor()
        await self._initializer.initialize_bot_integrator()

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Graceful shutdown."""
        await self._lifecycle.shutdown(timeout)

    def _trigger_shutdown(self) -> None:
        """Trigger shutdown via signal."""
        self._shutdown_event.set()

    async def _handle_critical_shutdown(self, reason: str = "") -> None:
        """Handle critical shutdown."""
        await self._notifications.handle_critical_shutdown(reason)


def main() -> None:
    """Entry point."""
    app = Application()
    asyncio.run(app.initialize())
