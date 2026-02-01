"""Configuration management utilities for DMarket Bot.

This module provides utilities for loading and managing configuration
from various sources including environment variables, YAML files, and defaults.
"""

import contextlib
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Any

import yaml


# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = "sqlite:///data/dmarket_bot.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class BotConfig:
    """Telegram bot configuration."""

    token: str = ""
    username: str = "dmarket_bot"
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_host: str = "127.0.0.1"  # По умолчанию localhost для безопасности
    webhook_port: int = 8443


@dataclass
class DMarketConfig:
    """DMarket API configuration."""

    api_url: str = "https://api.dmarket.com"
    public_key: str = ""
    secret_key: str = ""
    rate_limit: int = 30


@dataclass
class SecurityConfig:
    """Security configuration."""

    allowed_users: list[str | int] = field(default_factory=list)
    admin_users: list[str | int] = field(default_factory=list)


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: str = "logs/dmarket_bot.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    rotation: str = "1 week"
    retention: str = "1 month"


@dataclass
class TradingConfig:
    """Trading configuration."""

    max_item_price: float = 20.0
    min_profit_percent: float = 10.0
    games: list[str] = field(default_factory=lambda: ["csgo", "rust"])
    min_sales_last_month: int = 100
    max_inventory_items: int = 30

    # Universal percentage-based settings (new!)
    max_buy_percent: float = 0.25  # Max 25% of balance per item
    min_buy_percent: float = 0.005  # Min 0.5% of balance per item
    reserve_percent: float = 0.05  # Keep 5% as reserve
    max_stack_percent: float = 0.15  # Max 15% in same item type
    enable_smart_mode: bool = True  # Use dynamic limits based on balance


@dataclass
class FiltersConfig:
    """Item filtering configuration."""

    min_liquidity: int = 50
    max_items_in_stock: int = 5


@dataclass
class InventoryConfig:
    """Inventory management configuration."""

    auto_sell: bool = True
    undercut_price: float = 0.01
    min_margin_threshold: float = 1.02
    auto_repricing: bool = True  # Enable automatic price reduction
    repricing_interval_hours: int = 48  # Reduce price after this many hours
    max_price_cut_percent: float = 15.0  # Max price reduction percentage


@dataclass
class TradingSafetyConfig:
    """Trading safety configuration."""

    # Санитарная проверка цен
    max_price_multiplier: float = 1.5  # Максимум 50% выше средней цены
    price_history_days: int = 7  # Период анализа истории цен
    min_history_samples: int = 3  # Минимум сэмплов для расчета средней
    enable_price_sanity_check: bool = True  # Включить проверку цен


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    # Мониторинг rate limit
    warning_threshold: float = 0.9  # Порог для уведомлений (90%)
    enable_notifications: bool = True  # Включить уведомления

    # Exponential backoff
    base_retry_delay: float = 1.0  # Базовая задержка (секунды)
    max_backoff_time: float = 60.0  # Максимальное время backoff (секунды)
    max_retry_attempts: int = 5  # Максимум попыток повтора

    # Лимиты для разных эндпоинтов (запросов в секунду)
    market_limit: int = 2  # Рыночные запросы
    trade_limit: int = 1  # Торговые операции
    user_limit: int = 5  # Пользовательские данные
    balance_limit: int = 10  # Запросы баланса
    other_limit: int = 5  # Прочие запросы


@dataclass
class DailyReportConfig:
    """Daily report configuration."""

    enabled: bool = True  # Включить ежедневные отчёты
    report_time_hour: int = 9  # Час отправки отчёта (UTC)
    report_time_minute: int = 0  # Минута отправки отчёта
    include_days: int = 1  # Количество дней в отчёте


