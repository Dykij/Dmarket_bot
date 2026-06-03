"""Tests for configuration management functionality.

This module contains tests for configuration loading, validation,
and environment variable handling.
"""

import os
import tempfile

import pytest
import yaml

from src.utils.config import (
    BotConfig,
    Config,
    DatabaseConfig,
    DMarketConfig,
    SecurityConfig,
)


class TestConfig:
    """Test cases for configuration management."""

    def test_default_config_creation_sets_expected_default_values(self):
        """Тест проверяет создание конфигурации с ожидаемыми дефолтными значениями."""
        # Arrange & Act
        config = Config()

        # Assert

        assert isinstance(config.bot, BotConfig)
        assert isinstance(config.dmarket, DMarketConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.security, SecurityConfig)

        # Test default values
        assert config.bot.token == ""
        assert config.bot.username == "dmarket_bot"
        assert config.dmarket.api_url == "https://api.dmarket.com"
        assert config.dmarket.rate_limit == 30
        assert config.database.url == "sqlite:///data/dmarket_bot.db"
        assert config.debug is False
        assert config.testing is False

    def test_load_from_yaml_file_overrides_defaults_correctly(self, monkeypatch):
        """Тест проверяет корректное переопределение дефолтных значений при загрузке из YAML."""
        # Clear all relevant environment variables to ensure YAML file is used
        env_vars_to_clear = [
            "TELEGRAM_BOT_TOKEN",
            "BOT_USERNAME",
            "WEBHOOK_URL",
            "WEBHOOK_SECRET",
            "DMARKET_API_URL",
            "DMARKET_PUBLIC_KEY",
            "DMARKET_SECRET_KEY",
            "API_RATE_LIMIT",
            "DMARKET_RATE_LIMIT",
            "DATABASE_URL",
            "DATABASE_ECHO",
            "ALLOWED_USERS",
            "ADMIN_USERS",
            "LOG_LEVEL",
            "LOG_FILE",
        ]
        for var in env_vars_to_clear:
            monkeypatch.delenv(var, rAlgosing=False)

        # Arrange
        test_config = {
            "bot": {
                "token": "test_token_123",
                "username": "test_bot",
                "webhook": {
                    "url": "https://example.com/webhook",
                    "secret": "webhook_secret",
                },
            },
            "dmarket": {
                "api_url": "https://test.api.com",
                "public_key": "test_public",
                "secret_key": "test_secret",
                "rate_limit": 50,
            },
            "database": {
                "url": "postgresql://test:test@localhost/testdb",
                "echo": True,
            },
            "security": {"allowed_users": "123,456,789", "admin_users": "123"},
            "logging": {"level": "DEBUG", "file": "test.log"},
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(test_config, f)
            temp_path = f.name

        try:
            config = Config.load(temp_path)

            # Test bot configuration
            assert config.bot.token == "test_token_123"
            assert config.bot.username == "test_bot"
            assert config.bot.webhook_url == "https://example.com/webhook"
            assert config.bot.webhook_secret == "webhook_secret"

            # Test DMarket configuration
            assert config.dmarket.api_url == "https://test.api.com"
            assert config.dmarket.public_key == "test_public"
            assert config.dmarket.secret_key == "test_secret"
            assert config.dmarket.rate_limit == 50

            # Test database configuration
            assert config.database.url == "postgresql://test:test@localhost/testdb"
            assert config.database.echo is True

            # Test security configuration
            assert config.security.allowed_users == ["123", "456", "789"]
            assert config.security.admin_users == ["123"]

            # Test logging configuration
            assert config.logging.level == "DEBUG"
            assert config.logging.file == "test.log"

        finally:
            os.unlink(temp_path)

    def test_load_from_env_variables_takes_precedence_over_defaults(self):
        """Тест проверяет приоритет переменных окружения над дефолтными значениями."""
        # Arrange
        env_vars = {
            "TELEGRAM_BOT_TOKEN": "env_token_456",
            "BOT_USERNAME": "env_bot",
            "WEBHOOK_URL": "https://env.example.com/webhook",
            "WEBHOOK_SECRET": "env_webhook_secret",
            "DMARKET_API_URL": "https://env.api.com",
            "DMARKET_PUBLIC_KEY": "env_public",
            "DMARKET_SECRET_KEY": "env_secret",
            "API_RATE_LIMIT": "60",
            "DATABASE_URL": "sqlite:///env.db",
            "ALLOWED_USERS": "111,222,333",
            "ADMIN_USERS": "111,222",
            "LOG_LEVEL": "WARNING",
            "LOG_FILE": "env.log",
            "DEBUG": "true",
            "TESTING": "false",
        }

        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            config = Config.load()

            # Test that environment variables override defaults
            assert config.bot.token == "env_token_456"
            assert config.bot.username == "env_bot"
            assert config.bot.webhook_url == "https://env.example.com/webhook"
            assert config.bot.webhook_secret == "env_webhook_secret"
            assert config.dmarket.api_url == "https://env.api.com"
            assert config.dmarket.public_key == "env_public"
            assert config.dmarket.secret_key == "env_secret"
            assert config.dmarket.rate_limit == 60
            assert config.database.url == "sqlite:///env.db"
            assert config.security.allowed_users == ["111", "222", "333"]
            assert config.security.admin_users == ["111", "222"]
            assert config.logging.level == "WARNING"
            assert config.logging.file == "env.log"
            assert config.debug is True
            assert config.testing is False

        finally:
            # Clean up environment variables
            for key in env_vars:
                if key in os.environ:
                    del os.environ[key]

    def test_validate_passes_when_all_required_fields_are_set(self):
        """Тест проверяет успешную валидацию при заполнении всех обязательных полей."""
        # Arrange
        config = Config()
        config.bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        config.dmarket.public_key = "a" * 30  # Достаточно длинный ключ
        config.dmarket.secret_key = "b" * 30  # Достаточно длинный ключ

        # Act & Assert - не должно выбросить исключение
        config.validate()

    def test_validate_raises_error_when_bot_token_is_missing(self):
        """Тест проверяет выброс ошибки при отсутствии обязательного токена бота."""
        # Arrange
        config = Config()
        # bot.token остается пустым (дефолт)

        # Act & Assert
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN is required"):
            config.validate()

    def test_validate_raises_error_when_dmarket_keys_missing_in_production(self):
        """Тест проверяет выброс ошибки при отсутствии DMarket ключей в production режиме."""
        # Arrange
        config = Config()
        config.bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        config.testing = False  # Production режим
        # dmarket ключи остаются пустыми

        # Act & Assert
        with pytest.raises(ValueError, match="DMARKET_PUBLIC_KEY is required"):
            config.validate()

    def test_validate_allows_missing_dmarket_keys_in_testing_mode(self):
        """Тест проверяет, что отсутствие DMarket ключей допускается в testing режиме."""
        # Arrange
        config = Config()
        config.bot.token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        config.testing = True  # Testing режим
        # dmarket ключи остаются пустыми - допустимо в testing

        # Act & Assert - не должно выбросить исключение
        config.validate()

    def test_config_nonexistent_file(self):
        """Test loading config from nonexistent file."""
        config = Config.load("nonexistent_file.yaml")

        # Should create default config without errors
        assert isinstance(config, Config)
        assert config.bot.token == ""  # Default value

    def test_config_malformed_yaml(self):
        """Test loading config from malformed YAML file."""
        malformed_yaml = "bot:\n  token: test\n    invalid_indentation: value"

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(malformed_yaml)
            temp_path = f.name

        try:
            # Should handle the error gracefully and return default config
            config = Config.load(temp_path)
            assert isinstance(config, Config)

        finally:
            os.unlink(temp_path)

    def test_config_partial_yaml(self):
        """Test loading config from YAML with only some sections."""
        partial_config = {
            "bot": {"token": "partial_token"},
            # Missing other sections
        }

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(partial_config, f)
            temp_path = f.name

        try:
            config = Config.load(temp_path)

            # Should load specified values
            assert config.bot.token == "partial_token"

            # Should use defaults for unspecified values
            assert config.dmarket.api_url == "https://api.dmarket.com"
            assert config.database.url == "sqlite:///data/dmarket_bot.db"

        finally:
            os.unlink(temp_path)

    def test_config_invalid_rate_limit_env(self):
        """Test config with invalid rate limit in environment."""
        os.environ["API_RATE_LIMIT"] = "not_a_number"

        try:
            config = Config.load()

            # Should use default value when parsing fails
            assert config.dmarket.rate_limit == 30  # default value

        finally:
            if "API_RATE_LIMIT" in os.environ:
                del os.environ["API_RATE_LIMIT"]

    def test_config_empty_user_lists(self):
        """Test config with empty user lists."""
        config = Config()

        # Empty strings should result in empty lists
        config._update_from_dict({"security": {"allowed_users": "", "admin_users": ""}})

        assert config.security.allowed_users == []
        assert config.security.admin_users == []

    def test_config_yaml_and_env_precedence(self):
        """Test that environment variables take precedence over YAML."""
        yaml_config = {"bot": {"token": "yaml_token"}}

        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(yaml_config, f)
            temp_path = f.name

        # Set environment variable that should override YAML
        os.environ["TELEGRAM_BOT_TOKEN"] = "env_token"

        try:
            config = Config.load(temp_path)

            # Environment variable should take precedence
            assert config.bot.token == "env_token"

        finally:
            os.unlink(temp_path)
            if "TELEGRAM_BOT_TOKEN" in os.environ:
                del os.environ["TELEGRAM_BOT_TOKEN"]
