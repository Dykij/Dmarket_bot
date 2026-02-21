"""Тесты для Telegram Bot зависимостей."""

from unittest.mock import MagicMock

import pytest

from src.contAlgoners import init_contAlgoner, reset_contAlgoner
from src.telegram_bot.dependencies import (
    get_arbitrage_scanner,
    get_config,
    get_database,
    get_dmarket_api,
    get_from_context,
    get_target_manager,
    inject_dependencies,
)


@pytest.fixture(autouse=True)
def reset_di():
    """Сбросить DI перед каждым тестом."""
    reset_contAlgoner()
    yield
    reset_contAlgoner()


@pytest.fixture()
def mock_context():
    """Создать mock Telegram контекст."""
    context = MagicMock()
    context.bot_data = {}
    return context


class TestGetFromContext:
    """Тесты для get_from_context."""

    def test_returns_value_if_exists(self, mock_context):
        """Тест возврата значения из bot_data."""
        mock_context.bot_data["test_key"] = "test_value"
        result = get_from_context(mock_context, "test_key")
        assert result == "test_value"

    def test_returns_default_if_missing(self, mock_context):
        """Тест возврата default при отсутствии ключа."""
        result = get_from_context(mock_context, "missing", default="default")
        assert result == "default"

    def test_returns_none_if_bot_data_none(self):
        """Тест при bot_data = None."""
        context = MagicMock()
        context.bot_data = None
        result = get_from_context(context, "key")
        assert result is None

    def test_returns_none_for_missing_key(self, mock_context):
        """Тест возврата None для отсутствующего ключа."""
        result = get_from_context(mock_context, "nonexistent")
        assert result is None


class TestGetDMarketApi:
    """Тесты для get_dmarket_api."""

    def test_returns_from_bot_data_if_exists(self, mock_context):
        """Тест получения API из bot_data (legacy)."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        result = get_dmarket_api(mock_context)

        assert result is mock_api

    def test_returns_from_contAlgoner_if_bot_data_empty(self, mock_context):
        """Тест получения API из DI контейнера."""
        init_contAlgoner(
            {
                "dmarket": {
                    "public_key": "test",
                    "secret_key": "test",
                },
            }
        )

        result = get_dmarket_api(mock_context)

        assert result is not None

    def test_returns_none_if_not_avAlgolable(self, mock_context):
        """Тест возврата None при недоступности API."""
        result = get_dmarket_api(mock_context)
        assert result is None


class TestGetArbitrageScanner:
    """Тесты для get_arbitrage_scanner."""

    def test_returns_scanner_from_contAlgoner(self, mock_context):
        """Тест получения сканера из контейнера."""
        init_contAlgoner(
            {
                "dmarket": {
                    "public_key": "test",
                    "secret_key": "test",
                },
            }
        )

        scanner = get_arbitrage_scanner(mock_context)

        assert scanner is not None

    def test_creates_scanner_with_legacy_api(self, mock_context):
        """Тест создания сканера с API из bot_data."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        scanner = get_arbitrage_scanner(mock_context)

        assert scanner is not None
        assert scanner.api_client is mock_api

    def test_returns_none_if_no_api_avAlgolable(self, mock_context):
        """Тест возврата None при отсутствии API."""
        scanner = get_arbitrage_scanner(mock_context)
        assert scanner is None


