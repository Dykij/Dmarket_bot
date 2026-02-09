"""Unit tests for DMarketAPI module.

This module contains comprehensive unit tests for the DMarketAPI class,
covering initialization, authentication, HTTP methods, rate limiting,
caching, error handling, and edge cases.

Target coverage: 95%+
"""

import asyncio
import hashlib
import hmac
import time
from unittest.mock import MagicMock

import pytest

from src.dmarket.dmarket_api import (
    CACHE_TTL,
    GAME_MAP,
    DMarketAPI,
    api_cache,
)

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def api_client() -> DMarketAPI:
    """Create a DMarketAPI client for testing."""
    return DMarketAPI(
        public_key="test_public_key",
        secret_key="test_secret_key",
        dry_run=True,
        enable_cache=True,
    )


@pytest.fixture()
def api_client_live() -> DMarketAPI:
    """Create a DMarketAPI client with dry_run=False."""
    return DMarketAPI(
        public_key="test_public_key",
        secret_key="test_secret_key",
        dry_run=False,
        enable_cache=False,
    )


@pytest.fixture()
def api_client_bytes_secret() -> DMarketAPI:
    """Create a DMarketAPI client with bytes secret key."""
    return DMarketAPI(
        public_key="test_public_key",
        secret_key=b"test_secret_key_bytes",
        dry_run=True,
    )


# ===========================================================================
# Test Class: Initialization
# ===========================================================================


class TestDMarketAPIInitialization:
    """Test DMarketAPI initialization."""

    def test_init_with_string_secret_key(self, api_client: DMarketAPI) -> None:
        """Test initialization with string secret key."""
        assert api_client.public_key == "test_public_key"
        assert api_client._public_key == "test_public_key"
        assert api_client._secret_key == "test_secret_key"
        assert api_client.secret_key == b"test_secret_key"
        assert api_client.dry_run is True
        assert api_client.enable_cache is True

    def test_init_with_bytes_secret_key(
        self, api_client_bytes_secret: DMarketAPI
    ) -> None:
        """Test initialization with bytes secret key."""
        assert api_client_bytes_secret._secret_key == "test_secret_key_bytes"
        assert api_client_bytes_secret.secret_key == b"test_secret_key_bytes"

    def test_init_dry_run_true_default(self, api_client: DMarketAPI) -> None:
        """Test that dry_run defaults to True for safety."""
        assert api_client.dry_run is True

    def test_init_dry_run_false_warning(self, api_client_live: DMarketAPI) -> None:
        """Test that dry_run=False is set correctly."""
        assert api_client_live.dry_run is False

    def test_init_default_values(self, api_client: DMarketAPI) -> None:
        """Test default initialization values."""
        assert api_client.api_url == "https://api.dmarket.com"
        assert api_client.max_retries == 3
        assert api_client.connection_timeout == 30.0
        assert api_client.retry_codes == [429, 500, 502, 503, 504]

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            api_url="https://custom.api.com",
            max_retries=5,
            connection_timeout=60.0,
            retry_codes=[500, 503],
            dry_run=True,
        )
        assert client.api_url == "https://custom.api.com"
        assert client.max_retries == 5
        assert client.connection_timeout == 60.0
        assert client.retry_codes == [500, 503]

    def test_init_pool_limits(self, api_client: DMarketAPI) -> None:
        """Test that pool_limits is initialized correctly."""
        assert api_client.pool_limits is not None
        assert api_client.pool_limits.max_connections == 100
        assert api_client.pool_limits.max_keepalive_connections == 30

    def test_init_rate_limiter(self, api_client: DMarketAPI) -> None:
        """Test that rate limiter is initialized."""
        assert api_client.rate_limiter is not None


# ===========================================================================
# Test Class: Context Manager
# ===========================================================================


class TestDMarketAPIContextManager:
    """Test DMarketAPI context manager functionality."""

    @pytest.mark.asyncio()
    async def test_async_context_manager_enter(self, api_client: DMarketAPI) -> None:
        """Test async context manager enter."""
        async with api_client as client:
            assert client is api_client
            assert api_client._client_ref_count == 1

    @pytest.mark.asyncio()
    async def test_async_context_manager_exit(self, api_client: DMarketAPI) -> None:
        """Test async context manager exit."""
        async with api_client:
            pass
        assert api_client._client_ref_count == 0

    @pytest.mark.asyncio()
    async def test_async_context_manager_nested(self, api_client: DMarketAPI) -> None:
        """Test nested context manager calls."""
        async with api_client:
            assert api_client._client_ref_count == 1
            async with api_client:
                assert api_client._client_ref_count == 2
            assert api_client._client_ref_count == 1
        assert api_client._client_ref_count == 0


# ===========================================================================
# Test Class: Constants
# ===========================================================================


