"""Comprehensive tests for src/utils/config.py.

This module provides extensive testing for configuration management
to achieve 95%+ coverage.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

from src.utils.config import (
    BotConfig,
    Config,
    DailyReportConfig,
    DatabaseConfig,
    DMarketConfig,
    FiltersConfig,
    InventoryConfig,
    LoggingConfig,
    MonitoringConfig,
    RateLimitConfig,
    SecurityConfig,
    TradingConfig,
    TradingSafetyConfig,
    WaxpeerConfig,
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DatabaseConfig()
        assert config.url == "sqlite:///data/dmarket_bot.db"
        assert config.echo is False
        assert config.pool_size == 5
        assert config.max_overflow == 10

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = DatabaseConfig(
            url="postgresql://localhost/test",
            echo=True,
            pool_size=10,
            max_overflow=20,
        )
        assert config.url == "postgresql://localhost/test"
        assert config.echo is True
        assert config.pool_size == 10
        assert config.max_overflow == 20


class TestBotConfig:
    """Tests for BotConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default bot configuration."""
        config = BotConfig()
        assert config.token == ""
        assert config.username == "dmarket_bot"
        assert config.webhook_url == ""
        assert config.webhook_secret == ""
        assert config.webhook_host == "127.0.0.1"
        assert config.webhook_port == 8443

    def test_custom_values(self) -> None:
        """Test custom bot configuration."""
        config = BotConfig(
            token="123:ABC",
            username="my_bot",
            webhook_url="https://example.com/webhook",
            webhook_port=443,
        )
        assert config.token == "123:ABC"
        assert config.username == "my_bot"
        assert config.webhook_url == "https://example.com/webhook"
        assert config.webhook_port == 443


class TestDMarketConfig:
    """Tests for DMarketConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default DMarket configuration."""
        config = DMarketConfig()
        assert config.api_url == "https://api.dmarket.com"
        assert config.public_key == ""
        assert config.secret_key == ""
        assert config.rate_limit == 30

    def test_custom_values(self) -> None:
        """Test custom DMarket configuration."""
        config = DMarketConfig(
            api_url="https://custom.api.com",
            public_key="pub123",
            secret_key="sec456",
            rate_limit=60,
        )
        assert config.api_url == "https://custom.api.com"
        assert config.public_key == "pub123"
        assert config.secret_key == "sec456"
        assert config.rate_limit == 60


class TestSecurityConfig:
    """Tests for SecurityConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.allowed_users == []
        assert config.admin_users == []

    def test_custom_values(self) -> None:
        """Test custom security configuration."""
        config = SecurityConfig(
            allowed_users=[123, 456],
            admin_users=[789],
        )
        assert config.allowed_users == [123, 456]
        assert config.admin_users == [789]


