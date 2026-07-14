"""Tests for execution.py — instant-buy execution pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_item(
    title: str = "AK-47 | Redline",
    item_id: str = "item_001",
    base_price: float = 10.0,
    list_price: float = 12.0,
    best_bid: float = 11.50,
    best_ask: float = 10.0,
    is_rare: bool = False,
) -> dict[str, Any]:
    return {
        "title": title,
        "item_id": item_id,
        "base_price": base_price,
        "list_price": list_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "is_rare": is_rare,
        "buy_offer": {"offerId": f"offer_{item_id}", "price": {"USD": int(base_price * 100)}},
        "strategy": "intra_spread",
    }


def _make_mixin() -> MagicMock:
    mixin = MagicMock()
    mixin.client = AsyncMock()
    mixin.liquidity = MagicMock()
    mixin.risk = MagicMock()
    mixin._simulate_network_latency = AsyncMock()
    mixin._maybe_inject_error = MagicMock()
    mixin._simulate_competition = MagicMock(return_value=True)
    risk_result = MagicMock()
    risk_result.allowed = True
    risk_result.adjusted_size_usd = None
    mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)
    mixin.risk.record_trade_outcome = MagicMock()
    return mixin


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DRY_RUN", "true")


@pytest.fixture()
def _mock_notifier():
    n = MagicMock()
    n.buy = AsyncMock()
    return n


@pytest.fixture()
def _patch_execution(_mock_notifier):
    """Patch price_db and notifier at the execution module level."""
    with (
        patch("src.core.target_sniping.execution.price_db") as mock_db,
        patch("src.core.target_sniping.execution.notifier", _mock_notifier),
    ):
        mock_db.get_total_equity.return_value = {
            "assets": 0.0, "count": 0, "frozen": 0.0,
            "available": 100.0, "total": 100.0,
        }
        mock_db.get_virtual_inventory.return_value = []
        mock_db.calculate_vwap.return_value = 10.5
        mock_db.run_in_thread = AsyncMock(
            return_value=MagicMock(fetchone=MagicMock(return_value={"id": 1}))
        )
        yield mock_db


class TestExecuteBuyDryRun:

    @pytest.mark.asyncio
    async def test_dry_run_records_virtual_item(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.add_virtual_item.assert_called()
        _patch_execution.record_placed_target.assert_called_once()
        mixin.liquidity.record_spend.assert_called_once_with(10.0)

    @pytest.mark.asyncio
    async def test_dry_run_buy_items_still_called(self, _patch_execution, monkeypatch):
        """buy_items is always called (even in DRY) — the DRY gate is on local recording."""
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        # buy_items IS called — execution always attempts the API call
        mixin.client.buy_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_dry_run_sends_notification(self, _patch_execution, _mock_notifier, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _mock_notifier.buy.assert_called()


class TestExecuteBuyLive:

    @pytest.mark.asyncio
    async def test_live_calls_buy_items(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        mixin.client.buy_items.assert_called_once()
        call_args = mixin.client.buy_items.call_args[0][0]
        assert call_args[0]["offerId"] == "offer_item_001"

    @pytest.mark.asyncio
    async def test_live_records_spend_on_success(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        mixin.liquidity.record_spend.assert_called_with(10.0)
        mixin.risk.record_trade_outcome.assert_called_with(
            pnl_usd=-10.0, trade_type="buy", item_title="AK-47 | Redline",
        )

    @pytest.mark.asyncio
    async def test_live_handles_tx_failed(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "TxFailed",
            "dmOffersStatus": {},
            "dmOffersFailReason": {"code": "OfferNotFound", "offerId": "offer_item_001"},
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_no_items_key_still_records(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={"status": "OK"})

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_called_once()


class TestExecuteEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_list_is_noop(self):
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[], current_balance=100.0, game_id="a8db",
        )
        mixin.client.get_market_items_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_slippage_filter_skips_high_slippage(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        # Listing price jumped from 10.00 to 11.00 (10% slippage > 5% threshold)
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1100}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(base_price=10.0)],
            current_balance=100.0, game_id="a8db",
        )

        _patch_execution.add_virtual_item.assert_not_called()
        _patch_execution.record_placed_target.assert_not_called()

    @pytest.mark.asyncio
    async def test_slippage_check_failure_proceeds(self, _patch_execution, monkeypatch):
        """If slippage check raises, item proceeds (fail-open)."""
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(side_effect=Exception("timeout"))

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

    @pytest.mark.asyncio
    async def test_risk_blocks_in_dry_run(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin._simulate_competition = MagicMock(return_value=True)
        risk_result = MagicMock()
        risk_result.allowed = False
        risk_result.reason = "Drawdown freeze"
        risk_result.adjusted_size_usd = None
        mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.add_virtual_item.assert_not_called()
        _patch_execution.record_risk_event.assert_called()

    @pytest.mark.asyncio
    async def test_inventory_count_cap_blocks(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        _patch_execution.get_total_equity.return_value = {
            "assets": 0.0, "count": 100, "frozen": 0.0,
            "available": 100.0, "total": 100.0,
        }

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()

    @pytest.mark.asyncio
    async def test_saturation_same_item_cap(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # 2 existing holdings of same item (default cap is 2 from .env)
        _patch_execution.get_virtual_inventory.return_value = [
            {"hash_name": "AK-47 | Redline"},
            {"hash_name": "AK-47 | Redline"},
        ]

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_offers_status_started_records(self, _patch_execution, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "TxFailed",
            "dmOffersStatus": {"offer_item_001": {"started": True, "success": False}},
            "dmOffersFailReason": {},
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_500_propagates(self, _patch_execution, monkeypatch):
        """buy_items error propagates — no try/except around the API call."""
        monkeypatch.setenv("DRY_RUN", "false")
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(side_effect=Exception("API 500"))

        with pytest.raises(Exception, match="API 500"):
            await _ExecutionMixin._execute_instant_buys(
                mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
            )
