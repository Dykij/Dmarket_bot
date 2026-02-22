"""Tests for webhook configuration and setup (Roadmap Task #1).

Tests webhook configuration, SSL validation, and fallback to polling.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.webhook import (
    WebhookConfig,
    get_webhook_info,
    is_webhook_mode,
    setup_webhook,
    should_use_polling,
    stop_webhook,
)

# ============================================================================
# Tests: WebhookConfig
# ============================================================================


def test_webhook_config_initialization():
    """Test WebhookConfig initializes correctly."""
    config = WebhookConfig(
        url="https://bot.example.com",
        port=8443,
        url_path="telegram-webhook",
    )

    assert config.url == "https://bot.example.com"
    assert config.port == 8443
    assert config.webhook_url == "https://bot.example.com/telegram-webhook"
    assert not config.is_ssl  # No cert/key provided


def test_webhook_config_strips_trailing_slash():
    """Test WebhookConfig strips trailing slash from URL."""
    config = WebhookConfig(url="https://bot.example.com/")

    assert config.url == "https://bot.example.com"
    assert config.webhook_url == "https://bot.example.com/telegram-webhook"


def test_webhook_config_with_ssl():
    """Test WebhookConfig with SSL certificates."""
    # Create temporary cert files for testing
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False) as cert_file:
        cert_path = cert_file.name
        cert_file.write(b"fake cert")

    with tempfile.NamedTemporaryFile(delete=False) as key_file:
        key_path = key_file.name
        key_file.write(b"fake key")

    try:
        config = WebhookConfig(
            url="https://bot.example.com",
            cert_path=cert_path,
            key_path=key_path,
        )

        assert config.is_ssl
        assert config.cert_path == cert_path
        assert config.key_path == key_path
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)


def test_webhook_config_validates_https():
    """Test WebhookConfig requires HTTPS."""
    with pytest.raises(ValueError, match="must use HTTPS"):
        WebhookConfig(url="http://bot.example.com")


def test_webhook_config_max_connections_clamped():
    """Test max_connections is clamped to 1-100."""
    config1 = WebhookConfig(url="https://bot.example.com", max_connections=0)
    assert config1.max_connections == 1

    config2 = WebhookConfig(url="https://bot.example.com", max_connections=200)
    assert config2.max_connections == 100

    config3 = WebhookConfig(url="https://bot.example.com", max_connections=50)
    assert config3.max_connections == 50


def test_webhook_config_from_env():
    """Test WebhookConfig.from_env() creates config from environment."""
    with patch.dict(
        os.environ,
        {
            "WEBHOOK_URL": "https://bot.example.com",
            "WEBHOOK_PORT": "443",
            "WEBHOOK_PATH": "my-webhook",
        },
    ):
        config = WebhookConfig.from_env()

        assert config is not None
        assert config.url == "https://bot.example.com"
        assert config.port == 443
        assert config.url_path == "my-webhook"


def test_webhook_config_from_env_returns_none_if_no_url():
    """Test WebhookConfig.from_env() returns None if WEBHOOK_URL not set."""
    with patch.dict(os.environ, {}, clear=True):
        config = WebhookConfig.from_env()
        assert config is None


def test_webhook_config_to_dict():
    """Test WebhookConfig.to_dict() returns safe representation."""
    config = WebhookConfig(
        url="https://bot.example.com",
        port=8443,
        secret_token="my-secret",
    )

    data = config.to_dict()

    assert data["url"] == "https://bot.example.com"
    assert data["port"] == 8443
    assert data["has_secret_token"] is True
    assert "secret_token" not in data  # Secret not exposed


# ============================================================================
# Tests: Webhook Setup
# ============================================================================


@pytest.mark.asyncio()
async def test_setup_webhook_success():
    """Test setup_webhook successfully sets webhook."""
    mock_app = MagicMock()
    mock_app.bot.set_webhook = AsyncMock(return_value=True)

    config = WebhookConfig(url="https://bot.example.com")

    result = await setup_webhook(mock_app, config)

    assert result is True
    mock_app.bot.set_webhook.assert_called_once()

    # Check arguments
    call_kwargs = mock_app.bot.set_webhook.call_args.kwargs
    assert call_kwargs["url"] == "https://bot.example.com/telegram-webhook"
    assert call_kwargs["drop_pending_updates"] is True


@pytest.mark.asyncio()
async def test_setup_webhook_failure():
    """Test setup_webhook handles failure gracefully."""
    mock_app = MagicMock()
    mock_app.bot.set_webhook = AsyncMock(side_effect=Exception("API Error"))

    config = WebhookConfig(url="https://bot.example.com")

    result = await setup_webhook(mock_app, config)

    assert result is False


@pytest.mark.asyncio()
async def test_stop_webhook():
    """Test stop_webhook deletes webhook."""
    mock_app = MagicMock()
    mock_app.bot.delete_webhook = AsyncMock()

    await stop_webhook(mock_app)

    mock_app.bot.delete_webhook.assert_called_once_with(drop_pending_updates=True)


@pytest.mark.asyncio()
async def test_get_webhook_info():
    """Test get_webhook_info returns webhook information."""
    mock_info = MagicMock()
    mock_info.url = "https://bot.example.com/webhook"
    mock_info.has_custom_certificate = False
    mock_info.pending_update_count = 5
    mock_info.last_error_date = None
    mock_info.last_error_message = None
    mock_info.max_connections = 100
    mock_info.allowed_updates = None

    mock_app = MagicMock()
    mock_app.bot.get_webhook_info = AsyncMock(return_value=mock_info)

    info = await get_webhook_info(mock_app)

    assert info["url"] == "https://bot.example.com/webhook"
    assert info["pending_update_count"] == 5
    assert info["max_connections"] == 100


# ============================================================================
# Tests: Webhook Mode Detection
# ============================================================================


def test_is_webhook_mode_with_url():
    """Test is_webhook_mode returns True when URL is set."""
    assert is_webhook_mode("https://bot.example.com") is True


def test_is_webhook_mode_without_url():
    """Test is_webhook_mode returns False when URL is empty."""
    assert is_webhook_mode("") is False
    assert is_webhook_mode(None) is False
    assert is_webhook_mode("   ") is False


def test_is_webhook_mode_from_env():
    """Test is_webhook_mode checks environment if URL not provided."""
    with patch.dict(os.environ, {"WEBHOOK_URL": "https://bot.example.com"}):
        assert is_webhook_mode() is True

    with patch.dict(os.environ, {}, clear=True):
        assert is_webhook_mode() is False


def test_should_use_polling():
    """Test should_use_polling checks USE_POLLING environment variable."""
    with patch.dict(os.environ, {"USE_POLLING": "true"}):
        assert should_use_polling() is True

    with patch.dict(os.environ, {"USE_POLLING": "1"}):
        assert should_use_polling() is True

    with patch.dict(os.environ, {"USE_POLLING": "yes"}):
        assert should_use_polling() is True

    with patch.dict(os.environ, {"USE_POLLING": "false"}):
        assert should_use_polling() is False

    with patch.dict(os.environ, {}, clear=True):
        assert should_use_polling() is False


# ============================================================================
# Tests: Edge Cases
# ============================================================================


def test_webhook_config_secret_token_auto_generated():
    """Test secret_token is auto-generated if not provided."""
    config = WebhookConfig(url="https://bot.example.com")

    assert config.secret_token is not None
    assert len(config.secret_token) > 0


def test_webhook_config_warns_on_non_standard_port(caplog):
    """Test WebhookConfig warns on non-standard ports."""
    import logging

    with caplog.at_level(logging.WARNING):
        WebhookConfig(url="https://bot.example.com", port=9000)

    assert "not recommended" in caplog.text


def test_webhook_config_file_not_found():
    """Test WebhookConfig raises error if cert/key files don't exist."""
    with pytest.raises(FileNotFoundError):
        WebhookConfig(
            url="https://bot.example.com",
            cert_path="/nonexistent/cert.pem",
        )

    with pytest.raises(FileNotFoundError):
        WebhookConfig(
            url="https://bot.example.com",
            key_path="/nonexistent/key.pem",
        )


