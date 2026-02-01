"""Main entry point for DMarket Telegram Bot.

This module provides the main entry point for running the DMarket Telegram Bot,
including initialization, configuration loading, and graceful shutdown handling.
"""

import asyncio
import logging
import os
import signal
import sys

from telegram.ext import Application as TelegramApplication, ApplicationBuilder, PersistenceInput

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.scanner_manager import ScannerManager
from src.telegram_bot.health_check import health_check_server
from src.telegram_bot.notifier import send_crash_notification, send_critical_shutdown_notification
from src.telegram_bot.register_all_handlers import register_all_handlers
from src.utils.config import Config
from src.utils.daily_report_scheduler import DailyReportScheduler
from src.utils.database import DatabaseManager
from src.utils.logging_utils import BotLogger, setup_logging
from src.utils.sentry_integration import init_sentry
from src.utils.state_manager import StateManager


logger = logging.getLogger(__name__)
bot_logger = BotLogger(__name__)


class Application:
    """Main application class for DMarket Bot."""

    def __init__(self, config_path: str | None = None) -> None:
        """Initialize application.

        Args:
            config_path: Optional path to configuration file

        """
        self.config_path = config_path
        self.config: Config | None = None
        self.database: DatabaseManager | None = None
        self.dmarket_api: DMarketAPI | None = None
        self.bot: TelegramApplication | None = None
        self.state_manager: StateManager | None = None
        self.daily_report_scheduler: DailyReportScheduler | None = None
        self.scanner_manager: ScannerManager | None = None
        self.inventory_manager = None
        self.websocket_manager = None
        self.health_check_monitor = None
        self.ai_scheduler = None  # AI Training Scheduler
        self.bot_integrator = None  # Bot Integrator for all new improvements
        self._shutdown_event = asyncio.Event()
        self._scanner_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize all application components."""
        # Critical components - if these fail, the app cannot run
        await self._init_config_and_logging()
        await self._init_core_services()
        await self._init_dmarket_api()
        await self._init_telegram_bot()

        # Optional/Service components - app can run without them
        init_tasks = [
            ("Schedulers", self._init_schedulers),
            ("Scanner Manager", self._init_scanner_manager),
            ("Inventory & Trading", self._init_inventory_and_trading),
            ("WebSocket & Health", self._init_websocket_and_health),
            ("Bot Integrator", self._init_bot_integrator),
        ]

        for name, init_method in init_tasks:
            try:
                await init_method()
                logger.info(f"✅ {name} initialized successfully")
            except Exception as e:
                logger.error(f"⚠️ Failed to initialize {name}: {e}")
                if self.config and self.config.environment == "production":
                    # In production, maybe we want to know about these via Sentry
                    from src.utils.sentry_integration import capture_exception
                    capture_exception(e, tags={"component": name, "phase": "initialization"})

    async def run(self) -> None:
        """Run the application."""
        try:
            await self.initialize()

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start health check server (if enabled)
            if health_check_server:
                health_check_server.update_status("starting")
                await health_check_server.start()

            logger.info("Starting DMarket Telegram Bot...")

            # CRITICAL: Recover pending trades from database (NEW)
            # This ensures bot doesn't "forget" purchases after restart
            await self._recover_pending_trades()

            # Start Daily Report Scheduler
            if self.daily_report_scheduler:
                await self.daily_report_scheduler.start()
                logger.info("Daily Report Scheduler started")

            # Start AI Training Scheduler (nightly model training + data collection)
            if self.ai_scheduler:
                await self.ai_scheduler.start()
                logger.info("AI Training Scheduler started (nightly training at 03:00 UTC)")

            # Start Scanner Manager (background scanning)
            if self.scanner_manager and not self.config.testing:
                logger.info("Starting Scanner Manager background task...")

                # Configure which games to scan
                games_to_scan = getattr(
                    self.config, "arbitrage_games", ["csgo", "dota2", "rust", "tf2"]
                )
                arbitrage_level = getattr(self.config, "arbitrage_level", "medium")
                cleanup_interval = getattr(self.config, "cleanup_interval_hours", 6.0)

                self._scanner_task = asyncio.create_task(
                    self.scanner_manager.run_continuous(
                        games=games_to_scan,
                        level=arbitrage_level,
                        enable_cleanup=True,
                        cleanup_interval_hours=cleanup_interval,
                    )
                )

                logger.info(
                    f"Scanner Manager started: "
                    f"games={games_to_scan}, "
                    f"level={arbitrage_level}, "
                    f"cleanup_interval={cleanup_interval}h"
                )

            # Start Inventory Manager (Direct Buy - Undercutting)
            if (
                hasattr(self, "inventory_manager")
                and self.inventory_manager
                and not self.config.testing
            ):
                undercut_enabled = (
                    self.config.inventory.auto_sell
                    if self.config and hasattr(self.config, "inventory")
                    else False
                )
                if undercut_enabled:
                    logger.info("Starting Inventory Manager (Undercutting)...")
                    asyncio.create_task(self.inventory_manager.refresh_inventory_loop())
                    logger.info("Inventory Manager started - auto-repricing enabled")
                else:
                    logger.info("Inventory Manager initialized but undercutting is disabled")

            # Start WebSocket Listener
            if self.websocket_manager:
                logger.info("Starting WebSocket Listener...")
                await self.websocket_manager.start()
                logger.info("WebSocket Listener started - real-time updates enabled")

            # Start Health Check Monitor
            if self.health_check_monitor:
                logger.info("Starting Health Check Monitor...")
                asyncio.create_task(self.health_check_monitor.start())
                logger.info("Health Check Monitor started - 15min intervals")

            # Start Bot Integrator (all new improvements)
            if hasattr(self, "bot_integrator") and self.bot_integrator:
                logger.info("Starting Bot Integrator...")
                await self.bot_integrator.start()
                logger.info("Bot Integrator started - all improvements active")

            # Start the bot (webhook or polling)
            if self.bot is not None:
                await self.bot.start()

                # Check if webhook mode is enabled (Roadmap Task #1)
                from src.telegram_bot.webhook import (
                    WebhookConfig,
                    should_use_polling,
                    start_webhook,
                )

                webhook_config = WebhookConfig.from_env()

                # Use webhook if configured and not explicitly disabled
                if webhook_config and not should_use_polling():
                    logger.info("🌐 Starting in WEBHOOK mode")
                    try:
                        # Start webhook (this blocks until shutdown)
                        await start_webhook(self.bot, webhook_config)
                        health_check_server.update_status("running")
                    except Exception as e:
                        logger.exception(f"Failed to start webhook, falling back to polling: {e}")
                        # Fallback to polling
                        if self.bot.updater is not None:
                            await self.bot.updater.start_polling()
                        logger.info("📡 Bot polling started (fallback)")
                        health_check_server.update_status("running")
                else:
                    # Use polling (default for development)
                    if self.bot.updater is not None:
                        await self.bot.updater.start_polling()
                    logger.info("📡 Bot polling started")
                    if health_check_server:
                        health_check_server.update_status("running")

            # Wait for shutdown signal
            logger.info("Bot is running. Press Ctrl+C to stop.")
            await self._shutdown_event.wait()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.exception(f"Application error: {e}")

            # Log crash with BotLogger
            import traceback as tb

            traceback_text = tb.format_exc()
            bot_logger.log_crash(
                error=e,
                traceback_text=traceback_text,
                context={"component": "main_application"},
            )

            # Send crash notification to admins
            await self._send_crash_notifications(
                error=e,
                traceback_text=traceback_text,
            )

            raise
        finally:
            await self.shutdown()

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown the application.

        Args:
            timeout: Maximum time to wait for graceful shutdown (seconds)

        Roadmap Task #4: Graceful Shutdown
        """
        logger.info("=" * 60)
        logger.info("🛑 Initiating graceful shutdown...")
        logger.info("=" * 60)
        if health_check_server:
            health_check_server.update_status("stopping")

        # Set shutdown flag for scanners
        if hasattr(self, "_is_shutting_down"):
            self._is_shutting_down = True

        start_time = asyncio.get_event_loop().time()

        try:
            # Step 0: Stop WebSocket and Health Check
            logger.info("Step 0/9: Stopping WebSocket and Health Check...")

            if self.health_check_monitor:
                try:
                    await asyncio.wait_for(
                        self.health_check_monitor.stop(),
                        timeout=5.0,
                    )
                    logger.info("✅ Health Check Monitor stopped")
                except TimeoutError:
                    logger.warning("⚠️ Health Check Monitor stop timeout")
                except Exception as e:
                    logger.exception(f"❌ Error stopping Health Check: {e}")

            if self.websocket_manager:
                try:
                    await asyncio.wait_for(
                        self.websocket_manager.stop(),
                        timeout=5.0,
                    )
                    logger.info("✅ WebSocket Listener stopped")
                except TimeoutError:
                    logger.warning("⚠️ WebSocket Listener stop timeout")
                except Exception as e:
                    logger.exception(f"❌ Error stopping WebSocket: {e}")

            # Step 1: Stop Scanner Manager
            if self.scanner_manager:
                logger.info("Step 1/10: Stopping Scanner Manager...")
                try:
                    await asyncio.wait_for(
                        self.scanner_manager.stop(),
                        timeout=10.0,
                    )
                    if self._scanner_task:
                        self._scanner_task.cancel()
                        try:
                            await self._scanner_task
                        except asyncio.CancelledError:
                            pass
                    logger.info("✅ Scanner Manager stopped")
                except TimeoutError:
                    logger.warning("⚠️ Scanner Manager stop timeout")
                except Exception as e:
                    logger.exception(f"❌ Error stopping Scanner Manager: {e}")

            # Step 1a: Stop Bot Integrator (all new improvements)
            if hasattr(self, "bot_integrator") and self.bot_integrator:
                logger.info("Step 1a/10: Stopping Bot Integrator...")
                try:
                    await asyncio.wait_for(
                        self.bot_integrator.stop(),
                        timeout=10.0,
                    )
                    logger.info("✅ Bot Integrator stopped")
                except TimeoutError:
                    logger.warning("⚠️ Bot Integrator stop timeout")
                except Exception as e:
                    logger.exception(f"❌ Error stopping Bot Integrator: {e}")

            # Step 2: Stop accepting new updates
            logger.info("Step 2/9: Stopping new updates...")
            if self.bot is not None:
                try:
                    if self.bot.updater is not None and self.bot.updater.running:
                        await asyncio.wait_for(
                            self.bot.updater.stop(),
                            timeout=5.0,
                        )
                        logger.info("✅ Stopped accepting new updates")
                except TimeoutError:
                    logger.warning("⚠️  Timeout stopping updater, forcing...")

            # Step 2: Waiting for active tasks to complete (with timeout)
            logger.info("Step 3/9: Waiting for active tasks to complete...")
            active_tasks = [
                task
                for task in asyncio.all_tasks()
                if not task.done() and task != asyncio.current_task()
            ]

            if active_tasks:
                logger.info(f"  Found {len(active_tasks)} active tasks")
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*active_tasks, return_exceptions=True),
                        timeout=min(10.0, timeout - (asyncio.get_event_loop().time() - start_time)),
                    )
                    logger.info("✅ All tasks completed")
                except TimeoutError:
                    logger.warning(
                        f"⚠️  Timeout waiting for {len(active_tasks)} tasks, continuing..."
                    )
                    # Cancel remaining tasks
                    for task in active_tasks:
                        if not task.done():
                            task.cancel()

            # Step 3: Stop Daily Report Scheduler
            logger.info("Step 4/9: Stopping Daily Report Scheduler...")
            if self.daily_report_scheduler:
                try:
                    await asyncio.wait_for(
                        self.daily_report_scheduler.stop(),
                        timeout=5.0,
                    )
                    logger.info("✅ Daily Report Scheduler stopped")
                except TimeoutError:
                    logger.warning("⚠️  Timeout stopping scheduler")

            # Step 4a: Stop AI Training Scheduler
            if self.ai_scheduler:
                try:
                    await asyncio.wait_for(
                        self.ai_scheduler.stop(),
                        timeout=5.0,
                    )
                    logger.info("✅ AI Training Scheduler stopped")
                except TimeoutError:
                    logger.warning("⚠️  Timeout stopping AI scheduler")

            # Step 4: Stop Telegram Bot
            logger.info("Step 5/9: Stopping Telegram Bot...")
            if self.bot is not None:
                try:
                    if self.bot.running:
                        await asyncio.wait_for(
                            self.bot.stop(),
                            timeout=5.0,
                        )
                    await asyncio.wait_for(
                        self.bot.shutdown(),
                        timeout=5.0,
                    )
                    logger.info("✅ Telegram Bot stopped")
                except TimeoutError:
                    logger.warning("⚠️  Timeout stopping bot")
                except Exception as e:
                    logger.exception(f"❌ Error stopping bot: {e}")

            # Step 5: Close DMarket API connections
            logger.info("Step 6/9: Closing DMarket API connections...")
            if self.dmarket_api is not None:
                try:
                    await asyncio.wait_for(
                        self.dmarket_api._close_client(),
                        timeout=3.0,
                    )
                    logger.info("✅ DMarket API connections closed")
                except TimeoutError:
                    logger.warning("⚠️  Timeout closing API connections")
                except Exception as e:
                    logger.exception(f"❌ Error closing API: {e}")

            # Step 6: Close database connections
            logger.info("Step 7/9: Closing database connections...")
            if self.database:
                try:
                    await asyncio.wait_for(
                        self.database.close(),
                        timeout=5.0,
                    )
                    logger.info("✅ Database connections closed")
                except TimeoutError:
                    logger.warning("⚠️  Timeout closing database")
                except Exception as e:
                    logger.exception(f"❌ Error closing database: {e}")

            # Stop health check server (last)
            logger.info("Stopping health check server...")
            try:
                if health_check_server:
                    await health_check_server.stop()
                logger.info("✅ Health check server stopped")
            except Exception as e:
                logger.exception(f"❌ Error stopping health check: {e}")

            # Flush logs
            logger.info("Flushing logs...")
            for handler in logging.root.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass

        except Exception as e:
            logger.exception(f"❌ Error during shutdown: {e}")

        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ Application shutdown complete in {elapsed:.2f}s")
        logger.info("=" * 60)

    async def _handle_critical_shutdown(self, reason: str) -> None:
        """Handle critical shutdown event.

        Args:
            reason: Reason for critical shutdown

        """
        logger.critical(f"CRITICAL SHUTDOWN TRIGGERED: {reason}")

        # Отправить уведомления всем администраторам
        if self.bot and self.config:
            # Получить список администраторов
            admin_users = []
            if hasattr(self.config.security, "admin_users"):
                admin_users = self.config.security.admin_users

            if not admin_users and hasattr(
                self.config.security,
                "allowed_users",
            ):
                # Если нет админов, отправить первому разрешенному
                admin_users = self.config.security.allowed_users[:1]

            # Получить количество ошибок
            consecutive_errors = self.state_manager.consecutive_errors if self.state_manager else 0

            # Отправить уведомления
            for user_id in admin_users:
                try:
                    await send_critical_shutdown_notification(
                        bot=self.bot.bot,
                        user_id=int(user_id),
                        reason=reason,
                        details={"consecutive_errors": consecutive_errors},
                    )
                    logger.info(
                        f"Critical shutdown notification sent to {user_id}",
                    )
                except Exception as e:
                    logger.exception(
                        f"Failed to send shutdown notification to {user_id}: {e}",
                    )

    async def _send_crash_notifications(
        self,
        error: Exception,
        traceback_text: str,
    ) -> None:
        """Send crash notifications to all administrators.

        Args:
            error: Exception that caused the crash
            traceback_text: Full traceback string

        """
        if not self.bot or not self.config:
            return

        # Получить список администраторов
        admin_users = []
        if hasattr(self.config.security, "admin_users"):
            admin_users = self.config.security.admin_users

        if not admin_users and hasattr(self.config.security, "allowed_users"):
            # Если нет админов, отправить первому разрешенному пользователю
            admin_users = self.config.security.allowed_users[:1]

        # Отправить уведомления
        for user_id in admin_users:
            try:
                await send_crash_notification(
                    bot=self.bot.bot,
                    user_id=int(user_id),
                    error_type=type(error).__name__,
                    error_message=str(error),
                    traceback_str=traceback_text,
                )
                logger.info(f"Crash notification sent to user {user_id}")
            except Exception as e:
                logger.exception(
                    f"Failed to send crash notification to {user_id}: {e}",
                )

    async def _recover_pending_trades(self) -> None:
        """Recover pending trades from database after restart.

        This is CRITICAL for bot persistence. Without this, the bot would
        "forget" about purchased items after shutdown or restart.

        The recovery process:
        1. Reads pending trades from database
        2. Syncs with DMarket inventory (what's still there vs sold offline)
        3. Re-lists items that need to be sold
        4. Sends summary notification to admin
        """
        if not self.bot or self.config.testing:
            return

        trading_persistence = getattr(self.bot, "trading_persistence", None)
        if not trading_persistence:
            logger.debug("Trading persistence not available, skipping recovery")
            return

        try:
            logger.info("🔍 Recovering pending trades from database...")

            # Recover trades and sync with inventory
            results = await trading_persistence.recover_pending_trades()

            if not results:
                logger.info("✅ No pending trades to recover")
                return

            # Count actions
            to_list = sum(1 for r in results if r.get("action") == "list_for_sale")
            sold_offline = sum(1 for r in results if r.get("action") == "marked_sold")

            logger.info(
                f"📦 Recovery complete: {sold_offline} sold offline, {to_list} need listing"
            )

            # Auto-list items that need to be sold
            if to_list > 0 and self.inventory_manager:
                logger.info(f"📤 Scheduling {to_list} items for auto-listing...")
                # Inventory manager will pick them up in next cycle

        except Exception as e:
            logger.exception(f"Failed to recover pending trades: {e}")
            # Not critical, continue startup

    async def _init_config_and_logging(self) -> None:
        """Load configuration and setup logging."""
        logger.info("Loading configuration...")

        self.config = Config.load(self.config_path)

        # Setup structured logging based on config
        setup_logging(
            level=self.config.logging.level,
            log_file=self.config.logging.file,
            format_string=self.config.logging.format,
        )

        # Load whitelist if configured
        whitelist_path = os.getenv("WHITELIST_PATH", "data/whitelist.json")
        if os.path.exists(whitelist_path):
            logger.info(f"Loading whitelist from {whitelist_path}")

        logger.info("Configuration loaded successfully")

    async def _init_core_services(self) -> None:
        """Initialize Sentry, Database, and StateManager."""
        # Initialize Sentry for error monitoring
        sentry_dsn = os.getenv("SENTRY_DSN")
        if not self.config.testing and sentry_dsn:
            logger.info("Initializing Sentry...")
            environment = "production" if not self.config.debug else "development"
            init_sentry(dsn=sentry_dsn, environment=environment)
            logger.info("Sentry initialized successfully")

        # Initialize database
        logger.info("Initializing database...")
        self.database = DatabaseManager(database_url=self.config.database.url)
        await self.database.init_database()
        logger.info("Database initialized successfully")

        # Initialize StateManager for application state tracking
        logger.info("Initializing State Manager...")
        session = self.database.get_async_session()
        self.state_manager = StateManager(session=session, max_consecutive_errors=5)
        logger.info("State Manager initialized successfully")

    async def _init_dmarket_api(self) -> None:
        """Initialize DMarket API and test connection."""
        logger.info("Initializing DMarket API...")
        logger.info(f"DRY_RUN mode: {self.config.dry_run}")

        self.dmarket_api = DMarketAPI(
            public_key=self.config.dmarket.public_key,
            secret_key=self.config.dmarket.secret_key,
            api_url=self.config.dmarket.api_url,
            dry_run=self.config.dry_run,
        )

        # Test API connection (if not in testing mode)
        if not self.config.testing and self.config.dmarket.public_key:
            try:
                balance = await self.dmarket_api.get_balance()
                logger.info(f"DMarket API connected. Balance: ${balance.get('balance', 0):.2f}")
            except Exception as e:
                logger.warning(f"Failed to get balance: {e}")

        logger.info("DMarket API initialized successfully")

    async def _init_telegram_bot(self) -> None:
        """Initialize Telegram bot with persistence and dependencies."""
        logger.info("Initializing Telegram Bot...")

        if not self.config.bot.token:
            raise ValueError("Telegram bot token is not configured")

        builder = ApplicationBuilder().token(self.config.bot.token)

        # Enable database persistence (NEW: optimized for 2026)
        if not self.config.testing:
            from src.utils.db_persistence import SQLPersistence

            persistence = SQLPersistence(
                db_manager=self.database,
                store_data=PersistenceInput(
                    bot_data=True,
                    chat_data=True,
                    user_data=True,
                    callback_data=True,
                ),
            )
            builder.persistence(persistence)
            logger.info("✅ Database persistence enabled (SQLAlchemy)")

        self.bot = builder.build()
        self.bot.db = self.database
        logger.info("Database attached as application.db attribute")

        # Clear pending updates on start
        await self._clear_pending_updates()

        # Attach dependencies as application attributes
        self._attach_bot_dependencies()

        # Register handlers and initialize
        register_all_handlers(self.bot)
        await self.bot.initialize()

        # Setup bot commands for UI autocomplete
        from src.telegram_bot.initialization import setup_bot_commands
        await setup_bot_commands(self.bot.bot)

        logger.info("Telegram Bot initialized successfully")

    async def _clear_pending_updates(self) -> None:
        """Clear pending Telegram updates on start."""
        if self.config.testing:
            return

        try:
            logger.info("Clearing pending updates...")
            updates = await self.bot.bot.get_updates(timeout=5)
            if updates:
                last_id = updates[-1].update_id
                await self.bot.bot.get_updates(offset=last_id + 1, timeout=1)
                logger.info(f"Cleared {len(updates)} pending updates")
            else:
                logger.info("No pending updates to clear")
        except Exception as e:
            logger.warning(f"Failed to clear pending updates: {e}")

    def _attach_bot_dependencies(self) -> None:
        """Attach dependencies to bot as attributes (pickle-safe)."""
        self.bot.dmarket_api = self.dmarket_api
        self.bot.database = self.database
        self.bot.state_manager = self.state_manager
        self.bot.bot_instance = self
        self.bot.bot_data["config"] = self.config

        if self.state_manager:
            self.state_manager.set_shutdown_callback(self._handle_critical_shutdown)

        logger.info("Dependencies attached as application attributes (pickle-safe)")

    def _get_admin_users(self) -> list[int]:
        """Get list of admin user IDs from config."""
        admin_users_raw = getattr(self.config.security, "admin_users", [])

        if not admin_users_raw and hasattr(self.config.security, "allowed_users"):
            admin_users_raw = self.config.security.allowed_users

        return [int(uid) for uid in admin_users_raw if str(uid).isdigit()]

    async def _init_schedulers(self) -> None:
        """Initialize Daily Report and AI Training schedulers."""
        await self._init_daily_report_scheduler()
        await self._init_ai_scheduler()

    async def _init_daily_report_scheduler(self) -> None:
        """Initialize Daily Report Scheduler."""
        if self.config.testing or not self.database or not self.config.daily_report.enabled:
            return

        logger.info("Initializing Daily Report Scheduler...")
        from datetime import time

        admin_users = self._get_admin_users()
        report_time = time(
            hour=self.config.daily_report.report_time_hour,
            minute=self.config.daily_report.report_time_minute,
        )

        self.daily_report_scheduler = DailyReportScheduler(
            database=self.database,
            bot=self.bot.bot,
            admin_users=admin_users,
            report_time=report_time,
            enabled=self.config.daily_report.enabled,
        )
        self.bot.daily_report_scheduler = self.daily_report_scheduler

        logger.info(f"Daily Report Scheduler initialized at {report_time.strftime('%H:%M')}")

    async def _init_ai_scheduler(self) -> None:
        """Initialize AI Training Scheduler."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing AI Training Scheduler...")
        try:
            from datetime import time as dt_time

            from src.utils.ai_scheduler import AITrainingScheduler

            admin_users = self._get_admin_users()

            self.ai_scheduler = AITrainingScheduler(
                api_client=self.dmarket_api,
                admin_users=admin_users,
                bot=self.bot.bot if self.bot else None,
                training_time=dt_time(3, 0),
                data_collection_interval=300,
                enabled=True,
            )
            self.bot.ai_scheduler = self.ai_scheduler

            logger.info("AI Training Scheduler initialized (training at 03:00 UTC)")
        except Exception as e:
            logger.warning(f"Failed to initialize AI Training Scheduler: {e}")

    async def _init_scanner_manager(self) -> None:
        """Initialize Scanner Manager with adaptive, parallel, and cleanup features."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing Scanner Manager...")

        enable_adaptive = getattr(self.config, "enable_adaptive_scan", True)
        enable_parallel = getattr(self.config, "enable_parallel_scan", True)
        enable_cleanup = getattr(self.config, "enable_target_cleanup", True)

        self.scanner_manager = ScannerManager(
            api_client=self.dmarket_api,
            config=self.config,
            enable_adaptive=enable_adaptive,
            enable_parallel=enable_parallel,
            enable_cleanup=enable_cleanup,
        )
        self.bot.scanner_manager = self.scanner_manager

        logger.info(
            f"Scanner Manager initialized: adaptive={enable_adaptive}, "
            f"parallel={enable_parallel}, cleanup={enable_cleanup}"
        )

    async def _init_inventory_and_trading(self) -> None:
        """Initialize Inventory Manager, Auto Steam Scanner, and Autopilot."""
        await self._init_inventory_manager()
        await self._init_steam_arbitrage_scanner()
        await self._init_autopilot_orchestrator()

    async def _init_inventory_manager(self) -> None:
        """Initialize Inventory Manager for Direct Buy mode."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing Inventory Manager (Direct Buy Mode)...")
        try:
            from src.dmarket.inventory_manager import InventoryManager

            undercut_step = int(self.config.inventory.undercut_price * 100)
            min_profit_margin = self.config.inventory.min_margin_threshold
            check_interval = int(os.getenv("INVENTORY_CHECK_INTERVAL", "1800"))
            undercut_enabled = self.config.inventory.auto_sell

            self.inventory_manager = InventoryManager(
                api_client=self.dmarket_api,
                telegram_bot=self.bot.bot,
                undercut_step=undercut_step,
                min_profit_margin=min_profit_margin,
                check_interval=check_interval,
            )
            self.bot.inventory_manager = self.inventory_manager

            logger.info(
                f"Inventory Manager initialized: undercut={'ON' if undercut_enabled else 'OFF'}, "
                f"step=${undercut_step / 100:.2f}, margin={min_profit_margin:.2%}, interval={check_interval}s"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Inventory Manager: {e}")

    async def _init_steam_arbitrage_scanner(self) -> None:
        """Initialize Auto Steam Arbitrage Scanner."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing Auto Steam Arbitrage Scanner...")
        try:
            admin_users = getattr(self.config.security, "admin_users", [])
            if not admin_users and hasattr(self.config.security, "allowed_users"):
                admin_users = self.config.security.allowed_users

            if not admin_users:
                logger.warning("No admin users configured, Steam Scanner skipped")
                return

            from src.dmarket.auto_steam_arbitrage import AutoSteamArbitrageScanner

            self.steam_arbitrage_scanner = AutoSteamArbitrageScanner(
                dmarket_api=self.dmarket_api,
                telegram_bot=self.bot.bot,
                admin_chat_id=int(admin_users[0]),
                scan_interval_minutes=10,
                min_roi_percent=5.0,
                max_items_per_scan=50,
                game="csgo",
            )
            self.bot.steam_arbitrage_scanner = self.steam_arbitrage_scanner

            logger.info("Auto Steam Arbitrage Scanner initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Steam Arbitrage Scanner: {e}")

    async def _init_autopilot_orchestrator(self) -> None:
        """Initialize Autopilot Orchestrator with auto-buyer and auto-seller."""
        logger.info("Initializing Autopilot Orchestrator...")
        try:
            from src.dmarket.autopilot_orchestrator import AutopilotConfig, AutopilotOrchestrator

            auto_buyer = await self._init_auto_buyer()
            auto_seller = await self._init_auto_seller()
            await self._init_trading_persistence(auto_buyer)

            orchestrator_config = AutopilotConfig(
                games=self.config.trading.games,
                min_discount_percent=30.0,
                max_price_usd=self.config.trading.max_item_price,
                min_balance_threshold_usd=10.0,
            )

            orchestrator = AutopilotOrchestrator(
                scanner_manager=self.scanner_manager,
                auto_buyer=auto_buyer,
                auto_seller=auto_seller,
                api_client=self.dmarket_api,
                config=orchestrator_config,
            )
            self.bot.orchestrator = orchestrator

            logger.info("Autopilot Orchestrator initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Autopilot Orchestrator: {e}")

    async def _init_auto_buyer(self):
        """Initialize auto-buyer component."""
        from src.dmarket.auto_buyer import AutoBuyConfig, AutoBuyer

        auto_buyer = getattr(self.bot, "auto_buyer", None)
        if auto_buyer:
            return auto_buyer

        auto_buy_enabled = os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true"
        min_discount = float(os.getenv("MIN_DISCOUNT", "30.0"))

        auto_buy_config = AutoBuyConfig(
            enabled=auto_buy_enabled,
            dry_run=self.config.dry_run,
            max_price_usd=self.config.trading.max_item_price,
            min_discount_percent=min_discount,
        )
        auto_buyer = AutoBuyer(self.dmarket_api, auto_buy_config)
        self.bot.auto_buyer = auto_buyer

        if auto_buy_enabled:
            logger.warning(
                f"AUTO_BUY is ENABLED! Bot will make REAL purchases (dry_run={self.config.dry_run})"
            )

        return auto_buyer

    async def _init_auto_seller(self):
        """Initialize auto-seller component."""
        from src.dmarket.auto_seller import AutoSeller

        auto_seller = getattr(self.bot, "auto_seller", None)
        if auto_seller:
            return auto_seller

        auto_seller = AutoSeller(api=self.dmarket_api)
        self.bot.auto_seller = auto_seller
        return auto_seller

    async def _init_trading_persistence(self, auto_buyer) -> None:
        """Initialize Trading Persistence for surviving restarts."""
        from src.utils.trading_persistence import init_trading_persistence

        trading_persistence = init_trading_persistence(
            database=self.database,
            dmarket_api=self.dmarket_api,
            telegram_bot=self.bot.bot if self.bot else None,
            min_margin_percent=5.0,
            dmarket_fee_percent=7.0,
        )

        auto_buyer.set_trading_persistence(trading_persistence)
        self.bot.trading_persistence = trading_persistence

        logger.info("Trading Persistence initialized - purchases will survive restarts")

    async def _init_websocket_and_health(self) -> None:
        """Initialize WebSocket Listener and Health Check Monitor."""
        await self._init_websocket()
        await self._init_health_check()

    async def _init_websocket(self) -> None:
        """Initialize WebSocket Listener."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing WebSocket Listener...")
        try:
            from src.dmarket.websocket_listener import DMarketWebSocketListener, WebSocketManager

            websocket_listener = DMarketWebSocketListener(
                public_key=self.config.dmarket.public_key,
                secret_key=self.config.dmarket.secret_key,
            )
            self.websocket_manager = WebSocketManager(websocket_listener)
            self.bot.websocket_manager = self.websocket_manager

            logger.info("WebSocket Listener initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize WebSocket Listener: {e}")

    async def _init_health_check(self) -> None:
        """Initialize Health Check Monitor."""
        if self.config.testing or not self.bot:
            return

        logger.info("Initializing Health Check Monitor...")
        try:
            from src.utils.health_check import HealthCheckMonitor

            admin_users = (
                self.config.security.admin_users
                if hasattr(self.config.security, "admin_users")
                else self.config.security.allowed_users
            )

            if not admin_users:
                return

            self.health_check_monitor = HealthCheckMonitor(
                telegram_bot=self.bot.bot,
                user_id=int(admin_users[0]),
                check_interval=900,
                alert_on_failure=True,
            )

            if self.dmarket_api is not None:
                self.health_check_monitor.register_api_client(self.dmarket_api)

            if self.websocket_manager:
                self.health_check_monitor.register_websocket(self.websocket_manager.listener)

            self.bot.health_check_monitor = self.health_check_monitor

            logger.info("Health Check Monitor initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Health Check Monitor: {e}")

    async def _init_bot_integrator(self) -> None:
        """Initialize Bot Integrator for unified improvements."""
        if self.config.testing or not self.dmarket_api:
            return

        logger.info("Initializing Bot Integrator (unified improvements)...")
        try:
            from src.integration.bot_integrator import (
                BotIntegrator,
                set_integrator,
            )

            integrator_config = self._build_integrator_config()
            waxpeer_api = self._get_waxpeer_api()

            self.bot_integrator = BotIntegrator(
                dmarket_api=self.dmarket_api,
                waxpeer_api=waxpeer_api,
                telegram_bot=self.bot.bot if self.bot else None,
                database=self.database,
                config=integrator_config,
            )

            init_results = await self.bot_integrator.initialize()
            set_integrator(self.bot_integrator)
            self.bot.bot_integrator = self.bot_integrator

            success_count = sum(1 for v in init_results.values() if v)
            logger.info(f"Bot Integrator initialized: {success_count}/{len(init_results)} modules active")
        except Exception as e:
            logger.warning(f"Failed to initialize Bot Integrator: {e}")

    def _build_integrator_config(self):
        """Build IntegratorConfig from main config."""
        from src.integration.bot_integrator import IntegratorConfig

        return IntegratorConfig(
            enable_enhanced_polling=getattr(self.config, "enable_enhanced_polling", True),
            enable_price_analytics=getattr(self.config, "enable_price_analytics", True),
            enable_auto_listing=getattr(self.config, "enable_auto_listing", True),
            enable_portfolio_tracker=getattr(self.config, "enable_portfolio_tracker", True),
            enable_custom_alerts=getattr(self.config, "enable_custom_alerts", True),
            enable_watchlist=getattr(self.config, "enable_watchlist", True),
            enable_anomaly_detection=getattr(self.config, "enable_anomaly_detection", True),
            enable_smart_recommendations=getattr(self.config, "enable_smart_recommendations", True),
            enable_trading_automation=getattr(self.config, "enable_trading_automation", True),
            enable_reports=getattr(self.config, "enable_reports", True),
            enable_security=getattr(self.config, "enable_security", True),
            min_item_price_for_listing=getattr(self.config, "min_listing_price", 50.0),
            target_profit_margin=getattr(self.config, "target_margin", 0.10),
        )

    def _get_waxpeer_api(self):
        """Get Waxpeer API if available."""
        try:
            from src.waxpeer.waxpeer_api import WaxpeerAPI

            waxpeer_api_key = os.getenv("WAXPEER_API_KEY")
            if waxpeer_api_key:
                return WaxpeerAPI(api_key=waxpeer_api_key)
        except Exception as e:
            logger.debug(f"Waxpeer API not available: {e}")
        return None

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig: int, frame: object) -> None:
            _ = frame  # Unused but required by signal.signal protocol
            logger.info(f"Received signal {sig}")
            self._shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Windows doesn't have SIGQUIT
        if hasattr(signal, "SIGQUIT"):
            signal.signal(signal.SIGQUIT, signal_handler)


async def main() -> None:
    """Main entry point."""
    import argparse

    # Parse command line arguments
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

    # Setup basic logging first
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
    # Ensure proper event loop policy on Windows
    if sys.platform.startswith("win"):
        import sys
        import io
        # Force UTF-8 encoding for stdout/stderr to avoid charmap errors in PowerShell
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Run the application
    asyncio.run(main())
