"""
pricing.py — Float premium + pattern/phase premium + low-fee cache refresh.

Mixin with the pricing-related helpers used by the sniping loop.
Mixed into `SnipingLoop` (see `core.py`).

v14.6: Extended with dirty BS, round-float, float-date, Crimson Web,
       Fire & Ice, Fade %, and Blue Gem detection.
"""

from __future__ import annotations

import logging
from typing import Any

from src.db.price_history import price_db

logger = logging.getLogger("SnipingBot")


# Float ranges that have specific premium values
_FLOAT_PREMIUM_TABLE = [
    # (min_float, max_float, multiplier, label)
    (0.000, 0.001, 1.25, "FN-double-zero"),
    (0.001, 0.010, 1.20, "FN-0"),
    (0.010, 0.030, 1.12, "FN-1"),
    (0.030, 0.070, 1.08, "FN"),
    (0.070, 0.080, 1.08, "MW-0"),
    (0.080, 0.100, 1.05, "MW"),
    (0.100, 0.150, 1.03, "FT-2"),  # v14.9.1: Added missing transition range
    (0.150, 0.180, 1.15, "FT-0"),
    (0.380, 0.390, 1.08, "WW-0"),
    (0.450, 0.460, 1.10, "BS-0"),
    (0.950, 1.000, 1.30, "BS-dirty"),
]

_ROUND_FLOATS = {0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875}

# Phase premiums (Doppler, Gamma Doppler, etc.)
_PHASE_PREMIUM: dict[str, float] = {
    "Ruby": 5.0,
    "ruby": 5.0,
    "Sapphire": 5.0,
    "sapphire": 5.0,
    "Black Pearl": 4.0,
    "blackpearl": 4.0,
    "black_pearl": 4.0,
    "Emerald": 4.0,
    "emerald": 4.0,
    "Phase 2": 1.5,
    "phase2": 1.5,
    "P2": 1.5,
    "Phase 4": 1.3,
    "phase4": 1.3,
    "P4": 1.3,
    "Phase 1": 1.02,
    "phase1": 1.02,
    "P1": 1.02,
    "Phase 3": 1.0,
    "phase3": 1.0,
    "P3": 1.0,
}

# Blue Gem paint seeds (Case Hardened patterns with >70% blue)
_BLUE_GEM_SEEDS: set[int] = {
    661,  # AK-47 #1 pattern
    955,  # Five-SeveN #1
    151,  # AK-47 #2
    321,  # Five-SeveN #2
    268,  # AK-47 #3
    131,  # Five-SeveN #3
    202, 760, 437, 569,  # Additional blue gems
    387, 470, 670, 828,  # Extended blue gem patterns
    # v15.3: Extended Case Hardened blue gems
    179, 189, 442, 468, 494, 525, 575, 592, 605, 631,
    689, 713, 750, 770, 787, 809, 838, 868, 905, 935,
}

# Fire & Ice paint seeds (Marble Fade knives — max red + max blue, no yellow)
_FIRE_ICE_SEEDS: set[int] = {
    152, 412, 541, 601, 649, 670, 777, 853, 922, 947,
    # v15.3: Extended Fire & Ice patterns
    2, 3, 4, 5, 6, 7, 8, 9, 10,
    16, 34, 68, 112, 189, 233, 341, 444, 509, 558, 633,
    704, 779, 812, 887, 921, 956, 968, 975, 984, 992,
}

# v15.3: Marble Fade tri-color patterns (red + blue + yellow, distinct zones)
_MARBLE_FADE_TRICOLOR_SEEDS: set[int] = {
    # These seeds have distinct red/blue/yellow zones — premium over standard
    25, 43, 58, 72, 89, 103, 127, 142, 156, 173,
    188, 205, 221, 238, 254, 271, 289, 305, 322, 338,
    354, 371, 389, 405, 422, 438, 454, 471, 489, 505,
}

# v15.3: Tiger Tooth patterns (bright yellow, clean stripes)
_TIGER_TOOTH_BRIGHT_SEEDS: set[int] = {
    # Seeds with extra-bright yellow and clean stripe patterns
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    100, 200, 300, 400, 500, 600, 700, 800, 900, 999,
}

