"""Arbitrage Scanner Engine."""

import logging
import os
from typing import TYPE_CHECKING, Any

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.scanner import ScannerCache, ScannerFilters

if TYPE_CHECKING:
    from src.dmarket.item_filters import ItemFilters
    from src.interfaces import IDMarketAPI

logger = logging.getLogger(__name__)

class ArbitrageScanner:
    """Core engine for scanning arbitrage opportunities."""

    def __init__(
        self,
        api_client: "IDMarketAPI | None" = None,
        enable_liquidity_filter: bool = True,
        enable_competition_filter: bool = True,
        max_competition: int = 3,
        item_filters: "ItemFilters | None" = None,
        enable_steam_check: bool = False,
        min_profit_percent: float | None = None,
    ) -> None:
        self.api_client = api_client
        self._scanner_cache = ScannerCache(ttl=300, max_size=1000)
        self._scanner_filters = ScannerFilters(item_filters)
        self._is_shutting_down = False
        self.liquidity_analyzer = None
        self.enable_liquidity_filter = enable_liquidity_filter
        self.enable_competition_filter = enable_competition_filter
        self.max_competition = max_competition
        self.min_liquidity_score = 60
        self.min_sales_per_week = 5
        self.min_profit = 0.5
        self.min_profit_percent = min_profit_percent
        self.max_price = 50.0
        self.max_trades = 5
        self.total_scans = 0
        self.total_items_found = 0

    async def get_api_client(self) -> DMarketAPI:
        if self.api_client is None:
            self.api_client = DMarketAPI(
                public_key=os.getenv("DMARKET_PUBLIC_KEY", ""),
                secret_key=os.getenv("DMARKET_SECRET_KEY", ""),
            )
        return self.api_client

    async def scan_game(self, game: str, mode: str = "medium", max_items: int = 20) -> list[dict[str, Any]]:
        # Simplified scan logic for now (actual logic to be restored/modularized)
        logger.info(f"Scanning {game} in {mode} mode")
        return []

    # ... other methods ...

async def check_user_balance(api_client):
    """Stub for balance check to prevent ImportErrors"""
    try:
        return await api_client.get_balance()
    except Exception:
        return None