class TestLoggingConfig:
    """Tests for LoggingConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == "logs/dmarket_bot.log"
        assert "%(asctime)s" in config.format
        assert config.rotation == "1 week"
        assert config.retention == "1 month"

    def test_custom_values(self) -> None:
        """Test custom logging configuration."""
        config = LoggingConfig(
            level="DEBUG",
            file="/var/log/bot.log",
            rotation="1 day",
        )
        assert config.level == "DEBUG"
        assert config.file == "/var/log/bot.log"
        assert config.rotation == "1 day"


class TestTradingConfig:
    """Tests for TradingConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default trading configuration."""
        config = TradingConfig()
        assert config.max_item_price == 20.0
        assert config.min_profit_percent == 10.0
        assert config.games == ["csgo", "rust"]
        assert config.min_sales_last_month == 100
        assert config.max_inventory_items == 30
        assert config.max_buy_percent == 0.25
        assert config.min_buy_percent == 0.005
        assert config.reserve_percent == 0.05
        assert config.max_stack_percent == 0.15
        assert config.enable_smart_mode is True

    def test_custom_values(self) -> None:
        """Test custom trading configuration."""
        config = TradingConfig(
            max_item_price=50.0,
            min_profit_percent=15.0,
            games=["csgo", "dota2", "tf2"],
        )
        assert config.max_item_price == 50.0
        assert config.min_profit_percent == 15.0
        assert config.games == ["csgo", "dota2", "tf2"]


class TestFiltersConfig:
    """Tests for FiltersConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default filters configuration."""
        config = FiltersConfig()
        assert config.min_liquidity == 50
        assert config.max_items_in_stock == 5

    def test_custom_values(self) -> None:
        """Test custom filters configuration."""
        config = FiltersConfig(
            min_liquidity=100,
            max_items_in_stock=10,
        )
        assert config.min_liquidity == 100
        assert config.max_items_in_stock == 10


class TestInventoryConfig:
    """Tests for InventoryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default inventory configuration."""
        config = InventoryConfig()
        assert config.auto_sell is True
        assert config.undercut_price == 0.01
        assert config.min_margin_threshold == 1.02
        assert config.auto_repricing is True
        assert config.repricing_interval_hours == 48
        assert config.max_price_cut_percent == 15.0

    def test_custom_values(self) -> None:
        """Test custom inventory configuration."""
        config = InventoryConfig(
            auto_sell=False,
            undercut_price=0.05,
            repricing_interval_hours=24,
        )
        assert config.auto_sell is False
        assert config.undercut_price == 0.05
        assert config.repricing_interval_hours == 24


class TestTradingSafetyConfig:
    """Tests for TradingSafetyConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default trading safety configuration."""
        config = TradingSafetyConfig()
        assert config.max_price_multiplier == 1.5
        assert config.price_history_days == 7
        assert config.min_history_samples == 3
        assert config.enable_price_sanity_check is True

    def test_custom_values(self) -> None:
        """Test custom trading safety configuration."""
        config = TradingSafetyConfig(
            max_price_multiplier=2.0,
            price_history_days=14,
        )
        assert config.max_price_multiplier == 2.0
        assert config.price_history_days == 14


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default rate limit configuration."""
        config = RateLimitConfig()
        assert config.warning_threshold == 0.9
        assert config.enable_notifications is True
        assert config.base_retry_delay == 1.0
        assert config.max_backoff_time == 60.0
        assert config.max_retry_attempts == 5
        assert config.market_limit == 2
        assert config.trade_limit == 1
        assert config.user_limit == 5
        assert config.balance_limit == 10
        assert config.other_limit == 5

    def test_custom_values(self) -> None:
        """Test custom rate limit configuration."""
        config = RateLimitConfig(
            warning_threshold=0.8,
            max_retry_attempts=10,
        )
        assert config.warning_threshold == 0.8
        assert config.max_retry_attempts == 10


class TestDailyReportConfig:
    """Tests for DailyReportConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default daily report configuration."""
        config = DailyReportConfig()
        assert config.enabled is True
        assert config.report_time_hour == 9
        assert config.report_time_minute == 0
        assert config.include_days == 1

    def test_custom_values(self) -> None:
        """Test custom daily report configuration."""
        config = DailyReportConfig(
            enabled=False,
            report_time_hour=18,
            include_days=7,
        )
        assert config.enabled is False
        assert config.report_time_hour == 18
        assert config.include_days == 7


class TestWaxpeerConfig:
    """Tests for WaxpeerConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default Waxpeer configuration."""
        config = WaxpeerConfig()
        assert config.enabled is False
        assert config.api_key == ""
        assert config.markup == 10.0
        assert config.rare_markup == 25.0
        assert config.ultra_markup == 40.0
        assert config.min_profit == 5.0
        assert config.reprice is True
        assert config.reprice_interval == 30
        assert config.shadow is True
        assert config.scarcity_threshold == 3
        assert config.auto_hold is True
        assert config.alert_on_rare is True

    def test_custom_values(self) -> None:
        """Test custom Waxpeer configuration."""
        config = WaxpeerConfig(
            enabled=True,
            api_key="test_key",
            markup=15.0,
        )
        assert config.enabled is True
        assert config.api_key == "test_key"
        assert config.markup == 15.0


class TestMonitoringConfig:
    """Tests for MonitoringConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default monitoring configuration."""
        config = MonitoringConfig()
        assert config.prometheus_host == "127.0.0.1"
        assert config.prometheus_port == 9090
        assert config.enabled is True

    def test_custom_values(self) -> None:
        """Test custom monitoring configuration."""
        config = MonitoringConfig(
            prometheus_host="0.0.0.0",
            prometheus_port=9100,
            enabled=False,
        )
        assert config.prometheus_host == "0.0.0.0"
        assert config.prometheus_port == 9100
        assert config.enabled is False


