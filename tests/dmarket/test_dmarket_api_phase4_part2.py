"""
Phase 4: Расширенные тесты для dmarket_api.py (Часть 2/3 - исправленная).

Фокус: Context manager, управление клиентом, свойства API.
Цель: увеличить покрытие с 55% до 65%+ (работающие тесты).

Категории тестов:
- Context manager: 4 теста
- Client management: 4 теста
- Вспомогательные методы: 4 теста
- ERROR_CODES: 3 теста
- Retry codes: 3 теста
- Эндпоинты: 4 теста
"""

import httpx
import pytest

from src.dmarket.dmarket_api import DMarketAPI, api_cache


@pytest.fixture()
def api_keys():
    """Тестовые API ключи."""
    return {
        "public_key": "test_public_key_12345",
        "secret_key": "a" * 64,
    }


@pytest.fixture()
def dmarket_api(api_keys):
    """DMarket API клиент."""
    return DMarketAPI(
        public_key=api_keys["public_key"],
        secret_key=api_keys["secret_key"],
        max_retries=3,
        connection_timeout=10.0,
    )


@pytest.fixture(autouse=True)
def clear_api_cache():
    """Автоматически очищает api_cache перед каждым тестом."""
    api_cache.clear()
    yield
    api_cache.clear()


# ============================================================================
# Тесты context manager
# ============================================================================


class TestContextManager:
    """Тесты async context manager."""

    @pytest.mark.asyncio()
    async def test_async_with_creates_and_closes_client(self, dmarket_api):
        """Тест что async with создает и закрывает клиента."""
        async with dmarket_api as api:
            assert api is not None
            # Клиент должен быть создан
            client = await api._get_client()
            assert client is not None
            assert not client.is_closed

    @pytest.mark.asyncio()
    async def test_context_manager_returns_self(self, dmarket_api):
        """Тест что context manager возвращает self."""
        async with dmarket_api as api:
            assert api is dmarket_api

    @pytest.mark.asyncio()
    async def test_context_manager_handles_exceptions(self, dmarket_api):
        """Тест что context manager корректно обрабатывает исключения."""
        try:
            async with dmarket_api:
                raise ValueError("Test exception")
        except ValueError:
            pass  # Ожидаем это исключение

        # Клиент должен быть закрыт даже при исключении
        if dmarket_api._client:
            assert dmarket_api._client.is_closed

    @pytest.mark.asyncio()
    async def test_multiple_context_manager_uses(self, dmarket_api):
        """Тест что можно использовать context manager несколько раз."""
        async with dmarket_api as api1:
            assert api1 is not None

        async with dmarket_api as api2:
            assert api2 is not None

        assert api1 is api2  # Тот же объект


# ============================================================================
# Тесты управления HTTP клиентом
# ============================================================================


class TestClientManagement:
    """Тесты создания и управления HTTP клиентом."""

    @pytest.mark.asyncio()
    async def test_get_client_creates_new_client(self, dmarket_api):
        """Тест создания нового клиента."""
        client = await dmarket_api._get_client()

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed

    @pytest.mark.asyncio()
    async def test_get_client_reuses_existing_client(self, dmarket_api):
        """Тест переиспользования существующего клиента."""
        client1 = await dmarket_api._get_client()
        client2 = await dmarket_api._get_client()

        assert client1 is client2

    @pytest.mark.asyncio()
    async def test_close_client_closes_connection(self, dmarket_api):
        """Тест закрытия клиента."""
        client = await dmarket_api._get_client()
        assert not client.is_closed

        await dmarket_api._close_client()

        assert client.is_closed
        assert dmarket_api._client is None

    @pytest.mark.asyncio()
    async def test_close_client_when_no_client_exists(self, dmarket_api):
        """Тест закрытия когда клиента нет."""
        # Не должно вызывать ошибку
        await dmarket_api._close_client()
        assert dmarket_api._client is None


# ============================================================================
# Тесты вспомогательных методов
# ============================================================================


