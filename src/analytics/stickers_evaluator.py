"""
sticks_evaluator.py — Sticker value evaluation + combo premium calculator.

v14.6: Extended with combo detection (4x same = +100%, team/set matching +10%,
       Katowice 2014 special handling, wear penalty).
v15.3: Added mid-range tournament stickers (2015-2023), holo/foil premiums,
       and community favorites.
v15.4: Added slot premium (wood slot on AK, playside visibility),
       streak detection (3+ identical = strik), and weapon-specific multipliers.
"""

from typing import Any

# Rare sticker base prices (unapplied, USD) — ultra-premium (kept for reference)
_RARE_STICKERS: dict[str, float] = {
    "Titan | Katowice 2014": 15000.0,
    "iBUYPOWER | Katowice 2014": 20000.0,
    "Reason Gaming | Katowice 2014": 10000.0,
    "Dignitas | Katowice 2014": 5000.0,
    "Crown (Foil)": 800.0,
    "Howl": 1200.0,
}

# Mid-range tournament stickers (2015-2023) — $5-$500 range
# These are the sweet spot for sticker investment
_MID_RANGE_STICKERS: dict[str, float] = {
    # Katowice 2015 (mid-range holos)
    "Virtus.pro (Holo) | Katowice 2015": 200.0,
    "Natus Vincere (Holo) | Katowice 2015": 180.0,
    "Fnatic (Holo) | Katowice 2015": 150.0,
    "TSM Kinguin (Holo) | Katowice 2015": 120.0,
    "Team EnVyUs (Holo) | Katowice 2015": 100.0,
    "Ninjas in Pyjamas (Holo) | Katowice 2015": 100.0,
    "Team SoloMid (Holo) | Katowice 2015": 90.0,
    "PENTA Sports (Holo) | Katowice 2015": 80.0,
    "Cloud9 (Holo) | Katowice 2015": 150.0,
    "Titan | Katowice 2015": 50.0,
    "Virtus.pro | Katowice 2015": 30.0,
    "Natus Vincere | Katowice 2015": 25.0,

    # Cologne 2014 (holo premiums)
    "Virtus.pro (Holo) | Cologne 2014": 80.0,
    "Natus Vincere (Holo) | Cologne 2014": 70.0,
    "Fnatic (Holo) | Cologne 2014": 60.0,
    "Cloud9 (Holo) | Cologne 2014": 60.0,
    "Ninjas in Pyjamas (Holo) | Cologne 2014": 50.0,
    "Team Dignitas (Holo) | Cologne 2014": 40.0,

    # Cluj-Napoca 2015 (foil/holo)
    "Virtus.pro (Foil) | Cluj-Napoca 2015": 30.0,
    "Natus Vincere (Foil) | Cluj-Napoca 2015": 25.0,
    "Fnatic (Foil) | Cluj-Napoca 2015": 20.0,

    # Columbus 2016 (holo/foil)
    "Virtus.pro (Holo) | Columbus 2016": 40.0,
    "Natus Vincere (Holo) | Columbus 2016": 35.0,
    "Fnatic (Holo) | Columbus 2016": 30.0,
    "Luminosity Gaming (Holo) | Columbus 2016": 25.0,
    "Team Liquid (Holo) | Columbus 2016": 20.0,
    "Astralis (Holo) | Columbus 2016": 20.0,

    # Cologne 2016 (holo/foil)
    "Virtus.pro (Holo) | Cologne 2016": 35.0,
    "Natus Vincere (Holo) | Cologne 2016": 30.0,
    "SK Gaming (Holo) | Cologne 2016": 25.0,
    "Team Liquid (Holo) | Cologne 2016": 20.0,

    # Atlanta 2017 (holo/foil)
    "Virtus.pro (Holo) | Atlanta 2017": 30.0,
    "Astralis (Holo) | Atlanta 2017": 25.0,
    "Natus Vincere (Holo) | Atlanta 2017": 25.0,
    "SK Gaming (Holo) | Atlanta 2017": 20.0,
    "FaZe Clan (Holo) | Atlanta 2017": 20.0,

    # Krakow 2017 (gold)
    "Virtus.pro (Gold) | Krakow 2017": 50.0,
    "Astralis (Gold) | Krakow 2017": 40.0,
    "Gambit Gaming (Gold) | Krakow 2017": 35.0,
    "FaZe Clan (Gold) | Krakow 2017": 30.0,

    # Boston 2018 (holo/foil)
    "Cloud9 (Holo) | Boston 2018": 40.0,
    "FaZe Clan (Holo) | Boston 2018": 30.0,
    "G2 Esports (Holo) | Boston 2018": 20.0,
    "Natus Vincere (Holo) | Boston 2018": 25.0,

    # London 2018 (gold/holo)
    "Astralis (Gold) | London 2018": 30.0,
    "Natus Vincere (Gold) | London 2018": 25.0,
    "FaZe Clan (Gold) | London 2018": 20.0,

    # Katowice 2019 (gold/holo)
    "Astralis (Gold) | Katowice 2019": 40.0,
    "Natus Vincere (Gold) | Katowice 2019": 35.0,
    "FaZe Clan (Gold) | Katowice 2019": 25.0,
    "ENCE (Gold) | Katowice 2019": 20.0,
    "Team Liquid (Gold) | Katowice 2019": 20.0,

    # Berlin 2019 (gold/holo)
    "Astralis (Gold) | Berlin 2019": 30.0,
    "Team Liquid (Gold) | Berlin 2019": 25.0,
    "Natus Vincere (Gold) | Berlin 2019": 20.0,

    # Rio 2022 (gold/champion)
    "Outsiders (Gold) | Rio 2022": 15.0,
    "FaZe Clan (Gold) | Rio 2022": 12.0,

    # Paris 2023 (gold/champion)
    "Team Vitality (Gold) | Paris 2023": 15.0,
    "GamerLegion (Gold) | Paris 2023": 10.0,

    # Copenhagen 2024 (gold/champion)
    "Natus Vincere (Gold) | Copenhagen 2024": 12.0,
    "FaZe Clan (Gold) | Copenhagen 2024": 10.0,

    # Community favorites (non-tournament)
    "Crown (Foil)": 800.0,
    "Howl": 1200.0,
    "Headshot Guarantee": 15.0,
    "Battle Scarred": 10.0,
    "Chicken Lover": 8.0,
    "Backstab": 5.0,
    "Drug War Veteran": 5.0,
    "Vigilance": 3.0,
    "Recoil": 3.0,
    "Foil": 2.0,

    # Holo/Foil general premiums (by pattern)
    # These are generic — real prices depend on specific sticker
}

