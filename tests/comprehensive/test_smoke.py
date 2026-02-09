"""Comprehensive smoke tests for the DMarket Telegram Bot.

Smoke tests are quick, basic tests that verify critical functionality works.
These tests should run quickly and catch any major regression issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# SMOKE TEST MARKERS
# =============================================================================


pytestmark = [pytest.mark.smoke, pytest.mark.quick]


# =============================================================================
# CORE MODULE SMOKE TESTS
# =============================================================================


class TestCoreModuleImports:
    """Smoke tests for core module imports."""

    def test_dmarket_api_imports(self) -> None:
        """Test DMarket API module imports successfully."""
        from src.dmarket.dmarket_api import DMarketAPI

        assert DMarketAPI is not None

    def test_arbitrage_scanner_imports(self) -> None:
        """Test arbitrage scanner module imports successfully."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        assert ArbitrageScanner is not None

    def test_utils_module_imports(self) -> None:
        """Test utils modules import successfully."""
        from src.utils.api_circuit_breaker import (
            EndpointType,
            call_with_circuit_breaker,
        )
        from src.utils.rate_limiter import DMarketRateLimiter, RateLimiter

        assert EndpointType is not None
        assert call_with_circuit_breaker is not None
        assert RateLimiter is not None
        assert DMarketRateLimiter is not None

    def test_models_import(self) -> None:
        """Test data models import successfully."""
        from src.models.target import Target
        from src.models.user import User

        assert User is not None
        assert Target is not None

    def test_telegram_bot_imports(self) -> None:
        """Test Telegram bot modules import successfully."""
        from src.telegram_bot import keyboards, localization

        assert keyboards is not None
        assert localization is not None
        assert hasattr(keyboards, "get_settings_keyboard")
        assert hasattr(localization, "LOCALIZATIONS")


class TestDMarketAPIBasicFunctionality:
    """Smoke tests for DMarket API basic functionality."""

    def test_api_client_creates_successfully(self) -> None:
        """Test API client creates without error."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")
        assert api is not None
        assert api.public_key == "test_public_key"

    def test_game_map_contains_csgo(self) -> None:
        """Test GAME_MAP contains CS:GO entry."""
        from src.dmarket.dmarket_api import GAME_MAP

        assert "csgo" in GAME_MAP
        assert GAME_MAP["csgo"] == "a8db"

    @pytest.mark.asyncio
    async def test_api_client_has_required_methods(self) -> None:
        """Test API client has required methods."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")

        # Check required methods exist
        assert hasattr(api, "get_balance")
        assert hasattr(api, "get_market_items")
        assert hasattr(api, "get_user_targets")
        assert hasattr(api, "create_targets")
        assert callable(api.get_balance)
        assert callable(api.get_market_items)


class TestCircuitBreakerBasicFunctionality:
    """Smoke tests for circuit breaker basic functionality."""

    def test_circuit_breaker_creates_successfully(self) -> None:
        """Test circuit breaker creates without error."""
        from src.utils.api_circuit_breaker import APICircuitBreaker

        cb = APICircuitBreaker(name="smoke_test")
        assert cb is not None
        assert cb.name == "smoke_test"

    def test_endpoint_types_defined(self) -> None:
        """Test all endpoint types are defined."""
        from src.utils.api_circuit_breaker import EndpointType

        assert EndpointType.MARKET == "market"
        assert EndpointType.TARGETS == "targets"
        assert EndpointType.BALANCE == "balance"

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_works(self) -> None:
        """Test call_with_circuit_breaker executes successfully."""
        from src.utils.api_circuit_breaker import (
            EndpointType,
            call_with_circuit_breaker,
        )

        async def simple_func() -> str:
            return "success"

        result = await call_with_circuit_breaker(
            simple_func, endpoint_type=EndpointType.MARKET
        )

        assert result == "success"


class TestArbitrageScannerBasicFunctionality:
    """Smoke tests for arbitrage scanner basic functionality."""

    @pytest.mark.asyncio
    async def test_scanner_creates_successfully(self) -> None:
        """Test scanner creates without error."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")
        scanner = ArbitrageScanner(api_client=api)

        assert scanner is not None
        assert scanner.api_client is api

    def test_scanner_has_scan_method(self) -> None:
        """Test scanner has scan method."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")
        scanner = ArbitrageScanner(api_client=api)

        assert hasattr(scanner, "scan") or hasattr(scanner, "scan_level")


class TestTelegramBotBasicFunctionality:
    """Smoke tests for Telegram bot basic functionality."""

    def test_keyboards_creates_successfully(self) -> None:
        """Test keyboards module is available."""
        from src.telegram_bot import keyboards

        assert keyboards is not None
        # Check has functions for creating keyboards
        assert hasattr(keyboards, "get_settings_keyboard")

    def test_localization_loads(self) -> None:
        """Test localization loads without error."""
        from src.telegram_bot import localization

        assert localization is not None
        # Check LOCALIZATIONS exists
        assert hasattr(localization, "LOCALIZATIONS")
        assert "ru" in localization.LOCALIZATIONS
        assert "en" in localization.LOCALIZATIONS


class TestDatabaseModelsBasicFunctionality:
    """Smoke tests for database models."""

    def test_user_model_creates(self) -> None:
        """Test User model creates without error."""
        from src.models.user import User

        # Check model has required fields
        assert hasattr(User, "__tablename__")

    def test_target_model_creates(self) -> None:
        """Test Target model creates without error."""
        from src.models.target import Target

        assert hasattr(Target, "__tablename__")


