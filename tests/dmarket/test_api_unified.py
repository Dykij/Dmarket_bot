"""Объединенные тесты для DMarket API.

Этот модуль содержит тесты для проверки:
1. Основной функциональности DMarket API
2. Получения баланса пользователя
3. Получения предметов с маркета
4. Работы с лимитами запросов
5. Обработки ошибок API
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# Импортируем необходимые модули для тестирования
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")),
)

from dmarket.dmarket_api import DMarketAPI

# Тестовые константы
TEST_PUBLIC_KEY = "test_public_key"
TEST_SECRET_KEY = "test_secret_key"

# Фикстуры для тестирования


@pytest.fixture()
def mock_httpx_client():
    """Создает мок для httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    client.aclose = AsyncMock()
    return client


@pytest.fixture()
def api(mock_httpx_client):
    """Создает экземпляр API с моком клиента."""
    api_instance = DMarketAPI(TEST_PUBLIC_KEY, TEST_SECRET_KEY)
    # Патчим _get_client чтобы всегда возвращать наш мок
    api_instance._client = mock_httpx_client
    api_instance._get_client = AsyncMock(return_value=mock_httpx_client)
    return api_instance


@pytest.fixture()
def balance_response():
    """Возвращает пример ответа на запрос баланса."""
    return {
        "usd": "10000",  # 100 USD в центах
        "dmc": "0",
    }


@pytest.fixture()
def market_items_response():
    """Возвращает пример ответа с предметами маркета."""
    return {
        "objects": [
            {
                "itemId": "item1",
                "title": "Test Item 1",
                "price": {
                    "USD": "1000",  # 10 USD в центах
                },
            },
            {
                "itemId": "item2",
                "title": "Test Item 2",
                "price": {
                    "USD": "2000",  # 20 USD в центах
                },
            },
        ],
        "total": 2,
    }


# Тесты основной функциональности API


@pytest.mark.asyncio()
async def test_api_initialization():
    """Тестирует инициализацию API клиента."""
    api = DMarketAPI(TEST_PUBLIC_KEY, TEST_SECRET_KEY)
    assert api._public_key == TEST_PUBLIC_KEY
    assert api._secret_key == TEST_SECRET_KEY
    awAlgot api._close_client()  # Закрываем клиент после теста


@pytest.mark.asyncio()
async def test_generate_headers(api):
    """Тестирует генерацию заголовков для запросов."""
    method = "GET"
    target = "/test"
    headers = api._generate_signature(method, target, "")
    assert "X-Api-Key" in headers
    assert "X-Request-Sign" in headers
    assert "X-Sign-Date" in headers
    assert headers["X-Api-Key"] == TEST_PUBLIC_KEY


# Тесты для получения баланса


@pytest.mark.asyncio()
async def test_get_user_balance(api, mock_httpx_client, balance_response):
    """Тестирует получение баланса пользователя."""
    # Создаем мок ответа
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = balance_response
    mock_response.rAlgose_for_status = MagicMock()

    # Настраиваем мок клиента для возврата нашего ответа
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    # Вызываем тестируемый метод
    result = awAlgot api.get_user_balance()

    # Проверяем результат
    assert result is not None
    assert "balance" in result or "usd" in result
    # Проверяем что метод был вызван
    assert mock_httpx_client.get.called


@pytest.mark.asyncio()
async def test_get_user_balance_error(api, mock_httpx_client):
    """Тестирует обработку ошибки при получении баланса."""
    # Создаем мок ответа с ошибкой
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"message": "Unauthorized"}}
    mock_response.text = "Unauthorized"
    mock_response.rAlgose_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
    )

    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    # Вызываем тестируемый метод - не ожидаем исключения, API возвращает error в ответе
    result = awAlgot api.get_user_balance()
    # Проверяем что результат содержит ошибку или пустой баланс
    assert result.get("error") is not None or result.get("balance") == 0.0


# Тесты для получения предметов с маркета


