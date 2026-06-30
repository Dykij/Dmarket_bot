"""
offers.py — Sell-side offers (single, batch, edit, delete, list).

Mixin with the offer-lifecycle endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class _OffersMixin:
    """Sell-side offer endpoints (create, edit, delete, list)."""

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    async def get_user_offers(
        self, game_id: str, limit: int = 50, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches items the user currently has listed for sale.

        Endpoint: GET /exchange/v1/user-offers (per Swagger v1.1.0)
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/exchange/v1/user-offers", params=params
        )

    # ------------------------------------------------------------------
    # March 2026: Official v2 Batch Endpoints (Marketplace API v2)
    # Endpoint format: POST /marketplace-api/v2/offers:{action}
    # Prices in integer cents, body uses "requests" array
    # ------------------------------------------------------------------
    async def batch_create_offers_v2(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch list up to 100 items in a single request.

        Endpoint: POST /marketplace-api/v2/offers:batchCreate
        Body: {"requests": [{"assetId": "...", "priceCents": 12345}, ...]}
        """
        requests = []
        for o in offers:
            requests.append(
                {
                    "assetId": o["asset_id"],
                    "priceCents": int(round(o["price_usd"] * 100)),
                }
            )
        return await self.make_request(
            "POST",
            "/marketplace-api/v2/offers:batchCreate",
            body={"requests": requests},
        )

    async def batch_edit_offers_v2(self, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch reprice up to 100 offers in a single request.

        Endpoint: POST /marketplace-api/v2/offers:batchUpdate
        Body: {"requests": [{"offerId": "...", "priceCents": 12345}, ...]}
        """
        requests = []
        for e in edits:
            requests.append(
                {
                    "offerId": e["offer_id"],
                    "priceCents": int(round(e["new_price_usd"] * 100)),
                }
            )
        return await self.make_request(
            "POST",
            "/marketplace-api/v2/offers:batchUpdate",
            body={"requests": requests},
        )

    async def batch_delete_offers_v2(self, offer_ids: List[str]) -> Dict[str, Any]:
        """
        v2: Batch cancel (delist) up to 100 offers in a single request.

        Endpoint: POST /marketplace-api/v2/offers:batchDelete
        Body: {"requests": [{"offerId": "..."}, ...]}
        """
        requests = [{"offerId": oid} for oid in offer_ids]
        return await self.make_request(
            "POST",
            "/marketplace-api/v2/offers:batchDelete",
            body={"requests": requests},
        )

    async def get_user_closed_offers(
        self,
        game_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch closed (sold/reverted/trade_protected) offers.

        Endpoint: GET /marketplace-api/v1/user-offers/closed
        Params: gameId, limit, cursor, status (optional filter)
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-offers/closed", params=params
        )

    async def create_sell_offers_batch(
        self, game_id: str, payload: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Alias for batch_create_offers_v2 with item_id → asset_id key mapping.
        Used by resale.py _prod_list_unlocked.

        payload: [{"item_id": str, "price_usd": float}, ...]
        """
        offers = [
            {"asset_id": p["item_id"], "price_usd": p["price_usd"]}
            for p in payload
        ]
        return await self.batch_create_offers_v2(offers)

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
