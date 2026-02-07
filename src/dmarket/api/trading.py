"""Trading operations for DMarket API."""

from typing import Any
import logging
from .exceptions import InsufficientFundsError

logger = logging.getLogger(__name__)

class TradingMixin:
    """Methods for buying, selling and target management."""

    async def buy_item(self, item_id: str, price: float, game: str = "csgo") -> dict[str, Any]:
        """Buy item with balance safety check."""
        # Safety Check: Get current balance before purchase
        balance_info = await self.get_balance()
        available = balance_info.available_balance if hasattr(balance_info, 'available_balance') else 0.0
        
        if price > available:
            logger.error(f"Purchase blocked: price ${price:.2f} > available ${available:.2f}")
            raise InsufficientFundsError(required=price, available=available)

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
