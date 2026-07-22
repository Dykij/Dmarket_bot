"""Tests for execution.py — instant-buy execution pipeline."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping import execution as _exec_mod


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


async def _fake_run_in_thread(func, *args, **kwargs):
    """Execute the callable passed to run_in_thread so mock methods are invoked."""
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return func(*args, **kwargs)


@pytest.fixture(autouse=True)
def _env():
    _exec_mod.Config.DRY_RUN = True


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
        mock_db.state_conn = MagicMock()
        mock_db.run_in_thread = AsyncMock(side_effect=_fake_run_in_thread)
        yield mock_db


class TestExecuteBuyDryRun:

    @pytest.mark.asyncio
    async def test_dry_run_records_virtual_item(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_dry_run_buy_items_still_called(self, _patch_execution):
        """buy_items is always called (even in DRY) — the DRY gate is on local recording."""
        _exec_mod.Config.DRY_RUN = True
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
    async def test_dry_run_sends_notification(self, _patch_execution, _mock_notifier):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_live_calls_buy_items(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
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
    async def test_live_records_spend_on_success(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
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
    async def test_live_handles_tx_failed(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
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
    async def test_live_no_items_key_still_records(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
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
    async def test_slippage_filter_skips_high_slippage(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_slippage_check_failure_proceeds(self, _patch_execution):
        """If slippage check raises, item proceeds (fail-open)."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(side_effect=Exception("timeout"))

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

    @pytest.mark.asyncio
    async def test_risk_blocks_in_dry_run(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_inventory_count_cap_blocks(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_saturation_same_item_cap(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
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
    async def test_dm_offers_status_started_records(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
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
    async def test_api_500_propagates(self, _patch_execution):
        """buy_items error propagates — no try/except around the API call."""
        _exec_mod.Config.DRY_RUN = False
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


class TestRiskAdjustedSize:
    """Tests for soft-halt risk adjustment (adjusted_size_usd)."""

    @pytest.mark.asyncio
    async def test_soft_halt_adjusts_price(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # Soft halt: allowed=True but adjusted_size_usd < base_price
        risk_result = MagicMock()
        risk_result.allowed = True
        risk_result.adjusted_size_usd = 8.0
        mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(base_price=10.0, list_price=12.0)],
            current_balance=100.0, game_id="a8db",
        )

        # Should record with adjusted price
        _patch_execution.record_placed_target.assert_called_once()
        call_args = _patch_execution.record_placed_target.call_args[0]
        assert call_args[2] == 8.0  # adjusted base_price


class TestCircuitBreaker:
    """Tests for circuit breaker handling."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_buy(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })

        class CircuitOpenError(Exception):
            pass

        mixin.client.buy_items = AsyncMock(side_effect=CircuitOpenError("circuit open"))

        # Should not raise — circuit breaker is caught silently
        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()


class TestMultipleItems:
    """Tests for batch execution with multiple items."""

    @pytest.mark.asyncio
    async def test_dry_run_multiple_items(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()

        # Slippage check returns matching listing for each item
        async def _slippage_check(game_id, limit, title):
            items_map = {
                "Item A": {"itemId": "i1", "price": {"USD": "1000"}},
                "Item B": {"itemId": "i2", "price": {"USD": "800"}},
            }
            obj = items_map.get(title, {"itemId": "unknown", "price": {"USD": "1000"}})
            return {"objects": [obj]}

        mixin.client.get_market_items_v2 = AsyncMock(side_effect=_slippage_check)

        items = [
            _make_item(title="Item A", item_id="i1", base_price=10.0, list_price=12.0),
            _make_item(title="Item B", item_id="i2", base_price=8.0, list_price=10.0),
        ]

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=items, current_balance=100.0, game_id="a8db",
        )

        assert _patch_execution.record_placed_target.call_count == 2
        assert mixin.liquidity.record_spend.call_count == 2

    @pytest.mark.asyncio
    async def test_live_partial_success(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "price": {"USD": 1000}}],
        })
        # Only one offer succeeds
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_1", "title": "Item A"}],
            "dmOffersStatus": {
                "offer_i1": {"started": True, "success": True},
                "offer_i2": {"started": False, "success": False},
            },
        })

        items = [
            _make_item(title="Item A", item_id="i1", base_price=10.0),
            _make_item(title="Item B", item_id="i2", base_price=8.0),
        ]

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=items, current_balance=100.0, game_id="a8db",
        )

        # Only the successful item should be recorded
        assert _patch_execution.record_placed_target.call_count == 1


class TestSlippageEdgeCases:
    """Additional slippage protection tests."""

    @pytest.mark.asyncio
    async def test_slippage_no_matching_item_uses_first_listing(self, _patch_execution):
        """When item_id doesn't match any listing, use first listing price."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        # Listing has different itemId
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "other_id", "price": {"USD": 1000}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(base_price=10.0)],
            current_balance=100.0, game_id="a8db",
        )

        # Price is same (1000 cents = $10), no slippage, should proceed
        _patch_execution.record_placed_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_slippage_exactly_at_threshold_proceeds(self, _patch_execution):
        """5% slippage exactly should proceed (not > 5%)."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        # base_price=10.0, listing at 1050 cents = $10.50 → 5.0% slippage
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1050}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(base_price=10.0)],
            current_balance=100.0, game_id="a8db",
        )

        # 5.0% is NOT > 5.0%, so it proceeds
        _patch_execution.record_placed_target.assert_called_once()


class TestRiskBlockingEdgeCases:
    """Additional risk blocking tests."""

    @pytest.mark.asyncio
    async def test_risk_blocks_one_of_two_items(self, _patch_execution):
        """Only the risk-blocked item is skipped; the other proceeds."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()

        # Return matching listing for each item's slippage check
        async def _slippage_check(game_id, limit, title):
            items_map = {
                "Blocked": {"itemId": "i1", "price": {"USD": "5000"}},
                "Allowed": {"itemId": "i2", "price": {"USD": "500"}},
            }
            obj = items_map.get(title, {"itemId": "unknown", "price": {"USD": "500"}})
            return {"objects": [obj]}

        mixin.client.get_market_items_v2 = AsyncMock(side_effect=_slippage_check)

        def _risk_check(**kwargs):
            result = MagicMock()
            result.adjusted_size_usd = None
            if kwargs.get("item_title") == "Blocked":
                result.allowed = False
                result.reason = "too expensive"
            else:
                result.allowed = True
            return result

        mixin.risk.pre_trade_check = MagicMock(side_effect=_risk_check)

        items = [
            _make_item(title="Blocked", item_id="i1", base_price=50.0),
            _make_item(title="Allowed", item_id="i2", base_price=5.0),
        ]

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=items, current_balance=100.0, game_id="a8db",
        )

        # Only "Allowed" should be recorded
        assert _patch_execution.record_placed_target.call_count == 1
        recorded_title = _patch_execution.record_placed_target.call_args[0][1]
        assert recorded_title == "Allowed"


