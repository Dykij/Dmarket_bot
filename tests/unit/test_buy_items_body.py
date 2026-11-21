"""PATCH /exchange/v1/offers-buy request body (real client, make_request stubbed).

Spec v2.0.0 entity.OfferPrice: offerId, price{amount: cents string, currency},
type (`dmarket` default | `p2p`; "Sending a P2P offer as `dmarket` fails").
`clientOrderId` appears nowhere in the spec, so it is not sent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.api.dmarket_api_client import DMarketAPIClient


def _client() -> DMarketAPIClient:
    client = DMarketAPIClient("key", "sec")
    client.make_request = AsyncMock(return_value={"status": "TxSuccess"})
    return client


OFFER = {"offerId": "o-1", "price": {"amount": "123", "currency": "USD"}}


@pytest.mark.asyncio
async def test_body_has_type_dmarket_and_no_client_order_id() -> None:
    client = _client()
    await client.buy_items([dict(OFFER)])
    client.make_request.assert_awaited_once_with(
        "PATCH",
        "/exchange/v1/offers-buy",
        body={"offers": [{"offerId": "o-1", "price": {"amount": "123", "currency": "USD"}, "type": "dmarket"}]},
    )


@pytest.mark.asyncio
async def test_explicit_type_is_kept() -> None:
    client = _client()
    await client.buy_items([{**OFFER, "type": "p2p"}])
    sent = client.make_request.await_args.kwargs["body"]["offers"][0]
    assert sent["type"] == "p2p"


@pytest.mark.asyncio
async def test_caller_supplied_client_order_id_is_not_forwarded() -> None:
    client = _client()
    await client.buy_items([{**OFFER, "clientOrderId": "x"}])
    sent = client.make_request.await_args.kwargs["body"]["offers"][0]
    assert "clientOrderId" not in sent


@pytest.mark.asyncio
async def test_input_dicts_are_not_mutated() -> None:
    client = _client()
    offer = dict(OFFER)
    await client.buy_items([offer])
    assert offer == OFFER


@pytest.mark.asyncio
async def test_batch_keeps_order_and_count() -> None:
    client = _client()
    await client.buy_items([{**OFFER, "offerId": f"o-{i}"} for i in range(3)])
    sent = client.make_request.await_args.kwargs["body"]["offers"]
    assert [o["offerId"] for o in sent] == ["o-0", "o-1", "o-2"]
    assert all(o["type"] == "dmarket" for o in sent)
