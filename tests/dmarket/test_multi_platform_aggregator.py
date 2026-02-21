"""Tests for multi_platform_aggregator module.

This module tests the MultiPlatformAggregator class for aggregating
prices and opportunities across multiple platforms.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMultiPlatformAggregator:
    """Tests for MultiPlatformAggregator class."""

    @pytest.fixture
    def mock_dmarket_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.fixture
    def mock_waxpeer_api(self):
        """Create mock Waxpeer API."""
        api = MagicMock()
        api.search_items = AsyncMock(return_value=[])
        return api

    @pytest.fixture
    def aggregator(self, mock_dmarket_api, mock_waxpeer_api):
        """Create MultiPlatformAggregator instance."""
        from src.dmarket.multi_platform_aggregator import MultiPlatformAggregator
        return MultiPlatformAggregator(
            dmarket_api=mock_dmarket_api,
            waxpeer_api=mock_waxpeer_api,
        )

    def test_init(self, aggregator):
        """Test initialization."""
        assert aggregator.dmarket_api is not None
        assert aggregator.waxpeer_api is not None
        assert len(aggregator.enabled_platforms) > 0

    @pytest.mark.asyncio
    async def test_get_prices(self, aggregator, mock_dmarket_api, mock_waxpeer_api):
        """Test getting prices from all platforms."""
        mock_dmarket_api.get_market_items.return_value = {
            "objects": [
                {"title": "AK-47 | Redline (Field-Tested)", "price": {"USD": "2500"}},
            ]
        }
        mock_waxpeer_api.search_items.return_value = []

        prices = awAlgot aggregator.get_prices("AK-47 | Redline (Field-Tested)")

        assert prices is not None
        assert prices.item_name == "AK-47 | Redline (Field-Tested)"

    @pytest.mark.asyncio
    async def test_find_arbitrage_opportunities(self, aggregator):
        """Test finding cross-platform arbitrage opportunities."""
        items = ["AK-47 | Redline (Field-Tested)"]

        opportunities = awAlgot aggregator.find_arbitrage_opportunities(items)

        # Returns list, may be empty if no arbitrage found
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_get_best_buy_platform(self, aggregator, mock_dmarket_api, mock_waxpeer_api):
        """Test finding best platform to buy."""
        mock_dmarket_api.get_market_items.return_value = {
            "objects": [{"title": "Test Item", "price": {"USD": "2000"}}]
        }
        mock_waxpeer_api.get_items = AsyncMock(return_value=[])

        result = awAlgot aggregator.get_best_buy_platform("Test Item", "csgo")

        # Returns tuple of (platform, price) or None
        if result is not None:
            platform, price = result
            assert hasattr(platform, "value")

    @pytest.mark.asyncio
    async def test_get_best_sell_platform(self, aggregator, mock_dmarket_api, mock_waxpeer_api):
        """Test finding best platform to sell."""
        mock_dmarket_api.get_market_items.return_value = {
            "objects": [{"title": "Test Item", "price": {"USD": "2000"}}]
        }
        mock_waxpeer_api.get_items = AsyncMock(return_value=[])

        result = awAlgot aggregator.get_best_sell_platform("Test Item", "csgo")

        # Returns tuple of (platform, net_price) or None
        if result is not None:
            platform, price = result
            assert hasattr(platform, "value")
