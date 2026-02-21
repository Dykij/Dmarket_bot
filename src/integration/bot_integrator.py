"""Bot Integrator - Main orchestrator for all bot improvements.

This module provides a unified interface to integrate all new improvements
into the existing bot architecture without breaking existing functionality.

Features:
- Unified initialization of all new modules
- Graceful degradation when modules fail
- Event-driven communication between components
- Centralized health monitoring
- Configuration management

Usage:
    ```python
    from src.integration.bot_integrator import BotIntegrator

    integrator = BotIntegrator(
        dmarket_api=api,
        waxpeer_api=waxpeer,
        telegram_bot=bot,
        config=config,
    )

    await integrator.initialize()
    await integrator.start()
    # ... bot runs ...
    await integrator.stop()
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from src.integration.event_bus import Event, EventBus, EventTypes
from src.integration.health_aggregator import HealthAggregator
from src.integration.service_registry import ServiceRegistry

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.utils.config import Config
    from src.waxpeer.waxpeer_api import WaxpeerAPI


logger = structlog.get_logger(__name__)


@dataclass
class IntegratorConfig:
    """Configuration for bot integrator."""

    # Feature flags
    enable_enhanced_polling: bool = True
    enable_price_analytics: bool = True
    enable_auto_listing: bool = True
    enable_portfolio_tracker: bool = True
    enable_custom_alerts: bool = True
    enable_watchlist: bool = True
    enable_anomaly_detection: bool = True
    enable_smart_recommendations: bool = True
    enable_trading_automation: bool = True
    enable_reports: bool = True
    enable_security: bool = True

    # Thresholds
    min_item_price_for_listing: float = 50.0
    target_profit_margin: float = 0.10
    anomaly_detection_threshold: float = 0.3

    # Intervals
    health_check_interval: float = 60.0
    analytics_update_interval: float = 300.0

    @classmethod
    def from_config(cls, config: Config) -> IntegratorConfig:
        """Create integrator config from main config.

        Args:
            config: Main bot configuration

        Returns:
            IntegratorConfig instance
        """
        return cls(
            min_item_price_for_listing=getattr(config, "min_listing_price", 50.0),
            target_profit_margin=getattr(config, "target_margin", 0.10),
        )


class BotIntegrator:
    """Main orchestrator for all bot improvements.

    This class integrates all new modules (enhanced polling, analytics,
    auto-listing, etc.) with the existing bot architecture.

    It provides:
    - Centralized initialization
    - Event-driven communication
    - Health monitoring
    - Graceful degradation
    - Configuration management
    """

    def __init__(
        self,
        dmarket_api: DMarketAPI | None = None,
        waxpeer_api: WaxpeerAPI | None = None,
        telegram_bot: Any | None = None,
        database: Any | None = None,
        config: IntegratorConfig | None = None,
    ) -> None:
        """Initialize bot integrator.

        Args:
            dmarket_api: DMarket API client
            waxpeer_api: Waxpeer API client (optional)
            telegram_bot: Telegram bot instance
            database: Database manager
            config: Integrator configuration
        """
        self.dmarket_api = dmarket_api
        self.waxpeer_api = waxpeer_api
        self.telegram_bot = telegram_bot
        self.database = database
        self.config = config or IntegratorConfig()

        # Core components
        self.services = ServiceRegistry()
        self.events = EventBus()
        self.health = HealthAggregator(
            check_interval_seconds=self.config.health_check_interval,
        )

        # State
        self._initialized = False
        self._running = False
        self._start_time: datetime | None = None

        # Module instances (lazy loaded)
        self._enhanced_polling = None
        self._price_analytics = None
        self._auto_listing = None
        self._portfolio_tracker = None
        self._custom_alerts = None
        self._watchlist = None
        self._anomaly_detection = None
        self._smart_recommendations = None
        self._trading_automation = None
        self._reports = None
        self._security = None

        logger.info("BotIntegrator created")

    async def initialize(self) -> dict[str, bool]:
        """Initialize all modules.

        Returns:
            Dictionary of module name to initialization success
        """
        if self._initialized:
            logger.warning("BotIntegrator already initialized")
            return {}

        results = {}

        logger.info("=" * 60)
        logger.info("🚀 Initializing Bot Integrator...")
        logger.info("=" * 60)

        # Register core services
        if self.dmarket_api:
            self.services.register("dmarket_api", self.dmarket_api)
            self.health.register_component("dmarket_api", self.dmarket_api)

        if self.waxpeer_api:
            self.services.register("waxpeer_api", self.waxpeer_api)
            self.health.register_component("waxpeer_api", self.waxpeer_api)

        if self.telegram_bot:
            self.services.register("telegram_bot", self.telegram_bot)

        if self.database:
            self.services.register("database", self.database)
            self.health.register_component("database", self.database)

        # Initialize modules with graceful degradation
        modules_to_init = [
            ("enhanced_polling", self._init_enhanced_polling),
            ("price_analytics", self._init_price_analytics),
            ("auto_listing", self._init_auto_listing),
            ("portfolio_tracker", self._init_portfolio_tracker),
            ("custom_alerts", self._init_custom_alerts),
            ("watchlist", self._init_watchlist),
            ("anomaly_detection", self._init_anomaly_detection),
            ("smart_recommendations", self._init_smart_recommendations),
            ("trading_automation", self._init_trading_automation),
            ("reports", self._init_reports),
            ("security", self._init_security),
        ]

        for name, init_func in modules_to_init:
            try:
                success = await init_func()
                results[name] = success

                if success:
                    logger.info(f"  ✅ {name} initialized")
                else:
                    logger.warning(f"  ⚠️ {name} disabled (by config)")

            except Exception as e:
                results[name] = False
                logger.error(f"  ❌ {name} failed: {e}", exc_info=True)

        # Setup event handlers
        self._setup_event_handlers()

        self._initialized = True

        logger.info("=" * 60)
        logger.info(
            f"✅ Initialization complete: {sum(results.values())}/{len(results)} modules"
        )
        logger.info("=" * 60)

        # Publish initialization event
        await self.events.publish(
            Event(
                type=EventTypes.SERVICE_STARTED,
                data={
                    "service": "bot_integrator",
                    "modules": results,
                },
            )
        )

        return results

    async def start(self) -> None:
        """Start all modules."""
        if not self._initialized:
            await self.initialize()

        if self._running:
            logger.warning("BotIntegrator already running")
            return

        logger.info("Starting Bot Integrator modules...")

        # Start services
        await self.services.start_all()

        # Start health monitoring
        await self.health.start()

        # Start event bus
        self.events.start()

        self._running = True
        self._start_time = datetime.now(UTC)

        logger.info("Bot Integrator started successfully")

    async def stop(self) -> None:
        """Stop all modules."""
        if not self._running:
            return

        logger.info("Stopping Bot Integrator...")

        self._running = False

        # Stop in reverse order
        self.events.stop()
        await self.health.stop()
        await self.services.stop_all()

        # Publish shutdown event
        await self.events.publish(
            Event(
                type=EventTypes.SERVICE_STOPPED,
                data={"service": "bot_integrator"},
            )
        )

        logger.info("Bot Integrator stopped")

    async def _init_enhanced_polling(self) -> bool:
        """Initialize enhanced polling module."""
        if not self.config.enable_enhanced_polling:
            return False

        if not self.dmarket_api:
            logger.warning("Enhanced polling requires DMarket API")
            return False

        try:
            from src.dmarket.enhanced_polling import EnhancedPollingEngine

            self._enhanced_polling = EnhancedPollingEngine(
                api_client=self.dmarket_api,
            )

            self.services.register(
                "enhanced_polling",
                self._enhanced_polling,
                depends_on=["dmarket_api"],
            )
            self.health.register_component(
                "enhanced_polling",
                self._enhanced_polling,
            )

            return True

        except ImportError as e:
            logger.warning(f"Enhanced polling module not available: {e}")
            return False

    async def _init_price_analytics(self) -> bool:
        """Initialize price analytics module."""
        if not self.config.enable_price_analytics:
            return False

        try:
            from src.analytics.price_analytics import PriceAnalytics

            self._price_analytics = PriceAnalytics()

            self.services.register("price_analytics", self._price_analytics)

            return True

        except ImportError as e:
            logger.warning(f"Price analytics module not available: {e}")
            return False

    async def _init_auto_listing(self) -> bool:
        """Initialize auto-listing module."""
        if not self.config.enable_auto_listing:
            return False

        if not self.dmarket_api:
            logger.warning("Auto-listing requires DMarket API")
            return False

        try:
            from src.dmarket.auto_listing import AutoListingEngine, ListingConfig

            listing_config = ListingConfig(
                min_price_usd=self.config.min_item_price_for_listing,
                target_profit_margin=self.config.target_profit_margin,
            )

            self._auto_listing = AutoListingEngine(
                dmarket_api=self.dmarket_api,
                waxpeer_api=self.waxpeer_api,
                config=listing_config,
            )

            self.services.register(
                "auto_listing",
                self._auto_listing,
                depends_on=["dmarket_api"],
            )
            self.health.register_component("auto_listing", self._auto_listing)

            return True

        except ImportError as e:
            logger.warning(f"Auto-listing module not available: {e}")
            return False

    async def _init_portfolio_tracker(self) -> bool:
        """Initialize portfolio tracker module."""
        if not self.config.enable_portfolio_tracker:
            return False

        try:
            from src.portfolio.portfolio_tracker import PortfolioTracker

            self._portfolio_tracker = PortfolioTracker()

            self.services.register("portfolio_tracker", self._portfolio_tracker)

            return True

        except ImportError as e:
            logger.warning(f"Portfolio tracker module not available: {e}")
            return False

    async def _init_custom_alerts(self) -> bool:
        """Initialize custom alerts module."""
        if not self.config.enable_custom_alerts:
            return False

        try:
            from src.telegram_bot.notifications.custom_alerts import AlertManager

            self._custom_alerts = AlertManager()

            self.services.register("custom_alerts", self._custom_alerts)

            return True

        except ImportError as e:
            logger.warning(f"Custom alerts module not available: {e}")
            return False

    async def _init_watchlist(self) -> bool:
        """Initialize watchlist module."""
        if not self.config.enable_watchlist:
            return False

        try:
            from src.portfolio.watchlist import WatchlistManager

            self._watchlist = WatchlistManager()

            self.services.register("watchlist", self._watchlist)

            return True

        except ImportError as e:
            logger.warning(f"Watchlist module not available: {e}")
            return False

    async def _init_anomaly_detection(self) -> bool:
        """Initialize anomaly detection module."""
        if not self.config.enable_anomaly_detection:
            return False

        try:
            from src.ml.anomaly_detection import AnomalyDetector

            self._anomaly_detection = AnomalyDetector(
                z_score_threshold=self.config.anomaly_detection_threshold,
            )

            self.services.register("anomaly_detection", self._anomaly_detection)

            return True

        except ImportError as e:
            logger.warning(f"Anomaly detection module not available: {e}")
            return False

    async def _init_smart_recommendations(self) -> bool:
        """Initialize smart recommendations module."""
        if not self.config.enable_smart_recommendations:
            return False

        try:
            from src.ml.smart_recommendations import SmartRecommendations

            self._smart_recommendations = SmartRecommendations()

            self.services.register(
                "smart_recommendations",
                self._smart_recommendations,
            )

            return True

        except ImportError as e:
            logger.warning(f"Smart recommendations module not available: {e}")
            return False

    async def _init_trading_automation(self) -> bool:
        """Initialize trading automation module."""
        if not self.config.enable_trading_automation:
            return False

        if not self.dmarket_api:
            logger.warning("Trading automation requires DMarket API")
            return False

        try:
            from src.trading.trading_automation import TradingAutomation

            self._trading_automation = TradingAutomation(
                dry_run=True,  # Safe mode by default
            )

            self.services.register(
                "trading_automation",
                self._trading_automation,
                depends_on=["dmarket_api"],
            )
            self.health.register_component(
                "trading_automation",
                self._trading_automation,
            )

            return True

        except ImportError as e:
            logger.warning(f"Trading automation module not available: {e}")
            return False

    async def _init_reports(self) -> bool:
        """Initialize reports module."""
        if not self.config.enable_reports:
            return False

        try:
            from src.reporting.reports import ReportGenerator

            self._reports = ReportGenerator()

            self.services.register("reports", self._reports)

            return True

        except ImportError as e:
            logger.warning(f"Reports module not available: {e}")
            return False

    async def _init_security(self) -> bool:
        """Initialize security module."""
        if not self.config.enable_security:
            return False

        try:
            from src.security.security import SecurityManager

            self._security = SecurityManager()

            self.services.register("security", self._security)

            return True

        except ImportError as e:
            logger.warning(f"Security module not available: {e}")
            return False

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for inter-module communication."""

        # Price change -> Analytics
        async def on_price_update(event: Event) -> None:
            if self._price_analytics and self._price_analytics.is_ready():
                item_id = event.data.get("item_id")
                price = event.data.get("price")
                if item_id and price:
                    self._price_analytics.add_price(item_id, price)

        self.events.subscribe(EventTypes.PRICE_UPDATE, on_price_update)

        # Price change -> Alerts
        async def on_price_change(event: Event) -> None:
            if self._custom_alerts:
                await self._custom_alerts.check_alerts(
                    item_id=event.data.get("item_id"),
                    old_price=event.data.get("old_price"),
                    new_price=event.data.get("new_price"),
                )

        self.events.subscribe(EventTypes.PRICE_CHANGE, on_price_change)

        # Trade executed -> Portfolio
        async def on_trade_executed(event: Event) -> None:
            if self._portfolio_tracker:
                await self._portfolio_tracker.record_trade(
                    item_id=event.data.get("item_id"),
                    action=event.data.get("action"),
                    price=event.data.get("price"),
                    quantity=event.data.get("quantity", 1),
                )

        self.events.subscribe(EventTypes.TRADE_EXECUTED, on_trade_executed)

        # Analytics signal -> Recommendations
        async def on_analytics_signal(event: Event) -> None:
            if self._smart_recommendations:
                await self._smart_recommendations.process_signal(
                    signal_type=event.data.get("signal_type"),
                    item_id=event.data.get("item_id"),
                    data=event.data,
                )

        self.events.subscribe(EventTypes.ANALYTICS_SIGNAL, on_analytics_signal)

        logger.debug("Event handlers configured")

    # Public API for accessing modules

    @property
    def enhanced_polling(self):
        """Get enhanced polling module."""
        return self._enhanced_polling

    @property
    def price_analytics(self):
        """Get price analytics module."""
        return self._price_analytics

    @property
    def auto_listing(self):
        """Get auto-listing module."""
        return self._auto_listing

    @property
    def portfolio_tracker(self):
        """Get portfolio tracker module."""
        return self._portfolio_tracker

    @property
    def custom_alerts(self):
        """Get custom alerts module."""
        return self._custom_alerts

    @property
    def watchlist(self):
        """Get watchlist module."""
        return self._watchlist

    @property
    def anomaly_detection(self):
        """Get anomaly detection module."""
        return self._anomaly_detection

    @property
    def smart_recommendations(self):
        """Get smart recommendations module."""
        return self._smart_recommendations

    @property
    def trading_automation(self):
        """Get trading automation module."""
        return self._trading_automation

    @property
    def reports(self):
        """Get reports module."""
        return self._reports

    @property
    def security(self):
        """Get security module."""
        return self._security

    async def get_status(self) -> dict[str, Any]:
        """Get integrator status.

        Returns:
            Dictionary with status information
        """
        health_status = await self.health.check_health()

        return {
            "initialized": self._initialized,
            "running": self._running,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime_seconds": (
                (datetime.now(UTC) - self._start_time).total_seconds()
                if self._start_time
                else 0
            ),
            "services": self.services.get_health_summary(),
            "health": health_status.to_dict(),
            "events": self.events.get_stats(),
            "modules": {
                "enhanced_polling": self._enhanced_polling is not None,
                "price_analytics": self._price_analytics is not None,
                "auto_listing": self._auto_listing is not None,
                "portfolio_tracker": self._portfolio_tracker is not None,
                "custom_alerts": self._custom_alerts is not None,
                "watchlist": self._watchlist is not None,
                "anomaly_detection": self._anomaly_detection is not None,
                "smart_recommendations": self._smart_recommendations is not None,
                "trading_automation": self._trading_automation is not None,
                "reports": self._reports is not None,
                "security": self._security is not None,
            },
        }


# Global instance for easy access
_integrator: BotIntegrator | None = None


def get_integrator() -> BotIntegrator | None:
    """Get global integrator instance.

    Returns:
        BotIntegrator instance or None
    """
    return _integrator


def set_integrator(integrator: BotIntegrator) -> None:
    """Set global integrator instance.

    Args:
        integrator: BotIntegrator instance
    """
    global _integrator
    _integrator = integrator
