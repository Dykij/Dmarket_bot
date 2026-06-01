from typing import Dict, Any

class RareValuationEngine:
    """
    Evaluates algorithmic Estimated Value (EV) multipliers based on float, pattern, and phase.
    """
    
    def __init__(self):
        self.LOW_FLOAT_THRESHOLD = 0.001
        self.MW_FN_BORDER_FLOAT = 0.07005
        
        # Expanded Tier-1 Pattern Seeds (e.g., Case Hardened Blue Gem / Fade 100%)
        self.RARE_SEEDS = {902, 661, 321, 151, 670, 760, 417, 387, 809, 838}
        
    def get_rare_score(self, attrs: Dict[str, Any]) -> float:
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
            score += 0.15
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
        if "ruby" in phase:
            score += 5.0
        elif "sapphire" in phase:
            score += 6.0
        elif "black pearl" in phase:
            score += 4.0
        elif "emerald" in phase:
            score += 8.0
        elif "phase 2" in phase:
            score += 0.1
            
        return score

    def estimate_market_value(self, base_price: float, attrs: Dict[str, Any]) -> float:
        """Calculates deterministic Estimated Value (EV) adjusted for rarity."""
        multiplier = self.get_rare_score(attrs)
        return round(base_price * multiplier, 2)