# ============================================================================
# Tests: Additional Coverage for 90%+
# ============================================================================


@pytest.mark.asyncio()
async def test_setup_webhook_with_certificate():
    """Test setup_webhook with SSL certificate."""
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
        cert_path = cert_file.name
        cert_file.write(b"-----BEGIN CERTIFICATE-----\nfake cert\n-----END CERTIFICATE-----")

    try:
        mock_app = MagicMock()
        mock_app.bot.set_webhook = AsyncMock(return_value=True)

        config = WebhookConfig(
            url="https://bot.example.com",
            cert_path=cert_path,
        )

        result = await setup_webhook(mock_app, config)

        assert result is True
        mock_app.bot.set_webhook.assert_called_once()

        # Verify certificate was passed
        call_kwargs = mock_app.bot.set_webhook.call_args.kwargs
        assert call_kwargs["certificate"] is not None
    finally:
        os.unlink(cert_path)


@pytest.mark.asyncio()
async def test_setup_webhook_returns_false_when_telegram_returns_false():
    """Test setup_webhook returns False when Telegram API returns False."""
    mock_app = MagicMock()
    mock_app.bot.set_webhook = AsyncMock(return_value=False)

    config = WebhookConfig(url="https://bot.example.com")

    result = await setup_webhook(mock_app, config)

    assert result is False


