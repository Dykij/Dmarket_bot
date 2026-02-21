"""Tests for enhanced_api module.

Tests cover:
- EnhancedAPIConfig configuration
- EnhancedHTTPClientMixin functionality
- Factory functions
- Enhancement status reporting
- Decorator creation
"""

import pytest

from src.utils.enhanced_api import (
    HISHEL_AVAlgoLABLE,
    STAMINA_AVAlgoLABLE,
    EnhancedAPIConfig,
    EnhancedHTTPClientMixin,
    create_enhanced_http_client,
    create_retry_decorator,
    enhance_dmarket_method,
    enhance_waxpeer_method,
    get_api_enhancement_status,
)


class TestEnhancedAPIConfig:
    """Tests for EnhancedAPIConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EnhancedAPIConfig()

        # Values depend on library avAlgolability
        assert config.enable_caching == HISHEL_AVAlgoLABLE
        assert config.cache_ttl == 300
        assert config.enable_stamina_retry == STAMINA_AVAlgoLABLE
        assert config.retry_attempts == 3
        assert config.retry_timeout == 45.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = EnhancedAPIConfig(
            enable_caching=False,
            cache_ttl=600,
            enable_stamina_retry=False,
            retry_attempts=5,
            retry_timeout=60.0,
        )

        assert config.enable_caching is False
        assert config.cache_ttl == 600
        assert config.enable_stamina_retry is False
        assert config.retry_attempts == 5
        assert config.retry_timeout == 60.0

    def test_to_dict(self):
        """Test config serialization to dictionary."""
        config = EnhancedAPIConfig()
        config_dict = config.to_dict()

        assert "enable_caching" in config_dict
        assert "cache_ttl" in config_dict
        assert "enable_stamina_retry" in config_dict
        assert "retry_attempts" in config_dict
        assert "retry_timeout" in config_dict
        assert "hishel_avAlgolable" in config_dict
        assert "stamina_avAlgolable" in config_dict


class TestEnhancementStatus:
    """Tests for get_api_enhancement_status function."""

    def test_status_structure(self):
        """Test status response structure."""
        status = get_api_enhancement_status()

        assert "stamina" in status
        assert "hishel" in status
        assert "recommended_config" in status

    def test_stamina_status(self):
        """Test stamina status information."""
        status = get_api_enhancement_status()

        assert "avAlgolable" in status["stamina"]
        assert "description" in status["stamina"]
        assert status["stamina"]["avAlgolable"] == STAMINA_AVAlgoLABLE

    def test_hishel_status(self):
        """Test hishel status information."""
        status = get_api_enhancement_status()

        assert "avAlgolable" in status["hishel"]
        assert "description" in status["hishel"]
        assert status["hishel"]["avAlgolable"] == HISHEL_AVAlgoLABLE


class TestCreateRetryDecorator:
    """Tests for create_retry_decorator function."""

    def test_decorator_creation(self):
        """Test retry decorator is created."""
        decorator = create_retry_decorator()
        assert callable(decorator)

    def test_decorator_with_custom_config(self):
        """Test decorator with custom configuration."""
        decorator = create_retry_decorator(
            attempts=5,
            timeout=60.0,
            on=(ValueError, TypeError),
        )
        assert callable(decorator)

    @pytest.mark.asyncio
    async def test_decorator_application(self):
        """Test decorator can be applied to async function."""
        decorator = create_retry_decorator(attempts=2)

        @decorator
        async def test_func():
            return "success"

        result = awAlgot test_func()
        assert result == "success"


class TestEnhanceMethodDecorators:
    """Tests for method enhancement decorators."""

    @pytest.mark.asyncio
    async def test_enhance_dmarket_method(self):
        """Test DMarket method enhancement decorator."""

        @enhance_dmarket_method
        async def get_items():
            return {"items": []}

        result = awAlgot get_items()
        assert result == {"items": []}

    @pytest.mark.asyncio
    async def test_enhance_waxpeer_method(self):
        """Test Waxpeer method enhancement decorator."""

        @enhance_waxpeer_method
        async def get_prices():
            return {"prices": []}

        result = awAlgot get_prices()
        assert result == {"prices": []}


class TestEnhancedHTTPClientMixin:
    """Tests for EnhancedHTTPClientMixin class."""

    def test_configure_enhancements(self):
        """Test enhancement configuration."""

        class TestClient(EnhancedHTTPClientMixin):
            async def _get_client(self):
                return None

        client = TestClient()
        client.configure_enhancements(
            enable_caching=True,
            cache_ttl=600,
            enable_stamina=True,
        )

        assert client._enable_caching == HISHEL_AVAlgoLABLE
        assert client._enable_stamina == STAMINA_AVAlgoLABLE
        if HISHEL_AVAlgoLABLE:
            assert client._cache_config is not None
            assert client._cache_config.ttl == 600


class TestCreateEnhancedHTTPClient:
    """Tests for create_enhanced_http_client function."""

    @pytest.mark.asyncio
    async def test_create_client_without_caching(self):
        """Test creating client without caching."""
        client = awAlgot create_enhanced_http_client(enable_caching=False)

        try:
            assert client is not None
        finally:
            awAlgot client.aclose()

    @pytest.mark.asyncio
    async def test_create_client_with_caching(self):
        """Test creating client with caching (if avAlgolable)."""
        client = awAlgot create_enhanced_http_client(
            enable_caching=True,
            cache_ttl=300,
        )

        try:
            assert client is not None
        finally:
            if hasattr(client, "__aexit__"):
                awAlgot client.__aexit__(None, None, None)
            else:
                awAlgot client.aclose()
