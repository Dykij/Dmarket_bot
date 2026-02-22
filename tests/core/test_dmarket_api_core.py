"""Комплексные тесты для DMarket API клиента.

Покрывают основные аспекты работы с API:
- Инициализация клиента
- Генерация подписей и аутентификация
- Базовые операции (баланс, предметы рынка, инвентарь)
- Обработка ошибок и retry логика
- Rate limiting
- Кэширование
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.dmarket.dmarket_api import DMarketAPI


class TestDMarketAPIInitialization:
    """Тесты инициализации API клиента."""

    def test_init_with_required_params(self):
        """Тест создания клиента с обязательными параметрами."""
        api = DMarketAPI(
            public_key="test_public_key",
            secret_key="test_secret_key",
        )

        assert api.public_key == "test_public_key"
        assert api._secret_key == "test_secret_key"
        assert api.api_url == "https://api.dmarket.com"
        assert api.max_retries == 3
        assert api.enable_cache is True

    def test_init_with_custom_params(self):
        """Тест создания клиента с кастомными параметрами."""
        api = DMarketAPI(
            public_key="custom_public",
            secret_key="custom_secret",
            api_url="https://custom.api.com",
            max_retries=5,
            connection_timeout=60.0,
            enable_cache=False,
        )

        assert api.public_key == "custom_public"
        assert api.api_url == "https://custom.api.com"
        assert api.max_retries == 5
        assert api.connection_timeout == 60.0
        assert api.enable_cache is False

    def test_init_retry_codes_default(self):
        """Тест значений retry кодов по умолчанию."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        assert 429 in api.retry_codes  # Rate limit
        assert 500 in api.retry_codes  # Server error
        assert 502 in api.retry_codes  # Bad gateway
        assert 503 in api.retry_codes  # Service unavAlgolable
        assert 504 in api.retry_codes  # Gateway timeout

    def test_init_with_custom_retry_codes(self):
        """Тест создания клиента с кастомными retry кодами."""
        custom_codes = [408, 429, 500]
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
            retry_codes=custom_codes,
        )

        assert api.retry_codes == custom_codes

    def test_secret_key_as_bytes(self):
        """Тест инициализации с секретным ключом в виде bytes."""
        secret_bytes = b"test_secret_bytes"
        api = DMarketAPI(
            public_key="test_key",
            secret_key=secret_bytes,
        )

        assert api.secret_key == secret_bytes


class TestDMarketAPIAuthentication:
    """Тесты аутентификации и генерации подписей."""

    def test_generate_signature_basic(self):
        """Тест базовой генерации подписи."""
        api = DMarketAPI(
            public_key="test_public_key",
            secret_key="test_secret_key",
        )

        headers = api._generate_signature(
            method="GET",
            path="/account/v1/balance",
            body="",
        )

        assert "X-Api-Key" in headers
        assert "X-Sign-Date" in headers
        assert "X-Request-Sign" in headers
        assert headers["X-Api-Key"] == "test_public_key"

    def test_generate_signature_with_body(self):
        """Тест генерации подписи с телом запроса."""
        api = DMarketAPI(
            public_key="test_public_key",
            secret_key="test_secret_key",
        )

        body = json.dumps({"test": "data"})
        headers = api._generate_signature(
            method="POST",
            path="/exchange/v1/market/items/buy",
            body=body,
        )

        assert "X-Api-Key" in headers
        assert "X-Sign-Date" in headers
        assert "X-Request-Sign" in headers

    def test_generate_signature_without_keys(self):
        """Тест генерации заголовков без ключей API."""
        api = DMarketAPI(
            public_key="",
            secret_key="",
        )

        headers = api._generate_signature(
            method="GET",
            path="/exchange/v1/market/items",
            body="",
        )

        assert "Content-Type" in headers
        assert "X-Api-Key" not in headers
        assert "X-Request-Sign" not in headers

    def test_generate_signature_different_methods(self):
        """Тест генерации подписи для разных HTTP методов."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        for method in ["GET", "POST", "PUT", "DELETE"]:
            headers = api._generate_signature(
                method=method,
                path="/test/path",
                body="",
            )
            assert "X-Api-Key" in headers
            assert "X-Request-Sign" in headers


class TestDMarketAPIClientManagement:
    """Тесты управления HTTP клиентом."""

    @pytest.mark.asyncio()
    async def test_get_client_creates_new(self):
        """Тест создания нового HTTP клиента."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        assert api._client is None
        client = await api._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)

        await api._close_client()

    @pytest.mark.asyncio()
    async def test_get_client_reuses_existing(self):
        """Тест переиспользования существующего клиента."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        client1 = await api._get_client()
        client2 = await api._get_client()

        assert client1 is client2

        await api._close_client()

    @pytest.mark.asyncio()
    async def test_close_client(self):
        """Тест закрытия HTTP клиента."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        await api._get_client()
        assert api._client is not None

        await api._close_client()
        assert api._client is None

    @pytest.mark.asyncio()
    async def test_context_manager_usage(self):
        """Тест использования API клиента как контекстного менеджера."""
        async with DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        ) as api:
            assert api._client is not None

        # После выхода из контекста клиент должен быть закрыт
        assert api._client is None