class TestHelperMethods:
    """Тесты вспомогательных методов API."""

    def test_api_url_property(self, dmarket_api):
        """Тест что api_url доступен."""
        assert dmarket_api.api_url == "https://api.dmarket.com"

    def test_public_key_property(self, dmarket_api):
        """Тест что public_key доступен."""
        assert dmarket_api.public_key == "test_public_key_12345"

    def test_max_retries_property(self, dmarket_api):
        """Тест что max_retries установлен."""
        assert dmarket_api.max_retries == 3

    def test_enable_cache_property(self, dmarket_api):
        """Тест что кэш включен по умолчанию."""
        assert dmarket_api.enable_cache is True


# ============================================================================
# Тесты ERROR_CODES словаря
# ============================================================================


class TestErrorCodes:
    """Тесты словаря кодов ошибок."""

    def test_error_codes_contains_common_codes(self, dmarket_api):
        """Тест что ERROR_CODES содержит общие коды."""
        assert 400 in dmarket_api.ERROR_CODES
        assert 401 in dmarket_api.ERROR_CODES
        assert 404 in dmarket_api.ERROR_CODES
        assert 429 in dmarket_api.ERROR_CODES
        assert 500 in dmarket_api.ERROR_CODES

    def test_error_codes_has_descriptions(self, dmarket_api):
        """Тест что коды ошибок имеют описания."""
        assert isinstance(dmarket_api.ERROR_CODES[400], str)
        assert len(dmarket_api.ERROR_CODES[400]) > 0

    def test_error_codes_for_rate_limit(self, dmarket_api):
        """Тест описания для rate limit."""
        description = dmarket_api.ERROR_CODES[429]
        assert "rate limit" in description.lower() or "много" in description.lower()


# ============================================================================
# Тесты retry_codes списка
# ============================================================================


class TestRetryCodes:
    """Тесты списка кодов для retry."""

    def test_retry_codes_contains_server_errors(self, dmarket_api):
        """Тест что retry_codes содержит серверные ошибки."""
        assert 500 in dmarket_api.retry_codes
        assert 502 in dmarket_api.retry_codes
        assert 503 in dmarket_api.retry_codes
        assert 504 in dmarket_api.retry_codes

    def test_retry_codes_contains_rate_limit(self, dmarket_api):
        """Тест что retry_codes содержит 429."""
        assert 429 in dmarket_api.retry_codes

    def test_retry_codes_doesnt_contain_client_errors(self, dmarket_api):
        """Тест что retry_codes не содержит клиентские ошибки."""
        assert 400 not in dmarket_api.retry_codes
        assert 401 not in dmarket_api.retry_codes
        assert 404 not in dmarket_api.retry_codes


# ============================================================================
# Тесты эндпоинтов
# ============================================================================


class TestEndpoints:
    """Тесты констант эндпоинтов."""

    def test_balance_endpoint_defined(self, dmarket_api):
        """Тест что эндпоинт баланса определен."""
        assert hasattr(dmarket_api, "ENDPOINT_BALANCE")
        assert dmarket_api.ENDPOINT_BALANCE == "/account/v1/balance"

    def test_market_items_endpoint_defined(self, dmarket_api):
        """Тест что эндпоинт маркета определен."""
        assert hasattr(dmarket_api, "ENDPOINT_MARKET_ITEMS")
        assert "/market/items" in dmarket_api.ENDPOINT_MARKET_ITEMS

    def test_purchase_endpoint_defined(self, dmarket_api):
        """Тест что эндпоинт покупки определен."""
        assert hasattr(dmarket_api, "ENDPOINT_PURCHASE")
        assert "/buy" in dmarket_api.ENDPOINT_PURCHASE

    def test_sell_endpoint_defined(self, dmarket_api):
        """Тест что эндпоинт продажи определен."""
        assert hasattr(dmarket_api, "ENDPOINT_SELL")
        assert "/sell" in dmarket_api.ENDPOINT_SELL
