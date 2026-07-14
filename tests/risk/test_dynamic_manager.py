"""
Unit tests for src.risk.dynamic_manager.DynamicRiskManager.

Coverage:
- Initial state verification
- Risk adjustment on consecutive losses (adaptive sizing)
- Risk adjustment on wins
- Limit retrieval via properties
- Kelly fraction calculation
- Soft halt logic
- Trade recording
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.risk.dynamic_manager import DynamicRiskManager  # noqa: E402


# =====================================================================
# test_initial_state
# =====================================================================

class TestInitialState:
    """Verify default state after construction."""

    def test_default_kelly_fraction(self) -> None:
        rm = DynamicRiskManager()
        assert rm.base_fraction == 0.10

    def test_default_soft_halt_threshold(self) -> None:
        rm = DynamicRiskManager()
        assert rm.soft_halt_threshold == 0.015

    def test_custom_constructor_params(self) -> None:
        rm = DynamicRiskManager(base_kelly_fraction=0.20, soft_halt_threshold=0.05)
        assert rm.base_fraction == 0.20
        assert rm.soft_halt_threshold == 0.05

    def test_initial_trade_counters(self) -> None:
        rm = DynamicRiskManager()
        assert rm._total_trades == 0
        assert rm._win_trades == 0
        assert rm._gross_profit == 0.0
        assert rm._gross_loss == 0.0

    def test_initial_win_rate(self) -> None:
        rm = DynamicRiskManager()
        # No trades → win_rate = 0 / max(0, 1) = 0.0
        assert rm.win_rate == 0.0

    def test_initial_win_loss_ratio(self) -> None:
        rm = DynamicRiskManager()
        # No loss trades → avg_loss = 0 → ratio = 0.0
        assert rm.win_loss_ratio == 0.0


# =====================================================================
# test_adjust_risk_up
# =====================================================================

class TestAdjustRiskUp:
    """Verify risk increases (sizing reduced) on consecutive losses or high volatility."""

    def test_high_volatility_regime_scales_down(self) -> None:
        rm = DynamicRiskManager()
        # Regime 1 = high volatility → scale down by 50%
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=1,
            hawkes_intensity=1.0,
            current_drawdown=0.0,
        )
        assert result == 5.0

    def test_high_hawkes_intensity_scales_down(self) -> None:
        rm = DynamicRiskManager()
        # Hawkes intensity > 2.0 → scale down by 50%
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=3.0,
            current_drawdown=0.0,
        )
        assert result == 5.0

    def test_both_regime_and_hawkes_scales_down_once(self) -> None:
        """Both conditions true → still only 50% reduction (not cumulative)."""
        rm = DynamicRiskManager()
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=1,
            hawkes_intensity=3.0,
            current_drawdown=0.0,
        )
        assert result == 5.0

    def test_consecutive_losses_increase_kelly_fraction_impact(self) -> None:
        """Recording losses reduces win_rate, which reduces Kelly fraction."""
        rm = DynamicRiskManager()
        # Record 3 losses, 1 win → win_rate = 0.25
        rm.record_trade(won=True, profit_usd=5.0)
        rm.record_trade(won=False, loss_usd=3.0)
        rm.record_trade(won=False, loss_usd=3.0)
        rm.record_trade(won=False, loss_usd=3.0)

        assert rm.win_rate == pytest.approx(0.25)
        # With low win_rate and poor ratio, Kelly should be low
        fraction = DynamicRiskManager.kelly_fraction(rm.win_rate, rm.win_loss_ratio)
        assert fraction < 0.10  # lower than a 50% win rate scenario


# =====================================================================
# test_adjust_risk_down
# =====================================================================

class TestAdjustRiskDown:
    """Verify risk decreases (sizing maintained or improved) on wins."""

    def test_normal_regime_no_scale_down(self) -> None:
        rm = DynamicRiskManager()
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.0,
        )
        assert result == 10.0

    def test_win_improves_kelly_fraction(self) -> None:
        """Recording wins increases win_rate, which increases Kelly fraction."""
        rm = DynamicRiskManager()
        # Record 4 wins, 1 loss → win_rate = 0.8
        for _ in range(4):
            rm.record_trade(won=True, profit_usd=5.0)
        rm.record_trade(won=False, loss_usd=2.0)

        assert rm.win_rate == pytest.approx(0.8)
        fraction = DynamicRiskManager.kelly_fraction(rm.win_rate, rm.win_loss_ratio)
        assert fraction > 0.0

    def test_sell_order_permitted_during_soft_halt(self) -> None:
        """SELL orders are allowed even during soft halt."""
        rm = DynamicRiskManager(soft_halt_threshold=0.015)
        result = rm.evaluate_trade_size(
            direction="SELL",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.05,  # 5% drawdown > 1.5% threshold
        )
        assert result == 10.0  # not scaled down

    def test_buy_order_rejected_during_soft_halt(self) -> None:
        """BUY orders are rejected (return None) during soft halt."""
        rm = DynamicRiskManager(soft_halt_threshold=0.015)
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.05,  # 5% drawdown > 1.5% threshold
        )
        assert result is None


# =====================================================================
# test_get_current_limits
# =====================================================================

class TestGetCurrentLimits:
    """Verify limit retrieval via properties and methods."""

    def test_win_rate_after_trades(self) -> None:
        rm = DynamicRiskManager()
        rm.record_trade(won=True, profit_usd=10.0)
        rm.record_trade(won=True, profit_usd=10.0)
        rm.record_trade(won=False, loss_usd=5.0)
        assert rm.win_rate == pytest.approx(2 / 3, rel=1e-6)

    def test_win_loss_ratio_after_trades(self) -> None:
        rm = DynamicRiskManager()
        # 2 wins: $10 each → avg_profit = $10
        # 1 loss: $5 → avg_loss = $5
        # ratio = 10 / 5 = 2.0
        rm.record_trade(won=True, profit_usd=10.0)
        rm.record_trade(won=True, profit_usd=10.0)
        rm.record_trade(won=False, loss_usd=5.0)
        assert rm.win_loss_ratio == pytest.approx(2.0, rel=1e-6)

    def test_win_loss_ratio_zero_losses(self) -> None:
        """No loss trades → avg_loss = 0 → ratio = 0.0."""
        rm = DynamicRiskManager()
        rm.record_trade(won=True, profit_usd=10.0)
        assert rm.win_loss_ratio == 0.0

    def test_total_trades_counter(self) -> None:
        rm = DynamicRiskManager()
        rm.record_trade(won=True, profit_usd=1.0)
        rm.record_trade(won=False, loss_usd=1.0)
        rm.record_trade(won=True, profit_usd=1.0)
        assert rm._total_trades == 3
        assert rm._win_trades == 2

    def test_gross_profit_accumulates(self) -> None:
        rm = DynamicRiskManager()
        rm.record_trade(won=True, profit_usd=5.0)
        rm.record_trade(won=True, profit_usd=3.0)
        assert rm._gross_profit == pytest.approx(8.0)

    def test_gross_loss_accumulates(self) -> None:
        rm = DynamicRiskManager()
        rm.record_trade(won=False, loss_usd=4.0)
        rm.record_trade(won=False, loss_usd=2.0)
        assert rm._gross_loss == pytest.approx(6.0)

    def test_negative_profit_treated_as_absolute(self) -> None:
        """abs() is applied to profit_usd for wins."""
        rm = DynamicRiskManager()
        rm.record_trade(won=True, profit_usd=-5.0)
        assert rm._gross_profit == pytest.approx(5.0)

    def test_negative_loss_treated_as_absolute(self) -> None:
        """abs() is applied to loss_usd for losses."""
        rm = DynamicRiskManager()
        rm.record_trade(won=False, loss_usd=-3.0)
        assert rm._gross_loss == pytest.approx(3.0)


# =====================================================================
# test_kelly_fraction
# =====================================================================

class TestKellyFraction:
    """Test the static Kelly criterion calculation."""

    def test_half_kelly_default(self) -> None:
        """Default is half-kelly (50% of full Kelly)."""
        # Full Kelly: f* = 0.6 - (1-0.6)/2.0 = 0.6 - 0.2 = 0.4
        # Half Kelly: 0.4 * 0.5 = 0.2
        result = DynamicRiskManager.kelly_fraction(0.6, 2.0, half_kelly=True)
        assert result == pytest.approx(0.2, rel=1e-6)

    def test_full_kelly(self) -> None:
        # f* = 0.6 - (1-0.6)/2.0 = 0.4, but capped at 0.25
        result = DynamicRiskManager.kelly_fraction(0.6, 2.0, half_kelly=False)
        assert result == 0.25

    def test_negative_edge_returns_zero(self) -> None:
        """If win_rate is too low for the ratio, Kelly is 0 (don't bet)."""
        # f* = 0.2 - (1-0.2)/2.0 = 0.2 - 0.4 = -0.2 → 0
        result = DynamicRiskManager.kelly_fraction(0.2, 2.0)
        assert result == 0.0

    def test_zero_win_rate_returns_zero(self) -> None:
        result = DynamicRiskManager.kelly_fraction(0.0, 2.0)
        assert result == 0.0

    def test_zero_ratio_returns_zero(self) -> None:
        result = DynamicRiskManager.kelly_fraction(0.6, 0.0)
        assert result == 0.0

    def test_negative_ratio_returns_zero(self) -> None:
        result = DynamicRiskManager.kelly_fraction(0.6, -1.0)
        assert result == 0.0

    def test_capped_at_025(self) -> None:
        """Kelly fraction is capped at 0.25."""
        # Very high win rate and ratio → f* would be huge
        result = DynamicRiskManager.kelly_fraction(0.95, 10.0, half_kelly=False)
        assert result == 0.25

    def test_perfect_win_rate(self) -> None:
        """100% win rate → f* = 1.0 - 0/ratio = 1.0 → capped at 0.25."""
        result = DynamicRiskManager.kelly_fraction(1.0, 5.0, half_kelly=False)
        assert result == 0.25


# =====================================================================
# test_soft_halt_and_drawdown
# =====================================================================

class TestSoftHaltAndDrawdown:
    """Verify soft halt and drawdown-aware sizing."""

    def test_drawdown_below_threshold_no_halt(self) -> None:
        rm = DynamicRiskManager(soft_halt_threshold=0.05)
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.03,  # 3% < 5% threshold
        )
        assert result == 10.0

    def test_drawdown_at_threshold_triggers_halt(self) -> None:
        rm = DynamicRiskManager(soft_halt_threshold=0.05)
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.05,  # 5% >= 5% threshold
        )
        assert result is None

    def test_drawdown_above_threshold_triggers_halt(self) -> None:
        rm = DynamicRiskManager(soft_halt_threshold=0.05)
        result = rm.evaluate_trade_size(
            direction="BUY",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.10,  # 10% > 5%
        )
        assert result is None

    def test_sell_during_halt_returns_original_amount(self) -> None:
        """SELL during soft halt returns the original amount (not None)."""
        rm = DynamicRiskManager(soft_halt_threshold=0.05)
        result = rm.evaluate_trade_size(
            direction="SELL",
            original_amount=10.0,
            current_regime=0,
            hawkes_intensity=1.0,
            current_drawdown=0.10,
        )
        assert result == 10.0

    def test_sell_during_halt_scaled_by_regime(self) -> None:
        """SELL during halt is permitted but still scaled by regime."""
        rm = DynamicRiskManager(soft_halt_threshold=0.05)
        result = rm.evaluate_trade_size(
            direction="SELL",
            original_amount=10.0,
            current_regime=1,
            hawkes_intensity=1.0,
            current_drawdown=0.10,
        )
        # SELL is permitted (not None), but regime 1 still scales by 50%
        assert result == 5.0
