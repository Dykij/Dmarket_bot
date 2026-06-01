"""
offers.py — Sell-side offers (single, batch, edit, delete, list).

Mixin with the offer-lifecycle endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class _OffersMixin:
    """Sell-side offer endpoints (create, edit, delete, list)."""

    async def get_user_offers(
        self, game_id: str, limit: int = 50, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches items the user currently has listed for sale."""
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-offers", params=params
        )

    # --- v12.0: Sell Endpoints (resale pipeline) ---
    async def create_offer(self, asset_id: str, price_usd: float) -> Dict[str, Any]:
        """
        List an owned item for sale on DMarket.

        Endpoint: POST /marketplace-api/v1/user-offers/create
        Body: {"assetId": "...", "price": {"amount": "123", "currency": "USD"}}
        """
        body = {
            "assetId": asset_id,
            "price": {"amount": str(int(price_usd * 100)), "currency": "USD"},
        }
        return await self.make_request(
            "POST", "/marketplace-api/v1/user-offers/create", body=body
        )

    async def batch_create_offers(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch list items for sale.

        Endpoint: POST /marketplace-api/v1/user-offers/create-batch (if available)
        or POST /marketplace-api/v1/user-offers/create with array
        """
        body_offers = []
        for o in offers:
            body_offers.append(
                {
                    "assetId": o["asset_id"],
                    "price": {
                        "amount": str(int(o["price_usd"] * 100)),
                        "currency": "USD",
                    },
                }
            )
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-offers/create",
            body={"offers": body_offers},
        )

    async def delete_offers(self, offer_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel (delist) one or more offers.

        Endpoint: POST /marketplace-api/v1/user-offers/close
        Body: {"offerIds": ["...", "..."]}
        """
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-offers/close",
            body={"offerIds": offer_ids},
        )

    async def edit_offer(self, offer_id: str, new_price_usd: float) -> Dict[str, Any]:
        """
        Reprice an existing offer.

        Endpoint: PATCH /marketplace-api/v1/user-offers/edit
        Body: {"offerId": "...", "price": {"amount": "123", "currency": "USD"}}
        """
        body = {
            "offerId": offer_id,
            "price": {"amount": str(int(new_price_usd * 100)), "currency": "USD"},
        }
        return await self.make_request(
            "PATCH", "/marketplace-api/v1/user-offers/edit", body=body
        )

    # ------------------------------------------------------------------
    # v12.2 Phase 2.5: API v2 Batch Endpoints
    # ------------------------------------------------------------------
    async def batch_create_offers_v2(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch list up to 100 items in a single request.

        Endpoint: POST /exchange/v1/user-offers/batch-create
        Body: {"offers": [{"assetId": "...", "price": {"amount": "123", "currency": "USD"}}, ...]}
        """
        body_offers = []
        for o in offers:
            body_offers.append(
                {
                    "assetId": o["asset_id"],
                    "price": {
                        "amount": str(int(o["price_usd"] * 100)),
                        "currency": "USD",
                    },
                }
            )
        return await self.make_request(
            "POST",
            "/exchange/v1/user-offers/batch-create",
            body={"offers": body_offers},
        )

    async def batch_edit_offers_v2(self, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch reprice up to 100 offers in a single request.

        Endpoint: PATCH /exchange/v1/user-offers/batch-edit
        Body: {"edits": [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}, ...]}
        """
        body_edits = []
        for e in edits:
            body_edits.append(
                {
                    "offerId": e["offer_id"],
                    "price": {
                        "amount": str(int(e["new_price_usd"] * 100)),
                        "currency": "USD",
                    },
                }
            )
        return await self.make_request(
            "PATCH",
            "/exchange/v1/user-offers/batch-edit",
            body={"edits": body_edits},
        )

    async def batch_delete_offers_v2(self, offer_ids: List[str]) -> Dict[str, Any]:
        """
        v2: Batch cancel (delist) up to 100 offers in a single request.

        Endpoint: POST /exchange/v1/user-offers/batch-close
        Body: {"offerIds": ["...", "..."]}
        """
        return await self.make_request(
            "POST",
            "/exchange/v1/user-offers/batch-close",
            body={"offerIds": offer_ids},
        )

    async def get_user_offers_v2(
        self,
        game_id: str,
        limit: int = 100,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        v2: List active offers with optional status filter.

        Endpoint: GET /exchange/v1/user-offers?gameId=a8db&status=active&limit=100
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return await self.make_request("GET", "/exchange/v1/user-offers", params=params)