class TestMainConfig:
    """Tests for main Config class."""

    def test_default_values(self) -> None:
        """Test default main configuration."""
        config = Config()
        assert isinstance(config.bot, BotConfig)
        assert isinstance(config.dmarket, DMarketConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.filters, FiltersConfig)
        assert isinstance(config.inventory, InventoryConfig)
        assert isinstance(config.trading_safety, TradingSafetyConfig)
        assert isinstance(config.rate_limit, RateLimitConfig)
        assert isinstance(config.daily_report, DailyReportConfig)
        assert isinstance(config.waxpeer, WaxpeerConfig)
        assert isinstance(config.monitoring, MonitoringConfig)
        assert config.debug is False
        assert config.testing is False
        assert config.dry_run is True
        assert config.environment == "development"


class TestConfigLoad:
    """Tests for Config.load() method."""

    @pytest.fixture()
    def clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean environment variables."""
        # Store original env vars
        original_env = os.environ.copy()

        # Clear relevant env vars
        env_vars_to_clear = [
            "TELEGRAM_BOT_TOKEN",
            "DMARKET_PUBLIC_KEY",
            "DMARKET_SECRET_KEY",
            "DMARKET_API_URL",
            "DATABASE_URL",
            "DEBUG",
            "TESTING",
            "DRY_RUN",
        ]
        for var in env_vars_to_clear:
            os.environ.pop(var, None)

        yield

        # Restore original env vars
        os.environ.clear()
        os.environ.update(original_env)

    def test_load_without_config_file(self, clean_env: None) -> None:
        """Test loading configuration without file."""
        config = Config.load(None)
        assert config is not None
        assert isinstance(config, Config)

    def test_load_with_nonexistent_file(self, clean_env: None) -> None:
        """Test loading with nonexistent config file."""
        config = Config.load("/nonexistent/path/config.yaml")
        assert config is not None
        assert isinstance(config, Config)

    def test_load_from_yaml_file(self, clean_env: None) -> None:
        """Test loading configuration from YAML file."""
        yaml_content = {
            "bot": {
                "token": "test_token",
                "username": "test_bot",
            },
            "dmarket": {
                "api_url": "https://test.api.com",
                "public_key": "test_public_key_12345678901234567890",
                "secret_key": "test_secret_key_12345678901234567890",
            },
            "database": {
                "url": "sqlite:///test.db",
                "echo": True,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name

        try:
            config = Config.load(temp_path)
            assert config.bot.token == "test_token"
            assert config.bot.username == "test_bot"
            assert config.dmarket.api_url == "https://test.api.com"
            assert config.database.echo is True
        finally:
            Path(temp_path).unlink()


class TestConfigUpdateFromEnv:
    """Tests for Config._update_from_env() method."""

    @pytest.fixture()
    def clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean environment variables."""
        original_env = os.environ.copy()
        yield
        os.environ.clear()
        os.environ.update(original_env)

    def test_bot_token_from_env(self, clean_env: None) -> None:
        """Test bot token from environment variable."""
        os.environ["TELEGRAM_BOT_TOKEN"] = "env_token_123"
        config = Config()
        config._update_from_env()
        assert config.bot.token == "env_token_123"

    def test_dmarket_keys_from_env(self, clean_env: None) -> None:
        """Test DMarket keys from environment variables."""
        os.environ["DMARKET_PUBLIC_KEY"] = "env_public_key"
        os.environ["DMARKET_SECRET_KEY"] = "env_secret_key"
        config = Config()
        config._update_from_env()
        assert config.dmarket.public_key == "env_public_key"
        assert config.dmarket.secret_key == "env_secret_key"

    def test_database_url_from_env(self, clean_env: None) -> None:
        """Test database URL from environment variable."""
        os.environ["DATABASE_URL"] = "postgresql://localhost/test"
        config = Config()
        config._update_from_env()
        assert config.database.url == "postgresql://localhost/test"

    def test_debug_flag_from_env(self, clean_env: None) -> None:
        """Test debug flag from environment variable."""
        os.environ["DEBUG"] = "true"
        config = Config()
        config._update_from_env()
        assert config.debug is True

    def test_testing_flag_from_env(self, clean_env: None) -> None:
        """Test testing flag from environment variable."""
        os.environ["TESTING"] = "true"
        config = Config()
        config._update_from_env()
        assert config.testing is True

    def test_dry_run_flag_from_env(self, clean_env: None) -> None:
        """Test dry_run flag from environment variable."""
        os.environ["DRY_RUN"] = "false"
        config = Config()
        config._update_from_env()
        assert config.dry_run is False

    def test_numeric_env_vars(self, clean_env: None) -> None:
        """Test numeric environment variables."""
        os.environ["MAX_ITEM_PRICE"] = "50.0"
        os.environ["MIN_PROFIT_PERCENT"] = "15.0"
        os.environ["MIN_SALES_LAST_MONTH"] = "200"
        config = Config()
        config._update_from_env()
        assert config.trading.max_item_price == 50.0
        assert config.trading.min_profit_percent == 15.0
        assert config.trading.min_sales_last_month == 200

    def test_invalid_numeric_env_vars_ignored(self, clean_env: None) -> None:
        """Test invalid numeric values are ignored."""
        original_max_price = Config().trading.max_item_price
        os.environ["MAX_ITEM_PRICE"] = "not_a_number"
        config = Config()
        config._update_from_env()
        assert config.trading.max_item_price == original_max_price

    def test_security_users_from_env(self, clean_env: None) -> None:
        """Test security users from environment variables."""
        os.environ["ALLOWED_USERS"] = "123, 456, 789"
        os.environ["ADMIN_USERS"] = "123"
        config = Config()
        config._update_from_env()
        assert config.security.allowed_users == ["123", "456", "789"]
        assert config.security.admin_users == ["123"]

    def test_waxpeer_config_from_env(self, clean_env: None) -> None:
        """Test Waxpeer configuration from environment variables."""
        os.environ["WAXPEER_ENABLED"] = "true"
        os.environ["WAXPEER_API_KEY"] = "test_api_key"
        os.environ["WAXPEER_MARKUP"] = "20.0"
        config = Config()
        config._update_from_env()
        assert config.waxpeer.enabled is True
        assert config.waxpeer.api_key == "test_api_key"
        assert config.waxpeer.markup == 20.0

    def test_monitoring_config_from_env(self, clean_env: None) -> None:
        """Test monitoring configuration from environment variables."""
        os.environ["PROMETHEUS_HOST"] = "0.0.0.0"
        os.environ["PROMETHEUS_PORT"] = "9100"
        os.environ["MONITORING_ENABLED"] = "false"
        config = Config()
        config._update_from_env()
        assert config.monitoring.prometheus_host == "0.0.0.0"
        assert config.monitoring.prometheus_port == 9100
        assert config.monitoring.enabled is False

    def test_rate_limit_config_from_env(self, clean_env: None) -> None:
        """Test rate limit configuration from environment variables."""
        os.environ["RATE_LIMIT_WARNING_THRESHOLD"] = "0.8"
        os.environ["RATE_LIMIT_NOTIFICATIONS"] = "false"
        os.environ["RATE_LIMIT_MAX_ATTEMPTS"] = "10"
        config = Config()
        config._update_from_env()
        assert config.rate_limit.warning_threshold == 0.8
        assert config.rate_limit.enable_notifications is False
        assert config.rate_limit.max_retry_attempts == 10

    def test_daily_report_config_from_env(self, clean_env: None) -> None:
        """Test daily report configuration from environment variables."""
        os.environ["DAILY_REPORT_ENABLED"] = "false"
        os.environ["DAILY_REPORT_HOUR"] = "18"
        os.environ["DAILY_REPORT_DAYS"] = "7"
        config = Config()
        config._update_from_env()
        assert config.daily_report.enabled is False
        assert config.daily_report.report_time_hour == 18
        assert config.daily_report.include_days == 7

    def test_webhook_port_from_env(self, clean_env: None) -> None:
        """Test webhook port from environment variable."""
        os.environ["WEBHOOK_PORT"] = "443"
        config = Config()
        config._update_from_env()
        assert config.bot.webhook_port == 443

    def test_invalid_webhook_port_ignored(self, clean_env: None) -> None:
        """Test invalid webhook port is ignored."""
        original_port = Config().bot.webhook_port
        os.environ["WEBHOOK_PORT"] = "not_a_number"
        config = Config()
        config._update_from_env()
        assert config.bot.webhook_port == original_port


