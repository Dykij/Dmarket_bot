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

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
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
                    return True
                body = await resp.text()
                # 429 = rate limited by Telegram; back off
                if resp.status == 429:
                    self._total_failed += 1
                    self._last_sent_at[severity] = time.time()  # force throttle
                    logger.warning(
                        f"[notifier] Telegram 429 (rate limit): {body[:200]}"
                    )
                else:
                    self._total_failed += 1
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
            now = time.time()
            if now - self._last_error_log > 60:
                self._last_error_log = now
                logger.warning(f"[notifier] send failed: {e}")
            return False

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
        }


# Module-level singleton. Importable as:
#   from src.telegram.notifier import notifier
#   await notifier.buy(...)
notifier = _TelegramNotifier()
notifier.configure()


def reconfigure() -> None:
    """Re-read .env (call after loading a new .env at runtime)."""
    notifier.configure()
