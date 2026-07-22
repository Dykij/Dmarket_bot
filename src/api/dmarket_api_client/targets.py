"""
targets.py — Buy-side targets (buy orders) and instant purchase.

Mixin with target-order endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


def _make_idempotency_key(item_id: str, *, price_cents: int = 0) -> str:
    """Generate deterministic idempotency key for order deduplication on retry.

    Key is stable across retries for the same (item, price) pair so DMarket
    API can recognize a duplicate and return the original result instead of
    creating a second order.  Falls back to item_id-only when price is unknown.
    """
    if price_cents > 0:
        raw = f"{item_id}_{price_cents}"
    else:
        raw = item_id
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{item_id}_{h}"


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
                price_amount = 0
                try:
                    price_obj = t_copy.get("price", t_copy.get("Price", {}))
                    if isinstance(price_obj, dict):
                        price_amount = int(price_obj.get("amount", price_obj.get("Amount", 0)))
                except (ValueError, TypeError):
                    pass
                t_copy["clientOrderId"] = _make_idempotency_key(title, price_cents=price_amount)
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

        Each offer gets a deterministic idempotency key (offerId + price_cents)
        so that retries after timeout produce the SAME key and DMarket can
        deduplicate instead of creating a second order.
        """
        enriched = []
        for o in offers:
            o_copy = dict(o)
            if "clientOrderId" not in o_copy:
                offer_id = o_copy.get("offerId", "unknown")
                price_amount = 0
                try:
                    price_amount = int(o_copy.get("price", {}).get("amount", 0))
                except (ValueError, TypeError):
                    pass
                o_copy["clientOrderId"] = _make_idempotency_key(offer_id, price_cents=price_amount)
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
