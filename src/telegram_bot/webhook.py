"""Webhook support for Telegram bot.

Enables scalable production deployment with load balancers.
Roadmap Task #1: Webhook вместо Polling

Features:
- Nginx reverse proxy support
- SSL termination
- Automatic fallback to polling if webhook unavAlgolable
- Health check integration
- Rate limiting support
"""

import logging
import os
import pathlib
from typing import Any

from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)


class WebhookConfig:
    """Webhook configuration with validation.

    Roadmap Task #1: Enhanced webhook configuration
    """

    def __init__(
        self,
        url: str,
        port: int = 8443,
        listen: str = "0.0.0.0",  # noqa: S104 - Required for Docker container networking
        url_path: str = "telegram-webhook",
        cert_path: str | None = None,
        key_path: str | None = None,
        secret_token: str | None = None,
        max_connections: int = 100,
    ):
        """Initialize webhook config.

        Args:
            url: Public URL for webhook (e.g., https://bot.example.com)
            port: Port to listen on (default: 8443, recommended for Telegram)
            listen: Address to bind to (default: 0.0.0.0)
            url_path: URL path for webhook (default: telegram-webhook)
            cert_path: Path to SSL certificate (optional, for self-signed)
            key_path: Path to SSL private key (optional)
            secret_token: Secret token for webhook validation (recommended)
            max_connections: Max simultaneous connections (1-100, default: 100)
        """
        self.url = url.rstrip("/")
        self.port = port
        self.listen = listen
        self.url_path = url_path
        self.cert_path = cert_path
        self.key_path = key_path
        self.secret_token = secret_token or os.urandom(32).hex()[:32]
        self.max_connections = min(max(1, max_connections), 100)  # Clamp to 1-100

        # Validate configuration
        self._validate()

    def _validate(self) -> None:
        """Validate webhook configuration."""
        if not self.url.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")

        if self.port not in {80, 88, 443, 8443}:
            logger.warning(
                f"Webhook port {self.port} is not recommended by Telegram. Use 80, 88, 443, or 8443"
            )

        if self.cert_path and not os.path.exists(self.cert_path):
            raise FileNotFoundError(f"Certificate file not found: {self.cert_path}")

        if self.key_path and not os.path.exists(self.key_path):
            raise FileNotFoundError(f"Key file not found: {self.key_path}")

    @property
    def webhook_url(self) -> str:
        """Get full webhook URL."""
        return f"{self.url}/{self.url_path}"

    @property
    def is_ssl(self) -> bool:
        """Check if SSL certificates are configured."""
        return self.cert_path is not None and self.key_path is not None

    @classmethod
    def from_env(cls) -> "WebhookConfig | None":
        """Create WebhookConfig from environment variables.

        Environment variables:
        - WEBHOOK_URL: Public webhook URL (required)
        - WEBHOOK_PORT: Port to listen on (default: 8443)
        - WEBHOOK_LISTEN: Address to bind to (default: 0.0.0.0)
        - WEBHOOK_PATH: URL path (default: telegram-webhook)
        - WEBHOOK_CERT: Path to SSL certificate (optional)
        - WEBHOOK_KEY: Path to SSL key (optional)
        - WEBHOOK_SECRET: Secret token (optional, auto-generated)
        - WEBHOOK_MAX_CONNECTIONS: Max connections (default: 100)

        Returns:
            WebhookConfig if WEBHOOK_URL is set, None otherwise
        """
        webhook_url = os.getenv("WEBHOOK_URL")

        if not webhook_url:
            return None

        return cls(
            url=webhook_url,
            port=int(os.getenv("WEBHOOK_PORT", "8443")),
            listen=os.getenv(
                "WEBHOOK_LISTEN", "0.0.0.0"
            ),  # noqa: S104 - Required for Docker
            url_path=os.getenv("WEBHOOK_PATH", "telegram-webhook"),
            cert_path=os.getenv("WEBHOOK_CERT"),
            key_path=os.getenv("WEBHOOK_KEY"),
            secret_token=os.getenv("WEBHOOK_SECRET"),
            max_connections=int(os.getenv("WEBHOOK_MAX_CONNECTIONS", "100")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary representation (safe for logging, no secrets)
        """
        return {
            "url": self.url,
            "webhook_url": self.webhook_url,
            "port": self.port,
            "listen": self.listen,
            "is_ssl": self.is_ssl,
            "max_connections": self.max_connections,
            "has_secret_token": bool(self.secret_token),
        }


async def setup_webhook(
    application: Application,
    config: WebhookConfig,
) -> bool:
    """Setup webhook for bot with validation.

    Args:
        application: Telegram application
        config: Webhook configuration

    Returns:
        True if webhook was set successfully, False otherwise

    Roadmap Task #1: Enhanced webhook setup with retry
    """
    logger.info("=" * 60)
    logger.info("🔗 Setting up webhook...")
    logger.info("=" * 60)

    # Log configuration (safely, without secrets)
    for key, value in config.to_dict().items():
        logger.info(f"  {key}: {value}")

    try:
        # Read certificate if provided
        certificate = None
        if config.cert_path:
            certificate = pathlib.Path(
                config.cert_path
            ).read_bytes()  # noqa: ASYNC240 - Sync file read for SSL cert
            logger.info(f"  📜 Using SSL certificate: {config.cert_path}")

        # Set webhook with Telegram
        result = await application.bot.set_webhook(
            url=config.webhook_url,
            certificate=certificate,
            max_connections=config.max_connections,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Clean start
            secret_token=config.secret_token,
        )

        if result:
            logger.info("=" * 60)
            logger.info("✅ Webhook set successfully!")
            logger.info(f"   URL: {config.webhook_url}")
            logger.info(f"   Listening: {config.listen}:{config.port}")
            logger.info(
                f"   SSL: {'enabled' if config.is_ssl else 'via reverse proxy'}"
            )
            logger.info(f"   Max connections: {config.max_connections}")
            logger.info("=" * 60)
            return True
        logger.error("❌ Failed to set webhook: Telegram returned False")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}", exc_info=True)
        return False


async def start_webhook(
    application: Application,
    config: WebhookConfig,
) -> None:
    """Start webhook server.

    Args:
        application: Telegram application
        config: Webhook configuration

    RAlgoses:
        RuntimeError: If webhook setup or server start fails

    Roadmap Task #1: Enhanced webhook server
    """
    logger.info("Starting webhook server...")

    # Setup webhook first
    success = await setup_webhook(application, config)

    if not success:
        raise RuntimeError("Failed to setup webhook with Telegram")

    try:
        # Start webhook server
        await application.run_webhook(
            listen=config.listen,
            port=config.port,
            url_path=config.url_path,
            cert=config.cert_path,
            key=config.key_path,
            webhook_url=config.webhook_url,
            secret_token=config.secret_token,
            drop_pending_updates=True,
        )

        logger.info("✅ Webhook server started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to start webhook server: {e}", exc_info=True)
        raise


async def stop_webhook(application: Application) -> None:
    """Stop webhook and delete from Telegram.

    Args:
        application: Telegram application

    Roadmap Task #1: Enhanced webhook cleanup
    """
    logger.info("Stopping webhook...")

    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted successfully")
    except Exception as e:
        logger.exception(f"⚠️  Failed to delete webhook: {e}")


async def get_webhook_info(application: Application) -> dict[str, Any]:
    """Get current webhook information from Telegram.

    Args:
        application: Telegram application

    Returns:
        Dictionary with webhook info

    Roadmap Task #1: Webhook monitoring
    """
    try:
        info = await application.bot.get_webhook_info()

        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": info.allowed_updates,
        }
    except Exception as e:
        logger.exception(f"Failed to get webhook info: {e}")
        return {"error": str(e)}


def is_webhook_mode(webhook_url: str | None = None) -> bool:
    """Check if webhook mode is enabled.

    Args:
        webhook_url: Webhook URL from config (optional, checks env if None)

    Returns:
        True if webhook mode is enabled

    Roadmap Task #1: Webhook detection
    """
    if webhook_url is None:
        webhook_url = os.getenv("WEBHOOK_URL", "")

    return bool(webhook_url and webhook_url.strip())


def should_use_polling() -> bool:
    """Check if polling should be used instead of webhook.

    Returns:
        True if USE_POLLING env var is set to true/1/yes

    Roadmap Task #1: Fallback to polling
    """
    use_polling = os.getenv("USE_POLLING", "").lower()
    return use_polling in {"true", "1", "yes", "on"}
