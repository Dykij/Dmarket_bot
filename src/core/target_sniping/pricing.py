"""
pricing.py — Float premium + low-fee cache refresh.

Mixin with the pricing-related helpers used by the sniping loop.
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


class _PricingMixin:
    """Float premium + low-fee cache helpers."""

    # ------------------------------------------------------------------
    # v12.0 Phase 1.2: Float Premium
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_float_premium(attrs: Dict[str, Any]) -> float:
        """
        Returns a price multiplier based on item's float value.

        Float ranges (CS2):
        - FN-0: 0.00 - 0.01  (best) → 1.20x
        - FN:   0.00 - 0.07   → 1.10x
        - MW:   0.07 - 0.15   → 1.00x
        - FT-0: 0.15 - 0.18   → 1.15x
        - FT:   0.15 - 0.38   → 1.00x
        - WW:   0.38 - 0.45   → 0.95x
        - BS:   0.45 - 1.00   → 0.90x

        Returns 1.0 (no premium) if float not available.
        """
        try:
            float_str = attrs.get("floatPartValue")
            if not float_str:
                return 1.0
            float_val = float(float_str)
        except (ValueError, TypeError):
            return 1.0

        if float_val < 0.01:
            return 1.20  # FN-0
        if float_val < 0.07:
            return 1.10  # FN
        if 0.15 <= float_val <= 0.18:
            return 1.15  # FT-0
        if 0.38 <= float_val < 0.45:
            return 0.95  # WW
        if float_val >= 0.45:
            return 0.90  # BS
        return 1.0  # MW / regular FT

    # ------------------------------------------------------------------
    # v12.0 Phase 1.1: Low-fee cache
    # ------------------------------------------------------------------
    async def _refresh_low_fee_cache(self, game_id: str) -> None:
        """Refresh the low-fee items cache from DMarket (24h TTL)."""
        age = price_db.low_fee_cache_age_seconds()
        if age is not None and age < 86400:
            return  # Fresh enough
        try:
            await self._simulate_network_latency()
            self._maybe_inject_error("get_low_fee_items")
            items = await self.client.get_low_fee_items(game_id)
            if items:
                price_db.save_low_fee_items(items)
                logger.info(f"[LOW-FEE] Cached {len(items)} low-fee items (refreshed)")
        except Exception as e:
            logger.debug(f"Low-fee cache refresh failed: {e}")
