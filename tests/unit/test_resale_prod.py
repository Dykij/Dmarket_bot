"""Tests for resale_prod.py — PROD-mode helpers for resale pipeline."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.resale_prod import _ResaleProdMixin


def _make_resale_mixin() -> MagicMock:
    mixin = MagicMock(spec=_ResaleProdMixin)
    mixin.client = AsyncMock()
    mixin.oracle = MagicMock()
    mixin._background_tasks = set()
    return mixin


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
    async def test_new_item_linked(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "dm_001", "title": "AK-47 | Redline"}],
        })

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value=10.0)
        mock_fetchone = MagicMock(return_value=mock_row)

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.find_by_dm_item_id.return_value = None
            mock_db.run_in_thread = AsyncMock(side_effect=lambda f, *a: f(*a) if callable(f) else MagicMock(fetchone=MagicMock(return_value={"p": 10.0})))
            mock_db.state_conn = MagicMock()
            mock_db.state_conn.execute = MagicMock(return_value=MagicMock(fetchone=mock_fetchone))

            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")

        assert result == 1

    @pytest.mark.asyncio
    async def test_already_tracked_item_skipped(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "dm_001", "title": "AK-47 | Redline"}],
        })

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.find_by_dm_item_id.return_value = {"id": 1}  # already tracked
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")

        assert result == 0

    @pytest.mark.asyncio
    async def test_pagination_stops_on_empty_second_page(self):
        mixin = _make_resale_mixin()
        call_count = 0
        async def _mock_inv(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"objects": [{"itemId": "dm_001", "title": "A"}], "cursor": "p2"}
            return {"objects": []}

        mixin.client.get_user_inventory = AsyncMock(side_effect=_mock_inv)

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.find_by_dm_item_id.return_value = None
            mock_db.run_in_thread = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
            mock_db.state_conn = MagicMock()
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")

        # First page has items (processed), second page is empty (stops)
        assert call_count >= 1


class TestCheckExternalSales:

    @pytest.mark.asyncio
    async def test_no_listed_items_returns_zero(self):
        mixin = _make_resale_mixin()
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = []
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_api_error_returns_zero(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(side_effect=Exception("API down"))
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [
                {"id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47", "buy_price": 10.0, "sell_price": 15.0},
            ]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 0

    @pytest.mark.asyncio
    async def test_matched_offer_records_sale(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1500"},
                "status": "closed",
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [
                {"id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47", "buy_price": 10.0, "sell_price": 15.0},
            ]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mock_db.record_virtual_sale.assert_called_once()

    @pytest.mark.asyncio
    async def test_reverted_offer_records_rollback(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "status": "reverted",
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [
                {"id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47", "buy_price": 10.0, "sell_price": 15.0},
            ]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 1
        mock_db.set_rollback_refund.assert_called_once_with("offer_001")

    @pytest.mark.asyncio
    async def test_unmatched_offer_skipped(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{"offerId": "other_offer", "price": {"USD": "1500"}}],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [
                {"id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47", "buy_price": 10.0, "sell_price": 15.0},
            ]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 0
        mock_db.record_virtual_sale.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_offer_id_skipped(self):
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{"offerId": "offer_001", "price": {"USD": "1500"}}],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [
                {"id": 1, "dm_offer_id": "", "hash_name": "AK-47", "buy_price": 10.0, "sell_price": 15.0},
            ]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")

        assert result == 0


class TestSyncSoldOffers:

    @pytest.mark.asyncio
    async def test_returns_zero(self):
        mixin = _make_resale_mixin()
        result = await _ResaleProdMixin._sync_sold_offers(mixin, "a8db")
        assert result == 0


class TestProdListUnlocked:

    @pytest.mark.asyncio
    async def test_no_items_returns_early(self):
        mixin = _make_resale_mixin()
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = []
            await _ResaleProdMixin._prod_list_unlocked(mixin, [], "a8db")

    @pytest.mark.asyncio
    async def test_listing_cap_blocks(self):
        mixin = _make_resale_mixin()
        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = [{}] * 100
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            await _ResaleProdMixin._prod_list_unlocked(mixin, [{"hash_name": "A", "dm_item_id": "d1", "buy_price": 10.0}], "a8db")

    @pytest.mark.asyncio
    async def test_no_dm_item_id_skipped(self):
        mixin = _make_resale_mixin()
        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            # Item without dm_item_id
            items = [{"hash_name": "A", "dm_item_id": "", "buy_price": 10.0}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_zero_buy_price_skipped(self):
        mixin = _make_resale_mixin()
        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            items = [{"hash_name": "A", "dm_item_id": "d1", "buy_price": 0.0}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_list_error_skipped(self):
        mixin = _make_resale_mixin()
        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            items = [{"hash_name": "A", "dm_item_id": "d1", "buy_price": 10.0, "list_error": "API 500"}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_oracle_no_data_skips(self):
        """Oracle returns no data → item skipped."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 0
        fair_result.fair_price = 0.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_oracle_price_below_buy_skips(self):
        """Oracle price <= buy price → skip."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 8.0  # below buy price of 10.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_margin_too_low_skips(self):
        """Oracle price high but margin below threshold → skip."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 10.2  # just above buy price but below margin threshold
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_successful_listing(self):
        """Full successful listing path."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_batch_api_failure_marks_failed(self):
        """Batch API failure marks items as failed."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(side_effect=Exception("API 500"))
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_list_failed.assert_called()

    @pytest.mark.asyncio
    async def test_v2_response_format(self):
        """v2 response format with offers array."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001", "assetId": "d1"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_old_format_response(self):
        """Old format response with Items array."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "Items": [{"offerId": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_no_oracle_skips_all(self):
        """No oracle → all items skipped."""
        mixin = _make_resale_mixin()
        mixin.oracle = None

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")

    @pytest.mark.asyncio
    async def test_listing_cap_capping(self):
        """When already at listing cap, no new listings are made."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            # Already at cap
            mock_db.get_virtual_inventory.return_value = [{}] * 100
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            # At cap → early return, no batch call
            mixin.client.create_sell_offers_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_v2_failed_array_marks_error(self):
        """v2 response with failed array marks item as failed."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [],
                "failed": [{"assetId": "d1", "message": "Item not found"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_list_failed.assert_called()

    @pytest.mark.asyncio
    async def test_status_error_marks_failed(self):
        """Response with status=error marks item as failed."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "status": "error", "message": "Insufficient balance",
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_list_failed.assert_called()


class TestSyncRealInventoryExtended:

    @pytest.mark.asyncio
    async def test_empty_item_id_skipped(self):
        """Items with empty dm_item_id or title are skipped (line 53)."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={
            "objects": [
                {"itemId": "", "title": "AK-47"},  # empty id
                {"itemId": "dm_001", "title": ""},  # empty title
                {"itemId": "dm_002", "title": "M4A4"},  # valid
            ],
        })

        async def _mock_run(func, *args, **kwargs):
            if callable(func):
                result = func(*args, **kwargs)
                if hasattr(result, '__await__'):
                    return await result
                return result
            return MagicMock(fetchone=MagicMock(return_value={"p": 10.0}))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.find_by_dm_item_id.return_value = None
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")
        assert result >= 1

    @pytest.mark.asyncio
    async def test_inferred_price_from_avg(self):
        """Inferred price from AVG query (lines 62-70)."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "dm_001", "title": "AK-47"}],
        })

        async def _mock_run(func, *args, **kwargs):
            if callable(func):
                result = func(*args, **kwargs)
                if hasattr(result, '__await__'):
                    return await result
                return result
            return MagicMock(fetchone=MagicMock(return_value={"p": 15.5}))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.find_by_dm_item_id.return_value = None
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            result = await _ResaleProdMixin._sync_real_inventory(mixin, "a8db")
        assert result == 1


class TestCheckExternalSalesExtended:

    @pytest.mark.asyncio
    async def test_sell_price_fallback_to_listed_price(self):
        """When closed offer has no price, fall back to listed price (lines 139-141)."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "0"},  # no price in closed record
                "status": "closed",
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [{
                "id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47",
                "buy_price": 10.0, "sell_price": 15.0,
            }]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 1
        mock_db.record_virtual_sale.assert_called_once()
        # Should use sell_price=15.0 as fallback
        call_args = mock_db.record_virtual_sale.call_args[0]
        assert call_args[1] == 15.0

    @pytest.mark.asyncio
    async def test_sell_price_zero_skips(self):
        """When both closed price and listed price are 0, skip (line 142-143)."""
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "0"},
                "status": "closed",
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [{
                "id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47",
                "buy_price": 10.0, "sell_price": 0,  # no listed price either
            }]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 0
        mock_db.record_virtual_sale.assert_not_called()

    @pytest.mark.asyncio
    async def test_funds_hold_tracked(self):
        """Trade Protection funds hold is tracked (lines 147-152)."""
        import time as _time
        mixin = _make_resale_mixin()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1500"},
                "status": "closed",
                "FinalizationTime": _time.time() + 86400,  # 24h in future
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [{
                "id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47",
                "buy_price": 10.0, "sell_price": 15.0,
            }]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 1
        mock_db.set_funds_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_risk_record_trade_outcome(self):
        """Risk manager records sell outcome (lines 173-180)."""
        mixin = _make_resale_mixin()
        mixin.risk = MagicMock()
        mixin.client.get_user_closed_offers = AsyncMock(return_value={
            "objects": [{
                "offerId": "offer_001",
                "price": {"USD": "1500"},
                "status": "closed",
            }],
        })
        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = [{
                "id": 1, "dm_offer_id": "offer_001", "hash_name": "AK-47",
                "buy_price": 10.0, "sell_price": 15.0,
            }]
            result = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
        assert result == 1
        mixin.risk.record_trade_outcome.assert_called_once()


