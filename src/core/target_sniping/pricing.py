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
    """Float premium + low-fee cache helpers + pattern/phase premium."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...
    def _maybe_inject_error(self, method_name: str) -> None: ...

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
    # v13.0 Phase 1.3: Pattern / Phase Premium
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_pattern_premium(attrs: Dict[str, Any]) -> float:
        """
        Returns a price multiplier based on rare phases, patterns, and paint seeds.

        Known premium patterns (CS2):
        - Doppler Phase 2 / Phase 4 → 1.05-1.15x
        - Doppler Ruby → 2.0x+, Sapphire → 3.0x+, Emerald → 1.5x+
        - Gamma Doppler Phase 2 → 1.05x
        - Low paintSeed (<10) on some patterns → 1.02-1.05x (corner/webbing)

        Returns 1.0 (no premium) if no rare attributes detected.
        """
        try:
            phase = attrs.get("phase", "")
            paint_seed_str = attrs.get("paintSeed", "0")
            paint_seed = int(paint_seed_str)
        except (ValueError, TypeError):
            phase = ""
            paint_seed = 0

        multiplier = 1.0

        # Doppler phase premium
        if phase in ("Ruby", "ruby"):
            multiplier = 2.0
        elif phase in ("Sapphire", "sapphire"):
            multiplier = 3.0
        elif phase in ("Black Pearl", "blackpearl", "black_pearl"):
            multiplier = 1.5
        elif phase in ("Emerald", "emerald"):
            multiplier = 1.5
        elif phase in ("Phase 2", "phase2", "P2"):
            multiplier = 1.10
        elif phase in ("Phase 4", "phase4", "P4"):
            multiplier = 1.05
        elif phase in ("Phase 1", "phase1", "P1"):
            multiplier = 1.02
        elif phase in ("Phase 3", "phase3", "P3"):
            multiplier = 1.0

        # Rare paint seeds (e.g., pattern 661, 955, 151 for web/triangle patterns)
        if not multiplier > 1.0 and paint_seed in (661, 955, 151, 321, 268, 131, 202, 760, 437, 569):
            multiplier = 1.05

        # Very low paint seed (clean corners on some knives)
        if not multiplier > 1.0 and 0 < paint_seed < 5:
            multiplier = 1.03

        return multiplier

    @staticmethod
    def has_rare_phase_or_pattern(attrs: Dict[str, Any]) -> bool:
        """Check if item has rare phase or pattern worth exclusive keeping."""
        try:
            phase = attrs.get("phase", "")
            paint_seed_str = attrs.get("paintSeed", "0")
            paint_seed = int(paint_seed_str)
        except (ValueError, TypeError):
            return False
        rare_phases = ("Ruby", "Sapphire", "Black Pearl", "Emerald", "Phase 2", "Phase 4")
        rare_seeds = (661, 955, 151, 321, 268, 131, 202, 760, 437, 569)
        return phase in rare_phases or paint_seed in rare_seeds

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
