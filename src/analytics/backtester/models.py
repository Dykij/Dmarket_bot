"""
models.py — Dataclasses and enums for the backtester.

Trade: a single buy/sell in a backtest.
Position: held items, with weighted-average cost.
BacktestResult: aggregated metrics from a backtest run.
TradeType: enum of buy vs sell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


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
