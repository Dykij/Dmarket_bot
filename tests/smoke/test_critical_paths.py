"""Smoke tests for critical path functionality.

Smoke tests verify that the most critical paths in the application work.
They are designed to be:
- FAST: Complete in under 5 seconds total
- RELIABLE: Never flaky, always deterministic
- CRITICAL: Cover the most important user journeys

Run with: pytest tests/smoke/ -v --tb=short
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as smoke tests
pytestmark = [pytest.mark.smoke, pytest.mark.asyncio]


class TestDMarketAPISmoke:
    """Smoke tests for DMarket API client."""

    def test_api_client_can_be_instantiated(self) -> None:
        """CRITICAL: API client instantiation must work."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI(
            public_key="test_key",
            secret_key="a" * 64,
        )

        assert api is not None
        assert api.public_key == "test_key"
        assert api.api_url == "https://api.dmarket.com"

    def test_api_client_generates_signature(self) -> None:
        """CRITICAL: Signature generation must work for authentication."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI(
            public_key="test_key",
            secret_key="a" * 64,
        )

        headers = api._generate_signature(
            method="GET",
            path="/account/v1/balance",
            body="",
        )

        assert "X-Api-Key" in headers
        assert "X-Request-Sign" in headers
        assert "X-Sign-Date" in headers

    async def test_api_balance_endpoint_exists(self) -> None:
        """CRITICAL: Balance endpoint must be callable."""
        from src.dmarket.dmarket_api import DMarketAPI

        api = DMarketAPI(
            public_key="test_key",
            secret_key="a" * 64,
        )

        # Mock the _request method to avoid real API calls
        with patch.object(api, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"usd": "10000"}
            result = await api.get_balance()

        assert result is not None
        mock_request.assert_called()


class TestArbitrageScannerSmoke:
    """Smoke tests for arbitrage scanner."""

    def test_scanner_can_be_instantiated(self) -> None:
        """CRITICAL: ArbitrageScanner instantiation must work."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner()

        assert scanner is not None
        assert scanner.min_profit == 0.5
        assert scanner.max_price == 50.0

    def test_scanner_has_required_methods(self) -> None:
        """CRITICAL: Scanner must have all required methods."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner()

        # Check all essential methods exist
        assert hasattr(scanner, "scan_game")
        assert hasattr(scanner, "scan_multiple_games")
        assert hasattr(scanner, "scan_level")
        assert hasattr(scanner, "check_user_balance")
        assert hasattr(scanner, "get_statistics")

        # Methods should be callable
        assert callable(scanner.scan_game)
        assert callable(scanner.scan_multiple_games)
        assert callable(scanner.get_statistics)

    def test_scanner_level_config(self) -> None:
        """CRITICAL: Level configurations must be accessible."""
        from src.dmarket.arbitrage_scanner import ArbitrageScanner

        scanner = ArbitrageScanner()

        # Test known levels: boost, standard, medium, advanced, pro
        for level in ["boost", "standard", "medium", "advanced", "pro"]:
            config = scanner.get_level_config(level)
            assert "price_range" in config
            assert "min_profit_percent" in config
            assert "name" in config


class TestTargetManagerSmoke:
    """Smoke tests for target management."""

    def test_target_manager_imports(self) -> None:
        """CRITICAL: Target manager module must import without errors."""
        from src.dmarket.targets import TargetManager

        assert TargetManager is not None

    def test_target_manager_instantiation(self) -> None:
        """CRITICAL: TargetManager instantiation must work."""
        from src.dmarket.targets import TargetManager

        mock_api = MagicMock()
        manager = TargetManager(api_client=mock_api)

        assert manager is not None
        assert manager.api is mock_api


class TestUtilsSmoke:
    """Smoke tests for utility modules."""

    def test_rate_limiter_instantiation(self) -> None:
        """CRITICAL: RateLimiter must work."""
        from src.utils.rate_limiter import RateLimiter

        limiter = RateLimiter(is_authorized=True)

        assert limiter is not None
        assert hasattr(limiter, "wait_if_needed")

    def test_memory_cache_instantiation(self) -> None:
        """CRITICAL: TTLCache must work."""
        from src.utils.memory_cache import TTLCache

        cache = TTLCache(max_size=100, default_ttl=300)

        assert cache is not None
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "clear")


class TestModelSmoke:
    """Smoke tests for data models."""

    def test_user_model_imports(self) -> None:
        """CRITICAL: User model must import."""
        from src.models.user import User

        assert User is not None

    def test_target_model_imports(self) -> None:
        """CRITICAL: Target model must import."""
        from src.models.target import Target

        assert Target is not None


class TestConfigSmoke:
    """Smoke tests for configuration."""

    def test_config_module_imports(self) -> None:
        """CRITICAL: Config module must import."""
        from src.utils import config

        assert config is not None

    def test_logging_utils_import(self) -> None:
        """CRITICAL: Logging utilities must import."""
        from src.utils import logging_utils

        assert logging_utils is not None


class TestExceptionsSmoke:
    """Smoke tests for exception handling."""

    def test_custom_exceptions_import(self) -> None:
        """CRITICAL: Custom exceptions must be importable."""
        from src.utils.exceptions import (
            APIError,
            AuthenticationError,
            BaseAppException,
            RateLimitExceeded,
            ValidationError,
        )

        assert BaseAppException is not None
        assert APIError is not None
        assert AuthenticationError is not None
        assert RateLimitExceeded is not None
        assert ValidationError is not None

    def test_exception_inheritance(self) -> None:
        """CRITICAL: Custom exceptions must be proper exception classes."""
        from src.utils.exceptions import APIError, BaseAppException

        assert issubclass(BaseAppException, Exception)
        assert issubclass(APIError, BaseAppException)


class TestInterfacesSmoke:
    """Smoke tests for protocol interfaces."""

    def test_interfaces_import(self) -> None:
        """CRITICAL: Protocol interfaces must import."""
        from src.interfaces import IDMarketAPI

        assert IDMarketAPI is not None


class TestDependencyInjectionSmoke:
    """Smoke tests for dependency injection."""

    def test_container_imports(self) -> None:
        """CRITICAL: DI container must import."""
        from src.containers import ContAlgoner

        assert ContAlgoner is not None

    def test_container_instantiation(self) -> None:
        """CRITICAL: DI container must be instantiable."""
        from src.containers import ContAlgoner

        container = ContAlgoner()
        assert container is not None
