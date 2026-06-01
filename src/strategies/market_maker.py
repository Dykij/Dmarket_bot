from typing import Dict, Any
from src.strategies.base import BaseStrategy
from src.config import Config

class MarketMaker(BaseStrategy):
    def __init__(self):
        super().__init__("MarketMaker")

    def evaluate_opportunity(self, market_data: Dict[str, Any], current_balance: float = 50.0) -> Dict[str, Any]:
        """
        Market Maker logic: Find the spread, undercut the lowest Ask, and calculate
        position size dynamically based on available balance and volatility proxy.
        """
        # (This combines the logic previously scattered around trader.py)
        
        item_name = market_data.get("title", "UnknownItem")
        best_ask = market_data.get("best_ask", 0.0)
        best_bid = market_data.get("best_bid", 0.0)
        
        # Volatility proxy: higher spread means higher volatility/risk
        spread_pct = 0.0
        if best_bid > 0:
            spread_pct = ((best_ask - best_bid) / best_bid) * 100.0

        target_price = best_ask - 0.01

        # Calculate fees
        estimated_fee = target_price * Config.FEE_RATE
        net_profit = target_price - estimated_fee - target_price

        if spread_pct >= Config.MIN_SPREAD_PCT:
            # We have a valid opportunity
            # Using spread_pct as a volatility proxy (higher spread = more risk adjustment)
            volatility_proxy = max(1.0, spread_pct / Config.MIN_SPREAD_PCT)
            
            quantity = self.calculate_position_size(
                current_balance=current_balance, 
                item_price=target_price,
                volatility_score=volatility_proxy
            )
            
            if quantity > 0:
                self.logger.info(f"Targeting {quantity}x {item_name} at ${target_price:.2f} (Spread: {spread_pct:.2f}%)")
                return {
                    "action": "place_target",
                    "target_price": target_price,
                    "quantity": quantity
                }
        
        return {"action": "none"}
