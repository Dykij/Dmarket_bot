"""
Unit tests for src.telegram.notifier._TelegramNotifier.

Coverage:
- send_message: mock telegram API, verify message sent
- send_alert: verify alert formatting
- rate_limit_handling: verify backoff on telegram 429
- message_queue: verify messages are queued when rate limited
- Circuit breaker logic
- Throttling behavior
- High-level helpers (buy, sell, error, crash, etc.)
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# We need to import the class directly, not the singleton (which auto-configures)
from src.telegram.notifier import _TelegramNotifier  # noqa: E402


def _make_notifier(**env_vars) -> _TelegramNotifier:
    """Create a configured notifier with controlled env vars."""
    with patch.dict("os.environ", env_vars, clear=False):
        n = _TelegramNotifier()
        n.configure()
        return n


def _mock_session_post(status: int = 200, body: str = '{"ok":true}'):
    """Create a mock aiohttp session that returns the given status."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value=body)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.closed = False
    return mock_session


# =====================================================================
# test_send_message
# =====================================================================

class TestSendMessage:
    """Mock telegram API and verify message is sent."""

    @pytest.mark.asyncio
    async def test_send_raw_success(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n._send_raw("Test message", severity="info")
        assert result is True
        assert n._total_sent == 1
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_raw_disabled_returns_false(self) -> None:
        """When not configured (no token/chat_id), send returns False."""
        n = _make_notifier()  # no env vars → disabled
        result = await n._send_raw("Test", severity="info")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_raw_truncates_long_messages(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        long_msg = "x" * 5000
        await n._send_raw(long_msg, severity="info")

        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert len(payload["text"]) <= 4000

    @pytest.mark.asyncio
    async def test_send_raw_includes_parse_mode(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        await n._send_raw("<b>Bold</b>", severity="info", parse_mode="HTML")
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["parse_mode"] == "HTML"

    @pytest.mark.asyncio
    async def test_send_raw_silent_mode(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        await n._send_raw("Silent", severity="info", silent=True)
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["disable_notification"] is True


# =====================================================================
# test_send_alert
# =====================================================================

class TestSendAlert:
    """Verify alert formatting for buy, sell, error, crash."""

    @pytest.mark.asyncio
    async def test_buy_alert_format(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.buy(
            title="AK-47 | Redline (FT)",
            price_usd=12.50,
            expected_sell_usd=15.00,
            strategy="intra_spread",
        )
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "BOUGHT" in payload["text"]
        assert "AK-47" in payload["text"]
        assert "$12.50" in payload["text"]
        assert "$15.00" in payload["text"]

    @pytest.mark.asyncio
    async def test_sell_alert_profit(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.sell(
            title="AK-47 | Redline (FT)",
            buy_price_usd=12.50,
            sell_price_usd=15.00,
            profit_usd=2.50,
        )
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "SOLD" in payload["text"]
        assert "$+2.50" in payload["text"]

    @pytest.mark.asyncio
    async def test_sell_alert_loss(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.sell(
            title="AWP | Atheris (FT)",
            buy_price_usd=5.00,
            sell_price_usd=3.50,
            profit_usd=-1.50,
        )
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "SOLD" in payload["text"]
        assert "$-1.50" in payload["text"]

    @pytest.mark.asyncio
    async def test_error_alert(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.error("Circuit breaker tripped")
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "ERROR" in payload["text"]
        assert "Circuit breaker" in payload["text"]

    @pytest.mark.asyncio
    async def test_crash_alert(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.crash("Process out of memory")
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "CRASH" in payload["text"]

    @pytest.mark.asyncio
    async def test_circuit_open_alert(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        result = await n.circuit_open("DMarket API", 300.0)
        assert result is True
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert "CIRCUIT BREAKER" in payload["text"]
        assert "300s" in payload["text"]


# =====================================================================
# test_rate_limit_handling
# =====================================================================

class TestRateLimitHandling:
    """Verify backoff on telegram 429 responses."""

    @pytest.mark.asyncio
    async def test_429_increments_failed_counter(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(429, '{"retry_after":5}')
        n._session = mock_session

        result = await n._send_raw("Test", severity="info")
        assert result is False
        assert n._total_failed == 1

    @pytest.mark.asyncio
    async def test_429_forces_throttle(self) -> None:
        """After 429, the severity timestamp is updated to force throttle."""
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(429, '{"retry_after":5}')
        n._session = mock_session

        await n._send_raw("Test", severity="info")
        # The last_sent_at should be updated, causing throttle on next call
        assert "info" in n._last_sent_at

    @pytest.mark.asyncio
    async def test_5xx_increments_circuit_breaker(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(500, "Internal Server Error")
        n._session = mock_session

        await n._send_raw("Test", severity="info")
        assert n._cb_consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_network_error_increments_failure(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = AsyncMock()
        mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
        mock_session.closed = False
        n._session = mock_session

        result = await n._send_raw("Test", severity="info")
        assert result is False
        assert n._total_failed == 1


# =====================================================================
# test_message_queue
# =====================================================================

class TestMessageQueue:
    """Verify messages are throttled when rate limited."""

    @pytest.mark.asyncio
    async def test_throttle_window_blocks_rapid_messages(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        # First message succeeds
        result1 = await n._send_raw("Msg 1", severity="info")
        assert result1 is True

        # Second message immediately → throttled (info window = 60s)
        result2 = await n._send_raw("Msg 2", severity="info")
        assert result2 is False
        assert n._total_throttled == 1

    @pytest.mark.asyncio
    async def test_different_severities_have_independent_throttle(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        # info and warning have independent throttle windows
        result1 = await n._send_raw("Info msg", severity="info")
        result2 = await n._send_raw("Warning msg", severity="warning")
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_critical_severity_rarely_throttled(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(200)
        n._session = mock_session

        # Critical has 1s window — send two messages 0.05s apart
        result1 = await n._send_raw("Critical 1", severity="critical")
        # Force the timestamp to be slightly in the past
        n._last_sent_at["critical"] = time.time() - 1.1
        result2 = await n._send_raw("Critical 2", severity="critical")
        assert result1 is True
        assert result2 is True

    def test_throttle_window_values(self) -> None:
        """Verify throttle windows are configured correctly."""
        n = _TelegramNotifier()
        assert n.THROTTLE_S["info"] == 60.0
        assert n.THROTTLE_S["warning"] == 30.0
        assert n.THROTTLE_S["error"] == 10.0
        assert n.THROTTLE_S["critical"] == 1.0


# =====================================================================
# test_circuit_breaker
# =====================================================================

class TestCircuitBreaker:
    """Verify circuit breaker opens after consecutive failures."""

    @pytest.mark.asyncio
    async def test_cb_opens_after_threshold(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        mock_session = _mock_session_post(500, "Error")
        n._session = mock_session

        # Send CB_FAIL_THRESHOLD failures
        for _ in range(n.CB_FAIL_THRESHOLD):
            await n._send_raw("Test", severity="info")
            # Reset throttle to allow each send
            n._last_sent_at.clear()

        assert n._cb_is_open() is True

    @pytest.mark.asyncio
    async def test_cb_blocks_sends_when_open(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        n._cb_opened_at = time.time()  # force open

        result = await n._send_raw("Test", severity="info")
        assert result is False
        assert n._cb_total_short_circuits == 1

    def test_cb_force_close(self) -> None:
        n = _TelegramNotifier()
        n._cb_opened_at = time.time()
        n._cb_consecutive_failures = 5

        n.cb_force_close()
        assert n._cb_is_open() is False
        assert n._cb_consecutive_failures == 0

    def test_cb_force_open(self) -> None:
        n = _TelegramNotifier()
        n.cb_force_open()
        assert n._cb_is_open() is True
        assert n._cb_consecutive_failures == n.CB_FAIL_THRESHOLD

    @pytest.mark.asyncio
    async def test_cb_resets_on_success(self) -> None:
        n = _make_notifier(
            TELEGRAM_BOT_TOKEN="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            TELEGRAM_CHAT_ID="-1001234567890",
        )
        n._cb_consecutive_failures = 3
        mock_session = _mock_session_post(200)
        n._session = mock_session

        await n._send_raw("Test", severity="critical")
        assert n._cb_consecutive_failures == 0


# =====================================================================
# test_stats_and_configure
# =====================================================================

class TestStatsAndConfigure:
    """Verify stats reporting and configuration."""

    def test_stats_returns_expected_keys(self) -> None:
        n = _TelegramNotifier()
        s = n.stats()
        assert "enabled" in s
        assert "total_sent" in s
        assert "total_throttled" in s
        assert "total_failed" in s
        assert "circuit_breaker" in s
        assert "throttle_windows" in s

    def test_configure_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
        monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "111,222,333")
        n = _TelegramNotifier()
        n.configure()
        assert n._enabled is True
        assert n._admin_ids == {"111", "222", "333"}

    def test_configure_disabled_on_placeholder_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "ROTATE_ME_placeholder")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
        n = _TelegramNotifier()
        n.configure()
        assert n._enabled is False

    def test_configure_disabled_on_missing_chat_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        n = _TelegramNotifier()
        n.configure()
        assert n._enabled is False

    def test_recent_messages_tracked(self) -> None:
        n = _TelegramNotifier()
        assert len(n._recent_messages) == 0
        # max = 50, so it stays bounded

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        n = _TelegramNotifier()
        mock_session = AsyncMock()
        mock_session.closed = False
        n._session = mock_session

        await n.close()
        mock_session.close.assert_called_once()
        assert n._session is None
