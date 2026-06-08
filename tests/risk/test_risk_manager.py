"""
Unit tests for src.risk.risk_manager (v12.5 + v12.6 pump integration).

Coverage:
- pre_trade_check: pump-blacklist block (v12.6), daily trade count,
  daily loss, hard drawdown, soft halt (size halving), soft halt floor,
  happy path
- record_trade_outcome: counters increment, pnl accumulates
- get_state: snapshot accuracy, daily_halt_active, soft_halt_active
- get_daily_briefing_lines: all 4 lines + soft/daily halt warnings +
  pump summary
- _maybe_roll_day: day rollover resets all counters
- _update_equity: peak tracking (only updates on new high),
  drawdown math
- attach_pump_detector: late-binding works
- pump_detector is None: pump check is no-op (backward compat)
- env var overrides

No external API. No DB. ~1s total runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.risk.fatal_errors import (  # noqa: E402
    AuthError,
    ConfigError,
    DatabaseCorruption,
    LogicBug,
    classify,
    exit_code_for,
    is_fatal,
)
from src.risk.risk_manager import (  # noqa: E402
    RiskManager,
    RiskState,
)


# =====================================================================
# Helpers
# =====================================================================

def _make_manager(
    *,
    daily_loss_limit: float = 10.0,
    daily_trade_limit: int = 200,
    max_drawdown_pct: float = 15.0,
    soft_halt_drawdown_pct: float = 5.0,
    initial_equity_usd: float = 0.0,
    pump_detector=None,
) -> RiskManager:
    return RiskManager(
        daily_loss_limit_usd=daily_loss_limit,
        daily_trade_limit=daily_trade_limit,
        max_drawdown_pct=max_drawdown_pct,
        soft_halt_drawdown_pct=soft_halt_drawdown_pct,
        initial_equity_usd=initial_equity_usd,
        pump_detector=pump_detector,
    )


# =====================================================================
# TestRiskManagerConstructor
# =====================================================================

class TestRiskManagerConstructor:
    def test_default_values(self) -> None:
        rm = _make_manager()
        assert rm.daily_loss_limit_usd == 10.0
        assert rm.daily_trade_limit == 200
        assert rm.max_drawdown_pct == 15.0
        assert rm.soft_halt_drawdown_pct == 5.0
        assert rm.pump_detector is None  # default: no detector

    def test_initial_state_clean(self) -> None:
        rm = _make_manager(initial_equity_usd=50.0)
        s = rm.get_state()
        assert s.daily_trade_count == 0
        assert s.daily_loss_usd == 0.0
        assert s.daily_halt_active is False
        assert s.soft_halt_active is False
        assert s.max_drawdown_pct == 0.0
        assert s.current_drawdown_pct == 0.0
        assert s.peak_equity_usd == 50.0
        assert s.current_equity_usd == 50.0

    def test_env_override_loss_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_DAILY_LOSS_USD", "5.50")
        monkeypatch.setenv("MAX_DAILY_TRADES", "50")
        rm = RiskManager()  # picks up env vars
        assert rm.daily_loss_limit_usd == 5.50
        assert rm.daily_trade_limit == 50

    def test_attach_pump_detector(self) -> None:
        rm = _make_manager()
        assert rm.pump_detector is None
        det = MagicMock()
        rm.attach_pump_detector(det)
        assert rm.pump_detector is det


# =====================================================================
# TestPreTradeCheckHappyPath
# =====================================================================

class TestPreTradeCheckHappyPath:
    def test_clean_state_allows_trade(self) -> None:
        rm = _make_manager(initial_equity_usd=50.0)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
        )
        assert result.allowed is True
        assert result.adjusted_size_usd == 5.0
        assert "OK" in result.reason
        assert result.triggered_halt is False

    def test_passed_count_increments(self) -> None:
        rm = _make_manager()
        for _ in range(3):
            rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert rm.get_state().passed_count_today == 3
        assert rm.get_state().blocked_count_today == 0

    def test_equity_update_via_check(self) -> None:
        """pre_trade_check must update peak equity as it observes prices."""
        rm = _make_manager(initial_equity_usd=50.0)
        # First call sees equity = 60 → new peak
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=60.0)
        assert rm.get_state().peak_equity_usd == 60.0
        # Second call sees equity = 55 → drawdown but no new peak
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=55.0)
        s = rm.get_state()
        assert s.peak_equity_usd == 60.0  # peak unchanged
        assert s.current_drawdown_pct == pytest.approx(8.33, rel=1e-2)

    def test_zero_equity_does_not_divide_by_zero(self) -> None:
        """If equity is 0 and peak is 0, drawdown calc must not crash."""
        rm = _make_manager()
        result = rm.pre_trade_check(
            proposed_size_usd=1.0,
            current_equity_usd=0.0,  # no balance
        )
        # No crash, drawdown stays 0
        assert result.allowed is True
        assert rm.get_state().current_drawdown_pct == 0.0


# =====================================================================
# TestPreTradeCheckDailyTradeLimit
# =====================================================================

class TestPreTradeCheckDailyTradeLimit:
    def test_blocks_at_limit(self) -> None:
        rm = _make_manager(daily_trade_limit=3)
        # First 3 pass (or not, depending on other checks) — for THIS
        # test we just want to count.
        # Use the path that increments trade count: record_trade_outcome
        for _ in range(3):
            rm.record_trade_outcome(pnl_usd=-1.0, trade_type="buy")
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is False
        assert "Daily trade count limit reached" in result.reason
        assert result.triggered_halt is True

    def test_limit_at_exact_boundary(self) -> None:
        """At limit (count == limit), the next call must block."""
        rm = _make_manager(daily_trade_limit=2)
        rm.record_trade_outcome(pnl_usd=-1.0)
        rm.record_trade_outcome(pnl_usd=-1.0)
        # count=2, limit=2 → >= → block
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is False

    def test_below_limit_allows(self) -> None:
        rm = _make_manager(daily_trade_limit=5)
        rm.record_trade_outcome(pnl_usd=-1.0)
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is True

    def test_blocked_counter_increments(self) -> None:
        rm = _make_manager(daily_trade_limit=1)
        rm.record_trade_outcome(pnl_usd=-1.0)
        for _ in range(3):
            rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert rm.get_state().blocked_count_today == 3


# =====================================================================
# TestPreTradeCheckDailyLossLimit
# =====================================================================

class TestPreTradeCheckDailyLossLimit:
    def test_blocks_at_loss_limit(self) -> None:
        rm = _make_manager(daily_loss_limit=10.0)
        # Lose $10 cumulative → pnl = -10 → block
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="buy")
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="buy")
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is False
        assert "Daily loss limit hit" in result.reason
        assert result.triggered_halt is True

    def test_just_below_loss_limit_allows(self) -> None:
        rm = _make_manager(daily_loss_limit=10.0)
        rm.record_trade_outcome(pnl_usd=-9.99)
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is True

    def test_profitable_day_never_blocks_on_loss(self) -> None:
        rm = _make_manager(daily_loss_limit=10.0)
        rm.record_trade_outcome(pnl_usd=+20.0)
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert result.allowed is True

    def test_daily_halt_active_flag(self) -> None:
        rm = _make_manager(daily_loss_limit=10.0)
        rm.record_trade_outcome(pnl_usd=-10.0)
        assert rm.get_state().daily_halt_active is True

    def test_daily_halt_inactive_at_break_even(self) -> None:
        rm = _make_manager(daily_loss_limit=10.0)
        rm.record_trade_outcome(pnl_usd=0.0)
        assert rm.get_state().daily_halt_active is False


# =====================================================================
# TestPreTradeCheckDrawdown
# =====================================================================

class TestPreTradeCheckDrawdown:
    def test_hard_drawdown_blocks(self) -> None:
        """15% DD = max_drawdown_pct default → block."""
        rm = _make_manager(
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # peak=100, current=85 → 15% DD
        result = rm.pre_trade_check(
            proposed_size_usd=1.0,
            current_equity_usd=85.0,
        )
        assert result.allowed is False
        assert "Max drawdown hit" in result.reason
        assert result.triggered_halt is True

    def test_just_above_soft_halt_below_hard(self) -> None:
        """5% DD < 15% hard but >= 5% soft → size halved."""
        rm = _make_manager(
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # peak=100, current=94 → 6% DD
        result = rm.pre_trade_check(
            proposed_size_usd=10.0,
            current_equity_usd=94.0,
        )
        assert result.allowed is True
        assert result.adjusted_size_usd == 5.0  # halved
        assert "Soft-halt" in result.reason
        assert rm.get_state().soft_halt_active is True

    def test_soft_halt_below_floor_blocks(self) -> None:
        """If halving produces <$0.50, block entirely."""
        rm = _make_manager(
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # peak=100, current=90 → 10% DD, soft-halt active
        result = rm.pre_trade_check(
            proposed_size_usd=0.60,  # halved = 0.30 < 0.50
            current_equity_usd=90.0,
        )
        assert result.allowed is False
        assert "below floor" in result.reason

    def test_soft_halt_floor_exact(self) -> None:
        """If halved = exactly $0.50, allow (boundary is strict <)."""
        rm = _make_manager(
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # proposed=1.00 → halved=0.50 → NOT < 0.50 → allow
        result = rm.pre_trade_check(
            proposed_size_usd=1.00,
            current_equity_usd=90.0,  # 10% DD, soft-halt
        )
        assert result.allowed is True
        assert result.adjusted_size_usd == 0.50

    def test_no_drawdown_no_halt(self) -> None:
        rm = _make_manager(initial_equity_usd=50.0)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=51.0,  # up 2%
        )
        assert result.allowed is True
        assert result.adjusted_size_usd == 5.0
        assert rm.get_state().soft_halt_active is False

    def test_max_drawdown_seen_persists_after_recovery(self) -> None:
        """Once we've hit 10% DD, max_drawdown_seen stays 10% even after recovery."""
        rm = _make_manager(initial_equity_usd=100.0)
        # First call: peak=100, current=90 → 10% DD
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=90.0)
        # Second call: equity recovers to 100 → current DD = 0, but max_seen stays
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=100.0)
        s = rm.get_state()
        assert s.max_drawdown_pct == pytest.approx(10.0, rel=1e-6)
        assert s.current_drawdown_pct == 0.0  # recovered


