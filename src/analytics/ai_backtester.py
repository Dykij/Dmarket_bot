"""AI-Powered Automated Backtesting Module.

Модуль автоматизированного бэктестирования торговых стратегий
с использованием машинного обучения. Симулирует исторические сделки
и оценивает эффективность стратегий.

SKILL: AI Backtesting
Category: Research, Data & AI
Status: Phase 3 Implementation

Документация: src/analytics/SKILL_BACKTESTING.md
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Trade:
    """Simulated trade in backtest."""

    timestamp: datetime
    item_title: str
    action: str  # "buy" or "sell"
    price: float
    quantity: int = 1
    profit: float = 0.0
    commission: float = 0.0


@dataclass
class BacktestResult:
    """Result of backtest simulation.

    Attributes:
        total_trades: Total number of trades executed
        profitable_trades: Number of profitable trades
        total_profit: Net profit/loss (USD)
        roi_percent: Return on investment (%)
        sharpe_ratio: Risk-adjusted return metric
        max_drawdown: Maximum loss from peak (%)
        win_rate: Percentage of winning trades
        trades: List of all trades
    """

    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    roi_percent: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    trades: list[Trade] = field(default_factory=list)
    initial_balance: float = 0.0
    final_balance: float = 0.0


class AIBacktester:
    """AI-powered backtesting system for trading strategies.

    Simulates trading strategies on historical data with ML enhancement
    to evaluate performance before risking real capital.

    Attributes:
        commission_percent: Trading commission (default: 7% for DMarket)
        initial_balance: Starting balance for simulation
    """

    def __init__(
        self,
        initial_balance: float = 100.0,
        commission_percent: float = 7.0,
    ):
        """Initialize AI Backtester.

        Args:
            initial_balance: Starting balance for simulation (USD)
            commission_percent: Trading commission percentage
        """
        self.initial_balance = initial_balance
        self.commission_percent = commission_percent
        self.current_balance = initial_balance

        logger.info(
            "ai_backtester_initialized",
            initial_balance=initial_balance,
            commission=commission_percent,
        )

    async def backtest_arbitrage_strategy(
        self,
        historical_data: list[dict[str, Any]],
        strategy: str = "standard",
        min_profit_percent: float = 5.0,
    ) -> BacktestResult:
        """Backtest arbitrage strategy on historical data.

        Args:
            historical_data: List of historical market items with prices
            strategy: Strategy type ("conservative", "standard", "aggressive")
            min_profit_percent: Minimum profit threshold (%)

        Returns:
            BacktestResult with performance metrics

        Example:
            >>> backtester = AIBacktester(initial_balance=100.0)
            >>> result = await backtester.backtest_arbitrage_strategy(
            ...     historical_data=market_history,
            ...     strategy="standard",
            ...     min_profit_percent=5.0
            ... )
            >>> print(f"ROI: {result.roi_percent:.1f}%")
        """
        logger.info(
            "starting_backtest",
            data_points=len(historical_data),
            strategy=strategy,
            min_profit=min_profit_percent,
        )

        # Reset balance
        self.current_balance = self.initial_balance
        trades: list[Trade] = []
        positions: dict[str, dict[str, Any]] = {}

        # Strategy parameters
        strategy_params = self._get_strategy_params(strategy)

        # Simulate trades
        for i, data_point in enumerate(historical_data):
            timestamp = data_point.get("timestamp", datetime.now())
            item_id = data_point.get("itemId", f"item_{i}")
            title = data_point.get("title", "Unknown Item")
            current_price = self._get_price(data_point.get("price", {}))
            suggested_price = self._get_price(data_point.get("suggestedPrice", {}))

            # Check if we can buy (arbitrage opportunity)
            if item_id not in positions and current_price > 0:
                profit_margin = self._calculate_profit_margin(
                    current_price, suggested_price
                )

                # Apply strategy-specific logic
                should_buy = (
                    profit_margin >= min_profit_percent
                    and self.current_balance >= current_price
                    and profit_margin >= strategy_params["min_margin"]
                )

                if should_buy:
                    # Execute buy
                    trade = await self._execute_buy(
                        timestamp=timestamp,
                        item_id=item_id,
                        title=title,
                        price=current_price,
                    )
                    if trade:
                        trades.append(trade)
                        positions[item_id] = {
                            "buy_price": current_price,
                            "buy_timestamp": timestamp,
                            "title": title,
                        }

            # Check if we should sell existing position
            elif item_id in positions:
                position = positions[item_id]
                buy_price = position["buy_price"]

                # Sell if suggested price is higher or after holding period
                holding_time = (timestamp - position["buy_timestamp"]).total_seconds()
                should_sell = (
                    suggested_price > buy_price * 1.05  # 5% profit
                    or holding_time > strategy_params["max_hold_seconds"]
                )

                if should_sell:
                    # Execute sell
                    sell_price = max(suggested_price, current_price)
                    trade = await self._execute_sell(
                        timestamp=timestamp,
                        item_id=item_id,
                        title=position["title"],
                        price=sell_price,
                        buy_price=buy_price,
                    )
                    if trade:
                        trades.append(trade)
                        del positions[item_id]

        # Calculate metrics
        result = self._calculate_metrics(trades)

        logger.info(
            "backtest_complete",
            total_trades=result.total_trades,
            roi_percent=result.roi_percent,
            win_rate=result.win_rate,
        )

        return result

    async def _execute_buy(
        self,
        timestamp: datetime,
        item_id: str,
        title: str,
        price: float,
    ) -> Trade | None:
        """Execute buy trade in simulation.

        Args:
            timestamp: Trade timestamp
            item_id: Item identifier
            title: Item title
            price: Buy price

        Returns:
            Trade object or None if insufficient balance
        """
        if self.current_balance < price:
            return None

        commission = price * (self.commission_percent / 100)
        total_cost = price + commission

        self.current_balance -= total_cost

        return Trade(
            timestamp=timestamp,
            item_title=title,
            action="buy",
            price=price,
            commission=commission,
            profit=0.0,
        )

    async def _execute_sell(
        self,
        timestamp: datetime,
        item_id: str,
        title: str,
        price: float,
        buy_price: float,
    ) -> Trade | None:
        """Execute sell trade in simulation.

        Args:
            timestamp: Trade timestamp
            item_id: Item identifier
            title: Item title
            price: Sell price
            buy_price: Original buy price

        Returns:
            Trade object
        """
        commission = price * (self.commission_percent / 100)
        net_proceeds = price - commission
        profit = net_proceeds - buy_price

        self.current_balance += net_proceeds

        return Trade(
            timestamp=timestamp,
            item_title=title,
            action="sell",
            price=price,
            commission=commission,
            profit=profit,
        )

    def _calculate_metrics(self, trades: list[Trade]) -> BacktestResult:
        """Calculate backtest performance metrics.

        Args:
            trades: List of all trades

        Returns:
            BacktestResult with calculated metrics
        """
        if not trades:
            return BacktestResult(
                initial_balance=self.initial_balance,
                final_balance=self.current_balance,
            )

        # Count trades
        sell_trades = [t for t in trades if t.action == "sell"]
        profitable_trades = sum(1 for t in sell_trades if t.profit > 0)

        # Calculate total profit
        total_profit = sum(t.profit for t in sell_trades)

        # Calculate ROI
        roi_percent = (total_profit / self.initial_balance) * 100

        # Calculate win rate
        win_rate = (
            (profitable_trades / len(sell_trades) * 100) if sell_trades else 0.0
        )

        # Simple Sharpe ratio approximation
        if sell_trades:
            returns = [t.profit / t.price for t in sell_trades]
            avg_return = sum(returns) / len(returns)
            std_return = (
                sum((r - avg_return) ** 2 for r in returns) / len(returns)
            ) ** 0.5
            sharpe_ratio = avg_return / std_return if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(trades)

        return BacktestResult(
            total_trades=len(trades),
            profitable_trades=profitable_trades,
            total_profit=total_profit,
            roi_percent=roi_percent,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trades=trades,
            initial_balance=self.initial_balance,
            final_balance=self.current_balance,
        )

    def _calculate_max_drawdown(self, trades: list[Trade]) -> float:
        """Calculate maximum drawdown percentage.

        Args:
            trades: List of trades

        Returns:
            Maximum drawdown as percentage
        """
        if not trades:
            return 0.0

        # Track balance over time
        balance = self.initial_balance
        peak_balance = balance
        max_drawdown = 0.0

        for trade in trades:
            if trade.action == "buy":
                balance -= trade.price + trade.commission
            else:  # sell
                balance += trade.price - trade.commission

            # Update peak
            peak_balance = max(peak_balance, balance)

            # Calculate drawdown
            if peak_balance > 0:
                drawdown = ((peak_balance - balance) / peak_balance) * 100
                max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _get_strategy_params(self, strategy: str) -> dict[str, Any]:
        """Get parameters for strategy type.

        Args:
            strategy: Strategy name

        Returns:
            Dictionary of strategy parameters
        """
        strategies = {
            "conservative": {
                "min_margin": 10.0,  # 10% minimum profit
                "max_hold_seconds": 86400,  # 24 hours
            },
            "standard": {
                "min_margin": 5.0,  # 5% minimum profit
                "max_hold_seconds": 43200,  # 12 hours
            },
            "aggressive": {
                "min_margin": 3.0,  # 3% minimum profit
                "max_hold_seconds": 14400,  # 4 hours
            },
        }

        return strategies.get(strategy, strategies["standard"])

    def _calculate_profit_margin(
        self, buy_price: float, sell_price: float
    ) -> float:
        """Calculate profit margin percentage.

        Args:
            buy_price: Purchase price
            sell_price: Selling price

        Returns:
            Profit margin as percentage
        """
        if buy_price <= 0:
            return 0.0

        commission = sell_price * (self.commission_percent / 100)
        net_profit = sell_price - buy_price - commission

        return (net_profit / buy_price) * 100

    def _get_price(self, price_data: dict[str, Any]) -> float:
        """Extract price from API response format.

        Args:
            price_data: Price dictionary from API

        Returns:
            Price in USD
        """
        if isinstance(price_data, dict):
            price_cents = price_data.get("USD", 0)
            return price_cents / 100.0
        return 0.0


# Factory function
def create_ai_backtester(
    initial_balance: float = 100.0,
    commission_percent: float = 7.0,
) -> AIBacktester:
    """Create AI Backtester with configuration.

    Args:
        initial_balance: Starting balance for simulations
        commission_percent: Trading commission

    Returns:
        Initialized AIBacktester

    Example:
        >>> backtester = create_ai_backtester(initial_balance=500.0)
        >>> result = await backtester.backtest_arbitrage_strategy(data)
    """
    return AIBacktester(
        initial_balance=initial_balance,
        commission_percent=commission_percent,
    )
