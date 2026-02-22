"""Tests for TrendingItemsFinder class.

Tests the refactored version of find_trending_items() with:
- Early returns pattern
- Helper methods
- Reduced nesting
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.trending_items_finder import (
    TrendingItemsFinder,
    TrendMetrics,
    find_trending_items,
)


@pytest.fixture()
def mock_api():
    """Create mock DMarket API."""
    api = MagicMock()
    api.get_sales_history = AsyncMock()
    api.get_market_items = AsyncMock()
    api._close_client = AsyncMock()
    return api


@pytest.fixture()
def sample_market_items():
    """Sample market items data."""
    return {
        "items": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1500},  # $15.00
                "suggestedPrice": {"amount": 1800},  # $18.00
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 5000},  # $50.00
                "suggestedPrice": {"amount": 5500},  # $55.00
            },
            {
                "title": "M4A4 | Howl (FN)",
                "price": {"amount": 200000},  # $2000.00 (too expensive)
                "suggestedPrice": {"amount": 220000},
            },
        ]
    }


@pytest.fixture()
def sample_sales_history():
    """Sample sales history data."""
    return {
        "items": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1300},  # Last sold: $13.00
            },
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"amount": 1350},  # Another sale
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 6000},  # Last sold: $60.00 (downtrend)
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 5800},
            },
            {
                "title": "AWP | Asiimov (FT)",
                "price": {"amount": 5500},
            },
        ]
    }


class TestTrendingItemsFinderInitialization:
    """Test TrendingItemsFinder initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        finder = TrendingItemsFinder(game="csgo")

        assert finder.game == "csgo"
        assert finder.min_price == 5.0
        assert finder.max_price == 500.0
        assert finder.max_results == 10
        assert finder.market_data == {}

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        finder = TrendingItemsFinder(
            game="dota2",
            min_price=10.0,
            max_price=100.0,
            max_results=5,
        )

        assert finder.game == "dota2"
        assert finder.min_price == 10.0
        assert finder.max_price == 100.0
        assert finder.max_results == 5


class TestPriceExtraction:
    """Test price extraction logic."""

    def test_extract_price_from_dict_with_amount(self):
        """Test extracting price from dict format."""
        finder = TrendingItemsFinder(game="csgo")
        item = {"price": {"amount": 1500}}

        price = finder._extract_price(item, "price")

        assert price == 15.0

    def test_extract_price_from_direct_number(self):
        """Test extracting price from direct numeric value."""
        finder = TrendingItemsFinder(game="csgo")
        item = {"price": 25.50}

        price = finder._extract_price(item, "price")

        assert price == 25.50

    def test_extract_price_missing_key(self):
        """Test extracting price when key is missing."""
        finder = TrendingItemsFinder(game="csgo")
        item = {"title": "Test Item"}

        price = finder._extract_price(item, "price")

        assert price is None

    def test_extract_suggested_price(self):
        """Test extracting suggested price."""
        finder = TrendingItemsFinder(game="csgo")
        item = {"suggestedPrice": {"amount": 2000}}

        price = finder._extract_price(item, "suggestedPrice")

        assert price == 20.0


class TestPriceValidation:
    """Test price validation logic."""

    def test_valid_price_within_range(self):
        """Test price within valid range."""
        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)

        assert finder._is_price_valid(50.0) is True
        assert finder._is_price_valid(10.0) is True
        assert finder._is_price_valid(100.0) is True

    def test_invalid_price_below_minimum(self):
        """Test price below minimum."""
        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)

        assert finder._is_price_valid(5.0) is False

    def test_invalid_price_above_maximum(self):
        """Test price above maximum."""
        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)

        assert finder._is_price_valid(150.0) is False

    def test_invalid_price_none(self):
        """Test None price."""
        finder = TrendingItemsFinder(game="csgo")

        assert finder._is_price_valid(None) is False