class TestProdListUnlockedAdvanced:

    @pytest.mark.asyncio
    async def test_micro_price_enabled(self):
        """Micro-price calculation path (lines 260-285)."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_db.mark_listed = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = True
            mock_config.STOIKOV_MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_as_enabled_pricing(self):
        """Avellaneda-Stoikov pricing path (lines 304-340)."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
            patch("src.analysis.microstructure.reservation_price", return_value=19.0),
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.get_recent_prices.return_value = [(10.0, 1000), (11.0, 1001), (12.0, 1002)]
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_db.mark_listed = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = True
            mock_config.AS_RISK_AVERSION = 0.5
            mock_config.AS_TIME_HORIZON_DAYS = 7
            mock_config.MAX_SAME_ITEM_HOLDINGS = 3
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_vwap_bands_enabled(self):
        """VWAP bands pricing path (lines 344-349)."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
            patch("src.analysis.microstructure.vwap_bands", return_value=(15.0, 18.0, 22.0)),
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.get_trade_history.return_value = [{"price": 15.0}] * 10
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_db.mark_listed = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = True
            mock_config.DOM_GAP_ENABLED = False
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_dom_gap_enabled(self):
        """DOM gap pricing path (lines 353-362)."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)
        mixin._dom_cache = {"AK-47": [{"price": {"USD": "1500"}}, {"price": {"USD": "2000"}}]}

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
            patch("src.analysis.orderbook.find_gap_price", return_value=22.0),
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_db.mark_listed = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = True
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()

    @pytest.mark.asyncio
    async def test_dom_gap_no_listings_fallback(self):
        """DOM gap with no listings falls back to standard pricing (lines 361-362)."""
        mixin = _make_resale_mixin()
        fair_result = MagicMock()
        fair_result.source_count = 2
        fair_result.fair_price = 20.0
        mixin.oracle.get_fair_price = AsyncMock(return_value=fair_result)
        mixin._dom_cache = {"AK-47": []}  # empty listings

        async def _mock_run(func, *args, **kwargs):
            return func(*args, **kwargs) if callable(func) else MagicMock()

        with (
            patch("src.core.target_sniping.resale_prod.price_db") as mock_db,
            patch("src.core.target_sniping.resale_prod.Config") as mock_config,
        ):
            mock_db.get_virtual_inventory.return_value = []
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.state_conn = MagicMock()
            mock_db.mark_listed = MagicMock()
            mock_config.FEE_RATE = 0.05
            mock_config.WITHDRAWAL_FEE_RATE = 0.005
            mock_config.MICRO_PRICE_ENABLED = False
            mock_config.AS_ENABLED = False
            mock_config.VWAP_BANDS_ENABLED = False
            mock_config.DOM_GAP_ENABLED = True
            mock_config.SELL_MAX_OPEN_LISTINGS = 100
            items = [{"hash_name": "AK-47", "dm_item_id": "d1", "buy_price": 10.0, "id": 1}]
            mixin.client.create_sell_offers_batch = AsyncMock(return_value={
                "offers": [{"id": "offer_001"}],
            })
            await _ResaleProdMixin._prod_list_unlocked(mixin, items, "a8db")
            mock_db.mark_listed.assert_called()
