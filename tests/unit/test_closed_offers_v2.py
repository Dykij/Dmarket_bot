"""user-offers/closed: real client parsing + _check_external_sales consumer.

Live read 2026-11-15 (documented in the project): response keys
{Cursor, Total, Trades}; Trade = {OfferID, TargetID, AssetID, Price{Currency,
Amount: number, dollars}, CurrencyCode, Amount: "1", Title, Fee{Amount{Currency,
Amount}, Percent: "0.08", IsPersonal}, OfferCreatedAt, OfferClosedAt, Status,
FinalizationTime}; times are Unix seconds as STRINGS; `limit=5` (lowercase)
was ignored. Spec statuses: successful | reverted | trade_protected.
The old code read `objects/offerId/status/price.USD` (cents) -> never matched.
IDs below are synthetic.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.dmarket_api_client import DMarketAPIClient
from src.core.target_sniping.resale_prod import _ResaleProdMixin


def _trade(offer_id="off-1", price=1.72, status="successful", fin="0", fee=0.14, pct="0.08"):
    t = {
        "OfferID": offer_id,
        "TargetID": "",
        "AssetID": "asset-" + offer_id,
        "Price": {"Currency": "USD", "Amount": price},
        "CurrencyCode": "USD",
        "Amount": "1",
        "Title": "AK-47 | Redline (Field-Tested)",
        "OfferCreatedAt": "1771779390",
        "OfferClosedAt": "1771779390",
        "Status": status,
        "FinalizationTime": fin,
    }
    if fee is not None:
        t["Fee"] = {"Amount": {"Currency": "USD", "Amount": fee}, "Percent": pct, "IsPersonal": False}
    return t


def _client(*responses) -> DMarketAPIClient:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(side_effect=list(responses))
    return client


# --- client parsing ----------------------------------------------------------

@pytest.mark.asyncio
async def test_request_uses_spec_param_names() -> None:
    client = _client({"Trades": [], "Total": "0", "Cursor": ""})
    await client.get_user_closed_offers("a8db", limit=50, cursor="c1")
    client.make_request.assert_awaited_once_with(
        "GET",
        "/marketplace-api/v1/user-offers/closed",
        params={"Limit": 50, "Cursor": "c1"},
    )


@pytest.mark.asyncio
async def test_no_cursor_param_on_first_page() -> None:
    client = _client({"Trades": [], "Cursor": ""})
    await client.get_user_closed_offers("a8db")
    assert client.make_request.await_args.kwargs["params"] == {"Limit": 50}


@pytest.mark.asyncio
async def test_normalizes_live_shape() -> None:
    client = _client({"Trades": [_trade(price=1.72, fee=0.14, pct="0.08", fin="1771779390")],
                      "Total": "1", "Cursor": "next"})
    out = await client.get_user_closed_offers("a8db")
    o = out["objects"][0]
    assert o["offerId"] == "off-1"
    assert o["assetId"] == "asset-off-1"
    assert o["status"] == "successful"
    assert o["price_usd"] == 1.72          # dollars, NOT cents
    assert o["fee_usd"] == 0.14
    assert o["fee_percent"] == 0.08
    assert o["finalization_time"] == 1771779390.0  # string seconds -> float
    assert out["cursor"] == "next"


@pytest.mark.asyncio
async def test_missing_fee_and_empty_cursor() -> None:
    client = _client({"Trades": [_trade(fee=None, fin="")], "Cursor": ""})
    out = await client.get_user_closed_offers("a8db")
    o = out["objects"][0]
    assert o["fee_usd"] is None and o["fee_percent"] is None
    assert o["finalization_time"] == 0.0
    assert out["cursor"] is None


@pytest.mark.asyncio
async def test_errors_are_not_swallowed() -> None:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await client.get_user_closed_offers("a8db")


# --- consumer: _check_external_sales -----------------------------------------

def _mixin(*pages) -> MagicMock:
    mixin = MagicMock(spec=_ResaleProdMixin)
    mixin.client = AsyncMock()
    mixin.client.get_user_closed_offers = AsyncMock(side_effect=list(pages))
    mixin._background_tasks = set()
    return mixin


def _listed(offer_id="off-1", buy=1.0, sell=2.0, row_id=1) -> dict:
    return {
        "id": row_id, "hash_name": "AK-47 | Redline", "buy_price": buy,
        "dm_item_id": "dm_" + offer_id, "dm_offer_id": offer_id,
        "status": "listed", "sell_price": sell, "acquired_at": time.time() - 86400,
    }


async def _run_check(mixin, listed):
    async def _mock_run(fn, *args):
        return fn(*args) if callable(fn) else None

    with patch("src.core.target_sniping.resale_prod.price_db") as db:
        db.run_in_thread = AsyncMock(side_effect=_mock_run)
        db.get_virtual_inventory.return_value = listed
        n = await _ResaleProdMixin._check_external_sales(mixin, "a8db")
    return n, db


def _obj(offer_id="off-1", status="successful", price=1.72, fee=0.14, fin=0.0, pct=0.08):
    return {"offerId": offer_id, "status": status, "price_usd": price,
            "fee_usd": fee, "fee_percent": pct, "finalization_time": fin}


@pytest.mark.asyncio
async def test_sale_uses_dollar_price_and_actual_fee() -> None:
    mixin = _mixin({"objects": [_obj(price=1.72, fee=0.14)], "cursor": None})
    n, db = await _run_check(mixin, [_listed()])
    assert n == 1
    args = db.record_virtual_sale.call_args[0]
    assert args[1] == 1.72 and args[2] == 0.14


@pytest.mark.asyncio
async def test_missing_fee_falls_back_to_model() -> None:
    mixin = _mixin({"objects": [_obj(price=10.0, fee=None)], "cursor": None})
    n, db = await _run_check(mixin, [_listed()])
    args = db.record_virtual_sale.call_args[0]
    assert n == 1 and args[1] == 10.0 and args[2] > 0  # model fee


@pytest.mark.asyncio
async def test_absurd_fee_falls_back_to_model() -> None:
    mixin = _mixin({"objects": [_obj(price=10.0, fee=25.0)], "cursor": None})
    n, db = await _run_check(mixin, [_listed()])
    assert db.record_virtual_sale.call_args[0][2] != 25.0


@pytest.mark.asyncio
async def test_trade_protected_counts_as_sale_with_funds_hold() -> None:
    fin = time.time() + 7 * 86400
    mixin = _mixin({"objects": [_obj(status="trade_protected", fin=fin)], "cursor": None})
    n, db = await _run_check(mixin, [_listed()])
    assert n == 1
    db.set_funds_hold.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_status_is_not_a_sale() -> None:
    mixin = _mixin({"objects": [_obj(status="closed")], "cursor": None})
    n, db = await _run_check(mixin, [_listed()])
    assert n == 0
    db.record_virtual_sale.assert_not_called()


@pytest.mark.asyncio
async def test_follows_cursor_until_listed_offer_found() -> None:
    mixin = _mixin(
        {"objects": [_obj("other-1"), _obj("other-2")], "cursor": "p2"},
        {"objects": [_obj("off-1")], "cursor": None},
    )
    n, db = await _run_check(mixin, [_listed("off-1")])
    assert n == 1
    assert mixin.client.get_user_closed_offers.await_count == 2
    assert mixin.client.get_user_closed_offers.await_args_list[1].kwargs["cursor"] == "p2"


@pytest.mark.asyncio
async def test_stops_when_server_repeats_cursor() -> None:
    """If the server ignores Cursor, do not loop forever on the same page."""
    page = {"objects": [_obj("other-1")], "cursor": "same"}
    mixin = _mixin(page, page, page, page, page)
    n, _ = await _run_check(mixin, [_listed("off-1")])
    assert n == 0
    assert mixin.client.get_user_closed_offers.await_count <= 2


@pytest.mark.asyncio
async def test_error_on_later_page_keeps_earlier_pages() -> None:
    mixin = _mixin(
        {"objects": [_obj("off-1")], "cursor": "p2"},
        RuntimeError("down"),
    )
    n, _ = await _run_check(mixin, [_listed("off-1"), _listed("off-2", row_id=2)])
    assert n == 1