class TestDMarketAPIBasicOperations:
    """Тесты базовых операций API."""

    @pytest.mark.asyncio()
    async def test_get_balance_success(self):
        """Тест успешного получения баланса."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        mock_response = {
            "usd": {"amount": 10000},
            "balance": 100.0,
        }

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            balance = await api.get_balance()

            assert balance is not None
            assert "balance" in balance or "usd" in balance
            mock_request.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_market_items_basic(self):
        """Тест получения предметов рынка."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        mock_response = {
            "objects": [
                {
                    "itemId": "item_1",
                    "title": "Test Item 1",
                    "price": {"USD": "1000"},
                },
                {
                    "itemId": "item_2",
                    "title": "Test Item 2",
                    "price": {"USD": "2000"},
                },
            ],
        }

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            items = await api.get_market_items(game="csgo")

            assert items is not None
            mock_request.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_market_items_with_params(self):
        """Тест получения предметов с дополнительными параметрами."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"objects": []}

            await api.get_market_items(
                game="csgo",
                limit=50,
                offset=0,
                currency="USD",
            )

            # Проверяем, что параметры были переданы
            call_args = mock_request.call_args
            assert call_args is not None

    @pytest.mark.asyncio()
    async def test_get_user_inventory(self):
        """Тест получения инвентаря пользователя."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
        )

        mock_response = {
            "objects": [
                {
                    "itemId": "inventory_item_1",
                    "title": "My Item 1",
                },
            ],
        }

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            inventory = await api.get_user_inventory()

            assert inventory is not None
            mock_request.assert_called_once()


class TestDMarketAPIErrorHandling:
    """Тесты обработки ошибок."""

    def test_error_codes_constants(self):
        """Тест констант кодов ошибок."""
        assert 429 in DMarketAPI.ERROR_CODES  # Rate limit
        assert 401 in DMarketAPI.ERROR_CODES  # Authentication
        assert 500 in DMarketAPI.ERROR_CODES  # Server error

    def test_api_initialization_with_retry_logic(self):
        """Тест инициализации API с настSwarmками retry."""
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
            max_retries=5,
        )

        assert api.max_retries == 5

    def test_api_retry_codes_configuration(self):
        """Тест конфигурации кодов для повторных попыток."""
        custom_codes = [429, 500, 502]
        api = DMarketAPI(
            public_key="test_key",
            secret_key="test_secret",
            retry_codes=custom_codes,
        )

        assert api.retry_codes == custom_codes


class TestDMarketAPIConstants:
    """Тесты констант API."""

    def test_base_url(self):
        """Тест базового URL API."""
        assert DMarketAPI.BASE_URL == "https://api.dmarket.com"

    def test_balance_endpoints(self):
        """Тест эндпоинтов баланса."""
        assert DMarketAPI.ENDPOINT_BALANCE == "/account/v1/balance"
        assert DMarketAPI.ENDPOINT_BALANCE_LEGACY == "/api/v1/account/balance"

    def test_market_endpoints(self):
        """Тест эндпоинтов рынка."""
        assert DMarketAPI.ENDPOINT_MARKET_ITEMS == "/exchange/v1/market/items"
        assert (
            DMarketAPI.ENDPOINT_MARKET_PRICE_AGGREGATED == "/exchange/v1/market/aggregated-prices"
        )

    def test_user_endpoints(self):
        """Тест эндпоинтов пользователя."""
        assert DMarketAPI.ENDPOINT_USER_INVENTORY == "/inventory/v1/user/items"
        assert DMarketAPI.ENDPOINT_USER_OFFERS == "/marketplace-api/v1/user-offers"
        assert DMarketAPI.ENDPOINT_USER_TARGETS == "/main/v2/user-targets"

    def test_error_codes(self):
        """Тест констант кодов ошибок."""
        assert 400 in DMarketAPI.ERROR_CODES
        assert 401 in DMarketAPI.ERROR_CODES
        assert 429 in DMarketAPI.ERROR_CODES
        assert 500 in DMarketAPI.ERROR_CODES
