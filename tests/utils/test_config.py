"""Тесты для модуля config.

Проверяет классы конфигурации и утилиты загрузки настроек.
"""

from src.utils.config import (
    BotConfig,
    DatabaseConfig,
    DMarketConfig,
    LoggingConfig,
    RateLimitConfig,
    SecurityConfig,
    TradingSafetyConfig,
)


class TestDatabaseConfig:
    """Тесты класса DatabaseConfig."""

    def test_database_config_defaults(self):
        """Тест значений по умолчанию DatabaseConfig."""
        config = DatabaseConfig()
        assert config.url == "sqlite:///data/dmarket_bot.db"
        assert config.echo is False
        assert config.pool_size == 5
        assert config.max_overflow == 10

    def test_database_config_custom_values(self):
        """Тест создания DatabaseConfig с custom значениями."""
        config = DatabaseConfig(
            url="postgresql://localhost/test", echo=True, pool_size=10, max_overflow=20
        )
        assert config.url == "postgresql://localhost/test"
        assert config.echo is True
        assert config.pool_size == 10
        assert config.max_overflow == 20

    def test_database_config_partial_override(self):
        """Тест частичного переопределения значений."""
        config = DatabaseConfig(url="mysql://localhost/db")
        assert config.url == "mysql://localhost/db"
        assert config.echo is False  # Default


class TestBotConfig:
    """Тесты класса BotConfig."""

    def test_bot_config_defaults(self):
        """Тест значений по умолчанию BotConfig."""
        config = BotConfig()
        assert config.token == ""
        assert config.username == "dmarket_bot"
        assert config.webhook_url == ""
        assert config.webhook_secret == ""

    def test_bot_config_custom_values(self):
        """Тест создания BotConfig с custom значениями."""
        config = BotConfig(
            token="test_token",
            username="test_bot",
            webhook_url="https://example.com/webhook",
            webhook_secret="secret123",
        )
        assert config.token == "test_token"
        assert config.username == "test_bot"
        assert config.webhook_url == "https://example.com/webhook"
        assert config.webhook_secret == "secret123"

    def test_bot_config_token_only(self):
        """Тест установки только токена."""
        config = BotConfig(token="my_token")
        assert config.token == "my_token"
        assert config.username == "dmarket_bot"


class TestDMarketConfig:
    """Тесты класса DMarketConfig."""

    def test_dmarket_config_defaults(self):
        """Тест значений по умолчанию DMarketConfig."""
        config = DMarketConfig()
        assert config.api_url == "https://api.dmarket.com"
        assert config.public_key == ""
        assert config.secret_key == ""
        assert config.rate_limit == 30

    def test_dmarket_config_custom_values(self):
        """Тест создания DMarketConfig с custom значениями."""
        config = DMarketConfig(
            api_url="https://test.api.com",
            public_key="pub_key",
            secret_key="sec_key",
            rate_limit=60,
        )
        assert config.api_url == "https://test.api.com"
        assert config.public_key == "pub_key"
        assert config.secret_key == "sec_key"
        assert config.rate_limit == 60

    def test_dmarket_config_keys_set(self):
        """Тест установки ключей API."""
        config = DMarketConfig(public_key="test_public", secret_key="test_secret")
        assert config.public_key == "test_public"
        assert config.secret_key == "test_secret"


class TestSecurityConfig:
    """Тесты класса SecurityConfig."""

    def test_security_config_defaults(self):
        """Тест значений по умолчанию SecurityConfig."""
        config = SecurityConfig()
        assert config.allowed_users == []
        assert config.admin_users == []

    def test_security_config_with_users(self):
        """Тест создания SecurityConfig с пользователями."""
        config = SecurityConfig(
            allowed_users=[123, 456, "user1"], admin_users=[789, "admin1"]
        )
        assert 123 in config.allowed_users
        assert 456 in config.allowed_users
        assert "user1" in config.allowed_users
        assert 789 in config.admin_users
        assert "admin1" in config.admin_users

    def test_security_config_empty_lists(self):
        """Тест что пустые списки создаются правильно."""
        config = SecurityConfig()
        assert isinstance(config.allowed_users, list)
        assert isinstance(config.admin_users, list)
        assert len(config.allowed_users) == 0
        assert len(config.admin_users) == 0


class TestLoggingConfig:
    """Тесты класса LoggingConfig."""

    def test_logging_config_defaults(self):
        """Тест значений по умолчанию LoggingConfig."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == "logs/dmarket_bot.log"
        assert "asctime" in config.format
        assert config.rotation == "1 week"
        assert config.retention == "1 month"

    def test_logging_config_custom_values(self):
        """Тест создания LoggingConfig с custom значениями."""
        config = LoggingConfig(
            level="DEBUG",
            file="custom.log",
            format="%(message)s",
            rotation="1 day",
            retention="1 week",
        )
        assert config.level == "DEBUG"
        assert config.file == "custom.log"
        assert config.format == "%(message)s"
        assert config.rotation == "1 day"
        assert config.retention == "1 week"

    def test_logging_config_level_values(self):
        """Тест различных уровней логирования."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level


