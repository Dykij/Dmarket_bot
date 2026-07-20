"""
dynamic_fee.py — Dynamic fee discovery from DMarket API.

Replaces the hardcoded 0.05 (5%) fee with real-time fee data from DMarket.
Falls back to configurable defaults when API is unavailable.

Usage:
    from src.risk.dynamic_fee import fee_manager

    # Get fee for an item
    sell_fee = await fee_manager.get_sell_fee(item_id, price_usd)
    buy_fee = await fee_manager.get_buy_fee(item_id, price_usd)

    # Get combined fee for profit calculation
    total_fee = await fee_manager.get_total_fee(buy_price, sell_price)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("DynamicFee")


@dataclass
class FeeStructure:
    """Fee structure for a specific price range."""

    min_price: float = 0.0
    max_price: float = float("inf")
    sell_fee_pct: float = 5.0  # DMarket sell fee percentage
    buy_fee_pct: float = 0.0   # DMarket buy fee (usually 0)
    withdrawal_fee_pct: float = 0.5  # Withdrawal fee


@dataclass
class FeeCacheEntry:
    """Cached fee data."""

    fee_pct: float
    cached_at: float
    ttl: float = 3600.0  # 1 hour default TTL

    @property
    def is_expired(self) -> bool:
        return time.time() - self.cached_at > self.ttl


class DynamicFeeManager:
    """Dynamic fee discovery with caching and fallbacks."""

    # DMarket fee tiers (as of 2026 — update as needed)
    # These are the known fee ranges; API may return more granular data
    DEFAULT_FEE_TIERS = [
        FeeStructure(min_price=0.0, max_price=1.0, sell_fee_pct=10.0),
        FeeStructure(min_price=1.0, max_price=10.0, sell_fee_pct=5.0),
        FeeStructure(min_price=10.0, max_price=100.0, sell_fee_pct=5.0),
        FeeStructure(min_price=100.0, max_price=1000.0, sell_fee_pct=5.0),
        FeeStructure(min_price=1000.0, max_price=float("inf"), sell_fee_pct=5.0),
    ]

    def __init__(self) -> None:
        self._cache: dict[str, FeeCacheEntry] = {}
        self._fee_tiers: list[FeeStructure] = list(self.DEFAULT_FEE_TIERS)
        self._last_api_check: float = 0.0
        self._api_check_interval: float = 3600.0  # Check API every hour

    def _get_fee_for_price(self, price_usd: float) -> FeeStructure:
        """Get fee tier for a given price."""
        for tier in self._fee_tiers:
            if tier.min_price <= price_usd < tier.max_price:
                return tier
        # Default fallback
        return FeeStructure()

    async def get_sell_fee(
        self,
        item_id: str = "",
        price_usd: float = 0.0,
        force_refresh: bool = False,
    ) -> float:
        """Get sell fee percentage for an item.

        Args:
            item_id: DMarket item ID (for caching).
            price_usd: Item price in USD (for tier lookup).
            force_refresh: Force API refresh.

        Returns:
            Sell fee as decimal (e.g., 0.05 for 5%).
        """
        # Check cache first
        cache_key = f"sell_{item_id}" if item_id else f"sell_price_{price_usd:.2f}"
        if not force_refresh and cache_key in self._cache:
            entry = self._cache[cache_key]
            if not entry.is_expired:
                return entry.fee_pct / 100.0

        # Try API refresh
        fee_pct = await self._fetch_fee_from_api(item_id, price_usd)

        if fee_pct is None:
            # Fallback to tier-based lookup
            tier = self._get_fee_for_price(price_usd)
            fee_pct = tier.sell_fee_pct
            logger.debug(
                f"[DynamicFee] Using tier fallback for ${price_usd:.2f}: {fee_pct}%"
            )

        # Cache the result
        self._cache[cache_key] = FeeCacheEntry(
            fee_pct=fee_pct,
            cached_at=time.time(),
        )

        return fee_pct / 100.0

    async def get_buy_fee(
        self,
        item_id: str = "",
        price_usd: float = 0.0,
    ) -> float:
        """Get buy fee percentage (usually 0 for DMarket)."""
        return 0.0  # DMarket doesn't charge buy fees

    async def get_total_fee(
        self,
        buy_price: float,
        sell_price: float,
        item_id: str = "",
    ) -> float:
        """Get total fee for a buy-sell cycle.

        Returns:
            Total fee as decimal (e.g., 0.055 for 5.5% combined).
        """
        sell_fee = await self.get_sell_fee(item_id, sell_price)
        buy_fee = await self.get_buy_fee(item_id, buy_price)
        return sell_fee + buy_fee

    async def _fetch_fee_from_api(
        self,
        item_id: str,
        price_usd: float,
    ) -> float | None:
        """Try to fetch fee from DMarket API.

        Returns:
            Fee percentage or None if unavailable.
        """
        # Rate limit API checks
        now = time.time()
        if now - self._last_api_check < self._api_check_interval:
            return None

        self._last_api_check = now

        try:
            from src.api.dmarket_api_client.core import dmarket_api

            # Try to get fee info from DMarket API
            # This is a best-effort attempt — if the endpoint doesn't exist,
            # we fall back to tier-based lookup
            if hasattr(dmarket_api, "get_item_fee"):
                fee = await dmarket_api.get_item_fee(item_id)
                if fee is not None and 0 < fee < 1:
                    logger.info(f"[DynamicFee] API fee for {item_id}: {fee*100:.2f}%")
                    return fee * 100.0

        except Exception as e:
            logger.debug(f"[DynamicFee] API fetch failed: {e}")

        return None

    def update_fee_tiers(self, tiers: list[dict[str, Any]]) -> None:
        """Update fee tiers from external source (e.g., config file).

        Args:
            tiers: List of dicts with keys: min_price, max_price, sell_fee_pct
        """
        new_tiers = []
        for tier in tiers:
            new_tiers.append(FeeStructure(
                min_price=tier.get("min_price", 0.0),
                max_price=tier.get("max_price", float("inf")),
                sell_fee_pct=tier.get("sell_fee_pct", 5.0),
                buy_fee_pct=tier.get("buy_fee_pct", 0.0),
                withdrawal_fee_pct=tier.get("withdrawal_fee_pct", 0.5),
            ))
        if new_tiers:
            self._fee_tiers = new_tiers
            logger.info(f"[DynamicFee] Updated {len(new_tiers)} fee tiers")

    def clear_cache(self) -> None:
        """Clear the fee cache."""
        self._cache.clear()
        logger.info("[DynamicFee] Cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get fee manager statistics."""
        return {
            "cached_entries": len(self._cache),
            "fee_tiers": len(self._fee_tiers),
            "last_api_check": self._last_api_check,
            "default_sell_fee": self._fee_tiers[0].sell_fee_pct if self._fee_tiers else 5.0,
        }


# Global singleton
fee_manager = DynamicFeeManager()