# =====================================================================
# TestPreTradeCheckPumpDetector (v12.6)
# =====================================================================

class TestPreTradeCheckPumpDetector:
    """v12.6: pump-blacklist block runs FIRST (item-specific, no global halt)."""

    def _blacklist(self, title: str, det: MagicMock) -> None:
        det.is_blacklisted.return_value = title == "BLACKLISTED"

    def test_blacklisted_item_blocked(self) -> None:
        det = MagicMock()
        det.is_blacklisted.return_value = True
        rm = _make_manager(pump_detector=det)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
            item_title="BLACKLISTED",
        )
        assert result.allowed is False
        assert "Pump-blacklisted" in result.reason
        assert "BLACKLISTED" in result.reason
        assert result.triggered_halt is False  # item-specific, not global

    def test_clean_item_allowed(self) -> None:
        det = MagicMock()
        det.is_blacklisted.return_value = False
        rm = _make_manager(pump_detector=det)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
            item_title="CLEAN",
        )
        assert result.allowed is True
        det.is_blacklisted.assert_called_once_with("CLEAN")

    def test_pump_check_runs_before_global_halts(self) -> None:
        """
        Even when global halts are active, pump-blacklist must
        trigger first and the block must be classified as
        item-specific (triggered_halt=False), not a global kill-switch.
        """
        det = MagicMock()
        det.is_blacklisted.return_value = True
        rm = _make_manager(
            pump_detector=det,
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # Trigger global drawdown by also feeding a low equity
        result = rm.pre_trade_check(
            proposed_size_usd=1.0,
            current_equity_usd=80.0,  # 20% DD > 15% hard
            item_title="BLACKLISTED",
        )
        # The pump block must be the one returned (not the drawdown).
        assert result.allowed is False
        assert "Pump-blacklisted" in result.reason
        assert result.triggered_halt is False  # item-specific

    def test_no_pump_detector_is_backward_compatible(self) -> None:
        """When pump_detector is None, the check is a no-op (old callers)."""
        rm = _make_manager(pump_detector=None)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
            item_title="ANY",
        )
        assert result.allowed is True

    def test_pump_block_increments_blocked_counter(self) -> None:
        det = MagicMock()
        det.is_blacklisted.return_value = True
        rm = _make_manager(pump_detector=det)
        rm.pre_trade_check(proposed_size_usd=5.0, current_equity_usd=50.0, item_title="X")
        assert rm.get_state().blocked_count_today == 1

    def test_pump_block_does_not_count_as_passed(self) -> None:
        det = MagicMock()
        det.is_blacklisted.return_value = True
        rm = _make_manager(pump_detector=det)
        rm.pre_trade_check(proposed_size_usd=5.0, current_equity_usd=50.0, item_title="X")
        assert rm.get_state().passed_count_today == 0

    def test_empty_item_title_skips_pump_check(self) -> None:
        """Empty title → no pump check (caller didn't provide one)."""
        det = MagicMock()
        det.is_blacklisted.return_value = False
        rm = _make_manager(pump_detector=det)
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
            item_title="",  # empty
        )
        assert result.allowed is True
        det.is_blacklisted.assert_not_called()


