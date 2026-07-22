"""Tests for inventory_manager.py — DMarket inventory + oracle price data."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.inventory_manager import InventoryManager


def _make_manager() -> tuple[InventoryManager, MagicMock]:
    api = AsyncMock()
    oracle = AsyncMock()
    with patch("src.inventory_manager.OracleFactory") as mock_factory:
        mock_factory.get_cross_market_oracle.return_value = oracle
        manager = InventoryManager(api_client=api)
        manager._mock_oracle = oracle
        return manager, api


class TestFetchInventory:

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        result = await manager.fetch_inventory("a8db")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_page(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47"}],
        })
        result = await manager.fetch_inventory("a8db")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_pagination(self):
        manager, api = _make_manager()
        call_count = 0
        async def _mock_inv(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"objects": [{"itemId": "i1"}] * 50, "cursor": "p2"}
            return {"objects": [{"itemId": "i2"}]}

        api.get_user_inventory = AsyncMock(side_effect=_mock_inv)
        result = await manager.fetch_inventory("a8db")
        assert len(result) == 51

    @pytest.mark.asyncio
    async def test_api_error_returns_cache(self):
        manager, api = _make_manager()
        manager.cached_inventory = [{"itemId": "cached"}]
        api.get_user_inventory = AsyncMock(side_effect=Exception("API down"))
        result = await manager.fetch_inventory("a8db")
        assert result == [{"itemId": "cached"}]


class TestFetchActiveOffers:

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        manager, api = _make_manager()
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        result = await manager.fetch_active_offers("a8db")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_page(self):
        manager, api = _make_manager()
        api.get_user_offers = AsyncMock(return_value={
            "objects": [{"offerId": "o1", "title": "AK-47"}],
        })
        result = await manager.fetch_active_offers("a8db")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self):
        manager, api = _make_manager()
        api.get_user_offers = AsyncMock(side_effect=Exception("API down"))
        result = await manager.fetch_active_offers("a8db")
        assert result == []


class TestFetchAllWithOracle:

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory_count"] == 0
        assert result["offers_count"] == 0

    @pytest.mark.asyncio
    async def test_enriches_with_oracle_prices(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})

        snap = MagicMock()
        snap.has_data = True
        snap.min_price = 15.0
        manager._mock_oracle.get_prices_batch = AsyncMock(
            return_value={"AK-47": snap},
        )

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 15.0
        assert result["inventory"][0]["profit_pct"] > 0

    @pytest.mark.asyncio
    async def test_oracle_attribute_error_fallback(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        manager._mock_oracle.get_item_price = AsyncMock(return_value=15.0)

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 15.0

    @pytest.mark.asyncio
    async def test_oracle_exception_handled(self):
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=Exception("timeout"))

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 0.0


class TestMarkItemPurchased:

    def test_marks_purchased(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            manager.mark_item_purchased("AK-47", 10.0, "item_001")
            mock_db.add_virtual_item.assert_called_once()
            mock_db.record_placed_target.assert_called_once_with("item_001", "AK-47", 10.0)

    def test_marks_purchased_no_id(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            manager.mark_item_purchased("AK-47", 10.0)
            mock_db.add_virtual_item.assert_called_once()
            mock_db.record_placed_target.assert_not_called()


class TestMarkItemListed:

    def test_marks_listed(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            manager.mark_item_listed(1, 15.0)
            mock_db.update_virtual_status.assert_called_once_with(1, "selling")


class TestMarkItemSold:

    def test_marks_sold(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            manager.mark_item_sold(1, 15.0, 0.75)
            mock_db.record_virtual_sale.assert_called_once_with(1, 15.0, 0.75)


class TestIsItemPurchased:

    def test_returns_true(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.has_target_been_placed.return_value = True
            assert manager.is_item_purchased("item_001") is True

    def test_returns_false(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.has_target_been_placed.return_value = False
            assert manager.is_item_purchased("item_001") is False


class TestGetPortfolioSummary:

    def test_returns_summary(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_total_equity.return_value = {
                "cash": 50.0, "assets": 30.0, "total": 80.0,
            }
            mock_db.get_virtual_inventory.side_effect = [
                [{"buy_price": 10.0}],  # idle
                [{"buy_price": 15.0}],  # selling
                [{"buy_price": 8.0, "sell_price": 12.0, "fee_paid": 0.5}],  # sold
            ]
            result = manager.get_portfolio_summary(50.0)

        assert result["cash"] == 50.0
        assert result["items_holding"] == 2
        assert result["items_sold"] == 1


class TestCheckHeldItemsPrices:

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        manager, _ = _make_manager()
        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = []
            result = await manager.check_held_items_prices()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_oracle_prices(self):
        manager, _ = _make_manager()
        items = [{"hash_name": "AK-47", "buy_price": 10.0, "status": "idle", "acquired_at": 1000.0}]
        snap = MagicMock()
        snap.has_data = True
        snap.min_price = 15.0
        manager._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47": snap})
        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = items
            result = await manager.check_held_items_prices()

        assert len(result) == 1
        assert result[0]["oracle_price"] == 15.0
        assert result[0]["unrealized_pnl_pct"] > 0


class TestCacheMethods:

    def test_get_inventory(self):
        manager, _ = _make_manager()
        manager.cached_inventory = [{"itemId": "i1"}]
        assert manager.get_inventory() == [{"itemId": "i1"}]

    def test_get_offers(self):
        manager, _ = _make_manager()
        manager.cached_offers = [{"offerId": "o1"}]
        assert manager.get_offers() == [{"offerId": "o1"}]


class TestFetchAllWithOracleExtended:

    @pytest.mark.asyncio
    async def test_enriches_offers(self):
        """Offers are enriched with oracle prices (lines 146-157)."""
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={"objects": []})
        api.get_user_offers = AsyncMock(return_value={
            "objects": [{"offerId": "o1", "title": "AK-47", "price": {"USD": "1500"}}],
        })
        snap = MagicMock()
        snap.has_data = True
        snap.min_price = 20.0
        manager._mock_oracle.get_prices_batch = AsyncMock(return_value={"AK-47": snap})

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["offers_count"] == 1
        assert result["inventory"][0]["status"] == "on_sale"
        assert result["inventory"][0]["oracle_price"] == 20.0

    @pytest.mark.asyncio
    async def test_oracle_attribute_error_fallback(self):
        """AttributeError triggers per-item fallback (lines 170-177)."""
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        manager._mock_oracle.get_item_price = AsyncMock(return_value=15.0)

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 15.0

    @pytest.mark.asyncio
    async def test_oracle_per_item_exception(self):
        """Per-item oracle exception is caught (line 176-177)."""
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        manager._mock_oracle.get_item_price = AsyncMock(side_effect=Exception("timeout"))

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 0.0

    @pytest.mark.asyncio
    async def test_oracle_generic_exception(self):
        """Generic oracle exception is caught (line 178-179)."""
        manager, api = _make_manager()
        api.get_user_inventory = AsyncMock(return_value={
            "objects": [{"itemId": "i1", "title": "AK-47", "price": {"USD": "1000"}}],
        })
        api.get_user_offers = AsyncMock(return_value={"objects": []})
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=Exception("timeout"))

        result = await manager.fetch_all_with_oracle("a8db")
        assert result["inventory"][0]["oracle_price"] == 0.0


class TestCheckHeldItemsPricesExtended:

    @pytest.mark.asyncio
    async def test_oracle_attribute_error_fallback(self):
        """AttributeError triggers per-item fallback (lines 280-287)."""
        manager, _ = _make_manager()
        items = [{"hash_name": "AK-47", "buy_price": 10.0, "status": "idle", "acquired_at": 1000.0}]
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        manager._mock_oracle.get_item_price = AsyncMock(return_value=15.0)

        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = items
            result = await manager.check_held_items_prices()

        assert result[0]["oracle_price"] == 15.0

    @pytest.mark.asyncio
    async def test_oracle_per_item_exception(self):
        """Per-item exception in fallback is caught (lines 286-287)."""
        manager, _ = _make_manager()
        items = [{"hash_name": "AK-47", "buy_price": 10.0, "status": "idle", "acquired_at": 1000.0}]
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=AttributeError("no batch"))
        manager._mock_oracle.get_item_price = AsyncMock(side_effect=Exception("timeout"))

        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = items
            result = await manager.check_held_items_prices()

        assert result[0]["oracle_price"] == 0.0

    @pytest.mark.asyncio
    async def test_oracle_generic_exception(self):
        """Generic oracle exception is caught (lines 288-289)."""
        manager, _ = _make_manager()
        items = [{"hash_name": "AK-47", "buy_price": 10.0, "status": "idle", "acquired_at": 1000.0}]
        manager._mock_oracle.get_prices_batch = AsyncMock(side_effect=Exception("timeout"))

        with patch("src.inventory_manager.price_db") as mock_db:
            mock_db.get_virtual_inventory.return_value = items
            result = await manager.check_held_items_prices()

        assert result[0]["oracle_price"] == 0.0
