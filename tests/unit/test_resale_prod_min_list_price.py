"""Regression tests for the PROD listing floor in resale_prod.

Old formula:  buy * (1 + margin + fee)   -> net margin below the target
              (+2.60% instead of +3.00% at fee 5%).
New formula:  buy * (1 + margin) / (1 - fee)   (same as resale_pipeline.py).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.resale_prod import _min_list_price, _ResaleProdMixin


class TestMinListPrice:
    @pytest.mark.parametrize("fee", [0.02, 0.05, 0.055, 0.07])
    def test_net_proceeds_hit_target_margin_exactly(self, fee):
        buy, margin_pct = 10.0, 3.0
        price = _min_list_price(buy, margin_pct, fee)
        net_after_fee = price * (1.0 - fee)
        assert net_after_fee == pytest.approx(buy * 1.03)

    def test_old_formula_undershoots_target(self):
        """Documents the bug: additive formula gives only ~+2.6% net at fee 5%."""
        buy, margin_pct, fee = 10.0, 3.0, 0.05
        old_price = buy * (1 + margin_pct / 100.0 + fee)
        old_net_margin = old_price * (1 - fee) / buy - 1
        new_net_margin = _min_list_price(buy, margin_pct, fee) * (1 - fee) / buy - 1
        assert old_net_margin == pytest.approx(0.026)
        assert new_net_margin == pytest.approx(0.03)

    def test_known_value_fee_5_5_percent(self):
        assert _min_list_price(10.0, 3.0, 0.055) == pytest.approx(10.8995, abs=1e-4)

    def test_zero_fee(self):
        assert _min_list_price(10.0, 3.0, 0.0) == pytest.approx(10.3)

    @pytest.mark.parametrize("bad_fee", [1.0, 1.5, -0.01, float("nan"), float("inf")])
    def test_invalid_fee_returns_inf_so_item_is_skipped(self, bad_fee):
        assert _min_list_price(10.0, 3.0, bad_fee) == float("inf")


class TestProdListUnlockedUsesNewFloor:
    @pytest.mark.asyncio
    async def test_bid_between_old_and_new_floor_is_skipped(self):
        """buy=10, margin=3%, fee=5.5%: old floor 10.85, new floor ~10.90.
        best_bid=10.86 was listed by the old formula; it must now be skipped."""
        mixin = MagicMock(spec=_ResaleProdMixin)
        mixin.client = AsyncMock()
        mixin._background_tasks = set()
        mixin._current_agg_prices = {"Item": {"best_bid": 10.86, "best_ask": 11.50}}
        mixin.client.create_sell_offers_batch = AsyncMock()

        mock_get_inv = MagicMock(name="get_virtual_inventory")

        async def _mock_run(fn, *args):
            if fn is mock_get_inv:
                return []
            return MagicMock(fetchone=MagicMock(return_value=None))

        with patch("src.core.target_sniping.resale_prod.price_db") as mock_db, \
             patch("src.core.target_sniping.resale_prod.get_total_fee_rate", return_value=0.055), \
             patch("src.core.target_sniping.resale_constants.LIST_MIN_MARGIN_PCT", 3.0):
            mock_db.run_in_thread = AsyncMock(side_effect=_mock_run)
            mock_db.get_virtual_inventory = mock_get_inv
            await _ResaleProdMixin._prod_list_unlocked(mixin, [
                {"id": 1, "hash_name": "Item", "buy_price": 10.0,
                 "dm_item_id": "dm_001", "list_error": None}
            ], "a8db")

        mixin.client.create_sell_offers_batch.assert_not_called()