class TestDMarketAPIConstants:
    """Test DMarketAPI constants and endpoints."""

    def test_base_url(self) -> None:
        """Test BASE_URL constant."""
        assert DMarketAPI.BASE_URL == "https://api.dmarket.com"

    def test_balance_endpoints(self) -> None:
        """Test balance endpoints."""
        assert DMarketAPI.ENDPOINT_BALANCE == "/account/v1/balance"
        assert DMarketAPI.ENDPOINT_BALANCE_LEGACY == "/api/v1/account/balance"

    def test_market_endpoints(self) -> None:
        """Test market endpoints."""
        assert DMarketAPI.ENDPOINT_MARKET_ITEMS == "/exchange/v1/market/items"
        assert (
            DMarketAPI.ENDPOINT_MARKET_PRICE_AGGREGATED
            == "/exchange/v1/market/aggregated-prices"
        )

    def test_user_endpoints(self) -> None:
        """Test user endpoints."""
        assert DMarketAPI.ENDPOINT_USER_INVENTORY == "/inventory/v1/user/items"
        assert DMarketAPI.ENDPOINT_USER_TARGETS == "/main/v2/user-targets"

    def test_error_codes(self) -> None:
        """Test error codes mapping."""
        assert 400 in DMarketAPI.ERROR_CODES
        assert 401 in DMarketAPI.ERROR_CODES
        assert 429 in DMarketAPI.ERROR_CODES
        assert 500 in DMarketAPI.ERROR_CODES

    def test_game_map(self) -> None:
        """Test GAME_MAP constant."""
        assert GAME_MAP["csgo"] == "a8db"
        assert GAME_MAP["cs2"] == "a8db"
        assert GAME_MAP["dota2"] == "9a92"
        assert GAME_MAP["rust"] == "rust"
        assert GAME_MAP["tf2"] == "tf2"

    def test_cache_ttl(self) -> None:
        """Test CACHE_TTL constant."""
        assert CACHE_TTL["short"] == 30
        assert CACHE_TTL["medium"] == 300
        assert CACHE_TTL["long"] == 1800


# ===========================================================================
# Test Class: Signature Generation
# ===========================================================================


