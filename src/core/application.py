"""Main Application class - refactored version.

This module provides the main Application class that orchestrates
all bot components using the modular core components.
"""

import asyncio
import logging
import sys
import traceback as tb
from typing import Any

from telegram.ext import Application as TelegramApplication

from src.core.app_initialization import ComponentInitializer
from src.core.app_lifecycle import ApplicationLifecycle
from src.core.app_notifications import NotificationManager
from src.core.app_recovery import TradeRecovery
from src.core.app_signals import SignalHandler
from src.utils.config import Config
import structlog

logger = logging.getLogger(__name__)
bot_logger = structlog.get_logger(__name__)


class Application:
    """Main application class for DMarket Bot.

    This class orchestrates all bot components using modular core components:
    - ComponentInitializer: Handles initialization of all components
    - ApplicationLifecycle: Manages startup and shutdown sequences
    - SignalHandler: Handles OS signals for graceful shutdown
    - TradeRecovery: Recovers pending trades after restart
    - NotificationManager: Handles crash and shutdown notifications
    """

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize application.

        Args:
            config_path: Optional path to configuration file

        """
        self.config_path = config_path
        self.config: Config | None = None
        self.database: Any = None
        self.dmarket_api: Any = None
        self.bot: TelegramApplication | None = None
        self.state_manager: Any = None
        self.daily_report_scheduler: Any = None
        self.scanner_manager: Any = None
        self.inventory_manager: Any = None
        self.websocket_manager: Any = None
        self.health_check_monitor: Any = None
        self.ai_scheduler: Any = None
        self.bot_integrator: Any = None
        self.prometheus_server: Any = None
        self._scanner_task: asyncio.Task | None = None

        # Initialize core components
        self._initializer = ComponentInitializer(self)
        self._lifecycle = ApplicationLifecycle(self)
        self._recovery = TradeRecovery(self)
        self._notifications = NotificationManager(self)
        self._signal_handler = SignalHandler(self._trigger_shutdown)
        self._shutdown_event = asyncio.Event()

    def _trigger_shutdown(self) -> None:
        """Trigger shutdown event."""
        self._shutdown_event.set()

    async def initialize(self) -> None:
        """Initialize all application components."""
        try:
            # Step 1: Load configuration
            await self._initializer.initialize_config()

            # Step 2: Load whitelist
            await self._initializer.initialize_whitelist()

            # Step 3: Initialize Sentry
            await self._initializer.initialize_sentry()

            # Step 4: Initialize database
            await self._initializer.initialize_database()

            # Step 5: Initialize DMarket API
            await self._initializer.initialize_dmarket_api()

            # Step 6: Initialize Telegram bot
            await self._initializer.initialize_telegram_bot()

            # Step 7: Initialize Daily Report Scheduler
            await self._initializer.initialize_daily_report_scheduler()

            # Step 8: Initialize AI Scheduler
            await self._initializer.initialize_ai_scheduler()

            # Step 9: Initialize Scanner Manager
            await self._initializer.initialize_scanner_manager()

            # Step 10: Initialize Inventory Manager
            await self._initializer.initialize_inventory_manager()

            # Step 11: Initialize Autopilot
            await self._initializer.initialize_autopilot()

            # Step 12: Initialize WebSocket Manager
            await self._initializer.initialize_websocket_manager()

            # Step 13: Initialize Health Check Monitor
            await self._initializer.initialize_health_check_monitor()

            # Step 14: Initialize Bot Integrator
            await self._initializer.initialize_bot_integrator()

            # Step 15: Initialize Prometheus Exporter
            await self._initializer.initialize_prometheus_exporter()

            logger.info("Application initialization complete")

        except Exception as e:
            logger.exception(f"Failed to initialize application: {e}")
            raise

    async def run(self) -> None:
        """Run the application."""
        try:
            await self.initialize()

            # Setup signal handlers
            self._signal_handler.setup()

            # Start health check server
            from src.telegram_bot.health_check import health_check_server

            if health_check_server:
                health_check_server.update_status("starting")
                await health_check_server.start()

            logger.info("Starting DMarket Telegram Bot...")

            # Recover pending trades
            await self._recovery.recover_pending_trades()

            # Start all services
            await self._lifecycle.start_services()

            # Start the bot
            if self.bot:
                await self.bot.start()
                await self._start_bot_polling()

            # Wait for shutdown signal
            logger.info("Bot is running. Press Ctrl+C to stop.")
            await self._shutdown_event.wait()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.exception(f"Application error: {e}")

            # Log crash
            traceback_text = tb.format_exc()
            bot_logger.log_crash(
                error=e,
                traceback_text=traceback_text,
                context={"component": "main_application"},
            )

            # Send crash notifications
            await self._notifications.send_crash_notifications(
                error=e,
                traceback_text=traceback_text,
            )

            raise
        finally:
            await self.shutdown()

    async def _start_bot_polling(self) -> None:
        """Start bot polling or webhook."""
        from src.telegram_bot.health_check import health_check_server
        from src.telegram_bot.webhook import (
            WebhookConfig,
            should_use_polling,
            start_webhook,
        )

        webhook_config = WebhookConfig.from_env()

        if webhook_config and not should_use_polling():
            logger.info("🌐 Starting in WEBHOOK mode")
            try:
                await start_webhook(self.bot, webhook_config)
                if health_check_server:
                    health_check_server.update_status("running")
            except Exception as e:
                logger.exception(f"Failed to start webhook, falling back to polling: {e}")
                if self.bot.updater:
                    await self.bot.updater.start_polling()
                logger.info("📡 Bot polling started (fallback)")
        else:
            if self.bot.updater:
                await self.bot.updater.start_polling()
            logger.info("📡 Bot polling started")
            if health_check_server:
                health_check_server.update_status("running")

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the application.

        Args:
            timeout: Maximum time to wait for graceful shutdown

        """
        await self._lifecycle.shutdown(timeout)

    async def _handle_critical_shutdown(self, reason: str) -> None:
        """Handle critical shutdown event.

        Args:
            reason: Reason for critical shutdown

        """
        await self._notifications.handle_critical_shutdown(reason)


async def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="DMarket Telegram Bot")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Setup basic logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Override config with command line arguments
    if args.debug:
        import os

        os.environ["DEBUG"] = "true"
        os.environ["LOG_LEVEL"] = "DEBUG"

    # Create and run application
    app = Application(config_path=args.config)

    try:
        await app.run()
    except Exception as e:
        logger.critical(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
