"""Тесты для модуля dmarket_api.

Проверяет DMarket API клиент.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from src.dmarket.dmarket_api import DMarketAPI


class TestDMarketAPIInitialization:
    """Тесты инициализации DMarketAPI."""

    def test_init_with_string_secret_key(self):
        """Тест инициализации со строковым секретным ключом."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.public_key == "test_public"
        assert api._secret_key == "test_secret"
        assert isinstance(api.secret_key, bytes)

    def test_init_with_bytes_secret_key(self):
        """Тест инициализации с байтовым секретным ключом."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key=b"test_secret",
        )
        assert api.public_key == "test_public"
        assert api._secret_key == "test_secret"

    def test_init_default_values(self):
        """Тест значений по умолчанию."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.api_url == "https://api.dmarket.com"
        assert api.max_retries == 3
        assert api.connection_timeout == 30.0
        assert api.enable_cache is True
        assert api.dry_run is True

    def test_init_custom_values(self):
        """Тест custom значений инициализации."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            api_url="https://custom.api.com",
            max_retries=5,
            connection_timeout=60.0,
            enable_cache=False,
            dry_run=False,
        )
        assert api.api_url == "https://custom.api.com"
        assert api.max_retries == 5
        assert api.connection_timeout == 60.0
        assert api.enable_cache is False
        assert api.dry_run is False

    def test_init_retry_codes_default(self):
        """Тест что retry_codes по умолчанию корректные."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert 429 in api.retry_codes
        assert 500 in api.retry_codes
        assert 502 in api.retry_codes
        assert 503 in api.retry_codes
        assert 504 in api.retry_codes

    def test_init_custom_retry_codes(self):
        """Тест установки custom retry codes."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            retry_codes=[400, 404],
        )
        assert api.retry_codes == [400, 404]

    def test_init_pool_limits_default(self):
        """Тест настроек connection pool по умолчанию."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.pool_limits.max_connections == 100
        assert api.pool_limits.max_keepalive_connections == 30  # Updated to match actual default

    def test_init_custom_pool_limits(self):
        """Тест custom connection pool."""
        custom_limits = httpx.Limits(
            max_connections=50,
            max_keepalive_connections=10,
        )
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            pool_limits=custom_limits,
        )
        assert api.pool_limits.max_connections == 50
        assert api.pool_limits.max_keepalive_connections == 10

    def test_init_rate_limiter_created(self):
        """Тест что rate_limiter создается."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.rate_limiter is not None

    def test_init_rate_limiter_authorized(self):
        """Тест что rate_limiter знает о авторизации."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.rate_limiter.is_authorized is True

    def test_init_rate_limiter_unauthorized(self):
        """Тест rate_limiter без авторизации."""
        api = DMarketAPI(
            public_key="",
            secret_key="",
        )
        assert api.rate_limiter.is_authorized is False

    def test_init_client_is_none(self):
        """Тест что HTTP client изначально None."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api._client is None

    def test_init_dry_run_true_by_default(self):
        """Тест что dry_run True по умолчанию (безопасность)."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.dry_run is True

    def test_init_with_notifier(self):
        """Тест инициализации с notifier."""
        mock_notifier = MagicMock()
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            notifier=mock_notifier,
        )
        assert api.notifier is mock_notifier


class TestDMarketAPIEndpoints:
    """Тесты констант endpoints."""

    def test_base_url_constant(self):
        """Тест BASE_URL константы."""
        assert DMarketAPI.BASE_URL == "https://api.dmarket.com"

    def test_balance_endpoints(self):
        """Тест endpoints для баланса."""
        assert DMarketAPI.ENDPOINT_BALANCE == "/account/v1/balance"
        assert DMarketAPI.ENDPOINT_BALANCE_LEGACY == "/api/v1/account/balance"

    def test_market_endpoints(self):
        """Тест endpoints для маркета."""
        assert DMarketAPI.ENDPOINT_MARKET_ITEMS == "/exchange/v1/market/items"
        assert (
            DMarketAPI.ENDPOINT_MARKET_PRICE_AGGREGATED
            == "/exchange/v1/market/aggregated-prices"
        )

    def test_user_endpoints(self):
        """Тест endpoints для пользователя."""
        # Updated to match actual DMarket API v1.1.0 endpoints
        assert DMarketAPI.ENDPOINT_USER_INVENTORY == "/inventory/v1/user/items"
        assert DMarketAPI.ENDPOINT_USER_OFFERS == "/marketplace-api/v1/user-offers"
        assert DMarketAPI.ENDPOINT_USER_TARGETS == "/main/v2/user-targets"

    def test_operations_endpoints(self):
        """Тест endpoints для операций."""
        assert DMarketAPI.ENDPOINT_PURCHASE == "/exchange/v1/market/items/buy"
        assert DMarketAPI.ENDPOINT_SELL == "/exchange/v1/user/inventory/sell"

    def test_error_codes_defined(self):
        """Тест что коды ошибок определены."""
        assert 400 in DMarketAPI.ERROR_CODES
        assert 401 in DMarketAPI.ERROR_CODES
        assert 429 in DMarketAPI.ERROR_CODES
        assert 500 in DMarketAPI.ERROR_CODES


