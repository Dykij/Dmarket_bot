"""Backtesting Module for Trading Strategies.

Provides backtesting capabilities:
- Historical price data simulation
- Strategy performance evaluation
- Risk metrics calculation
- Trade execution simulation

Based on SkillsMP `octobot` and `trading-best-practices` skills.

Usage:
    ```python
    from src.trading.backtester import Backtester, SimpleStrategy

    # Create backtester
    bt = Backtester(initial_balance=1000.0)

    # Add price data
    bt.load_prices(prices=[100, 102, 98, 105, 110, 108, 115])

    # Run strategy
    strategy = SimpleStrategy(buy_threshold=-0.02, sell_threshold=0.05)
    results = bt.run(strategy)

    print(results.total_return)  # 15.5%
    print(results.sharpe_ratio)  # 1.2
    ```

Created: January 23, 2026
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TradeAction(StrEnum):
    """Trade action types."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PositionType(StrEnum):
    """Position types."""

    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class PricePoint:
    """Single price point in time series."""

    timestamp: datetime
    price: float
    volume: float = 0.0

    # Optional OHLC data
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None


@dataclass
class Trade:
    """Executed trade record."""

    trade_id: int
    action: TradeAction
    price: float
    quantity: float
    timestamp: datetime

    # Fees
    fee: float = 0.0
    fee_percent: float = 0.0

    # P&L (for sells)
    pnl: float = 0.0
    pnl_percent: float = 0.0

    # Context
    balance_after: float = 0.0
    position_after: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "action": self.action.value,
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
            "fee": self.fee,
            "pnl": self.pnl,
            "pnl_percent": round(self.pnl_percent, 2),
        }


@dataclass
class BacktestConfig:
    """Backtesting configuration."""

    initial_balance: float = 1000.0
    fee_percent: float = 2.0  # Trading fee percentage
    slippage_percent: float = 0.5  # Slippage simulation
    max_position_percent: float = 100.0  # Max % of balance per trade
    allow_short: bool = False
    stop_loss_percent: float | None = None
    take_profit_percent: float | None = None


@dataclass
class BacktestResults:
    """Results from backtesting run."""

    # Performance
    total_return: float = 0.0
    total_return_percent: float = 0.0
    final_balance: float = 0.0

    # Trades
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L
    total_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0

    # Time metrics
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration_days: int = 0

    # Trades history
    trades: list[Trade] = field(default_factory=list)

    # Equity curve
    equity_curve: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_return_percent": round(self.total_return_percent, 2),
            "final_balance": round(self.final_balance, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "total_pnl": round(self.total_pnl, 2),
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "profit_factor": round(self.profit_factor, 2),
            "duration_days": self.duration_days,
        }

    def summary(self) -> str:
        """Generate text summary."""
        return f"""
📊 Backtest Results Summary
═══════════════════════════════════════
💰 Initial → Final: ${self.final_balance - self.total_return:.2f} → ${self.final_balance:.2f}
📈 Total Return: {self.total_return_percent:+.2f}%

🔄 Trades: {self.total_trades} ({self.winning_trades}W / {self.losing_trades}L)
🎯 Win Rate: {self.win_rate * 100:.1f}%

📉 Max Drawdown: {self.max_drawdown_percent:.2f}%
📐 Sharpe Ratio: {self.sharpe_ratio:.2f}
⚖️ Profit Factor: {self.profit_factor:.2f}

⏱️ Duration: {self.duration_days} days
═══════════════════════════════════════
"""


class Strategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def analyze(
        self,
        prices: list[float],
        current_idx: int,
        position: float,
        balance: float,
    ) -> tuple[TradeAction, float]:
        """Analyze and decide on trade action.

        Args:
            prices: Full price history
            current_idx: Current position in price history
            position: Current position quantity
            balance: Current cash balance

        Returns:
            Tuple of (action, quantity)
        """
        ...

    @property
    def name(self) -> str:
        """Strategy name."""
        return self.__class__.__name__


