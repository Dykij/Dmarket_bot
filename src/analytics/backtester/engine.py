"""
engine.py — Backtester: simulates a strategy over historical price data.

The main entry point is `Backtester.run(strategy, ...)`. It uses the
metric functions from `metrics.py` and the dataclasses from `models.py`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from .metrics import calculate_max_drawdown, calculate_sharpe_ratio
from .models import (
    BacktestResult,
    Position,
    Trade,
    TradeType,
)
from .strategies import TradingStrategy

if TYPE_CHECKING:
    from src.analytics.historical_data import PriceHistory, PricePoint

logger = logging.getLogger(__name__)


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
            pos_history = price_histories.get(position.item_title)
            if pos_history is not None and pos_history.points:
                last_price = pos_history.points[-1].price
                final_balance += last_price * position.quantity

        # Calculate metrics
        total_profit = final_balance - initial_balance
        max_drawdown = calculate_max_drawdown(balance_history)
        sharpe_ratio = calculate_sharpe_ratio(balance_history)
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
