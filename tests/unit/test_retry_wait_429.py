"""Tests for skipping tenacity retry wait on HTTP 429 in DMarketAPIClient.make_request."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from tenacity import RetryError

from src.api.dmarket_api_client import DMarketAPIClient

OK = {"ok": 1}


def _http(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=status)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> DMarketAPIClient:
    c = DMarketAPIClient("key", "sec")

    async def _no_net(*_a, **_kw):
        raise AssertionError("network used")

    monkeypatch.setattr(c, "get_session", _no_net)
    c.RETRY_WAIT = MagicMock(return_value=0.0)
    return c


@pytest.mark.asyncio
async def test_get_429_skips_tenacity_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[_http(429), OK])
    client._request_once = req

    res = await client.make_request("GET", "/marketplace-api/v2/offers")

    assert res == OK
    assert req.await_count == 2
    assert client.RETRY_WAIT.call_count == 0


@pytest.mark.asyncio
async def test_mutation_429_retries_and_skips_tenacity_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[_http(429), OK])
    client._request_once = req

    res = await client.make_request("POST", "/marketplace-api/v2/offers:batchCreate", body={"requests": []})

    assert res == OK
    assert req.await_count == 2
    assert client.RETRY_WAIT.call_count == 0


@pytest.mark.asyncio
async def test_get_500_uses_tenacity_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[_http(500), OK])
    client._request_once = req

    res = await client.make_request("GET", "/marketplace-api/v2/offers")

    assert res == OK
    assert req.await_count == 2
    assert client.RETRY_WAIT.call_count == 1


@pytest.mark.asyncio
async def test_get_timeout_uses_tenacity_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[asyncio.TimeoutError(), OK])
    client._request_once = req

    res = await client.make_request("GET", "/marketplace-api/v2/offers")

    assert res == OK
    assert req.await_count == 2
    assert client.RETRY_WAIT.call_count == 1


@pytest.mark.asyncio
async def test_get_429_exhausted_raises_retry_error_without_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[_http(429), _http(429), _http(429)])
    client._request_once = req

    with pytest.raises(RetryError):
        await client.make_request("GET", "/marketplace-api/v2/offers")

    assert req.await_count == 3
    assert client.RETRY_WAIT.call_count == 0


@pytest.mark.asyncio
async def test_mutation_500_does_not_retry_or_wait(client: DMarketAPIClient) -> None:
    req = AsyncMock(side_effect=[_http(500)])
    client._request_once = req

    with pytest.raises(aiohttp.ClientResponseError) as exc_info:
        await client.make_request("POST", "/marketplace-api/v2/offers:batchCreate", body={"requests": []})

    assert exc_info.value.status == 500
    assert req.await_count == 1
    assert client.RETRY_WAIT.call_count == 0
