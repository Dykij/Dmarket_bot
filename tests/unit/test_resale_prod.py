"""Tests for resale_prod.py — PROD-mode helpers for resale pipeline.

Rewritten 2026-08-06: removed all oracle mocks, updated for _current_agg_prices
and fee_utils. Previous tests were broken by oracle removal (Phase 5-6).
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.resale_prod import _ResaleProdMixin


def _make_resale_mixin() -> MagicMock:
    """Create a mixin mock with current architecture (no oracle)."""
    mixin = MagicMock(spec=_ResaleProdMixin)
    mixin.client = AsyncMock()
    mixin._background_tasks = set()
    mixin._current_agg_prices = {}
    return mixin


def _make_listed_item(
    item_id: int = 1,
    hash_name: str = "AK-47 | Redline",
    buy_price: float = 10.0,
    dm_item_id: str = "dm_001",
    dm_offer_id: str = "offer_001",
) -> dict:
    return {
        "id": item_id,
        "hash_name": hash_name,
        "buy_price": buy_price,
        "dm_item_id": dm_item_id,
        "dm_offer_id": dm_offer_id,
        "status": "listed",
        "sell_price": 12.0,
        "acquired_at": time.time() - 86400,
    }


# =====================================================================
# _check_external_sales
# =====================================================================


class TestCheckExternalSales:

    @pytest.mark.asyncio
    async def test_no_listed_items_returns_zero(self):
        """Empty listed inventory → 0 detections."""
        mixin = _make_resale_mixin()
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(return_value=[])
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_api_error_returns_zero(self):
        """API failure → 0 detections (graceful handling)."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(side_effect=Exception("API down"))
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(return_value=[_make_listed_item()])
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_matched_offer_records_sale(self):
        """Closed offer matching dm_offer_id → records sale."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1200"},  # $12.00
                "status": "closed",
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [_make_listed_item()]
            mock_db.record_virtual_sale = MagicMock()
            mock_db.update_virtual_status = MagicMock()
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mock_db.record_virtual_sale.assert_called_once()

    @pytest.mark.asyncio
    async def test_reverted_offer_records_rollback(self):
        """Reverted offer → rollback refund recorded."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1200"},
                "status": "reverted",
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [_make_listed_item()]
            mock_db.set_rollback_refund = MagicMock()
            mock_db.update_virtual_status = MagicMock()
            mock_db.record_virtual_sale = MagicMock()
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mock_db.set_rollback_refund.assert_called_once_with("offer_001")

    @pytest.mark.asyncio
    async def test_unmatched_offer_skipped(self):
        """Offer not matching any local item → skipped."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{"offerId": "unknown_offer", "price": {"USD": "1000"}, "status": "closed"}],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [_make_listed_item()]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 0

    @pytest.mark.asyncio
    async def test_no_offer_id_skipped(self):
        """Item with empty dm_offer_id → skipped."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={"objects": []})

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        item = _make_listed_item(dm_offer_id="")
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [item]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 0


# =====================================================================
# _check_external_sales — Extended
# =====================================================================


class TestCheckExternalSalesExtended:

    @pytest.mark.asyncio
    async def test_sell_price_fallback_to_listed_price(self):
        """When closed offer has no price, falls back to listed sell_price."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "0"},  # No price in closed record
                "status": "closed",
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        item = _make_listed_item()
        item["sell_price"] = 12.50
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [item]
            mock_db.record_virtual_sale = MagicMock()
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        # Should use sell_price=12.50 from local record
        call_args = mock_db.record_virtual_sale.call_args
        assert call_args[0][1] == 12.50  # sell_price

    @pytest.mark.asyncio
    async def test_sell_price_zero_skips(self):
        """When both closed price and local sell_price are 0, item is skipped."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "0"},
                "status": "closed",
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        item = _make_listed_item()
        item["sell_price"] = 0
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [item]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 0

    @pytest.mark.asyncio
    async def test_funds_hold_tracked(self):
        """Items with future FinalizationTime get funds_hold recorded."""
        mixin = _make_resale_mixin()
        future_time = time.time() + 86400 * 7  # 7 days from now
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1200"},
                "status": "closed",
                "FinalizationTime": future_time,
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [_make_listed_item()]
            mock_db.record_virtual_sale = MagicMock()
            mock_db.set_funds_hold = MagicMock()
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mock_db.set_funds_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_record_trade_outcome(self):
        """Successful sale records trade outcome in risk manager."""
        mixin = _make_resale_mixin()
        mixin.risk = MagicMock()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1200"},
                "status": "closed",
            }],
        })

        async def _mock_run(fn, *args):
            return fn(*args) if callable(fn) else None

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory.return_value = [_make_listed_item()]
            mock_db.record_virtual_sale = MagicMock()
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mixin.risk.record_trade_outcome.assert_called_once()