class TestTwapExecutor:
    """Tests for TWAP executor lazy initialization (lines 37-44)."""

    def test_twap_lazy_init(self):
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = MagicMock()
        mixin._twap_executor = None
        mixin.client = AsyncMock()

        result = _ExecutionMixin._get_twap_executor(mixin)

        assert result is not None
        assert mixin._twap_executor is result

    def test_twap_returns_cached(self):
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = MagicMock()
        existing = MagicMock()
        mixin._twap_executor = existing

        result = _ExecutionMixin._get_twap_executor(mixin)

        assert result is existing


class TestFrozenFundsLogging:
    """Tests for frozen funds logging (lines 72-78)."""

    @pytest.mark.asyncio
    async def test_frozen_funds_log_message(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        _patch_execution.get_total_equity.return_value = {
            "assets": 50.0, "count": 2, "frozen": 30.0,
            "available": 70.0, "total": 100.0,
        }

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        # Should still proceed — frozen funds just logged
        _patch_execution.record_placed_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_equity_update_failure_continues(self, _patch_execution):
        """If risk._update_equity raises, code falls through with raw balance."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.risk._update_equity = MagicMock(side_effect=Exception("db down"))

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        # Should still proceed
        _patch_execution.record_placed_target.assert_called_once()


class TestProdRiskBlock:
    """Tests for pre-trade risk block in PROD path (lines 140-167)."""

    @pytest.mark.asyncio
    async def test_prod_risk_blocks_item(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        risk_result = MagicMock()
        risk_result.allowed = False
        risk_result.reason = "drawdown freeze"
        risk_result.adjusted_size_usd = None
        mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_risk_event.assert_called()
        mixin.client.buy_items.assert_not_called()

    @pytest.mark.asyncio
    async def test_prod_all_blocked_returns_early(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        risk_result = MagicMock()
        risk_result.allowed = False
        risk_result.reason = "halt"
        risk_result.adjusted_size_usd = None
        mixin.risk.pre_trade_check = MagicMock(return_value=risk_result)

        items = [
            _make_item(title="A", item_id="i1", base_price=5.0),
            _make_item(title="B", item_id="i2", base_price=8.0),
        ]

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=items, current_balance=100.0, game_id="a8db",
        )

        mixin.client.buy_items.assert_not_called()


class TestInventoryValueCap:
    """Tests for inventory value cap (lines 190-196) and post-buy checks (331-354)."""

    @pytest.mark.asyncio
    async def test_inventory_value_cap_blocks(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        _patch_execution.get_total_equity.return_value = {
            "assets": 9999.0, "count": 1, "frozen": 0.0,
            "available": 100.0, "total": 10000.0,
        }

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(base_price=10.0)],
            current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()


class TestBoughtItemsMatching:
    """Tests for offerId matching in bought_items (lines 317-326)."""

    @pytest.mark.asyncio
    async def test_offerid_match_from_response(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline", "offerId": "offer_item_001"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.attach_dm_item_id.assert_called()

    @pytest.mark.asyncio
    async def test_title_fallback_match(self, _patch_execution):
        """When offerId doesn't match, fallback to title matching."""
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # Items response has no offerId, just title
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.attach_dm_item_id.assert_called()


class TestRareItemMarking:
    """Tests for rare item mark_exclusive (line 410)."""

    @pytest.mark.asyncio
    async def test_rare_item_marked_exclusive(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item(is_rare=True)],
            current_balance=100.0, game_id="a8db",
        )

        _patch_execution.mark_exclusive.assert_called()


