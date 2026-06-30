"""
item_intel.py — Enhanced item intelligence (v14.5).

Wires previously unused analytics into the trading pipeline:
  1. PriceAnalytics (RSI/MACD/Bollinger) → filter scoring bonus
  2. DMarket discount/marker detection (discount, suggestedPrice, tagName)
  3. Item categorization (rifle/pistol/knife/sticker/case/other)
  4. Cross-wear grouping (family-level concentration control)
  5. Event Shield activation (is_category_risky + is_opportunity_mode)

Mixed into `_FilterMixin` (see `filter.py`).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from src.config import Config
from src.db.price_history import price_db

logger = logging.getLogger("ItemIntel")

# Discount marker tuning
DISCOUNT_THRESHOLD_PCT = float(os.getenv("DISCOUNT_THRESHOLD_PCT", "10.0"))
USE_DISCOUNT_FILTER = os.getenv("USE_DISCOUNT_FILTER", "true").lower() == "true"
USE_CATEGORY_FILTER = os.getenv("USE_CATEGORY_FILTER", "true").lower() == "true"
USE_CROSS_WEAR_GUARD = os.getenv("USE_CROSS_WEAR_GUARD", "true").lower() == "true"

# Skin name → weapon type patterns
_WEAPON_PATTERNS: Dict[str, re.Pattern] = {
    "rifle": re.compile(
        r"\b(AK-47|M4A4|M4A1-S|AUG|SG 553|FAMAS|Galil AR|SSG 08|AWP|SCAR-20|G3SG1)\b", re.I
    ),
    "smg": re.compile(
        r"\b(MP9|MP7|MP5-SD|UMP-45|P90|PP-Bizon|MAC-10)\b", re.I
    ),
    "pistol": re.compile(
        r"\b(Desert Eagle|R8 Revolver|P250|P2000|USP-S|Glock-18|CZ75-Auto|Five-SeveN|Tec-9|Dual Berettas)\b", re.I
    ),
    "heavy": re.compile(
        r"\b(MAG-7|Nova|XM1014|Sawed-Off|M249|Negev)\b", re.I
    ),
    "knife": re.compile(
        r"\b★\b|Knife|Bayonet|Flip|Gut|Karambit|M9|Huntsman|Butterfly|Falchion|Shadow|Bowie|Ursus|Navaja|Stiletto|Talon|Skeleton|Survival|Nomad|Paracord|Classic|Kukri", re.I
    ),
    "gloves": re.compile(
        r"\bGloves\b|Hand Wraps|Driver|Specialist|Sport|Moto|Bloodhound|Hydra|Broken Fang", re.I
    ),
    "sticker": re.compile(
        r"\bSticker\b", re.I
    ),
    "case": re.compile(
        r"\b(Case|Capsule|Package|Souvenir)\b", re.I
    ),
    "graffiti": re.compile(
        r"\bGraffiti\b", re.I
    ),
}

# Wear levels from float ranges
_WEAR_LEVELS = [
    "Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred",
    "FN", "MW", "FT", "WW", "BS",
]

# Risky categories from Event Shield that should be filtered during caution events
_RISKY_CATEGORIES = {
    "case": "New case release — existing case prices may drop",
    "sticker": "Sticker capsule/bundle release — sticker prices volatile",
    "collection": "New collection — existing skins may devalue",
}


class _ItemIntelMixin:
    """Enhanced item analysis for filter pipeline."""

    _analytics_engine: Any = None

    def _ensure_analytics(self):
        if self._analytics_engine is None:
            from src.analytics.price_analytics import PriceAnalytics
            self._analytics_engine = PriceAnalytics()

    # ─────────────────────────────────────────────
    # 1. PriceAnalytics: RSI/MACD/Bollinger scoring
    # ─────────────────────────────────────────────

    def compute_technical_score(
        self, title: str, current_price: float, listing_count: int = 0,
    ) -> Tuple[float, str]:
        """
        Compute a 0..1 technical score from RSI/MACD/Bollinger.
        Returns (score, signal_desc).
        Higher = better buying opportunity.
        """
        self._ensure_analytics()
        history = price_db.get_recent_prices(title, days=30)
        prices = [float(p[0]) for p in history]

        if len(prices) < 15:  # need minimum data for reliable indicators
            return 0.5, "insufficient_data"

        from decimal import Decimal
        analysis = self._analytics_engine.analyze_item(
            item_name=title,
            price_history=prices,
            current_price=Decimal(str(current_price)),
            listings_count=listing_count,
        )

        score = 0.5  # neutral base
        signals = []

        # RSI: oversold = good buy
        if analysis.rsi:
            rsi = analysis.rsi
            if rsi.is_oversold:
                score += 0.20
                signals.append(f"RSI_oversold({rsi.value:.0f})")
            elif rsi.is_overbought:
                score -= 0.15
                signals.append(f"RSI_overbought({rsi.value:.0f})")
            else:
                signals.append(f"RSI({rsi.value:.0f})")

        # MACD: bullish crossover = good buy
        if analysis.macd:
            macd = analysis.macd
            if macd.is_bullish_crossover:
                score += 0.15
                signals.append("MACD_bullish_x")
            elif macd.is_bearish_crossover:
                score -= 0.15
                signals.append("MACD_bearish_x")

        # Bollinger: near lower band = undervalued
        if analysis.bollinger:
            bb = analysis.bollinger
            mid = (bb.upper + bb.lower) / 2 if bb.upper > 0 and bb.lower > 0 else 0
            if mid > 0 and current_price <= bb.lower * 1.05:
                score += 0.15
                signals.append("BB_lower")
            elif current_price >= bb.upper * 0.95:
                score -= 0.10
                signals.append("BB_upper")

        # Trend: bullish = good
        if analysis.trend:
            from src.analytics.price_analytics import Trend
            trend = analysis.trend
            if trend.direction == Trend.BULLISH:
                score += 0.05
                signals.append("trend_up")
            elif trend.direction == Trend.BEARISH:
                score -= 0.10
                signals.append("trend_down")

        score = max(0.0, min(score, 1.0))
        return score, "|".join(signals) if signals else "no_data"

    # ─────────────────────────────────────────────
    # 2. DMarket discount/marker detection
    # ─────────────────────────────────────────────

    def extract_dmarket_markers(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract discount, suggestedPrice, tagName, and other markers
        from a DMarket market-items listing object.
        """
        markers: Dict[str, Any] = {}

        discount = item.get("discount")
        if discount is not None:
            try:
                markers["discount_pct"] = float(discount)
            except (ValueError, TypeError):
                pass

        suggested = item.get("suggestedPrice", {})
        if isinstance(suggested, dict):
            try:
                markers["suggested_price_usd"] = float(suggested.get("USD", 0)) / 100.0
            except (ValueError, TypeError):
                pass

        instant = item.get("instantPrice", {})
        if isinstance(instant, dict):
            try:
                markers["instant_price_usd"] = float(instant.get("USD", 0)) / 100.0
            except (ValueError, TypeError):
                pass

        extra = item.get("extra", {})
        if isinstance(extra, dict):
            markers["is_new"] = bool(extra.get("isNew"))
            markers["tag_name"] = extra.get("tagName", "")
            markers["trade_locked"] = bool(extra.get("tradeLock"))
            markers["withdrawable"] = bool(extra.get("withdrawable"))

        return markers

    def is_discounted_deal(self, item: Dict[str, Any], base_price: float) -> bool:
        """Check if the item has a significant DMarket discount."""
        if not USE_DISCOUNT_FILTER:
            return False

        markers = self.extract_dmarket_markers(item)

        # Check for discount percentage
        discount_pct = markers.get("discount_pct", 0)
        if discount_pct >= DISCOUNT_THRESHOLD_PCT:
            return True

        # Check if price is significantly below suggested/recommended
        suggested = markers.get("suggested_price_usd", 0)
        if suggested > 0 and base_price < suggested * 0.90:
            return True  # at least 10% below suggested

        # Check for "Best Price" / "Лучшая цена" marker
        tag = markers.get("tag_name", "")
        if tag and ("best" in tag.lower() or "лучш" in tag.lower() or "cheapest" in tag.lower()):
            return True

        return False

    def get_marker_bonus(self, item: Dict[str, Any]) -> float:
        """
        Return a score multiplier (>=1.0) for items with favourable DMarket markers.
        """
        if not USE_DISCOUNT_FILTER:
            return 1.0

        markers = self.extract_dmarket_markers(item)
        bonus = 1.0

        discount_pct = markers.get("discount_pct", 0)
        if discount_pct >= 30:
            bonus += 0.15
        elif discount_pct >= 20:
            bonus += 0.10
        elif discount_pct >= 10:
            bonus += 0.05

        if markers.get("is_new"):
            bonus += 0.05  # New listings may be underpriced initially

        tag = markers.get("tag_name", "")
        if "best" in tag.lower() or "лучш" in tag.lower():
            bonus += 0.10

        return min(bonus, 1.30)

    # ─────────────────────────────────────────────
    # 3. Item categorization
    # ─────────────────────────────────────────────

    def categorize_item(self, title: str) -> str:
        """Return item category: rifle, smg, pistol, heavy, knife, gloves, sticker, case, graffiti, other."""
        if not USE_CATEGORY_FILTER:
            return "other"

        for cat, pattern in _WEAPON_PATTERNS.items():
            if pattern.search(title):
                return cat
        return "other"

    def get_category_risk_multiplier(self, title: str) -> float:
        """
        Return a risk multiplier for position sizing based on category.
        Knives/cases are more volatile → smaller positions.
        Rifles/pistols are more liquid → standard positions.
        """
        cat = self.categorize_item(title)

        multipliers = {
            "rifle": 1.0,
            "smg": 0.9,
            "pistol": 0.95,
            "heavy": 0.85,
            "knife": 0.5,     # high value, high volatility — half position
            "gloves": 0.5,    # same as knives
            "sticker": 0.3,   # very illiquid, high spread — smallest position
            "case": 0.7,      # low value but volatile on release
            "graffiti": 0.0,  # do not buy graffiti
            "other": 1.0,
        }
        return multipliers.get(cat, 1.0)

    def is_blocked_category(self, title: str) -> bool:
        """Return True if this category should be entirely skipped."""
        cat = self.categorize_item(title)
        if cat == "graffiti":
            return True
        return False

    # ─────────────────────────────────────────────
    # 4. Cross-wear grouping (family-level guard)
    # ─────────────────────────────────────────────

    @staticmethod
    def extract_base_skin(title: str) -> str:
        """Extract base skin name without wear/condition suffix.
        'AK-47 | Redline (Field-Tested)' → 'AK-47 | Redline'
        '★ Karambit | Doppler (Factory New)' → '★ Karambit | Doppler'
        """
        # Remove wear suffix: (FN), (MW), (FT), (WW), (BS) or full names
        result = title
        for wear in _WEAR_LEVELS:
            result = result.replace(f" ({wear})", "")
            result = result.replace(f"({wear})", "")
        return result.strip()

    def get_family_holdings_count(self, title: str) -> int:
        """Count how many items of the same base skin (any wear) are held."""
        if not USE_CROSS_WEAR_GUARD:
            return 0

        base = self.extract_base_skin(title)
        all_idle = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
        all_selling = price_db.get_virtual_inventory(status="selling")
        all_listed = price_db.get_virtual_inventory(status="listed")

        count = 0
        for item in all_idle + all_selling + all_listed:
            item_base = self.extract_base_skin(item["hash_name"])
            if item_base == base:
                count += 1
        return count

    def is_family_saturated(self, title: str, max_family: int = 3) -> bool:
        """Check if cross-wear family holdings exceed limit."""
        if not USE_CROSS_WEAR_GUARD:
            return False
        count = self.get_family_holdings_count(title)
        return count >= max_family

    # ─────────────────────────────────────────────
    # 5. Event Shield activation
    # ─────────────────────────────────────────────

    @staticmethod
    def check_event_risk(title: str) -> Optional[str]:
        """
        Check if the item category is risky during active events.
        Returns None if safe, or a reason string if blocked.
        """
        from src.core.event_shield import event_shield

        if event_shield.is_category_risky(title):
            return "event_shield: category_risky"

        return None

    @staticmethod
    def get_event_opportunity_multiplier() -> float:
        """
        During opportunity events (Steam sales, etc.), return a lower
        margin threshold to buy more aggressively. Returns 1.0 normally.
        """
        from src.core.event_shield import event_shield

        if event_shield.is_opportunity_mode():
            return 0.70  # 30% more aggressive during opportunity events
        return 1.0
