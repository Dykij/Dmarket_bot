"""
strategies.py — Trading strategy ABC and a sample strategy.

Implement `TradingStrategy.should_buy` and `should_sell` to plug in a
new strategy. The `SimpleArbitrageStrategy` is provided as a working
example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analytics.historical_data import PriceHistory

from .models import Position


class TradingStrategy(ABC):
    """Base class for trading strategies.

    Implement this to create custom trading strategies for backtesting.
    """

    name: str = "BaseStrategy"

    @abstractmethod
    def should_buy(
        self,
        price_history: PriceHistory,
        current_price: Decimal,
        balance: Decimal,
        positions: dict[str, Position],
    ) -> tuple[bool, Decimal, int]:
        """Determine if should buy.

        Args:
            price_history: Historical price data
            current_price: Current market price
            balance: Available balance
            positions: Current positions

        Returns:
            Tuple of (should_buy, price_to_buy_at, quantity)
        """

    @abstractmethod
    def should_sell(
        self,
        price_history: PriceHistory,
        current_price: Decimal,
        position: Position,
    ) -> tuple[bool, Decimal, int]:
        """Determine if should sell.

        Args:
            price_history: Historical price data
            current_price: Current market price
            position: Current position

        Returns:
            Tuple of (should_sell, price_to_sell_at, quantity)
        """


class SimpleArbitrageStrategy(TradingStrategy):
    """Simple arbitrage strategy based on price deviation.

    Buys when price is X% below average and sells when Y% above purchase.
    """

    name = "SimpleArbitrage"

    def __init__(
        self,
        buy_threshold: float = 0.05,  # Buy when 5% below average
        sell_margin: float = 0.08,  # Sell when 8% above purchase
        max_position_pct: float = 0.1,  # Max 10% of balance per position
        dmarket_fee: float = 0.07,  # 7% DMarket fee
    ) -> None:
        """Initialize strategy.

        Args:
            buy_threshold: Percentage below average to buy
            sell_margin: Target profit margin
            max_position_pct: Max percentage of balance per position
            dmarket_fee: DMarket trading fee
        """
        self.buy_threshold = buy_threshold
        self.sell_margin = sell_margin
        self.max_position_pct = max_position_pct
        self.dmarket_fee = dmarket_fee

    def should_buy(
        self,
        price_history: PriceHistory,
        current_price: Decimal,
        balance: Decimal,
        positions: dict[str, Position],
    ) -> tuple[bool, Decimal, int]:
        """Check if should buy based on price deviation."""
        # Don't buy if already have position
        if price_history.title in positions:
            return False, Decimal(0), 0

        avg_price = price_history.average_price
        if avg_price == 0:
            return False, Decimal(0), 0

        # Buy if price is below threshold
        price_ratio = float(current_price / avg_price)
        if price_ratio > (1 - self.buy_threshold):
            return False, Decimal(0), 0

        # Calculate position size
        max_spend = balance * Decimal(str(self.max_position_pct))
        if max_spend < current_price:
            return False, Decimal(0), 0

        quantity = int(max_spend / current_price)
        if quantity < 1:
            return False, Decimal(0), 0

        return True, current_price, quantity

    def should_sell(
        self,
        price_history: PriceHistory,
        current_price: Decimal,
        position: Position,
    ) -> tuple[bool, Decimal, int]:
        """Check if should sell based on profit margin."""
        # Calculate required sell price for target margin
        target_price = position.average_cost * Decimal(
            str(1 + self.sell_margin + self.dmarket_fee)
        )

        if current_price >= target_price:
            return True, current_price, position.quantity

        # Stop-loss at -10%
        stop_loss_price = position.average_cost * Decimal("0.90")
        if current_price <= stop_loss_price:
            return True, current_price, position.quantity

        return False, Decimal(0), 0
