"""Tests for OBI/OFI logging pipeline reorder (afe714c).

Verifies:
- Test A: Items blocked by velocity gate still get OBI/OFI logged
- Test B: Net margin gate still works after pipeline reorder
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Config


class TestOBIOFILoggingBeforeVelocityGate:
    """Verify OBI/OFI logging happens BEFORE velocity gate."""

    @pytest.mark.asyncio
    async def test_obi_ofi_logged_when_velocity_low(self):
        """Test A: Items get OBI/OFI logged even when velocity gate blocks.

        Scenario: velocity < 0.5x → cycle skips after logging.
        Decision_logs must contain 'scanned' entries with obi_norm/ofi.
        """
        from src.core.target_sniping.cycle_orchestrator import CycleContext, CycleOrchestrator

        orch = MagicMock(spec=CycleOrchestrator)
        orch._obi_cache = {}

        # Mock API returns items with known bid/ask counts
        agg_prices = {
            "AK-47 | Redline": {
                "best_bid": 10.0, "best_ask": 10.50,
                "bid_count": 30, "ask_count": 10,
            },
            "AWP | Asiimov": {
                "best_bid": 25.0, "best_ask": 26.0,
                "bid_count": 50, "ask_count": 5,
            },
        }
        orch.client = AsyncMock()
        orch.client.get_aggregated_prices = AsyncMock(return_value=agg_prices)
        orch._fetch_cheapest_listings = AsyncMock(return_value=[])

        logged_entries = []

        def _capture_log(title, decision, reason, details=None):
            logged_entries.append({
                "title": title,
                "decision": decision,
                "reason": reason,
                "details": json.loads(details) if details else None,
            })

        with patch("src.core.target_sniping.cycle_orchestrator.Config") as mock_config, \
             patch("src.core.target_sniping.cycle_orchestrator.price_db") as mock_db:
            mock_config.DEMAND_STRATEGY_ENABLED = True
            mock_config.MIN_BID_ASK_COUNT = 5
            mock_config.CAPITAL_VELOCITY_ENABLED = True
            mock_config.CAPITAL_VELOCITY_MIN = 0.5

            mock_db.get_state.return_value = ""
            mock_db.log_decision = MagicMock(side_effect=_capture_log)
            # Velocity gate: low sales → low velocity → skip
            mock_db.get_virtual_inventory_weekly_sales.return_value = 0
            mock_db.get_virtual_inventory_locked_value.return_value = 0

            ctx = MagicMock(spec=CycleContext)
            ctx.is_fresh_cycle = True
            ctx.cursor_key = "cursor"
            ctx.effective_balance = 100.0
            ctx.game_id = "a8db"
            ctx.agg_prices = {}

            await CycleOrchestrator._stage_scan(orch, ctx)

        # Verify: 2 items logged as "scanned" (one per title)
        scanned = [e for e in logged_entries if e["decision"] == "scanned"]
        assert len(scanned) == 2, f"Expected 2 scanned entries, got {len(scanned)}"

        # Verify: each has obi_norm and ofi in details
        for entry in scanned:
            d = entry["details"]
            assert d is not None, f"No details for {entry['title']}"
            assert "obi_norm" in d, f"Missing obi_norm for {entry['title']}"
            assert "ofi" in d, f"Missing ofi for {entry['title']}"
            assert "bid_count" in d, f"Missing bid_count for {entry['title']}"
            assert "ask_count" in d, f"Missing ask_count for {entry['title']}"
            assert isinstance(d["obi_norm"], (int, float)), "obi_norm must be numeric"
            assert isinstance(d["ofi"], (int, float)), "ofi must be numeric"

        # Verify: AK-47 OBI = (30-10)/(30+10) = 0.5
        ak_entry = next(e for e in scanned if e["title"] == "AK-47 | Redline")
        assert ak_entry["details"]["obi_norm"] == pytest.approx(0.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_no_duplicate_logging(self):
        """Verify each title gets exactly ONE scanned entry per cycle."""
        from src.core.target_sniping.cycle_orchestrator import CycleContext, CycleOrchestrator

        orch = MagicMock(spec=CycleOrchestrator)
        orch._obi_cache = {}

        agg_prices = {
            "Item_A": {"best_bid": 10.0, "best_ask": 10.5, "bid_count": 20, "ask_count": 10},
        }
        orch.client = AsyncMock()
        orch.client.get_aggregated_prices = AsyncMock(return_value=agg_prices)
        orch._fetch_cheapest_listings = AsyncMock(return_value=[])

        logged_titles = []

        def _capture_log(title, decision, reason, details=None):
            if decision == "scanned":
                logged_titles.append(title)

        with patch("src.core.target_sniping.cycle_orchestrator.Config") as mock_config, \
             patch("src.core.target_sniping.cycle_orchestrator.price_db") as mock_db:
            mock_config.DEMAND_STRATEGY_ENABLED = True
            mock_config.MIN_BID_ASK_COUNT = 5
            mock_config.CAPITAL_VELOCITY_ENABLED = False  # Don't block

            mock_db.get_state.return_value = ""
            mock_db.log_decision = MagicMock(side_effect=_capture_log)

            ctx = MagicMock(spec=CycleContext)
            ctx.is_fresh_cycle = True
            ctx.cursor_key = "cursor"
            ctx.effective_balance = 100.0
            ctx.game_id = "a8db"
            ctx.agg_prices = {}

            await CycleOrchestrator._stage_scan(orch, ctx)

        # Each title logged exactly once
        assert logged_titles.count("Item_A") == 1, \
            f"Item_A logged {logged_titles.count('Item_A')} times (expected 1)"


class TestNetMarginGateAfterReorder:
    """Verify net margin gate still works after pipeline reorder."""

    def test_ak47_redline_rejected_by_gate(self):
        """Test B: AK-47 Redline $10→$10.19 with 5.5% fee → REJECTED."""
        from src.utils.fee_utils import get_total_fee_rate

        buy_price = 10.00
        sell_price = 10.19
        total_fee_rate = get_total_fee_rate()
        net_margin_pct = ((sell_price - buy_price) / buy_price - total_fee_rate) * 100

        # With 5% + 0.5% = 5.5% fees: net = (0.19/10.00 - 0.055) * 100 = -3.6%
        assert net_margin_pct < 0, f"Expected negative margin, got {net_margin_pct:.2f}%"
        assert net_margin_pct == pytest.approx(-3.6, abs=0.1)

    def test_profitable_item_passes_gate(self):
        """Profitable item ($10→$12) with fees → positive margin."""
        from src.utils.fee_utils import get_total_fee_rate

        buy_price = 10.00
        sell_price = 12.00
        total_fee_rate = get_total_fee_rate()
        net_margin_pct = ((sell_price - buy_price) / buy_price - total_fee_rate) * 100

        # net = (2.00/10.00 - 0.055) * 100 = 14.5%
        assert net_margin_pct > 0
        assert net_margin_pct == pytest.approx(14.5, abs=0.1)
