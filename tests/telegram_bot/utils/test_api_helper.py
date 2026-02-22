"""Unit tests for src/telegram_bot/utils/api_helper.py module.

Tests for DMarket API client creation helper functions.
"""

import os
from unittest.mock import MagicMock, patch


class TestCreateDmarketApiClient:
    """Tests for create_dmarket_api_client function."""

    def test_create_dmarket_api_client_from_context_bot_data(self):
        """Test create_dmarket_api_client uses keys from context.bot_data."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        mock_context = MagicMock()
        mock_context.bot_data = {
            "DMARKET_PUBLIC_KEY": "context_public_key",
            "DMARKET_SECRET_KEY": "context_secret_key",
        }

        with patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance

            result = create_dmarket_api_client(mock_context)

            assert result == mock_instance
            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "context_public_key"
            assert call_kwargs["secret_key"] == "context_secret_key"

    def test_create_dmarket_api_client_from_env_vars(self):
        """Test create_dmarket_api_client uses keys from environment."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "env_public_key",
                    "DMARKET_SECRET_KEY": "env_secret_key",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance

            result = create_dmarket_api_client(None)

            assert result == mock_instance
            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "env_public_key"
            assert call_kwargs["secret_key"] == "env_secret_key"

    def test_create_dmarket_api_client_prefers_context_over_env(self):
        """Test create_dmarket_api_client prefers context keys over env."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        mock_context = MagicMock()
        mock_context.bot_data = {
            "DMARKET_PUBLIC_KEY": "context_public",
            "DMARKET_SECRET_KEY": "context_secret",
        }

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "env_public",
                    "DMARKET_SECRET_KEY": "env_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(mock_context)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "context_public"
            assert call_kwargs["secret_key"] == "context_secret"

    def test_create_dmarket_api_client_falls_back_to_env_for_missing_context_keys(self):
        """Test create_dmarket_api_client falls back to env when context keys missing."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        mock_context = MagicMock()
        mock_context.bot_data = {}  # Empty bot_data

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "env_public",
                    "DMARKET_SECRET_KEY": "env_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(mock_context)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "env_public"
            assert call_kwargs["secret_key"] == "env_secret"

    def test_create_dmarket_api_client_handles_missing_public_key(self):
        """Test create_dmarket_api_client handles missing public key."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {"DMARKET_SECRET_KEY": "secret_key"},
                clear=True,
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(None)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == ""

    def test_create_dmarket_api_client_handles_missing_secret_key(self):
        """Test create_dmarket_api_client handles missing secret key."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {"DMARKET_PUBLIC_KEY": "public_key"},
                clear=True,
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(None)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["secret_key"] == ""

    def test_create_dmarket_api_client_handles_missing_both_keys(self):
        """Test create_dmarket_api_client handles missing both keys."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with patch.dict(os.environ, {}, clear=True):
            with patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api:
                mock_api.return_value = MagicMock()

                create_dmarket_api_client(None)

                call_kwargs = mock_api.call_args[1]
                assert call_kwargs["public_key"] == ""
                assert call_kwargs["secret_key"] == ""

    def test_create_dmarket_api_client_with_context_without_bot_data_attr(self):
        """Test create_dmarket_api_client when context has no bot_data."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        mock_context = MagicMock(spec=[])  # No bot_data attribute

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "env_public",
                    "DMARKET_SECRET_KEY": "env_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(mock_context)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "env_public"
            assert call_kwargs["secret_key"] == "env_secret"

    def test_create_dmarket_api_client_logs_key_prefix_suffix(self):
        """Test create_dmarket_api_client logs key prefix and suffix."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "abcd1234efgh",
                    "DMARKET_SECRET_KEY": "secretkey123",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            with patch("src.telegram_bot.utils.api_helper.logger") as mock_logger:
                create_dmarket_api_client(None)

                # Should log something about the key
                assert mock_logger.debug.called or mock_logger.warning.called

    def test_create_dmarket_api_client_returns_dmarket_api_instance(self):
        """Test create_dmarket_api_client returns DMarketAPI instance."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "public",
                    "DMARKET_SECRET_KEY": "secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            expected_instance = MagicMock()
            mock_api.return_value = expected_instance

            result = create_dmarket_api_client(None)

            assert result is expected_instance

    def test_create_dmarket_api_client_with_partial_context_keys(self):
        """Test create_dmarket_api_client with only public key in context."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        mock_context = MagicMock()
        mock_context.bot_data = {
            "DMARKET_PUBLIC_KEY": "context_public",
            # Missing secret key
        }

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_SECRET_KEY": "env_secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            create_dmarket_api_client(mock_context)

            call_kwargs = mock_api.call_args[1]
            assert call_kwargs["public_key"] == "context_public"
            assert call_kwargs["secret_key"] == "env_secret"


class TestLogging:
    """Tests for logging behavior."""

    def test_logs_warning_when_public_key_missing(self):
        """Test logs warning when public key is missing."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with patch.dict(os.environ, {}, clear=True):
            with patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api:
                mock_api.return_value = MagicMock()

                with patch("src.telegram_bot.utils.api_helper.logger") as mock_logger:
                    create_dmarket_api_client(None)

                    # Should log warning about missing key
                    mock_logger.warning.assert_called()

    def test_logs_warning_when_secret_key_missing(self):
        """Test logs warning when secret key is missing."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {"DMARKET_PUBLIC_KEY": "public"},
                clear=True,
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            with patch("src.telegram_bot.utils.api_helper.logger") as mock_logger:
                create_dmarket_api_client(None)

                # Should log warning about missing secret key
                assert mock_logger.warning.called

    def test_logs_debug_when_public_key_present(self):
        """Test logs debug when public key is present."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with (
            patch.dict(
                os.environ,
                {
                    "DMARKET_PUBLIC_KEY": "abcd1234efgh",
                    "DMARKET_SECRET_KEY": "secret",
                },
            ),
            patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api,
        ):
            mock_api.return_value = MagicMock()

            with patch("src.telegram_bot.utils.api_helper.logger") as mock_logger:
                create_dmarket_api_client(None)

                # Should log debug about the key
                assert mock_logger.debug.called


class TestModuleIntegration:
    """Integration tests for the module."""

    def test_module_can_be_imported(self):
        """Test module can be imported without errors."""
        from src.telegram_bot.utils import api_helper

        assert hasattr(api_helper, "create_dmarket_api_client")

    def test_function_signature_accepts_none_context(self):
        """Test function accepts None as context parameter."""
        from src.telegram_bot.utils.api_helper import create_dmarket_api_client

        with patch("src.telegram_bot.utils.api_helper.DMarketAPI") as mock_api:
            mock_api.return_value = MagicMock()

            # Should not raise
            result = create_dmarket_api_client(None)

            assert result is not None
