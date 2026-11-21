"""Retry policy of DMarketAPIClient.make_request (real client).

Reads (GET and the read-only POST aggregated-prices) keep the transient retry
(timeout, connection error, 5xx, 429). Mutations (POST/PATCH/PUT/DELETE:
offers-buy, offers:batch*, user-targets/*) are retried ONLY when the server
certainly did not process the request: HTTP 429, or a connection that was
never established (ClientConnectorError). A timeout, a dropped connection or
a 5xx may hide a request that went through; those surface to the caller.
The network is forbidden: get_session raises, only `_request_once` is scripted.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from tenacity import RetryError, wait_none

from src.api.dmarket_api_client import DMarketAPIClient

OK = {"ok": 1}


class _NeverConnected(aiohttp.ClientConnectorError):
    def __init__(self) -> None:  # real ctor needs a ConnectionKey
        pass


def _http(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(MagicMock(), (), status=status, message="x")


@pytest.fixture()
def client(monkeypatch):
    c = DMarketAPIClient("key", "sec")

    async def _no_net(*_a, **_kw):
        raise AssertionError("network used")

    monkeypatch.setattr(c, "get_session", _no_net)
    c.RETRY_WAIT = wait_none()
    return c


def _script(c: DMarketAPIClient, *outcomes) -> AsyncMock:
    m = AsyncMock(side_effect=list(outcomes))
    c._request_once = m
    return m


# --- reads keep the transient retry -----------------------------------------

@pytest.mark.asyncio
async def test_get_retries_timeouts_then_succeeds(client) -> None:
    m = _script(client, asyncio.TimeoutError(), asyncio.TimeoutError(), OK)
    assert await client.make_request("GET", "/account/v1/balance") == OK
    assert m.await_count == 3


@pytest.mark.asyncio
async def test_get_retries_5xx(client) -> None:
    m = _script(client, _http(503), OK)
    assert await client.make_request("GET", "/account/v1/balance") == OK
    assert m.await_count == 2


@pytest.mark.asyncio
async def test_get_exhausted_keeps_retry_error_behaviour(client) -> None:
    m = _script(client, *[asyncio.TimeoutError()] * 3)
    with pytest.raises(RetryError):
        await client.make_request("GET", "/account/v1/balance")
    assert m.await_count == 3


@pytest.mark.asyncio
async def test_read_only_post_aggregated_prices_is_retried(client) -> None:
    m = _script(client, asyncio.TimeoutError(), OK)
    path = "/marketplace-api/v1/aggregated-prices"
    assert await client.make_request("POST", path, body={"filter": {}}) == OK
    assert m.await_count == 2


# --- mutations: no retry when the outcome is ambiguous ----------------------

MUTATIONS = [
    ("PATCH", "/exchange/v1/offers-buy"),
    ("POST", "/marketplace-api/v2/offers:batchCreate"),
    ("POST", "/marketplace-api/v2/offers:batchUpdate"),
    ("POST", "/marketplace-api/v2/offers:batchDelete"),
    ("POST", "/marketplace-api/v1/user-targets/create"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", MUTATIONS)
async def test_mutation_timeout_is_not_retried(client, method, path) -> None:
    m = _script(client, asyncio.TimeoutError(), OK)
    with pytest.raises(asyncio.TimeoutError):
        await client.make_request(method, path, body={"x": 1})
    assert m.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", MUTATIONS)
async def test_mutation_5xx_is_not_retried(client, method, path) -> None:
    m = _script(client, _http(500), OK)
    with pytest.raises(aiohttp.ClientResponseError):
        await client.make_request(method, path, body={"x": 1})
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_mutation_dropped_connection_is_not_retried(client) -> None:
    m = _script(client, aiohttp.ServerDisconnectedError(), OK)
    with pytest.raises(aiohttp.ServerDisconnectedError):
        await client.make_request("PATCH", "/exchange/v1/offers-buy", body={"offers": []})
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_lowercase_method_is_treated_as_mutation(client) -> None:
    m = _script(client, asyncio.TimeoutError(), OK)
    with pytest.raises(asyncio.TimeoutError):
        await client.make_request("patch", "/exchange/v1/offers-buy", body={"offers": []})
    assert m.await_count == 1


# --- mutations: retry only when certainly not processed ---------------------

@pytest.mark.asyncio
async def test_mutation_429_is_retried(client) -> None:
    m = _script(client, _http(429), OK)
    path = "/marketplace-api/v2/offers:batchCreate"
    assert await client.make_request("POST", path, body={"requests": []}) == OK
    assert m.await_count == 2


@pytest.mark.asyncio
async def test_mutation_never_connected_is_retried(client) -> None:
    m = _script(client, _NeverConnected(), OK)
    assert await client.make_request("PATCH", "/exchange/v1/offers-buy", body={"offers": []}) == OK
    assert m.await_count == 2


@pytest.mark.asyncio
async def test_mutation_4xx_is_not_retried(client) -> None:
    m = _script(client, _http(400), OK)
    with pytest.raises(aiohttp.ClientResponseError):
        await client.make_request("PATCH", "/exchange/v1/offers-buy", body={"offers": []})
    assert m.await_count == 1
