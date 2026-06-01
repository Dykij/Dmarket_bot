"""Unit tests for src/telegram_bot/utils/api_client.py module.

Tests for DMarket API client creation and key validation.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetupApiClient:
    """Tests for setup_api_client function."""

    def test_setup_api_client_with_valid_env_vars(self):
        """Test setup_api_client creates client with valid env vars."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public_key",
                    "DMARKET_SECRET_KEY": "test_secret_key",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance

            result = setup_api_client()

            assert result == mock_instance
            mock_api.assert_called_once()

    def test_setup_api_client_without_public_key(self):
        """Test setup_api_client returns None without public key."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with patch.dict(
            os.environ,
            {"DMARKET_SECRET_KEY": "test_secret_key"},
            clear=True,
        ):
            result = setup_api_client()

            assert result is None

    def test_setup_api_client_without_secret_key(self):
        """Test setup_api_client returns None without secret key."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with patch.dict(
            os.environ,
            {"DMARKET_PUBLIC_KEY": "test_public_key"},
            clear=True,
        ):
            result = setup_api_client()

            assert result is None

    def test_setup_api_client_without_any_keys(self):
        """Test setup_api_client returns None without any keys."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with patch.dict(os.environ, {}, clear=True):
            result = setup_api_client()

            assert result is None

    def test_setup_api_client_uses_custom_api_url(self):
        """Test setup_api_client uses custom API URL from env."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                    "DMARKET_API_URL": "https://custom.api.url",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client()

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["api_url"] == "https://custom.api.url"

    def test_setup_api_client_uses_default_api_url(self):
        """Test setup_api_client uses default API URL when not specified."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client()

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["api_url"] == "https://api.dmarket.com"

    def test_setup_api_client_sets_max_retries(self):
        """Test setup_api_client sets max_retries parameter."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client()

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["max_retries"] == 3

    def test_setup_api_client_sets_connection_timeout(self):
        """Test setup_api_client sets connection_timeout parameter."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client()

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["connection_timeout"] == 30.0

    def test_setup_api_client_enables_cache(self):
        """Test setup_api_client enables caching."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client()

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["enable_cache"] is True

    def test_setup_api_client_handles_exception(self):
        """Test setup_api_client handles exceptions during creation."""
        from src.telegram_bot.utils.api_client import setup_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "test_public",
                    "DMARKET_SECRET_KEY": "test_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.side_effect = Exception("Creation failed")

            result = setup_api_client()

            assert result is None


