"""Tests for resale_pipeline.py — end-to-end buy-sell pipeline."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.resale_pipeline import ResalePipeline
from src.core import resale_pipeline as _rp_mod


def _make_dmarket_item(
    item_id: str = "dm_001",
    title: str = "AK-47 | Redline",
    price_cents: int = 1000,
) -> dict[str, Any]:
    return {
        "itemId": item_id,
        "title": title,
        "price": {"USD": str(price_cents)},
    }


def _make_virtual_item(
    item_id: int = 1,
    hash_name: str = "AK-47 | Redline",
    buy_price: float = 10.0,
    status: str = "idle",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "hash_name": hash_name,
        "buy_price": buy_price,
        "status": status,
        "acquired_at": 1700000000.0,
    }


def _make_pipeline() -> tuple[ResalePipeline, MagicMock]:
    """Create a ResalePipeline with mocked dependencies (oracle removed)."""
    api = AsyncMock()
    api.get_item_fee = AsyncMock(return_value=0.05)

    with patch("src.core.resale_pipeline.price_db") as mock_db:
        risk = MagicMock()
        risk_result = MagicMock()
        risk_result.allowed = True
        risk_result.reason = ""
        risk.pre_trade_check = MagicMock(return_value=risk_result)
        risk.record_trade_outcome = MagicMock()

        mock_db.run_in_thread.return_value = False
        mock_db.get_virtual_inventory.return_value = []
        mock_db.add_virtual_item = MagicMock()
        mock_db.record_placed_target = MagicMock()
        mock_db.update_virtual_status = MagicMock()

        pipeline = ResalePipeline(api_client=api, risk=risk)
        pipeline._mock_db = mock_db
        return pipeline, api


class TestCalculateSellPrice:
    """Tests for _calculate_sell_price(buy_price, reference_price, fee_rate)."""

    def test_basic_reference_price(self):
        """Sell price based on reference price with min profit enforcement."""
        pipeline, _ = _make_pipeline()
        result = pipeline._calculate_sell_price(
            buy_price=10.0, reference_price=15.0, fee_rate=0.05,
        )
        # min_sell = 10.0 * (1 + 0.015) / (1 - 0.05) ≈ 10.68
        # max_allowed = 15.0 * 1.10 = 16.50
        # target_sell = max(15.0, 10.68) = 15.0, then min(15.0, 16.50) = 15.0
        assert result == 15.0

    def test_reference_price_zero_fallback(self):
        """When reference_price is 0, fallback to buy_price * 1.10."""
        pipeline, _ = _make_pipeline()
        result = pipeline._calculate_sell_price(
            buy_price=10.0, reference_price=0.0, fee_rate=0.05,
        )
        assert result == 11.0

    def test_min_profit_margin_enforced(self):
        """Sell price respects minimum profit margin."""
        pipeline, _ = _make_pipeline()
        original = _rp_mod.Config.MIN_SPREAD_PCT
        try:
            _rp_mod.Config.MIN_SPREAD_PCT = 10.0
            result = pipeline._calculate_sell_price(
                buy_price=10.0, reference_price=10.5, fee_rate=0.05,
            )
        finally:
            _rp_mod.Config.MIN_SPREAD_PCT = original
        # min_sell = 10.0 * (1 + 0.10) / (1 - 0.05) ≈ 11.58
        # max_allowed = 10.5 * 1.10 = 11.55
        # target_sell = max(10.5, 11.58) = 11.58, then min(11.58, 11.55) = 11.55
        assert result == 11.55
        assert result > 10.0  # profitable

    def test_does_not_exceed_max_above_reference(self):
        """Sell price doesn't exceed reference * 1.10."""
        pipeline, _ = _make_pipeline()
        original = _rp_mod.Config.MIN_SPREAD_PCT
        try:
            _rp_mod.Config.MIN_SPREAD_PCT = 50.0
            result = pipeline._calculate_sell_price(
                buy_price=10.0, reference_price=12.0, fee_rate=0.05,
            )
        finally:
            _rp_mod.Config.MIN_SPREAD_PCT = original
        # max_allowed = 12.0 * 1.10 = 13.20
        assert result <= 13.20


class TestSellInventoryItems:

    @pytest.mark.asyncio
    async def test_empty_inventory_returns_empty(self):
        pipeline, _ = _make_pipeline()
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=[]):
            result = await pipeline.sell_inventory_items()
        assert result == []

    @pytest.mark.asyncio
    async def test_dry_run_lists_items(self):
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="AK-47 | Redline", buy_price=10.0)]
        # Mock aggregated prices API (replaces oracle)
        api.get_aggregated_prices = AsyncMock(return_value={
            "AK-47 | Redline": {"best_bid": 15.0, "best_ask": 16.0},
        })
        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.object(_rp_mod.price_db, "update_virtual_status") as mock_update,
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 5.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread
        assert len(result) == 1
        assert result[0]["status"] == "listed_sim"
        mock_update.assert_called_once_with(1, "selling")

    @pytest.mark.asyncio
    async def test_low_margin_item_skipped(self):
        pipeline, api = _make_pipeline()
        virtual_items = [_make_virtual_item(item_id=1, hash_name="Expensive", buy_price=14.0)]
        api.get_aggregated_prices = AsyncMock(return_value={
            "Expensive": {"best_bid": 14.5, "best_ask": 15.0},
        })
        with (
            patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=virtual_items),
            patch.dict("os.environ", {"DRY_RUN": "true"}),
        ):
            orig_fee, orig_spread = _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT
            try:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = 0.05, 10.0
                result = await pipeline.sell_inventory_items()
            finally:
                _rp_mod.Config.FEE_RATE, _rp_mod.Config.MIN_SPREAD_PCT = orig_fee, orig_spread
        assert result == []


class TestGetInventoryStatus:

    @pytest.mark.asyncio
    async def test_returns_virtual_and_real_counts(self):
        pipeline, api = _make_pipeline()
        idle_items = [_make_virtual_item(status="idle")]
        selling_items = [_make_virtual_item(status="selling")]
        call_count = 0
        def _get_virtual(status=None, only_unlocked=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return idle_items
            elif call_count == 2:
                return selling_items
            return []
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", side_effect=_get_virtual):
            api.get_user_inventory = AsyncMock(return_value={"objects": [{}] * 3})
            api.get_user_offers = AsyncMock(return_value={"objects": [{}] * 2})
            result = await pipeline.get_inventory_status()
        assert result["virtual"]["idle"] == 1
        assert result["virtual"]["selling"] == 1
        assert result["real"]["inventory"] == 3
        assert result["real"]["active_offers"] == 2

    @pytest.mark.asyncio
    async def test_api_failure_handled_gracefully(self):
        pipeline, api = _make_pipeline()
        with patch.object(_rp_mod.price_db, "get_virtual_inventory", return_value=[]):
            api.get_user_inventory = AsyncMock(side_effect=Exception("down"))
            api.get_user_offers = AsyncMock(side_effect=Exception("down"))
            result = await pipeline.get_inventory_status()
        assert result["real"]["inventory"] == 0
        assert result["real"]["active_offers"] == 0


class TestTurnoverPenalty:

    def test_lazy_init_market_maker(self):
        pipeline, _ = _make_pipeline()
        assert pipeline._turnover_mm is None
        with patch("src.strategies.market_maker.MarketMaker") as mock_mm:
            mock_mm.return_value = MagicMock(calculate_turnover_penalty=MagicMock(return_value=0.02))
            result = pipeline._get_turnover_penalty()
        assert result == 0.02
        assert pipeline._turnover_mm is not None


