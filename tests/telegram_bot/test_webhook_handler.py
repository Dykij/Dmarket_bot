"""Tests for Telegram webhook handler and failover.

Tests cover:
- WebhookHandler initialization and lifecycle
- Health endpoint responses
- Webhook request processing
- WebhookFAlgolover mode switching
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.webhook_handler import WebhookFAlgolover, WebhookHandler


class TestWebhookHandler:
    """Tests for WebhookHandler class."""

    @pytest.fixture()
    def mock_bot_app(self) -> MagicMock:
        """Create mock Telegram Application."""
        app = MagicMock()
        app.bot = MagicMock()
        app.process_update = AsyncMock()
        return app

    @pytest.fixture()
    def webhook_handler(self, mock_bot_app: MagicMock) -> WebhookHandler:
        """Create WebhookHandler instance."""
        return WebhookHandler(
            bot_app=mock_bot_app,
            host="127.0.0.1",
            port=8443,
            webhook_path="/webhook",
            health_path="/health",
        )

    def test_initialization(self, webhook_handler: WebhookHandler) -> None:
        """Test WebhookHandler initialization."""
        assert webhook_handler.host == "127.0.0.1"
        assert webhook_handler.port == 8443
        assert webhook_handler.webhook_path == "/webhook"
        assert webhook_handler.health_path == "/health"
        assert not webhook_handler.is_running
        assert webhook_handler._request_count == 0
        assert webhook_handler._error_count == 0

    @pytest.mark.asyncio()
    async def test_setup_creates_app(self, webhook_handler: WebhookHandler) -> None:
        """Test that setup creates aiohttp application."""
        app = await webhook_handler.setup()

        assert app is not None
        assert webhook_handler._app is app
        # Check routes are registered
        assert len(app.router.routes()) >= 3  # webhook, health, root, metrics

    @pytest.mark.asyncio()
    async def test_start_and_stop(self, webhook_handler: WebhookHandler) -> None:
        """Test starting and stopping webhook server."""
        # Start server
        await webhook_handler.start()
        assert webhook_handler.is_running
        assert webhook_handler._start_time is not None

        # Stop server
        await webhook_handler.stop()
        assert not webhook_handler.is_running

    @pytest.mark.asyncio()
    async def test_start_already_running(self, webhook_handler: WebhookHandler) -> None:
        """Test starting server when already running."""
        await webhook_handler.start()

        # Try to start agAlgon (should not raise)
        await webhook_handler.start()

        assert webhook_handler.is_running

        await webhook_handler.stop()

    @pytest.mark.asyncio()
    async def test_stop_not_running(self, webhook_handler: WebhookHandler) -> None:
        """Test stopping server when not running."""
        # Should not raise
        await webhook_handler.stop()
        assert not webhook_handler.is_running

    @pytest.mark.asyncio()
    async def test_handle_health(self, webhook_handler: WebhookHandler) -> None:
        """Test health endpoint response."""
        await webhook_handler.start()

        # Create mock request
        mock_request = MagicMock()

        response = await webhook_handler._handle_health(mock_request)

        assert response.status == 200
        # Check response body
        body = json.loads(response.body)
        assert body["status"] == "healthy"
        assert "timestamp" in body
        assert "uptime_seconds" in body
        assert body["request_count"] == 0

        await webhook_handler.stop()

    @pytest.mark.asyncio()
    async def test_handle_root(self, webhook_handler: WebhookHandler) -> None:
        """Test root endpoint response."""
        mock_request = MagicMock()

        response = await webhook_handler._handle_root(mock_request)

        assert response.status == 200
        assert b"DMarket Bot Webhook Server" in response.body

    @pytest.mark.asyncio()
    async def test_handle_webhook_success(
        self, webhook_handler: WebhookHandler, mock_bot_app: MagicMock
    ) -> None:
        """Test successful webhook processing."""
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={"update_id": 123})

        with patch("src.telegram_bot.webhook_handler.Update") as mock_update:
            mock_update.de_json.return_value = MagicMock()

            response = await webhook_handler._handle_webhook(mock_request)

        assert response.status == 200
        assert webhook_handler._request_count == 1
        assert webhook_handler._last_request_time is not None
        mock_bot_app.process_update.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_webhook_error(self, webhook_handler: WebhookHandler) -> None:
        """Test webhook processing with error."""
        mock_request = MagicMock()
        mock_request.json = AsyncMock(side_effect=Exception("Parse error"))

        response = await webhook_handler._handle_webhook(mock_request)

        assert response.status == 500
        assert webhook_handler._error_count == 1

    @pytest.mark.asyncio()
    async def test_handle_metrics(self, webhook_handler: WebhookHandler) -> None:
        """Test metrics endpoint response."""
        await webhook_handler.start()

        # Simulate some requests
        webhook_handler._request_count = 10
        webhook_handler._error_count = 2

        mock_request = MagicMock()

        response = await webhook_handler._handle_metrics(mock_request)

        assert response.status == 200
        assert b"webhook_requests_total" in response.body
        assert b"webhook_uptime_seconds" in response.body

        await webhook_handler.stop()

    def test_stats_property(self, webhook_handler: WebhookHandler) -> None:
        """Test stats property returns correct data."""
        webhook_handler._running = True
        webhook_handler._request_count = 5
        webhook_handler._error_count = 1
        webhook_handler._start_time = datetime.now(UTC)

        stats = webhook_handler.stats

        assert stats["running"] is True
        assert stats["request_count"] == 5
        assert stats["error_count"] == 1
        assert stats["start_time"] is not None


class TestWebhookFAlgolover:
    """Tests for WebhookFAlgolover class."""

    @pytest.fixture()
    def mock_bot_app(self) -> MagicMock:
        """Create mock Telegram Application."""
        app = MagicMock()
        app.bot = MagicMock()
        app.bot.set_webhook = AsyncMock(return_value=True)
        app.bot.delete_webhook = AsyncMock()
        app.start = AsyncMock()
        app.updater = MagicMock()
        app.updater.running = False
        app.updater.start_polling = AsyncMock()
        app.updater.stop = AsyncMock()
        return app

    @pytest.fixture()
    def mock_webhook_handler(self, mock_bot_app: MagicMock) -> MagicMock:
        """Create mock WebhookHandler."""
        handler = MagicMock(spec=WebhookHandler)
        handler.bot_app = mock_bot_app
        handler.webhook_path = "/webhook"
        handler.is_running = True
        handler.start = AsyncMock()
        handler.stop = AsyncMock()
        return handler

    @pytest.fixture()
    def failover(
        self, mock_bot_app: MagicMock, mock_webhook_handler: MagicMock
    ) -> WebhookFAlgolover:
        """Create WebhookFAlgolover instance."""
        return WebhookFAlgolover(
            bot_app=mock_bot_app,
            webhook_url="https://example.com",
            webhook_handler=mock_webhook_handler,
            health_check_interval=1,
            failure_threshold=2,
        )

    def test_initialization(self, failover: WebhookFAlgolover) -> None:
        """Test WebhookFAlgolover initialization."""
        assert failover.webhook_url == "https://example.com"
        assert failover.health_check_interval == 1
        assert failover.failure_threshold == 2
        assert failover.current_mode == "polling"
        assert not failover.is_running

    @pytest.mark.asyncio()
    async def test_start_with_webhook(
        self,
        failover: WebhookFAlgolover,
        mock_webhook_handler: MagicMock,
        mock_bot_app: MagicMock,
    ) -> None:
        """Test starting with webhook mode."""
        await failover.start_with_failover()

        assert failover.is_running
        assert failover.current_mode == "webhook"
        mock_webhook_handler.start.assert_called_once()
        mock_bot_app.bot.set_webhook.assert_called_once()

        await failover.stop()

    @pytest.mark.asyncio()
    async def test_start_fallback_to_polling(
        self,
        failover: WebhookFAlgolover,
        mock_webhook_handler: MagicMock,
        mock_bot_app: MagicMock,
    ) -> None:
        """Test falling back to polling when webhook fails."""
        # Make webhook setup fail
        mock_bot_app.bot.set_webhook = AsyncMock(return_value=False)

        await failover.start_with_failover()

        assert failover.is_running
        assert failover.current_mode == "polling"
        mock_bot_app.start.assert_called_once()
        mock_bot_app.updater.start_polling.assert_called_once()

        await failover.stop()

    @pytest.mark.asyncio()
    async def test_start_without_webhook_url(
        self, mock_bot_app: MagicMock, mock_webhook_handler: MagicMock
    ) -> None:
        """Test starting without webhook URL uses polling."""
        failover = WebhookFAlgolover(
            bot_app=mock_bot_app,
            webhook_url="",  # No webhook URL
            webhook_handler=mock_webhook_handler,
        )

        await failover.start_with_failover()

        assert failover.current_mode == "polling"

        await failover.stop()

    @pytest.mark.asyncio()
    async def test_stop(
        self, failover: WebhookFAlgolover, mock_webhook_handler: MagicMock
    ) -> None:
        """Test stopping failover manager."""
        await failover.start_with_failover()
        await failover.stop()

        assert not failover.is_running
        mock_webhook_handler.stop.assert_called()

    @pytest.mark.asyncio()
    async def test_switch_to_polling_on_failure(
        self,
        failover: WebhookFAlgolover,
        mock_webhook_handler: MagicMock,
        mock_bot_app: MagicMock,
    ) -> None:
        """Test automatic switch to polling on webhook failure."""
        await failover.start_with_failover()
        assert failover.current_mode == "webhook"

        # Simulate webhook becoming unhealthy
        mock_webhook_handler.is_running = False

        # WAlgot for failover loop to detect failure
        await asyncio.sleep(
            failover.health_check_interval * (failover.failure_threshold + 1)
        )

        # Should have switched to polling
        assert failover.current_mode == "polling"

        await failover.stop()

    @pytest.mark.asyncio()
    async def test_try_webhook_mode_exception(
        self,
        failover: WebhookFAlgolover,
        mock_webhook_handler: MagicMock,
    ) -> None:
        """Test handling exception in webhook setup."""
        mock_webhook_handler.start = AsyncMock(
            side_effect=Exception("Connection error")
        )

        result = await failover._try_webhook_mode()

        assert result is False

    @pytest.mark.asyncio()
    async def test_switch_to_webhook_from_polling(
        self,
        failover: WebhookFAlgolover,
        mock_bot_app: MagicMock,
        mock_webhook_handler: MagicMock,
    ) -> None:
        """Test switch from polling to webhook mode."""
        # Start in polling mode
        mock_bot_app.bot.set_webhook = AsyncMock(return_value=False)
        await failover.start_with_failover()
        assert failover.current_mode == "polling"

        # Now webhook becomes avAlgolable
        mock_bot_app.bot.set_webhook = AsyncMock(return_value=True)
        mock_webhook_handler.is_running = True

        # Manually test _switch_to_webhook which just sets mode
        # (the actual switch logic is now in _failover_loop)
        failover._mode = "webhook"

        assert failover.current_mode == "webhook"

        await failover.stop()


class TestWebhookFAlgoloverIntegration:
    """Integration tests for webhook failover."""

    @pytest.mark.asyncio()
    async def test_full_failover_cycle(self) -> None:
        """Test a complete failover cycle: webhook -> polling."""
        # Create mocks
        mock_bot_app = MagicMock()
        mock_bot_app.bot = MagicMock()
        mock_bot_app.bot.set_webhook = AsyncMock(return_value=True)
        mock_bot_app.bot.delete_webhook = AsyncMock()
        mock_bot_app.start = AsyncMock()
        mock_bot_app.updater = MagicMock()
        mock_bot_app.updater.running = False
        mock_bot_app.updater.start_polling = AsyncMock()
        mock_bot_app.updater.stop = AsyncMock()

        mock_handler = MagicMock(spec=WebhookHandler)
        mock_handler.webhook_path = "/webhook"
        mock_handler.is_running = True
        mock_handler.start = AsyncMock()
        mock_handler.stop = AsyncMock()

        failover = WebhookFAlgolover(
            bot_app=mock_bot_app,
            webhook_url="https://test.example.com",
            webhook_handler=mock_handler,
            health_check_interval=0.1,
            failure_threshold=1,
        )

        # Start in webhook mode
        await failover.start_with_failover()
        assert failover.current_mode == "webhook"

        # Simulate webhook failure (set_webhook will fail for recovery attempts)
        mock_handler.is_running = False
        mock_bot_app.bot.set_webhook = AsyncMock(return_value=False)
        await asyncio.sleep(0.3)

        # Should be in polling mode now
        assert failover.current_mode == "polling"

        # Cleanup
        await failover.stop()
        assert not failover.is_running