class TestSetupApiClientWithKeys:
    """Tests for setup_api_client_with_keys function."""

    def test_setup_api_client_with_keys_creates_client(self):
        """Test setup_api_client_with_keys creates client with provided keys."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        with patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance

            result = setup_api_client_with_keys("public_key", "secret_key")

            assert result == mock_instance
            mock_api.assert_called_once()
            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "public_key"
            assert call_kwargs["secret_key"] == "secret_key"

    def test_setup_api_client_with_keys_empty_public_key(self):
        """Test setup_api_client_with_keys returns None for empty public key."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        result = setup_api_client_with_keys("", "secret_key")

        assert result is None

    def test_setup_api_client_with_keys_empty_secret_key(self):
        """Test setup_api_client_with_keys returns None for empty secret key."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        result = setup_api_client_with_keys("public_key", "")

        assert result is None

    def test_setup_api_client_with_keys_none_public_key(self):
        """Test setup_api_client_with_keys returns None for None public key."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        result = setup_api_client_with_keys(None, "secret_key")

        assert result is None

    def test_setup_api_client_with_keys_none_secret_key(self):
        """Test setup_api_client_with_keys returns None for None secret key."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        result = setup_api_client_with_keys("public_key", None)

        assert result is None

    def test_setup_api_client_with_keys_handles_exception(self):
        """Test setup_api_client_with_keys handles exceptions."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        with patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api:
            mock_api.side_effect = Exception("Creation failed")

            result = setup_api_client_with_keys("public", "secret")

            assert result is None

    def test_setup_api_client_with_keys_uses_env_api_url(self):
        """Test setup_api_client_with_keys uses API URL from env."""
        from src.telegram_bot.utils.api_client import setup_api_client_with_keys

        with (
            patch.dict(
                os.environ,
                {"DMARKET_API_URL": "https://custom.url"},
            ),
            patch("src.telegram_bot.utils.api_client.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            setup_api_client_with_keys("public", "secret")

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["api_url"] == "https://custom.url"


class TestValidateApiKeys:
    """Tests for validate_api_keys function."""

    @pytest.mark.asyncio()
    async def test_validate_api_keys_with_valid_keys(self):
        """Test validate_api_keys returns True for valid keys."""
        from src.telegram_bot.utils.api_client import validate_api_keys

        with patch(
            "src.telegram_bot.utils.api_client.setup_api_client_with_keys"
        ) as mock_setup:
            mock_api = AsyncMock()
            mock_api.get_balance = AsyncMock(return_value={"usd": "100"})
            mock_api.__aenter__ = AsyncMock(return_value=mock_api)
            mock_api.__aexit__ = AsyncMock(return_value=None)
            mock_setup.return_value = mock_api

            success, message = await validate_api_keys("public", "secret")

            assert success is True
            assert "валидны" in message

    @pytest.mark.asyncio()
    async def test_validate_api_keys_with_api_error_response(self):
        """Test validate_api_keys returns False when API returns error."""
        from src.telegram_bot.utils.api_client import validate_api_keys

        with patch(
            "src.telegram_bot.utils.api_client.setup_api_client_with_keys"
        ) as mock_setup:
            mock_api = AsyncMock()
            mock_api.get_balance = AsyncMock(
                return_value={"error": True, "error_message": "Invalid key"}
            )
            mock_api.__aenter__ = AsyncMock(return_value=mock_api)
            mock_api.__aexit__ = AsyncMock(return_value=None)
            mock_setup.return_value = mock_api

            success, message = await validate_api_keys("public", "secret")

            assert success is False
            assert "Invalid key" in message

    @pytest.mark.asyncio()
    async def test_validate_api_keys_with_client_creation_failure(self):
        """Test validate_api_keys returns False when client creation fails."""
        from src.telegram_bot.utils.api_client import validate_api_keys

        with patch(
            "src.telegram_bot.utils.api_client.setup_api_client_with_keys"
        ) as mock_setup:
            mock_setup.return_value = None

            success, message = await validate_api_keys("public", "secret")

            assert success is False
            assert "Не удалось создать клиент" in message

    @pytest.mark.asyncio()
    async def test_validate_api_keys_handles_exception(self):
        """Test validate_api_keys handles exceptions."""
        from src.telegram_bot.utils.api_client import validate_api_keys

        with patch(
            "src.telegram_bot.utils.api_client.setup_api_client_with_keys"
        ) as mock_setup:
            mock_api = AsyncMock()
            mock_api.get_balance = AsyncMock(side_effect=Exception("API Error"))
            mock_api.__aenter__ = AsyncMock(return_value=mock_api)
            mock_api.__aexit__ = AsyncMock(return_value=None)
            mock_setup.return_value = mock_api

            success, message = await validate_api_keys("public", "secret")

            assert success is False
            assert "Ошибка" in message


class TestCreateApiClientFromEnvAlias:
    """Tests for create_api_client_from_env alias."""

    def test_create_api_client_from_env_is_alias(self):
        """Test create_api_client_from_env is alias for setup_api_client."""
        from src.telegram_bot.utils.api_client import (
            create_api_client_from_env,
            setup_api_client,
        )

        assert create_api_client_from_env is setup_api_client


class TestModuleExports:
    """Tests for module exports."""

    def test_module_exports_all_functions(self):
        """Test module exports all required functions."""
        from src.telegram_bot.utils import api_client

        assert hasattr(api_client, "setup_api_client")
        assert hasattr(api_client, "setup_api_client_with_keys")
        assert hasattr(api_client, "validate_api_keys")
        assert hasattr(api_client, "create_api_client_from_env")

        # Check __all__
        assert "setup_api_client" in api_client.__all__
        assert "setup_api_client_with_keys" in api_client.__all__
        assert "validate_api_keys" in api_client.__all__
        assert "create_api_client_from_env" in api_client.__all__
