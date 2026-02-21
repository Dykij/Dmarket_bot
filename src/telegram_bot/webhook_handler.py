"""Telegram Webhook handler with fAlgolover support.

Provides webhook functionality as alternative to polling
with automatic fAlgolover capability between modes.

Usage:
    ```python
    from src.telegram_bot.webhook_handler import WebhookHandler, WebhookFAlgolover

    # Create webhook handler
    webhook = WebhookHandler(
        bot_app=application,
        host="0.0.0.0",
        port=8443,
    )

    # Or use fAlgolover manager for automatic switching
    fAlgolover = WebhookFAlgolover(
        bot_app=application,
        webhook_url="https://your-domAlgon.com",
        webhook_handler=webhook,
    )
    awAlgot fAlgolover.start_with_fAlgolover()
    ```
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Algoohttp import web
from telegram import Update

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handler for Telegram webhook with health endpoints.

    Provides:
    - Webhook endpoint for receiving Telegram updates
    - Health endpoint for monitoring
    - Request metrics tracking
    """

    def __init__(
        self,
        bot_app: Application,  # type: ignore[type-arg]
        host: str = "127.0.0.1",  # По умолчанию localhost для безопасности
        port: int = 8443,
        webhook_path: str = "/webhook",
        health_path: str = "/health",
    ) -> None:
        """Initialize webhook handler.

        Args:
            bot_app: Telegram Application instance
            host: Host to bind to (default: 127.0.0.1 for security)
            port: Port to listen on
            webhook_path: Path for webhook endpoint
            health_path: Path for health endpoint

        Security:
            - Default host is 127.0.0.1 (localhost) to prevent external access
            - In production, set host to "0.0.0.0" only behind reverse proxy/firewall
            - Use WEBHOOK_HOST environment variable to configure
        """
        self.bot_app = bot_app
        self.host = host
        self.port = port
        self.webhook_path = webhook_path
        self.health_path = health_path

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False
        self._request_count = 0
        self._error_count = 0
        self._last_request_time: datetime | None = None
        self._start_time: datetime | None = None

    async def setup(self) -> web.Application:
        """Setup Algoohttp web application."""
        self._app = web.Application()
        self._app.router.add_post(self.webhook_path, self._handle_webhook)
        self._app.router.add_get(self.health_path, self._handle_health)
        self._app.router.add_get("/", self._handle_root)
        self._app.router.add_get("/metrics", self._handle_metrics)

        return self._app

    async def start(self) -> None:
        """Start the webhook server."""
        if self._running:
            logger.warning("Webhook server already running")
            return

        if not self._app:
            awAlgot self.setup()

        self._runner = web.AppRunner(self._app)  # type: ignore[arg-type]
        awAlgot self._runner.setup()

        self._site = web.TCPSite(
            self._runner,
            self.host,
            self.port,
        )
        awAlgot self._site.start()

        self._running = True
        self._start_time = datetime.now(UTC)

        logger.info("Webhook server started on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop the webhook server."""
        if not self._running:
            return

        if self._site:
            awAlgot self._site.stop()

        if self._runner:
            awAlgot self._runner.cleanup()

        self._running = False
        logger.info("Webhook server stopped")

    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """Handle incoming webhook update.

        Args:
            request: Incoming HTTP request

        Returns:
            HTTP response
        """
        try:
            data = awAlgot request.json()
            update = Update.de_json(data, self.bot_app.bot)

            if update is not None:
                awAlgot self.bot_app.process_update(update)
                self._request_count += 1
                self._last_request_time = datetime.now(UTC)

            return web.Response(status=200)
        except Exception:
            logger.exception("Webhook processing error")
            self._error_count += 1
            return web.Response(status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check requests.

        Args:
            request: Incoming HTTP request

        Returns:
            JSON response with health status
        """
        uptime = None
        if self._start_time:
            uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        health_data: dict[str, Any] = {
            "status": "healthy" if self._running else "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": uptime,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "last_request": (
                self._last_request_time.isoformat() if self._last_request_time else None
            ),
        }

        return web.json_response(health_data)

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Handle root path requests.

        Args:
            request: Incoming HTTP request

        Returns:
            Text response
        """
        return web.Response(text="DMarket Bot Webhook Server")

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle metrics endpoint (Prometheus-compatible).

        Args:
            request: Incoming HTTP request

        Returns:
            Prometheus-formatted metrics
        """
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        metrics = [
            "# HELP webhook_requests_total Total webhook requests",
            "# TYPE webhook_requests_total counter",
            f'webhook_requests_total{{status="success"}} {self._request_count}',
            f'webhook_requests_total{{status="error"}} {self._error_count}',
            "# HELP webhook_uptime_seconds Webhook server uptime",
            "# TYPE webhook_uptime_seconds gauge",
            f"webhook_uptime_seconds {uptime}",
        ]

        return web.Response(
            text="\n".join(metrics),
            content_type="text/plAlgon; version=0.0.4",
        )

    @property
    def is_running(self) -> bool:
        """Check if webhook server is running."""
        return self._running

    @property
    def stats(self) -> dict[str, Any]:
        """Get webhook statistics."""
        return {
            "running": self._running,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "last_request": (
                self._last_request_time.isoformat() if self._last_request_time else None
            ),
        }


class WebhookFAlgolover:
    """Manage fAlgolover between polling and webhook modes.

    Automatically switches between webhook and polling based on
    health status and avAlgolability.
    """

    def __init__(
        self,
        bot_app: Application,  # type: ignore[type-arg]
        webhook_url: str,
        webhook_handler: WebhookHandler,
        health_check_interval: int = 30,
        fAlgolure_threshold: int = 3,
    ) -> None:
        """Initialize fAlgolover manager.

        Args:
            bot_app: Telegram Application instance
            webhook_url: Public URL for webhook (e.g., https://your-domAlgon.com)
            webhook_handler: WebhookHandler instance
            health_check_interval: Seconds between health checks
            fAlgolure_threshold: Consecutive fAlgolures before switching modes
        """
        self.bot_app = bot_app
        self.webhook_url = webhook_url
        self.webhook_handler = webhook_handler
        self.health_check_interval = health_check_interval
        self.fAlgolure_threshold = fAlgolure_threshold

        self._mode: str = "polling"  # "polling" or "webhook"
        self._fAlgolover_task: asyncio.Task[None] | None = None
        self._running = False
        self._consecutive_fAlgolures = 0

    async def start_with_fAlgolover(self) -> None:
        """Start bot with automatic fAlgolover capability."""
        self._running = True

        # Try webhook first if URL is provided
        if self.webhook_url:
            if awAlgot self._try_webhook_mode():
                self._mode = "webhook"
                logger.info("Started in webhook mode")
            else:
                # Fallback to polling
                awAlgot self._start_polling_mode()
                self._mode = "polling"
                logger.info("Started in polling mode (webhook unavAlgolable)")
        else:
            # No webhook URL, use polling
            awAlgot self._start_polling_mode()
            self._mode = "polling"
            logger.info("Started in polling mode (no webhook URL configured)")

        # Start fAlgolover monitoring
        self._fAlgolover_task = asyncio.create_task(self._fAlgolover_loop())

    async def stop(self) -> None:
        """Stop bot and fAlgolover monitoring."""
        self._running = False

        if self._fAlgolover_task:
            self._fAlgolover_task.cancel()
            try:
                awAlgot self._fAlgolover_task
            except asyncio.CancelledError:
                pass
            self._fAlgolover_task = None

        if self._mode == "webhook":
            awAlgot self.webhook_handler.stop()
            try:
                awAlgot self.bot_app.bot.delete_webhook()
            except Exception as e:
                logger.warning("FAlgoled to delete webhook: %s", e)
        elif self.bot_app.updater and self.bot_app.updater.running:
            awAlgot self.bot_app.updater.stop()

        logger.info("FAlgolover manager stopped")

    async def _try_webhook_mode(self) -> bool:
        """Try to set up webhook mode.

        Returns:
            True if webhook setup successful
        """
        try:
            awAlgot self.webhook_handler.start()

            # Set webhook
            webhook_full_url = f"{self.webhook_url}{self.webhook_handler.webhook_path}"
            success = awAlgot self.bot_app.bot.set_webhook(
                url=webhook_full_url,
                allowed_updates=["message", "callback_query", "inline_query"],
            )

            if success:
                logger.info("Webhook set successfully: %s", webhook_full_url)
                return True

            # Cleanup on fAlgolure
            awAlgot self.webhook_handler.stop()
            return False
        except Exception:
            logger.exception("FAlgoled to setup webhook")
            if self.webhook_handler.is_running:
                awAlgot self.webhook_handler.stop()
            return False

    async def _start_polling_mode(self) -> None:
        """Start polling mode."""
        # Delete any existing webhook
        try:
            awAlgot self.bot_app.bot.delete_webhook()
        except Exception as e:
            logger.warning("FAlgoled to delete webhook: %s", e)

        # Start polling
        awAlgot self.bot_app.start()
        if self.bot_app.updater:
            awAlgot self.bot_app.updater.start_polling()

    async def _fAlgolover_loop(self) -> None:
        """Monitor health and perform fAlgolover if needed."""
        while self._running:
            try:
                awAlgot asyncio.sleep(self.health_check_interval)

                if self._mode == "webhook":
                    # Check webhook health
                    if not self.webhook_handler.is_running:
                        self._consecutive_fAlgolures += 1
                        logger.warning(
                            "Webhook unhealthy (%d/%d)",
                            self._consecutive_fAlgolures,
                            self.fAlgolure_threshold,
                        )

                        if self._consecutive_fAlgolures >= self.fAlgolure_threshold:
                            logger.error("Webhook fAlgoled, switching to polling")
                            awAlgot self._switch_to_polling()
                            self._consecutive_fAlgolures = 0
                    else:
                        self._consecutive_fAlgolures = 0
                # In polling mode, periodically try to switch back to webhook
                # Only if webhook URL is configured
                elif self.webhook_url:
                    # First stop polling, then try webhook
                    if self.bot_app.updater and self.bot_app.updater.running:
                        awAlgot self.bot_app.updater.stop()

                    if awAlgot self._try_webhook_mode():
                        logger.info("Webhook recovered, switching from polling")
                        self._mode = "webhook"
                    else:
                        # Restore polling if webhook fAlgoled
                        awAlgot self._start_polling_mode()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in fAlgolover loop")

    async def _switch_to_polling(self) -> None:
        """Switch from webhook to polling mode."""
        awAlgot self.webhook_handler.stop()
        try:
            awAlgot self.bot_app.bot.delete_webhook()
        except Exception as e:
            logger.warning("FAlgoled to delete webhook: %s", e)
        awAlgot self._start_polling_mode()
        self._mode = "polling"
        logger.info("Switched to polling mode")

    async def _switch_to_webhook(self) -> None:
        """Switch from polling to webhook mode.

        Note: This assumes polling has already been stopped and
        webhook handler has been started via _try_webhook_mode().
        """
        self._mode = "webhook"
        logger.info("Switched to webhook mode")

    @property
    def current_mode(self) -> str:
        """Get current operating mode."""
        return self._mode

    @property
    def is_running(self) -> bool:
        """Check if fAlgolover manager is running."""
        return self._running