class TestTradingSafetyConfig:
    """Тесты класса TradingSafetyConfig."""

    def test_trading_safety_config_defaults(self):
        """Тест значений по умолчанию TradingSafetyConfig."""
        config = TradingSafetyConfig()
        assert config.max_price_multiplier == 1.5
        assert config.price_history_days == 7
        assert config.min_history_samples == 3
        assert config.enable_price_sanity_check is True

    def test_trading_safety_config_custom_values(self):
        """Тест создания TradingSafetyConfig с custom значениями."""
        config = TradingSafetyConfig(
            max_price_multiplier=2.0,
            price_history_days=14,
            min_history_samples=5,
            enable_price_sanity_check=False,
        )
        assert config.max_price_multiplier == 2.0
        assert config.price_history_days == 14
        assert config.min_history_samples == 5
        assert config.enable_price_sanity_check is False

    def test_trading_safety_config_price_multiplier(self):
        """Тест установки price_multiplier."""
        config = TradingSafetyConfig(max_price_multiplier=3.0)
        assert config.max_price_multiplier == 3.0

    def test_trading_safety_config_disable_check(self):
        """Тест отключения price sanity check."""
        config = TradingSafetyConfig(enable_price_sanity_check=False)
        assert config.enable_price_sanity_check is False


class TestRateLimitConfig:
    """Тесты класса RateLimitConfig."""

    def test_rate_limit_config_defaults(self):
        """Тест значений по умолчанию RateLimitConfig."""
        config = RateLimitConfig()
        assert config.warning_threshold == 0.9
        assert config.enable_notifications is True
        assert config.base_retry_delay == 1.0
        assert config.max_backoff_time == 60.0
        assert config.max_retry_attempts == 5

    def test_rate_limit_config_custom_values(self):
        """Тест создания RateLimitConfig с custom значениями."""
        config = RateLimitConfig(
            warning_threshold=0.8,
            enable_notifications=False,
            base_retry_delay=2.0,
            max_backoff_time=120.0,
            max_retry_attempts=10,
        )
        assert config.warning_threshold == 0.8
        assert config.enable_notifications is False
        assert config.base_retry_delay == 2.0
        assert config.max_backoff_time == 120.0
        assert config.max_retry_attempts == 10

    def test_rate_limit_config_threshold_values(self):
        """Тест различных значений threshold."""
        for threshold in [0.5, 0.75, 0.9, 0.95]:
            config = RateLimitConfig(warning_threshold=threshold)
            assert config.warning_threshold == threshold

    def test_rate_limit_config_backoff_settings(self):
        """Тест настроек exponential backoff."""
        config = RateLimitConfig(base_retry_delay=0.5, max_backoff_time=30.0)
        assert config.base_retry_delay == 0.5
        assert config.max_backoff_time == 30.0


class TestConfigDataclasses:
    """Тесты общих свойств dataclass конфигов."""

    def test_all_configs_are_dataclasses(self):
        """Тест что все конфиги являются dataclass."""
        configs = [
            DatabaseConfig,
            BotConfig,
            DMarketConfig,
            SecurityConfig,
            LoggingConfig,
            TradingSafetyConfig,
            RateLimitConfig,
        ]
        for config_class in configs:
            assert hasattr(config_class, "__dataclass_fields__")

    def test_configs_can_be_instantiated_without_args(self):
        """Тест что все конфиги можно создать без аргументов."""
        configs = [
            DatabaseConfig(),
            BotConfig(),
            DMarketConfig(),
            SecurityConfig(),
            LoggingConfig(),
            TradingSafetyConfig(),
            RateLimitConfig(),
        ]
        for config in configs:
            assert config is not None

    def test_configs_equality(self):
        """Тест сравнения конфигов."""
        config1 = DatabaseConfig(url="test")
        config2 = DatabaseConfig(url="test")
        config3 = DatabaseConfig(url="other")
        assert config1 == config2
        assert config1 != config3

    def test_configs_repr(self):
        """Тест строкового представления конфигов."""
        config = DatabaseConfig(url="test_url")
        repr_str = repr(config)
        assert "DatabaseConfig" in repr_str
        assert "test_url" in repr_str


class TestConfigIntegration:
    """Интеграционные тесты конфигурации."""

    def test_multiple_configs_coexist(self):
        """Тест что несколько конфигов могут существовать одновременно."""
        db_config = DatabaseConfig(url="sqlite:///test.db")
        bot_config = BotConfig(token="test_token")
        dmarket_config = DMarketConfig(public_key="pub")

        assert db_config.url == "sqlite:///test.db"
        assert bot_config.token == "test_token"
        assert dmarket_config.public_key == "pub"

    def test_configs_independent(self):
        """Тест что конфиги независимы друг от друга."""
        config1 = DatabaseConfig(url="db1")
        config2 = DatabaseConfig(url="db2")

        config1.url = "modified"
        assert config2.url == "db2"


class TestConfigEdgeCases:
    """Тесты граничных случаев конфигурации."""

    def test_empty_string_values(self):
        """Тест пустых строк в конфигурации."""
        bot_config = BotConfig(token="", username="")
        assert bot_config.token == ""
        assert bot_config.username == ""

    def test_zero_values(self):
        """Тест нулевых значений."""
        dmarket_config = DMarketConfig(rate_limit=0)
        assert dmarket_config.rate_limit == 0

    def test_negative_values(self):
        """Тест отрицательных значений (должны приниматься)."""
        rate_config = RateLimitConfig(max_retry_attempts=-1)
        assert rate_config.max_retry_attempts == -1

    def test_very_large_values(self):
        """Тест очень больших значений."""
        db_config = DatabaseConfig(pool_size=10000, max_overflow=50000)
        assert db_config.pool_size == 10000
        assert db_config.max_overflow == 50000
