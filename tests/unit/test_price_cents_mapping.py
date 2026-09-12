import pytest
from src.api.dmarket_api_client.core import DMarketAPIClient
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_price_cents_mapping_no_conversion():
    """
    Test that priceCents from v2 (which is in cents, e.g. '1599')
    is mapped exactly as is to price["USD"] (which v1 also expected in cents).
    """
    client = DMarketAPIClient("key", "sec")
    v2_resp = {
        "items": [
            {
                "attributes": {"title": "Test", "id": "1"},
                "priceCents": "1599",
                "offerId": "offer_1"
            }
        ]
    }
    client.make_request = AsyncMock(return_value=v2_resp)
    resp = await client.get_user_offers("a8db")
    
    obj = resp["objects"][0]
    # In v1, price["USD"] was in cents, e.g. "1599".
    # Since V2 provides priceCents="1599", the mapping should just put it in price["USD"] without dividing by 100.
    assert obj["price"]["USD"] == "1599"

