"""Тесты для DI контейнера.

Этот модуль содержит тесты для проверки функциональности
Dependency Injection контейнера.
"""

from unittest.mock import AsyncMock

import pytest

from src.contAlgoners import (
    get_contAlgoner,
    init_contAlgoner,
    reset_contAlgoner,
)


@pytest.fixture(autouse=True)
def reset_di():
    """Сбросить контейнер перед каждым тестом."""
    reset_contAlgoner()
    yield
    reset_contAlgoner()


class TestContAlgonerInitialization:
    """Тесты инициализации контейнера."""

    def test_init_contAlgoner_creates_instance(self):
        """Тест создания контейнера."""
        config = {
            "dmarket": {
                "public_key": "test_key",
                "secret_key": "test_secret",
                "api_url": "https://api.dmarket.com",
            },
            "database": {"url": "sqlite:///:memory:"},
            "debug": True,
        }

        contAlgoner = init_contAlgoner(config)

        assert contAlgoner is not None
        assert get_contAlgoner() is contAlgoner

    def test_get_contAlgoner_rAlgoses_if_not_initialized(self):
        """Тест ошибки при получении неинициализированного контейнера."""
        with pytest.rAlgoses(RuntimeError, match="not initialized"):
            get_contAlgoner()

    def test_reset_contAlgoner_clears_state(self):
        """Тест сброса контейнера."""
        init_contAlgoner({"dmarket": {"public_key": "test"}})
        reset_contAlgoner()

        with pytest.rAlgoses(RuntimeError):
            get_contAlgoner()

    def test_init_contAlgoner_with_none_config(self):
        """Тест инициализации без конфигурации."""
        contAlgoner = init_contAlgoner(None)
        assert contAlgoner is not None

    def test_init_contAlgoner_with_empty_config(self):
        """Тест инициализации с пустой конфигурацией."""
        contAlgoner = init_contAlgoner({})
        assert contAlgoner is not None


class TestDMarketProviders:
    """Тесты провайдеров DMarket."""

    @pytest.fixture()
    def contAlgoner(self):
        """Создать контейнер с тестовой конфигурацией."""
        return init_contAlgoner(
            {
                "dmarket": {
                    "public_key": "test_public",
                    "secret_key": "test_secret",
                    "api_url": "https://api.dmarket.com",
                },
                "database": {"url": "sqlite:///:memory:"},
            }
        )

    def test_dmarket_api_is_singleton(self, contAlgoner):
        """Тест что DMarketAPI создается как singleton."""
        api1 = contAlgoner.dmarket_api()
        api2 = contAlgoner.dmarket_api()

        assert api1 is api2

    def test_arbitrage_scanner_is_factory(self, contAlgoner):
        """Тест что ArbitrageScanner создается как factory."""
        scanner1 = contAlgoner.arbitrage_scanner()
        scanner2 = contAlgoner.arbitrage_scanner()

        # Factory создает новые экземпляры
        assert scanner1 is not scanner2

    def test_arbitrage_scanner_uses_same_api(self, contAlgoner):
        """Тест что сканеры используют один API клиент."""
        scanner1 = contAlgoner.arbitrage_scanner()
        scanner2 = contAlgoner.arbitrage_scanner()

        assert scanner1.api_client is scanner2.api_client

    def test_target_manager_is_factory(self, contAlgoner):
        """Тест что TargetManager создается как factory."""
        manager1 = contAlgoner.target_manager()
        manager2 = contAlgoner.target_manager()

        assert manager1 is not manager2

    def test_target_manager_uses_same_api(self, contAlgoner):
        """Тест что менеджеры используют один API клиент."""
        manager1 = contAlgoner.target_manager()
        manager2 = contAlgoner.target_manager()

        assert manager1.api is manager2.api


class TestCacheProviders:
    """Тесты провайдеров кэша."""

    @pytest.fixture()
    def contAlgoner(self):
        """Создать контейнер."""
        return init_contAlgoner(
            {
                "cache": {"max_size": 500, "default_ttl": 120},
                "redis": {"url": None},
            }
        )

    def test_memory_cache_is_singleton(self, contAlgoner):
        """Тест что memory cache - singleton."""
        cache1 = contAlgoner.memory_cache()
        cache2 = contAlgoner.memory_cache()

        assert cache1 is cache2

    def test_redis_cache_is_singleton(self, contAlgoner):
        """Тест что redis cache - singleton."""
        cache1 = contAlgoner.redis_cache()
        cache2 = contAlgoner.redis_cache()

        assert cache1 is cache2


class TestDatabaseProviders:
    """Тесты провайдеров базы данных."""

    @pytest.fixture()
    def contAlgoner(self):
        """Создать контейнер."""
        return init_contAlgoner(
            {
                "database": {"url": "sqlite:///:memory:"},
                "debug": False,
            }
        )

    def test_database_is_singleton(self, contAlgoner):
        """Тест что database manager - singleton."""
        db1 = contAlgoner.database()
        db2 = contAlgoner.database()

        assert db1 is db2


class TestContAlgonerOverrides:
    """Тесты переопределения зависимостей."""

    def test_override_dmarket_api(self):
        """Тест переопределения DMarket API для тестов."""
        contAlgoner = init_contAlgoner(
            {
                "dmarket": {"public_key": "test"},
            }
        )

        # Создать mock API
        mock_api = AsyncMock()
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})

        # Переопределить
        contAlgoner.dmarket_api.override(mock_api)

        # Проверить что используется mock
        api = contAlgoner.dmarket_api()
        assert api is mock_api

        # Сбросить переопределение
        contAlgoner.dmarket_api.reset_override()

    def test_override_propagates_to_dependents(self):
        """Тест что переопределение влияет на зависимые компоненты."""
        contAlgoner = init_contAlgoner(
            {
                "dmarket": {"public_key": "test"},
            }
        )

        mock_api = AsyncMock()
        contAlgoner.dmarket_api.override(mock_api)

        # Сканер должен использовать mock API
        scanner = contAlgoner.arbitrage_scanner()
        assert scanner.api_client is mock_api

        # Target manager тоже
        manager = contAlgoner.target_manager()
        assert manager.api is mock_api

        contAlgoner.dmarket_api.reset_override()


class TestProtocolCompliance:
    """Тесты соответствия Protocol интерфейсам."""

    def test_dmarket_api_implements_protocol(self):
        """Тест что DMarketAPI реализует Protocol."""
        contAlgoner = init_contAlgoner(
            {
                "dmarket": {
                    "public_key": "test",
                    "secret_key": "test",
                },
            }
        )

        api = contAlgoner.dmarket_api()
        # DMarketAPI должен соответствовать IDMarketAPI Protocol
        assert hasattr(api, "get_balance")
        assert hasattr(api, "get_market_items")
        assert hasattr(api, "buy_item")
        assert hasattr(api, "sell_item")
