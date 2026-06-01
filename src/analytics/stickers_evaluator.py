from typing import List, Dict, Any

class StickerEvaluator:
    """
    Evaluates algorithmic Sticker Price Percentage (SPP).
    """
    
    RARE_STICKERS = {
        "Titan | Katowice 2014": 15000.0,
        "iBUYPOWER | Katowice 2014": 20000.0,
        "Reason Gaming | Katowice 2014": 10000.0,
        "Dignitas | Katowice 2014": 5000.0,
        "Crown (Foil)": 800.0,
        "Howl": 1200.0,
    }

    def __init__(self, spp_base: float = 0.05, spp_rare_bonus: float = 0.10):
        self.spp_base = spp_base
        self.spp_rare_bonus = spp_rare_bonus

    def calculate_added_value(self, stickers: List[Dict[str, Any]]) -> float:
        """
        Calculates the estimated USD value added by stickers using exponential decay for wear.
        """
        total_added_value = 0.0
        
        for s in stickers:
            name = s.get("name", "")
            try:
                wear = float(s.get("wear", 0.0))
            except (ValueError, TypeError):
                wear = 0.0
                
            unapplied_price = self.RARE_STICKERS.get(name, 0.0)
            
            if unapplied_price <= 0.0:
                continue
                
            wear_factor = max(0.0, 1.0 - (wear ** 0.5)) if wear > 0.0 else 1.0
            spp = self.spp_rare_bonus if unapplied_price > 1000.0 else self.spp_base
            
            added = unapplied_price * spp * wear_factor
            total_added_value += added
            
        return round(total_added_value, 2)

    def is_undervalued(self, item_price: float, base_price: float, stickers: List[Dict[str, Any]]) -> bool:
        """
        Validates if item is undervalued compared to baseline + SPP value.
        Margin of safety is strictly 5% (0.95 multiplier).
        """
        sticker_value = self.calculate_added_value(stickers)
        return item_price < (base_price + sticker_value) * 0.95