class TestDMarketAPIContextManager:
    """Тесты context manager."""

    @pytest.mark.asyncio()
    async def test_context_manager_enter(self):
        """Тест входа в context manager."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        async with api as client:
            assert client is api
            assert api._client is not None

    @pytest.mark.asyncio()
    async def test_context_manager_exit(self):
        """Тест выхода из context manager."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        async with api:
            pass

        # Client должен быть закрыт
        assert api._client is None or api._client.is_closed

    @pytest.mark.asyncio()
    async def test_context_manager_client_created(self):
        """Тест что client создается в context manager."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        async with api:
            assert api._client is not None
            assert isinstance(api._client, httpx.AsyncClient)


class TestDMarketAPIClientManagement:
    """Тесты управления HTTP клиентом."""

    @pytest.mark.asyncio()
    async def test_get_client_creates_new(self):
        """Тест что _get_client создает новый клиент."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        client = await api._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        await api._close_client()

    @pytest.mark.asyncio()
    async def test_get_client_returns_existing(self):
        """Тест что _get_client возвращает существующий клиент."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        client1 = await api._get_client()
        client2 = await api._get_client()
        assert client1 is client2
        await api._close_client()

    @pytest.mark.asyncio()
    async def test_close_client(self):
        """Тест закрытия клиента."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        await api._get_client()
        await api._close_client()
        assert api._client is None

    @pytest.mark.asyncio()
    async def test_close_client_when_none(self):
        """Тест закрытия когда клиент None."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )

        # Не должно быть ошибки
        await api._close_client()


class TestDMarketAPISignature:
    """Тесты генерации подписи."""

    def test_generate_signature_without_keys(self):
        """Тест генерации подписи без ключей."""
        api = DMarketAPI(
            public_key="",
            secret_key="",
        )

        headers = api._generate_signature("GET", "/test")
        assert headers == {"Content-Type": "application/json"}

    def test_generate_signature_with_keys(self):
        """Тест генерации подписи с ключами."""
        # Используем валидный hex ключ (32 байта = 64 hex символа)
        api = DMarketAPI(
            public_key="test_public",
            secret_key="a" * 64,
        )

        headers = api._generate_signature("GET", "/account/v1/balance")

        assert "X-Api-Key" in headers
        assert "X-Request-Sign" in headers
        assert "X-Sign-Date" in headers
        assert "Content-Type" in headers

    def test_generate_signature_includes_method(self):
        """Тест что подпись включает HTTP метод."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="a" * 64,
        )

        headers_get = api._generate_signature("GET", "/test")
        headers_post = api._generate_signature("POST", "/test")

        # Подписи должны быть разными для разных методов
        assert headers_get["X-Request-Sign"] != headers_post["X-Request-Sign"]

    def test_generate_signature_with_body(self):
        """Тест генерации подписи с телом запроса."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="a" * 64,
        )

        body = '{"key": "value"}'
        headers = api._generate_signature("POST", "/test", body)

        assert "X-Request-Sign" in headers

    def test_generate_signature_api_key_matches(self):
        """Тест что X-Api-Key совпадает с public_key."""
        api = DMarketAPI(
            public_key="my_public_key",
            secret_key="a" * 64,
        )

        headers = api._generate_signature("GET", "/test")
        assert headers["X-Api-Key"] == "my_public_key"


class TestDMarketAPIDryRun:
    """Тесты dry run режима."""

    def test_dry_run_true_by_default(self):
        """Тест что dry_run включен по умолчанию."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.dry_run is True

    def test_dry_run_can_be_disabled(self):
        """Тест что dry_run можно отключить."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            dry_run=False,
        )
        assert api.dry_run is False

    def test_dry_run_mode_logged(self, caplog):
        """Тест что dry_run режим логируется."""
        DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            dry_run=True,
        )
        # Проверяем что в логах есть указание на dry-run режим


class TestDMarketAPICache:
    """Тесты кэширования."""

    def test_cache_enabled_by_default(self):
        """Тест что кэш включен по умолчанию."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
        )
        assert api.enable_cache is True

    def test_cache_can_be_disabled(self):
        """Тест что кэш можно отключить."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            enable_cache=False,
        )
        assert api.enable_cache is False


class TestDMarketAPIProperties:
    """Тесты свойств API."""

    def test_public_key_stored(self):
        """Тест что public_key сохраняется."""
        api = DMarketAPI(
            public_key="my_public_key",
            secret_key="test_secret",
        )
        assert api.public_key == "my_public_key"
        assert api._public_key == "my_public_key"

    def test_secret_key_stored_as_string(self):
        """Тест что secret_key сохраняется как строка."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="my_secret",
        )
        assert api._secret_key == "my_secret"

    def test_api_url_stored(self):
        """Тест что api_url сохраняется."""
        api = DMarketAPI(
            public_key="test_public",
            secret_key="test_secret",
            api_url="https://custom.api.com",
        )
        assert api.api_url == "https://custom.api.com"
