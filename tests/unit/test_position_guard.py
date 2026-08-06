"""Tests for position_guard.py — stop-loss/take-profit with DMarket prices."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.target_sniping.position_guard import _PositionGuardMixin, STOP_LOSS_PCT, TAKE_PROFIT_PCT


class FakePositionGuard(_PositionGuardMixin):
    """Concrete stub for testing the mixin."""

    def __init__(self):
        self.client = AsyncMock()
        self._current_agg_prices: dict = {}
        self._background_tasks: set = set()


def _make_item(hash_name="AK-47 | Redline", buy_price=10.0, status="idle", age_hours=48.0):
    """Create a virtual_inventory-like row."""
    import time
    return {
        "id": 1,
        "hash_name": hash_name,
        "buy_price": buy_price,
        "status": status,
        "acquired_at": time.time() - age_hours * 3600,
        "dm_item_id": "test-dm-id-001",
    }


class TestGetCurrentPrice:

    @pytest.mark.asyncio
    async def test_returns_best_bid_when_use_bid_true(self):
        guard = FakePositionGuard()
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": 8.50, "best_ask": 9.00}
        }
        price = await guard._get_current_price("AK-47 | Redline", use_bid=True)
        assert price == 8.50

    @pytest.mark.asyncio
    async def test_returns_best_ask_when_use_bid_false(self):
        guard = FakePositionGuard()
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": 8.50, "best_ask": 9.00}
        }
        price = await guard._get_current_price("AK-47 | Redline", use_bid=False)
        assert price == 9.00

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_data(self):
        guard = FakePositionGuard()
        guard._current_agg_prices = {}
        price = await guard._get_current_price("AK-47 | Redline", use_bid=True)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_returns_zero_when_price_is_none(self):
        guard = FakePositionGuard()
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": None, "best_ask": None}
        }
        price = await guard._get_current_price("AK-47 | Redline", use_bid=True)
        assert price == 0.0


class TestCheckStopLosses:

    @pytest.mark.asyncio
    async def test_triggers_liquidation_when_price_drops(self):
        """When best_bid drops below stop-loss threshold, items should be liquidated."""
        guard = FakePositionGuard()
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": 7.00, "best_ask": 7.50}
        }

        item = _make_item(buy_price=10.0, age_hours=48.0)

        with patch("src.core.target_sniping.position_guard.price_db") as mock_db, \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_ENABLED", True), \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_MIN_AGE_HOURS", 1.0):
            mock_db.get_virtual_inventory.return_value = [item]
            guard._execute_liquidation = AsyncMock(return_value=1)

            result = await guard.check_stop_losses("a8db")

            # stop-loss: (10-7)/10 = 30% loss + fees
            assert result == 1
            guard._execute_liquidation.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_liquidation_when_price_stable(self):
        """When best_bid is close to buy_price, no liquidation should occur."""
        guard = FakePositionGuard()
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": 9.80, "best_ask": 10.00}
        }

        item = _make_item(buy_price=10.0, age_hours=48.0)

        with patch("src.core.target_sniping.position_guard.price_db") as mock_db, \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_ENABLED", True), \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_MIN_AGE_HOURS", 1.0):
            mock_db.get_virtual_inventory.return_value = [item]

            result = await guard.check_stop_losses("a8db")
            assert result == 0

    @pytest.mark.asyncio
    async def test_skips_when_price_zero(self):
        """Items with no price data should be skipped, not sold at $0."""
        guard = FakePositionGuard()
        guard._current_agg_prices = {}

        item = _make_item(buy_price=10.0, age_hours=48.0)

        with patch("src.core.target_sniping.position_guard.price_db") as mock_db, \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_ENABLED", True), \
             patch("src.core.target_sniping.position_guard.STOP_LOSS_MIN_AGE_HOURS", 1.0):
            mock_db.get_virtual_inventory.return_value = [item]

            result = await guard.check_stop_losses("a8db")
            assert result == 0


class TestCheckTakeProfits:

    @pytest.mark.asyncio
    async def test_triggers_take_profit_when_price_rises(self):
        """When best_bid rises above take-profit threshold, items should be sold."""
        guard = FakePositionGuard()
        # Need best_bid high enough to cover TAKE_PROFIT_PCT (15%) + fees (5.5%)
        # buy=10, sell=13: profit=30%, realized=30%-5.5%=24.5% > 15%
        guard._current_agg_prices = {
            "AK-47 | Redline": {"best_bid": 13.00, "best_ask": 13.50}
        }

        item = _make_item(buy_price=10.0, age_hours=48.0)

        with patch("src.core.target_sniping.position_guard.price_db") as mock_db, \
             patch("src.core.target_sniping.position_guard.TAKE_PROFIT_ENABLED", True):
            mock_db.get_virtual_inventory.return_value = [item]
            guard._execute_liquidation = AsyncMock(return_value=1)

            result = await guard.check_take_profits("a8db")

            # profit: (13-10)/10 = 30% - fees (5.5%) = 24.5% > 15% threshold
            assert result == 1
            guard._execute_liquidation.assert_called_once()
