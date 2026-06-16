"""
notifier.py — Lightweight Telegram notifier for the trading bot.

Why this exists:
The original `src.telegram.bot` and `src.telegram.control_bot` are
**command dispatchers** (a user types /balance → bot replies). They
are not designed to be called from the trading loop's hot path.

The trading bot needs to PUSH messages: "I made a buy", "I lost $X",
"circuit breaker tripped". This module is the bridge — it gives the
trading loop a one-line API to send alerts without depending on
aiogram dispatchers or importing the control_bot (which would create
a circular import since the control_bot imports from src.core.*).

Design:
- `Notifier` is a process-wide singleton (no module-level aiogram
  Bot/Dispatcher — we use aiohttp directly to avoid the dispatcher
  lifecycle coupling).
- All sends are throttled: at most 1 message per N seconds per
  severity (info / warning / error) to avoid Telegram rate limits
  during a crash storm.
- The notifier is fire-and-forget: if Telegram is down, the trading
  loop continues unaffected.

Usage (from any module, even from inside a coroutine):
    from src.telegram.notifier import notifier
    await notifier.buy(title="AK-47 | Redline (FT)", price=1.50)
    await notifier.error("Circuit breaker tripped for CS2Cap")

Configuration is read from .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
TELEGRAM_ADMIN_IDS). If either is missing or a placeholder, the
notifier silently no-ops.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Set, Tuple

import aiohttp

logger = logging.getLogger("TelegramNotifier")


class _TelegramNotifier:
    """
    Process-singleton Telegram notifier for the trading bot.

    See module docstring for design rationale.
    """

    # Throttle windows (seconds). A new message of severity X is held
    # back if one was sent in the last THROTTLE_S[X] seconds.
    THROTTLE_S: Dict[str, float] = {
        "info": 60.0,        # buy/sell — at most 1/min
        "warning": 30.0,     # circuit breaker — at most 1/30s
        "error": 10.0,        # crashes — at most 1/10s
        "critical": 1.0,      # daily loss limit — almost never throttled
    }

    # v12.7: Circuit breaker thresholds. After N consecutive send
    # failures (HTTP non-200, network error, etc.) the notifier opens
    # the circuit for COOLDOWN_S seconds, during which it silently
    # no-ops to avoid hammering a down Telegram API. After the cooldown
    # a single probe is sent on the next call; if it succeeds the
    # circuit closes, otherwise it stays open another COOLDOWN_S.
    CB_FAIL_THRESHOLD: int = 5
    CB_COOLDOWN_S: float = 300.0  # 5 min

    def __init__(self) -> None:
        self._token: str = ""
        self._chat_id: str = ""
        self._admin_ids: Set[str] = set()
        self._last_sent_at: Dict[str, float] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._enabled: bool = False
        self._last_error_log: float = 0.0
        self._total_sent: int = 0
        self._total_throttled: int = 0
        self._total_failed: int = 0
        self._recent_messages: Deque[Tuple[float, str]] = deque(maxlen=50)

        # v12.7: circuit breaker state
        self._cb_consecutive_failures: int = 0
        self._cb_opened_at: float = 0.0  # 0.0 = closed
        self._cb_total_opens: int = 0
        self._cb_total_short_circuits: int = 0  # sends blocked by open CB

    def configure(self) -> None:
        """Re-read .env values. Idempotent; call after env changes."""
        self._token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        admins_env = os.getenv("TELEGRAM_ADMIN_IDS", "").strip()
        if admins_env:
            self._admin_ids = {
                x.strip() for x in admins_env.split(",") if x.strip()
            }
        else:
            self._admin_ids = set()
        # Placeholder detection: after .env rotation, tokens may be
        # "ROTATE_ME_*" until the user fills in real values. In that
        # case, the notifier must stay silent (don't try to call the
        # real Telegram API with a bogus token, or we'd waste a ban
        # on the wrong token).
        bogus = self._token.startswith("ROTATE_ME") or not self._token
        self._enabled = bool(self._token) and bool(self._chat_id) and not bogus
        if not self._enabled:
            logger.debug(
                "[notifier] disabled (token/chat_id missing or placeholder)"
            )

    async def _ensure_session(self) -> Optional[aiohttp.ClientSession]:
        if not self._enabled:
            return None
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _should_throttle(self, severity: str) -> bool:
        now = time.time()
        last = self._last_sent_at.get(severity, 0.0)
        window = self.THROTTLE_S.get(severity, 30.0)
        return (now - last) < window

    async def _send_raw(
        self,
        text: str,
        severity: str = "info",
        parse_mode: str = "HTML",
        silent: bool = False,
    ) -> bool:
        """Send a single message. Returns True on success, False on throttled/failed."""
        if not self._enabled:
            return False

        # v12.7: Circuit breaker check (before throttle so we don't
        # count CB-blocked sends as 'throttled' — those are different
        # concerns: throttle is rate-limiting, CB is fault-isolation).
        if self._cb_is_open():
            self._cb_total_short_circuits += 1
            return False

        if self._should_throttle(severity):
            self._total_throttled += 1
            logger.debug(
                f"[notifier] throttled severity={severity} "
                f"({self._total_throttled} total throttled)"
            )
            return False

        session = await self._ensure_session()
        if session is None:
            return False

        # v12.9: Security — never log the URL containing the bot token.
        # CVE-2026-27003 showed that logging bot URLs = token leak.
        # Use a redacted placeholder for any logging context instead.
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        _redacted_url = "https://api.telegram.org/bot<REDACTED>/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": text[:4000],  # Telegram hard cap is 4096
            "disable_notification": silent,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    self._last_sent_at[severity] = time.time()
                    self._total_sent += 1
                    self._recent_messages.append((time.time(), severity))
                    self._cb_record_success()
                    return True
                body = await resp.text()
                # 429 = rate limited by Telegram; back off
                if resp.status == 429:
                    self._total_failed += 1
                    self._last_sent_at[severity] = time.time()  # force throttle
                    self._cb_record_failure()  # CB counts 429s too
                    logger.warning(
                        f"[notifier] Telegram 429 (rate limit): {body[:200]}"
                    )
                else:
                    self._total_failed += 1
                    self._cb_record_failure()
                    # Don't spam the log on transient errors
                    now = time.time()
                    if now - self._last_error_log > 60:
                        self._last_error_log = now
                        logger.warning(
                            f"[notifier] HTTP {resp.status}: {body[:200]}"
                        )
                return False
        except Exception as e:
            self._total_failed += 1
            self._cb_record_failure()
            now = time.time()
            if now - self._last_error_log > 60:
                self._last_error_log = now
                logger.warning(f"[notifier] send failed: {e}", exc_info=True)
            return False

    # ----------------------------------------------------------------
    # v12.7: Circuit breaker internals
    # ----------------------------------------------------------------
    def _cb_is_open(self) -> bool:
        """True if the circuit is currently OPEN (blocking sends)."""
        if self._cb_opened_at == 0.0:
            return False  # closed
        # If the cooldown has elapsed, transition to half-open: the
        # next send becomes a probe; success closes, failure re-opens.
        # We reset _cb_opened_at here so that _cb_record_failure can
        # re-open the circuit (otherwise the "if _cb_opened_at == 0.0"
        # guard would block the re-open).
        if time.time() - self._cb_opened_at >= self.CB_COOLDOWN_S:
            self._cb_opened_at = 0.0
            return False
        return True

    def _cb_record_success(self) -> None:
        """Call after a successful send. Closes the circuit if open."""
        if self._cb_opened_at > 0.0:
            logger.info(
                f"[notifier] Circuit breaker CLOSED after "
                f"{self._cb_consecutive_failures} consecutive failures"
            )
        self._cb_consecutive_failures = 0
        self._cb_opened_at = 0.0

    def _cb_record_failure(self) -> None:
        """Call after a send failure. Opens the circuit if threshold hit."""
        self._cb_consecutive_failures += 1
        if (
            self._cb_opened_at == 0.0
            and self._cb_consecutive_failures >= self.CB_FAIL_THRESHOLD
        ):
            self._cb_opened_at = time.time()
            self._cb_total_opens += 1
            logger.warning(
                f"[notifier] Circuit breaker OPENED after "
                f"{self._cb_consecutive_failures} consecutive failures. "
                f"Cooldown: {self.CB_COOLDOWN_S:.0f}s"
            )

    def cb_force_close(self) -> None:
        """Manual reset (admin override). Closes the circuit immediately."""
        if self._cb_opened_at > 0.0:
            logger.info("[notifier] Circuit breaker manually CLOSED")
        self._cb_opened_at = 0.0
        self._cb_consecutive_failures = 0

    def cb_force_open(self) -> None:
        """Manual trip (admin override). Opens the circuit for cooldown."""
        self._cb_opened_at = time.time()
        self._cb_total_opens += 1
        self._cb_consecutive_failures = self.CB_FAIL_THRESHOLD
        logger.warning("[notifier] Circuit breaker manually OPENED")

    # ---- High-level helpers used by the trading loop ----

    async def buy(
        self,
        title: str,
        price_usd: float,
        expected_sell_usd: float,
        strategy: str = "intra_spread",
    ) -> bool:
        """Alert: we just bought something."""
        margin = ((expected_sell_usd - price_usd) / price_usd * 100) if price_usd > 0 else 0
        text = (
            f"🟢 <b>BOUGHT</b>\n"
            f"<code>{title}</code>\n"
            f"Buy: ${price_usd:.2f} → Sell target: ${expected_sell_usd:.2f} "
            f"(<b>{margin:+.1f}%</b>)\n"
            f"Strategy: {strategy}"
        )
        return await self._send_raw(text, severity="info")

    async def sell(
        self,
        title: str,
        buy_price_usd: float,
        sell_price_usd: float,
        profit_usd: float,
    ) -> bool:
        """Alert: an item was sold."""
        emoji = "🟢" if profit_usd >= 0 else "🔴"
        text = (
            f"{emoji} <b>SOLD</b>\n"
            f"<code>{title}</code>\n"
            f"Buy: ${buy_price_usd:.2f} → Sell: ${sell_price_usd:.2f}\n"
            f"PnL: <b>${profit_usd:+.2f}</b>"
        )
        return await self._send_raw(text, severity="info")

    async def equity_milestone(
        self,
        cash: float,
        assets_value: float,
        total: float,
        items_count: int,
    ) -> bool:
        """Alert: equity crossed a $5 threshold (either up or down)."""
        text = (
            f"📊 <b>EQUITY UPDATE</b>\n"
            f"Cash: ${cash:.2f} | Assets: ${assets_value:.2f}\n"
            f"Total: <b>${total:.2f}</b> | Items: {items_count}"
        )
        return await self._send_raw(text, severity="info")

    async def error(self, message: str) -> bool:
        """Alert: non-fatal error (use sparingly)."""
        return await self._send_raw(
            f"⚠️ <b>ERROR</b>\n{message[:3500]}",
            severity="warning",
        )

    async def crash(self, message: str) -> bool:
        """Alert: process is about to crash/restart (severity=critical)."""
        return await self._send_raw(
            f"🔴 <b>CRASH</b>\n{message[:3500]}",
            severity="critical",
        )

    async def circuit_open(self, name: str, cooldown_s: float) -> bool:
        """Alert: a circuit breaker tripped."""
        return await self._send_raw(
            f"⛔ <b>CIRCUIT BREAKER</b>\n"
            f"<code>{name}</code> is OPEN\n"
            f"Cooldown: {cooldown_s:.0f}s",
            severity="warning",
        )

    async def daily_briefing(
        self,
        total_equity: float,
        realized_pnl: float,
        items_holding: int,
        items_sold_today: int,
    ) -> bool:
        """Daily summary (severity=info, throttled to 1/24h by caller)."""
        emoji = "📈" if realized_pnl >= 0 else "📉"
        text = (
            f"🌅 <b>DAILY BRIEFING</b>\n"
            f"{emoji} Today's PnL: <b>${realized_pnl:+.2f}</b>\n"
            f"Total equity: ${total_equity:.2f}\n"
            f"Holding: {items_holding} | Sold today: {items_sold_today}"
        )
        return await self._send_raw(text, severity="info")

    async def custom(self, text: str, severity: str = "info") -> bool:
        """Send an arbitrary message with the given severity."""
        return await self._send_raw(text, severity=severity)

    def stats(self) -> Dict[str, Any]:
        """Diagnostic info for /status and logs."""
        return {
            "enabled": self._enabled,
            "total_sent": self._total_sent,
            "total_throttled": self._total_throttled,
            "total_failed": self._total_failed,
            "throttle_windows": dict(self.THROTTLE_S),
            "last_sent_per_severity": dict(self._last_sent_at),
            "recent_count": len(self._recent_messages),
            "circuit_breaker": {
                "state": "open" if self._cb_is_open() else "closed",
                "consecutive_failures": self._cb_consecutive_failures,
                "fail_threshold": self.CB_FAIL_THRESHOLD,
                "cooldown_s": self.CB_COOLDOWN_S,
                "total_opens": self._cb_total_opens,
                "total_short_circuits": self._cb_total_short_circuits,
                "opened_at": self._cb_opened_at,
            },
        }


# Module-level singleton. Importable as:
#   from src.telegram.notifier import notifier
#   await notifier.buy(...)
notifier = _TelegramNotifier()
notifier.configure()


def reconfigure() -> None:
    """Re-read .env (call after loading a new .env at runtime)."""
    notifier.configure()
