"""Tests for smart_bidder module.

This module tests the SmartBidder class for intelligent
bidding on items.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSmartBidder:
    """Tests for SmartBidder class."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_balance = AsyncMock(return_value={"balance": 100.0})
        api.get_market_items = AsyncMock(return_value={"objects": []})
        api._request = AsyncMock(return_value={"success": True})
        return api

    @pytest.fixture()
    def bidder(self, mock_api):
        """Create SmartBidder instance."""
        from src.dmarket.smart_bidder import SmartBidder

        return SmartBidder(api_client=mock_api)

    def test_init(self, bidder, mock_api):
        """Test initialization."""
        assert bidder.api == mock_api
        assert bidder.min_profit_margin == 0.15

    def test_init_custom_margin(self, mock_api):
        """Test initialization with custom margin."""
        from src.dmarket.smart_bidder import SmartBidder

        bidder = SmartBidder(api_client=mock_api, min_profit_margin=0.20)
        assert bidder.min_profit_margin == 0.20

    @pytest.mark.asyncio()
    async def test_place_competitive_bid(self, bidder, mock_api):
        """Test placing a competitive bid."""
        mock_api.get_market_items = AsyncMock(
            return_value={"objects": [{"title": "AK-47 | Redline", "price": {"USD": "2500"}}]}
        )

        result = await bidder.place_competitive_bid(
            item_title="AK-47 | Redline",
            max_price_usd=25.0,
            expected_sell_price_usd=30.0,
        )

        # BidResult is a dataclass
        assert result is not None

    @pytest.mark.asyncio()
    async def test_adjust_existing_bids(self, bidder, mock_api):
        """Test adjusting existing bids."""
        mock_api.get_market_items = AsyncMock(
            return_value={"objects": [{"title": "AK-47 | Redline", "price": {"USD": "2500"}}]}
        )

        result = await bidder.adjust_existing_bids("AK-47 | Redline")
        assert isinstance(result, dict)

    def test_get_bid_stats(self, bidder):
        """Test getting bidding statistics."""
        stats = bidder.get_bid_stats()

        assert isinstance(stats, dict)
        assert "total_bids" in stats
        assert "successful_bids" in stats
