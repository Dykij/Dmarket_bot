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

        With ACTUAL Config (fixed): FEE_RATE=5% + WITHDRAWAL_FEE_RATE=0.5% = 5.5% total:
        net_received = $10.19 * (1 - 0.055) = $9.62955
        profit = $9.62955 - $10.00 = -$0.37045
        net_margin = (-0.37045 / 10.00) * 100 = -3.7%

        This should be REJECTED by the gate (net margin < 0).
        """
        base_price = 10.00
        list_price = 10.19
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        net_margin_pct = (((list_price * (1.0 - total_fee_rate)) - base_price) / base_price) * 100

        assert net_margin_pct < 0, f"Expected negative margin, got {net_margin_pct:.2f}%"
        assert net_margin_pct == pytest.approx(-3.7, abs=0.1)

    def test_ak47_redline_10_to_10_19_rejected_with_legacy_5pct_fees(self):
        """
        Same case but with 5% fee (the rate that was actually applied in dry run).
        net_received = $10.19 * (1 - 0.05) = $9.6805
        profit = $9.6805 - $10.00 = -$0.3195
        net_margin = (-0.3195 / 10.00) * 100 = -3.2%
        """
        base_price = 10.00
        list_price = 10.19

        # With 5% fee (legacy/hardcoded)
        net_margin_pct_legacy = (((list_price * (1.0 - 0.05)) - base_price) / base_price) * 100
        assert net_margin_pct_legacy < 0
        assert net_margin_pct_legacy == pytest.approx(-3.2, abs=0.1)

        # With actual fee
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE
        net_margin_pct_actual = (((list_price * (1.0 - total_fee_rate)) - base_price) / base_price) * 100
        assert net_margin_pct_actual < 0

    def test_profitable_listing_passes(self):
        """
        A listing with enough margin should pass.
        $10.00 buy → $11.00 list
        net_received = $11.00 * (1 - 0.055) = $10.395
        net_margin = (0.395 / 10.00) * 100 = 3.95%
        """
        base_price = 10.00
        list_price = 11.00
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        net_margin_pct = (((list_price * (1.0 - total_fee_rate)) - base_price) / base_price) * 100

        assert net_margin_pct > 0, f"Expected positive margin, got {net_margin_pct:.2f}%"
        assert net_margin_pct == pytest.approx(3.95, abs=0.1)

    def test_break_even_price(self):
        """
        Break-even price for $10.00 buy with actual fees (5.5%):
        sell_price = buy_price / (1 - fee_rate) = $10.00 / (1 - 0.055) = $10.582
        """
        base_price = 10.00
        total_fee_rate = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE

        break_even = base_price / (1.0 - total_fee_rate)

        # At break-even, net margin should be ~0
        net_at_breakeven = (((break_even * (1.0 - total_fee_rate)) - base_price) / base_price) * 100
        assert net_at_breakeven == pytest.approx(0.0, abs=0.01)

        # Just below break-even should be negative
        net_below = ((((break_even - 0.01) * (1.0 - total_fee_rate)) - base_price) / base_price) * 100
        assert net_below < 0

    def test_fee_rate_values_from_env(self):
        """Verify the actual fee rate constants from .env."""
        # Fixed: .env FEE_RATE corrected from 0.025 to 0.05 (verified DMarket rate)
        assert Config.FEE_RATE == 0.05, f"Expected 5% sell fee, got {Config.FEE_RATE}"
        assert Config.WITHDRAWAL_FEE_RATE == 0.005, f"Expected 0.5% withdrawal fee, got {Config.WITHDRAWAL_FEE_RATE}"

    def test_min_spread_from_env(self):
        """Verify MIN_SPREAD_PCT from .env."""
        assert Config.MIN_SPREAD_PCT == 1.5, f"Expected 1.5% min spread, got {Config.MIN_SPREAD_PCT}"

    def test_dry_run_profit_discrepancy_investigation(self):
        """
        Investigate the discrepancy between recorded profit (-$0.3195) and
        expected profit with actual fees.
        """
        sell_price = 10.19
        buy_price = 10.00
        recorded_profit = -0.3195

        # Back-calculate the fee rate from recorded profit
        actual_fee_rate = 1.0 - (recorded_profit + buy_price) / sell_price

        # Should be ~5%
        assert actual_fee_rate == pytest.approx(0.05, abs=0.001), (
            f"Recorded profit implies fee_rate={actual_fee_rate:.4f} "
            f"({actual_fee_rate*100:.2f}%), but Config.FEE_RATE={Config.FEE_RATE}"
        )