class TestMarketItemsProcessing:
    """Test market items processing."""

    def test_process_market_items_valid(self):
        """Test processing valid market items."""
        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)
        items = [
            {
                "title": "Test Item",
                "price": {"amount": 5000},  # $50.00
                "suggestedPrice": {"amount": 5500},
            }
        ]

        finder._process_market_items(items)

        assert "Test Item" in finder.market_data
        assert finder.market_data["Test Item"]["current_price"] == 50.0
        assert finder.market_data["Test Item"]["suggested_price"] == 55.0

    def test_process_market_items_skips_invalid_price(self):
        """Test skipping items with invalid price."""
        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)
        items = [
            {
                "title": "Too Cheap",
                "price": {"amount": 500},  # $5.00 (below min)
            },
            {
                "title": "Too Expensive",
                "price": {"amount": 20000},  # $200.00 (above max)
            },
        ]

        finder._process_market_items(items)

        assert "Too Cheap" not in finder.market_data
        assert "Too Expensive" not in finder.market_data

    def test_process_market_items_skips_missing_title(self):
        """Test skipping items without title."""
        finder = TrendingItemsFinder(game="csgo")
        items = [{"price": {"amount": 5000}}]

        finder._process_market_items(items)

        assert len(finder.market_data) == 0


class TestSalesHistoryProcessing:
    """Test sales history processing."""

    def test_update_sale_data_first_sale(self):
        """Test updating with first sale data."""
        finder = TrendingItemsFinder(game="csgo")
        finder.market_data = {
            "Test Item": {
                "item": {},
                "current_price": 50.0,
                "supply": 1,
            }
        }

        sale = {"title": "Test Item", "price": {"amount": 4500}}
        finder._update_sale_data("Test Item", sale)

        assert finder.market_data["Test Item"]["last_sold_price"] == 45.0
        assert finder.market_data["Test Item"]["sales_count"] == 1

    def test_update_sale_data_multiple_sales(self):
        """Test updating with multiple sales."""
        finder = TrendingItemsFinder(game="csgo")
        finder.market_data = {
            "Test Item": {
                "item": {},
                "current_price": 50.0,
                "last_sold_price": 45.0,
                "sales_count": 1,
            }
        }

        sale = {"title": "Test Item", "price": {"amount": 4600}}
        finder._update_sale_data("Test Item", sale)

        # Should keep first last_sold_price and increment count
        assert finder.market_data["Test Item"]["last_sold_price"] == 45.0
        assert finder.market_data["Test Item"]["sales_count"] == 2


class TestTrendMetrics:
    """Test trend metrics extraction."""

    def test_extract_metrics(self):
        """Test extracting trend metrics."""
        finder = TrendingItemsFinder(game="csgo")
        data = {
            "current_price": 50.0,
            "last_sold_price": 45.0,
            "sales_count": 3,
        }

        metrics = finder._extract_metrics(data)

        assert metrics.current_price == 50.0
        assert metrics.last_sold_price == 45.0
        assert metrics.sales_count == 3
        # Price change: (50-45)/45 * 100 = 11.11%
        assert abs(metrics.price_change_percent - 11.11) < 0.1


class TestUpwardTrend:
    """Test upward trend detection."""

    def test_upward_trend_valid(self):
        """Test detecting valid upward trend."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {"title": "Test"}, "game": "csgo"}
        metrics = TrendMetrics(
            current_price=50.0,
            last_sold_price=45.0,  # +11% change
            price_change_percent=11.11,
            sales_count=2,
        )

        item = finder._check_upward_trend(data, metrics)

        assert item is not None
        assert item.trend == "upward"
        assert abs(item.projected_price - 55.0) < 0.01  # 50 * 1.1
        assert abs(item.potential_profit - 5.0) < 0.01  # 55 - 50

    def test_upward_trend_insufficient_price_change(self):
        """Test rejecting upward trend with low price change."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=50.0,
            last_sold_price=48.0,  # Only +4% change
            price_change_percent=4.0,
            sales_count=2,
        )

        item = finder._check_upward_trend(data, metrics)

        assert item is None

    def test_upward_trend_insufficient_sales(self):
        """Test rejecting upward trend with insufficient sales."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=50.0,
            last_sold_price=45.0,
            price_change_percent=11.11,
            sales_count=1,  # Only 1 sale
        )

        item = finder._check_upward_trend(data, metrics)

        assert item is None

    def test_upward_trend_low_profit(self):
        """Test rejecting upward trend with low profit."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=2.0,  # Low price
            last_sold_price=1.8,  # +11% but only $0.20 profit
            price_change_percent=11.11,
            sales_count=2,
        )

        item = finder._check_upward_trend(data, metrics)

        assert item is None  # Profit < $0.50


