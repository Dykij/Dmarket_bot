"""
sticker_cache.py — Luxury sticker rejection + mid-range sticker premium cache.

v15.10: Two-tier sticker strategy:
  1. REJECT items with ultra-premium stickers (Katowice 2014, Crown Foil, etc.)
     — these are investment pieces, not trading targets; price is dominated by
     sticker value which is illiquid and hard to realize.
  2. BOOST items with mid-range stickers (Souvenir Major, Team Holo 2015-2023)
     — these carry measurable premium that the market pays for.

Integrates with existing StickerEvaluator (src/analytics/stickers_evaluator.py)
which handles USD value calculation; this module adds the filter/rank layer.

Usage:
    cache = StickerPremiumCache()
    if cache.should_reject_by_stickers(stickers):
        return None  # skip luxury items
    multiplier = cache.calculate_premium_multiplier(stickers, base_price)
    boost = cache.get_ranking_boost(stickers)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("SnipingBot")


# ═══════════════════════════════════════════════════════════════════════
# LEVEL 1: LUXURY BLACKLIST — reject these items entirely
# These stickers dominate item price, making spread trading unprofitable.
# ═══════════════════════════════════════════════════════════════════════

_LUXURY_KEYWORDS: set[str] = {
    "Katowice 2014",
    "iBUYPOWER",
    "Titan | Katowice",
    "Reason Gaming",
    "Crown (Foil)",
    "Howl",
    "Dignitas | Katowice 2014",
    "Virtus.pro (Holo) | Katowice 2014",
    "Natus Vincere (Holo) | Katowice 2014",
    "Fnatic (Holo) | Katowice 2014",
    "LGB eSports (Holo) | Katowice 2014",
    "compLexity Gaming (Holo) | Katowice 2014",
    "Clan-Mystik (Holo) | Katowice 2014",
    "HellRaisers (Holo) | Katowice 2014",
    "3DMAX (Holo) | Katowice 2014",
    "mousesports (Holo) | Katowice 2014",
    "Vox Eminor (Holo) | Katowice 2014",
}

# Souvenir items from Majors — often overpriced due to sticker nostalgia
_LUXURY_SOUVENIR_EVENTS: set[str] = {
    "Katowice 2014",
    "Cologne 2014",
    "DreamHack 2014",
    "Katowice 2015",
    "Cologne 2015",
    "Cluj-Napoca 2015",
}

# Minimum total unapplied sticker value to consider "luxury"
_LUXURY_VALUE_THRESHOLD_USD: float = 500.0

# ═══════════════════════════════════════════════════════════════════════
# LEVEL 2: MID-RANGE PREMIUM TABLE — boost ranking, adjust list price
# Source: historical price data from StickerEvaluator + market observation
# ═══════════════════════════════════════════════════════════════════════

# Event → approximate premium % for items with Souvenir stickers from that event
_SOUVENIR_PREMIUMS: dict[str, float] = {
    "Copenhagen 2024": 0.12,
    "Antwerp 2022": 0.10,
    "Rio 2022": 0.08,
    "Stockholm 2021": 0.10,
    "RMR 2021": 0.06,
    "Berlin 2019": 0.05,
    "Katowice 2019": 0.08,
    "London 2018": 0.04,
    "Boston 2018": 0.05,
    "Krakow 2017": 0.06,
    "Atlanta 2017": 0.05,
    "Cologne 2016": 0.04,
    "Columbus 2016": 0.04,
}

# Holo/foil multiplier for stickers not in our database
_HOLO_FOIL_KEYWORDS: dict[str, float] = {
    "(Holo)": 0.06,       # +6% base premium
    "(Foil)": 0.04,       # +4%
    "(Gold)": 0.08,       # +8%
    "(Glitter)": 0.03,    # +3%
    "(Lenticular)": 0.05, # +5%
}

# Combo bonus: 4 identical stickers → extra premium
_COMBO_BONUS_4X: float = 0.05  # +5% for 4x same sticker


class StickerPremiumCache:
    """
    Two-tier sticker evaluation for the trading pipeline.

    Tier 1 (Filter): Reject items with luxury stickers before any
    further analysis. Saves API calls and prevents overpaying for
    sticker-dominated items.

    Tier 2 (Rank/Price): Calculate a premium multiplier for items
    with mid-range stickers. Used in ranking (score boost) and
    listing (price adjustment).
    """

    def __init__(self) -> None:
        # Runtime cache for sticker name → premium lookup
        self._premium_cache: dict[str, float] = {}
        self._rejection_cache: dict[str, bool] = {}

    # ──────────────────────────────────────────────────────────────
    # TIER 1: Luxury Rejection Filter
    # ──────────────────────────────────────────────────────────────

    def should_reject_by_stickers(self, stickers: list[dict[str, Any]]) -> bool:
        """
        Check if item should be rejected due to luxury stickers.

        Called from: filter.py → _evaluate_candidate() (early check)

        Args:
            stickers: List of sticker dicts with 'name' key

        Returns:
            True = reject (luxury sticker detected)
        """
        if not stickers:
            return False

        for sticker in stickers:
            name = sticker.get("name", "")
            if not name:
                continue

            # Check cache
            if name in self._rejection_cache:
                if self._rejection_cache[name]:
                    return True
                continue

            rejected = self._is_luxury_sticker(name)
            self._rejection_cache[name] = rejected

            if rejected:
                logger.debug(f"[STICKER-REJECT] Luxury sticker detected: {name}")
                return True

        return False

    def _is_luxury_sticker(self, name: str) -> bool:
        """Check if a single sticker name matches luxury criteria."""
        # 1. Direct keyword match
        for keyword in _LUXURY_KEYWORDS:
            if keyword in name:
                return True

        # 2. Souvenir from early Majors (2014-2015)
        if "Souvenir" in name:
            for event in _LUXURY_SOUVENIR_EVENTS:
                if event in name:
                    return True

        # 3. Very old holo/foil (2014 era) — any holo from 2014 is luxury
        return "2014" in name and ("Holo" in name or "Foil" in name)

    # ──────────────────────────────────────────────────────────────
    # TIER 2: Premium Multiplier (for ranking + listing price)
    # ──────────────────────────────────────────────────────────────

    def calculate_premium_multiplier(
        self,
        stickers: list[dict[str, Any]],
        base_price: float,
    ) -> float:
        """
        Calculate price multiplier from mid-range stickers.

        Called from: pricing.py → get_adjusted_list_price()
                     ranking.py → score_candidates()

        Args:
            stickers: List of sticker dicts
            base_price: Item price without sticker consideration

        Returns:
            Multiplier: 1.0 = no premium, 1.15 = +15% premium
            Capped at 1.30 to prevent overpricing.
        """
        if not stickers:
            return 1.0

        # Luxury items should have been rejected already
        if self.should_reject_by_stickers(stickers):
            return 1.0

        total_premium = 0.0

        for sticker in stickers:
            name = sticker.get("name", "")
            if not name:
                continue

            # Check cache first
            if name in self._premium_cache:
                total_premium += self._premium_cache[name]
                continue

            premium = self._estimate_sticker_premium(name)
            self._premium_cache[name] = premium
            total_premium += premium

        # Combo bonus: 4 identical stickers
        if len(stickers) == 4:
            names = [s.get("name", "") for s in stickers]
            if len(set(names)) == 1 and names[0]:
                total_premium += _COMBO_BONUS_4X

        # Cap at +30%
        return min(1.0 + total_premium, 1.30)

    def _estimate_sticker_premium(self, name: str) -> float:
        """Estimate premium for a single sticker name."""
        premium = 0.0

        # 1. Souvenir event premium
        for event, event_premium in _SOUVENIR_PREMIUMS.items():
            if event in name:
                premium = max(premium, event_premium)
                break

        # 2. Holo/Foil/Gold type premium
        for keyword, type_premium in _HOLO_FOIL_KEYWORDS.items():
            if keyword in name:
                premium = max(premium, type_premium)
                break

        # 3. Year-based heuristic (newer tournaments = more liquid)
        year_match = re.search(r"20(1[5-9]|2[0-9])", name)
        if year_match:
            year = int(year_match.group(0))
            if year >= 2022:
                premium = max(premium, 0.03)  # Recent = +3% minimum
            elif year >= 2019:
                premium = max(premium, 0.02)

        return premium

    # ──────────────────────────────────────────────────────────────
    # RANKING BOOST (for rank_candidates_by_spread)
    # ──────────────────────────────────────────────────────────────

    def get_ranking_boost(self, stickers: list[dict[str, Any]]) -> float:
        """
        Get a 0.0-1.0 boost score for ranking purposes.

        Higher = more desirable sticker combination.
        Used as a weight in the ranking formula.

        Returns:
            0.0 = no stickers or luxury (rejected)
            0.3-0.5 = common stickers with small premium
            0.6-0.8 = mid-range tournament stickers
            0.9-1.0 = excellent combo (4x same, holo, etc.)
        """
        if not stickers:
            return 0.0

        if self.should_reject_by_stickers(stickers):
            return 0.0

        multiplier = self.calculate_premium_multiplier(stickers, 0.0)
        # Normalize: 1.0 → 0.0, 1.30 → 1.0
        boost = (multiplier - 1.0) / 0.30
        return min(max(boost, 0.0), 1.0)

    # ──────────────────────────────────────────────────────────────
    # CACHE MANAGEMENT
    # ──────────────────────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Clear all caches (call periodically, e.g., every 24h)."""
        self._premium_cache.clear()
        self._rejection_cache.clear()

    @property
    def cache_stats(self) -> dict[str, int]:
        """Return cache hit statistics."""
        return {
            "premium_entries": len(self._premium_cache),
            "rejection_entries": len(self._rejection_cache),
        }