# =====================================================================
# TestPreTradeCheckCheckOrder
# =====================================================================

class TestPreTradeCheckCheckOrder:
    """
    Verify the documented order: pump → daily_count → daily_loss → hard_dd
    → soft_halt → OK. Important for behaviour consistency.
    """

    def test_pump_blocks_before_daily_count(self) -> None:
        """If both conditions hit, pump-blacklist must win (it runs first)."""
        det = MagicMock()
        det.is_blacklisted.return_value = True
        rm = _make_manager(
            pump_detector=det,
            daily_trade_limit=1,
        )
        rm.record_trade_outcome(pnl_usd=-1.0)  # count=1=limit
        result = rm.pre_trade_check(
            proposed_size_usd=5.0,
            current_equity_usd=50.0,
            item_title="BLACKLISTED",
        )
        assert "Pump-blacklisted" in result.reason
        assert "Daily trade count" not in result.reason

    def test_daily_count_blocks_before_loss(self) -> None:
        rm = _make_manager(
            daily_trade_limit=1,
            daily_loss_limit=10.0,
        )
        rm.record_trade_outcome(pnl_usd=-1.0)  # count=1=limit
        rm.record_trade_outcome(pnl_usd=-20.0)  # also over loss limit
        result = rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        assert "Daily trade count" in result.reason
        assert "Daily loss" not in result.reason

    def test_daily_loss_blocks_before_drawdown(self) -> None:
        rm = _make_manager(
            daily_loss_limit=10.0,
            max_drawdown_pct=15.0,
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        # Over loss limit AND over DD
        rm.record_trade_outcome(pnl_usd=-15.0)  # -$15 = -150% of limit
        result = rm.pre_trade_check(
            proposed_size_usd=1.0,
            current_equity_usd=80.0,  # 20% DD
        )
        assert "Daily loss" in result.reason
        assert "Max drawdown" not in result.reason


# =====================================================================
# TestRecordTradeOutcome
# =====================================================================

class TestRecordTradeOutcome:
    def test_buy_increments_count(self) -> None:
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-2.0, trade_type="buy", item_title="AK-47")
        assert rm.get_state().daily_trade_count == 1
        assert rm.get_state().daily_loss_usd == -2.0

    def test_sell_increments_count_and_pnl(self) -> None:
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=+5.0, trade_type="sell", item_title="AK-47")
        assert rm.get_state().daily_trade_count == 1
        # daily_loss_usd is min(0, pnl) → 0 when pnl is positive
        assert rm.get_state().daily_loss_usd == 0.0

    def test_trades_today_log(self) -> None:
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-1.0, trade_type="buy", item_title="AK-47")
        rm.record_trade_outcome(pnl_usd=+3.0, trade_type="sell", item_title="AWP")
        # We don't expose _trades_today directly, but we can verify
        # get_state() reports the totals correctly.
        s = rm.get_state()
        assert s.daily_trade_count == 2

    def test_pnl_accumulates(self) -> None:
        rm = _make_manager()
        for pnl in [-1.0, -2.0, -3.0]:
            rm.record_trade_outcome(pnl_usd=pnl, trade_type="buy")
        assert rm.get_state().daily_loss_usd == -6.0


