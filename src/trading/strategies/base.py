"""Base trading strategy interface."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from src.trading.fees import FeeCalculator


class BaseStrategy(ABC):
    """Abstract base class for game-specific trading strategies."""

    def __init__(self, game_id: str, min_profit_percent: float = 5.0):
        """
        Initialize strategy.
        
        Args:
            game_id: Game identifier (csgo, dota2, etc.)
            min_profit_percent: Minimum desired profit percentage (e.g. 5.0 for 5%)
        """
        self.game_id = game_id
        self.min_profit_percent = Decimal(str(min_profit_percent)) / 100

    @abstractmethod
    async def should_buy(self, item_data: dict[str, Any]) -> bool:
        """
        Determine if an item is worth buying based on market data.
        
        Args:
            item_data: Dictionary containing DMarket item info, Steam price, and Waxpeer price.
        
        Returns:
            True if the item matches buy criteria.
        """
        pass

    def calculate_target_sell_price(self, buy_price: float | Decimal) -> Decimal:
        """
        Calculate the minimum sell price on Waxpeer to meet profit goals.
        
        Uses FeeCalculator with game-specific risk premiums.
        """
        return FeeCalculator.calculate_target_price(
            buy_price=buy_price,
            game=self.game_id,
            min_profit=float(self.min_profit_percent)
        )

    def calculate_roi(self, buy_price: float | Decimal, sell_price: float | Decimal) -> Decimal:
        """Calculate projected Return on Investment (ROI)."""
        profit = FeeCalculator.calculate_profit(buy_price, sell_price)
        real_cost = FeeCalculator.calculate_real_cost(buy_price)
        
        if real_cost == 0:
            return Decimal("0")
            
        return (profit / real_cost) * 100