@dataclass
class WaxpeerConfig:
    """Waxpeer P2P integration configuration."""

    enabled: bool = False  # Включить интеграцию с Waxpeer
    api_key: str = ""  # API ключ Waxpeer

    # Настройки наценок
    markup: float = 10.0  # Наценка для обычных скинов (%)
    rare_markup: float = 25.0  # Наценка для редких скинов (%)
    ultra_markup: float = 40.0  # Наценка для JACKPOT скинов (%)
    min_profit: float = 5.0  # Минимальная прибыль для листинга (%)

    # Авто-репрайсинг
    reprice: bool = True  # Включить автоматический undercut
    reprice_interval: int = 30  # Интервал проверки цен (минуты)

    # Shadow Listing
    shadow: bool = True  # Умное ценообразование
    scarcity_threshold: int = 3  # Порог дефицита

    # Auto-Hold
    auto_hold: bool = True  # Не выставлять редкие предметы
    alert_on_rare: bool = True  # Уведомлять о редких находках


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration."""

    prometheus_host: str = "127.0.0.1"  # По умолчанию localhost для безопасности
    prometheus_port: int = 9090
    enabled: bool = True


@dataclass
class Config:
    """Main application configuration."""

    bot: BotConfig = field(default_factory=BotConfig)
    dmarket: DMarketConfig = field(default_factory=DMarketConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    inventory: InventoryConfig = field(default_factory=InventoryConfig)
    trading_safety: TradingSafetyConfig = field(default_factory=TradingSafetyConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    daily_report: DailyReportConfig = field(default_factory=DailyReportConfig)
    waxpeer: WaxpeerConfig = field(default_factory=WaxpeerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    debug: bool = False
    testing: bool = False
    dry_run: bool = True  # По умолчанию True для защиты
    environment: str = "development"  # development, staging, production

    @classmethod
    def load(cls, config_path: str | None = None) -> "Config":
        """Load configuration from file and environment variables.

        Args:
            config_path: Path to configuration file (YAML)

        Returns:
            Config: Loaded configuration

        """
        config = cls()

        # Load from YAML file if provided
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                config._update_from_dict(yaml_config)
                logger.info(f"Configuration loaded from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

        # Override with environment variables
        config._update_from_env()

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            # In testing or dev, we might want to continue, but in prod it should fail
            if config.environment == "production":
                raise

        return config

    def _update_from_dict(self, data: dict[str, Any]) -> None:
        """Update configuration from dictionary."""
        if "bot" in data:
            bot_data = data["bot"]
            self.bot.token = bot_data.get("token", self.bot.token)
            self.bot.username = bot_data.get("username", self.bot.username)
            if "webhook" in bot_data:
                webhook = bot_data["webhook"]
                self.bot.webhook_url = webhook.get("url", self.bot.webhook_url)
                self.bot.webhook_secret = webhook.get("secret", self.bot.webhook_secret)

        if "dmarket" in data:
            dmarket_data = data["dmarket"]
            self.dmarket.api_url = dmarket_data.get("api_url", self.dmarket.api_url)
            self.dmarket.public_key = dmarket_data.get(
                "public_key",
                self.dmarket.public_key,
            )
            self.dmarket.secret_key = dmarket_data.get(
                "secret_key",
                self.dmarket.secret_key,
            )
            self.dmarket.rate_limit = dmarket_data.get(
                "rate_limit",
                self.dmarket.rate_limit,
            )

        if "database" in data:
            db_data = data["database"]
            self.database.url = db_data.get("url", self.database.url)
            self.database.echo = db_data.get("echo", self.database.echo)
            self.database.pool_size = db_data.get(
                "pool_size",
                self.database.pool_size,
            )
            self.database.max_overflow = db_data.get(
                "max_overflow",
                self.database.max_overflow,
            )

        if "security" in data:
            security_data = data["security"]
            allowed = security_data.get("allowed_users", "")
            if allowed:
                self.security.allowed_users = [u.strip() for u in allowed.split(",")]
            admin = security_data.get("admin_users", "")
            if admin:
                self.security.admin_users = [u.strip() for u in admin.split(",")]

        if "logging" in data:
            log_data = data["logging"]
            self.logging.level = log_data.get("level", self.logging.level)
            self.logging.file = log_data.get("file", self.logging.file)

        if "trading" in data:
            trading_data = data["trading"]
            self.trading.max_item_price = trading_data.get(
                "max_item_price", self.trading.max_item_price
            )
            self.trading.min_profit_percent = trading_data.get(
                "min_profit_percent", self.trading.min_profit_percent
            )
            self.trading.games = trading_data.get("games", self.trading.games)
            self.trading.min_sales_last_month = trading_data.get(
                "min_sales_last_month", self.trading.min_sales_last_month
            )
            self.trading.max_inventory_items = trading_data.get(
                "max_inventory_items", self.trading.max_inventory_items
            )

        if "filters" in data:
            filters_data = data["filters"]
            self.filters.min_liquidity = filters_data.get(
                "min_liquidity", self.filters.min_liquidity
            )
            self.filters.max_items_in_stock = filters_data.get(
                "max_items_in_stock", self.filters.max_items_in_stock
            )

        if "inventory" in data:
            inv_data = data["inventory"]
            self.inventory.auto_sell = inv_data.get("auto_sell", self.inventory.auto_sell)
            self.inventory.undercut_price = inv_data.get(
                "undercut_price", self.inventory.undercut_price
            )
            self.inventory.min_margin_threshold = inv_data.get(
                "min_margin_threshold", self.inventory.min_margin_threshold
            )

        if "trading_safety" in data:
            safety_data = data["trading_safety"]
            self.trading_safety.max_price_multiplier = safety_data.get(
                "max_price_multiplier",
                self.trading_safety.max_price_multiplier,
            )
            self.trading_safety.price_history_days = safety_data.get(
                "price_history_days",
                self.trading_safety.price_history_days,
            )
            self.trading_safety.min_history_samples = safety_data.get(
                "min_history_samples",
                self.trading_safety.min_history_samples,
            )
            self.trading_safety.enable_price_sanity_check = safety_data.get(
                "enable_price_sanity_check",
                self.trading_safety.enable_price_sanity_check,
            )

        if "daily_report" in data:
            report_data = data["daily_report"]
            self.daily_report.enabled = report_data.get(
                "enabled",
                self.daily_report.enabled,
            )
            self.daily_report.report_time_hour = report_data.get(
                "report_time_hour",
                self.daily_report.report_time_hour,
            )
            self.daily_report.report_time_minute = report_data.get(
                "report_time_minute",
                self.daily_report.report_time_minute,
            )
            self.daily_report.include_days = report_data.get(
                "include_days",
                self.daily_report.include_days,
            )

        if "rate_limit" in data:
            rl_data = data["rate_limit"]
            self.rate_limit.warning_threshold = rl_data.get(
                "warning_threshold",
                self.rate_limit.warning_threshold,
            )
            self.rate_limit.enable_notifications = rl_data.get(
                "enable_notifications",
                self.rate_limit.enable_notifications,
            )
            self.rate_limit.base_retry_delay = rl_data.get(
                "base_retry_delay",
                self.rate_limit.base_retry_delay,
            )
            self.rate_limit.max_backoff_time = rl_data.get(
                "max_backoff_time",
                self.rate_limit.max_backoff_time,
            )
            self.rate_limit.max_retry_attempts = rl_data.get(
                "max_retry_attempts",
                self.rate_limit.max_retry_attempts,
            )
            self.rate_limit.market_limit = rl_data.get(
                "market_limit",
                self.rate_limit.market_limit,
            )
            self.rate_limit.trade_limit = rl_data.get(
                "trade_limit",
                self.rate_limit.trade_limit,
            )
            self.rate_limit.user_limit = rl_data.get(
                "user_limit",
                self.rate_limit.user_limit,
            )
            self.rate_limit.balance_limit = rl_data.get(
                "balance_limit",
                self.rate_limit.balance_limit,
            )
            self.rate_limit.other_limit = rl_data.get(
                "other_limit",
                self.rate_limit.other_limit,
            )

    # ============================================================================
    # Environment variable helper methods (Phase 2 refactoring)
    # ============================================================================

    @staticmethod
    def _get_env_int(name: str, default: int) -> int:
        """Get integer from environment variable.

        Args:
            name: Environment variable name
            default: Default value

        Returns:
            Integer value or default
        """
        value = os.getenv(name)
        if value:
            with contextlib.suppress(ValueError):
                return int(value)
        return default

    @staticmethod
    def _get_env_float(name: str, default: float) -> float:
        """Get float from environment variable.

        Args:
            name: Environment variable name
            default: Default value

        Returns:
            Float value or default
        """
        value = os.getenv(name)
        if value:
            with contextlib.suppress(ValueError):
                return float(value)
        return default

    @staticmethod
    def _get_env_bool(name: str, default: bool) -> bool:
        """Get boolean from environment variable.

        Args:
            name: Environment variable name
            default: Default value

        Returns:
            Boolean value
        """
        value = os.getenv(name)
        if value:
            return value.lower() == "true"
        return default

    @staticmethod
    def _get_env_list(name: str, default: list[str] | None = None) -> list[str]:
        """Get list from comma-separated environment variable.

        Args:
            name: Environment variable name
            default: Default list

        Returns:
            List of strings
        """
        value = os.getenv(name, "")
        if value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return default or []

    def _update_bot_from_env(self) -> None:
        """Update bot configuration from environment."""
        self.bot.token = os.getenv("TELEGRAM_BOT_TOKEN", self.bot.token)
        self.bot.username = os.getenv("BOT_USERNAME", self.bot.username)
        self.bot.webhook_url = os.getenv("WEBHOOK_URL", self.bot.webhook_url)
        self.bot.webhook_secret = os.getenv("WEBHOOK_SECRET", self.bot.webhook_secret)
        self.bot.webhook_host = os.getenv("WEBHOOK_HOST", self.bot.webhook_host)
        self.bot.webhook_port = self._get_env_int("WEBHOOK_PORT", self.bot.webhook_port)

    def _update_dmarket_from_env(self) -> None:
        """Update DMarket configuration from environment."""
        self.dmarket.api_url = os.getenv("DMARKET_API_URL", self.dmarket.api_url)
        self.dmarket.public_key = os.getenv("DMARKET_PUBLIC_KEY", self.dmarket.public_key)
        self.dmarket.secret_key = os.getenv("DMARKET_SECRET_KEY", self.dmarket.secret_key)
        self.dmarket.rate_limit = self._get_env_int("API_RATE_LIMIT", self.dmarket.rate_limit)

    def _update_trading_from_env(self) -> None:
        """Update trading configuration from environment."""
        self.trading.max_item_price = self._get_env_float(
            "MAX_ITEM_PRICE", self.trading.max_item_price
        )
        self.trading.min_profit_percent = self._get_env_float(
            "MIN_PROFIT_PERCENT", self.trading.min_profit_percent
        )
        self.trading.min_sales_last_month = self._get_env_int(
            "MIN_SALES_LAST_MONTH", self.trading.min_sales_last_month
        )
        self.trading.max_inventory_items = self._get_env_int(
            "MAX_INVENTORY_ITEMS", self.trading.max_inventory_items
        )
        self.trading.max_buy_percent = self._get_env_float(
            "MAX_BUY_PERCENT", self.trading.max_buy_percent
        )
        self.trading.min_buy_percent = self._get_env_float(
            "MIN_BUY_PERCENT", self.trading.min_buy_percent
        )
        self.trading.reserve_percent = self._get_env_float(
            "RESERVE_PERCENT", self.trading.reserve_percent
        )
        self.trading.max_stack_percent = self._get_env_float(
            "MAX_STACK_PERCENT", self.trading.max_stack_percent
        )
        self.trading.enable_smart_mode = self._get_env_bool(
            "ENABLE_SMART_MODE", self.trading.enable_smart_mode
        )

    def _update_waxpeer_from_env(self) -> None:
        """Update Waxpeer configuration from environment."""
        self.waxpeer.enabled = self._get_env_bool("WAXPEER_ENABLED", self.waxpeer.enabled)
        self.waxpeer.api_key = os.getenv("WAXPEER_API_KEY", self.waxpeer.api_key)
        self.waxpeer.markup = self._get_env_float("WAXPEER_MARKUP", self.waxpeer.markup)
        self.waxpeer.rare_markup = self._get_env_float(
            "WAXPEER_RARE_MARKUP", self.waxpeer.rare_markup
        )
        self.waxpeer.ultra_markup = self._get_env_float(
            "WAXPEER_ULTRA_MARKUP", self.waxpeer.ultra_markup
        )
        self.waxpeer.min_profit = self._get_env_float(
            "WAXPEER_MIN_PROFIT", self.waxpeer.min_profit
        )
        self.waxpeer.reprice = self._get_env_bool("WAXPEER_REPRICE", self.waxpeer.reprice)
        self.waxpeer.reprice_interval = self._get_env_int(
            "WAXPEER_REPRICE_INTERVAL", self.waxpeer.reprice_interval
        )
        self.waxpeer.shadow = self._get_env_bool("WAXPEER_SHADOW", self.waxpeer.shadow)
        self.waxpeer.scarcity_threshold = self._get_env_int(
            "WAXPEER_SCARCITY", self.waxpeer.scarcity_threshold
        )
        self.waxpeer.auto_hold = self._get_env_bool("WAXPEER_AUTO_HOLD", self.waxpeer.auto_hold)
        self.waxpeer.alert_on_rare = self._get_env_bool("WAXPEER_ALERT", self.waxpeer.alert_on_rare)

    # ============================================================================
    # End of environment variable helper methods
    # ============================================================================

    def _update_from_env(self) -> None:
        """Update configuration from environment variables."""
        # Update each config section using helper methods (Phase 2 refactoring)
        self._update_bot_from_env()
        self._update_dmarket_from_env()
        self._update_trading_from_env()
        self._update_waxpeer_from_env()

        # Environment
        self.environment = os.getenv("ENVIRONMENT", self.environment)

        # Monitoring configuration
        self.monitoring.prometheus_host = os.getenv(
            "PROMETHEUS_HOST", self.monitoring.prometheus_host
        )
        self.monitoring.prometheus_port = self._get_env_int(
            "PROMETHEUS_PORT", self.monitoring.prometheus_port
        )
        self.monitoring.enabled = self._get_env_bool("MONITORING_ENABLED", self.monitoring.enabled)

        # Database configuration
        self.database.url = os.getenv("DATABASE_URL", self.database.url)

        # Security configuration
        allowed = self._get_env_list("ALLOWED_USERS")
        if allowed:
            self.security.allowed_users = allowed
        admin = self._get_env_list("ADMIN_USERS")
        if admin:
            self.security.admin_users = admin

        # Logging configuration
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
        self.logging.file = os.getenv("LOG_FILE", self.logging.file)

        # Debug and testing flags
        self.debug = self._get_env_bool("DEBUG", self.debug)
        self.testing = self._get_env_bool("TESTING", self.testing)

        # Filters configuration
        self.filters.min_liquidity = self._get_env_int(
            "MIN_LIQUIDITY_SCORE", self.filters.min_liquidity
        )

        # Inventory configuration
        self.inventory.undercut_price = self._get_env_float(
            "PRICE_STEP", self.inventory.undercut_price
        )
        self.inventory.min_margin_threshold = self._get_env_float(
            "MIN_MARGIN_THRESHOLD", self.inventory.min_margin_threshold
        )
        self.inventory.auto_repricing = self._get_env_bool(
            "AUTO_REPRICING", self.inventory.auto_repricing
        )
        self.inventory.repricing_interval_hours = self._get_env_int(
            "REPRICING_INTERVAL_HOURS", self.inventory.repricing_interval_hours
        )
        self.inventory.max_price_cut_percent = self._get_env_float(
            "MAX_PRICE_CUT_PERCENT", self.inventory.max_price_cut_percent
        )

        # Trading safety mode - defaults to True for safety
        self.dry_run = self._get_env_bool("DRY_RUN", self.dry_run)

        # Trading safety configuration
        self.trading_safety.max_price_multiplier = self._get_env_float(
            "MAX_PRICE_MULTIPLIER", self.trading_safety.max_price_multiplier
        )
        self.trading_safety.price_history_days = self._get_env_int(
            "PRICE_HISTORY_DAYS", self.trading_safety.price_history_days
        )
        self.trading_safety.min_history_samples = self._get_env_int(
            "MIN_HISTORY_SAMPLES", self.trading_safety.min_history_samples
        )
        self.trading_safety.enable_price_sanity_check = self._get_env_bool(
            "ENABLE_PRICE_SANITY_CHECK", self.trading_safety.enable_price_sanity_check
        )

        # Daily report configuration
        self.daily_report.enabled = self._get_env_bool(
            "DAILY_REPORT_ENABLED", self.daily_report.enabled
        )
        self.daily_report.report_time_hour = self._get_env_int(
            "DAILY_REPORT_HOUR", self.daily_report.report_time_hour
        )
        self.daily_report.report_time_minute = self._get_env_int(
            "DAILY_REPORT_MINUTE", self.daily_report.report_time_minute
        )
        self.daily_report.include_days = self._get_env_int(
            "DAILY_REPORT_DAYS", self.daily_report.include_days
        )

        # Rate limit configuration
        self.rate_limit.warning_threshold = self._get_env_float(
            "RATE_LIMIT_WARNING_THRESHOLD", self.rate_limit.warning_threshold
        )
        self.rate_limit.enable_notifications = self._get_env_bool(
            "RATE_LIMIT_NOTIFICATIONS", self.rate_limit.enable_notifications
        )
        self.rate_limit.base_retry_delay = self._get_env_float(
            "RATE_LIMIT_BASE_DELAY", self.rate_limit.base_retry_delay
        )
        self.rate_limit.max_backoff_time = self._get_env_float(
            "RATE_LIMIT_MAX_BACKOFF", self.rate_limit.max_backoff_time
        )
        self.rate_limit.max_retry_attempts = self._get_env_int(
            "RATE_LIMIT_MAX_ATTEMPTS", self.rate_limit.max_retry_attempts
        )

    def validate(self) -> None:
        """Validate configuration and raise errors for required missing values."""
        errors = []

        # Validate Telegram Bot configuration
        if not self.bot.token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        elif not self.bot.token.startswith("bot") and ":" not in self.bot.token:
            errors.append(
                "TELEGRAM_BOT_TOKEN appears invalid "
                "(should be in format: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)"
            )

        # Validate DMarket API configuration (unless in testing mode)
        if not self.testing:
            if not self.dmarket.public_key:
                errors.append("DMARKET_PUBLIC_KEY is required (unless in testing mode)")
            elif len(self.dmarket.public_key) < 20:
                errors.append("DMARKET_PUBLIC_KEY appears too short")

            if not self.dmarket.secret_key:
                errors.append("DMARKET_SECRET_KEY is required (unless in testing mode)")
            elif len(self.dmarket.secret_key) < 20:
                errors.append("DMARKET_SECRET_KEY appears too short")

            # Validate API URL format
            if not self.dmarket.api_url.startswith(("http://", "https://")):
                errors.append(
                    "DMARKET_API_URL must start with http:// or https://, "
                    f"got: {self.dmarket.api_url}"
                )

            # Validate rate limit
            if self.dmarket.rate_limit <= 0:
                errors.append(
                    f"DMARKET rate_limit must be positive, got: {self.dmarket.rate_limit}"
                )

        # Validate database URL
        if not self.database.url:
            errors.append("DATABASE_URL is required")
        elif not self.database.url.startswith(("sqlite://", "postgresql://", "mysql://")):
            errors.append(
                "DATABASE_URL has unsupported scheme. "
                "Supported: sqlite://, postgresql://, mysql://. "
                f"Got: {self.database.url}"
            )

        # Validate logging level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level.upper() not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of {valid_log_levels}, got: {self.logging.level}")

        # Validate security settings (convert user IDs)
        if self.security.allowed_users:
            try:
                self.security.allowed_users = [
                    int(uid) if isinstance(uid, str) and uid.isdigit() else uid
                    for uid in self.security.allowed_users
                ]
            except ValueError as e:
                errors.append(f"Invalid ALLOWED_USERS format: {e}")

        if self.security.admin_users:
            try:
                self.security.admin_users = [
                    int(uid) if isinstance(uid, str) and uid.isdigit() else uid
                    for uid in self.security.admin_users
                ]
            except ValueError as e:
                errors.append(f"Invalid ADMIN_USERS format: {e}")

        # Validate pool settings
        if self.database.pool_size <= 0:
            errors.append(f"Database pool_size must be positive, got: {self.database.pool_size}")

        if self.database.max_overflow < 0:
            errors.append(
                f"Database max_overflow must be non-negative, got: {self.database.max_overflow}"
            )

        # Log safety warnings
        if not self.dry_run and not self.testing:
            logger.warning(
                "⚠️  DRY_RUN=false - BOT WILL MAKE REAL TRADES! Make sure you understand the risks."
            )
        elif self.dry_run:
            logger.info("✅ DRY_RUN=true - Bot is in safe mode (no real trades will be made)")

        # Raise all errors at once
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValueError(error_msg)


# Global settings instance
settings = Config.load()