# Holo/foil multiplier for stickers not in our database
_HOLO_MULTIPLIER = 3.0
_FOIL_MULTIPLIER = 2.0
_GOLD_MULTIPLIER = 4.0

# Tournament year → approximate base value for unknown stickers
_TOURNAMENT_YEAR_VALUE: dict[int, float] = {
    2014: 500.0,   # Cologne/Katowice 2014
    2015: 30.0,    # Katowice/Cluj 2015
    2016: 15.0,    # Columbus/Cologne 2016
    2017: 10.0,    # Atlanta/Krakow 2017
    2018: 8.0,     # Boston/London 2018
    2019: 6.0,     # Katowice/Berlin 2019
    2020: 4.0,     # RMR 2020
    2021: 3.0,     # Stockholm 2021
    2022: 2.5,     # Antwerp/Rio 2022
    2023: 2.0,     # Paris 2023
    2024: 1.5,     # Copenhagen 2024
}

# v15.4: Weapon slot visibility multipliers
# Slots on weapons have different visibility — "wood" slot on AK is most visible
# CSFloat API returns stickers[].slot (0-3, left to right on inspect)
# Map: weapon_type → {slot → multiplier}
_SLOT_PREMIUM: dict[str, dict[int, float]] = {
    "AK-47": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.30},   # slot 3 = wood (most visible)
    "M4A4": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.20},
    "M4A1-S": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.20},
    "AWP": {0: 1.0, 1: 1.10, 2: 1.15, 3: 1.0},      # scope area most visible
    "Desert Eagle": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.15},
    "USP-S": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.10},
    "Glock-18": {0: 1.0, 1: 1.05, 2: 1.0, 3: 1.10},
    "knife": {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.25},      # playside on knives
}
# Default slot multiplier if weapon not in map
_DEFAULT_SLOT_MULT: dict[int, float] = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}

