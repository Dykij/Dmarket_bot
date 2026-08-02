"""
rare_valuation.py — Multi-factor rarity scoring engine.

v15.3: Enhanced with extended pattern seeds, Gamma Doppler phases,
       mid-range sticker awareness, and ultra-low-float detection.
"""

from typing import Any


class RareValuationEngine:
    """
    Evaluates algorithmic Estimated Value (EV) multipliers based on
    float, pattern, phase, and sticker rarity.
    """

    def __init__(self):
        self.LOW_FLOAT_THRESHOLD = 0.001
        self.MW_FN_BORDER_FLOAT = 0.07005

        # Tier-1 Pattern Seeds (Blue Gem, Fire & Ice, rare fades)
        self.RARE_SEEDS = {
            902, 661, 321, 151, 670, 760, 417, 387, 809, 838,
            # Extended Blue Gem
            179, 189, 442, 468, 494, 525, 575, 592, 605, 631,
            689, 713, 750, 770, 787, 868, 905, 935,
            # Fire & Ice
            152, 412, 541, 601, 649, 777, 853, 922, 947,
        }

        # Phase premiums (Doppler + Gamma Doppler)
        self.PHASE_PREMIUMS = {
            "ruby": 5.0, "sapphire": 6.0, "black pearl": 4.0,
            "emerald": 8.0, "phase 2": 1.5, "phase 4": 1.3,
        }

    def get_rare_score(self, attrs: dict[str, Any]) -> float:
        """
        Calculates multiplier for base price (1.0 = Market API Price).
        """
        score = 1.0

        # 1. Float Analysis
        try:
            float_val = float(attrs.get("float_value", attrs.get("floatPartValue", 1.0)))
        except (ValueError, TypeError):
            float_val = 1.0

        if float_val < self.LOW_FLOAT_THRESHOLD:
            score += 0.20  # v15.3: increased from 0.15
        elif float_val < 0.005:
            score += 0.10  # v15.3: new tier
        elif float_val < 0.01:
            score += 0.05

        # 2. Pattern Analysis
        try:
            paint_seed = int(attrs.get("paint_seed", attrs.get("paintSeed", 0)))
        except (ValueError, TypeError):
            paint_seed = 0

        if paint_seed in self.RARE_SEEDS:
            score += 2.0

        # 3. Phase Analysis
        phase = str(attrs.get("phase", "")).lower()
        for phase_key, premium in self.PHASE_PREMIUMS.items():
            if phase_key in phase:
                score += premium
                break

        # 4. v15.3: Sticker bonus (if present)
        stickers = attrs.get("stickers", [])
        if stickers and isinstance(stickers, list):
            holo_count = sum(
                1 for s in stickers
                if isinstance(s, dict) and any(
                    t in s.get("name", "").lower()
                    for t in ("holo", "foil", "gold")
                )
            )
            if holo_count >= 3:
                score += 0.15  # Holo/foil combo bonus
            elif holo_count >= 1:
                score += 0.05  # Single holo bonus

        return score

    def estimate_market_value(self, base_price: float, attrs: dict[str, Any]) -> float:
        """Calculates deterministic Estimated Value (EV) adjusted for rarity."""
        multiplier = self.get_rare_score(attrs)
        return round(base_price * multiplier, 2)
