"""get_last_sales price units (real client, only make_request is stubbed).

Live read 2026-11-21 (GET /trade-aggregator/v1/last-sales, AK-47 | Redline
(Field-Tested)): `price` is a decimal USD STRING: "33.08", "50.6", "23.13".
The client used to divide it by 100 (cents), understating prices 100x.
Consumers (underpriced.py, cycle_orchestrator -> price_db) work in dollars.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.api.dmarket_api_client import DMarketAPIClient

# Values copied from the live response (dates are epoch seconds as strings).
LIVE_SALES = {
    "sales": [
        {"price": "33.08", "date": "1795258947", "txOperationType": "Offer"},
        {"price": "50.6", "date": "1795258000", "txOperationType": "Offer"},
        {"price": "23.13", "date": "1795257000", "txOperationType": "Offer"},
        {"price": "23.13", "date": "1795256000", "txOperationType": "Offer"},
        {"price": "23.25", "date": "1795255000", "txOperationType": "Offer"},
    ]
}


def _client(resp) -> DMarketAPIClient:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_live_string_prices_are_dollars_not_cents() -> None:
    client = _client(LIVE_SALES)
    out = await client.get_last_sales("a8db", "AK-47 | Redline (Field-Tested)", days=7, limit=5)
    assert [s["price"] for s in out] == [33.08, 50.6, 23.13, 23.13, 23.25]


@pytest.mark.asyncio
async def test_date_is_passed_through_unchanged() -> None:
    client = _client(LIVE_SALES)
    out = await client.get_last_sales("a8db", "x")
    assert out[0]["date"] == "1795258947"


@pytest.mark.asyncio
async def test_numeric_price_is_dollars_too() -> None:
    client = _client({"sales": [{"price": 12.5, "date": "1"}]})
    out = await client.get_last_sales("a8db", "x")
    assert out[0]["price"] == 12.5


@pytest.mark.asyncio
async def test_legacy_dict_shape_still_treated_as_cents() -> None:
    """Old {"price": {"USD": "<cents>"}} shape is unchanged (not seen live)."""
    client = _client({"sales": [{"price": {"USD": "1000"}, "date": "1"}]})
    out = await client.get_last_sales("a8db", "x")
    assert out[0]["price"] == 10.0


@pytest.mark.asyncio
async def test_unparsable_prices_are_skipped() -> None:
    client = _client(
        {"sales": [{"price": "n/a"}, {"price": None}, {"price": "5.00", "date": "1"}]}
    )
    out = await client.get_last_sales("a8db", "x")
    assert [s["price"] for s in out] == [5.0]


@pytest.mark.asyncio
async def test_request_params_unchanged() -> None:
    client = _client(LIVE_SALES)
    await client.get_last_sales("a8db", "T", days=7, limit=5)
    client.make_request.assert_awaited_once_with(
        "GET",
        "/trade-aggregator/v1/last-sales",
        params={"gameId": "a8db", "title": "T", "days": 7, "limit": 5},
    )