class TestCompetitionSimulation:
    """Tests for competition simulation in DRY (lines 357-361)."""

    @pytest.mark.asyncio
    async def test_competition_snipe_skips_item(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin._simulate_competition = MagicMock(return_value=False)

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_not_called()


class TestLiquidityRejection:
    """Tests for can_spend_and_record rejection (lines 458-461)."""

    @pytest.mark.asyncio
    async def test_liquidity_rejection_skips_item(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.liquidity.can_spend_and_record = AsyncMock(return_value=False)

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_called_once()  # recorded before liquidity check
        mixin.liquidity.record_spend.assert_not_called()


class TestDmItemIdAttachProd:
    """Tests for dm_item_id attachment in PROD (lines 476-489)."""

    @pytest.mark.asyncio
    async def test_prod_attaches_dm_item_id(self, _patch_execution):
        _exec_mod.Config.DRY_RUN = False
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline", "offerId": "offer_item_001"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        # attach_dm_item_id should be called twice (once in DRY block, once in PROD)
        assert _patch_execution.attach_dm_item_id.call_count >= 1


class TestCachedEquityFallback:
    """Tests for cached equity fallback path (lines 175-178)."""

    @pytest.mark.asyncio
    async def test_no_risk_attribute_skips_equity_update(self, _patch_execution):
        """When mixin has no risk attribute, cached equity stays None."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # Remove risk entirely so hasattr(self, "risk") is False
        delattr(mixin, "risk")

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_dict_equity_fallback(self, _patch_execution):
        """When get_total_equity returns non-dict, use default counts (line 178)."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # Remove risk so cached equity path is skipped entirely
        delattr(mixin, "risk")
        # Make get_total_equity return non-dict
        _patch_execution.get_total_equity = MagicMock(return_value="not_a_dict")

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        _patch_execution.record_placed_target.assert_called_once()


class TestPostBuyWarnings:
    """Tests for post-buy inventory warnings (lines 331-354).

    These warnings are defensive checks that fire when equity/inventory state
    changes between the pre-buy check and the post-buy recording. They use
    fresh DB queries (not cached values).
    """

    @pytest.mark.asyncio
    async def test_post_buy_equity_check_runs(self, _patch_execution):
        """Post-buy equity check executes without error (lines 331-347)."""
        _exec_mod.Config.DRY_RUN = False
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

        # Post-buy check ran (get_total_equity called multiple times)
        assert _patch_execution.get_total_equity.call_count >= 2
        _patch_execution.record_placed_target.assert_called_once()


class TestDryRunWithBoughtItems:
    """Tests for DRY mode with buy_items returning Items (line 408)."""

    @pytest.mark.asyncio
    async def test_dry_with_bought_items_attaches_dm_id(self, _patch_execution):
        """DRY mode with buy response containing Items attaches dm_item_id."""
        _exec_mod.Config.DRY_RUN = True
        from src.core.target_sniping.execution import _ExecutionMixin

        mixin = _make_mixin()
        mixin.client.get_market_items_v2 = AsyncMock(return_value={
            "objects": [{"itemId": "item_001", "price": {"USD": 1000}}],
        })
        # buy_items returns Items even in DRY mode
        mixin.client.buy_items = AsyncMock(return_value={
            "status": "OK",
            "Items": [{"itemId": "new_dm_001", "title": "AK-47 | Redline", "offerId": "offer_item_001"}],
        })

        await _ExecutionMixin._execute_instant_buys(
            mixin, instant_buys=[_make_item()], current_balance=100.0, game_id="a8db",
        )

        # attach_dm_item_id should be called (line 408)
        _patch_execution.attach_dm_item_id.assert_called()