# v15.4: Streak bonus (3+ identical stickers on same weapon)
_STREAK_BONUS: dict[int, float] = {
    2: 0.10,   # 2 identical = +10% of sticker value
    3: 0.30,   # 3 identical = +30%
    4: 1.00,   # 4 identical = +100% (already handled in combo, but explicit)
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


def _extract_year(sticker_name: str) -> int | None:
    """Extract tournament year from sticker name."""
    import re
    match = re.search(r'20(1[4-9]|2[0-9])', sticker_name)
    return int(match.group()) if match else None


def _is_katowice_2014(name: str) -> bool:
    return "Katowice 2014" in name


def _get_sticker_base_price(name: str) -> float:
    """Get sticker base price from all databases."""
    # 1. Ultra-premium
    price = _RARE_STICKERS.get(name, 0.0)
    if price > 0:
        return price

    # 2. Mid-range tournament
    price = _MID_RANGE_STICKERS.get(name, 0.0)
    if price > 0:
        return price

    # 3. Estimate from type + year
    year = _extract_year(name)
    if year and year in _TOURNAMENT_YEAR_VALUE:
        base = _TOURNAMENT_YEAR_VALUE[year]
        name_lower = name.lower()
        if "(gold)" in name_lower:
            return base * _GOLD_MULTIPLIER
        if "(holo)" in name_lower:
            return base * _HOLO_MULTIPLIER
        if "(foil)" in name_lower:
            return base * _FOIL_MULTIPLIER
        return base * 0.3  # Normal paper sticker

    return 0.0


class StickerEvaluator:
    """Evaluates sticker value with combo premium, slot premium, and streak detection."""

    def __init__(self, spp_base: float = 0.05, spp_rare_bonus: float = 0.10):
        self.spp_base = spp_base
        self.spp_rare_bonus = spp_rare_bonus

    # ------------------------------------------------------------------
    # v15.4: Slot premium — weapon-specific visibility bonus
    # ------------------------------------------------------------------
    @staticmethod
    def get_slot_multiplier(weapon_name: str, slot: int) -> float:
        """Get visibility multiplier for a sticker slot on a weapon.

        CSFloat API: stickers[].slot (0-3)
        AK-47 slot 3 = "wood" (most visible) → 1.30x
        AWP slots 1-2 = scope area → 1.10-1.15x
        """
        weapon_lower = weapon_name.lower()
        for weapon_key, slots in _SLOT_PREMIUM.items():
            if weapon_key.lower() in weapon_lower:
                return slots.get(slot, 1.0)
        return _DEFAULT_SLOT_MULT.get(slot, 1.0)

    # ------------------------------------------------------------------
    # v15.4: Streak detection — identical sticker count bonus
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_streak_bonus(stickers: list[dict[str, Any]]) -> float:
        """Calculate bonus for having multiple identical stickers.

        Returns USD bonus value. 3+ identical = strik (high demand).
        """
        if not stickers or len(stickers) < 2:
            return 0.0

        names = [s.get("name", "") for s in stickers]
        name_counts: dict[str, int] = {}
        for n in names:
            if n:
                name_counts[n] = name_counts.get(n, 0) + 1

        bonus = 0.0
        for name, count in name_counts.items():
            if count >= 2:
                base_price = _get_sticker_base_price(name)
                streak_mult = _STREAK_BONUS.get(count, 0.0)
                bonus += base_price * streak_mult

        return bonus

    # ------------------------------------------------------------------
    # Combo premium (v14.6)
    # ------------------------------------------------------------------
    def calculate_combo_premium(self, stickers: list[dict[str, Any]]) -> float:
        """Calculate additional USD value from sticker combinations.

        Rules:
        - 4 identical stickers (stick): +100% of ONE sticker's value
        - Same team/event (3+ stickers): +10% of total sticker value
        - Tournament year match (3+ same year): +8% of total
        - All worn (wear > 0): 0 premium
        - Holo/foil mixed set (3+): +5% bonus
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

        # Same team or event (3+ stickers) → +10%
        teams = {_extract_team(s.get("name", "")) for s in stickers}
        events = {_extract_event(s.get("name", "")) for s in stickers}
        if len(teams) == 1 and len(stickers) >= 3:
            return total_value * 0.10
        if len(events) == 1 and events != {""} and len(stickers) >= 3:
            return total_value * 0.10

        # Same tournament year (3+ stickers) → +8%
        years = {_extract_year(s.get("name", "")) for s in stickers}
        years.discard(None)
        if len(years) == 1 and len(stickers) >= 3:
            return total_value * 0.08

        # Holo/foil mixed set (3+ holo/foil) → +5%
        holo_foil_count = sum(
            1 for s in stickers
            if any(t in s.get("name", "").lower() for t in ("holo", "foil", "gold"))
        )
        if holo_foil_count >= 3:
            return total_value * 0.05

        # Generic: 5% for 2+ stickers
        if len(stickers) >= 2:
            return total_value * 0.05

        return 0.0

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------
    def _sticker_price(self, sticker: dict[str, Any]) -> float:
        """Get estimated unapplied price for a sticker.

        Checks: ultra-premium → mid-range tournament → year/type estimate.
        """
        name = sticker.get("name", "")
        return _get_sticker_base_price(name)

    def calculate_added_value(
        self,
        stickers: list[dict[str, Any]],
        weapon_name: str = "",
    ) -> float:
        """Calculates the estimated USD value added by stickers.

        v15.4: Enhanced with slot premium (wood slot visibility)
        and streak detection (3+ identical = strik bonus).

        Uses exponential decay for wear penalty on applied stickers.
        Includes combo premium from calculate_combo_premium.
        """
        total_added_value = 0.0

        for s in stickers:
            s.get("name", "")
            try:
                wear = float(s.get("wear", 0.0))
            except (ValueError, TypeError):
                wear = 0.0

            unapplied_price = self._sticker_price(s)
            if unapplied_price <= 0.0:
                continue

            wear_factor = max(0.0, 1.0 - (wear ** 0.5)) if wear > 0.0 else 1.0
            spp = self.spp_rare_bonus if unapplied_price > 1000.0 else self.spp_base

            # v15.4: Slot premium
            slot = int(s.get("slot", 0))
            slot_mult = self.get_slot_multiplier(weapon_name, slot) if weapon_name else 1.0

            added = unapplied_price * spp * wear_factor * slot_mult
            total_added_value += added

        # Add combo premium
        total_added_value += self.calculate_combo_premium(stickers)

        # v15.4: Add streak bonus
        total_added_value += self.calculate_streak_bonus(stickers)

        return round(total_added_value, 2)

    def is_undervalued(self, item_price: float, base_price: float, stickers: list[dict[str, Any]]) -> bool:
        """Validates if item is undervalued compared to baseline + SPP value."""
        sticker_value = self.calculate_added_value(stickers)
        return item_price < (base_price + sticker_value) * 0.95
