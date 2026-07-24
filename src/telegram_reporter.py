"""
telegram_reporter.py — Automated Telegram reports with 4 cadences.

Sends structured reports to Telegram based on elapsed time since last send.
Uses existing scanning_state table (via price_db) for timestamp persistence.
Uses existing notifier singleton for message delivery.

Report types:
  'hourly'  — every 1h  — brief cycle stats
  'cron'    — every 5h  — launch confirmation, 429 count, oracle status
  'daily'   — every 24h — full daily summary
  'weekly'  — every 7d  — trends, forecasts

Integration: called from scheduler.py after each main-loop cycle.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("TelegramReporter")

# Report type -> default interval (seconds)
DEFAULT_INTERVALS: dict[str, int] = {
    "hourly": 3600,
    "cron": 18000,
    "daily": 86400,
    "weekly": 604800,
}

# State key prefix in scanning_state table
_STATE_PREFIX = "report_last_sent_"


class TelegramReporter:
    """Automated Telegram reporter with 4 cadences.

    Args:
        notifier: TelegramNotifier singleton (src.telegram.notifier)
        price_db: PriceHistoryDB singleton (src.db.price_history)
        intervals: override default intervals (seconds per report type)
        get_stats: async callable returning current stats dict
    """

    def __init__(
        self,
        notifier: Any,
        price_db: Any,
        intervals: dict[str, int] | None = None,
        get_stats: Any = None,
    ) -> None:
        self._notifier = notifier
        self._db = price_db
        self._intervals = {**DEFAULT_INTERVALS, **(intervals or {})}
        self._get_stats = get_stats
        self._boot_time = time.time()
        # In-session counters (reset each run)
        self._session_cycles = 0
        self._session_listings = 0
        self._session_candidates = 0
        self._session_429 = 0
        self._session_cycle_times: list[float] = []
        self._last_balance = 0.0
        self._last_drawdown = 0.0

    def record_cycle(
        self,
        balance: float = 0.0,
        listings: int = 0,
        candidates: int = 0,
        errors_429: int = 0,
        cycle_time: float = 0.0,
        drawdown: float = 0.0,
    ) -> None:
        """Record one cycle's stats (called from main loop)."""
        self._session_cycles += 1
        self._session_listings += listings
        self._session_candidates += candidates
        self._session_429 += errors_429
        if cycle_time > 0:
            self._session_cycle_times.append(cycle_time)
        if balance > 0:
            self._last_balance = balance
        self._last_drawdown = drawdown

    async def check_and_send_reports(self) -> None:
        """Check all report types and send those whose interval has elapsed."""
        now = time.time()
        for report_type, interval in self._intervals.items():
            try:
                last_sent = self._get_last_sent(report_type)
                if (now - last_sent) >= interval:
                    text = await self._generate_report(report_type)
                    if text:
                        ok = await self._notifier.custom(text, severity="info")
                        if ok:
                            self._update_last_sent(report_type, now)
                            logger.info(
                                f"[Reporter] {report_type} report sent "
                                f"(interval={interval}s)"
                            )
                        else:
                            logger.warning(
                                f"[Reporter] {report_type} report send failed"
                            )
            except Exception as e:
                logger.debug(f"[Reporter] {report_type} report error: {e}")

    def _get_last_sent(self, report_type: str) -> float:
        """Get last sent timestamp from scanning_state table."""
        key = f"{_STATE_PREFIX}{report_type}"
        try:
            val = self._db.get_state(key)
            return float(val) if val else 0.0
        except Exception:
            return 0.0

    def _update_last_sent(self, report_type: str, ts: float) -> None:
        """Update last sent timestamp in scanning_state table."""
        key = f"{_STATE_PREFIX}{report_type}"
        try:
            self._db.save_state(key, str(ts))
        except Exception as e:
            logger.debug(f"[Reporter] Failed to update {report_type} ts: {e}")

    async def _generate_report(self, report_type: str) -> str:
        """Generate report text based on type."""
        generators = {
            "hourly": self._report_hourly,
            "cron": self._report_cron,
            "daily": self._report_daily,
            "weekly": self._report_weekly,
        }
        gen = generators.get(report_type)
        if not gen:
            return ""
        try:
            return await gen()
        except Exception as e:
            logger.warning(f"[Reporter] {report_type} generation error: {e}")
            return ""

    # ------------------------------------------------------------------
    # Report generators
    # ------------------------------------------------------------------

    async def _report_hourly(self) -> str:
        """Hourly: brief status."""
        avg_time = (
            sum(self._session_cycle_times[-60:]) /
            max(len(self._session_cycle_times[-60:]), 1)
        )
        uptime_min = (time.time() - self._boot_time) / 60
        lines = [
            "<b>HOURLY STATUS</b>",
            f"Uptime: {uptime_min:.0f}m | Cycles: {self._session_cycles}",
            f"Listings: {self._session_listings} | Candidates: {self._session_candidates}",
            f"Balance: ${self._last_balance:.2f} | Drawdown: {self._last_drawdown:.1f}%",
            f"429 errors: {self._session_429} | Avg cycle: {avg_time:.1f}s",
        ]
        return "\n".join(lines)

    async def _report_cron(self) -> str:
        """Cron (every 5h): launch confirmation + detailed stats."""
        avg_time = (
            sum(self._session_cycle_times) /
            max(len(self._session_cycle_times), 1)
        )
        uptime_min = (time.time() - self._boot_time) / 60
        lines = [
            "<b>CRON REPORT (5h)</b>",
            f"Run uptime: {uptime_min:.0f}m",
            f"Cycles: {self._session_cycles}",
            f"Listings fetched: {self._session_listings}",
            f"Candidates found: {self._session_candidates}",
            f"429 errors: {self._session_429}",
            f"Avg cycle time: {avg_time:.1f}s",
            f"Balance: ${self._last_balance:.2f}",
            f"Drawdown: {self._last_drawdown:.1f}%",
        ]
        # Oracle status (if available)
        stats = await self._safe_get_stats()
        if stats:
            if "oracle_status" in stats:
                lines.append(f"Oracles: {stats['oracle_status']}")
            if "rate_limiter_margin" in stats:
                lines.append(f"Rate margin: {stats['rate_limiter_margin']}")
        return "\n".join(lines)

    async def _report_daily(self) -> str:
        """Daily: full summary."""
        avg_time = (
            sum(self._session_cycle_times) /
            max(len(self._session_cycle_times), 1)
        )
        max_balance = max(
            self._last_balance,
            float(self._db.get_state("report_max_balance") or "0"),
        )
        min_balance = min(
            self._last_balance,
            float(self._db.get_state("report_min_balance") or self._last_balance),
        )
        # Persist for next report
        self._db.save_state("report_max_balance", str(max_balance))
        self._db.save_state("report_min_balance", str(min_balance))

        lines = [
            "<b>DAILY REPORT</b>",
            f"Cycles: {self._session_cycles}",
            f"Listings: {self._session_listings}",
            f"Candidates: {self._session_candidates}",
            f"429 errors: {self._session_429}",
            f"Avg cycle: {avg_time:.1f}s",
            f"Balance: ${self._last_balance:.2f}",
            f"Balance range: ${min_balance:.2f} - ${max_balance:.2f}",
            f"Drawdown: {self._last_drawdown:.1f}%",
        ]
        stats = await self._safe_get_stats()
        if stats:
            if "oracle_status" in stats:
                lines.append(f"Oracles: {stats['oracle_status']}")
            if "rate_limiter_margin" in stats:
                lines.append(f"Rate margin: {stats['rate_limiter_margin']}")
        return "\n".join(lines)

    async def _report_weekly(self) -> str:
        """Weekly: trends and forecasts."""
        # Read stored daily snapshots
        prev_cycles = float(self._db.get_state("report_weekly_cycles") or "0")
        prev_429 = float(self._db.get_state("report_weekly_429") or "0")
        prev_balance = float(self._db.get_state("report_weekly_balance") or "0")

        cycles_delta = self._session_cycles - prev_cycles
        errors_delta = self._session_429 - prev_429
        balance_delta = self._last_balance - prev_balance

        # Store for next week
        self._db.save_state("report_weekly_cycles", str(self._session_cycles))
        self._db.save_state("report_weekly_429", str(self._session_429))
        self._db.save_state("report_weekly_balance", str(self._last_balance))

        sign_bal = "+" if balance_delta >= 0 else ""
        lines = [
            "<b>WEEKLY REPORT</b>",
            f"Total cycles: {self._session_cycles} ({cycles_delta:+.0f} this week)",
            f"Total 429 errors: {self._session_429} ({errors_delta:+.0f} this week)",
            f"Balance: ${self._last_balance:.2f} ({sign_bal}${balance_delta:.2f})",
            f"Drawdown: {self._last_drawdown:.1f}%",
            f"Avg cycle time: "
            f"{sum(self._session_cycle_times) / max(len(self._session_cycle_times), 1):.1f}s",
        ]
        stats = await self._safe_get_stats()
        if stats:
            if "oracle_status" in stats:
                lines.append(f"Oracles: {stats['oracle_status']}")
        return "\n".join(lines)

    async def _safe_get_stats(self) -> dict[str, Any] | None:
        """Safely call get_stats callback."""
        if not self._get_stats:
            return None
        try:
            result = self._get_stats()
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            logger.debug(f"[Reporter] get_stats error: {e}")
            return None
