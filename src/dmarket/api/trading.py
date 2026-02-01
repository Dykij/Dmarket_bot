"""Trading operations for DMarket API."""

from typing import Any
import logging

logger = logging.getLogger(__name__)

class TradingMixin:
    """Methods for buying, selling and target management."""

    async def buy_item(self, item_id: str, price: float, game: str = "csgo") -> dict[str, Any]:
        if self.dry_run:
            logger.info(f"[DRY-RUN] Simulated buy: {item_id} @ ${price}")
            return {"success": True, "dry_run": True, "message": "Simulated purchase"}
        
        data = {
            "itemId": item_id,
            "price": {"amount": int(price * 100), "currency": "USD"},
            "gameType": game
        }
        return await self._request("POST", "/exchange/v1/market/items/buy", data=data)

    async def sell_item(self, item_id: str, price: float) -> dict[str, Any]:
        if self.dry_run:
            logger.info(f"[DRY-RUN] Simulated sell: {item_id} @ ${price}")
            return {"success": True, "dry_run": True}
        
        data = {
            "itemId": item_id,
            "price": {"amount": int(price * 100), "currency": "USD"}
        }
        return await self._request("POST", "/exchange/v1/user/inventory/sell", data=data)

    async def create_targets(self, game_id: str, targets: list[dict[str, Any]]) -> dict[str, Any]:
        data = {"GameID": game_id, "Targets": targets}
        return await self._request("POST", "/marketplace-api/v1/user-targets/create", data=data)
