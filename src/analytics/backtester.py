"""Backtesting engine for trading strategies.

Provides a framework for testing trading strategies on historical data.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .historical_data import PriceHistory, PricePoint


logger = logging.getLogger(__name__)


class TradeType(StrEnum):
    """Type of trade."""

    BUY = "buy"
    SELL = "sell"


@dataclass
class Trade:
    """A single trade in backtesting.

    Attributes:
        trade_type: Buy or sell
        item_title: Item name
        price: Trade price
        quantity: Number of items
        timestamp: When trade occurred
        fees: Trading fees
    """

    trade_type: TradeType
    item_title: str
    price: Decimal
    quantity: int
    timestamp: datetime
    fees: Decimal = Decimal(0)

    @property
    def total_cost(self) -> Decimal:
        """Total cost including fees."""
        return self.price * self.quantity + self.fees

    @property
    def net_amount(self) -> Decimal:
        """Net amount (positive for buys, negative for sells after fees)."""
        if self.trade_type == TradeType.BUY:
            return -self.total_cost
        return self.price * self.quantity - self.fees


@dataclass
class Position:
    """A position held in backtesting.

    Attributes:
        item_title: Item name
        quantity: Number of items held
        average_cost: Average purchase price
        created_at: When position was opened
    """

    item_title: str
    quantity: int
    average_cost: Decimal
    created_at: datetime

    @property
    def total_value(self) -> Decimal:
        """Total value at average cost."""
        return self.average_cost * self.quantity

    def update(self, quantity: int, price: Decimal) -> None:
        """Update position with new purchase.

        Args:
            quantity: Additional quantity
            price: Price per item
        """
        total_cost = self.average_cost * self.quantity + price * quantity
        self.quantity += quantity
        if self.quantity > 0:
            self.average_cost = total_cost / self.quantity


@dataclass
class BacktestResult:
    """Results of a backtest run.

    Attributes:
        strategy_name: Name of the strategy tested
        start_date: Start of backtest period
        end_date: End of backtest period
        initial_balance: Starting balance
        final_balance: Ending balance
        total_trades: Number of trades executed
        profitable_trades: Number of profitable trades
        total_profit: Total profit/loss
        max_drawdown: Maximum drawdown percentage
        sharpe_ratio: Risk-adjusted return metric
        win_rate: Percentage of profitable trades
        trades: List of all trades
    """

    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    final_balance: Decimal
    total_trades: int
    profitable_trades: int
    total_profit: Decimal
    max_drawdown: Decimal
    sharpe_ratio: float
    win_rate: float
    trades: list[Trade] = field(default_factory=list)
    positions_closed: int = 0

    @property
    def total_return(self) -> float:
        """Total return as percentage."""
        if self.initial_balance == 0:
            return 0.0
        return float(
            (self.final_balance - self.initial_balance) / self.initial_balance * 100
        )

    @property
    def avg_profit_per_trade(self) -> Decimal:
        """Average profit per trade."""
        if self.total_trades == 0:
            return Decimal(0)
        return self.total_profit / self.total_trades

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_balance": float(self.initial_balance),
            "final_balance": float(self.final_balance),
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "total_profit": float(self.total_profit),
            "total_return": self.total_return,
            "max_drawdown": float(self.max_drawdown),
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "avg_profit_per_trade": float(self.avg_profit_per_trade),
            "positions_closed": self.positions_closed,
        }


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
            balance: AvAlgolable balance
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


class Backtester:
    """Backtesting engine for trading strategies.

    Simulates trading on historical data to evaluate strategy performance.
    """

    def __init__(
        self,
        fee_rate: float = 0.07,  # 7% DMarket fee
    ) -> None:
        """Initialize backtester.

        Args:
            fee_rate: Trading fee rate
        """
        self.fee_rate = fee_rate

    async def run(
        self,
        strategy: TradingStrategy,
        price_histories: dict[str, PriceHistory],
        start_date: datetime,
        end_date: datetime,
        initial_balance: Decimal,
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            strategy: Trading strategy to test
            price_histories: Historical price data by item title
            start_date: Start of backtest period
            end_date: End of backtest period
            initial_balance: Starting balance

        Returns:
            BacktestResult with performance metrics
        """
        logger.info(
            "starting_backtest",
            extra={
                "strategy": strategy.name,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "initial_balance": float(initial_balance),
            },
        )

        balance = initial_balance
        positions: dict[str, Position] = {}
        trades: list[Trade] = []
        balance_history: list[Decimal] = [initial_balance]
        profitable_trades = 0
        positions_closed = 0

        # Simulate each day in the period
        current_date = start_date
        while current_date <= end_date:
            for title, history in price_histories.items():
                # Find price point for current date
                price_point = self._get_price_at_date(history, current_date)
                if not price_point:
                    continue

                current_price = price_point.price

                # Check sell signals first
                if title in positions:
                    should_sell, sell_price, quantity = strategy.should_sell(
                        history, current_price, positions[title]
                    )

                    if should_sell and quantity > 0:
                        trade = self._execute_sell(
                            title, sell_price, quantity, current_date, positions[title]
                        )
                        trades.append(trade)
                        balance += trade.net_amount

                        # Track profit
                        profit = sell_price - positions[title].average_cost
                        if profit > 0:
                            profitable_trades += 1

                        # Close position
                        positions[title].quantity -= quantity
                        if positions[title].quantity <= 0:
                            del positions[title]
                            positions_closed += 1

                # Check buy signals
                should_buy, buy_price, quantity = strategy.should_buy(
                    history, current_price, balance, positions
                )

                if should_buy and quantity > 0:
                    trade = self._execute_buy(title, buy_price, quantity, current_date)
                    if trade.total_cost <= balance:
                        trades.append(trade)
                        balance += trade.net_amount

                        # Update or create position
                        if title in positions:
                            positions[title].update(quantity, buy_price)
                        else:
                            positions[title] = Position(
                                item_title=title,
                                quantity=quantity,
                                average_cost=buy_price,
                                created_at=current_date,
                            )

            # Track balance at end of day
            balance_history.append(balance)
            current_date += timedelta(days=1)

        # Calculate final balance including open positions
        final_balance = balance
        for position in positions.values():
            # Estimate value at last known price
            history = price_histories.get(position.item_title)
            if history is not None and history.points:
                last_price = history.points[-1].price
                final_balance += last_price * position.quantity

        # Calculate metrics
        total_profit = final_balance - initial_balance
        max_drawdown = self._calculate_max_drawdown(balance_history)
        sharpe_ratio = self._calculate_sharpe_ratio(balance_history)
        win_rate = (profitable_trades / len(trades) * 100) if trades else 0.0

        result = BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            profitable_trades=profitable_trades,
            total_profit=total_profit,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            trades=trades,
            positions_closed=positions_closed,
        )

        logger.info(
            "backtest_completed",
            extra={
                "strategy": strategy.name,
                "total_trades": len(trades),
                "total_profit": float(total_profit),
                "win_rate": win_rate,
            },
        )

        return result

    def _get_price_at_date(
        self,
        history: PriceHistory,
        date: datetime,
    ) -> PricePoint | None:
        """Get price point closest to given date.

        Args:
            history: Price history
            date: Target date

        Returns:
            Closest PricePoint or None
        """
        if not history.points:
            return None

        # Find closest point
        closest: PricePoint | None = None
        min_diff = timedelta(days=365)

        for point in history.points:
            diff = abs(point.timestamp - date)
            if diff < min_diff:
                min_diff = diff
                closest = point

        # Only return if within 1 day
        if min_diff <= timedelta(days=1):
            return closest

        return None

    def _execute_buy(
        self,
        title: str,
        price: Decimal,
        quantity: int,
        timestamp: datetime,
    ) -> Trade:
        """Execute a buy trade.

        Args:
            title: Item title
            price: Buy price
            quantity: Number of items
            timestamp: Trade time

        Returns:
            Trade object
        """
        return Trade(
            trade_type=TradeType.BUY,
            item_title=title,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            fees=Decimal(0),  # No fees on buy
        )

    def _execute_sell(
        self,
        title: str,
        price: Decimal,
        quantity: int,
        timestamp: datetime,
        position: Position,
    ) -> Trade:
        """Execute a sell trade.

        Args:
            title: Item title
            price: Sell price
            quantity: Number of items
            timestamp: Trade time
            position: Position being sold

        Returns:
            Trade object
        """
        gross = price * quantity
        fees = gross * Decimal(str(self.fee_rate))

        return Trade(
            trade_type=TradeType.SELL,
            item_title=title,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            fees=fees,
        )

    def _calculate_max_drawdown(self, balance_history: list[Decimal]) -> Decimal:
        """Calculate maximum drawdown.

        Args:
            balance_history: List of balance values over time

        Returns:
            Maximum drawdown as percentage
        """
        if len(balance_history) < 2:
            return Decimal(0)

        peak = balance_history[0]
        max_drawdown = Decimal(0)

        for balance in balance_history[1:]:
            if balance > peak:
                peak = balance
            else:
                drawdown = (peak - balance) / peak if peak > 0 else Decimal(0)
                max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown * 100

    def _calculate_sharpe_ratio(
        self,
        balance_history: list[Decimal],
        risk_free_rate: float = 0.02,  # 2% annual risk-free rate
    ) -> float:
        """Calculate Sharpe ratio.

        Args:
            balance_history: List of balance values over time
            risk_free_rate: Annual risk-free rate

        Returns:
            Sharpe ratio
        """
        if len(balance_history) < 2:
            return 0.0

        # Calculate daily returns
        returns: list[float] = []
        for i in range(1, len(balance_history)):
            if balance_history[i - 1] > 0:
                daily_return = float(
                    (balance_history[i] - balance_history[i - 1])
                    / balance_history[i - 1]
                )
                returns.append(daily_return)

        if not returns:
            return 0.0

        # Calculate mean and std dev
        mean_return = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0

        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance**0.5

        if std_dev == 0:
            return 0.0

        # Annualize (assuming 365 trading days)
        daily_rf = (1 + risk_free_rate) ** (1 / 365) - 1
        excess_return = mean_return - daily_rf

        # Sharpe ratio (annualized)
        sharpe = (excess_return * (365**0.5)) / (std_dev * (365**0.5))

        return float(round(sharpe, 2))


__all__ = [
    "BacktestResult",
    "Backtester",
    "Position",
    "SimpleArbitrageStrategy",
    "Trade",
    "TradeType",
    "TradingStrategy",
]
