"""get_user_inventory on the v2 endpoint (real client, only make_request stubbed).

Context: GET /exchange/v1/user-inventory is not in spec v2.0.0 and answered
404 on the live read of 2026-11-15. The working endpoint is
GET /marketplace-api/v2/user/inventory (gameId + limit required, limit 1..100,
cursor; response {items[], total, cursor}). Consumers still expect the legacy
shape {"objects": [{"itemId", "assetId", "title"}], "cursor"}.

The sample below mirrors the live item of 2026-11-15: `attributes.id` is a
composite instanceId:classId:assetId:appId (item NOT on DMarket), `inMarket`
absent. IDs are synthetic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.dmarket_api_client import DMarketAPIClient
from src.core.target_sniping.resale_prod import _ResaleProdMixin

COMPOSITE = "1111111111:2222222222:33333333333:730"
UUID = "3d9c9c6a-4f2e-4b83-a1c7-90ab12cd34ef"


def _v2_item(asset_id: str, title: str, in_market=None) -> dict:
    item = {
        "attributes": {
            "id": asset_id,
            "title": title,
            "inGameAssetId": COMPOSITE,
            "steamAssetId": "33333333333",
            "tradable": True,
        },
        "suggestedPrice": {"Currency": "USD", "Amount": "0.03"},
    }
    if in_market is not None:
        item["inMarket"] = in_market
    return item


def _client(*responses) -> DMarketAPIClient:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(side_effect=list(responses))
    return client


@pytest.mark.asyncio
async def test_uses_v2_path_and_params() -> None:
    client = _client({"items": [], "total": "0", "cursor": ""})
    await client.get_user_inventory("a8db", limit=50, cursor="c1")
    client.make_request.assert_awaited_once_with(
        "GET",
        "/marketplace-api/v2/user/inventory",
        params={"gameId": "a8db", "limit": 50, "cursor": "c1"},
    )


@pytest.mark.asyncio
async def test_no_cursor_param_when_none() -> None:
    client = _client({"items": [], "total": "0", "cursor": ""})
    await client.get_user_inventory("a8db")
    params = client.make_request.await_args.kwargs["params"]
    assert "cursor" not in params and "basic" not in params


@pytest.mark.asyncio
async def test_normalizes_to_legacy_objects_shape() -> None:
    client = _client(
        {
            "items": [
                _v2_item(COMPOSITE, "PP-Bizon | Facility Sketch (Field-Tested)"),
                _v2_item(UUID, "AK-47 | Redline (Field-Tested)", in_market=True),
            ],
            "total": "2",
            "cursor": "",
        }
    )
    out = await client.get_user_inventory("a8db")
    assert [o["itemId"] for o in out["objects"]] == [COMPOSITE, UUID]
    assert [o["assetId"] for o in out["objects"]] == [COMPOSITE, UUID]
    assert out["objects"][0]["title"] == "PP-Bizon | Facility Sketch (Field-Tested)"
    assert out["objects"][0]["inGameAssetId"] == COMPOSITE
    assert out["objects"][0]["inMarket"] is None  # not in the response -> unknown
    assert out["objects"][1]["inMarket"] is True
    assert out["cursor"] is None  # empty string on the last page -> None


@pytest.mark.asyncio
async def test_cursor_is_passed_through() -> None:
    client = _client({"items": [_v2_item(UUID, "X")], "total": "9", "cursor": "next"})
    out = await client.get_user_inventory("a8db")
    assert out["cursor"] == "next"


@pytest.mark.asyncio
async def test_errors_are_not_swallowed() -> None:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(side_effect=RuntimeError("404"))
    with pytest.raises(RuntimeError):
        await client.get_user_inventory("a8db")


@pytest.mark.asyncio
async def test_items_without_attributes_do_not_crash() -> None:
    client = _client({"items": [{"inMarket": True}, {}], "cursor": ""})
    out = await client.get_user_inventory("a8db")
    assert len(out["objects"]) == 2
    assert out["objects"][0]["itemId"] == ""


# --- _sync_real_inventory: items not on DMarket must not be linked ---------

def _mixin(client) -> MagicMock:
    mixin = MagicMock()
    mixin.client = client
    return mixin


@pytest.mark.asyncio
async def test_sync_skips_items_not_on_dmarket() -> None:
    """inMarket=False -> composite id, dmarket listing would answer 400."""
    client = _client(
        {
            "items": [
                _v2_item(COMPOSITE, "Steam-only item", in_market=False),
                _v2_item(UUID, "On DMarket item", in_market=True),
            ],
            "cursor": "",
        }
    )
    inserted: list[tuple] = []

    async def _run(fn, *args):
        if fn is mock_db.execute_and_get_lastrowid:
            inserted.append(args)
            return 1
        return None

    with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
        mock_db.run_in_thread = AsyncMock(side_effect=_run)
        mock_db.find_by_dm_item_id = MagicMock(return_value=None)
        n = await _ResaleProdMixin._sync_real_inventory(_mixin(client), "a8db")

    assert n == 1
    assert len(inserted) == 1
    assert inserted[0][1][0] == "On DMarket item"
    assert inserted[0][1][-1] == UUID


@pytest.mark.asyncio
async def test_sync_keeps_items_with_unknown_in_market() -> None:
    """inMarket absent (None) keeps the old behaviour: item is linked."""
    client = _client({"items": [_v2_item(UUID, "Unknown flag item")], "cursor": ""})
    inserted: list[tuple] = []

    async def _run(fn, *args):
        if fn is mock_db.execute_and_get_lastrowid:
            inserted.append(args)
            return 1
        return None

    with patch("src.core.target_sniping.resale_prod.price_db") as mock_db:
        mock_db.run_in_thread = AsyncMock(side_effect=_run)
        mock_db.find_by_dm_item_id = MagicMock(return_value=None)
        n = await _ResaleProdMixin._sync_real_inventory(_mixin(client), "a8db")

    assert n == 1 and inserted[0][1][-1] == UUID
