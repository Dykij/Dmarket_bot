"""Tests for sel5: v2 user inventory migration (get_user_inventory & get_user_inventory_detailed)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.api.dmarket_api_client import DMarketAPIClient

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "dmarket_v2_user_inventory_sample.json"


def _load_sample() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _client(*responses) -> DMarketAPIClient:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(side_effect=list(responses))
    return client


@pytest.mark.asyncio
async def test_t1_uses_v2_path_and_params() -> None:
    """T1: get_user_inventory and get_user_inventory_detailed call GET /marketplace-api/v2/user/inventory."""
    sample = _load_sample()
    client = _client(sample, {"items": [], "total": "0", "cursor": ""})

    await client.get_user_inventory("a8db", limit=25, cursor="c1")
    await client.get_user_inventory_detailed("a8db", limit=50)

    assert client.make_request.await_count == 2
    call1 = client.make_request.await_args_list[0]
    call2 = client.make_request.await_args_list[1]

    assert call1.args[:2] == ("GET", "/marketplace-api/v2/user/inventory")
    assert call1.kwargs["params"] == {"gameId": "a8db", "limit": 25, "cursor": "c1"}

    assert call2.args[:2] == ("GET", "/marketplace-api/v2/user/inventory")
    assert call2.kwargs["params"] == {"gameId": "a8db", "limit": 50}
    assert "basic" not in call2.kwargs["params"]


@pytest.mark.asyncio
async def test_t2_detailed_pagination_cursor_and_stop() -> None:
    """T2: get_user_inventory_detailed follows cursor across pages and stops on empty cursor."""
    sample = _load_sample()
    page1 = {"items": [sample["items"][0]], "total": "2", "cursor": "next-cursor-2"}
    page2 = {"items": [sample["items"][1]], "total": "2", "cursor": ""}
    client = _client(page1, page2)

    out = await client.get_user_inventory_detailed("a8db", limit=1)

    assert client.make_request.await_count == 2
    assert client.make_request.await_args_list[1].kwargs["params"] == {
        "gameId": "a8db",
        "limit": 1,
        "cursor": "next-cursor-2",
    }
    assert len(out) == 2
    assert [it["itemId"] for it in out] == [
        "11111111-1111-4111-8111-111111111111",
        "123456:1000000002:2000000002:730",
    ]


@pytest.mark.asyncio
async def test_t3_normalization_item_id_title_and_cursor() -> None:
    """T3: Normalizes attributes.id -> itemId, attributes.title -> title, and top-level cursor."""
    sample = _load_sample()
    page = {"items": sample["items"], "total": "2", "cursor": "cur-next"}
    client = _client(page, {"items": sample["items"], "total": "2", "cursor": ""})

    inv = await client.get_user_inventory("a8db")
    assert inv["cursor"] == "cur-next"
    assert [o["itemId"] for o in inv["objects"]] == [
        "11111111-1111-4111-8111-111111111111",
        "123456:1000000002:2000000002:730",
    ]
    assert [o["title"] for o in inv["objects"]] == [
        "AK-47 | Redline (Field-Tested)",
        "PP-Bizon | Facility Sketch (Field-Tested)",
    ]

    detailed = await client.get_user_inventory_detailed("a8db")
    assert [d["itemId"] for d in detailed] == [
        "11111111-1111-4111-8111-111111111111",
        "123456:1000000002:2000000002:730",
    ]
    assert [d["title"] for d in detailed] == [
        "AK-47 | Redline (Field-Tested)",
        "PP-Bizon | Facility Sketch (Field-Tested)",
    ]


@pytest.mark.asyncio
async def test_t4_detailed_status_and_finalization_time() -> None:
    """T4: Future unlockDate -> trade_protected + FinalizationTime>now; 1970-01-01 -> active + 0.0."""
    sample = _load_sample()
    client = _client(sample)

    out = await client.get_user_inventory_detailed("a8db")
    assert len(out) == 2

    locked_item, unlocked_item = out[0], out[1]
    assert locked_item["status"] == "trade_protected"
    assert locked_item["FinalizationTime"] > time.time()

    assert unlocked_item["status"] == "active"
    assert unlocked_item["FinalizationTime"] == 0.0


@pytest.mark.asyncio
async def test_t5_detailed_error_on_second_page_returns_first_page() -> None:
    """T5: Network error on page 2 returns page 1 items without raising; get_user_inventory raises."""
    sample = _load_sample()
    page1 = {"items": [sample["items"][0]], "total": "2", "cursor": "c2"}
    client = _client(page1, RuntimeError("network timeout"))

    out = await client.get_user_inventory_detailed("a8db", limit=1)
    assert len(out) == 1
    assert out[0]["itemId"] == "11111111-1111-4111-8111-111111111111"

    client_inv = _client(RuntimeError("404"))
    with pytest.raises(RuntimeError):
        await client_inv.get_user_inventory("a8db")
