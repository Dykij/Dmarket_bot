"""Extended operations for DMarket API."""

import logging
from typing import TYPE_CHECKING, Any

from src.dmarket.api_validator import validate_response
from src.dmarket.schemas import (
    AggregatedPricesResponse,
    BuyOffersResponse,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

class ExtendedMixin:
    """Extra methods for DMarket API v1.1.0 compliance."""

    async def get_user_profile(self) -> dict[str, Any]:
        return await self._request("GET", "/account/v1/user")

    async def deposit_assets(self, asset_ids: list[str]) -> dict[str, Any]:
        return await self._request("POST", "/marketplace-api/v1/deposit-assets", data={"AssetID": asset_ids})

    async def get_deposit_status(self, deposit_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/marketplace-api/v1/deposit-status/{deposit_id}")

    async def withdraw_assets(self, asset_ids: list[str]) -> dict[str, Any]:
        return await self._request("POST", "/exchange/v1/withdraw-assets", data={"AssetIDs": asset_ids})

    async def get_sales_history(self, game: str, title: str, days: int = 7) -> dict[str, Any]:
        params = {"gameId": game, "title": title, "days": days, "currency": "USD"}
        return await self._request("GET", "/account/v1/sales-history", params=params)

    async def get_item_price_history(self, game: str, title: str, period: str = "last_month") -> dict[str, Any]:
        params = {"gameId": game, "title": title, "period": period, "currency": "USD"}
        return await self._request("GET", "/exchange/v1/market/price-history", params=params)

    async def list_market_items(self, game_id: str = "a8db", limit: int = 100, offset: int = 0, order_by: str = "best_deal", order_dir: str = "desc", price_from: int | None = None, price_to: int | None = None, title: str | None = None) -> dict[str, Any]:
        params = {"GameID": game_id, "Limit": str(limit), "Offset": str(offset), "OrderBy": order_by, "OrderDir": order_dir}
        if price_from is not None: params["PriceFrom"] = str(price_from)
        if price_to is not None: params["PriceTo"] = str(price_to)
        if title: params["Title"] = title
        return await self._request("GET", "/marketplace-api/v1/market-items", params=params)

    @validate_response(BuyOffersResponse, endpoint="/exchange/v1/offers-buy")
    async def buy_offers(self, offers: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._request("PATCH", "/exchange/v1/offers-buy", data={"offers": offers})

    @validate_response(AggregatedPricesResponse, endpoint="/marketplace-api/v1/aggregated-prices")
    async def get_aggregated_prices_bulk(self, game: str, titles: list[str], limit: int = 100, cursor: str = "") -> dict[str, Any]:
        data = {"filter": {"game": game, "titles": titles}, "limit": str(limit), "cursor": cursor}
        return await self._request("POST", "/marketplace-api/v1/aggregated-prices", data=data)

    async def get_market_best_offers(self, game: str = "csgo", title: str | None = None, limit: int = 50) -> dict[str, Any]:
        params = {"gameId": game, "limit": limit, "currency": "USD"}
        if title: params["title"] = title
        return await self._request("GET", "/exchange/v1/market/best-offers", params=params)

    async def edit_offer(self, offer_id: str, price: float) -> dict[str, Any]:
        data = {"offerId": offer_id, "price": {"amount": int(price * 100), "currency": "USD"}}
        return await self._request("POST", "/exchange/v1/user/offers/edit", data=data)

    async def delete_offer(self, offer_id: str) -> dict[str, Any]:
        return await self._request("DELETE", "/exchange/v1/user/offers/delete", data={"offers": [offer_id]})

    async def get_active_offers(self, game: str = "csgo", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        params = {"gameId": game, "limit": limit, "offset": offset, "status": "active"}
        return await self._request("GET", "/api/v1/account/offers", params=params)

    async def delete_targets(self, target_ids: list[str]) -> dict[str, Any]:
        data = {"Targets": [{"TargetID": tid} for tid in target_ids]}
        return await self._request("POST", "/marketplace-api/v1/user-targets/delete", data=data)

    async def get_targets_by_title(self, game_id: str, title: str) -> dict[str, Any]:
        from urllib.parse import quote
        return await self._request("GET", f"/marketplace-api/v1/targets-by-title/{game_id}/{quote(title)}")

    async def get_supported_games(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/game/v1/games")

    async def list_user_inventory(self, game_id: str = "a8db", limit: int = 100, offset: int = 0) -> dict[str, Any]:
        params = {"GameID": game_id, "Limit": str(limit), "Offset": str(offset)}
        return await self._request("GET", "/marketplace-api/v1/user-inventory", params=params)

    async def list_market_items_alt(self, game_id: str = "a8db", limit: int = 100) -> dict[str, Any]:
        params = {"GameID": game_id, "Limit": str(limit)}
        return await self._request("GET", "/marketplace-api/v1/market-items", params=params)

    async def get_buy_orders_competition(self, game_id: str, title: str) -> dict[str, Any]:
        # Implementation moved to specialized mixin or simplified here
        return await self.get_targets_by_title(game_id, title)
