"""Тестовый DI контейнер и фикстуры.

Этот модуль предоставляет специализированные фикстуры для тестирования
с использованием Dependency Injection.

Example:
    >>> def test_with_di(test_container, mock_dmarket_api):
    ...     test_container.dmarket.api.override(mock_dmarket_api)
    ...     scanner = test_container.dmarket.arbitrage_scanner()
    ...     assert scanner.api_client is mock_dmarket_api
"""

from unittest.mock import AsyncMock

import pytest

from src.containers import init_container, reset_container


@pytest.fixture()
def di_config():
    """Конфигурация для тестового DI контейнера."""
    return {
        "dmarket": {
            "public_key": "test_public_key",
            "secret_key": "test_secret_key",
            "api_url": "https://api.dmarket.com",
        },
        "database": {
            "url": "sqlite:///:memory:",
        },
        "redis": {
            "url": None,  # Без Redis в тестах
            "default_ttl": 60,
        },
        "cache": {
            "max_size": 100,
            "default_ttl": 60,
        },
        "debug": True,
        "testing": True,
    }


@pytest.fixture()
def test_container(di_config):
    """Создать тестовый DI контейнер.

    Автоматически сбрасывается после теста.
    """
    container = init_container(di_config)
    yield container
    reset_container()


@pytest.fixture()
def mock_dmarket_api():
    """Mock DMarket API для тестов.

    Предоставляет полностью мокированный API клиент
    с предустановленными return values.

    Example:
        >>> async def test_balance(mock_dmarket_api):
        ...     balance = await mock_dmarket_api.get_balance()
        ...     assert balance["balance"] == 100.0
    """
    mock = AsyncMock()

    # Balance
    mock.get_balance.return_value = {
        "balance": 100.0,
        "usd": {"amount": 10000},
        "error": False,
    }

    # Market items
    mock.get_market_items.return_value = {
        "objects": [
            {
                "itemId": "test_item_1",
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"USD": "1250"},
                "suggestedPrice": {"USD": "1500"},
                "gameId": "csgo",
            },
        ],
        "cursor": None,
    }

    # Buy/Sell
    mock.buy_item.return_value = {"success": True, "orderId": "order_123"}
    mock.sell_item.return_value = {"success": True, "offerId": "offer_123"}

    # Targets
    mock.create_targets.return_value = {
        "success": True,
        "targets": [{"targetId": "target_1"}],
    }
    mock.get_user_targets.return_value = {
        "targets": [],
        "total": 0,
    }

    # Additional commonly used methods
    mock.get_user_inventory.return_value = {
        "objects": [],
        "total": 0,
    }

    mock.get_aggregated_prices.return_value = {
        "objects": [],
    }

    mock.get_last_sales.return_value = {
        "sales": [],
    }

    return mock


@pytest.fixture()
def container_with_mock_api(test_container, mock_dmarket_api):
    """Тестовый контейнер с мокированным API.

    Использовать когда нужен полный контейнер, но с mock API.

    Example:
        >>> def test_scanner(container_with_mock_api):
        ...     scanner = container_with_mock_api.arbitrage_scanner()
        ...     # scanner использует mock API
    """
    test_container.dmarket_api.override(mock_dmarket_api)
    yield test_container
    test_container.dmarket_api.reset_override()


@pytest.fixture()
def mock_scanner(mock_dmarket_api):
    """Mock ArbitrageScanner для тестов.

    Создает ArbitrageScanner с мокированным API клиентом.
    """
    from src.dmarket.arbitrage_scanner import ArbitrageScanner

    return ArbitrageScanner(api_client=mock_dmarket_api)


@pytest.fixture()
def mock_target_manager(mock_dmarket_api):
    """Mock TargetManager для тестов.

    Создает TargetManager с мокированным API клиентом.
    """
    from src.dmarket.targets import TargetManager

    return TargetManager(api_client=mock_dmarket_api)


@pytest.fixture()
def mock_telegram_context(mock_dmarket_api):
    """Mock Telegram контекст с зависимостями.

    Создает полноценный mock контекст для тестирования handlers.

    Example:
        >>> async def test_handler(mock_telegram_context):
        ...     api = get_dmarket_api(mock_telegram_context)
        ...     assert api is not None
    """
    from unittest.mock import MagicMock

    context = MagicMock()
    context.bot_data = {
        "dmarket_api": mock_dmarket_api,
        "config": MagicMock(),
        "database": MagicMock(),
    }
    return context


__all__ = [
    "container_with_mock_api",
    "di_config",
    "mock_dmarket_api",
    "mock_scanner",
    "mock_target_manager",
    "mock_telegram_context",
    "test_container",
]
