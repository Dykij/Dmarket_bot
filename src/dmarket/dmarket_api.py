"""Modular DMarket API client for 2026.

This is the v2 implementation of the DMarket Client, standardized according to SACS-2026.
It provides a unified interface for interacting with the DMarket API.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.dmarket.api.client import GAME_MAP, BaseDMarketClient, api_cache
from src.dmarket.api.extended import ExtendedMixin
from src.dmarket.api.inventory import InventoryMixin
from src.dmarket.api.market import MarketMixin
from src.dmarket.api.trading import TradingMixin
from src.dmarket.api.wallet import WalletMixin

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DMarketAPI(
    BaseDMarketClient,
    MarketMixin,
    WalletMixin,
    TradingMixin,
    InventoryMixin,
    ExtendedMixin,
):
    """Facade for DMarket API v2.0.0 (SACS-2026 standardized)."""

    VERSION = "2.0.0"

    async def direct_balance_request(self) -> Dict[str, Any]:
        """Direct balance request logic (v2 implementation)."""
        logger.info("Executing direct balance request (v2)")
        return await self._request("GET", "/account/v1/balance")

    async def get_user_targets(
        self,
        game_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Retrieve user targets with standardized filtering."""
        mapped_game_id = GAME_MAP.get(game_id.lower(), game_id)
        params = {
            "GameID": mapped_game_id,
            "Limit": str(limit),
            "Offset": str(offset),
        }
        if status:
            params["BasicFilters.Status"] = status

        logger.debug(f"Fetching user targets for game {mapped_game_id}")
        return await self._request(
            "GET", "/marketplace-api/v1/user-targets", params=params
        )

    async def get_sacs_compliance_status(self) -> Dict[str, str]:
        """Check compliance with SACS-2026 standards."""
        return {"status": "compliant", "version": self.VERSION, "standard": "SACS-2026"}

    async def clear_cache(self) -> None:
        """Clear the API cache."""
        api_cache.clear()
        logger.info("API cache cleared (v2)")

    async def clear_cache_for_endpoint(self, endpoint_path: str) -> None:
        """Clear specific cache entries."""
        keys_to_remove = [k for k in api_cache if endpoint_path in k]
        for k in keys_to_remove:
            api_cache.pop(k, None)
        logger.info(
            f"Cleared {len(keys_to_remove)} cache entries for {endpoint_path} (v2)"
        )

    async def __aenter__(self) -> "DMarketAPI":
        """Async context manager entry."""
        async with self._client_lock:
            self._client_ref_count += 1
            await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        async with self._client_lock:
            self._client_ref_count -= 1
            if self._client_ref_count <= 0:
                await self._close_client()
                self._client_ref_count = 0
