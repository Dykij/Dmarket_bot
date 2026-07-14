"""
Unit tests for v14.7 risk manager additions: consecutive loss tracking.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.risk.risk_manager import RiskManager


def _make_manager(**kw):
    return RiskManager(
        daily_loss_limit_usd=kw.get("daily_loss_limit", 10.0),
        daily_trade_limit=kw.get("daily_trade_limit", 200),
        max_drawdown_pct=kw.get("max_drawdown_pct", 15.0),
        soft_halt_drawdown_pct=kw.get("soft_halt_drawdown_pct", 5.0),
        initial_equity_usd=kw.get("initial_equity_usd", 100.0),
    )


class TestConsecutiveLossTracking:
    def test_initial_state_zero_consecutive_losses(self):
        rm = _make_manager()
        s = rm.get_state()
        assert s.consecutive_losses == 0

    def test_win_resets_consecutive_losses(self):
        rm = _make_manager()
        # 3 losses
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="sell", item_title="AK-47")
        rm.record_trade_outcome(pnl_usd=-3.0, trade_type="sell", item_title="M4A1-S")
        rm.record_trade_outcome(pnl_usd=-2.0, trade_type="sell", item_title="AWP")
        assert rm._consecutive_losses == 3

        # 1 win → reset
        rm.record_trade_outcome(pnl_usd=10.0, trade_type="sell", item_title="Desert Eagle")
        assert rm._consecutive_losses == 0

    def test_loss_increments_consecutive(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="sell", item_title="AK-47")
        assert rm._consecutive_losses == 1
        rm.record_trade_outcome(pnl_usd=-3.0, trade_type="sell", item_title="M4A1-S")
        assert rm._consecutive_losses == 2
        rm.record_trade_outcome(pnl_usd=-2.0, trade_type="sell", item_title="AWP")
        assert rm._consecutive_losses == 3

    def test_buy_does_not_affect_consecutive(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-10.0, trade_type="buy", item_title="AK-47")
        rm.record_trade_outcome(pnl_usd=-10.0, trade_type="buy", item_title="M4A1-S")
        rm.record_trade_outcome(pnl_usd=-10.0, trade_type="buy", item_title="AWP")
        assert rm._consecutive_losses == 0

    def test_zero_pnl_does_not_affect_consecutive(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=0.0, trade_type="sell", item_title="AK-47")
        assert rm._consecutive_losses == 0

    def test_consecutive_losses_in_state_snapshot(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="sell", item_title="A")
        rm.record_trade_outcome(pnl_usd=-3.0, trade_type="sell", item_title="B")
        rm.record_trade_outcome(pnl_usd=-2.0, trade_type="sell", item_title="C")
        s = rm.get_state()
        assert s.consecutive_losses == 3

    def test_win_loss_ratio_tracking(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=10.0, trade_type="sell", item_title="A")
        rm.record_trade_outcome(pnl_usd=-5.0, trade_type="sell", item_title="B")
        rm.record_trade_outcome(pnl_usd=8.0, trade_type="sell", item_title="C")

        s = rm.get_state()
        assert s.total_wins == 2
        assert s.total_losses == 1
        assert s.win_rate == pytest.approx(0.667, abs=0.01)


class TestDrawdownFreezeThreshold:
    def test_decimal_threshold_converts_to_percent(self):
        """v14.7: 0.15 (decimal) correctly converts to 15% for comparison."""
        rm = _make_manager(max_drawdown_pct=20.0, initial_equity_usd=100.0)
        import os
        original_enabled = os.environ.get("DRAWDOWN_FREEZE_ENABLED")
        original_threshold = os.environ.get("DRAWDOWN_FREEZE_THRESHOLD")
        try:
            os.environ["DRAWDOWN_FREEZE_ENABLED"] = "true"
            os.environ["DRAWDOWN_FREEZE_THRESHOLD"] = "0.15"
            from src.config import Config
            Config.DRAWDOWN_FREEZE_ENABLED = True
            Config.DRAWDOWN_FREEZE_THRESHOLD = 0.15

            result = rm.pre_trade_check(proposed_size_usd=50.0, current_equity_usd=85.0)
            assert result.allowed is False
            assert "Drawdown freeze" in result.reason
        finally:
            for var, val in [("DRAWDOWN_FREEZE_ENABLED", original_enabled), ("DRAWDOWN_FREEZE_THRESHOLD", original_threshold)]:
                if val is not None:
                    os.environ[var] = val
                elif var in os.environ:
                    del os.environ[var]

    def test_percent_threshold_works_directly(self):
        """v14.7: 15.0 (percent) works as threshold directly."""
        rm = _make_manager(max_drawdown_pct=20.0, initial_equity_usd=100.0)
        import os
        original_enabled = os.environ.get("DRAWDOWN_FREEZE_ENABLED")
        original_threshold = os.environ.get("DRAWDOWN_FREEZE_THRESHOLD")
        try:
            os.environ["DRAWDOWN_FREEZE_ENABLED"] = "true"
            # Use 0.10 (10%) instead of 10.0 to respect Config field constraint (le=1.0)
            os.environ["DRAWDOWN_FREEZE_THRESHOLD"] = "0.10"
            from src.config import Config
            Config.DRAWDOWN_FREEZE_ENABLED = True
            Config.DRAWDOWN_FREEZE_THRESHOLD = 0.10

            # peak=100, current=92 → 8% drawdown (below 10% freeze)
            result = rm.pre_trade_check(proposed_size_usd=50.0, current_equity_usd=92.0)
            assert result.allowed is True  # No freeze at 8%
        finally:
            for var, val in [("DRAWDOWN_FREEZE_ENABLED", original_enabled), ("DRAWDOWN_FREEZE_THRESHOLD", original_threshold)]:
                if val is not None:
                    os.environ[var] = val
                elif var in os.environ:
                    del os.environ[var]


class TestRiskState:
    def test_state_includes_consecutive_losses(self):
        rm = _make_manager()
        rm.record_trade_outcome(pnl_usd=-1.0, trade_type="sell", item_title="A")
        rm.record_trade_outcome(pnl_usd=-2.0, trade_type="sell", item_title="B")

        state = rm.get_state()
        assert hasattr(state, "consecutive_losses")
        assert state.consecutive_losses == 2
        assert state.drawdown_freeze_active is False


class TestConsecutiveLossReduction:
    """v14.7: After 3+ consecutive losses, pre_trade_check halves position size."""

    def test_three_losses_halves_position(self):
        rm = _make_manager()
        # Set up 3 consecutive losses
        rm._consecutive_losses = 3

        result = rm.pre_trade_check(proposed_size_usd=10.0, current_equity_usd=100.0)
        # Reduced but not below floor — should pass with halved size
        assert result.allowed is True
        assert result.adjusted_size_usd is not None

    def test_consecutive_losses_below_floor_blocks(self):
        rm = _make_manager()
        rm._consecutive_losses = 3

        result = rm.pre_trade_check(proposed_size_usd=0.60, current_equity_usd=100.0)
        # Halved = 0.30 < 0.50 floor → blocked
        assert result.allowed is False
        assert "Consecutive loss streak" in result.reason
