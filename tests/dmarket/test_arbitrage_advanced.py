from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.arbitrage import (
    ArbitrageTrader,
    _arbitrage_cache,
    _save_arbitrage_cache,
    find_arbitrage_opportunities_advanced,
)
from src.dmarket.dmarket_api import DMarketAPI


@pytest.fixture(autouse=True)
def clear_cache():
    _arbitrage_cache.clear()
    yield
    _arbitrage_cache.clear()


@pytest.fixture()
def mock_api_client():
    client = AsyncMock(spec=DMarketAPI)
    client.get_all_market_items = AsyncMock()
    client.get_market_items = AsyncMock()
    client.get_price_info = AsyncMock()
    # Support async context manager (async with self.api:)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture()
def trader(mock_api_client):
    # Patch DMarketAPI at the actual source location where it's imported
    # ArbitrageTrader.__init__ imports DMarketAPI from src.dmarket.dmarket_api
    with patch("src.dmarket.dmarket_api.DMarketAPI", return_value=mock_api_client):
        trader = ArbitrageTrader(public_key="test_pub", secret_key="test_sec")
        # Ensure the trader uses our mock client
        trader.api = mock_api_client
        return trader


@pytest.mark.asyncio()
class TestFindArbitrageOpportunitiesAdvanced:
    async def test_basic_functionality(self, mock_api_client):
        # Arrange
        mock_items = [
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"USD": 1000},  # $10.00
                "extra": {
                    "category": "Rifle",
                    "rarity": "Classified",
                    "popularity": 0.9,
                },
                "itemId": "item1",
                "imageUrl": "http://image.url/1",
            },
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "price": {"USD": 1500},  # $15.00
                "extra": {
                    "category": "Rifle",
                    "rarity": "Classified",
                    "popularity": 0.9,
                },
                "itemId": "item2",
            },
        ]
        mock_api_client.get_all_market_items.return_value = mock_items

        # Act
        results = await find_arbitrage_opportunities_advanced(
            api_client=mock_api_client,
            mode="medium",
            game="csgo",
            min_profit_percent=5.0,
        )

        # Assert
        assert len(results) == 1
        opportunity = results[0]
        assert opportunity["item_name"] == "AK-47 | Redline (Field-Tested)"
        assert opportunity["buy_price"] == 10.0
        assert opportunity["sell_price"] == 15.0
        assert opportunity["buy_item_id"] == "item1"
        assert opportunity["sell_item_id"] == "item2"
        assert opportunity["profit_percent"] > 5.0
        assert "image_url" in opportunity
        assert "buy_link" in opportunity
        assert "sell_link" in opportunity

    async def test_empty_response(self, mock_api_client):
        # Arrange
        mock_api_client.get_all_market_items.return_value = []

        # Act
        results = await find_arbitrage_opportunities_advanced(
            api_client=mock_api_client, mode="medium", game="csgo"
        )

        # Assert
        assert len(results) == 0

    async def test_mode_handling(self, mock_api_client):
        # Arrange
        mock_api_client.get_all_market_items.return_value = []

        # Act & Assert
        # Test "normal" -> "medium"
        await find_arbitrage_opportunities_advanced(mock_api_client, mode="normal")
        # Verify default params were used
        # (medium mode implies certAlgon profit/price ranges)
        # Since we can't easily check internal vars,
        # we rely on no errors and coverage

        # Test "best" -> "high"
        await find_arbitrage_opportunities_advanced(mock_api_client, mode="best")

        # Test "game_dota2" -> game="dota2", mode="normal"
        await find_arbitrage_opportunities_advanced(mock_api_client, mode="game_dota2")
        mock_api_client.get_all_market_items.assert_called_with(
            game="dota2",
            max_items=100,
            price_from=5.0,  # medium default
            price_to=20.0,  # medium default
            sort="price",
        )

    async def test_invalid_inputs_fallback(self, mock_api_client):
        # Arrange
        mock_api_client.get_all_market_items.return_value = []

        # Act
        await find_arbitrage_opportunities_advanced(
            mock_api_client, mode="invalid_mode", game="invalid_game"
        )

        # Assert
        # Should fallback to csgo and medium
        mock_api_client.get_all_market_items.assert_called_with(
            game="csgo",
            max_items=100,
            price_from=5.0,
            price_to=20.0,
            sort="price",
        )

    async def test_caching(self, mock_api_client):
        # Arrange
        cache_key = ("csgo", "medium", 5.0, 20.0, 5.0)
        mock_result = [{"item_name": "Cached Item"}]

        # Clear cache first
        _arbitrage_cache.clear()

        # Save to cache
        _save_arbitrage_cache(cache_key, mock_result)

        # Act
        results = await find_arbitrage_opportunities_advanced(
            api_client=mock_api_client,
            mode="medium",
            game="csgo",
            min_profit_percent=5.0,
        )

        # Assert
        assert results == mock_result
        mock_api_client.get_all_market_items.assert_not_called()

    async def test_insufficient_items_for_arbitrage(self, mock_api_client):
        # Arrange
        mock_items = [{"title": "Single Item", "price": {"USD": 1000}, "extra": {}}]
        mock_api_client.get_all_market_items.return_value = mock_items

        # Act
        results = await find_arbitrage_opportunities_advanced(
            api_client=mock_api_client, mode="medium"
        )

        # Assert
        assert len(results) == 0


