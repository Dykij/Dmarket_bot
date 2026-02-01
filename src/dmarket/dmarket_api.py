"""Modular DMarket API client for 2026."""

from typing import Any, TYPE_CHECKING
import logging
import time
from src.dmarket.api.client import BaseDMarketClient, api_cache, CACHE_TTL, GAME_MAP
from src.dmarket.api.market import MarketMixin
from src.dmarket.api.wallet import WalletMixin
from src.dmarket.api.trading import TradingMixin
from src.dmarket.api.inventory import InventoryMixin
from src.dmarket.api.extended import ExtendedMixin

if TYPE_CHECKING:
    from src.telegram_bot.notifier import Notifier

logger = logging.getLogger(__name__)

class DMarketAPI(BaseDMarketClient, MarketMixin, WalletMixin, TradingMixin, InventoryMixin, ExtendedMixin):
    """Facade for DMarket API v1.1.0."""
    
    async def direct_balance_request(self) -> dict[str, Any]:
        """Direct balance request logic."""
        return await self._request("GET", "/account/v1/balance")

    async def get_user_targets(self, game_id: str, status: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        from src.dmarket.api.client import GAME_MAP
        mapped_game_id = GAME_MAP.get(game_id.lower(), game_id)
        params = {"GameID": mapped_game_id, "Limit": str(limit), "Offset": str(offset)}
        if status: params["BasicFilters.Status"] = status
        return await self._request("GET", "/marketplace-api/v1/user-targets", params=params)

    async def clear_cache(self) -> None:
        api_cache.clear()
        logger.info("API cache cleared")

    async def clear_cache_for_endpoint(self, endpoint_path: str) -> None:
        keys_to_remove = [k for k in api_cache if endpoint_path in k]
        for k in keys_to_remove: api_cache.pop(k, None)
        logger.info(f"Cleared {len(keys_to_remove)} cache entries for {endpoint_path}")

    async def __aenter__(self) -> "DMarketAPI":
        async with self._client_lock:
            self._client_ref_count += 1
            await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        async with self._client_lock:
            self._client_ref_count -= 1
            if self._client_ref_count <= 0:
                await self._close_client()
                self._client_ref_count = 0
