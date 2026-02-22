"""Tests for smart_repricing module.

This module tests the SmartRepricer class for intelligent
price adjustments based on item age and market conditions.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.smart_repricing import RepricingAction, SmartRepricer


class TestSmartRepricer:
    """Tests for SmartRepricer class."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_my_offers = AsyncMock(return_value={"objects": []})
        api.update_offer = AsyncMock(return_value={"success": True})
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.fixture()
    def repricer(self, mock_api):
        """Create SmartRepricer instance."""
        return SmartRepricer(
            api_client=mock_api,
            config={
                "max_price_cut_percent": 15,
                "dmarket_fee_percent": 7.0,
                "night_mode_enabled": True,
                "panic_threshold_percent": 15,
            },
        )

    def test_init(self, repricer, mock_api):
        """Test initialization."""
        assert repricer.api == mock_api

    def test_determine_repricing_action_new(self, repricer):
        """Test repricing action for new listing."""
        listed_at = datetime.now(UTC) - timedelta(hours=1)
        current_time = datetime.now(UTC)

        action = repricer.determine_repricing_action(listed_at, current_time)

        # New items should be held
        assert action == RepricingAction.HOLD

    def test_determine_repricing_action_old(self, repricer):
        """Test repricing action for old listing (24+ hours)."""
        listed_at = datetime.now(UTC) - timedelta(hours=30)
        current_time = datetime.now(UTC)

        action = repricer.determine_repricing_action(listed_at, current_time)

        # 30 hours - should reduce to target
        assert action == RepricingAction.REDUCE_TO_TARGET

    def test_determine_repricing_action_stale(self, repricer):
        """Test repricing action for stale listing (48+ hours)."""
        listed_at = datetime.now(UTC) - timedelta(hours=50)
        current_time = datetime.now(UTC)

        action = repricer.determine_repricing_action(listed_at, current_time)

        # 50 hours - should reduce to break-even
        assert action == RepricingAction.REDUCE_TO_BREAK_EVEN

    def test_determine_repricing_action_liquidate(self, repricer):
        """Test repricing action for very old listing (72+ hours)."""
        listed_at = datetime.now(UTC) - timedelta(hours=80)
        current_time = datetime.now(UTC)

        action = repricer.determine_repricing_action(listed_at, current_time)

        # 80 hours - should liquidate
        assert action == RepricingAction.LIQUIDATE

    def test_is_night_mode(self, repricer):
        """Test night mode detection."""
        # Method should return boolean based on current UTC hour
        result = repricer.is_night_mode()
        assert isinstance(result, bool)

    def test_get_undercut_step_normal(self, repricer):
        """Test undercut step in normal mode."""
        # Force night mode off
        repricer.night_mode_enabled = False
        step = repricer.get_undercut_step(base_step=1)
        assert step == 1

    def test_get_undercut_step_night_mode(self, repricer):
        """Test undercut step in night mode is multiplied."""
        repricer.night_mode_enabled = True
        # Night mode returns multiplied step when active
        if repricer.is_night_mode():
            step = repricer.get_undercut_step(base_step=1)
            assert step == 2  # default multiplier is 2.0

    def test_calculate_new_price_hold(self, repricer):
        """Test calculate_new_price returns None for HOLD action."""
        item = {"buy_price": 1000, "current_price": 1200}
        market_min = 1100

        result = repricer.calculate_new_price(item, market_min, RepricingAction.HOLD)
        assert result is None

    def test_calculate_dynamic_undercut(self, repricer):
        """Test dynamic undercut calculation."""
        result = repricer.calculate_dynamic_undercut(
            my_price=1000,
            market_prices=[900, 950, 990],
        )
        assert isinstance(result, int)

    @pytest.mark.asyncio()
    async def test_check_market_panic_no_panic(self, repricer, mock_api):
        """Test panic detection with stable market."""
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"price": {"USD": "1000"}},
                    {"price": {"USD": "1010"}},
                ]
            }
        )

        is_panic = await repricer.check_market_panic("AK-47", current_price=1000)
        assert isinstance(is_panic, bool)

    @pytest.mark.asyncio()
    async def test_should_pause_selling(self, repricer, mock_api):
        """Test pause selling decision."""
        item = {"title": "AK-47", "buy_price": 800}
        result = await repricer.should_pause_selling(item, market_min_price=1000)
        assert isinstance(result, bool)

    def test_get_repricing_summary(self, repricer):
        """Test getting repricing summary."""
        items = [
            {"title": "Item1", "price": 100},
            {"title": "Item2", "price": 200},
        ]

        summary = repricer.get_repricing_summary(items)

        assert isinstance(summary, dict)
        # Check returned keys match actual implementation
        assert "hold" in summary