# =====================================================================
# TestGetState
# =====================================================================

class TestGetState:
    def test_state_dataclass_fields(self) -> None:
        s = RiskState()
        assert s.daily_loss_usd == 0.0
        assert s.daily_loss_limit_usd == 0.0
        assert s.daily_trade_count == 0
        assert s.daily_trade_limit == 0
        assert s.max_drawdown_pct == 0.0
        assert s.current_drawdown_pct == 0.0
        assert s.soft_halt_active is False
        assert s.daily_halt_active is False
        assert s.peak_equity_usd == 0.0
        assert s.current_equity_usd == 0.0
        assert s.last_reset_date == ""
        assert s.blocked_count_today == 0
        assert s.passed_count_today == 0

    def test_state_consistency_after_activity(self) -> None:
        rm = _make_manager(initial_equity_usd=100.0)
        rm.record_trade_outcome(pnl_usd=-5.0)
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=92.0)
        s = rm.get_state()
        assert s.daily_trade_count == 1
        assert s.passed_count_today == 1
        assert s.blocked_count_today == 0
        assert s.peak_equity_usd == 100.0
        assert s.current_drawdown_pct == pytest.approx(8.0, rel=1e-6)
        assert s.max_drawdown_pct == pytest.approx(8.0, rel=1e-6)