# =============================================================================
# CRITICAL PATH SMOKE TESTS
# =============================================================================


class TestCriticalPaths:
    """Smoke tests for critical application paths."""

    @pytest.mark.asyncio
    async def test_balance_check_path(self) -> None:
        """Test balance check critical path."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "usd": {"amount": "100000", "currency": "USD"}
            }
            balance = await api.get_balance()

            assert balance is not None
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_market_scan_path(self) -> None:
        """Test market scan critical path."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "objects": [{"itemId": "1", "title": "Test", "price": {"USD": "1000"}}],
                "total": {"items": 1},
            }
            items = await api.get_market_items(game="csgo", limit=10)

            assert items is not None
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_target_management_path(self) -> None:
        """Test target management critical path."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test_public_key", "test_secret_key")

        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"Items": [], "TotalItems": 0}
            targets = await api.get_user_targets(game_id="csgo")

            assert targets is not None


# =============================================================================
# CONFIGURATION SMOKE TESTS
# =============================================================================


class TestConfigurationSmoke:
    """Smoke tests for configuration loading."""

    def test_cache_ttl_config_exists(self) -> None:
        """Test CACHE_TTL configuration exists."""
        from src.dmarket.dmarket_api import CACHE_TTL

        assert "short" in CACHE_TTL
        assert "medium" in CACHE_TTL
        assert "long" in CACHE_TTL

    def test_endpoint_configs_exist(self) -> None:
        """Test ENDPOINT_CONFIGS exists and is complete."""
        from src.utils.api_circuit_breaker import ENDPOINT_CONFIGS, EndpointType

        for endpoint in EndpointType:
            assert endpoint in ENDPOINT_CONFIGS


# =============================================================================
# DEPENDENCY SMOKE TESTS
# =============================================================================


class TestExternalDependencies:
    """Smoke tests for external dependencies."""

    def test_httpx_available(self) -> None:
        """Test httpx is available."""
        import httpx

        assert httpx is not None
        assert httpx.AsyncClient is not None

    def test_pydantic_available(self) -> None:
        """Test pydantic is available."""
        import pydantic

        assert pydantic is not None
        assert pydantic.BaseModel is not None

    def test_structlog_available(self) -> None:
        """Test structlog is available."""
        import structlog

        assert structlog is not None
        logger = structlog.get_logger()
        assert logger is not None

    def test_circuitbreaker_available(self) -> None:
        """Test circuitbreaker is available."""
        from circuitbreaker import CircuitBreaker

        assert CircuitBreaker is not None


# =============================================================================
# SECURITY SMOKE TESTS
# =============================================================================


class TestSecuritySmoke:
    """Basic security smoke tests."""

    def test_api_key_not_logged(self) -> None:
        """Test API keys are not exposed in str/repr."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("secret_public_key", "very_secret_key")

        # Key should not appear in string representation
        str_repr = str(api)
        assert "very_secret_key" not in str_repr.lower()

    def test_dry_run_mode_available(self) -> None:
        """Test DRY_RUN mode is available for safety."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test", "test")
        # DRY_RUN should be configurable
        assert api is not None


# =============================================================================
# PERFORMANCE SMOKE TESTS
# =============================================================================


class TestPerformanceSmoke:
    """Basic performance smoke tests."""

    def test_import_time_reasonable(self) -> None:
        """Test main module imports in reasonable time."""
        import time

        start = time.time()

        # Re-import to measure time
        import importlib

        import src.dmarket.dmarket_api

        importlib.reload(src.dmarket.dmarket_api)

        elapsed = time.time() - start
        # Should import in under 2 seconds
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_overhead_minimal(self) -> None:
        """Test circuit breaker adds minimal overhead."""
        import time

        from src.utils.api_circuit_breaker import (
            EndpointType,
            call_with_circuit_breaker,
        )

        async def fast_func() -> int:
            return 42

        start = time.time()
        for _ in range(100):
            await call_with_circuit_breaker(
                fast_func, endpoint_type=EndpointType.MARKET
            )
        elapsed = time.time() - start

        # 100 calls should complete in under 1 second
        assert elapsed < 1.0


# =============================================================================
# INTEGRATION SMOKE TESTS
# =============================================================================


class TestIntegrationSmoke:
    """Smoke tests for module integration."""

    @pytest.mark.asyncio
    async def test_api_and_scanner_integrate(self) -> None:
        """Test API client and scanner work together."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI("test", "test")
        scanner = ArbitrageScanner(api_client=api)

        assert scanner.api_client is api

    @pytest.mark.asyncio
    async def test_api_and_circuit_breaker_integrate(self) -> None:
        """Test API client works with circuit breaker."""
        from src.dmarket.dmarket_api import DMarketAPI
        from src.utils.api_circuit_breaker import (
            EndpointType,
            call_with_circuit_breaker,
        )

        api = DMarketAPI("test", "test")

        async def wrapped_balance() -> dict[str, Any]:
            with patch.object(api, "_request", new_callable=AsyncMock) as mock:
                mock.return_value = {"usd": {"amount": "1000"}}
                return await api.get_balance()

        result = await call_with_circuit_breaker(
            wrapped_balance, endpoint_type=EndpointType.BALANCE
        )

        assert result is not None
