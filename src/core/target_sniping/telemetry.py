"""
telemetry.py — Health reporting + diagnostic logging.

Mixin with _update_health_metrics(), _send_equity_milestone(), and _log_cycle_diag().
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from src.telegram.notifier import notifier

logger = logging.getLogger("SnipingBot")


class _TelemetryMixin:
    """Health-state, equity milestones, and per-cycle diagnostics."""

    client: Any
    cs2cap_cache: Optional[Any]
    deep_scan_counter: int
    risk: Any
    pump_detector: Any
    _last_milestone: float

    def _update_health_metrics(self, equity: dict) -> None:
        """v12.7: Update HTTP health server metrics (no-op if disabled)."""
        try:
            from src.utils.health_server import health_state
            risk_state = self.risk.get_state()
            health_state.mark_cycle(
                equity_usd=equity["total"],
                peak_equity_usd=risk_state.peak_equity_usd,
                drawdown_pct=risk_state.current_drawdown_pct,
            )
            health_state.set_daily_stats(
                pnl_usd=-risk_state.daily_loss_usd,
                trade_count=risk_state.daily_trade_count,
            )
            health_state.set_halts(
                soft_halt=risk_state.soft_halt_active,
                daily_halt=risk_state.daily_halt_active,
            )
            if self.pump_detector is not None:
                pd_stats = self.pump_detector.stats()
                health_state.set_pump_stats(
                    blacklist_size=pd_stats["active_blacklist_size"],
                    total_detections=pd_stats["total_detections"],
                )
            if self.cs2cap_cache is not None:
                cache_stats = self.cs2cap_cache.stats()
                used = cache_stats.get("monthly_used", 0)
                limit = cache_stats.get("monthly_limit", 50000)
                quota_pct = (used / limit * 100.0) if limit > 0 else None
                health_state.set_cs2cap_quota_pct(quota_pct)
        except Exception as e:
            logger.debug(f"[health_state] update failed: {e}")

    def _send_equity_milestone(self, equity: dict) -> None:
        """v12.5: Telegram equity milestone (every $5 change, throttled to 1/min)."""
        if not hasattr(self, "_last_milestone") or (
            abs(equity["total"] - self._last_milestone) >= 5.0
        ):
            self._last_milestone = equity["total"]
            asyncio.create_task(
                notifier.equity_milestone(
                    cash=equity["cash"],
                    assets_value=equity["assets"],
                    total=equity["total"],
                    items_count=int(equity["count"]),
                )
            )

    def _log_cycle_diag(self, game_id: str, candidates_len: int, buys_len: int) -> None:
        """v12.9 + v12.4: Sanitized cycle log + periodic CS2Cap/breaker diagnostic."""
        logger.debug(
            f"[v12.9 CYCLE] game={game_id} cycle={self.deep_scan_counter} "
            f"candidates={candidates_len} buys={buys_len}"
        )

        if self.deep_scan_counter % 10 == 0:
            cache_stats = (
                self.cs2cap_cache.stats()
                if self.cs2cap_cache is not None
                else {"ask_count": 0, "bid_count": 0, "is_stale": True}
            )
            cb_stats = self.client.circuit_breaker_status()
            logger.info(
                f"[v12.4 DIAG] CS2Cap cache: {cache_stats['ask_count']} asks, "
                f"{cache_stats['bid_count']} bids, "
                f"stale={cache_stats['is_stale']}, "
                f"age={cache_stats.get('age_seconds')}s, "
                f"refreshes={cache_stats['refresh_count']} | "
                f"CB: state={cb_stats['state']}, "
                f"opens={cb_stats['total_opens']}, "
                f"fails={cb_stats['consecutive_failures']}"
            )
