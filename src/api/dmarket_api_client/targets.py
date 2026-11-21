"""
targets.py — Buy-side targets (buy orders) and instant purchase.

Mixin with target-order endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class _TargetsMixin:
    """Buy-side target endpoints (create, list, delete, instant buy).
    NOTE: All target endpoints remain on v1 because v2 equivalents DO NOT exist in the API.
    """

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    # --- Trading Ops (Targets / Buy Orders) ---
    async def batch_create_targets(self, targets: list[dict[str, Any]]) -> dict[str, Any]:
        """Creation of targets (buy orders). Path verified via Swagger 2026.
        NOTE: Kept on v1 (/marketplace-api/v1/user-targets/create) as v2 does not exist.

        The spec (v2.0.0) has no `clientOrderId`/idempotency key; it is not sent
        (a value passed by the caller is dropped, the caller's dicts are untouched).
        """
        enriched = []
        for t in targets:
            t_copy = dict(t)
            t_copy.pop("clientOrderId", None)
            enriched.append(t_copy)
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-targets/create",
            body={"Targets": enriched},
        )

    async def batch_delete_targets(self, targets: list[dict[str, Any]]) -> dict[str, Any]:
        """Mass deletion of targets. Path verified via Swagger 2026.
        NOTE: Kept on v1 (/marketplace-api/v1/user-targets/delete) as v2 does not exist.
        """
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-targets/delete",
            body={"Targets": targets},
        )

    async def buy_items(self, offers: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Instant Purchase of existing market listings.
        Payload: [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}]
        Endpoint: PATCH /exchange/v1/offers-buy (verified 2026-06-06, was 404 on
        /exchange/v1/market/buy)
        NOTE: Kept on v1 as v2 does not exist for this functionality.

        Body per spec v2.0.0 (entity.OfferPrice): offerId, price{amount (cents,
        string), currency}, type. `type` defaults to "dmarket" here (a P2P
        offer sent as dmarket fails; pass type="p2p" explicitly and buy P2P in
        a request of its own). `clientOrderId` is NOT sent: it appears nowhere
        in the spec and the server's reaction is unverified. A repeated buy of
        the same offerId cannot succeed twice (the offer is gone), so a retry
        after a timeout may report a failure for a purchase that went through;
        the inventory sync (`_sync_real_inventory`) picks such items up.
        """
        enriched = []
        for o in offers:
            o_copy = dict(o)
            o_copy.pop("clientOrderId", None)
            o_copy.setdefault("type", "dmarket")
            enriched.append(o_copy)
        return await self.make_request(
            "PATCH", "/exchange/v1/offers-buy", body={"offers": enriched}
        )

    async def get_user_targets(
        self, game_id: str, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        """List active buy orders.
        NOTE: Kept on v1 (/marketplace-api/v1/user-targets) as v2 does not exist.
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-targets", params=params
        )