class SimpleStrategy(Strategy):
    """Simple momentum strategy.

    Buys when price drops by threshold, sells when rises by threshold.
    """

    def __init__(
        self,
        buy_threshold: float = -0.02,  # Buy when -2% from recent high
        sell_threshold: float = 0.05,  # Sell when +5% from entry
        lookback: int = 5,
    ) -> None:
        """Initialize strategy."""
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.lookback = lookback
        self._entry_price: float | None = None

    def analyze(
        self,
        prices: list[float],
        current_idx: int,
        position: float,
        balance: float,
    ) -> tuple[TradeAction, float]:
        """Analyze and decide."""
        if current_idx < self.lookback:
            return TradeAction.HOLD, 0.0

        current_price = prices[current_idx]
        recent_prices = prices[max(0, current_idx - self.lookback) : current_idx]
        recent_high = max(recent_prices)

        # No position - look to buy
        if position <= 0:
            change_from_high = (current_price - recent_high) / recent_high
            if change_from_high <= self.buy_threshold:
                # Buy with all available balance
                quantity = balance / current_price
                self._entry_price = current_price
                return TradeAction.BUY, quantity

        # Has position - look to sell
        elif self._entry_price:
            profit_pct = (current_price - self._entry_price) / self._entry_price
            if profit_pct >= self.sell_threshold:
                self._entry_price = None
                return TradeAction.SELL, position

        return TradeAction.HOLD, 0.0


class MeanReversionStrategy(Strategy):
    """Mean reversion strategy.

    Buys when price below moving average, sells when above.
    """

    def __init__(
        self,
        window: int = 20,
        buy_deviation: float = -0.05,  # Buy when 5% below MA
        sell_deviation: float = 0.05,  # Sell when 5% above MA
    ) -> None:
        """Initialize strategy."""
        self.window = window
        self.buy_deviation = buy_deviation
        self.sell_deviation = sell_deviation

    def analyze(
        self,
        prices: list[float],
        current_idx: int,
        position: float,
        balance: float,
    ) -> tuple[TradeAction, float]:
        """Analyze and decide."""
        if current_idx < self.window:
            return TradeAction.HOLD, 0.0

        current_price = prices[current_idx]
        ma = sum(prices[current_idx - self.window : current_idx]) / self.window
        deviation = (current_price - ma) / ma

        # No position - look to buy below MA
        if position <= 0 and deviation <= self.buy_deviation:
            quantity = balance / current_price
            return TradeAction.BUY, quantity

        # Has position - look to sell above MA
        if position > 0 and deviation >= self.sell_deviation:
            return TradeAction.SELL, position

        return TradeAction.HOLD, 0.0


class BreakoutStrategy(Strategy):
    """Breakout strategy.

    Buys on new highs, sells on stop-loss or trailing stop.
    """

    def __init__(
        self,
        lookback: int = 20,
        stop_loss: float = 0.05,  # 5% stop loss
        trailing_stop: float = 0.03,  # 3% trailing stop
    ) -> None:
        """Initialize strategy."""
        self.lookback = lookback
        self.stop_loss = stop_loss
        self.trailing_stop = trailing_stop
        self._entry_price: float | None = None
        self._highest_since_entry: float | None = None

    def analyze(
        self,
        prices: list[float],
        current_idx: int,
        position: float,
        balance: float,
    ) -> tuple[TradeAction, float]:
        """Analyze and decide."""
        if current_idx < self.lookback:
            return TradeAction.HOLD, 0.0

        current_price = prices[current_idx]
        lookback_prices = prices[current_idx - self.lookback : current_idx]
        lookback_high = max(lookback_prices)

        # No position - look for breakout
        if position <= 0:
            if current_price > lookback_high:
                quantity = balance / current_price
                self._entry_price = current_price
                self._highest_since_entry = current_price
                return TradeAction.BUY, quantity

        # Has position - check stops
        elif self._entry_price and self._highest_since_entry:
            # Update highest
            self._highest_since_entry = max(self._highest_since_entry, current_price)

            # Check stop loss
            loss_pct = (current_price - self._entry_price) / self._entry_price
            if loss_pct <= -self.stop_loss:
                self._entry_price = None
                self._highest_since_entry = None
                return TradeAction.SELL, position

            # Check trailing stop
            trail_pct = (current_price - self._highest_since_entry) / self._highest_since_entry
            if trail_pct <= -self.trailing_stop:
                self._entry_price = None
                self._highest_since_entry = None
                return TradeAction.SELL, position

        return TradeAction.HOLD, 0.0