@pytest.mark.asyncio()
class TestArbitrageTraderFindProfitableItems:
    async def test_find_profitable_items_success(self, trader, mock_api_client):
        # Arrange - Need at least 2 items with same title and different prices
        # The algorithm finds arbitrage between items with same name
        mock_items = [
            {
                "title": "Item 1",
                "price": {"USD": 1000},  # $10 - buy price
                "extra": {
                    "popularity": 0.8,
                    "category": "Rifle",
                    "rarity": "Classified",
                },
                "itemId": "id1",
            },
            {
                "title": "Item 1",
                "price": {"USD": 1500},  # $15 - sell price
                "extra": {
                    "popularity": 0.8,
                    "category": "Rifle",
                    "rarity": "Classified",
                },
                "itemId": "id2",
            },
        ]
        mock_api_client.get_all_market_items.return_value = mock_items

        # Act
        items = await trader.find_profitable_items(
            game="csgo", min_profit_percentage=10.0
        )

        # Assert
        assert len(items) == 1
        item = items[0]
        assert item["name"] == "Item 1"
        assert item["buy_price"] == 10.0
        assert item["sell_price"] == 15.0
        assert item["profit_percentage"] > 10.0

    async def test_find_profitable_items_no_suggested_price(
        self, trader, mock_api_client
    ):
        # Arrange - Test case with low profit margin
        mock_items = [
            {
                "title": "Item 1",
                "price": {"USD": 1000},  # $10 - buy price
                "extra": {"popularity": 0.5, "category": "Knife", "rarity": "Covert"},
                "itemId": "id1",
            },
            {
                "title": "Item 1",
                "price": {"USD": 1200},  # $12 - sell price
                "extra": {"popularity": 0.5, "category": "Knife", "rarity": "Covert"},
                "itemId": "id2",
            },
        ]
        mock_api_client.get_all_market_items.return_value = mock_items

        # Act
        items = await trader.find_profitable_items(
            game="csgo", min_profit_percentage=5.0
        )

        # Assert
        assert len(items) == 1
        item = items[0]
        # Profit: 12 * (1 - commission%) - 10
        assert item["buy_price"] == 10.0
        assert item["sell_price"] == 12.0
        # With ~7% commission: 12 * 0.93 - 10 = 11.16 - 10 = 1.16 (11.6%)
        assert item["profit_percentage"] > 5.0

    async def test_find_profitable_items_no_items_found(self, trader, mock_api_client):
        # Arrange - get_all_market_items returns a list directly
        mock_api_client.get_all_market_items.return_value = []

        # Act
        items = await trader.find_profitable_items(game="csgo")

        # Assert
        assert len(items) == 0

    async def test_find_profitable_items_api_error(self, trader, mock_api_client):
        # Arrange - get_all_market_items should raise exception
        mock_api_client.get_all_market_items.side_effect = Exception("API Error")

        # Act
        items = await trader.find_profitable_items(game="csgo")

        # Assert
        assert len(items) == 0

    async def test_find_profitable_items_item_processing_error(
        self, trader, mock_api_client
    ):
        # Arrange - Items with invalid price format
        mock_items = [
            {
                "title": "Bad Item",
                # This will cause float conversion error
                "price": "invalid_price",
                "itemId": "id1",
            },
            {
                "title": "Bad Item",
                "price": {"USD": "not_a_number"},
                "itemId": "id2",
            },
        ]
        mock_api_client.get_all_market_items.return_value = mock_items

        # Act
        items = await trader.find_profitable_items(game="csgo")

        # Assert - should return empty list without crashing
        assert len(items) == 0
