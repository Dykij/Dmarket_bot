"""Tests for DMarket JSON error body parsing in _handle_response_error."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.api.dmarket_api_client import DMarketAPIClient

MISSING = object()


def _fake_response(status: int) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        headers={},
        request_info=MagicMock(),
        history=(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "expected_code", "expected_message", "expected_body", "expected_prefix"),
    [
        (
            400,
            '{"code":"BadRequest","message":"Invalid title"}',
            "BadRequest",
            "Invalid title",
            {"code": "BadRequest", "message": "Invalid title"},
            "DMarket API Error: ",
        ),
        (
            401,
            '{"code":"Unauthorized","message":"bad sign"}',
            "Unauthorized",
            "bad sign",
            {"code": "Unauthorized", "message": "bad sign"},
            "Authentication failed (401): ",
        ),
        (
            500,
            "<html>cloudflare</html>",
            None,
            None,
            {},
            "DMarket API Error: ",
        ),
        (
            404,
            '{"error":"NotFound","code":12,"message":"no item"}',
            "12",
            "no item",
            {"error": "NotFound", "code": 12, "message": "no item"},
            "DMarket API Error: ",
        ),
        (
            400,
            "[1,2]",
            None,
            None,
            {},
            "DMarket API Error: ",
        ),
    ],
)
async def test_handle_response_error_parses_dm_fields(
    status: int,
    body: str,
    expected_code: str | None,
    expected_message: str | None,
    expected_body: dict,
    expected_prefix: str,
) -> None:
    client = DMarketAPIClient("key", "sec")
    resp = _fake_response(status)

    with pytest.raises(aiohttp.ClientResponseError) as exc_info:
        await client._handle_response_error(resp, body, "/test")

    exc = exc_info.value
    assert isinstance(exc, aiohttp.ClientResponseError)
    assert exc.status == status
    assert getattr(exc, "dm_code", MISSING) == expected_code
    assert getattr(exc, "dm_message", MISSING) == expected_message
    assert getattr(exc, "dm_body", MISSING) == expected_body
    assert f"{expected_prefix}{body}" in str(exc)


@pytest.mark.asyncio
async def test_handle_response_error_429_parses_body_and_sleeps_once() -> None:
    client = DMarketAPIClient("key", "sec")
    body = '{"code":"TooMany","message":"slow down"}'
    resp = _fake_response(429)

    with (
        patch("src.api.dmarket_api_client.core.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(aiohttp.ClientResponseError) as exc_info,
    ):
        await client._handle_response_error(resp, body, "/test")

    exc = exc_info.value
    assert isinstance(exc, aiohttp.ClientResponseError)
    assert exc.status == 429
    assert getattr(exc, "dm_code", MISSING) == "TooMany"
    assert getattr(exc, "dm_message", MISSING) == "slow down"
    assert getattr(exc, "dm_body", MISSING) == {"code": "TooMany", "message": "slow down"}
    assert mock_sleep.await_count == 1