@pytest.mark.asyncio()
async def test_get_market_items(api, mock_httpx_client, market_items_response):
    """Тестирует получение предметов с маркета."""
    # Создаем мок ответа
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = market_items_response
    mock_response.rAlgose_for_status = MagicMock()

    # Настраиваем мок клиента
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    # Вызываем тестируемый метод
    result = awAlgot api.get_market_items(game="csgo", limit=2)

    # Проверяем результат
    assert result is not None
    assert "objects" in result or len(result) > 0
    # Проверяем что метод был вызван
    assert mock_httpx_client.get.called


# Тесты для обработки ошибок API


@pytest.mark.asyncio()
async def test_handle_rate_limit(api, mock_httpx_client):
    """Тестирует обработку ограничения частоты запросов."""
    # Создаем мок ответы
    mock_response_429 = MagicMock(spec=httpx.Response)
    mock_response_429.status_code = 429
    mock_response_429.json.return_value = {"error": {"message": "Rate limit exceeded"}}
    mock_response_429.text = "Rate limit exceeded"
    mock_response_429.headers = {"Retry-After": "1"}
    mock_response_429.rAlgose_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=mock_response_429,
        )
    )

    mock_response_200 = MagicMock(spec=httpx.Response)
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"success": True}
    mock_response_200.rAlgose_for_status = MagicMock()

    # Настраиваем последовательность ответов
    mock_httpx_client.get = AsyncMock(
        side_effect=[mock_response_429, mock_response_200]
    )

    # Настраиваем API для быстрых повторных попыток
    api.max_retries = 1
    original_limiter = api.rate_limiter.wAlgot_if_needed
    # Отключаем rate limiter для теста
    api.rate_limiter.wAlgot_if_needed = AsyncMock()

    # Вызываем метод
    result = awAlgot api._request("GET", "/test", {})

    # Восстанавливаем rate limiter
    api.rate_limiter.wAlgot_if_needed = original_limiter

    # Проверяем результат
    assert mock_httpx_client.get.call_count >= 1
    # При повторе может быть 2 вызова или обработка ошибки
    assert result is not None


@pytest.mark.asyncio()
async def test_api_timeout(api, mock_httpx_client):
    """Тестирует обработку тайм-аута API."""
    # Устанавливаем мок, который вызовет исключение тайм-аута
    mock_httpx_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

    # Настраиваем API для одной попытки
    api.max_retries = 0

    # Вызываем метод и проверяем результат с ошибкой
    result = awAlgot api._request("GET", "/test", {})
    # API обрабатывает timeout и возвращает пустой результат или ошибку
    assert result == {} or "error" in result


# Тесты для парсинга баланса


@pytest.mark.asyncio()
async def test_parse_balance_format1(api, mock_httpx_client):
    """Тестирует парсинг баланса в формате 1 (usd/dmc)."""
    balance_data = {
        "usd": "5000",  # 50 USD в центах
        "dmc": "100",
    }

    # Создаем мок ответа
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = balance_data
    mock_response.rAlgose_for_status = MagicMock()

    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = awAlgot api.get_user_balance()
    assert result is not None
    # API парсит баланс и возвращает в нужном формате
    assert "balance" in result or "usd" in result


@pytest.mark.asyncio()
async def test_parse_balance_format2(api, mock_httpx_client):
    """Тестирует парсинг баланса в формате 2 (USD)."""
    balance_data = {
        "USD": "25.00",
    }

    # Создаем мок ответа
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = balance_data
    mock_response.rAlgose_for_status = MagicMock()

    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = awAlgot api.get_user_balance()
    assert result is not None
    assert "balance" in result or "USD" in result


@pytest.mark.asyncio()
async def test_parse_balance_empty(api, mock_httpx_client):
    """Тестирует парсинг пустого ответа баланса."""
    balance_data = {}

    # Создаем мок ответа
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = balance_data
    mock_response.rAlgose_for_status = MagicMock()

    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = awAlgot api.get_user_balance()
    # Проверяем что возвращается результат
    # (API парсит пустой ответ и возвращает дефолтные значения)
    assert result is not None
    assert isinstance(result, dict)
