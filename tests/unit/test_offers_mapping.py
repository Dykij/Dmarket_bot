"""Tests for DMarket API offers endpoint migration."""

import pytest
from unittest.mock import AsyncMock
from src.api.dmarket_api_client.core import DMarketAPIClient

@pytest.mark.asyncio
async def test_get_user_offers_v2_mapping():
    client = DMarketAPIClient("key", "sec")
    
    # Real V2 response structure based on Swagger
    v2_resp = {
        "items": [
            {
                "attributes": {
                    "id": "3d9c9c6a-4f2e-4b83-a1c7-90ab12cd34ef",
                    "title": "AK-47 | Redline (Field-Tested)"
                },
                "priceCents": "1599",
                "offerId": "c3d4e5f6-1234-4abc-9def-7890abcdef12"
            }
        ],
        "cursor": "next_page_token",
        "total": "1"
    }
    
    client.make_request = AsyncMock(return_value=v2_resp)
    
    resp = await client.get_user_offers("a8db")
    
    assert "objects" in resp
    obj = resp["objects"][0]
    
    # Check fields expected by callers
    assert obj["offerId"] == "c3d4e5f6-1234-4abc-9def-7890abcdef12"
    assert obj["itemId"] == "3d9c9c6a-4f2e-4b83-a1c7-90ab12cd34ef"
    assert obj["title"] == "AK-47 | Redline (Field-Tested)"
    assert obj["price"]["USD"] == "1599"

@pytest.mark.asyncio
async def test_get_user_offers_pagination():
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(return_value={"items": []})
    
    await client.get_user_offers("a8db", limit=50, cursor="abc")
    
    client.make_request.assert_called_once_with(
        "GET", "/marketplace-api/v2/user/offers", params={"gameId": "a8db", "limit": 50, "cursor": "abc"}
    )
