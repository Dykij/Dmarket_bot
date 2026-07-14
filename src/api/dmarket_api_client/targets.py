"""
targets.py — Buy-side targets (buy orders) and instant purchase.

Mixin with target-order endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


def _make_idempotency_key(item_id: str) -> str:
    """Generate unique idempotency key to prevent duplicate orders on retry."""
    ts = time.time_ns()
    h = hashlib.sha256(f"{item_id}_{ts}".encode()).hexdigest()[:12]
    return f"{item_id}_{ts}_{h}"


class _TargetsMixin:
    """Buy-side target endpoints (create, list, delete, instant buy)."""

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    # --- Trading Ops (Targets / Buy Orders) ---
    async def batch_create_targets(self, targets: list[dict[str, Any]]) -> dict[str, Any]:
        """Creation of targets (buy orders). Path verified via Swagger 2026.

        Each target gets an idempotency key to prevent duplicate placement on retry.
        """
        enriched = []
        for t in targets:
            t_copy = dict(t)
            if "clientOrderId" not in t_copy:
                title = t_copy.get("title", t_copy.get("Title", "unknown"))
                t_copy["clientOrderId"] = _make_idempotency_key(title)
            enriched.append(t_copy)
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-targets/create",
            body={"Targets": enriched},
        )

    async def batch_delete_targets(self, targets: list[dict[str, Any]]) -> dict[str, Any]:
        """Mass deletion of targets. Path verified via Swagger 2026."""
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

        Each offer gets an idempotency key to prevent duplicate buys on retry.
        """
        enriched = []
        for o in offers:
            o_copy = dict(o)
            if "clientOrderId" not in o_copy:
                offer_id = o_copy.get("offerId", "unknown")
                o_copy["clientOrderId"] = _make_idempotency_key(offer_id)
            enriched.append(o_copy)
        return await self.make_request(
            "PATCH", "/exchange/v1/offers-buy", body={"offers": enriched}
        )

    async def get_user_targets(
        self, game_id: str, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        """List active buy orders."""
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-targets", params=params
        )