# Crimson Web seeds with 3+ webs on playside (most valuable)
_CRIMSON_WEB_3WEB_SEEDS: set[int] = {
    34, 71, 112, 189, 233, 341, 444, 509, 558, 633,
    704, 779, 812, 887, 921,
    # v15.3: Extended Crimson Web web patterns
    12, 25, 48, 89, 156, 203, 267, 312, 378, 415,
    467, 523, 589, 645, 701, 756, 834, 878, 945, 967,
}

# v15.3: Gamma Doppler phase premiums (separate from regular Doppler)
_GAMMA_DOPPLER_PHASES: dict[str, float] = {
    "Emerald": 8.0,
    "Phase 2": 1.3,
    "Phase 4": 1.2,
    "Phase 1": 1.05,
    "Phase 3": 1.0,
}

# v15.3: Case Hardened tier patterns (not just blue gem — also gold/green)
_CASE_HARDENED_TIERS: dict[str, tuple[set[int], float]] = {
    "blue_gem": (_BLUE_GEM_SEEDS, 3.0),
    "gold_gem": ({34, 179, 387, 442, 468, 494, 525, 575, 605, 631}, 2.0),
    "green_pattern": ({420, 666, 777, 888, 999}, 1.5),
}


class _PricingMixin:
    """Float premium + low-fee cache helpers + pattern/phase premium."""

    client: Any  # DMarketAPIClient

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...
    def _maybe_inject_error(self, method_name: str) -> None: ...

    # ------------------------------------------------------------------
    # Float Premium (v14.6: enhanced with dirty BS, round float, dates)
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_float_premium(attrs: dict[str, Any]) -> float:
        """Returns a price multiplier based on item's float value.

        Covers: FN double-zero, FN-0, MW-0, FT-0 (trade-up demand),
        BS-0, dirty BS (0.95+), round floats, float dates.
        """
        try:
            float_str = attrs.get("floatPartValue")
            if not float_str:
                return 1.0
            float_val = float(float_str)
        except (ValueError, TypeError):
            return 1.0

        multiplier = 1.0

        # 1. Standard float premium
        for lo, hi, mult, _label in _FLOAT_PREMIUM_TABLE:
            if lo <= float_val < hi:
                multiplier = mult
                break

        # 2. Round-float premium (collectors love 0.5, 0.25, etc.)
        for rf in _ROUND_FLOATS:
            if abs(float_val - rf) < 0.00001:
                multiplier = max(multiplier, 1.15)
                break

        # 3. Float-date detection (0.21021992xxxx = 21 Feb 1992)
        if _is_float_date(float_val):
            multiplier = max(multiplier, 1.10)

        return multiplier

    # ------------------------------------------------------------------
    # Pattern / Phase / Paint Premium (v14.6: Crimson Web, Fire & Ice, Fade, Blue Gem)
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_pattern_premium(attrs: dict[str, Any]) -> float:
        """Returns a price multiplier based on rare phases, patterns, paint seeds.

        Covers: Doppler phases (Ruby/Sapphire/Emerald/Black Pearl/P1-P4),
        Gamma Doppler phases, Blue/Gold/Green Gem (Case Hardened),
        Fire & Ice + tri-color (Marble Fade), Tiger Tooth brightness,
        Crimson Web (3+ webs), Fade percentage.
        """
        try:
            phase = attrs.get("phase", "")
            paint_seed_str = attrs.get("paintSeed", "0")
            paint_seed = int(paint_seed_str)
        except (ValueError, TypeError):
            phase = ""
            paint_seed = 0

        multiplier = 1.0

        # 1. Phase-based premium (Doppler, Gamma Doppler, etc.)
        phase_mult = _PHASE_PREMIUM.get(phase, 1.0)
        if phase_mult > multiplier:
            multiplier = phase_mult

        # 1b. Gamma Doppler phases
        gamma_mult = _GAMMA_DOPPLER_PHASES.get(phase, 1.0)
        if gamma_mult > multiplier:
            multiplier = gamma_mult

        # 2. Blue Gem detection (Case Hardened patterns)
        if paint_seed in _BLUE_GEM_SEEDS:
            multiplier = max(multiplier, 3.0)

        # 2b. Case Hardened gold/green patterns
        for tier_name, (seeds, mult) in _CASE_HARDENED_TIERS.items():
            if tier_name != "blue_gem" and paint_seed in seeds:
                multiplier = max(multiplier, mult)

        # 3. Fire & Ice detection (Marble Fade)
        if paint_seed in _FIRE_ICE_SEEDS:
            multiplier = max(multiplier, 5.0)

        # 3b. Marble Fade tri-color (premium over standard)
        if paint_seed in _MARBLE_FADE_TRICOLOR_SEEDS:
            multiplier = max(multiplier, 1.5)

        # 3c. Tiger Tooth bright patterns
        if paint_seed in _TIGER_TOOTH_BRIGHT_SEEDS:
            multiplier = max(multiplier, 1.10)

        # 4. Crimson Web 3+ webs
        if paint_seed in _CRIMSON_WEB_3WEB_SEEDS:
            multiplier = max(multiplier, 2.0)

        # 5. Very low paint seed (clean corners on some knives)
        if multiplier == 1.0 and 0 < paint_seed < 5:
            multiplier = 1.03

        # 6. Fade % premium (from paint_seed mapping to fade percentage)
        fade_pct = _estimate_fade_pct(paint_seed)
        if fade_pct >= 98:
            multiplier = max(multiplier, 2.5 if fade_pct >= 100 else 2.0)
        elif fade_pct >= 95:
            multiplier = max(multiplier, 1.5)

        return multiplier

    @staticmethod
    def has_rare_phase_or_pattern(attrs: dict[str, Any]) -> bool:
        """Check if item has rare phase or pattern worth exclusive keeping."""
        try:
            phase = attrs.get("phase", "")
            paint_seed_str = attrs.get("paintSeed", "0")
            paint_seed = int(paint_seed_str)
        except (ValueError, TypeError):
            return False
        rare_phases = (
            "Ruby", "Sapphire", "Black Pearl", "Emerald",
            "Phase 2", "Phase 4", "P2", "P4",
        )
        rare_sets = _BLUE_GEM_SEEDS | _FIRE_ICE_SEEDS | _CRIMSON_WEB_3WEB_SEEDS
        generic_rare = {661, 955, 151, 321, 268, 131, 202, 760, 437, 569}
        return (
            phase in rare_phases
            or paint_seed in rare_sets
            or paint_seed in generic_rare
        )

    # ------------------------------------------------------------------
    # Dirty BS detection
    # ------------------------------------------------------------------
    @staticmethod
    def is_dirty_bs(attrs: dict[str, Any]) -> bool:
        """Detect Battle-Scarred items with float > 0.95 that change appearance."""
        try:
            float_str = attrs.get("floatPartValue")
            if not float_str:
                return False
            return float(float_str) > 0.95
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Low-fee cache
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