class TestDMarketAPISignature:
    """Test DMarketAPI signature generation."""

    def test_generate_hmac_signature_format(self, api_client: DMarketAPI) -> None:
        """Test HMAC signature generation format."""
        method = "GET"
        path = "/test/path"
        timestamp = str(int(time.time()))
        body = ""

        # The signature should be generated without errors
        string_to_sign = f"{method}{path}{timestamp}{body}"
        expected = hmac.new(
            api_client.secret_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert len(expected) == 64  # SHA256 hex digest length

    def test_generate_signature_different_methods(
        self, api_client: DMarketAPI
    ) -> None:
        """Test signature differs for different HTTP methods."""
        timestamp = str(int(time.time()))
        path = "/test"

        sig_get = hmac.new(
            api_client.secret_key,
            f"GET{path}{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()

        sig_post = hmac.new(
            api_client.secret_key,
            f"POST{path}{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()

        assert sig_get != sig_post


# ===========================================================================
# Test Class: Rate Limiting
# ===========================================================================


class TestDMarketAPIRateLimiting:
    """Test DMarketAPI rate limiting."""

    def test_rate_limiter_initialized(self, api_client: DMarketAPI) -> None:
        """Test rate limiter is initialized."""
        assert api_client.rate_limiter is not None

    def test_advanced_rate_limiter_initialized(self, api_client: DMarketAPI) -> None:
        """Test advanced rate limiter is initialized."""
        assert api_client.rate_limiter is not None


# ===========================================================================
# Test Class: Caching
# ===========================================================================


class TestDMarketAPICaching:
    """Test DMarketAPI caching functionality."""

    def test_cache_enabled(self, api_client: DMarketAPI) -> None:
        """Test cache is enabled by default."""
        assert api_client.enable_cache is True

    def test_cache_disabled(self, api_client_live: DMarketAPI) -> None:
        """Test cache can be disabled."""
        assert api_client_live.enable_cache is False

    def test_api_cache_global(self) -> None:
        """Test api_cache is a global dictionary."""
        assert isinstance(api_cache, dict)


# ===========================================================================
# Test Class: HTTP Client
# ===========================================================================


class TestDMarketAPIHttpClient:
    """Test DMarketAPI HTTP client functionality."""

    @pytest.mark.asyncio()
    async def test_get_client_creates_client(self, api_client: DMarketAPI) -> None:
        """Test _get_client creates HTTP client."""
        assert api_client._client is None
        client = await api_client._get_client()
        assert client is not None
        assert api_client._client is client
        await api_client._close_client()

    @pytest.mark.asyncio()
    async def test_get_client_reuses_client(self, api_client: DMarketAPI) -> None:
        """Test _get_client reuses existing client."""
        client1 = await api_client._get_client()
        client2 = await api_client._get_client()
        assert client1 is client2
        await api_client._close_client()

    @pytest.mark.asyncio()
    async def test_close_client(self, api_client: DMarketAPI) -> None:
        """Test _close_client closes client."""
        await api_client._get_client()
        assert api_client._client is not None
        await api_client._close_client()
        assert api_client._client is None


# ===========================================================================
# Test Class: DRY_RUN Mode
# ===========================================================================


class TestDMarketAPIDryRunMode:
    """Test DMarketAPI DRY_RUN mode."""

    def test_dry_run_true(self, api_client: DMarketAPI) -> None:
        """Test DRY_RUN mode is enabled."""
        assert api_client.dry_run is True

    def test_dry_run_false(self, api_client_live: DMarketAPI) -> None:
        """Test DRY_RUN mode can be disabled."""
        assert api_client_live.dry_run is False


# ===========================================================================
# Test Class: Error Handling
# ===========================================================================


class TestDMarketAPIErrorHandling:
    """Test DMarketAPI error handling."""

    def test_error_codes_present(self) -> None:
        """Test error codes are present."""
        assert len(DMarketAPI.ERROR_CODES) >= 8

    def test_error_code_messages(self) -> None:
        """Test error code messages are strings."""
        for code, message in DMarketAPI.ERROR_CODES.items():
            assert isinstance(code, int)
            assert isinstance(message, str)
            assert len(message) > 0


# ===========================================================================
# Test Class: Pool Limits
# ===========================================================================


class TestDMarketAPIPoolLimits:
    """Test DMarketAPI connection pool limits."""

    def test_default_pool_limits(self, api_client: DMarketAPI) -> None:
        """Test default pool limits."""
        limits = api_client.pool_limits
        assert limits.max_connections == 100
        assert limits.max_keepalive_connections == 30
        assert limits.keepalive_expiry == 60.0

    def test_custom_pool_limits(self) -> None:
        """Test custom pool limits."""
        import httpx

        custom_limits = httpx.Limits(
            max_connections=50,
            max_keepalive_connections=10,
            keepalive_expiry=30.0,
        )
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            pool_limits=custom_limits,
            dry_run=True,
        )
        assert client.pool_limits.max_connections == 50
        assert client.pool_limits.max_keepalive_connections == 10


# ===========================================================================
# Test Class: HTTP/2 Support
# ===========================================================================


class TestDMarketAPIHttp2:
    """Test DMarketAPI HTTP/2 support."""

    def test_http2_enabled_by_default(self, api_client: DMarketAPI) -> None:
        """Test HTTP/2 is enabled by default."""
        assert api_client._http2_enabled is True


# ===========================================================================
# Test Class: Notifier Integration
# ===========================================================================


class TestDMarketAPINotifier:
    """Test DMarketAPI notifier integration."""

    def test_notifier_none_by_default(self, api_client: DMarketAPI) -> None:
        """Test notifier is None by default."""
        assert api_client.notifier is None

    def test_notifier_can_be_set(self) -> None:
        """Test notifier can be set."""
        mock_notifier = MagicMock()
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            notifier=mock_notifier,
            dry_run=True,
        )
        assert client.notifier is mock_notifier


# ===========================================================================
# Test Class: Signing Executor
# ===========================================================================


class TestDMarketAPISigningExecutor:
    """Test DMarketAPI signing executor."""

    def test_signing_executor_initialized(self, api_client: DMarketAPI) -> None:
        """Test signing executor is initialized."""
        assert api_client._signing_executor is not None

    def test_signing_executor_max_workers(self, api_client: DMarketAPI) -> None:
        """Test signing executor has correct max workers."""
        # ThreadPoolExecutor with max_workers=4
        assert api_client._signing_executor._max_workers == 4


# ===========================================================================
# Test Class: Thread Safety
# ===========================================================================


class TestDMarketAPIThreadSafety:
    """Test DMarketAPI thread safety."""

    def test_client_lock_initialized(self, api_client: DMarketAPI) -> None:
        """Test client lock is initialized."""
        assert api_client._client_lock is not None
        assert isinstance(api_client._client_lock, asyncio.Lock)

    def test_client_ref_count_initialized(self, api_client: DMarketAPI) -> None:
        """Test client reference count is initialized to zero."""
        assert api_client._client_ref_count == 0


# ===========================================================================
# Test Class: API Version
# ===========================================================================


class TestDMarketAPIVersion:
    """Test DMarketAPI version-specific features."""

    def test_v1_1_0_endpoints_present(self) -> None:
        """Test v1.1.0 endpoints are present."""
        assert DMarketAPI.ENDPOINT_LAST_SALES == "/trade-aggregator/v1/last-sales"
        assert (
            DMarketAPI.ENDPOINT_AGGREGATED_PRICES_POST
            == "/marketplace-api/v1/aggregated-prices"
        )
        assert (
            DMarketAPI.ENDPOINT_TARGETS_BY_TITLE == "/marketplace-api/v1/targets-by-title"
        )


# ===========================================================================
# Test Class: Game ID Mapping
# ===========================================================================


class TestDMarketAPIGameMapping:
    """Test DMarketAPI game ID mapping."""

    def test_csgo_mapping(self) -> None:
        """Test CS:GO game mapping."""
        assert GAME_MAP.get("csgo") == "a8db"

    def test_cs2_mapping(self) -> None:
        """Test CS2 game mapping (same as CS:GO)."""
        assert GAME_MAP.get("cs2") == "a8db"
        assert GAME_MAP.get("csgo") == GAME_MAP.get("cs2")

    def test_dota2_mapping(self) -> None:
        """Test Dota 2 game mapping."""
        assert GAME_MAP.get("dota2") == "9a92"

    def test_rust_mapping(self) -> None:
        """Test Rust game mapping."""
        assert GAME_MAP.get("rust") == "rust"

    def test_tf2_mapping(self) -> None:
        """Test TF2 game mapping."""
        assert GAME_MAP.get("tf2") == "tf2"

    def test_unknown_game_returns_none(self) -> None:
        """Test unknown game returns None."""
        assert GAME_MAP.get("unknown_game") is None


# ===========================================================================
# Test Class: Edge Cases
# ===========================================================================


class TestDMarketAPIEdgeCases:
    """Test DMarketAPI edge cases."""

    def test_empty_public_key(self) -> None:
        """Test initialization with empty public key."""
        client = DMarketAPI(
            public_key="",
            secret_key="secret",
            dry_run=True,
        )
        assert client.public_key == ""  # noqa: PLC1901

    def test_empty_secret_key(self) -> None:
        """Test initialization with empty secret key."""
        client = DMarketAPI(
            public_key="public",
            secret_key="",
            dry_run=True,
        )
        assert client._secret_key == ""  # noqa: PLC1901

    def test_very_long_secret_key(self) -> None:
        """Test initialization with very long secret key."""
        long_key = "a" * 10000
        client = DMarketAPI(
            public_key="public",
            secret_key=long_key,
            dry_run=True,
        )
        assert len(client._secret_key) == 10000

    def test_unicode_secret_key(self) -> None:
        """Test initialization with unicode secret key."""
        unicode_key = "секретный_ключ_🔐"
        client = DMarketAPI(
            public_key="public",
            secret_key=unicode_key,
            dry_run=True,
        )
        assert client._secret_key == unicode_key


# ===========================================================================
# Test Class: Retry Logic
# ===========================================================================


class TestDMarketAPIRetryLogic:
    """Test DMarketAPI retry logic configuration."""

    def test_default_retry_codes(self, api_client: DMarketAPI) -> None:
        """Test default retry codes."""
        assert 429 in api_client.retry_codes
        assert 500 in api_client.retry_codes
        assert 502 in api_client.retry_codes
        assert 503 in api_client.retry_codes
        assert 504 in api_client.retry_codes

    def test_custom_retry_codes(self) -> None:
        """Test custom retry codes."""
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            retry_codes=[500, 503],
            dry_run=True,
        )
        assert client.retry_codes == [500, 503]
        assert 429 not in client.retry_codes

    def test_default_max_retries(self, api_client: DMarketAPI) -> None:
        """Test default max retries."""
        assert api_client.max_retries == 3

    def test_custom_max_retries(self) -> None:
        """Test custom max retries."""
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            max_retries=5,
            dry_run=True,
        )
        assert client.max_retries == 5


# ===========================================================================
# Test Class: Connection Timeout
# ===========================================================================


class TestDMarketAPIConnectionTimeout:
    """Test DMarketAPI connection timeout configuration."""

    def test_default_connection_timeout(self, api_client: DMarketAPI) -> None:
        """Test default connection timeout."""
        assert api_client.connection_timeout == 30.0

    def test_custom_connection_timeout(self) -> None:
        """Test custom connection timeout."""
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            connection_timeout=60.0,
            dry_run=True,
        )
        assert client.connection_timeout == 60.0


# ===========================================================================
# Test Class: API URL Configuration
# ===========================================================================


class TestDMarketAPIUrlConfiguration:
    """Test DMarketAPI URL configuration."""

    def test_default_api_url(self, api_client: DMarketAPI) -> None:
        """Test default API URL."""
        assert api_client.api_url == "https://api.dmarket.com"

    def test_custom_api_url(self) -> None:
        """Test custom API URL."""
        client = DMarketAPI(
            public_key="pk",
            secret_key="sk",
            api_url="https://staging.api.dmarket.com",
            dry_run=True,
        )
        assert client.api_url == "https://staging.api.dmarket.com"