# =====================================================================
# TestGetDailyBriefingLines
# =====================================================================

class TestGetDailyBriefingLines:
    def test_returns_base_4_lines(self) -> None:
        rm = _make_manager()
        lines = rm.get_daily_briefing_lines()
        assert len(lines) >= 4
        assert any("Daily Risk Report" in line for line in lines)
        assert any("Realized PnL" in line for line in lines)
        assert any("Trades:" in line for line in lines)
        assert any("Max drawdown:" in line for line in lines)

    def test_soft_halt_warning_appended(self) -> None:
        rm = _make_manager(
            soft_halt_drawdown_pct=5.0,
            initial_equity_usd=100.0,
        )
        rm.pre_trade_check(proposed_size_usd=5.0, current_equity_usd=90.0)  # 10% DD
        lines = rm.get_daily_briefing_lines()
        assert any("Soft-halt" in line for line in lines)

    def test_daily_halt_warning_appended(self) -> None:
        rm = _make_manager(daily_loss_limit=5.0)
        rm.record_trade_outcome(pnl_usd=-5.0)
        lines = rm.get_daily_briefing_lines()
        assert any("Daily loss limit hit" in line for line in lines)

    def test_pump_summary_appended_when_blacklist_nonempty(self) -> None:
        det = MagicMock()
        det.stats.return_value = {"active_blacklist_size": 3, "total_detections": 5}
        rm = _make_manager(pump_detector=det)
        lines = rm.get_daily_briefing_lines()
        assert any("Pump-blacklist: 3" in line for line in lines)

    def test_pump_summary_omitted_when_blacklist_empty(self) -> None:
        det = MagicMock()
        det.stats.return_value = {"active_blacklist_size": 0, "total_detections": 0}
        rm = _make_manager(pump_detector=det)
        lines = rm.get_daily_briefing_lines()
        assert not any("Pump-blacklist" in line for line in lines)


# =====================================================================
# TestDayRollover
# =====================================================================

