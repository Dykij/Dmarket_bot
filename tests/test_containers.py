"""Тесты для DI контейнера.

Этот модуль содержит тесты для проверки функциональности
Dependency Injection контейнера.
"""

from unittest.mock import AsyncMock

import pytest

from src.containers import (
    get_container,
    init_container,
    reset_container,
)


@pytest.fixture(autouse=True)
def reset_di():
    """Сбросить контейнер перед каждым тестом."""
    reset_container()
    yield
    reset_container()


class TestContAlgonerInitialization:
    """Тесты инициализации контейнера."""

    def test_init_container_creates_instance(self):
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

        container = init_container(config)

        assert container is not None
        assert get_container() is container

    def test_get_container_raises_if_not_initialized(self):
        """Тест ошибки при получении неинициализированного контейнера."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_container()

    def test_reset_container_clears_state(self):
        """Тест сброса контейнера."""
        init_container({"dmarket": {"public_key": "test"}})
        reset_container()

        with pytest.raises(RuntimeError):
            get_container()

    def test_init_container_with_none_config(self):
        """Тест инициализации без конфигурации."""
        container = init_container(None)
        assert container is not None

    def test_init_container_with_empty_config(self):
        """Тест инициализации с пустой конфигурацией."""
        container = init_container({})
        assert container is not None


class TestDMarketProviders:
    """Тесты провайдеров DMarket."""

    @pytest.fixture()
    def container(self):
        """Создать контейнер с тестовой конфигурацией."""
        return init_container(
            {
                "dmarket": {
                    "public_key": "test_public",
                    "secret_key": "test_secret",
                    "api_url": "https://api.dmarket.com",
                },
                "database": {"url": "sqlite:///:memory:"},
            }
        )

    def test_dmarket_api_is_singleton(self, container):
        """Тест что DMarketAPI создается как singleton."""
        api1 = container.dmarket_api()
        api2 = container.dmarket_api()

        assert api1 is api2

    def test_arbitrage_scanner_is_factory(self, container):
        """Тест что ArbitrageScanner создается как factory."""
        scanner1 = container.arbitrage_scanner()
        scanner2 = container.arbitrage_scanner()

        # Factory создает новые экземпляры
        assert scanner1 is not scanner2

    def test_arbitrage_scanner_uses_same_api(self, container):
        """Тест что сканеры используют один API клиент."""
        scanner1 = container.arbitrage_scanner()
        scanner2 = container.arbitrage_scanner()

        assert scanner1.api_client is scanner2.api_client

    def test_target_manager_is_factory(self, container):
        """Тест что TargetManager создается как factory."""
        manager1 = container.target_manager()
        manager2 = container.target_manager()

        assert manager1 is not manager2

    def test_target_manager_uses_same_api(self, container):
        """Тест что менеджеры используют один API клиент."""
        manager1 = container.target_manager()
        manager2 = container.target_manager()

        assert manager1.api is manager2.api


class TestCacheProviders:
    """Тесты провайдеров кэша."""

    @pytest.fixture()
    def container(self):
        """Создать контейнер."""
        return init_container(
            {
                "cache": {"max_size": 500, "default_ttl": 120},
                "redis": {"url": None},
            }
        )

    def test_memory_cache_is_singleton(self, container):
        """Тест что memory cache - singleton."""
        cache1 = container.memory_cache()
        cache2 = container.memory_cache()

        assert cache1 is cache2

    def test_redis_cache_is_singleton(self, container):
        """Тест что redis cache - singleton."""
        cache1 = container.redis_cache()
        cache2 = container.redis_cache()

        assert cache1 is cache2


class TestDatabaseProviders:
    """Тесты провайдеров базы данных."""

    @pytest.fixture()
    def container(self):
        """Создать контейнер."""
        return init_container(
            {
                "database": {"url": "sqlite:///:memory:"},
                "debug": False,
            }
        )

    def test_database_is_singleton(self, container):
        """Тест что database manager - singleton."""
        db1 = container.database()
        db2 = container.database()

        assert db1 is db2


class TestContAlgonerOverrides:
    """Тесты переопределения зависимостей."""

    def test_override_dmarket_api(self):
        """Тест переопределения DMarket API для тестов."""
        container = init_container(
            {
                "dmarket": {"public_key": "test"},
            }
        )

        # Создать mock API
        mock_api = AsyncMock()
        mock_api.get_balance = AsyncMock(return_value={"balance": 100.0})

        # Переопределить
        container.dmarket_api.override(mock_api)

        # Проверить что используется mock
        api = container.dmarket_api()
        assert api is mock_api

        # Сбросить переопределение
        container.dmarket_api.reset_override()

    def test_override_propagates_to_dependents(self):
        """Тест что переопределение влияет на зависимые компоненты."""
        container = init_container(
            {
                "dmarket": {"public_key": "test"},
            }
        )

        mock_api = AsyncMock()
        container.dmarket_api.override(mock_api)

        # Сканер должен использовать mock API
        scanner = container.arbitrage_scanner()
        assert scanner.api_client is mock_api

        # Target manager тоже
        manager = container.target_manager()
        assert manager.api is mock_api

        container.dmarket_api.reset_override()


class TestProtocolCompliance:
    """Тесты соответствия Protocol интерфейсам."""

    def test_dmarket_api_implements_protocol(self):
        """Тест что DMarketAPI реализует Protocol."""
        container = init_container(
            {
                "dmarket": {
                    "public_key": "test",
                    "secret_key": "test",
                },
            }
        )

        api = container.dmarket_api()
        # DMarketAPI должен соответствовать IDMarketAPI Protocol
        assert hasattr(api, "get_balance")
        assert hasattr(api, "get_market_items")
        assert hasattr(api, "buy_item")
        assert hasattr(api, "sell_item")
