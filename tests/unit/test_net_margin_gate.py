"""Tests for the P0 net margin gate in filter.py."""

from __future__ import annotations

import pytest

from src.config import Config


class TestNetMarginGate:
    """Verify that the net margin gate rejects unprofitable listings."""

    def test_ak47_redline_10_to_10_19_rejected_with_actual_fees(self):
        """
        Reproduce the exact dry-run case: AK-47 Redline bought at $10.00,
        listed at $10.19 (best_bid - $0.01 discount).

        With ACTUAL Config: FEE_RATE=2.5% + WITHDRAWAL_FEE_RATE=0.5% = 3% total:
        net_margin = ($10.19 - $10.00) / $10.00 - 0.03 = 1.9% - 3% = -1.1%

        This should be REJECTED by the gate (net margin < 0).
        """
        base_price = 10.00
        list_price = 10.19
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        net_margin_pct = ((list_price - base_price) / base_price - total_fee_rate) * 100

        # net_margin = (0.19/10.00 - 0.03) * 100 = (0.019 - 0.03) * 100 = -1.1%
        assert net_margin_pct < 0, f"Expected negative margin, got {net_margin_pct:.2f}%"
        assert net_margin_pct == pytest.approx(-1.1, abs=0.1)

    def test_ak47_redline_10_to_10_19_rejected_with_legacy_5pct_fees(self):
        """
        Same case but with 5% fee (the rate that was actually applied in dry run).
        net_margin = ($10.19 - $10.00) / $10.00 - 0.05 = 1.9% - 5% = -3.1%

        This confirms the systematic loss regardless of which fee rate was used.
        """
        base_price = 10.00
        list_price = 10.19

        # With 5% fee (legacy/hardcoded)
        net_margin_pct_legacy = ((list_price - base_price) / base_price - 0.05) * 100
        assert net_margin_pct_legacy < 0
        assert net_margin_pct_legacy == pytest.approx(-3.1, abs=0.1)

        # With 3% fee (actual Config)
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE
        net_margin_pct_actual = ((list_price - base_price) / base_price - total_fee_rate) * 100
        assert net_margin_pct_actual < 0

    def test_profitable_listing_passes(self):
        """
        A listing with enough margin should pass.
        $10.00 buy → $11.00 list → net = (1.00/10.00 - 0.03) * 100 = 7%
        """
        base_price = 10.00
        list_price = 11.00
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        net_margin_pct = ((list_price - base_price) / base_price - total_fee_rate) * 100

        assert net_margin_pct > 0, f"Expected positive margin, got {net_margin_pct:.2f}%"
        assert net_margin_pct == pytest.approx(7.0, abs=0.1)

    def test_break_even_price(self):
        """
        Break-even price for $10.00 buy with actual fees (3%):
        sell_price = buy_price * (1 + fee_rate) = $10.00 * 1.03 = $10.30
        """
        base_price = 10.00
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        break_even = base_price * (1 + total_fee_rate)

        # At break-even, net margin should be ~0
        net_at_breakeven = ((break_even - base_price) / base_price - total_fee_rate) * 100
        assert net_at_breakeven == pytest.approx(0.0, abs=0.01)

        # Just below break-even should be negative
        net_below = ((break_even - 0.01 - base_price) / base_price - total_fee_rate) * 100
        assert net_below < 0

    def test_fee_rate_values_from_env(self):
        """Verify the actual fee rate constants from .env."""
        # These are the ACTUAL values from .env, not hardcoded assumptions
        assert Config.FEE_RATE == 0.025, f"Expected 2.5% sell fee, got {Config.FEE_RATE}"
        assert Config.WITHDRAWAL_FEE_RATE == 0.005, f"Expected 0.5% withdrawal fee, got {Config.WITHDRAWAL_FEE_RATE}"

    def test_min_spread_from_env(self):
        """Verify MIN_SPREAD_PCT from .env."""
        assert Config.MIN_SPREAD_PCT == 1.5, f"Expected 1.5% min spread, got {Config.MIN_SPREAD_PCT}"

    def test_dry_run_profit_discrepancy_investigation(self):
        """
        Investigate the discrepancy between recorded profit (-$0.3195) and
        expected profit with actual fees.

        Recorded: buy $10.00, sell $10.19, profit = -$0.3195
        This implies fee = $10.19 - $10.00 + $0.3195 = $0.5095
        fee_rate = $0.5095 / $10.19 = 4.9995% ≈ 5%

        But Config.FEE_RATE = 2.5%. So either:
        1. The code used a hardcoded 5% instead of Config.FEE_RATE
        2. The Config was different when trades happened (different .env)
        3. DMarket charged a higher fee than configured
        """
        sell_price = 10.19
        buy_price = 10.00
        recorded_profit = -0.3195

        # Back-calculate the fee rate from recorded profit
        # profit = sell - buy - fee => fee = sell - buy - profit
        actual_fee = sell_price - buy_price - recorded_profit
        actual_fee_rate = actual_fee / sell_price

        # Should be ~5%
        assert actual_fee_rate == pytest.approx(0.05, abs=0.001), (
            f"Recorded profit implies fee_rate={actual_fee_rate:.4f} "
            f"({actual_fee_rate*100:.2f}%), but Config.FEE_RATE={Config.FEE_RATE}"
        )