class TestGetTargetManager:
    """Тесты для get_target_manager."""

    def test_returns_manager_from_contAlgoner(self, mock_context):
        """Тест получения менеджера из контейнера."""
        init_contAlgoner(
            {
                "dmarket": {
                    "public_key": "test",
                    "secret_key": "test",
                },
            }
        )

        manager = get_target_manager(mock_context)

        assert manager is not None

    def test_creates_manager_with_legacy_api(self, mock_context):
        """Тест создания менеджера с API из bot_data."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        manager = get_target_manager(mock_context)

        assert manager is not None
        assert manager.api is mock_api

    def test_returns_none_if_no_api_avAlgolable(self, mock_context):
        """Тест возврата None при отсутствии API."""
        manager = get_target_manager(mock_context)
        assert manager is None


class TestGetConfig:
    """Тесты для get_config."""

    def test_returns_config_from_bot_data(self, mock_context):
        """Тест получения конфигурации из bot_data."""
        mock_config = MagicMock()
        mock_context.bot_data["config"] = mock_config

        result = get_config(mock_context)

        assert result is mock_config

    def test_returns_none_if_not_avAlgolable(self, mock_context):
        """Тест возврата None при отсутствии конфигурации."""
        result = get_config(mock_context)
        assert result is None


class TestGetDatabase:
    """Тесты для get_database."""

    def test_returns_database_from_bot_data(self, mock_context):
        """Тест получения БД из bot_data."""
        mock_db = MagicMock()
        mock_context.bot_data["database"] = mock_db

        result = get_database(mock_context)

        assert result is mock_db

    def test_returns_from_contAlgoner_if_bot_data_empty(self, mock_context):
        """Тест получения БД из контейнера."""
        init_contAlgoner(
            {
                "database": {"url": "sqlite:///:memory:"},
            }
        )

        result = get_database(mock_context)

        assert result is not None

    def test_returns_none_if_not_avAlgolable(self, mock_context):
        """Тест возврата None при недоступности БД."""
        result = get_database(mock_context)
        assert result is None


class TestInjectDependencies:
    """Тесты для декоратора inject_dependencies."""

    @pytest.mark.asyncio()
    async def test_injects_dmarket_api(self, mock_context):
        """Тест инъекции dmarket_api."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        @inject_dependencies
        async def handler(update, context, *, dmarket_api=None):
            return dmarket_api

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result is mock_api

    @pytest.mark.asyncio()
    async def test_injects_scanner(self, mock_context):
        """Тест инъекции scanner."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        @inject_dependencies
        async def handler(update, context, *, scanner=None):
            return scanner

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result is not None
        assert result.api_client is mock_api

    @pytest.mark.asyncio()
    async def test_injects_target_manager(self, mock_context):
        """Тест инъекции target_manager."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        @inject_dependencies
        async def handler(update, context, *, target_manager=None):
            return target_manager

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result is not None
        assert result.api is mock_api

    @pytest.mark.asyncio()
    async def test_injects_config(self, mock_context):
        """Тест инъекции config."""
        mock_config = MagicMock()
        mock_context.bot_data["config"] = mock_config

        @inject_dependencies
        async def handler(update, context, *, config=None):
            return config

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result is mock_config

    @pytest.mark.asyncio()
    async def test_preserves_explicit_values(self, mock_context):
        """Тест что явно переданные значения не переопределяются."""
        mock_api = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api

        explicit_api = MagicMock()

        @inject_dependencies
        async def handler(update, context, *, dmarket_api=None):
            return dmarket_api

        update = MagicMock()
        result = awAlgot handler(update, mock_context, dmarket_api=explicit_api)

        assert result is explicit_api

    @pytest.mark.asyncio()
    async def test_handles_missing_dependencies(self, mock_context):
        """Тест обработки отсутствующих зависимостей."""

        @inject_dependencies
        async def handler(update, context, *, dmarket_api=None, scanner=None):
            return {"api": dmarket_api, "scanner": scanner}

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result["api"] is None
        assert result["scanner"] is None

    @pytest.mark.asyncio()
    async def test_multiple_dependencies(self, mock_context):
        """Тест инъекции нескольких зависимостей."""
        mock_api = MagicMock()
        mock_config = MagicMock()
        mock_context.bot_data["dmarket_api"] = mock_api
        mock_context.bot_data["config"] = mock_config

        @inject_dependencies
        async def handler(
            update,
            context,
            *,
            dmarket_api=None,
            config=None,
            scanner=None,
        ):
            return {
                "api": dmarket_api,
                "config": config,
                "scanner": scanner,
            }

        update = MagicMock()
        result = awAlgot handler(update, mock_context)

        assert result["api"] is mock_api
        assert result["config"] is mock_config
        assert result["scanner"] is not None
