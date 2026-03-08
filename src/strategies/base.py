from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
from src.config import Config

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Strategy.{name}")

    def calculate_position_size(self, current_balance: float, item_price: float, volatility_score: float = 1.0) -> int:
        """
        Dynamic Position Sizing (Pseudo-Kelly Criterion)
        Volatile items get smaller position sizes to protect capital.
        """
        if not Config.USE_DYNAMIC_SIZING or current_balance <= 0:
            return 1 # Default

        max_risk_amount = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)
        
        # Adjust risk based on volatility (higher volatility = lower risk allowed)
        adjusted_risk_amount = max_risk_amount / volatility_score

        if item_price > adjusted_risk_amount:
            self.logger.warning(f"Item price ${item_price} exceeds adjusted risk tolerance ${adjusted_risk_amount:.2f}")
            return 0 # Do not buy

        # How many items can we buy within our risk limit?
        quantity = int(adjusted_risk_amount // item_price)
        return max(1, quantity) # Buy at least 1 if it passed the check

    @abstractmethod
    def evaluate_opportunity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strategy core logic to analyze market data and return an action plan.
        Should return a dictionary containing 'action' (buy/none), 'target_price', and 'quantity'.
        """
        pass
