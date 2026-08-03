"""
telemetry.py — Health reporting + diagnostic logging.

Mixin with _update_health_metrics(), _send_equity_milestone(), and _log_cycle_diag().
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# P1-1: Lazy import

logger = logging.getLogger("SnipingBot")

def _get_notifier():
    """P1-1: Lazy import notifier to avoid core->telegram coupling at import time."""
    from src.telegram.notifier import notifier
    return notifier



class _TelemetryMixin:
    """Health-state, equity milestones, and per-cycle diagnostics."""

    client: Any
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
                pnl_usd=getattr(risk_state, 'daily_realized_pnl', -risk_state.daily_loss_usd),
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
        except Exception as e:
            logger.debug(f"[health_state] update failed: {e}")

    def _send_equity_milestone(self, equity: dict) -> None:
        """v12.5: Telegram equity milestone (every $5 change, throttled to 1/min)."""
        if not hasattr(self, "_last_milestone") or (
            abs(equity["total"] - self._last_milestone) >= 5.0
        ):
            self._last_milestone = equity["total"]
            # Store task reference to prevent GC before completion
            bg = getattr(self, "_background_tasks", set())
            if not bg:
                self._background_tasks = bg
            task = asyncio.create_task(
                _get_notifier().equity_milestone(
                    cash=equity["cash"],
                    assets_value=equity["assets"],
                    total=equity["total"],
                    items_count=int(equity["count"]),
                )
            )
            bg.add(task)
            task.add_done_callback(bg.discard)

    def _log_cycle_diag(self, game_id: str, candidates_len: int, buys_len: int) -> None:
        """v15.0: Sanitized cycle log + periodic MultiSource diagnostic."""
        logger.debug(
            f"[v15.0 CYCLE] game={game_id} cycle={self.deep_scan_counter} "
            f"candidates={candidates_len} buys={buys_len}"
        )

        if self.deep_scan_counter % 10 == 0:
            cb_stats = self.client.circuit_breaker_status()
            logger.info(
                f"[v15.0 DIAG] CB: state={cb_stats['state']}, "
                f"opens={cb_stats['total_opens']}, "
                f"fails={cb_stats['consecutive_failures']}"
            )