class TestDayRollover:
    def test_rollover_resets_counters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rm = _make_manager(daily_trade_limit=10, daily_loss_limit=10.0)
        rm.record_trade_outcome(pnl_usd=-5.0)
        rm.record_trade_outcome(pnl_usd=-2.0)
        assert rm._daily_trade_count == 2
        assert rm._daily_realized_pnl == -7.0

        # Simulate day rollover: force _today to a past date
        rm._today = "2000-01-01"
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)

        # Counters must be reset
        s = rm.get_state()
        assert s.daily_trade_count == 0
        assert s.daily_loss_usd == 0.0
        assert s.blocked_count_today == 0
        assert s.passed_count_today == 1  # this call passed

    def test_rollover_preserves_peak_equity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Peak equity should NOT reset on day rollover (it's long-term)."""
        rm = _make_manager(initial_equity_usd=100.0)
        # First call sets peak to 110
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=110.0)
        assert rm.get_state().peak_equity_usd == 110.0

        # Rollover
        rm._today = "2000-01-01"
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=105.0)
        # Peak should still be 110
        assert rm.get_state().peak_equity_usd == 110.0

    def test_no_rollover_when_same_day(self) -> None:
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-5.0)
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=50.0)
        # Counters NOT reset (same day)
        s = rm.get_state()
        assert s.daily_trade_count == 1
        assert s.daily_loss_usd == -5.0


# =====================================================================
# TestUpdateEquity
# =====================================================================

class TestUpdateEquity:
    def test_peak_only_increases(self) -> None:
        rm = _make_manager(initial_equity_usd=100.0)
        # Equity goes 100 → 110 → 105 → 100 → 120
        # Peak should be 120
        for eq in [110, 105, 100, 120]:
            rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=eq)
        assert rm.get_state().peak_equity_usd == 120

    def test_drawdown_pct_correct(self) -> None:
        rm = _make_manager(initial_equity_usd=100.0)
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=80.0)
        s = rm.get_state()
        # 100 → 80 = 20% DD
        assert s.current_drawdown_pct == pytest.approx(20.0, rel=1e-6)

    def test_max_drawdown_seen_latches_high_watermark(self) -> None:
        rm = _make_manager(initial_equity_usd=100.0)
        # 20% DD then recover then 5% DD
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=80.0)
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=100.0)  # recover
        rm.pre_trade_check(proposed_size_usd=1.0, current_equity_usd=95.0)  # 5% DD
        s = rm.get_state()
        assert s.max_drawdown_pct == pytest.approx(20.0, rel=1e-6)  # latched
        assert s.current_drawdown_pct == pytest.approx(5.0, rel=1e-6)


# =====================================================================
# TestFatalErrorClassification (cross-module sanity)
# =====================================================================

class TestFatalErrorClassification:
    """
    Sanity tests for fatal_errors.py — the watchdog uses these
    exit codes to decide whether to restart. If classification
    changes, our restart behaviour silently changes.
    """

    def test_config_error_is_fatal(self) -> None:
        assert is_fatal(ConfigError("bad config")) is True
        assert exit_code_for(ConfigError("x")) == 2

    def test_auth_error_is_fatal(self) -> None:
        assert is_fatal(AuthError("bad key")) is True
        assert exit_code_for(AuthError("x")) == 3

    def test_database_corruption_is_fatal(self) -> None:
        assert is_fatal(DatabaseCorruption("corrupt")) is True
        assert exit_code_for(DatabaseCorruption("x")) == 4

    def test_logic_bug_is_fatal(self) -> None:
        assert is_fatal(LogicBug("bug")) is True
        assert exit_code_for(LogicBug("x")) == 5

    def test_key_error_is_treated_as_logic_bug(self) -> None:
        """A KeyError in our code is almost always a bug. Treat as fatal."""
        assert is_fatal(KeyError("missing")) is True
        assert exit_code_for(KeyError("missing")) == 5

    def test_attribute_error_is_treated_as_logic_bug(self) -> None:
        assert is_fatal(AttributeError("missing")) is True
        assert exit_code_for(AttributeError("missing")) == 5

    def test_timeout_is_transient(self) -> None:
        """Network timeouts are NOT fatal — retry next cycle."""
        assert is_fatal(TimeoutError("net blip")) is False
        assert classify(TimeoutError()) == "TRANSIENT"

    def test_connection_error_is_transient(self) -> None:
        assert is_fatal(ConnectionError("net blip")) is False
        assert classify(ConnectionError()) == "TRANSIENT"

    def test_unknown_exception_is_fatal(self) -> None:
        """When in doubt, halt. Safer than a tight crash loop."""
        assert is_fatal(ValueError("weird")) is True
        assert classify(ValueError("weird")) == "UNKNOWN"
        assert exit_code_for(ValueError("weird")) == 6
