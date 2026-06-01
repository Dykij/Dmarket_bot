"""
Comprehensive tests for smart_notifications/utils.py module.

This module tests utility functions for smart notifications:
- get_market_data_for_items - Batch market data retrieval
- get_item_by_id - Single item retrieval
- get_market_items_for_game - Game market items
- get_price_history_for_items - Price history retrieval
- get_item_price - Price extraction from item data

Coverage Target: 85%+
Estimated Tests: 20+ tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.smart_notifications.utils import (
    get_item_by_id,
    get_item_price,
    get_market_data_for_items,
    get_market_items_for_game,
    get_price_history_for_items,
)
from src.utils.exceptions import APIError, NetworkError

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_api():
    """Create a mock DMarketAPI instance."""
    api = MagicMock()
    api._request = AsyncMock()
    return api


@pytest.fixture()
def sample_market_items():
    """Sample market items response."""
    return {
        "items": [
            {
                "itemId": "item_001",
                "title": "AK-47 | Redline",
                "price": {"amount": 2500},  # $25.00
            },
            {
                "itemId": "item_002",
                "title": "AWP | Asiimov",
                "price": {"amount": 8500},  # $85.00
            },
            {
                "itemId": "item_003",
                "title": "M4A4 | Howl",
                "price": {"amount": 150000},  # $1500.00
            },
        ]
    }


@pytest.fixture()
def sample_price_history():
    """Sample price history response."""
    return {
        "data": [
            {"date": "2025-12-01", "price": 25.00, "volume": 100},
            {"date": "2025-12-02", "price": 26.50, "volume": 85},
            {"date": "2025-12-03", "price": 24.75, "volume": 120},
        ]
    }


# ============================================================================
# Tests for get_market_data_for_items
# ============================================================================


class TestGetMarketDataForItems:
    """Tests for get_market_data_for_items function."""

    @pytest.mark.asyncio()
    async def test_returns_indexed_items_by_id(self, mock_api, sample_market_items):
        """Test that items are correctly indexed by itemId."""
        # Arrange
        mock_api._request.return_value = sample_market_items
        item_ids = ["item_001", "item_002"]

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert "item_001" in result
        assert "item_002" in result
        assert result["item_001"]["title"] == "AK-47 | Redline"
        assert result["item_002"]["title"] == "AWP | Asiimov"

    @pytest.mark.asyncio()
    async def test_handles_empty_item_ids_list(self, mock_api):
        """Test handling of empty item IDs list."""
        # Arrange
        item_ids = []

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}
        mock_api._request.assert_not_called()

    @pytest.mark.asyncio()
    async def test_handles_api_error(self, mock_api):
        """Test handling of APIError exception."""
        # Arrange
        mock_api._request.side_effect = APIError("API Error")
        item_ids = ["item_001"]

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}  # Returns empty dict on error

    @pytest.mark.asyncio()
    async def test_handles_network_error(self, mock_api):
        """Test handling of NetworkError exception."""
        # Arrange
        mock_api._request.side_effect = NetworkError("Network Error")
        item_ids = ["item_001"]

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}

    @pytest.mark.asyncio()
    async def test_handles_generic_exception(self, mock_api):
        """Test handling of generic exception."""
        # Arrange
        mock_api._request.side_effect = ValueError("Unexpected error")
        item_ids = ["item_001"]

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}

    @pytest.mark.asyncio()
    async def test_batches_requests_correctly(self, mock_api, sample_market_items):
        """Test that requests are batched correctly for large item lists."""
        # Arrange
        mock_api._request.return_value = sample_market_items
        # Create 75 item IDs (should be split into 2 batches of 50 and 25)
        item_ids = [f"item_{i:03d}" for i in range(75)]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert mock_api._request.call_count == 2  # Two batches

    @pytest.mark.asyncio()
    async def test_uses_correct_api_parameters(self, mock_api, sample_market_items):
        """Test that correct API parameters are passed."""
        # Arrange
        mock_api._request.return_value = sample_market_items
        item_ids = ["item_001", "item_002"]

        # Act
        await get_market_data_for_items(mock_api, item_ids, "dota2")

        # Assert
        mock_api._request.assert_called_once()
        call_args = mock_api._request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/exchange/v1/market/items"
        params = call_args[1]["params"]
        assert params["gameId"] == "dota2"
        assert params["currency"] == "USD"

    @pytest.mark.asyncio()
    async def test_skips_items_without_item_id(self, mock_api):
        """Test that items without itemId are skipped."""
        # Arrange
        mock_api._request.return_value = {
            "items": [
                {"itemId": "item_001", "title": "Valid Item"},
                {"title": "No ID Item"},  # Missing itemId
                {"itemId": None, "title": "Null ID"},  # None itemId
            ]
        }
        item_ids = ["item_001"]

        # Act
        result = await get_market_data_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert len(result) == 1
        assert "item_001" in result


# ============================================================================
# Tests for get_item_by_id
# ============================================================================


class TestGetItemById:
    """Tests for get_item_by_id function."""

    @pytest.mark.asyncio()
    async def test_returns_item_when_found(self, mock_api):
        """Test returning item when found."""
        # Arrange
        mock_api._request.return_value = {
            "items": [{"itemId": "item_001", "title": "Test Item", "price": 1000}]
        }

        # Act
        result = await get_item_by_id(mock_api, "item_001", "csgo")

        # Assert
        assert result is not None
        assert result["itemId"] == "item_001"
        assert result["title"] == "Test Item"

    @pytest.mark.asyncio()
    async def test_returns_none_when_not_found(self, mock_api):
        """Test returning None when item not found."""
        # Arrange
        mock_api._request.return_value = {"items": []}

        # Act
        result = await get_item_by_id(mock_api, "nonexistent", "csgo")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_handles_api_error(self, mock_api):
        """Test handling of APIError."""
        # Arrange
        mock_api._request.side_effect = APIError("API Error")

        # Act
        result = await get_item_by_id(mock_api, "item_001", "csgo")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_handles_network_error(self, mock_api):
        """Test handling of NetworkError."""
        # Arrange
        mock_api._request.side_effect = NetworkError("Network Error")

        # Act
        result = await get_item_by_id(mock_api, "item_001", "csgo")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_handles_generic_exception(self, mock_api):
        """Test handling of generic exception."""
        # Arrange
        mock_api._request.side_effect = RuntimeError("Unexpected")

        # Act
        result = await get_item_by_id(mock_api, "item_001", "csgo")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_uses_correct_api_parameters(self, mock_api):
        """Test that correct API parameters are passed."""
        # Arrange
        mock_api._request.return_value = {"items": []}

        # Act
        await get_item_by_id(mock_api, "item_123", "dota2")

        # Assert
        mock_api._request.assert_called_once()
        call_args = mock_api._request.call_args
        params = call_args[1]["params"]
        assert params["itemId"] == ["item_123"]
        assert params["gameId"] == "dota2"
        assert params["currency"] == "USD"


# ============================================================================
# Tests for get_market_items_for_game
# ============================================================================


class TestGetMarketItemsForGame:
    """Tests for get_market_items_for_game function."""

    @pytest.mark.asyncio()
    async def test_returns_items_list(self, mock_api, sample_market_items):
        """Test returning items list."""
        # Arrange
        mock_api._request.return_value = sample_market_items

        # Act
        result = await get_market_items_for_game(mock_api, "csgo")

        # Assert
        assert len(result) == 3
        assert result[0]["title"] == "AK-47 | Redline"

    @pytest.mark.asyncio()
    async def test_returns_empty_list_on_api_error(self, mock_api):
        """Test returning empty list on APIError."""
        # Arrange
        mock_api._request.side_effect = APIError("API Error")

        # Act
        result = await get_market_items_for_game(mock_api, "csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_returns_empty_list_on_network_error(self, mock_api):
        """Test returning empty list on NetworkError."""
        # Arrange
        mock_api._request.side_effect = NetworkError("Network Error")

        # Act
        result = await get_market_items_for_game(mock_api, "csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_returns_empty_list_on_generic_error(self, mock_api):
        """Test returning empty list on generic error."""
        # Arrange
        mock_api._request.side_effect = Exception("Unexpected")

        # Act
        result = await get_market_items_for_game(mock_api, "csgo")

        # Assert
        assert result == []

    @pytest.mark.asyncio()
    async def test_uses_default_limit(self, mock_api, sample_market_items):
        """Test that default limit is used."""
        # Arrange
        mock_api._request.return_value = sample_market_items

        # Act
        await get_market_items_for_game(mock_api, "csgo")

        # Assert
        call_args = mock_api._request.call_args
        params = call_args[1]["params"]
        assert params["limit"] == 100

    @pytest.mark.asyncio()
    async def test_uses_custom_limit(self, mock_api, sample_market_items):
        """Test using custom limit."""
        # Arrange
        mock_api._request.return_value = sample_market_items

        # Act
        await get_market_items_for_game(mock_api, "csgo", limit=50)

        # Assert
        call_args = mock_api._request.call_args
        params = call_args[1]["params"]
        assert params["limit"] == 50

    @pytest.mark.asyncio()
    async def test_uses_correct_api_parameters(self, mock_api, sample_market_items):
        """Test that correct API parameters are passed."""
        # Arrange
        mock_api._request.return_value = sample_market_items

        # Act
        await get_market_items_for_game(mock_api, "dota2", limit=25)

        # Assert
        call_args = mock_api._request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/exchange/v1/market/items"
        params = call_args[1]["params"]
        assert params["gameId"] == "dota2"
        assert params["limit"] == 25
        assert params["currency"] == "USD"
        assert params["orderBy"] == "popular"


# ============================================================================
# Tests for get_price_history_for_items
# ============================================================================


class TestGetPriceHistoryForItems:
    """Tests for get_price_history_for_items function."""

    @pytest.mark.asyncio()
    async def test_returns_price_history_dict(self, mock_api, sample_price_history):
        """Test returning price history dictionary."""
        # Arrange
        mock_api._request.return_value = sample_price_history
        item_ids = ["item_001"]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert "item_001" in result
        assert len(result["item_001"]) == 3

    @pytest.mark.asyncio()
    async def test_handles_multiple_items(self, mock_api, sample_price_history):
        """Test handling multiple items."""
        # Arrange
        mock_api._request.return_value = sample_price_history
        item_ids = ["item_001", "item_002"]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert "item_001" in result
        assert "item_002" in result
        assert mock_api._request.call_count == 2

    @pytest.mark.asyncio()
    async def test_skips_items_with_empty_history(self, mock_api):
        """Test that items with empty history are skipped."""
        # Arrange
        mock_api._request.return_value = {"data": []}
        item_ids = ["item_001"]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert "item_001" not in result

    @pytest.mark.asyncio()
    async def test_handles_api_error(self, mock_api):
        """Test handling of APIError."""
        # Arrange
        mock_api._request.side_effect = APIError("API Error")
        item_ids = ["item_001"]

        # Act
        result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}

    @pytest.mark.asyncio()
    async def test_handles_network_error(self, mock_api):
        """Test handling of NetworkError."""
        # Arrange
        mock_api._request.side_effect = NetworkError("Network Error")
        item_ids = ["item_001"]

        # Act
        result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}

    @pytest.mark.asyncio()
    async def test_handles_generic_exception(self, mock_api):
        """Test handling of generic exception."""
        # Arrange
        mock_api._request.side_effect = ValueError("Unexpected")
        item_ids = ["item_001"]

        # Act
        result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}

    @pytest.mark.asyncio()
    async def test_uses_correct_api_parameters(self, mock_api, sample_price_history):
        """Test that correct API parameters are passed."""
        # Arrange
        mock_api._request.return_value = sample_price_history
        item_ids = ["item_123"]

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await get_price_history_for_items(mock_api, item_ids, "dota2")

        # Assert
        call_args = mock_api._request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/exchange/v1/market/price-history"
        params = call_args[1]["params"]
        assert params["itemId"] == "item_123"
        assert params["gameId"] == "dota2"
        assert params["currency"] == "USD"
        assert params["period"] == "last_month"

    @pytest.mark.asyncio()
    async def test_handles_empty_item_ids(self, mock_api):
        """Test handling empty item IDs list."""
        # Arrange
        item_ids = []

        # Act
        result = await get_price_history_for_items(mock_api, item_ids, "csgo")

        # Assert
        assert result == {}
        mock_api._request.assert_not_called()


# ============================================================================
# Tests for get_item_price
# ============================================================================


class TestGetItemPrice:
    """Tests for get_item_price function."""

    def test_extracts_price_from_dict_amount(self):
        """Test extracting price from dict with amount."""
        # Arrange
        item_data = {"price": {"amount": 2500}}  # 2500 cents = $25.00

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 25.0

    def test_extracts_price_from_int(self):
        """Test extracting price when it's an integer."""
        # Arrange
        item_data = {"price": 3000}

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 3000.0

    def test_extracts_price_from_float(self):
        """Test extracting price when it's a float."""
        # Arrange
        item_data = {"price": 45.99}

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 45.99

    def test_returns_zero_for_missing_price(self):
        """Test returning 0.0 when price is missing."""
        # Arrange
        item_data = {"title": "Item without price"}

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 0.0

    def test_returns_zero_for_empty_dict(self):
        """Test returning 0.0 for empty dictionary."""
        # Arrange
        item_data = {}

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 0.0

    def test_handles_price_dict_without_amount(self):
        """Test handling price dict without amount key."""
        # Arrange
        item_data = {"price": {"currency": "USD"}}  # No amount key

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == 0.0

    @pytest.mark.parametrize(
        ("price_cents", "expected_usd"),
        (
            (100, 1.0),  # $1.00
            (150, 1.5),  # $1.50
            (9999, 99.99),  # $99.99
            (1, 0.01),  # $0.01
            (0, 0.0),  # $0.00
        ),
    )
    def test_converts_cents_to_usd_correctly(self, price_cents, expected_usd):
        """Test correct conversion from cents to USD."""
        # Arrange
        item_data = {"price": {"amount": price_cents}}

        # Act
        result = get_item_price(item_data)

        # Assert
        assert result == expected_usd


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 40 tests

Test Categories:
1. get_market_data_for_items: 8 tests
   - Basic functionality
   - Empty input handling
   - Error handling (API, Network, Generic)
   - Batching logic
   - Parameter validation

2. get_item_by_id: 6 tests
   - Item found/not found
   - Error handling
   - Parameter validation

3. get_market_items_for_game: 7 tests
   - Basic functionality
   - Error handling
   - Limit parameter testing
   - Parameter validation

4. get_price_history_for_items: 8 tests
   - Basic functionality
   - Multiple items
   - Empty history handling
   - Error handling
   - Parameter validation

5. get_item_price: 8 tests
   - Different price formats
   - Edge cases
   - Parametrized cents-to-USD conversion

Expected Coverage: 85%+
"""
