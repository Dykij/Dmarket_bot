"""
offers.py — Sell-side offers (single, batch, edit, delete, list).

Mixin with the offer-lifecycle endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

from typing import Any
from src.utils.units import usd_to_cents


class _OffersMixin:
    """Sell-side offer endpoints (create, edit, delete, list)."""

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    async def get_user_offers(
        self, game_id: str, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        """Fetches items the user currently has listed for sale.

        Endpoint: GET /exchange/v1/user-offers (per Swagger v1.1.0)
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await self.make_request(
            "GET", "/marketplace-api/v2/user/offers", params=params
        )
        if "items" in resp and "objects" not in resp:
            objects = []
            for item in resp["items"]:
                obj = dict(item)
                if "attributes" in item:
                    obj["title"] = item["attributes"].get("title", "")
                    obj["itemId"] = item["attributes"].get("id", "")
                if "priceCents" in item:
                    obj["price"] = {"USD": str(item["priceCents"])}
                objects.append(obj)
            resp["objects"] = objects
        return resp

    # ------------------------------------------------------------------
    # March 2026: Official v2 Batch Endpoints (Marketplace API v2)
    # Endpoint format: POST /marketplace-api/v2/offers:{action}
    # Prices in integer cents, body uses "requests" array
    # ------------------------------------------------------------------
    async def batch_create_offers_v2(self, offers: list[dict[str, Any]]) -> dict[str, Any]:
        """
        v2: Batch list up to 100 items in a single request.

        Endpoint: POST /marketplace-api/v2/offers:batchCreate
        Body: {"requests": [{"assetId": "...", "priceCents": 12345}, ...]}

        The spec (v2.0.0) has no idempotency key, so none is sent. A repeated
        listing of an already listed asset is rejected by the server (`failed[]`).
        """
        requests = []
        for o in offers:
            requests.append(
                {
                    "assetId": o["asset_id"],
                    "priceCents": usd_to_cents(o["price_usd"]),
                }
            )
        return await self.make_request(
            "POST",
            "/marketplace-api/v2/offers:batchCreate",
            body={"requests": requests},
        )

    async def batch_edit_offers_v2(self, edits: list[dict[str, Any]]) -> dict[str, Any]:
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
                    "priceCents": usd_to_cents(e["new_price_usd"]),
                }
            )
        return await self.make_request(
            "POST",
            "/marketplace-api/v2/offers:batchUpdate",
            body={"requests": requests},
        )

    async def batch_delete_offers_v2(self, offer_ids: list[str]) -> dict[str, Any]:
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
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch closed offers (one page): successful / reverted / trade_protected.

        Endpoint: GET /marketplace-api/v1/user-offers/closed
        Spec v2.0.0 params are PascalCase (`Limit`, `Cursor`); there is no
        `gameId` (the live response mixes all games; `game_id` is kept only for
        call compatibility). Live read 2026-11-15: lowercase `limit` was
        ignored; whether the server honours `Limit`/`Cursor` is NOT verified.

        Response (live): {"Trades": [...], "Total", "Cursor"}; Price.Amount is
        a number in DOLLARS; FinalizationTime/OfferClosedAt are Unix seconds
        as strings; Fee = {Amount{Amount}, Percent: "0.08"}.

        Returns a flat, unit-explicit shape: {"objects": [{offerId, assetId,
        title, status, price_usd, fee_usd | None, fee_percent | None,
        finalization_time, closed_at}], "cursor": str | None}.
        """
        params: dict[str, Any] = {"Limit": limit}
        if cursor:
            params["Cursor"] = cursor
        res = await self.make_request(
            "GET", "/marketplace-api/v1/user-offers/closed", params=params
        )
        res = res or {}

        def _num(v: Any) -> float | None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def _pick(d: Any, *keys: str) -> Any:
            if isinstance(d, dict):
                for k in keys:
                    if k in d:
                        return d[k]
            return None

        objects: list[dict[str, Any]] = []
        for t in res.get("Trades") or []:
            price = t.get("Price")
            currency = _pick(price, "Currency", "currency")
            price_usd = _num(_pick(price, "Amount", "amount")) if currency in (None, "", "USD") else None
            fee = t.get("Fee")
            fee_money = _pick(fee, "Amount", "amount")
            fee_usd = _num(_pick(fee_money, "Amount", "amount"))
            objects.append(
                {
                    "offerId": t.get("OfferID", ""),
                    "assetId": t.get("AssetID", ""),
                    "title": t.get("Title", ""),
                    "status": str(t.get("Status", "")).lower(),
                    "price_usd": price_usd or 0.0,
                    "fee_usd": fee_usd,
                    "fee_percent": _num(_pick(fee, "Percent", "percent")),
                    "finalization_time": _num(t.get("FinalizationTime")) or 0.0,
                    "closed_at": _num(t.get("OfferClosedAt")) or 0.0,
                }
            )
        return {"objects": objects, "cursor": res.get("Cursor") or None}

    async def create_sell_offers_batch(
        self, game_id: str, payload: list[dict[str, Any]]
    ) -> dict[str, Any]:
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
        cursor: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        v2: List active offers.

        Endpoint: GET /marketplace-api/v2/user/offers
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status and status != "active":
            pass # /marketplace-api/v2/user/offers implicitly returns active offers
        resp = await self.make_request("GET", "/marketplace-api/v2/user/offers", params=params)
        if "items" in resp and "objects" not in resp:
            objects = []
            for item in resp["items"]:
                obj = dict(item)
                if "attributes" in item:
                    obj["title"] = item["attributes"].get("title", "")
                    obj["itemId"] = item["attributes"].get("id", "")
                if "priceCents" in item:
                    obj["price"] = {"USD": str(item["priceCents"])}
                objects.append(obj)
            resp["objects"] = objects
        return resp