# =====================================================================
# _prod_list_unlocked
# =====================================================================


class TestProdListUnlocked:

    @pytest.mark.asyncio
    async def test_no_items_returns_early(self):
        """Empty items list → no-op, no batch API call."""
        mixin = _make_resale_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")
        mock_get_inv.return_value = []

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [], "a8db")

        mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_dm_item_id_skipped(self):
        """Items without dm_item_id are skipped — no batch API call."""
        mixin = _make_resale_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return [{"id": 1, "hash_name": "Item", "buy_price": 10.0, "dm_item_id": None}]
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "Item", "buy_price": 10.0, "dm_item_id": None}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_buy_price_skipped(self):
        """Items with buy_price=0 are skipped — no batch API call."""
        mixin = _make_resale_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "Item", "buy_price": 0, "dm_item_id": "dm_001", "list_error": None}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_error_skipped(self):
        """Items with recent list_error are skipped — no batch API call."""
        mixin = _make_resale_mixin()
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "Item", "buy_price": 10.0, "dm_item_id": "dm_001", "list_error": "API 500"}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_margin_too_low_skips(self):
        """Items where best_bid < target_sell are skipped — no batch API call."""
        mixin = _make_resale_mixin()
        mixin._current_agg_prices = {"Item": {"best_bid": 10.10, "best_ask": 10.50}}
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "Item", "buy_price": 10.0, "dm_item_id": "dm_001", "list_error": None}
            ], "a8db")

        # best_bid (10.10) < target_sell (10.0 * 1.085 ≈ 10.85) → skipped
        mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_listing(self):
        """Valid item with sufficient margin → listed via batch API."""
        mixin = _make_resale_mixin()
        mixin._current_agg_prices = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 16.0}}
        mixin.client.create_sell_offers_batch = AsyncMock(return_value={
            "offers": [{"assetId": "dm_001", "id": "offer_001"}],
        })

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            mock_db.mark_listed = MagicMock()
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "AK-47 | Redline", "buy_price": 10.0, "dm_item_id": "dm_001", "list_error": None}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_called_once()


# =====================================================================
# _prod_list_unlocked — Advanced
# =====================================================================


class TestProdListUnlockedAdvanced:

    @pytest.mark.asyncio
    async def test_micro_price_enabled(self):
        """With AS_ENABLED, uses reservation price for listing."""
        mixin = _make_resale_mixin()
        mixin._current_agg_prices = {"AK-47 | Redline": {"best_bid": 15.0, "best_ask": 16.0}}
        mixin.client.create_sell_offers_batch = AsyncMock(return_value={
            "offers": [{"assetId": "dm_001", "id": "offer_001"}],
        })

        mock_get_inv = MagicMock(name="get_virtual_inventory")
        mock_get_recent = MagicMock(name="get_recent_prices")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            if fn is mock_get_recent:
                return [(14.0, time.time()), (14.5, time.time()), (15.0, time.time())]
            return MagicMock(fetchone=MagicMock(return_value=None))

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            mock_db.get_recent_prices = mock_get_recent
            mock_db.mark_listed = MagicMock()
            mock_config.AS_ENABLED = True
            mock_config.AS_RISK_AVERSION = 0.3
            mock_config.AS_TIME_HORIZON_DAYS = 7.0
            mock_config.MAX_SAME_ITEM_HOLDINGS = 3
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False

            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "AK-47 | Redline", "buy_price": 10.0, "dm_item_id": "dm_001", "list_error": None}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_called_once()


# =====================================================================
# _sync_real_inventory
# =====================================================================


class TestSyncRealInventory:

    @pytest.mark.asyncio
    async def test_empty_inventory_returns_zero(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={"objects": []})
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_api_error_returns_zero(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(side_effect=Exception("API down"))
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_already_tracked_item_skipped(self):
        """Items already in virtual_inventory are not re-added."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "dm_001", "title": "AK-47 | Redline"}],
        })

        async def _mock_run(fn, *args):
            return MagicMock(fetchone=MagicMock(return_value={"id": 1}))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.find_by_dm_item_id = MagicMock(return_value={"id": 1})  # Already tracked
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")

        assert result == 0  # No new items linked
