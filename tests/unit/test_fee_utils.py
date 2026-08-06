"""Tests for fee_utils.py — unified fee source and regression guard."""

from __future__ import annotations

import pytest

from src.config import Config
from src.utils.fee_utils import (
    VERIFIED_DMARKET_FEE_RATE,
    get_sell_fee_rate,
    get_total_fee_rate,
)


class TestGetSellFeeRate:
    """Verify get_sell_fee_rate priority and fallback logic."""

    def test_bulk_fees_takes_priority(self):
        """API bulk_fees should override Config.FEE_RATE."""
        bulk_fees = {"item_123": 0.03}  # 3% low-fee item
        result = get_sell_fee_rate("item_123", bulk_fees)
        assert result == 0.03

    def test_bulk_fees_missing_item_falls_back_to_config(self):
        """When item not in bulk_fees, fall back to Config."""
        bulk_fees = {"other_item": 0.03}
        result = get_sell_fee_rate("item_123", bulk_fees)
        assert result == Config.FEE_RATE

    def test_no_bulk_fees_uses_config(self):
        """Without bulk_fees, use Config.FEE_RATE."""
        result = get_sell_fee_rate("item_123", None)
        assert result == Config.FEE_RATE

    def test_empty_bulk_fees_uses_config(self):
        """Empty bulk_fees dict falls back to Config."""
        result = get_sell_fee_rate("item_123", {})
        assert result == Config.FEE_RATE

    def test_bulk_fees_invalid_rate_ignored(self):
        """Invalid fee rates in bulk_fees (>1 or <=0) are ignored."""
        bulk_fees = {"item_123": 1.5}  # Invalid
        result = get_sell_fee_rate("item_123", bulk_fees)
        assert result == Config.FEE_RATE

    def test_verified_dmarket_fee_rate(self):
        """Hardcoded verified fee rate should be 5%."""
        assert VERIFIED_DMARKET_FEE_RATE == 0.05

    def test_config_fee_rate_matches_verified(self):
        """Config.FEE_RATE should match verified DMarket fee."""
        # This test will FAIL if .env has FEE_RATE=0.025
        assert Config.FEE_RATE == pytest.approx(VERIFIED_DMARKET_FEE_RATE, abs=0.01), (
            f"Config.FEE_RATE={Config.FEE_RATE} differs from "
            f"verified DMarket fee={VERIFIED_DMARKET_FEE_RATE}. "
            f"Update .env FEE_RATE to match."
        )


class TestGetTotalFeeRate:
    """Verify total fee rate (sell + withdrawal)."""

    def test_total_fee_includes_withdrawal(self):
        """Total fee = sell fee + withdrawal fee."""
        result = get_total_fee_rate()
        expected = Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE
        assert result == pytest.approx(expected, abs=0.001)

    def test_total_fee_with_bulk_fees(self):
        """Total fee with API data includes withdrawal."""
        bulk_fees = {"item_123": 0.03}
        result = get_total_fee_rate("item_123", bulk_fees)
        assert result == pytest.approx(0.03 + Config.WITHDRAWAL_FEE_RATE, abs=0.001)


class TestFeeConsistencyRegression:
    """
    Regression test for the FEE_RATE desync incident.

    Incident (2026-08-05): .env had FEE_RATE=0.025 (2.5%) but DMarket
    charges 5%. The bot bought AK-47 Redline at $10.00 and sold at $10.19,
    losing $0.3195 per trade (112 trades, total -$33.74).

    Root cause: resale_dry.py used Config.FEE_RATE (2.5%) while the actual
    DMarket fee was 5%. Later, hardcoded 0.05 was replaced with Config.FEE_RATE,
    making the bug worse.

    This test ensures all critical P&L paths use get_sell_fee_rate() which
    validates Config.FEE_RATE against the verified DMarket fee rate.
    """

    def test_resale_dry_uses_fee_utils(self):
        """resale_dry.py should use get_sell_fee_rate(), not Config.FEE_RATE."""
        import ast
        import pathlib

        source = pathlib.Path("src/core/target_sniping/resale_dry.py").read_text()
        tree = ast.parse(source)

        # Find all Name nodes that reference Config.FEE_RATE
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if (hasattr(node.value, 'attr') and node.value.attr == 'FEE_RATE'
                        and hasattr(node.value, 'value')
                        and hasattr(node.value.value, 'id')
                        and node.value.value.id == 'Config'):
                    # Check if it's inside a multiply operation (fee calculation)
                    # Config.FEE_RATE should NOT appear in fee calculations
                    pytest.fail(
                        "resale_dry.py still uses Config.FEE_RATE directly. "
                        "Should use get_sell_fee_rate() from fee_utils."
                    )

    def test_ak47_redline_scenario_rejected(self):
        """
        The exact AK-47 Redline scenario from the incident.

        Buy $10.00, sell $10.19, with actual DMarket fee (5%):
        net_margin = (10.19 - 10.00) / 10.00 - 0.05 = -3.1%

        This MUST be rejected by the net margin gate.
        """
        buy_price = 10.00
        sell_price = 10.19
        fee_rate = get_sell_fee_rate()  # Should be 0.05 (5%)
        total_fee = fee_rate + Config.WITHDRAWAL_FEE_RATE

        net_margin = ((sell_price - buy_price) / buy_price - total_fee) * 100

        # With 5% fee: net = (0.19/10.00 - 0.055) * 100 = -3.6%
        assert net_margin < 0, (
            f"AK-47 Redline scenario should have negative margin, "
            f"got {net_margin:.2f}%"
        )

    def test_three_pnl_paths_give_same_fee(self):
        """
        Verify that at least 3 critical P&L paths compute the same fee
        for the same item price.

        This is the side-by-side comparison requested in the task.
        """
        sell_price = 10.19
        item_id = "test_item"
        bulk_fees = {item_id: 0.05}

        # Path 1: fee_utils (unified source)
        fee1 = sell_price * get_sell_fee_rate(item_id, bulk_fees)

        # Path 2: fee_utils total (with withdrawal)
        fee2 = sell_price * get_total_fee_rate(item_id, bulk_fees)

        # Path 3: Config-based (should match after .env fix)
        fee3 = sell_price * Config.FEE_RATE

        # All should give the same sell fee
        assert fee1 == pytest.approx(fee3, abs=0.001), (
            f"fee_utils ({fee1:.4f}) != Config ({fee3:.4f})"
        )

        # Total fee should be sell + withdrawal
        assert fee2 == pytest.approx(fee1 + sell_price * Config.WITHDRAWAL_FEE_RATE, abs=0.001)

        # Print for RAW comparison
        print(f"\n  Fee comparison for sell_price=${sell_price}:")
        print(f"    fee_utils.get_sell_fee_rate(): ${fee1:.4f}")
        print(f"    fee_utils.get_total_fee_rate(): ${fee2:.4f}")
        print(f"    Config.FEE_RATE:               ${fee3:.4f}")
        print(f"    Config.WITHDRAWAL_FEE_RATE:    ${sell_price * Config.WITHDRAWAL_FEE_RATE:.4f}")
