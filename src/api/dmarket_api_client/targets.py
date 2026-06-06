"""
targets.py — Buy-side targets (buy orders) and instant purchase.

Mixin with target-order endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class _TargetsMixin:
    """Buy-side target endpoints (create, list, delete, instant buy)."""

    # --- Trading Ops (Targets / Buy Orders) ---
    async def batch_create_targets(self, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creation of targets (buy orders). Path verified via Swagger 2026."""
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-targets/create",
            body={"Targets": targets},
        )

    async def batch_delete_targets(self, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Mass deletion of targets. Path verified via Swagger 2026."""
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-targets/delete",
            body={"Targets": targets},
        )

    async def buy_items(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Instant Purchase of existing market listings.
        Payload: [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}]
        Endpoint: PATCH /exchange/v1/offers-buy (verified 2026-06-06, was 404 on
        /exchange/v1/market/buy)
        """
        return await self.make_request(
            "PATCH", "/exchange/v1/offers-buy", body={"offers": offers}
        )

    async def get_user_targets(
        self, game_id: str, limit: int = 50, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """List active buy orders."""
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-targets", params=params
        )
