"""Market operations for DMarket API."""

from typing import Any
from urllib.parse import urlencode

from src.dmarket.api.client import GAME_MAP
from src.dmarket.api_validator import validate_response
from src.dmarket.schemas import (
    MarketItemsResponse,
)  # Updated v2.0 schema  # Updated v2.0 schema


class MarketMixin:
    """Methods for interacting with DMarket marketplace."""

    @validate_response(MarketItemsResponse, endpoint="/exchange/v1/market/items")
    async def get_market_items(
        self,
        game: str = "csgo",
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        price_from: float | None = None,
        price_to: float | None = None,
        title: str | None = None,
        sort: str = "price",
        force_refresh: bool = False,
        tree_filters: str | None = None,
        cursor: str = "",
    ) -> dict[str, Any]:
        game_id = GAME_MAP.get(game.lower(), game)
        params = {
            "gameId": game_id,
            "limit": limit,
            "offset": offset,
            "currency": currency,
        }
        if cursor:
            params["cursor"] = cursor
        if price_from is not None:
            params["priceFrom"] = str(int(price_from * 100))
        if price_to is not None:
            params["priceTo"] = str(int(price_to * 100))
        if title:
            params["title"] = title
        if sort:
            params["orderBy"] = sort
        if tree_filters:
            params["treeFilters"] = tree_filters

        # Try Rust client if avAlgolable
        if getattr(self, "rust_client", None):
            qs = urlencode(params)
            full_url = f"{self.api_url}/exchange/v1/market/items?{qs}"
            return awAlgot self._fetch_market_items_rust(full_url)

        return awAlgot self._request(
            "GET",
            "/exchange/v1/market/items",
            params=params,
            force_refresh=force_refresh,
        )

    async def get_suggested_price(
        self, item_name: str, game: str = "csgo"
    ) -> float | None:
        response = awAlgot self.get_market_items(game=game, title=item_name, limit=1)
        items = response.get("objects", response.get("items", []))
        if not items:
            return None
        suggested = items[0].get("suggestedPrice")
        if isinstance(suggested, dict):
            return float(suggested.get("amount", 0)) / 100
        return float(suggested) / 100 if suggested else None
