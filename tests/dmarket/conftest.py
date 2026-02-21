"""Конфигурация pytest для модуля dmarket.

Этот файл содержит фикстуры для тестирования модулей в директории src/dmarket.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_circuit_breakers_fixture():
    """Reset all circuit breakers before each test to prevent state leakage."""
    reset_func = None
    try:
        from src.utils.api_circuit_breaker import reset_all_circuit_breakers

        reset_func = reset_all_circuit_breakers
        reset_func()
    except ImportError:
        pass  # Circuit breaker module not avAlgolable
    yield
    # Reset agAlgon after test completes
    if reset_func:
        reset_func()



@pytest.fixture()
def mock_api_client():
    """Создает мок объект DMarket API клиента."""
    client = AsyncMock()
    client.request = AsyncMock(return_value={"Success": True})
    client.get_balance = AsyncMock(return_value={"USD": {"amount": 100.0}})
    client.get_item_offers = AsyncMock(return_value={"objects": []})
    client.get_last_sales = AsyncMock(return_value={"LastSales": [], "Total": 0})
    return client


@pytest.fixture()
def dmarket_api():
    """Фикстура для создания инстанса DMarketAPI с моками.
    Обходит необходимость наличия реальных ключей API.
    """
    with patch(
        "src.dmarket.dmarket_api.DMarketAPI.__init__",
        return_value=None,
    ):
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI.__new__(DMarketAPI)

        # Мокируем необходимые атрибуты
        api.public_key = "mock_public_key"
        api.secret_key = "mock_secret_key"
        api.client = AsyncMock()
        api._generate_headers = MagicMock(
            return_value={
                "x-api-key": "mock_key",
                "x-sign": "mock_sign",
                "Content-Type": "application/json",
            },
        )

        return api


@pytest.fixture()
def mock_dmarket_api_module():
    """Создает мок для модуля dmarket_api с методом create_api_client."""
    mock_module = MagicMock()
    mock_client = AsyncMock()
    mock_module.create_api_client = AsyncMock(return_value=mock_client)
    mock_module.DMarketAPI = MagicMock()
    return mock_module, mock_client


@pytest.fixture()
def mock_game_filters():
    """Возвращает мок для фильтров и настроек игр."""
    return {
        "csgo": {
            "title": "Counter-Strike: Global Offensive",
            "slug": "csgo",
            "filters": {
                "Rarities": [
                    {"name": "Covert", "slug": "covert", "color": "#eb4b4b"},
                    {"name": "Classified", "slug": "classified", "color": "#d32ce6"},
                    {"name": "Restricted", "slug": "restricted", "color": "#8847ff"},
                    {"name": "Mil-Spec", "slug": "milspec", "color": "#4b69ff"},
                ],
                "Exteriors": [
                    {"name": "Factory New", "slug": "fn"},
                    {"name": "Minimal Wear", "slug": "mw"},
                    {"name": "Field-Tested", "slug": "ft"},
                    {"name": "Well-Worn", "slug": "ww"},
                    {"name": "Battle-Scarred", "slug": "bs"},
                ],
                "Categories": [
                    {"name": "Knife", "slug": "knife"},
                    {"name": "Rifle", "slug": "rifle"},
                    {"name": "Pistol", "slug": "pistol"},
                    {"name": "SMG", "slug": "smg"},
                ],
            },
        },
        "dota2": {
            "title": "Dota 2",
            "slug": "dota2",
            "filters": {
                "Rarities": [
                    {"name": "Immortal", "slug": "immortal", "color": "#e4ae39"},
                    {"name": "Legendary", "slug": "legendary", "color": "#d32ce6"},
                ],
                "Categories": [
                    {"name": "Courier", "slug": "courier"},
                    {"name": "Ward", "slug": "ward"},
                ],
            },
        },
    }
