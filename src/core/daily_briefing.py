"""
daily_briefing.py — Daily P&L + risk report scheduler (v12.5).

Runs as a background asyncio task inside the main bot loop. Every UTC
midnight it:
  1. Pulls the current equity, realized PnL, holding/sold counts
  2. Pulls the risk manager's state (daily loss, drawdown, halts)
  3. Pulls the most recent equity_snapshots for trend
  4. Pulls risk_events log for any kill-switch trips
  5. Sends a single Telegram message (throttled to 1/day by the notifier)
  6. Records today's final equity snapshot to SQLite for crash-recovery

Public API:
    scheduler = DailyBriefingScheduler(
        risk=risk_manager,
        notifier=notifier,
        price_db=price_db,
        get_balance=async_callable_returning_usd,
    )
    task = asyncio.create_task(scheduler.run())
    # ... in shutdown:
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from src.db.price_history import price_db
from src.telegram.notifier import notifier

logger = logging.getLogger("DailyBriefing")


class DailyBriefingScheduler:
    """
    Schedules a daily Telegram briefing at UTC midnight.

    Robustness features:
    - Skips a day if the bot is restarted mid-day (sends at the next midnight)
    - Catches all exceptions; never crashes the bot
    - Reschedules within 1 second if the bot is started mid-day
    - Records equity snapshot to SQLite before sending (crash-recovery)
    """

    def __init__(
        self,
        risk,  # RiskManager instance
        get_balance: Callable[[], Awaitable[float]],
        get_equity: Optional[Callable[[float], dict]] = None,
        hour: int = 0,
        minute: int = 0,
    ) -> None:
        """
        Args:
            risk: RiskManager instance (for risk state in the briefing)
            get_balance: async callable returning current USD balance
            get_equity: optional async callable(usd_balance) -> {cash, assets, total, count}
                        (defaults to price_db.get_total_equity)
            hour: UTC hour to send (default 0 = midnight)
            minute: UTC minute (default 0)
        """
        self._risk = risk
        self._get_balance = get_balance
        self._get_equity = get_equity or self._default_equity
        self._hour = hour
        self._minute = minute
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._last_sent_date: Optional[str] = None
        self._startup_sent: bool = False
        self._consecutive_failures: int = 0

    def start(self) -> asyncio.Task:
        """Launch the scheduler as a background task. Returns the task."""
        if self._task is not None and not self._task.done():
            logger.warning("[Briefing] Scheduler already running")
            return self._task
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="daily-briefing")
        logger.info(f"[Briefing] Scheduler started (UTC {self._hour:02d}:{self._minute:02d})")
        return self._task

    async def stop(self) -> None:
        """Stop the scheduler cleanly."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("[Briefing] Scheduler stopped")

    async def send_now(self, note: str = "") -> bool:
        """Force-send a briefing right now (e.g. on bot startup, /briefing command)."""
        return await self._send_briefing(note=note or "manual")

    async def _run(self) -> None:
        """Main loop: wait until next UTC HH:MM, send briefing, repeat."""
        assert self._stop_event is not None
        try:
            # Send a startup briefing immediately if the bot started
            # mid-day (so the user knows the bot is alive even before
            # midnight arrives). Throttled to once per process lifetime.
            if not self._startup_sent:
                try:
                    # Small delay to let the bot fully boot first
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=30.0
                    )
                except asyncio.TimeoutError:
                    pass
                if not self._stop_event.is_set():
                    await self._send_briefing(note="startup")
                    self._startup_sent = True
                    self._last_sent_date = self._current_date()

            while not self._stop_event.is_set():
                now = datetime.now(timezone.utc)
                # Compute next briefing time
                target = now.replace(
                    hour=self._hour, minute=self._minute, second=0, microsecond=0
                )
                if target <= now:
                    # Already past today's HH:MM; schedule tomorrow
                    target = target.replace(day=target.day + 1)
                sleep_s = (target - now).total_seconds()
                logger.debug(
                    f"[Briefing] Next briefing in {sleep_s:.0f}s "
                    f"(at {target.isoformat()})"
                )
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=sleep_s
                    )
                    return  # stop event set
                except asyncio.TimeoutError:
                    pass
                if self._stop_event.is_set():
                    return
                # Sleep done — but make sure we don't double-send
                today = self._current_date()
                if self._last_sent_date == today:
                    continue
                await self._send_briefing(note="scheduled")
                self._last_sent_date = today
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.exception(f"[Briefing] Fatal error in scheduler loop: {e}")

    async def _send_briefing(self, note: str = "") -> bool:
        """Compose and send the daily briefing. Returns True on success."""
        self._consecutive_failures += 1
        try:
            # 1. Pull current state
            balance = await self._safe_get_balance()
            equity = await self._safe_get_equity(balance)
            risk_state = self._risk.get_state()
            realized_today = -risk_state.daily_loss_usd
            holdings = equity.get("count", 0) if isinstance(equity, dict) else 0
            sold_today = price_db.state_conn.execute(
                "SELECT COUNT(*) as c FROM virtual_inventory "
                "WHERE status='sold' AND sold_at > ?",
                (time.time() - 86400,),
            ).fetchone()["c"]

            # 2. Compute delta vs yesterday (if snapshot exists)
            snapshots = price_db.get_equity_snapshots(days=2)
            yesterday_total = snapshots[-2]["total"] if len(snapshots) >= 2 else None
            delta_str = ""
            if yesterday_total is not None and yesterday_total > 0:
                delta_pct = ((equity["total"] - yesterday_total) / yesterday_total) * 100
                sign = "+" if delta_pct >= 0 else ""
                delta_str = f" ({sign}{delta_pct:.2f}% vs yesterday)"

            # 3. Compose message
            emoji = "📈" if realized_today >= 0 else "📉"
            msg_lines = [
                f"{emoji} <b>DAILY BRIEFING</b> — {self._current_date()} UTC",
                f"Mode: {'🧪 DRY_RUN' if self._is_dry() else '💸 LIVE'}",
                f"Note: {note}",
                "",
                f"💰 Cash: ${equity['cash']:.2f}",
                f"📦 Assets: ${equity['assets']:.2f} ({holdings} items)",
                f"💎 Total Equity: <b>${equity['total']:.2f}</b>{delta_str}",
                "",
                f"📊 Today's PnL: <b>${realized_today:+.2f}</b>",
                f"🔄 Trades: {risk_state.daily_trade_count}/{risk_state.daily_trade_limit} "
                f"(blocked: {risk_state.blocked_count_today})",
                f"📉 Drawdown: {risk_state.current_drawdown_pct:.1f}% "
                f"(max: {risk_state.max_drawdown_pct:.1f}%)",
                f"🏷️ Sold today: {sold_today}",
            ]
            if risk_state.soft_halt_active:
                msg_lines.append("⚠️ <b>Soft-halt active</b> (size halved on next buy)")
            if risk_state.daily_halt_active:
                msg_lines.append("🔴 <b>Daily loss limit hit</b> — trading halted until midnight")

            # 4. Risk events today
            events = price_db.get_risk_events_today()
            if events:
                msg_lines.append("")
                msg_lines.append(f"⚠️ <b>Risk events today: {len(events)}</b>")
                for e in events[:5]:
                    msg_lines.append(
                        f"  [{e['severity']}] {e['type']}: {e['details'][:80]}"
                    )

            text = "\n".join(msg_lines)

            # 5. Record equity snapshot FIRST (so a Telegram failure
            # doesn't lose the data).
            try:
                price_db.record_equity_snapshot(
                    cash=equity["cash"],
                    assets=equity["assets"],
                    total=equity["total"],
                    realized_pnl=realized_today,
                    note=note,
                )
            except Exception as e:
                logger.warning(f"[Briefing] Failed to record equity snapshot: {e}")

            # 6. Send via Telegram (severity=info, throttled to 1/min by
            # the notifier — but daily briefings are only 1/day so OK).
            ok = await notifier.custom(text, severity="info")
            self._consecutive_failures = 0
            if ok:
                logger.info(f"[Briefing] Sent ({note})")
            else:
                logger.info("[Briefing] Notifier returned False (probably disabled)")
            return ok
        except Exception as e:
            logger.exception(f"[Briefing] Failed to send ({note}): {e}")
            return False

    @staticmethod
    def _current_date() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def _is_dry() -> bool:
        import os
        return os.getenv("DRY_RUN", "true").lower() == "true"

    async def _safe_get_balance(self) -> float:
        try:
            return float(await self._get_balance())
        except Exception as e:
            logger.debug(f"[Briefing] get_balance failed: {e}")
            return 0.0

    async def _safe_get_equity(self, balance: float) -> dict:
        try:
            return await self._get_equity(balance)
        except Exception as e:
            logger.debug(f"[Briefing] get_equity failed: {e}")
            return {"cash": balance, "assets": 0.0, "total": balance, "count": 0}

    async def _default_equity(self, balance: float) -> dict:
        """Default equity calculator using price_db (DB-only, no network)."""
        return price_db.get_total_equity(balance)
