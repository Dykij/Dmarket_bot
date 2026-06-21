"""
stickers_evaluator.py — Sticker value evaluation + combo premium calculator.

v14.6: Extended with combo detection (4x same = +100%, team/set matching +10%,
Katowice 2014 special handling, wear penalty).
"""

from typing import Dict, List, Any

# Rare sticker base prices (unapplied, USD)
_RARE_STICKERS: Dict[str, float] = {
    "Titan | Katowice 2014": 15000.0,
    "iBUYPOWER | Katowice 2014": 20000.0,
    "Reason Gaming | Katowice 2014": 10000.0,
    "Dignitas | Katowice 2014": 5000.0,
    "Crown (Foil)": 800.0,
    "Howl": 1200.0,
}

# Katowice 2014 sticker base prices
_KATOWICE_2014: Dict[str, float] = {
    "Titan | Katowice 2014": 15000.0,
    "Titan (Holo) | Katowice 2014": 60000.0,
    "iBUYPOWER | Katowice 2014": 20000.0,
    "iBUYPOWER (Holo) | Katowice 2014": 50000.0,
    "Reason Gaming | Katowice 2014": 10000.0,
    "Reason Gaming (Holo) | Katowice 2014": 30000.0,
    "Dignitas | Katowice 2014": 5000.0,
    "Dignitas (Holo) | Katowice 2014": 25000.0,
    "Vox Eminor | Katowice 2014": 3000.0,
    "Vox Eminor (Holo) | Katowice 2014": 15000.0,
    "LGB eSports | Katowice 2014": 2000.0,
    "LGB eSports (Holo) | Katowice 2014": 10000.0,
    "Complexity Gaming | Katowice 2014": 2000.0,
    "Complexity Gaming (Holo) | Katowice 2014": 10000.0,
    "Team LDLC.com | Katowice 2014": 2000.0,
    "Team LDLC.com (Holo) | Katowice 2014": 10000.0,
    "Natus Vincere | Katowice 2014": 3000.0,
    "Natus Vincere (Holo) | Katowice 2014": 20000.0,
    "Virtus.pro | Katowice 2014": 2000.0,
    "Virtus.pro (Holo) | Katowice 2014": 8000.0,
    "Fnatic | Katowice 2014": 2000.0,
    "Fnatic (Holo) | Katowice 2014": 8000.0,
    "HellRaisers | Katowice 2014": 1500.0,
    "HellRaisers (Holo) | Katowice 2014": 6000.0,
    "3DMAX | Katowice 2014": 1500.0,
    "3DMAX (Holo) | Katowice 2014": 5000.0,
    "mousesports | Katowice 2014": 1500.0,
    "mousesports (Holo) | Katowice 2014": 5000.0,
}

# Team name extraction: "TeamName | Event Year" or "TeamName (Holo) | Event Year"
def _extract_team(sticker_name: str) -> str:
    """Extract team/player name from sticker string."""
    for sep in (" | ", " ("):
        if sep in sticker_name:
            return sticker_name.split(sep)[0]
    return sticker_name


def _extract_event(sticker_name: str) -> str:
    """Extract event name from sticker string."""
    if " | " in sticker_name:
        parts = sticker_name.split(" | ", 1)
        event = parts[1] if len(parts) > 1 else ""
        return event.split(" (")[0] if " (" in event else event
    return ""


def _is_katowice_2014(name: str) -> bool:
    return "Katowice 2014" in name


class StickerEvaluator:
    """Evaluates sticker value with combo premium detection."""

    def __init__(self, spp_base: float = 0.05, spp_rare_bonus: float = 0.10):
        self.spp_base = spp_base
        self.spp_rare_bonus = spp_rare_bonus

    # ------------------------------------------------------------------
    # Combo premium (v14.6)
    # ------------------------------------------------------------------
    def calculate_combo_premium(self, stickers: List[Dict[str, Any]]) -> float:
        """Calculate additional USD value from sticker combinations.

        Rules (from TA site analysis):
        - 4 identical stickers (stick): +100% of ONE sticker's value
        - Same team/event (3+ stickers): +10% of total sticker value
        - Katowice 2014 (any count): special 15% of total (conservative)
        - All worn (wear > 0): 0 premium
        """
        if not stickers or len(stickers) < 2:
            return 0.0

        total_value = sum(self._sticker_price(s) for s in stickers)
        if total_value <= 0:
            return 0.0

        # 4 identical = stick → +100% of ONE sticker
        names = [s.get("name", "") for s in stickers]
        if len(set(names)) == 1 and len(stickers) == 4:
            one_price = self._sticker_price(stickers[0])
            return one_price  # +100% of one

        # All worn → no combo premium
        worn_count = sum(1 for s in stickers if float(s.get("wear", 0) or 0) > 0)
        if worn_count == len(stickers):
            return 0.0

        # Katowice 2014 → special handling (conservative 15%)
        if any(_is_katowice_2014(s.get("name", "")) for s in stickers):
            return total_value * 0.15

        # Same team or event (3+ stickers) → +10%
        teams = {_extract_team(s.get("name", "")) for s in stickers}
        events = {_extract_event(s.get("name", "")) for s in stickers}
        if len(teams) == 1 and len(stickers) >= 3:
            return total_value * 0.10
        if len(events) == 1 and events != {""} and len(stickers) >= 3:
            return total_value * 0.10

        # Generic: 5% for 2+ stickers
        if len(stickers) >= 2:
            return total_value * 0.05

        return 0.0

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------
    def _sticker_price(self, sticker: Dict[str, Any]) -> float:
        """Get estimated unapplied price for a sticker."""
        name = sticker.get("name", "")
        price = _RARE_STICKERS.get(name, 0.0)
        if price <= 0:
            price = _KATOWICE_2014.get(name, 0.0)
        return price

    def calculate_added_value(self, stickers: List[Dict[str, Any]]) -> float:
        """Calculates the estimated USD value added by stickers.

        Uses exponential decay for wear penalty on applied stickers.
        Includes combo premium from calculate_combo_premium.
        """
        total_added_value = 0.0

        for s in stickers:
            name = s.get("name", "")
            try:
                wear = float(s.get("wear", 0.0))
            except (ValueError, TypeError):
                wear = 0.0

            unapplied_price = self._sticker_price(s)
            if unapplied_price <= 0.0:
                continue

            wear_factor = max(0.0, 1.0 - (wear ** 0.5)) if wear > 0.0 else 1.0
            spp = self.spp_rare_bonus if unapplied_price > 1000.0 else self.spp_base

            added = unapplied_price * spp * wear_factor
            total_added_value += added

        # Add combo premium
        total_added_value += self.calculate_combo_premium(stickers)

        return round(total_added_value, 2)

    def is_undervalued(self, item_price: float, base_price: float, stickers: List[Dict[str, Any]]) -> bool:
        """Validates if item is undervalued compared to baseline + SPP value."""
        sticker_value = self.calculate_added_value(stickers)
        return item_price < (base_price + sticker_value) * 0.95
