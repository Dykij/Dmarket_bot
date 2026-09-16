import pytest
from unittest.mock import AsyncMock
from src.analytics.historical_data.sources import collect_from_aggregated
from pydantic import ValidationError

@pytest.mark.asyncio
async def test_collect_from_aggregated_success():
    api = AsyncMock()
    api.get_aggregated_prices_bulk.return_value = {
        "aggregatedPrices": [
            {
                "title": "AK-47",
                "offerBestPrice": {"Currency": "USD", "Amount": "1500"},
                "orderBestPrice": {"Currency": "USD", "Amount": "1400"}
            }
        ]
    }
    
    points = await collect_from_aggregated(api, "a8db", "AK-47")
    assert len(points) == 1
    assert points[0].best_ask == 15.0
    assert points[0].best_bid == 14.0

@pytest.mark.asyncio
async def test_collect_from_aggregated_invalid_format():
    api = AsyncMock()
    api.get_aggregated_prices_bulk.return_value = {
        "aggregatedPrices": [
            {
                "title": "AK-47",
                "offerBestPrice": "invalid_string_instead_of_dict"
            }
        ]
    }
    
    # We expect the ValidationError to be caught and logged, returning empty list
    points = await collect_from_aggregated(api, "a8db", "AK-47")
    assert len(points) == 0


@pytest.mark.asyncio
async def test_collect_from_aggregated_non_numeric_amount():
    api = AsyncMock()
    api.get_aggregated_prices_bulk.return_value = {
        "aggregatedPrices": [
            {"title": "AK-47", "offerBestPrice": {"Currency": "USD", "Amount": "N/A"}}
        ]
    }
    points = await collect_from_aggregated(api, "a8db", "AK-47")
    assert len(points) == 0  # не падает, просто не даёт точку