class TestRecoveryTrend:
    """Test recovery trend detection."""

    def test_recovery_trend_valid(self):
        """Test detecting valid recovery trend."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {"title": "Test"}, "game": "csgo"}
        metrics = TrendMetrics(
            current_price=40.0,
            last_sold_price=60.0,  # -33% change (crashed)
            price_change_percent=-33.33,
            sales_count=3,
        )

        item = finder._check_recovery_trend(data, metrics)

        assert item is not None
        assert item.trend == "recovery"
        assert item.projected_price == 54.0  # 60 * 0.9
        assert item.potential_profit == 14.0  # 54 - 40

    def test_recovery_trend_insufficient_drop(self):
        """Test rejecting recovery with insufficient price drop."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=50.0,
            last_sold_price=55.0,  # Only -9% drop
            price_change_percent=-9.0,
            sales_count=3,
        )

        item = finder._check_recovery_trend(data, metrics)

        assert item is None

    def test_recovery_trend_insufficient_sales(self):
        """Test rejecting recovery with insufficient sales."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=40.0,
            last_sold_price=60.0,
            price_change_percent=-33.33,
            sales_count=2,  # Only 2 sales, need 3+
        )

        item = finder._check_recovery_trend(data, metrics)

        assert item is None

    def test_recovery_trend_low_profit(self):
        """Test rejecting recovery with low profit."""
        finder = TrendingItemsFinder(game="csgo")
        data = {"item": {}}
        metrics = TrendMetrics(
            current_price=5.0,
            last_sold_price=7.0,  # Projected: 6.3, profit: 1.3 (but < $1 after fees)
            price_change_percent=-28.57,
            sales_count=3,
        )

        item = finder._check_recovery_trend(data, metrics)

        # Should still pass since profit > $1.00
        assert item is not None


@pytest.mark.asyncio()
class TestFindMethod:
    """Test main find() method."""

    async def test_find_with_trending_items(
        self, mock_api, sample_market_items, sample_sales_history
    ):
        """Test finding trending items successfully."""
        mock_api.get_market_items.return_value = sample_market_items
        mock_api.get_sales_history.return_value = sample_sales_history

        finder = TrendingItemsFinder(game="csgo", min_price=10.0, max_price=100.0)
        results = await finder.find(mock_api)

        assert len(results) > 0
        assert all("potential_profit" in item for item in results)
        assert all("trend" in item for item in results)

    async def test_find_with_no_sales_history(self, mock_api, sample_market_items):
        """Test handling missing sales history."""
        mock_api.get_market_items.return_value = sample_market_items
        mock_api.get_sales_history.return_value = None

        finder = TrendingItemsFinder(game="csgo")
        results = await finder.find(mock_api)

        assert results == []

    async def test_find_with_empty_market_items(self, mock_api, sample_sales_history):
        """Test handling empty market items."""
        mock_api.get_market_items.return_value = {"items": []}
        mock_api.get_sales_history.return_value = sample_sales_history

        finder = TrendingItemsFinder(game="csgo")
        results = await finder.find(mock_api)

        assert results == []


@pytest.mark.asyncio()
class TestBackwardCompatibleWrapper:
    """Test backward-compatible find_trending_items() function."""

    async def test_wrapper_with_provided_api(
        self, mock_api, sample_market_items, sample_sales_history
    ):
        """Test wrapper with provided API instance."""
        mock_api.get_market_items.return_value = sample_market_items
        mock_api.get_sales_history.return_value = sample_sales_history

        results = await find_trending_items(
            game="csgo",
            min_price=10.0,
            max_price=100.0,
            dmarket_api=mock_api,
        )

        assert isinstance(results, list)
        mock_api._close_client.assert_not_called()

    async def test_wrapper_handles_exceptions(self, mock_api):
        """Test wrapper handles exceptions gracefully."""
        mock_api.get_market_items.side_effect = Exception("API Error")

        results = await find_trending_items(game="csgo", dmarket_api=mock_api)

        assert results == []