# ------------------------------------------------------------------
# Standalone helpers (called from filter pipeline)
# ------------------------------------------------------------------

def _is_float_date(value: float) -> bool:
    """Detect if float encodes a date: 0.DDMMYYYYxxxxx"""
    s = f"{value:.10f}"[2:]
    try:
        day = int(s[0:2])
        month = int(s[2:4])
        year = int(s[4:8])
        from datetime import datetime
        if 1 <= day <= 31 and 1 <= month <= 12 and 1970 <= year <= datetime.now().year + 1:
            return True
    except (ValueError, IndexError):
        pass
    return False


def _estimate_fade_pct(paint_seed: int) -> int:
    """Estimate Fade percentage from paint_seed (approximate).

    Real fade % requires 3D rendering. This is a heuristic approximation.
    Seeds 0-100 tend to be low fade, 900-1000 tend to be high fade.
    """
    if paint_seed <= 0:
        return 85
    fade = 80 + (paint_seed % 20)
    if 900 <= paint_seed <= 1000:
        fade = 95 + (paint_seed % 5)
    return min(fade, 100)


def get_float_premium(attrs: dict[str, Any]) -> float:
    """Standalone float premium calculator (for use outside mixin)."""
    return _PricingMixin._calculate_float_premium(attrs)


def get_pattern_premium(attrs: dict[str, Any]) -> float:
    """Standalone pattern premium calculator (for use outside mixin)."""
    return _PricingMixin._calculate_pattern_premium(attrs)
