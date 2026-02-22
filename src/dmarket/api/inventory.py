"""Inventory and offer management for DMarket API."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InventoryMixin:
    """Methods for managing user inventory and trade offers."""

    async def get_user_inventory(
        self, game_id: str = "a8db99ca-dc45-4c0e-9989-11ba71ed97a2", limit: int = 100
    ) -> dict[str, Any]:
        params = {"GameID": game_id, "Limit": str(limit), "Offset": "0"}
        return await self._request(
            "GET", "/marketplace-api/v1/user-inventory", params=params
        )

    async def list_user_offers(
        self,
        game_id: str = "a8db",
        status: str = "OfferStatusActive",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        params = {
            "GameID": game_id,
            "Status": status,
            "Limit": str(limit),
            "Offset": str(offset),
        }
        return await self._request(
            "GET", "/marketplace-api/v1/user-offers", params=params
        )

    async def create_offers(self, offers: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._request(
            "POST", "/marketplace-api/v1/user-offers/create", data={"Offers": offers}
        )

    async def remove_offers(self, offer_ids: list[str]) -> dict[str, Any]:
        data = {"Offers": [{"OfferID": oid} for oid in offer_ids]}
        return await self._request(
            "POST", "/marketplace-api/v1/user-offers/delete", data=data
        )

    async def list_market_items(
        self,
        game_id: str = "a8db",
        limit: int = 100,
        offset: int = 0,
        order_by: str = "best_deal",
        order_dir: str = "desc",
        price_from: int | None = None,
        price_to: int | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "GameID": game_id,
            "Limit": str(limit),
            "Offset": str(offset),
            "OrderBy": order_by,
            "OrderDir": order_dir,
        }
        if price_from is not None:
            params["PriceFrom"] = str(price_from)
        if price_to is not None:
            params["PriceTo"] = str(price_to)
        if title:
            params["Title"] = title
        return await self._request(
            "GET", "/marketplace-api/v1/market-items", params=params
        )

    async def sync_inventory(self, game_id: str = "a8db") -> dict[str, Any]:
        return await self._request(
            "POST", "/marketplace-api/v1/user-inventory/sync", data={"GameID": game_id}
        )