class TestConfigValidation:
    """Tests for Config.validate() method."""

    @pytest.fixture()
    def clean_env(self) -> Generator[None, None, None]:
        """Fixture to clean environment variables."""
        original_env = os.environ.copy()
        yield
        os.environ.clear()
        os.environ.update(original_env)

    def test_validation_fails_without_bot_token(self, clean_env: None) -> None:
        """Test validation fails without bot token."""
        config = Config()
        config.bot.token = ""
        config.testing = True  # Skip DMarket validation
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "TELEGRAM_BOT_TOKEN is required" in str(exc_info.value)

    def test_validation_fails_with_invalid_token_format(self, clean_env: None) -> None:
        """Test validation fails with invalid token format."""
        config = Config()
        config.bot.token = "invalid_token"
        config.testing = True
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "appears invalid" in str(exc_info.value)

    def test_validation_passes_with_valid_token(self, clean_env: None) -> None:
        """Test validation passes with valid token."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"  # Valid format
        config.testing = True  # Skip DMarket validation
        config.validate()  # Should not raise

    def test_validation_fails_without_dmarket_keys(self, clean_env: None) -> None:
        """Test validation fails without DMarket keys in non-testing mode."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = False
        config.dmarket.public_key = ""
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "DMARKET_PUBLIC_KEY is required" in str(exc_info.value)

    def test_validation_fails_with_short_keys(self, clean_env: None) -> None:
        """Test validation fails with too short DMarket keys."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = False
        config.dmarket.public_key = "short"
        config.dmarket.secret_key = "short"
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "appears too short" in str(exc_info.value)

    def test_validation_fails_with_invalid_api_url(self, clean_env: None) -> None:
        """Test validation fails with invalid API URL."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = False
        config.dmarket.public_key = "a" * 30
        config.dmarket.secret_key = "b" * 30
        config.dmarket.api_url = "invalid_url"
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "must start with http:// or https://" in str(exc_info.value)

    def test_validation_fails_with_invalid_db_url(self, clean_env: None) -> None:
        """Test validation fails with invalid database URL."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.database.url = "invalid://db"
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "unsupported scheme" in str(exc_info.value)

    def test_validation_fails_with_invalid_log_level(self, clean_env: None) -> None:
        """Test validation fails with invalid log level."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.logging.level = "INVALID"
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "LOG_LEVEL must be one of" in str(exc_info.value)

    def test_validation_fails_with_negative_pool_size(self, clean_env: None) -> None:
        """Test validation fails with negative pool size."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.database.pool_size = -1
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "pool_size must be positive" in str(exc_info.value)

    def test_validation_fails_with_negative_max_overflow(self, clean_env: None) -> None:
        """Test validation fails with negative max_overflow."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.database.max_overflow = -1
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        assert "max_overflow must be non-negative" in str(exc_info.value)

    def test_validation_converts_user_ids(self, clean_env: None) -> None:
        """Test validation converts string user IDs to integers."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.security.allowed_users = ["123", "456"]
        config.security.admin_users = ["789"]
        config.validate()
        assert 123 in config.security.allowed_users
        assert 456 in config.security.allowed_users
        assert 789 in config.security.admin_users

    def test_validation_warns_about_dry_run_false(self, clean_env: None) -> None:
        """Test validation logs warning when dry_run is False."""
        config = Config()
        config.bot.token = "123456:ABC-DEF"
        config.testing = True
        config.dry_run = False
        # Should not raise, just warn
        config.validate()


class TestConfigUpdateFromDict:
    """Tests for Config._update_from_dict() method."""

    def test_update_bot_config(self) -> None:
        """Test updating bot configuration from dict."""
        config = Config()
        data = {
            "bot": {
                "token": "dict_token",
                "username": "dict_bot",
                "webhook": {
                    "url": "https://webhook.example.com",
                    "secret": "webhook_secret",
                },
            }
        }
        config._update_from_dict(data)
        assert config.bot.token == "dict_token"
        assert config.bot.username == "dict_bot"
        assert config.bot.webhook_url == "https://webhook.example.com"
        assert config.bot.webhook_secret == "webhook_secret"

    def test_update_dmarket_config(self) -> None:
        """Test updating DMarket configuration from dict."""
        config = Config()
        data = {
            "dmarket": {
                "api_url": "https://dict.api.com",
                "public_key": "dict_public",
                "secret_key": "dict_secret",
                "rate_limit": 60,
            }
        }
        config._update_from_dict(data)
        assert config.dmarket.api_url == "https://dict.api.com"
        assert config.dmarket.public_key == "dict_public"
        assert config.dmarket.secret_key == "dict_secret"
        assert config.dmarket.rate_limit == 60

    def test_update_database_config(self) -> None:
        """Test updating database configuration from dict."""
        config = Config()
        data = {
            "database": {
                "url": "postgresql://dict",
                "echo": True,
                "pool_size": 20,
                "max_overflow": 30,
            }
        }
        config._update_from_dict(data)
        assert config.database.url == "postgresql://dict"
        assert config.database.echo is True
        assert config.database.pool_size == 20
        assert config.database.max_overflow == 30

    def test_update_security_config(self) -> None:
        """Test updating security configuration from dict."""
        config = Config()
        data = {
            "security": {
                "allowed_users": "123, 456",
                "admin_users": "789",
            }
        }
        config._update_from_dict(data)
        assert config.security.allowed_users == ["123", "456"]
        assert config.security.admin_users == ["789"]

    def test_update_trading_config(self) -> None:
        """Test updating trading configuration from dict."""
        config = Config()
        data = {
            "trading": {
                "max_item_price": 100.0,
                "min_profit_percent": 20.0,
                "games": ["csgo", "dota2"],
                "min_sales_last_month": 500,
                "max_inventory_items": 50,
            }
        }
        config._update_from_dict(data)
        assert config.trading.max_item_price == 100.0
        assert config.trading.min_profit_percent == 20.0
        assert config.trading.games == ["csgo", "dota2"]
        assert config.trading.min_sales_last_month == 500
        assert config.trading.max_inventory_items == 50

    def test_update_filters_config(self) -> None:
        """Test updating filters configuration from dict."""
        config = Config()
        data = {
            "filters": {
                "min_liquidity": 200,
                "max_items_in_stock": 20,
            }
        }
        config._update_from_dict(data)
        assert config.filters.min_liquidity == 200
        assert config.filters.max_items_in_stock == 20

    def test_update_inventory_config(self) -> None:
        """Test updating inventory configuration from dict."""
        config = Config()
        data = {
            "inventory": {
                "auto_sell": False,
                "undercut_price": 0.1,
                "min_margin_threshold": 1.1,
            }
        }
        config._update_from_dict(data)
        assert config.inventory.auto_sell is False
        assert config.inventory.undercut_price == 0.1
        assert config.inventory.min_margin_threshold == 1.1

    def test_update_trading_safety_config(self) -> None:
        """Test updating trading safety configuration from dict."""
        config = Config()
        data = {
            "trading_safety": {
                "max_price_multiplier": 2.0,
                "price_history_days": 14,
                "min_history_samples": 5,
                "enable_price_sanity_check": False,
            }
        }
        config._update_from_dict(data)
        assert config.trading_safety.max_price_multiplier == 2.0
        assert config.trading_safety.price_history_days == 14
        assert config.trading_safety.min_history_samples == 5
        assert config.trading_safety.enable_price_sanity_check is False

    def test_update_daily_report_config(self) -> None:
        """Test updating daily report configuration from dict."""
        config = Config()
        data = {
            "daily_report": {
                "enabled": False,
                "report_time_hour": 12,
                "report_time_minute": 30,
                "include_days": 7,
            }
        }
        config._update_from_dict(data)
        assert config.daily_report.enabled is False
        assert config.daily_report.report_time_hour == 12
        assert config.daily_report.report_time_minute == 30
        assert config.daily_report.include_days == 7

    def test_update_rate_limit_config(self) -> None:
        """Test updating rate limit configuration from dict."""
        config = Config()
        data = {
            "rate_limit": {
                "warning_threshold": 0.7,
                "enable_notifications": False,
                "base_retry_delay": 2.0,
                "max_backoff_time": 120.0,
                "max_retry_attempts": 10,
                "market_limit": 5,
                "trade_limit": 2,
                "user_limit": 10,
                "balance_limit": 20,
                "other_limit": 10,
            }
        }
        config._update_from_dict(data)
        assert config.rate_limit.warning_threshold == 0.7
        assert config.rate_limit.enable_notifications is False
        assert config.rate_limit.base_retry_delay == 2.0
        assert config.rate_limit.max_backoff_time == 120.0
        assert config.rate_limit.max_retry_attempts == 10
        assert config.rate_limit.market_limit == 5

    def test_update_logging_config(self) -> None:
        """Test updating logging configuration from dict."""
        config = Config()
        data = {
            "logging": {
                "level": "DEBUG",
                "file": "/var/log/test.log",
            }
        }
        config._update_from_dict(data)
        assert config.logging.level == "DEBUG"
        assert config.logging.file == "/var/log/test.log"

    def test_partial_update(self) -> None:
        """Test partial configuration update."""
        config = Config()
        original_url = config.dmarket.api_url
        data = {
            "dmarket": {
                "public_key": "partial_key",
            }
        }
        config._update_from_dict(data)
        assert config.dmarket.public_key == "partial_key"
        assert config.dmarket.api_url == original_url  # Unchanged

    def test_empty_dict_no_changes(self) -> None:
        """Test empty dict makes no changes."""
        config = Config()
        original_token = config.bot.token
        config._update_from_dict({})
        assert config.bot.token == original_token
