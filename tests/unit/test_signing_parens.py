"""Tests for DMarket API request signing and URL encoding without stripping parentheses."""

from __future__ import annotations

import urllib.parse
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yarl

from src.api.dmarket_api_client import DMarketAPIClient


def _old_reference(base_url: str, path: str, params: dict | None) -> tuple[str, str]:
    """Exact copy of pre-f15 signing/URL logic (core.py:408-418,429 at e2d22db)."""
    path = path.replace("(", "").replace(")", "")
    api_path = path
    if params:
        clean_params = {}
        for k, v in params.items():
            if isinstance(v, str):
                clean_params[k] = v.replace("(", "").replace(")", "")
            else:
                clean_params[k] = v
        query_string = urllib.parse.urlencode(clean_params)
        api_path = f"{path}?{query_string}"
    url = f"{base_url}{api_path}"
    return api_path, url


def _make_client(base_url: str = "https://api.dmarket.com") -> tuple[DMarketAPIClient, list[str]]:
    client = DMarketAPIClient("key", "sec", base_url=base_url)
    captured_api_paths: list[str] = []

    def _fake_sign(method: str, api_path: str, body: str, timestamp: str) -> str:
        captured_api_paths.append(api_path)
        return "sig"

    client._generate_signature = _fake_sign  # type: ignore[method-assign]
    return client, captured_api_paths


def _patch_clock():
    mock_clock = MagicMock()
    mock_clock.ensure_synced = AsyncMock()
    mock_clock.now = MagicMock(return_value=1764000000.0)
    return patch("src.utils.clock_sync.clock_sync", mock_clock)


INVARIANT_CASES = [
    ("GET", "/marketplace-api/v2/offers", {"gameId": "a8db", "limit": 100, "title": "Kilowatt Case", "cursor": "abc123"}, None),
    ("GET", "/trade-aggregator/v1/last-sales", {"gameId": "a8db", "title": "Kilowatt Case", "days": 7, "limit": 20}, None),
    ("GET", "/exchange/v1/customized-fees", {"gameId": "a8db", "limit": 100, "offset": 0}, None),
    ("GET", "/marketplace-api/v2/user/offers", {"gameId": "a8db", "limit": 50}, None),
    ("GET", "/account/v1/balance", None, None),
    ("GET", "/marketplace-api/v1/user-offers/closed", {"Limit": 50, "OrderDir": "desc"}, None),
    ("POST", "/marketplace-api/v2/offers:batchCreate", None, {"requests": [{"assetId": "a1", "priceCents": 1500}]}),
    ("PATCH", "/exchange/v1/offers-buy", None, {"offers": [{"offerId": "o1", "price": {"amount": "1500", "currency": "USD"}}]}),
    ("POST", "/marketplace-api/v1/aggregated-prices", None, {"limit": 100, "filter": {"game": "a8db", "titles": ["AK-47 | Redline (Field-Tested)"]}}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,params,body", INVARIANT_CASES)
async def test_invariant_no_parens_byte_identical(
    method: str,
    path: str,
    params: dict | None,
    body: dict | None,
) -> None:
    client, captured = _make_client()
    expected_api_path, expected_url = _old_reference(client.BASE_URL, path, params)

    with _patch_clock():
        url, _body_str, _headers = await client._prepare_request_params(method, path, params, body)

    assert captured == [expected_api_path]
    assert url == expected_url


@pytest.mark.asyncio
async def test_last_sales_with_parens_signs_and_builds_url_with_encoded_parens() -> None:
    client, captured = _make_client()
    params = {"gameId": "a8db", "title": "AK-47 | Redline (Field-Tested)", "limit": 20}

    with _patch_clock():
        url, _body_str, _headers = await client._prepare_request_params(
            "GET", "/trade-aggregator/v1/last-sales", params, None
        )

    signed_api_path = captured[0]
    assert "title=AK-47+%7C+Redline+%28Field-Tested%29" in signed_api_path
    signed_query = signed_api_path.split("?", 1)[1]
    assert url.endswith(f"?{signed_query}")


@pytest.mark.asyncio
async def test_yarl_encoded_true_preserves_signed_query_with_parens() -> None:
    client, captured = _make_client()
    params = {"gameId": "a8db", "title": "AK-47 | Redline (Field-Tested)", "limit": 20}

    with _patch_clock():
        url, _body_str, _headers = await client._prepare_request_params(
            "GET", "/trade-aggregator/v1/last-sales", params, None
        )

    signed_query = captured[0].split("?", 1)[1]
    assert "%28" in signed_query
    assert yarl.URL(url, encoded=True).raw_query_string == signed_query


@pytest.mark.asyncio
async def test_path_param_with_parens_signed_decoded_and_sent_encoded() -> None:
    client, captured = _make_client()
    path = "/marketplace-api/v1/targets-by-title/a8db/AK-47 | Redline (Field-Tested)"

    with _patch_clock():
        url, _body_str, _headers = await client._prepare_request_params("GET", path, None, None)

    assert captured[0] == path
    assert yarl.URL(url, encoded=True).raw_path == (
        "/marketplace-api/v1/targets-by-title/a8db/AK-47%20%7C%20Redline%20(Field-Tested)"
    )


@pytest.mark.asyncio
async def test_request_once_sends_yarl_url_with_encoded_true() -> None:
    client, captured = _make_client()
    params = {"gameId": "a8db", "title": "AK-47 | Redline (Field-Tested)", "limit": 20}
    sent_urls: list[object] = []
    sent_kwargs: list[dict[str, object]] = []

    class _FakeResp:
        status = 200

        async def read(self) -> bytes:
            return b"{}"

    class _FakeSession:
        @asynccontextmanager
        async def request(self, method: str, url: object, **kwargs):
            sent_urls.append(url)
            sent_kwargs.append(kwargs)
            yield _FakeResp()

    client.get_session = AsyncMock(return_value=_FakeSession())  # type: ignore[method-assign]
    client._wait_for_rate_limit = AsyncMock()  # type: ignore[method-assign]

    with _patch_clock():
        await client._request_once("GET", "/trade-aggregator/v1/last-sales", params=params)

    signed_query = captured[0].split("?", 1)[1]
    assert len(sent_urls) == 1
    url_arg = sent_urls[0]
    assert isinstance(url_arg, yarl.URL)
    assert url_arg.raw_query_string == signed_query
    assert "params" not in sent_kwargs[0]


@pytest.mark.asyncio
async def test_get_market_items_v2_preserves_parens_in_title() -> None:
    client, _ = _make_client()
    captured_params: list[dict] = []

    async def _fake_make_request(method: str, path: str, params=None, body=None):
        captured_params.append(params)
        return {"items": []}

    client.make_request = _fake_make_request  # type: ignore[method-assign]
    await client.get_market_items_v2(game_id="a8db", title="AK-47 | Redline (Field-Tested)")

    assert captured_params[0]["title"] == "AK-47 | Redline (Field-Tested)"
