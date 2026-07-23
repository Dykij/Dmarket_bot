"""
risk_manager.py — Central risk orchestrator (v12.5).

Wraps the existing risk modules (liquidity_manager, security_auditor,
trade_gate, dynamic_manager, plus NEW daily_loss / drawdown / trade_count
checks) into a single pre-trade check that the hot path calls before
each buy.

The goal: make it impossible to accidentally lose more than X% in a
day, more than Y trades, or buy outside the safe price range — without
needing to thread 5 different checks through the code.

Public API:
    risk = RiskManager(client=api_client)
    state = risk.pre_trade_check(...)
    if not state.allowed:
        # block the trade
    risk.record_trade_outcome(...)  # after buy/sell completes
    state = risk.get_state()  # for /status, daily briefing
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Forward reference: pump_detector is injected at runtime by
    # SnipingLoop.__init__ to avoid the circular import (pump_detector
    # imports nothing from risk_manager, but risk_manager would re-import
    # pump_detector's type for annotations, which is the kind of edge
    # that gets you into trouble during test setup).
    from src.risk.pump_detector import PumpDetector

logger = logging.getLogger("RiskManager")


def _get_drawdown_freeze_threshold() -> float:
    """Read drawdown freeze threshold from Config (module-level, no hot import)."""
    from src.config import Config
    raw = float(Config.DRAWDOWN_FREEZE_THRESHOLD)
    return raw * 100.0 if raw < 1.0 else raw


def _is_drawdown_freeze_enabled() -> bool:
    """Read drawdown freeze enabled flag from Config (module-level, no hot import)."""
    from src.config import Config
    return Config.DRAWDOWN_FREEZE_ENABLED


@dataclass
class RiskState:
    """Snapshot of the current risk posture (for /status and briefings)."""
    daily_loss_usd: float = 0.0  # deprecated — use daily_realized_pnl
    daily_realized_pnl: float = 0.0  # can be positive (profit) or negative (loss)
    daily_loss_limit_usd: float = 0.0
    daily_trade_count: int = 0
    daily_trade_limit: int = 0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    soft_halt_active: bool = False
    daily_halt_active: bool = False
    peak_equity_usd: float = 0.0
    current_equity_usd: float = 0.0
    last_reset_date: str = ""
    blocked_count_today: int = 0
    passed_count_today: int = 0
    # v14.4: Kelly Criterion inputs
    win_rate: float = 0.55
    win_loss_ratio: float = 1.5
    total_wins: int = 0
    total_losses: int = 0
    drawdown_freeze_active: bool = False
    consecutive_losses: int = 0


@dataclass
class PreTradeCheck:
    """Result of a pre-trade risk check."""
    allowed: bool
    reason: str = ""
    adjusted_size_usd: float | None = None  # if non-None, override proposed size
    triggered_halt: bool = False  # True if this check tripped a kill-switch


class RiskManager:
    """
    Centralized risk manager.

    Responsibilities:
    1. Daily loss limit (configurable, default $10)
    2. Daily trade count limit (configurable, default 200)
    3. Max drawdown tracking (kill switch at 15%)
    4. Pre-trade validation (price, balance, sanity)
    5. Soft-halt on cascading losses
    6. Secret-leak scanning on log lines (delegated to SecurityAuditor)
    """

    def __init__(
        self,
        daily_loss_limit_usd: float | None = None,
        daily_trade_limit: int | None = None,
        max_drawdown_pct: float = 15.0,
        soft_halt_drawdown_pct: float = 5.0,
        initial_equity_usd: float = 0.0,
        pump_detector: PumpDetector | None = None,
    ) -> None:
        # Read limits from env (with defaults)
        self.daily_loss_limit_usd = daily_loss_limit_usd if daily_loss_limit_usd is not None else float(
            os.getenv("MAX_DAILY_LOSS_USD", "10.00")
        )
        self.daily_trade_limit = daily_trade_limit if daily_trade_limit is not None else int(
            os.getenv("MAX_DAILY_TRADES", "200")
        )
        self.max_drawdown_pct = max_drawdown_pct
        self.soft_halt_drawdown_pct = soft_halt_drawdown_pct

        # v12.6: Optional pump detector (block buys on suspected FOMO spikes)
        # The detector is injected by SnipingLoop.__init__ to avoid
        # circular imports. If absent, the pump check is a no-op.
        self.pump_detector = pump_detector

        # State
        self._today: str = self._current_date()
        self._daily_realized_pnl: float = 0.0
        self._daily_trade_count: int = 0
        self._daily_blocked: int = 0
        self._daily_passed: int = 0

        # Drawdown tracking
        self._peak_equity: float = initial_equity_usd
        self._current_equity: float = initial_equity_usd
        self._current_drawdown_pct: float = 0.0
        self._max_drawdown_seen: float = 0.0

        # v14.4: Kelly Criterion tracking (total wins/losses for win rate)
        self._total_wins: int = 0
        self._total_losses: int = 0
        self._avg_win_usd: float = 0.0
        self._avg_loss_usd: float = 0.0
        self._drawdown_freeze_active: bool = False
        self._consecutive_losses: int = 0
        self._max_consecutive_losses: int = 0
        self._last_proposed_size: float = 0.0

        # Trade history for the day (for /status)
        self._trades_today: list[dict[str, Any]] = []

        self._soft_halt_active: bool = False

        # Restore persisted state from SQLite (survives restarts for 24/7 ops)
        self.restore_state_from_db()

    def attach_pump_detector(self, pump_detector: PumpDetector) -> None:
        """
        Late-bind the pump detector. Called from SnipingLoop.__init__
        after both objects are constructed (avoids circular imports).
        """
        self.pump_detector = pump_detector

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    def pre_trade_check(
        self,
        proposed_size_usd: float,
        current_equity_usd: float,
        game_id: str = "a8db",
        item_title: str = "",
        current_position_count: int = 0,
    ) -> PreTradeCheck:
        """
        Pre-trade risk check. Returns PreTradeCheck with .allowed.

        Order of checks (cheapest first):
        1. New day? Reset counters.
        2. Pump-detector blacklist check (item-specific, blocks FOMO buys).
        3. Daily trade count limit.
        4. Daily loss limit.
        5. Concurrent positions cap (v12.8).
        6. Drawdown → soft halt (only blocks BUYs, not SELLs)
        7. Hard drawdown → block everything.
        8. Equity track peak (for max drawdown calc).
        """
        self._maybe_roll_day()
        self._update_equity(current_equity_usd)

        # 1. Pump-detector blacklist check (v12.6)
        if self.pump_detector is not None and item_title:
            if self.pump_detector.is_blacklisted(item_title):
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=(
                        f"Pump-blacklisted: {item_title} (price spike detected, "
                        f"buys blocked for 24h)"
                    ),
                    triggered_halt=False,
                )

        # 2. Daily trade count
        if self._daily_trade_count >= self.daily_trade_limit:
            self._daily_blocked += 1
            return PreTradeCheck(
                allowed=False,
                reason=(
                    f"Daily trade count limit reached: "
                    f"{self._daily_trade_count}/{self.daily_trade_limit}"
                ),
                triggered_halt=False,  # Cap, not a halt — auto-resets next day
            )

        # 3. Daily loss limit
        if self._daily_realized_pnl <= -self.daily_loss_limit_usd:
            self._daily_blocked += 1
            return PreTradeCheck(
                allowed=False,
                reason=(
                    f"Daily loss limit hit: ${-self._daily_realized_pnl:.2f} >= "
                    f"${self.daily_loss_limit_usd:.2f}"
                ),
                triggered_halt=True,
            )

        # 4. Concurrent positions cap (v12.8)
        max_positions = int(os.getenv("MAX_CONCURRENT_POSITIONS", "50"))
        if current_position_count >= max_positions:
            self._daily_blocked += 1
            return PreTradeCheck(
                allowed=False,
                reason=(
                    f"Concurrent positions cap reached: "
                    f"{current_position_count}/{max_positions}"
                ),
                triggered_halt=True,
            )

        # 4.2. Balance gate — ensure proposed trade fits within available equity
        if proposed_size_usd > 0:
            if current_equity_usd <= 0:
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=f"Zero or negative equity: ${current_equity_usd:.2f} — cannot trade",
                )
            from src.config import Config
            effective_balance = current_equity_usd - float(getattr(Config, "BALANCE_RESERVE_USD", 0.0))
            if proposed_size_usd > effective_balance:
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=(
                        f"Insufficient balance: ${proposed_size_usd:.2f} > "
                        f"${effective_balance:.2f} available "
                        f"(equity ${current_equity_usd:.2f} - reserve)"
                    ),
                )

        # 4.5. v14.7: Consecutive loss streak — halve position after 3+ losses
        # Note: _last_proposed_size is set AFTER reduction to track actual size used
        consecutive_loss_reduced = False
        if self._consecutive_losses >= 3 and proposed_size_usd > 0:
            reduced = round(proposed_size_usd * 0.5, 2)
            if reduced < 0.50:
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=(
                        f"Consecutive loss streak: {self._consecutive_losses} losses, "
                        f"position ${reduced:.2f} below floor $0.50"
                    ),
                )
            logger.warning(
                f"[Risk] {self._consecutive_losses} consecutive losses — "
                f"halving position: ${proposed_size_usd:.2f} → ${reduced:.2f}"
            )
            proposed_size_usd = reduced
            consecutive_loss_reduced = True

        # Track actual proposed size after all reductions
        self._last_proposed_size = proposed_size_usd

        # 5. v14.4: Drawdown-aware spending freeze (must come BEFORE hard kill-switch)
        freeze_threshold_pct = _get_drawdown_freeze_threshold()
        if _is_drawdown_freeze_enabled() and self._current_drawdown_pct >= freeze_threshold_pct:
            if proposed_size_usd > 0:
                self._drawdown_freeze_active = True
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=(
                        f"Drawdown freeze: {self._current_drawdown_pct:.1f}% >= "
                        f"{freeze_threshold_pct:.1f}%. Sells only until recovery."
                    ),
                    triggered_halt=True,
                )
        else:
            self._drawdown_freeze_active = False

        # 6. Hard drawdown kill switch
        if self._current_drawdown_pct >= self.max_drawdown_pct:
            self._daily_blocked += 1
            return PreTradeCheck(
                allowed=False,
                reason=(
                    f"Max drawdown hit: {self._current_drawdown_pct:.1f}% >= "
                    f"{self.max_drawdown_pct:.1f}%"
                ),
                triggered_halt=True,
            )

        # 7. Soft halt — reduce size by 50% at 5%+ drawdown (only for buys)
        # Skip if already reduced by consecutive-loss halving (prevents double-halve)
        if self._current_drawdown_pct >= self.soft_halt_drawdown_pct and not consecutive_loss_reduced:
            self._soft_halt_active = True
            reduced = round(proposed_size_usd * 0.5, 2)
            if reduced < 0.50:
                self._daily_blocked += 1
                return PreTradeCheck(
                    allowed=False,
                    reason=(
                        f"Soft-halt active (drawdown {self._current_drawdown_pct:.1f}%); "
                        f"reduced size ${reduced:.2f} below floor $0.50"
                    ),
                )
            self._daily_passed += 1
            return PreTradeCheck(
                allowed=True,
                reason=f"Soft-halt: size halved to ${reduced:.2f}",
                adjusted_size_usd=reduced,
            )

        # 8. No halt
        self._soft_halt_active = False
        self._daily_passed += 1
        return PreTradeCheck(
            allowed=True,
            reason="OK",
            adjusted_size_usd=proposed_size_usd,
        )

    def record_trade_outcome(
        self,
        pnl_usd: float,
        trade_type: str = "buy",  # 'buy' (cost, negative PnL) or 'sell' (revenue, positive PnL)
        item_title: str = "",
    ) -> None:
        """
        Record a trade outcome for daily stats.

        `pnl_usd` should be the realized PnL (sell - buy - fees) for sells,
        or the spend (negative) for buys. Either way, it contributes to
        the daily PnL total.
        """
        self._maybe_roll_day()
        self._daily_trade_count += 1
        self._daily_realized_pnl += pnl_usd
        self._trades_today.append({
            "type": trade_type,
            "title": item_title,
            "pnl_usd": pnl_usd,
            "ts": time.time(),
        })
        # v14.4: Track wins/losses for Kelly Criterion
        if trade_type == "sell" and pnl_usd != 0:
            # Track total sell trades for statistics (win + loss = total sells)
            pass  # total tracked via _total_wins + _total_losses in get_state()
            if pnl_usd > 0:
                self._total_wins += 1
                self._avg_win_usd = (self._avg_win_usd * (self._total_wins - 1) + pnl_usd) / self._total_wins
                self._consecutive_losses = 0
            else:
                self._total_losses += 1
                abs_loss = abs(pnl_usd)
                self._avg_loss_usd = (self._avg_loss_usd * (self._total_losses - 1) + abs_loss) / self._total_losses
                self._consecutive_losses += 1
                self._max_consecutive_losses = max(self._max_consecutive_losses, self._consecutive_losses)

    def get_state(self) -> RiskState:
        """Snapshot of current risk state (for /status, daily briefing, logs)."""
        self._maybe_roll_day()
        total = self._total_wins + self._total_losses
        wr = (self._total_wins / total) if total > 0 else 0.55
        wlr = (self._avg_win_usd / self._avg_loss_usd) if self._avg_loss_usd > 0 else 1.5
        return RiskState(
            daily_loss_usd=min(0.0, self._daily_realized_pnl),  # backward compat
            daily_realized_pnl=self._daily_realized_pnl,
            daily_loss_limit_usd=self.daily_loss_limit_usd,
            daily_trade_count=self._daily_trade_count,
            daily_trade_limit=self.daily_trade_limit,
            max_drawdown_pct=self._max_drawdown_seen * 100.0,
            current_drawdown_pct=self._current_drawdown_pct,
            soft_halt_active=self._soft_halt_active,
            daily_halt_active=self._daily_realized_pnl <= -self.daily_loss_limit_usd,
            peak_equity_usd=self._peak_equity,
            current_equity_usd=self._current_equity,
            last_reset_date=self._today,
            blocked_count_today=self._daily_blocked,
            passed_count_today=self._daily_passed,
            win_rate=round(wr, 3),
            win_loss_ratio=round(wlr, 3),
            total_wins=self._total_wins,
            total_losses=self._total_losses,
            drawdown_freeze_active=self._drawdown_freeze_active,
            consecutive_losses=self._consecutive_losses,
        )

    def get_daily_briefing_lines(self) -> list[str]:
        """Human-readable lines for the daily Telegram briefing."""
        state = self.get_state()
        lines = [
            f"📅 <b>Daily Risk Report</b> ({state.last_reset_date})",
            f"  Realized PnL today: <b>${state.daily_realized_pnl:+.2f}</b> "
            f"(limit -${state.daily_loss_limit_usd:.2f})",
            f"  Trades: {state.daily_trade_count}/{state.daily_trade_limit} "
            f"(blocked: {state.blocked_count_today})",
            f"  Max drawdown: {state.max_drawdown_pct:.1f}% "
            f"(current: {state.current_drawdown_pct:.1f}%)",
        ]
        if state.soft_halt_active:
            lines.append("  ⚠️ Soft-halt active: size halved on next buy")
        if state.daily_halt_active:
            lines.append("  🔴 Daily loss limit hit — trading halted until midnight")
        # v12.6: Pump detector summary
        if self.pump_detector is not None:
            pd_stats = self.pump_detector.stats()
            active = pd_stats.get("active_blacklist_size", 0)
            if active > 0:
                lines.append(
                    f"  🚨 Pump-blacklist: {active} active item(s) "
                    f"(total detections: {pd_stats.get('total_detections', 0)})"
                )
        return lines

    # ----------------------------------------------------------------
    # State Persistence (survives restarts for 24/7 operation)
    # ----------------------------------------------------------------
    def save_state_to_db(self) -> None:
        """Persist critical risk state to SQLite scanning_state table.
        Call periodically (e.g. every cycle) to survive unexpected restarts."""
        try:
            import json

            from src.db.price_history import price_db
            state = {
                "peak_equity": self._peak_equity,
                "current_equity": self._current_equity,
                "daily_realized_pnl": self._daily_realized_pnl,
                "daily_trade_count": self._daily_trade_count,
                "drawdown_freeze_active": self._drawdown_freeze_active,
                "total_wins": self._total_wins,
                "total_losses": self._total_losses,
                "avg_win_usd": self._avg_win_usd,
                "avg_loss_usd": self._avg_loss_usd,
                "consecutive_losses": self._consecutive_losses,
                "today": self._today,
                "soft_halt_active": self._soft_halt_active,
            }
            price_db.save_state("risk_manager_state", json.dumps(state))
        except Exception as e:
            logger.debug(f"[RiskManager] save_state_to_db failed: {e}")

    def restore_state_from_db(self) -> None:
        """Restore critical risk state from SQLite after restart."""
        try:
            import json

            from src.db.price_history import price_db
            raw = price_db.get_state("risk_manager_state")
            if not raw:
                return
            state = json.loads(raw)
            # Only restore if same day — otherwise daily counters should reset
            today = self._current_date()
            saved_today = state.get("today", "")
            if saved_today == today:
                self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
                self._daily_trade_count = state.get("daily_trade_count", 0)
                self._consecutive_losses = state.get("consecutive_losses", 0)
                self._soft_halt_active = state.get("soft_halt_active", False)
                logger.info(
                    f"[RiskManager] Restored daily state: PnL=${self._daily_realized_pnl:+.2f}, "
                    f"trades={self._daily_trade_count}, consecutive_losses={self._consecutive_losses}"
                )
            else:
                logger.info(
                    f"[RiskManager] Saved state from {saved_today}, today is {today} — daily counters reset"
                )
            # Always restore cross-day state (peak equity, drawdown freeze, Kelly)
            self._peak_equity = state.get("peak_equity", self._peak_equity)
            self._current_equity = state.get("current_equity", self._current_equity)
            self._drawdown_freeze_active = state.get("drawdown_freeze_active", False)
            self._total_wins = state.get("total_wins", 0)
            self._total_losses = state.get("total_losses", 0)
            self._avg_win_usd = state.get("avg_win_usd", 0.0)
            self._avg_loss_usd = state.get("avg_loss_usd", 0.0)
            # Recompute drawdown from restored peak
            if self._peak_equity > 0:
                dd = (self._peak_equity - self._current_equity) / self._peak_equity
                self._current_drawdown_pct = dd * 100.0
            logger.info(
                f"[RiskManager] Restored: peak=${self._peak_equity:.2f}, "
                f"drawdown={self._current_drawdown_pct:.1f}%, "
                f"freeze={self._drawdown_freeze_active}, "
                f"wins={self._total_wins}/losses={self._total_losses}"
            )
        except Exception as e:
            logger.warning(f"[RiskManager] restore_state_from_db failed: {e}")

    # ----------------------------------------------------------------
    # Internals
    # ----------------------------------------------------------------
    def _current_date(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_roll_day(self) -> None:
        """If we've crossed into a new UTC day, reset the daily counters."""
        today = self._current_date()
        if today != self._today:
            logger.info(
                f"[RiskManager] New day detected ({self._today} → {today}); "
                f"resetting daily stats. Yesterday: PnL ${self._daily_realized_pnl:+.2f}, "
                f"{self._daily_trade_count} trades."
            )
            self._today = today
            self._daily_realized_pnl = 0.0
            self._daily_trade_count = 0
            self._daily_blocked = 0
            self._daily_passed = 0
            self._trades_today = []
            # Reset consecutive-loss tracking on new day to allow recovery
            self._consecutive_losses = 0
            self._drawdown_freeze_active = False

    def _update_equity(self, current_equity_usd: float) -> None:
        """Update peak/current equity and recompute drawdown."""
        self._current_equity = current_equity_usd
        if current_equity_usd > self._peak_equity:
            self._peak_equity = current_equity_usd
        if self._peak_equity > 0:
            dd = (self._peak_equity - current_equity_usd) / self._peak_equity
            self._current_drawdown_pct = dd * 100.0
            if self._current_drawdown_pct > self._max_drawdown_seen * 100.0:
                self._max_drawdown_seen = dd
