"""Application initialization module.

This module handles initialization of all application components.
"""

import logging
import os
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from src.core.application import Application

logger = logging.getLogger(__name__)


class ComponentInitializer:
    """Handles initialization of application components."""

    def __init__(self, app: "Application") -> None:
        """Initialize the component initializer.

        Args:
            app: Application instance

        """
        self.app = app

    async def initialize_config(self) -> None:
        """Load and validate configuration."""
        from src.utils.config import Config
        from src.utils.logging_utils import setup_logging

        logger.info("Loading configuration...")
        self.app.config = Config.load(self.app.config_path)
        self.app.config.validate()

        # Setup logging
        setup_logging(
            level=self.app.config.logging.level,
            log_file=self.app.config.logging.file,
            format_string=self.app.config.logging.format,
        )

        logger.info("Configuration loaded successfully")
        logger.info(f"Debug mode: {self.app.config.debug}")
        logger.info(f"Testing mode: {self.app.config.testing}")

    async def initialize_whitelist(self) -> None:
        """Load whitelist from JSON file."""
        try:
            from src.dmarket.whitelist_config import load_whitelist_from_json

            whitelist_path = os.getenv("WHITELIST_PATH", "data/whitelist.json")
            if load_whitelist_from_json(whitelist_path):
                logger.info(f"Whitelist loaded from {whitelist_path}")
            else:
                logger.info("Using default whitelist (no JSON file found)")
        except Exception as e:
            logger.warning(f"Failed to load whitelist: {e}")

    async def initialize_sentry(self) -> None:
        """Initialize Sentry error monitoring."""
        if self.app.config.testing:
            return

        from src.utils.sentry_integration import init_sentry

        environment = "production" if not self.app.config.debug else "development"
        init_sentry(
            dsn=os.getenv("SENTRY_DSN"),
            environment=environment,
            release=os.getenv("SENTRY_RELEASE", "1.0.0"),
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            debug=self.app.config.debug,
        )
        logger.info(f"Sentry initialized for {environment} environment")

    async def initialize_database(self) -> None:
        """Initialize database connection."""
        if self.app.config.testing:
            return

        from src.utils.database import DatabaseManager
        from src.utils.state_manager import StateManager

        logger.info("Initializing database...")
        self.app.database = DatabaseManager(
            database_url=self.app.config.database.url,
            echo=self.app.config.debug,
        )
        await self.app.database.init_database()
        logger.info("Database initialized successfully")

        # Initialize StateManager
        session = self.app.database.get_async_session()
        self.app.state_manager = StateManager(
            session=session,
            max_consecutive_errors=5,
        )
        logger.info("StateManager initialized")

    async def initialize_dmarket_api(self) -> None:
        """Initialize DMarket API client."""
        from src.dmarket.dmarket_api import DMarketAPI

        logger.info("Initializing DMarket API...")
        logger.info(f"DRY_RUN mode: {self.app.config.dry_run}")

        self.app.dmarket_api = DMarketAPI(
            public_key=self.app.config.dmarket.public_key,
            secret_key=self.app.config.dmarket.secret_key,
            api_url=self.app.config.dmarket.api_url,
            dry_run=self.app.config.dry_run,
        )

        # Test API connection
        if not self.app.config.testing and self.app.config.dmarket.public_key:
            await self._test_api_connection()

    async def _test_api_connection(self) -> None:
        """Test DMarket API connection."""
        try:
            balance_result = await self.app.dmarket_api.get_balance()
            if balance_result.get("error"):
                logger.warning(
                    f"DMarket API test failed: {balance_result.get('error_message', 'Unknown error')}"
                )
            else:
                balance_value = balance_result.get("balance", 0)
                logger.info(f"DMarket API connected. Balance: ${balance_value:.2f}")
        except Exception as e:
            logger.warning(f"DMarket API test failed: {e}")

    async def initialize_telegram_bot(self) -> None:
        """Initialize Telegram bot."""
        from telegram.ext import ApplicationBuilder, PersistenceInput

        from src.telegram_bot.register_all_handlers import register_all_handlers

        logger.info("Initializing Telegram Bot...")

        if not self.app.config.bot.token:
            raise ValueError("Telegram bot token is not configured")

        builder = ApplicationBuilder().token(self.app.config.bot.token)

        # Enable persistence
        if not self.app.config.testing:
            from src.utils.db_persistence import SQLPersistence
            
            persistence = SQLPersistence(db_manager=self.app.database)
            builder.persistence(persistence)
            logger.info("Persistence enabled: SQLPersistence (Database)")

        self.app.bot = builder.build()

        # Attach dependencies
        self.app.bot.db = self.app.database
        self.app.bot.dmarket_api = self.app.dmarket_api
        self.app.bot.database = self.app.database
        self.app.bot.state_manager = self.app.state_manager
        self.app.bot.bot_instance = self.app
        self.app.bot.bot_data["config"] = self.app.config

        # Clear pending updates
        if not self.app.config.testing:
            await self._clear_pending_updates()

        # Register critical shutdown callback
        if self.app.state_manager:
            self.app.state_manager.set_shutdown_callback(
                self.app._handle_critical_shutdown
            )

        # Register handlers
        register_all_handlers(self.app.bot)

        # Initialize bot
        await self.app.bot.initialize()

        # Setup commands
        from src.telegram_bot.initialization import setup_bot_commands

        await setup_bot_commands(self.app.bot.bot)
        logger.info("Telegram Bot initialized successfully")

    async def _clear_pending_updates(self) -> None:
        """Clear pending Telegram updates."""
        try:
            logger.info("Clearing pending updates...")
            updates = await self.app.bot.bot.get_updates(timeout=5)
            if updates:
                last_id = updates[-1].update_id
                await self.app.bot.bot.get_updates(offset=last_id + 1, timeout=1)
                logger.info(f"Cleared {len(updates)} pending updates")
            else:
                logger.info("No pending updates to clear")
        except Exception as e:
            logger.warning(f"Failed to clear pending updates: {e}")

    async def initialize_daily_report_scheduler(self) -> None:
        """Initialize daily report scheduler."""
        if self.app.config.testing or not self.app.database:
            return

        if not self.app.config.daily_report.enabled:
            return

        from datetime import time

        from src.utils.daily_report_scheduler import DailyReportScheduler

        logger.info("Initializing Daily Report Scheduler...")

        admin_users = self._get_admin_users()
        report_time = time(
            hour=self.app.config.daily_report.report_time_hour,
            minute=self.app.config.daily_report.report_time_minute,
        )

        self.app.daily_report_scheduler = DailyReportScheduler(
            database=self.app.database,
            bot=self.app.bot.bot,
            admin_users=admin_users,
            report_time=report_time,
            enabled=self.app.config.daily_report.enabled,
        )

        self.app.bot.daily_report_scheduler = self.app.daily_report_scheduler
        logger.info(f"Daily Report Scheduler initialized at {report_time.strftime('%H:%M')}")

    async def initialize_ai_scheduler(self) -> None:
        """Initialize AI training scheduler."""
        if self.app.config.testing or not self.app.dmarket_api:
            return

        logger.info("Initializing AI Training Scheduler...")
        try:
            from datetime import time as dt_time

            from src.utils.ai_scheduler import AITrainingScheduler

            admin_users = self._get_admin_users()

            self.app.ai_scheduler = AITrainingScheduler(
                api_client=self.app.dmarket_api,
                admin_users=admin_users,
                bot=self.app.bot.bot if self.app.bot else None,
                training_time=dt_time(3, 0),
                data_collection_interval=300,
                enabled=True,
            )

            self.app.bot.ai_scheduler = self.app.ai_scheduler
            logger.info("AI Training Scheduler initialized (training at 03:00 UTC)")
        except Exception as e:
            logger.warning(f"Failed to initialize AI Training Scheduler: {e}")

    async def initialize_scanner_manager(self) -> None:
        """Initialize scanner manager."""
        if self.app.config.testing or not self.app.dmarket_api:
            return

        from src.dmarket.scanner_manager import ScannerManager

        logger.info("Initializing Scanner Manager...")

        enable_adaptive = getattr(self.app.config, "enable_adaptive_scan", True)
        enable_parallel = getattr(self.app.config, "enable_parallel_scan", True)
        enable_cleanup = getattr(self.app.config, "enable_target_cleanup", True)

        self.app.scanner_manager = ScannerManager(
            api_client=self.app.dmarket_api,
            config=self.app.config,
            enable_adaptive=enable_adaptive,
            enable_parallel=enable_parallel,
            enable_cleanup=enable_cleanup,
        )

        self.app.bot.scanner_manager = self.app.scanner_manager
        logger.info(
            f"Scanner Manager initialized: "
            f"adaptive={enable_adaptive}, parallel={enable_parallel}, cleanup={enable_cleanup}"
        )

    async def initialize_inventory_manager(self) -> None:
        """Initialize inventory manager for Direct Buy mode."""
        if self.app.config.testing or not self.app.dmarket_api:
            return

        logger.info("Initializing Inventory Manager...")
        try:
            from src.dmarket.inventory_manager import InventoryManager

            undercut_step = int(self.app.config.inventory.undercut_price * 100)
            min_profit_margin = self.app.config.inventory.min_margin_threshold
            check_interval = int(os.getenv("INVENTORY_CHECK_INTERVAL", "1800"))

            self.app.inventory_manager = InventoryManager(
                api_client=self.app.dmarket_api,
                telegram_bot=self.app.bot.bot,
                undercut_step=undercut_step,
                min_profit_margin=min_profit_margin,
                check_interval=check_interval,
            )

            self.app.bot.inventory_manager = self.app.inventory_manager
            logger.info(
                f"Inventory Manager initialized: "
                f"step=${undercut_step / 100:.2f}, margin={min_profit_margin:.2%}"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Inventory Manager: {e}")

    async def initialize_autopilot(self) -> None:
        """Initialize autopilot orchestrator."""
        logger.info("Initializing Autopilot Orchestrator...")
        try:
            from src.dmarket.auto_buyer import AutoBuyConfig, AutoBuyer
            from src.dmarket.auto_seller import AutoSeller
            from src.dmarket.autopilot_orchestrator import AutopilotConfig, AutopilotOrchestrator
            from src.utils.trading_persistence import init_trading_persistence

            # Initialize auto-buyer
            auto_buy_enabled = os.getenv("AUTO_BUY_ENABLED", "false").lower() == "true"
            min_discount = float(os.getenv("MIN_DISCOUNT", "30.0"))

            auto_buy_config = AutoBuyConfig(
                enabled=auto_buy_enabled,
                dry_run=self.app.config.dry_run,
                max_price_usd=self.app.config.trading.max_item_price,
                min_discount_percent=min_discount,
            )
            auto_buyer = AutoBuyer(self.app.dmarket_api, auto_buy_config)
            self.app.bot.auto_buyer = auto_buyer

            if auto_buy_enabled:
                logger.warning(
                    f"AUTO_BUY is ENABLED! (dry_run={self.app.config.dry_run})"
                )

            # Initialize auto-seller
            auto_seller = AutoSeller(api=self.app.dmarket_api)
            self.app.bot.auto_seller = auto_seller

            # Initialize trading persistence
            trading_persistence = init_trading_persistence(
                database=self.app.database,
                dmarket_api=self.app.dmarket_api,
                telegram_bot=self.app.bot.bot if self.app.bot else None,
                min_margin_percent=5.0,
                dmarket_fee_percent=7.0,
            )

            auto_buyer.set_trading_persistence(trading_persistence)
            self.app.bot.trading_persistence = trading_persistence
            logger.info("Trading Persistence initialized")

            # Create orchestrator
            orchestrator_config = AutopilotConfig(
                games=self.app.config.trading.games,
                min_discount_percent=30.0,
                max_price_usd=self.app.config.trading.max_item_price,
                min_balance_threshold_usd=10.0,
            )

            orchestrator = AutopilotOrchestrator(
                scanner_manager=self.app.scanner_manager,
                auto_buyer=auto_buyer,
                auto_seller=auto_seller,
                api_client=self.app.dmarket_api,
                config=orchestrator_config,
            )

            self.app.bot.orchestrator = orchestrator
            logger.info("Autopilot Orchestrator initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Autopilot: {e}")

    async def initialize_websocket_manager(self) -> None:
        """Initialize WebSocket listener."""
        if self.app.config.testing or not self.app.dmarket_api:
            return

        logger.info("Initializing WebSocket Listener...")
        try:
            from src.dmarket.websocket_listener import (
                DMarketWebSocketListener,
                WebSocketManager,
            )

            websocket_listener = DMarketWebSocketListener(
                public_key=self.app.config.dmarket.public_key,
                secret_key=self.app.config.dmarket.secret_key,
            )

            self.app.websocket_manager = WebSocketManager(websocket_listener)
            self.app.bot.websocket_manager = self.app.websocket_manager
            logger.info("WebSocket Listener initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize WebSocket: {e}")

    async def initialize_health_check_monitor(self) -> None:
        """Initialize health check monitor."""
        if self.app.config.testing or not self.app.bot:
            return

        logger.info("Initializing Health Check Monitor...")
        try:
            from src.utils.health_check import HealthCheckMonitor

            admin_users = self._get_admin_users()
            if not admin_users:
                return

            first_admin = admin_users[0]

            self.app.health_check_monitor = HealthCheckMonitor(
                telegram_bot=self.app.bot.bot,
                user_id=first_admin,
                check_interval=900,
                alert_on_failure=True,
            )

            if self.app.dmarket_api:
                self.app.health_check_monitor.register_api_client(self.app.dmarket_api)

            if self.app.websocket_manager:
                self.app.health_check_monitor.register_websocket(
                    self.app.websocket_manager.listener
                )

            self.app.bot.health_check_monitor = self.app.health_check_monitor
            logger.info("Health Check Monitor initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Health Check: {e}")

    async def initialize_bot_integrator(self) -> None:
        """Initialize Bot Integrator for all new improvements."""
        if self.app.config.testing or not self.app.dmarket_api:
            return

        logger.info("Initializing Bot Integrator...")
        try:
            from src.integration.bot_integrator import (
                BotIntegrator,
                IntegratorConfig,
                set_integrator,
            )

            integrator_config = IntegratorConfig(
                enable_enhanced_polling=getattr(self.app.config, "enable_enhanced_polling", True),
                enable_price_analytics=getattr(self.app.config, "enable_price_analytics", True),
                enable_auto_listing=getattr(self.app.config, "enable_auto_listing", True),
                enable_portfolio_tracker=getattr(self.app.config, "enable_portfolio_tracker", True),
                enable_custom_alerts=getattr(self.app.config, "enable_custom_alerts", True),
                enable_watchlist=getattr(self.app.config, "enable_watchlist", True),
                enable_anomaly_detection=getattr(self.app.config, "enable_anomaly_detection", True),
                enable_smart_recommendations=getattr(self.app.config, "enable_smart_recommendations", True),
                enable_trading_automation=getattr(self.app.config, "enable_trading_automation", True),
                enable_reports=getattr(self.app.config, "enable_reports", True),
                enable_security=getattr(self.app.config, "enable_security", True),
                min_item_price_for_listing=getattr(self.app.config, "min_listing_price", 50.0),
                target_profit_margin=getattr(self.app.config, "target_margin", 0.10),
            )

            # Get Waxpeer API if available
            waxpeer_api = self._get_waxpeer_api()

            self.app.bot_integrator = BotIntegrator(
                dmarket_api=self.app.dmarket_api,
                waxpeer_api=waxpeer_api,
                telegram_bot=self.app.bot.bot if self.app.bot else None,
                database=self.app.database,
                config=integrator_config,
            )

            init_results = await self.app.bot_integrator.initialize()
            set_integrator(self.app.bot_integrator)
            self.app.bot.bot_integrator = self.app.bot_integrator

            success_count = sum(1 for v in init_results.values() if v)
            logger.info(f"Bot Integrator: {success_count}/{len(init_results)} modules active")
        except Exception as e:
            logger.warning(f"Failed to initialize Bot Integrator: {e}")

    async def initialize_prometheus_exporter(self) -> None:
        """Initialize Prometheus metrics exporter."""
        if self.app.config.testing:
            return

        logger.info("Initializing Prometheus Metrics Exporter...")
        try:
            from src.utils.prometheus_server import PrometheusServer

            prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
            prometheus_host = os.getenv("PROMETHEUS_HOST", "127.0.0.1")

            self.app.prometheus_server = PrometheusServer(
                host=prometheus_host,
                port=prometheus_port,
            )
            logger.info(f"Prometheus Exporter initialized on {prometheus_host}:{prometheus_port}")
        except Exception as e:
            logger.warning(f"Failed to initialize Prometheus Exporter: {e}")

    def _get_admin_users(self) -> list[int]:
        """Get list of admin user IDs."""
        admin_users_raw = (
            self.app.config.security.admin_users
            if hasattr(self.app.config.security, "admin_users")
            else []
        )

        if not admin_users_raw and hasattr(self.app.config.security, "allowed_users"):
            admin_users_raw = self.app.config.security.allowed_users

        return [int(uid) for uid in admin_users_raw if str(uid).isdigit()]

    def _get_waxpeer_api(self) -> Any | None:
        """Get Waxpeer API if available."""
        try:
            from src.waxpeer.waxpeer_api import WaxpeerAPI

            waxpeer_api_key = os.getenv("WAXPEER_API_KEY")
            if waxpeer_api_key:
                return WaxpeerAPI(api_key=waxpeer_api_key)
        except Exception as e:
            logger.debug(f"Waxpeer API not available: {e}")
        return None