class Backtester:
    """Backtesting engine for trading strategies."""

    def __init__(
        self,
        config: BacktestConfig | None = None,
        initial_balance: float = 1000.0,
    ) -> None:
        """Initialize backtester.

        Args:
            config: Backtesting configuration
            initial_balance: Initial cash balance
        """
        self.config = config or BacktestConfig(initial_balance=initial_balance)
        self._prices: list[PricePoint] = []
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset internal state."""
        self._balance = self.config.initial_balance
        self._position = 0.0
        self._entry_price: float | None = None
        self._trades: list[Trade] = []
        self._trade_counter = 0
        self._equity_curve: list[float] = []
        self._peak_equity = self.config.initial_balance

    def load_prices(
        self,
        prices: list[float] | list[PricePoint],
        start_date: datetime | None = None,
    ) -> None:
        """Load price data.

        Args:
            prices: List of prices or PricePoints
            start_date: Start date for timestamps
        """
        self._prices = []
        base_date = start_date or datetime.now(UTC)

        for i, p in enumerate(prices):
            if isinstance(p, PricePoint):
                self._prices.append(p)
            else:
                point = PricePoint(
                    timestamp=base_date + timedelta(hours=i),
                    price=float(p),
                )
                self._prices.append(point)

        logger.info("prices_loaded", count=len(self._prices))

    def run(self, strategy: Strategy) -> BacktestResults:
        """Run backtest with given strategy.

        Args:
            strategy: Trading strategy to test

        Returns:
            BacktestResults
        """
        if not self._prices:
            raise ValueError("No price data loaded. Call load_prices() first.")

        self._reset_state()
        prices = [p.price for p in self._prices]

        logger.info(
            "backtest_started",
            strategy=strategy.name,
            prices_count=len(prices),
            initial_balance=self.config.initial_balance,
        )

        # Run through each price point
        for i, price_point in enumerate(self._prices):
            current_price = price_point.price

            # Get strategy decision
            action, quantity = strategy.analyze(
                prices=prices,
                current_idx=i,
                position=self._position,
                balance=self._balance,
            )

            # Execute trade
            if action == TradeAction.BUY and quantity > 0:
                self._execute_buy(current_price, quantity, price_point.timestamp)
            elif action == TradeAction.SELL and quantity > 0:
                self._execute_sell(current_price, quantity, price_point.timestamp)

            # Check stop-loss / take-profit
            self._check_stops(current_price, price_point.timestamp)

            # Update equity curve
            equity = self._balance + (self._position * current_price)
            self._equity_curve.append(equity)

            # Track peak for drawdown
            self._peak_equity = max(self._peak_equity, equity)

        # Calculate results
        results = self._calculate_results()

        logger.info(
            "backtest_completed",
            strategy=strategy.name,
            total_return=f"{results.total_return_percent:.2f}%",
            trades=results.total_trades,
        )

        return results

    def _execute_buy(
        self,
        price: float,
        quantity: float,
        timestamp: datetime,
    ) -> None:
        """Execute buy order."""
        # Apply slippage
        execution_price = price * (1 + self.config.slippage_percent / 100)

        # Calculate cost
        cost = execution_price * quantity
        fee = cost * self.config.fee_percent / 100
        total_cost = cost + fee

        # Check if we have enough balance
        max_allowed = self._balance * self.config.max_position_percent / 100
        if total_cost > max_allowed:
            quantity = max_allowed / (execution_price * (1 + self.config.fee_percent / 100))
            cost = execution_price * quantity
            fee = cost * self.config.fee_percent / 100
            total_cost = cost + fee

        if total_cost > self._balance or quantity <= 0:
            return

        # Execute
        self._balance -= total_cost
        self._position += quantity
        self._entry_price = execution_price
        self._trade_counter += 1

        trade = Trade(
            trade_id=self._trade_counter,
            action=TradeAction.BUY,
            price=execution_price,
            quantity=quantity,
            timestamp=timestamp,
            fee=fee,
            fee_percent=self.config.fee_percent,
            balance_after=self._balance,
            position_after=self._position,
        )

        self._trades.append(trade)

    def _execute_sell(
        self,
        price: float,
        quantity: float,
        timestamp: datetime,
    ) -> None:
        """Execute sell order."""
        if self._position <= 0:
            return

        # Sell all or specified quantity
        sell_quantity = min(quantity, self._position)

        # Apply slippage
        execution_price = price * (1 - self.config.slippage_percent / 100)

        # Calculate proceeds
        proceeds = execution_price * sell_quantity
        fee = proceeds * self.config.fee_percent / 100
        net_proceeds = proceeds - fee

        # Calculate P&L
        pnl = 0.0
        pnl_percent = 0.0
        if self._entry_price:
            pnl = net_proceeds - (self._entry_price * sell_quantity)
            pnl_percent = (execution_price - self._entry_price) / self._entry_price * 100

        # Execute
        self._balance += net_proceeds
        self._position -= sell_quantity
        self._trade_counter += 1

        if self._position <= 0:
            self._entry_price = None

        trade = Trade(
            trade_id=self._trade_counter,
            action=TradeAction.SELL,
            price=execution_price,
            quantity=sell_quantity,
            timestamp=timestamp,
            fee=fee,
            fee_percent=self.config.fee_percent,
            pnl=pnl,
            pnl_percent=pnl_percent,
            balance_after=self._balance,
            position_after=self._position,
        )

        self._trades.append(trade)

    def _check_stops(self, current_price: float, timestamp: datetime) -> None:
        """Check and execute stop-loss / take-profit."""
        if self._position <= 0 or not self._entry_price:
            return

        change_pct = (current_price - self._entry_price) / self._entry_price

        # Stop-loss
        if self.config.stop_loss_percent:
            if change_pct <= -self.config.stop_loss_percent / 100:
                self._execute_sell(current_price, self._position, timestamp)
                return

        # Take-profit
        if self.config.take_profit_percent:
            if change_pct >= self.config.take_profit_percent / 100:
                self._execute_sell(current_price, self._position, timestamp)

    def _calculate_results(self) -> BacktestResults:
        """Calculate backtest results."""
        if not self._prices:
            return BacktestResults()

        # Final equity
        final_price = self._prices[-1].price
        final_equity = self._balance + (self._position * final_price)
        total_return = final_equity - self.config.initial_balance
        total_return_pct = (total_return / self.config.initial_balance) * 100

        # Trade statistics
        sell_trades = [t for t in self._trades if t.action == TradeAction.SELL]
        winning = [t for t in sell_trades if t.pnl > 0]
        losing = [t for t in sell_trades if t.pnl < 0]

        total_pnl = sum(t.pnl for t in sell_trades)
        win_rate = len(winning) / len(sell_trades) if sell_trades else 0.0

        max_profit = max((t.pnl for t in sell_trades), default=0.0)
        max_loss = min((t.pnl for t in sell_trades), default=0.0)

        # Profit factor
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Drawdown
        max_drawdown = 0.0
        peak = self.config.initial_balance
        for equity in self._equity_curve:
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)

        max_drawdown_pct = (max_drawdown / peak * 100) if peak > 0 else 0.0

        # Sharpe ratio (simplified)
        if len(self._equity_curve) > 1:
            returns = [
                (self._equity_curve[i] - self._equity_curve[i - 1]) / self._equity_curve[i - 1]
                for i in range(1, len(self._equity_curve))
            ]
            if returns:
                avg_return = sum(returns) / len(returns)
                variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
                std_dev = variance**0.5
                # Annualized (assuming hourly data)
                sharpe = (avg_return * 8760) / (std_dev * (8760**0.5)) if std_dev > 0 else 0.0
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        # Duration
        start_date = self._prices[0].timestamp
        end_date = self._prices[-1].timestamp
        duration = (end_date - start_date).days

        return BacktestResults(
            total_return=total_return,
            total_return_percent=total_return_pct,
            final_balance=final_equity,
            total_trades=len(self._trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=total_pnl / len(sell_trades) if sell_trades else 0.0,
            max_profit=max_profit,
            max_loss=max_loss,
            max_drawdown=max_drawdown,
            max_drawdown_percent=max_drawdown_pct,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration,
            trades=self._trades,
            equity_curve=self._equity_curve,
        )

    def compare_strategies(
        self,
        strategies: list[Strategy],
    ) -> dict[str, BacktestResults]:
        """Compare multiple strategies.

        Args:
            strategies: List of strategies to compare

        Returns:
            Dict of strategy_name -> results
        """
        results = {}

        for strategy in strategies:
            result = self.run(strategy)
            results[strategy.name] = result

        # Log comparison
        logger.info("strategy_comparison")
        for name, res in results.items():
            logger.info(
                f"  {name}",
                return_pct=f"{res.total_return_percent:.2f}%",
                sharpe=f"{res.sharpe_ratio:.2f}",
                drawdown=f"{res.max_drawdown_percent:.2f}%",
            )

        return results


# Factory functions
def create_backtester(
    initial_balance: float = 1000.0,
    fee_percent: float = 2.0,
    slippage_percent: float = 0.5,
) -> Backtester:
    """Create backtester instance.

    Args:
        initial_balance: Starting balance
        fee_percent: Trading fee %
        slippage_percent: Slippage %

    Returns:
        Backtester instance
    """
    config = BacktestConfig(
        initial_balance=initial_balance,
        fee_percent=fee_percent,
        slippage_percent=slippage_percent,
    )
    return Backtester(config=config)


def create_simple_strategy(
    buy_threshold: float = -0.02,
    sell_threshold: float = 0.05,
) -> SimpleStrategy:
    """Create simple momentum strategy.

    Args:
        buy_threshold: Buy threshold (negative = dip)
        sell_threshold: Sell threshold (positive = profit)

    Returns:
        SimpleStrategy instance
    """
    return SimpleStrategy(
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )
