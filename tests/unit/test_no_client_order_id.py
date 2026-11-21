"""`clientOrderId` is not part of DMarket API spec v2.0.0 (no idempotency key
anywhere), so no request builder may send it: batchCreate (offers) and
user-targets/create. A caller-supplied value is dropped as well.
"""

from __future__ import annotations

import pytest

from src.api.dmarket_api_client import offers as offers_mod
from src.api.dmarket_api_client import targets as targets_mod
from src.api.dmarket_api_client.offers import _OffersMixin
from src.api.dmarket_api_client.targets import _TargetsMixin


class _C(_OffersMixin, _TargetsMixin):
    def __init__(self) -> None:
        self.sent: dict = {}

    async def make_request(self, method, path, params=None, body=None):
        self.sent = {"method": method, "path": path, "body": body}
        return {}


@pytest.mark.asyncio
async def test_batch_create_offers_has_no_client_order_id() -> None:
    c = _C()
    await c.batch_create_offers_v2([{"asset_id": "A1", "price_usd": 1.23}])
    assert c.sent["path"] == "/marketplace-api/v2/offers:batchCreate"
    assert c.sent["body"] == {"requests": [{"assetId": "A1", "priceCents": 123}]}


@pytest.mark.asyncio
async def test_batch_create_offers_drops_caller_client_order_id() -> None:
    c = _C()
    await c.batch_create_offers_v2(
        [{"asset_id": "A1", "price_usd": 1.0, "clientOrderId": "mine"}]
    )
    assert "clientOrderId" not in c.sent["body"]["requests"][0]


@pytest.mark.asyncio
async def test_batch_create_targets_has_no_client_order_id() -> None:
    c = _C()
    t = {"title": "AK-47", "price": {"amount": "100", "currency": "USD"}}
    await c.batch_create_targets([t])
    assert c.sent["body"]["Targets"] == [t]


@pytest.mark.asyncio
async def test_batch_create_targets_drops_caller_client_order_id() -> None:
    c = _C()
    t = {"title": "AK-47", "price": {"amount": "100"}, "clientOrderId": "mine"}
    await c.batch_create_targets([t])
    assert "clientOrderId" not in c.sent["body"]["Targets"][0]
    assert "clientOrderId" in t  # caller's dict is not mutated


def test_dead_idempotency_helper_is_gone() -> None:
    assert not hasattr(targets_mod, "_make_idempotency_key")
    assert not hasattr(targets_mod, "hashlib")
    assert not hasattr(offers_mod, "_make_idempotency_key")
