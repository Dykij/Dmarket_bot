"""_execute_liquidation (PROD path): fallback and accounting of listed items.

- The one-by-one fallback runs only after a DEFINITE rejection of the whole
  batch (HTTP 4xx except 429). After a timeout / dropped connection / 5xx /
  exhausted retries the batch may have been processed, so re-listing item by
  item is forbidden (it would only produce errors or double-handle items).
- An item counts as liquidated only if its assetId is in `offers[]` and not in
  `failed[]` of the answer (a 200 answer may carry per-item failures).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from tenacity import RetryError

from src.core.target_sniping.position_guard import _PositionGuardMixin

P = "src.core.target_sniping.position_guard"


class _Guard(_PositionGuardMixin):
    def __init__(self) -> None:
        self.client = MagicMock()
        self.client.batch_create_offers_v2 = AsyncMock()
        self._background_tasks: set = set()


def _row(i: int, asset: str) -> dict:
    return {"id": i, "hash_name": f"Item {i}", "buy_price": 10.0, "dm_item_id": asset}


def _items(*assets: str):
    return [(_row(i + 1, a), 12.0, "test") for i, a in enumerate(assets)]


def _http(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(MagicMock(), (), status=status, message="x")


@pytest.fixture()
def env():
    notifier = MagicMock()
    notifier.sell = AsyncMock()
    with patch(f"{P}.Config") as cfg, patch(f"{P}.price_db") as db, patch(
        f"{P}._get_notifier", return_value=notifier
    ):
        cfg.DRY_RUN = False
        yield db


async def _run(guard: _Guard, *assets: str) -> int:
    return await guard._execute_liquidation(_items(*assets), "a8db", "TST")


def _calls(guard: _Guard) -> list:
    return guard.client.batch_create_offers_v2.await_args_list


# --- fallback only after a definite rejection -------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        asyncio.TimeoutError(),
        aiohttp.ServerDisconnectedError(),
        _http(500),
        _http(503),
        RetryError(MagicMock()),
    ],
    ids=["timeout", "disconnect", "500", "503", "retry_error"],
)
async def test_no_fallback_after_ambiguous_failure(env, exc) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = exc
    n = await _run(g, "A1", "A2")
    assert n == 0
    assert len(_calls(g)) == 1  # the batch only, no per-item calls


@pytest.mark.asyncio
async def test_no_fallback_after_429(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = _http(429)
    assert await _run(g, "A1", "A2") == 0
    assert len(_calls(g)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 403, 404, 422])
async def test_fallback_after_definite_4xx_rejection(env, status) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = [
        _http(status),
        {"offers": [{"assetId": "A1"}], "failed": []},
        {"offers": [{"assetId": "A2"}], "failed": []},
    ]
    assert await _run(g, "A1", "A2") == 2
    assert len(_calls(g)) == 3
    single = [c.args[0] for c in _calls(g)[1:]]
    assert [len(s) for s in single] == [1, 1]
    assert [s[0]["asset_id"] for s in single] == ["A1", "A2"]
    marked = [c.args for c in env.update_virtual_status.call_args_list]
    assert marked == [(1, "selling"), (2, "selling")]


# --- accounting: offers[] minus failed[] ------------------------------------

@pytest.mark.asyncio
async def test_batch_failed_items_not_counted_or_marked_selling(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.return_value = {
        "offers": [{"assetId": "A1"}, {"assetId": "A2"}],
        "failed": [{"assetId": "A2", "code": "AlreadyExists"}],
    }
    assert await _run(g, "A1", "A2") == 1
    marked = [c.args for c in env.update_virtual_status.call_args_list]
    assert marked == [(1, "selling")]


@pytest.mark.asyncio
async def test_batch_only_failed_counts_zero(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.return_value = {
        "offers": [],
        "failed": [{"assetId": "A1", "code": "Internal"}],
    }
    assert await _run(g, "A1") == 0
    env.update_virtual_status.assert_not_called()


@pytest.mark.asyncio
async def test_single_call_failed_not_counted(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = [
        _http(400),
        {"offers": [{"assetId": "A1"}], "failed": []},
        {"offers": [], "failed": [{"assetId": "A2", "code": "AlreadyExists"}]},
    ]
    assert await _run(g, "A1", "A2") == 1
    marked = [c.args for c in env.update_virtual_status.call_args_list]
    assert marked == [(1, "selling")]


@pytest.mark.asyncio
async def test_single_call_empty_answer_not_counted(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = [_http(400), {}, {}]
    assert await _run(g, "A1", "A2") == 0


@pytest.mark.asyncio
async def test_single_call_error_does_not_stop_next_items(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.side_effect = [
        _http(400),
        asyncio.TimeoutError(),
        {"offers": [{"assetId": "A2"}], "failed": []},
    ]
    assert await _run(g, "A1", "A2") == 1
    marked = [c.args for c in env.update_virtual_status.call_args_list]
    assert marked == [(2, "selling")]


@pytest.mark.asyncio
async def test_clean_batch_success_unchanged(env) -> None:
    g = _Guard()
    g.client.batch_create_offers_v2.return_value = {
        "offers": [{"assetId": "A1"}, {"assetId": "A2"}],
    }
    assert await _run(g, "A1", "A2") == 2
    assert len(_calls(g)) == 1
