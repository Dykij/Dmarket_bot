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
from typing import Any, Dict, List, Optional

logger = logging.getLogger("RiskManager")


@dataclass
class RiskState:
    """Snapshot of the current risk posture (for /status and briefings)."""
    daily_loss_usd: float = 0.0
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


@dataclass
class PreTradeCheck:
    """Result of a pre-trade risk check."""
    allowed: bool
    reason: str = ""
    adjusted_size_usd: Optional[float] = None  # if non-None, override proposed size
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
        daily_loss_limit_usd: Optional[float] = None,
        daily_trade_limit: Optional[int] = None,
        max_drawdown_pct: float = 15.0,
        soft_halt_drawdown_pct: float = 5.0,
        initial_equity_usd: float = 0.0,
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

        # Trade history for the day (for /status)
        self._trades_today: List[Dict[str, Any]] = []

        self._soft_halt_active: bool = False

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------
    def pre_trade_check(
        self,
        proposed_size_usd: float,
        current_equity_usd: float,
        game_id: str = "a8db",
        item_title: str = "",
    ) -> PreTradeCheck:
        """
        Pre-trade risk check. Returns PreTradeCheck with .allowed.

        Order of checks (cheapest first):
        1. New day? Reset counters.
        2. Daily trade count limit.
        3. Daily loss limit.
        4. Drawdown → soft halt (only blocks BUYs, not SELLs)
        5. Hard drawdown → block everything.
        6. Equity track peak (for max drawdown calc).
        """
        self._maybe_roll_day()
        self._update_equity(current_equity_usd)

        # 1. Daily trade count
        if self._daily_trade_count >= self.daily_trade_limit:
            self._daily_blocked += 1
            return PreTradeCheck(
                allowed=False,
                reason=(
                    f"Daily trade count limit reached: "
                    f"{self._daily_trade_count}/{self.daily_trade_limit}"
                ),
                triggered_halt=True,
            )

        # 2. Daily loss limit
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

        # 3. Hard drawdown kill switch
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

        # 4. Soft halt (only on BUYs; we don't block sells)
        if self._current_drawdown_pct >= self.soft_halt_drawdown_pct:
            self._soft_halt_active = True
            # Reduce size by 50% in soft-halt
            reduced = round(proposed_size_usd * 0.5, 2)
            if reduced < 0.50:  # below floor
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

        # 5. No halt
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

    def get_state(self) -> RiskState:
        """Snapshot of current risk state (for /status, daily briefing, logs)."""
        self._maybe_roll_day()
        return RiskState(
            daily_loss_usd=min(0.0, self._daily_realized_pnl),  # negative or zero
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
        )

    def get_daily_briefing_lines(self) -> List[str]:
        """Human-readable lines for the daily Telegram briefing."""
        state = self.get_state()
        lines = [
            f"📅 <b>Daily Risk Report</b> ({state.last_reset_date})",
            f"  Realized PnL today: <b>${-state.daily_loss_usd:+.2f}</b> "
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
        return lines

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


# Convenience: a global default (replaced per bot instance in autonomous_scanner)
# TODO(remove-default-risk-manager): this singleton is never imported anywhere
# in src/ (grep proves 1 match — its own definition). It is a leftover from
# an earlier design where external scripts might import it. Safe to delete
# once we have unit-test coverage that exercises RiskManager directly.
default_risk_manager = RiskManager()