@pytest.mark.asyncio()
async def test_stop_webhook_handles_errors():
    """Test stop_webhook handles deletion errors gracefully."""
    mock_app = MagicMock()
    mock_app.bot.delete_webhook = AsyncMock(side_effect=Exception("API Error"))

    # Should not raise exception
    await stop_webhook(mock_app)


@pytest.mark.asyncio()
async def test_get_webhook_info_handles_errors():
    """Test get_webhook_info handles API errors."""
    mock_app = MagicMock()
    mock_app.bot.get_webhook_info = AsyncMock(side_effect=Exception("API Error"))

    info = await get_webhook_info(mock_app)

    assert "error" in info
    assert info["error"] == "API Error"


@pytest.mark.asyncio()
async def test_start_webhook_raises_on_setup_failure():
    """Test start_webhook raises RuntimeError if webhook setup fails."""
    from src.telegram_bot.webhook import start_webhook

    mock_app = MagicMock()
    mock_app.bot.set_webhook = AsyncMock(return_value=False)

    config = WebhookConfig(url="https://bot.example.com")

    with pytest.raises(RuntimeError, match="Failed to setup webhook"):
        await start_webhook(mock_app, config)


@pytest.mark.asyncio()
async def test_start_webhook_raises_on_server_start_failure():
    """Test start_webhook raises exception if server fails to start."""
    from src.telegram_bot.webhook import start_webhook

    mock_app = MagicMock()
    mock_app.bot.set_webhook = AsyncMock(return_value=True)
    mock_app.run_webhook = AsyncMock(side_effect=Exception("Server start failed"))

    config = WebhookConfig(url="https://bot.example.com")

    with pytest.raises(Exception, match="Server start failed"):
        await start_webhook(mock_app, config)


def test_webhook_config_from_env_with_all_parameters():
    """Test WebhookConfig.from_env() with all environment variables."""
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as cert_file:
        cert_path = cert_file.name
        cert_file.write(b"fake cert")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as key_file:
        key_path = key_file.name
        key_file.write(b"fake key")

    try:
        with patch.dict(
            os.environ,
            {
                "WEBHOOK_URL": "https://bot.example.com",
                "WEBHOOK_PORT": "443",
                "WEBHOOK_LISTEN": "127.0.0.1",
                "WEBHOOK_PATH": "custom-webhook",
                "WEBHOOK_CERT": cert_path,
                "WEBHOOK_KEY": key_path,
                "WEBHOOK_SECRET": "my-secret-token",
                "WEBHOOK_MAX_CONNECTIONS": "50",
            },
        ):
            config = WebhookConfig.from_env()

            assert config is not None
            assert config.url == "https://bot.example.com"
            assert config.port == 443
            assert config.listen == "127.0.0.1"
            assert config.url_path == "custom-webhook"
            assert config.cert_path == cert_path
            assert config.key_path == key_path
            assert config.secret_token == "my-secret-token"
            assert config.max_connections == 50
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)


def test_should_use_polling_with_on():
    """Test should_use_polling with 'on' value."""
    with patch.dict(os.environ, {"USE_POLLING": "on"}):
        assert should_use_polling() is True


def test_webhook_config_custom_secret_token():
    """Test WebhookConfig with custom secret token."""
    config = WebhookConfig(
        url="https://bot.example.com",
        secret_token="my-custom-token-12345678901234567890",
    )

    assert config.secret_token == "my-custom-token-12345678901234567890"
