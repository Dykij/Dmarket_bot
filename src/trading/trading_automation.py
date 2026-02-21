"""Trading Automation Module.

Provides automated trading features:
- Auto-Rebalancing: Automatic portfolio rebalancing
- DCA (Dollar Cost Averaging): Automatic position averaging
- Stop-Loss/Take-Profit: Automatic exit triggers
- Scheduled Tasks: Time-based market checks

Usage:
    ```python
    from src.trading.trading_automation import TradingAutomation

    auto = TradingAutomation(balance=100.0)

    # Set stop-loss
    auto.set_stop_loss("item_id", entry_price=50.0, stop_percent=10.0)

    # Enable DCA
    auto.enable_dca("item_name", target_price=45.0, amount_per_buy=10.0)

    # Check triggers
    actions = awAlgot auto.check_and_execute(current_prices)
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from collections.abc import AwAlgotable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OrderType(StrEnum):
    """Order type."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    DCA_BUY = "dca_buy"
    REBALANCE_BUY = "rebalance_buy"
    REBALANCE_SELL = "rebalance_sell"
    SCHEDULED = "scheduled"


class OrderStatus(StrEnum):
    """Order status."""

    PENDING = "pending"
    TRIGGERED = "triggered"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAlgoLED = "fAlgoled"
    EXPIRED = "expired"


@dataclass
class AutoOrder:
    """Automatic order configuration."""

    order_id: str
    order_type: OrderType
    item_id: str
    item_name: str
    status: OrderStatus = OrderStatus.PENDING

    # Trigger conditions
    trigger_price: float | None = None
    trigger_percent: float | None = None
    trigger_time: datetime | None = None

    # Order detAlgols
    quantity: int = 1
    limit_price: float | None = None
    amount_usd: float | None = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    triggered_at: datetime | None = None
    executed_at: datetime | None = None

    # Entry price for stop-loss/take-profit
    entry_price: float | None = None

    # Notes
    notes: str = ""

    def is_expired(self) -> bool:
        """Check if order is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "order_type": self.order_type.value,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "status": self.status.value,
            "trigger_price": self.trigger_price,
            "trigger_percent": self.trigger_percent,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "amount_usd": self.amount_usd,
            "entry_price": self.entry_price,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class DCAConfig:
    """Dollar Cost Averaging configuration."""

    item_name: str
    target_price: float
    amount_per_buy: float  # USD amount per DCA buy
    interval_hours: int = 24
    max_total_amount: float = 0.0  # 0 = unlimited

    # State
    total_invested: float = 0.0
    buy_count: int = 0
    avg_price: float = 0.0
    last_buy_time: datetime | None = None
    is_active: bool = True

    def can_buy(self, current_price: float, user_balance: float) -> bool:
        """Check if DCA buy is allowed."""
        if not self.is_active:
            return False

        if current_price > self.target_price * 1.1:  # Price too high
            return False

        if self.amount_per_buy > user_balance:  # Insufficient balance
            return False

        if self.max_total_amount > 0 and self.total_invested >= self.max_total_amount:
            return False

        # Check interval
        if self.last_buy_time:
            next_buy = self.last_buy_time + timedelta(hours=self.interval_hours)
            if datetime.now(UTC) < next_buy:
                return False

        return True

    def record_buy(self, price: float, amount: float) -> None:
        """Record a DCA buy."""
        self.buy_count += 1
        old_total = self.total_invested
        self.total_invested += amount

        # Update average price
        if self.buy_count == 1:
            self.avg_price = price
        else:
            self.avg_price = (
                (old_total * self.avg_price + amount * price) / self.total_invested
                if self.total_invested > 0
                else price
            )

        self.last_buy_time = datetime.now(UTC)


@dataclass
class RebalanceConfig:
    """Portfolio rebalancing configuration."""

    target_allocations: dict[str, float]  # item_name -> target percentage (0-1)
    rebalance_threshold: float = 0.1  # Trigger rebalance when >10% off target
    min_trade_amount: float = 5.0  # Minimum trade amount in USD
    is_active: bool = True

    def validate(self) -> bool:
        """Validate allocations sum to 1."""
        total = sum(self.target_allocations.values())
        return abs(total - 1.0) < 0.01


@dataclass
class ScheduledTask:
    """Scheduled task configuration."""

    task_id: str
    task_type: str
    schedule_time: datetime | None = None
    interval_hours: int | None = None  # For recurring tasks
    is_recurring: bool = False
    is_active: bool = True

    # Execution history
    last_run: datetime | None = None
    run_count: int = 0

    # Callback
    callback_name: str = ""
    callback_params: dict[str, Any] = field(default_factory=dict)

    def should_run(self) -> bool:
        """Check if task should run now."""
        if not self.is_active:
            return False

        now = datetime.now(UTC)

        if self.is_recurring and self.interval_hours:
            if self.last_run is None:
                return True
            next_run = self.last_run + timedelta(hours=self.interval_hours)
            return now >= next_run
        if self.schedule_time:
            return now >= self.schedule_time and (
                self.last_run is None or self.last_run < self.schedule_time
            )

        return False


@dataclass
class ExecutionResult:
    """Result of automated order execution."""

    order: AutoOrder
    success: bool
    message: str
    executed_price: float | None = None
    executed_quantity: int = 0
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order.order_id,
            "order_type": self.order.order_type.value,
            "success": self.success,
            "message": self.message,
            "executed_price": self.executed_price,
            "executed_quantity": self.executed_quantity,
            "executed_at": self.executed_at.isoformat(),
        }


class TradingAutomation:
    """Trading automation engine.

    Manages:
    - Stop-loss and take-profit orders
    - Dollar cost averaging
    - Portfolio rebalancing
    - Scheduled tasks
    """

    def __init__(
        self,
        balance: float = 0.0,
        dry_run: bool = True,
        max_orders_per_hour: int = 10,
    ) -> None:
        """Initialize trading automation.

        Args:
            balance: Initial balance
            dry_run: If True, don't execute actual trades
            max_orders_per_hour: Rate limit for order execution
        """
        self.balance = balance
        self.dry_run = dry_run
        self.max_orders_per_hour = max_orders_per_hour

        # Orders
        self._orders: dict[str, AutoOrder] = {}
        self._order_counter = 0

        # DCA configs
        self._dca_configs: dict[str, DCAConfig] = {}

        # Rebalance config
        self._rebalance_config: RebalanceConfig | None = None

        # Scheduled tasks
        self._scheduled_tasks: dict[str, ScheduledTask] = {}

        # Execution callbacks
        self._callbacks: dict[str, Callable[..., AwAlgotable[Any]]] = {}

        # Rate limiting
        self._executions_this_hour: list[datetime] = []

    def set_balance(self, balance: float) -> None:
        """Update balance."""
        self.balance = max(0.0, balance)

    def register_callback(
        self,
        name: str,
        callback: Callable[..., AwAlgotable[Any]],
    ) -> None:
        """Register execution callback.

        Args:
            name: Callback name
            callback: Async callback function
        """
        self._callbacks[name] = callback

    # ==================== Stop-Loss / Take-Profit ====================

    def set_stop_loss(
        self,
        item_id: str,
        item_name: str,
        entry_price: float,
        stop_percent: float = 10.0,
        quantity: int = 1,
        expires_hours: int | None = None,
    ) -> AutoOrder:
        """Set stop-loss order.

        Args:
            item_id: Item ID
            item_name: Item name
            entry_price: Entry price
            stop_percent: Stop loss percentage (e.g., 10 = sell if price drops 10%)
            quantity: Quantity to sell
            expires_hours: Hours until expiry (None = no expiry)

        Returns:
            Created AutoOrder
        """
        trigger_price = entry_price * (1 - stop_percent / 100)

        order = AutoOrder(
            order_id=self._generate_order_id(),
            order_type=OrderType.STOP_LOSS,
            item_id=item_id,
            item_name=item_name,
            trigger_price=trigger_price,
            trigger_percent=-stop_percent,
            quantity=quantity,
            entry_price=entry_price,
            expires_at=(
                datetime.now(UTC) + timedelta(hours=expires_hours)
                if expires_hours
                else None
            ),
            notes=f"Stop-loss at {stop_percent}% below entry ${entry_price:.2f}",
        )

        self._orders[order.order_id] = order
        logger.info(
            "stop_loss_set",
            order_id=order.order_id,
            item=item_name,
            trigger_price=trigger_price,
        )

        return order

    def set_take_profit(
        self,
        item_id: str,
        item_name: str,
        entry_price: float,
        profit_percent: float = 20.0,
        quantity: int = 1,
        expires_hours: int | None = None,
    ) -> AutoOrder:
        """Set take-profit order.

        Args:
            item_id: Item ID
            item_name: Item name
            entry_price: Entry price
            profit_percent: Take profit percentage (e.g., 20 = sell if price rises 20%)
            quantity: Quantity to sell
            expires_hours: Hours until expiry

        Returns:
            Created AutoOrder
        """
        trigger_price = entry_price * (1 + profit_percent / 100)

        order = AutoOrder(
            order_id=self._generate_order_id(),
            order_type=OrderType.TAKE_PROFIT,
            item_id=item_id,
            item_name=item_name,
            trigger_price=trigger_price,
            trigger_percent=profit_percent,
            quantity=quantity,
            entry_price=entry_price,
            expires_at=(
                datetime.now(UTC) + timedelta(hours=expires_hours)
                if expires_hours
                else None
            ),
            notes=f"Take-profit at {profit_percent}% above entry ${entry_price:.2f}",
        )

        self._orders[order.order_id] = order
        logger.info(
            "take_profit_set",
            order_id=order.order_id,
            item=item_name,
            trigger_price=trigger_price,
        )

        return order

    def set_trAlgoling_stop(
        self,
        item_id: str,
        item_name: str,
        entry_price: float,
        trAlgol_percent: float = 5.0,
        quantity: int = 1,
    ) -> AutoOrder:
        """Set trAlgoling stop order.

        The stop price moves up as the price increases, but never down.

        Args:
            item_id: Item ID
            item_name: Item name
            entry_price: Entry price
            trAlgol_percent: TrAlgol percentage
            quantity: Quantity

        Returns:
            Created AutoOrder
        """
        trigger_price = entry_price * (1 - trAlgol_percent / 100)

        order = AutoOrder(
            order_id=self._generate_order_id(),
            order_type=OrderType.STOP_LOSS,
            item_id=item_id,
            item_name=item_name,
            trigger_price=trigger_price,
            trigger_percent=-trAlgol_percent,
            quantity=quantity,
            entry_price=entry_price,
            notes=f"TrAlgoling stop at {trAlgol_percent}% trAlgol",
        )

        self._orders[order.order_id] = order
        return order

    def update_trAlgoling_stop(
        self,
        order_id: str,
        current_price: float,
    ) -> bool:
        """Update trAlgoling stop price based on current price.

        Args:
            order_id: Order ID
            current_price: Current market price

        Returns:
            True if stop was updated
        """
        order = self._orders.get(order_id)
        if not order or order.order_type != OrderType.STOP_LOSS:
            return False

        if order.trigger_percent is None or order.entry_price is None:
            return False

        trAlgol_percent = abs(order.trigger_percent)
        new_stop = current_price * (1 - trAlgol_percent / 100)

        # Only update if new stop is higher
        if order.trigger_price and new_stop > order.trigger_price:
            order.trigger_price = new_stop
            order.entry_price = current_price
            logger.info(
                "trAlgoling_stop_updated",
                order_id=order_id,
                new_stop=new_stop,
            )
            return True

        return False

    # ==================== DCA (Dollar Cost Averaging) ====================

    def enable_dca(
        self,
        item_name: str,
        target_price: float,
        amount_per_buy: float,
        interval_hours: int = 24,
        max_total_amount: float = 0.0,
    ) -> DCAConfig:
        """Enable dollar cost averaging for an item.

        Args:
            item_name: Item name
            target_price: Target price (DCA when at or below)
            amount_per_buy: USD amount per DCA buy
            interval_hours: Hours between buys
            max_total_amount: Maximum total investment (0 = unlimited)

        Returns:
            DCA configuration
        """
        config = DCAConfig(
            item_name=item_name,
            target_price=target_price,
            amount_per_buy=amount_per_buy,
            interval_hours=interval_hours,
            max_total_amount=max_total_amount,
        )

        self._dca_configs[item_name] = config
        logger.info(
            "dca_enabled",
            item=item_name,
            target_price=target_price,
            amount_per_buy=amount_per_buy,
        )

        return config

    def disable_dca(self, item_name: str) -> bool:
        """Disable DCA for an item.

        Args:
            item_name: Item name

        Returns:
            True if DCA was disabled
        """
        if item_name in self._dca_configs:
            self._dca_configs[item_name].is_active = False
            return True
        return False

    def get_dca_status(self, item_name: str) -> dict[str, Any] | None:
        """Get DCA status for an item.

        Args:
            item_name: Item name

        Returns:
            DCA status dict or None
        """
        config = self._dca_configs.get(item_name)
        if not config:
            return None

        return {
            "item_name": config.item_name,
            "target_price": config.target_price,
            "amount_per_buy": config.amount_per_buy,
            "total_invested": config.total_invested,
            "buy_count": config.buy_count,
            "avg_price": round(config.avg_price, 2),
            "is_active": config.is_active,
            "last_buy": (
                config.last_buy_time.isoformat() if config.last_buy_time else None
            ),
        }

    # ==================== Rebalancing ====================

    def set_rebalance_config(
        self,
        target_allocations: dict[str, float],
        rebalance_threshold: float = 0.1,
        min_trade_amount: float = 5.0,
    ) -> RebalanceConfig | None:
        """Set portfolio rebalancing configuration.

        Args:
            target_allocations: Target allocations (item -> percentage)
            rebalance_threshold: Threshold to trigger rebalance
            min_trade_amount: Minimum trade amount

        Returns:
            Rebalance config or None if invalid
        """
        config = RebalanceConfig(
            target_allocations=target_allocations,
            rebalance_threshold=rebalance_threshold,
            min_trade_amount=min_trade_amount,
        )

        if not config.validate():
            logger.warning("Invalid rebalance config: allocations don't sum to 1")
            return None

        self._rebalance_config = config
        logger.info("rebalance_config_set", allocations=target_allocations)

        return config

    def calculate_rebalance_trades(
        self,
        current_holdings: dict[str, float],  # item -> current value
        total_portfolio_value: float,
    ) -> list[dict[str, Any]]:
        """Calculate trades needed to rebalance.

        Args:
            current_holdings: Current holdings values
            total_portfolio_value: Total portfolio value

        Returns:
            List of suggested trades
        """
        if not self._rebalance_config or not self._rebalance_config.is_active:
            return []

        trades = []
        config = self._rebalance_config

        for item, target_pct in config.target_allocations.items():
            current_value = current_holdings.get(item, 0)
            current_pct = (
                current_value / total_portfolio_value
                if total_portfolio_value > 0
                else 0
            )
            target_value = total_portfolio_value * target_pct

            diff_pct = abs(current_pct - target_pct)

            if diff_pct > config.rebalance_threshold:
                diff_value = target_value - current_value

                if abs(diff_value) >= config.min_trade_amount:
                    trade_type = "buy" if diff_value > 0 else "sell"
                    trades.append(
                        {
                            "item": item,
                            "action": trade_type,
                            "amount_usd": abs(diff_value),
                            "current_pct": round(current_pct * 100, 2),
                            "target_pct": round(target_pct * 100, 2),
                            "diff_pct": round(diff_pct * 100, 2),
                        }
                    )

        return trades

    # ==================== Scheduled Tasks ====================

    def schedule_task(
        self,
        task_type: str,
        schedule_time: datetime | None = None,
        interval_hours: int | None = None,
        callback_name: str = "",
        callback_params: dict[str, Any] | None = None,
    ) -> ScheduledTask:
        """Schedule a task.

        Args:
            task_type: Type of task
            schedule_time: One-time schedule time
            interval_hours: Recurring interval
            callback_name: Callback function name
            callback_params: Parameters for callback

        Returns:
            Scheduled task
        """
        task = ScheduledTask(
            task_id=f"task_{len(self._scheduled_tasks) + 1}",
            task_type=task_type,
            schedule_time=schedule_time,
            interval_hours=interval_hours,
            is_recurring=interval_hours is not None,
            callback_name=callback_name,
            callback_params=callback_params or {},
        )

        self._scheduled_tasks[task.task_id] = task
        logger.info(
            "task_scheduled",
            task_id=task.task_id,
            task_type=task_type,
            recurring=task.is_recurring,
        )

        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled
        """
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id].is_active = False
            return True
        return False

    # ==================== Execution ====================

    async def check_and_execute(
        self,
        current_prices: dict[str, float],  # item_id -> current price
    ) -> list[ExecutionResult]:
        """Check triggers and execute orders.

        Args:
            current_prices: Current prices for items

        Returns:
            List of execution results
        """
        results = []

        # Check rate limit
        self._cleanup_rate_limit()
        if len(self._executions_this_hour) >= self.max_orders_per_hour:
            logger.warning("Rate limit reached for order execution")
            return results

        # Check stop-loss and take-profit orders
        for order in list(self._orders.values()):
            if order.status != OrderStatus.PENDING:
                continue

            if order.is_expired():
                order.status = OrderStatus.EXPIRED
                continue

            current_price = current_prices.get(order.item_id)
            if current_price is None:
                continue

            should_trigger = False

            if order.order_type == OrderType.STOP_LOSS:
                # Trigger if price falls to or below stop price
                if order.trigger_price and current_price <= order.trigger_price:
                    should_trigger = True
            elif order.order_type == OrderType.TAKE_PROFIT:
                # Trigger if price rises to or above target price
                if order.trigger_price and current_price >= order.trigger_price:
                    should_trigger = True

            if should_trigger:
                result = awAlgot self._execute_order(order, current_price)
                results.append(result)

        # Check DCA
        for config in self._dca_configs.values():
            if not config.is_active:
                continue

            # Find current price for item
            item_price = None
            for item_id, price in current_prices.items():
                if config.item_name.lower() in item_id.lower():
                    item_price = price
                    break

            if item_price and config.can_buy(item_price, self.balance):
                result = awAlgot self._execute_dca_buy(config, item_price)
                if result:
                    results.append(result)

        # Check scheduled tasks
        for task in self._scheduled_tasks.values():
            if task.should_run():
                awAlgot self._execute_task(task)

        return results

    async def _execute_order(
        self,
        order: AutoOrder,
        current_price: float,
    ) -> ExecutionResult:
        """Execute an order.

        Args:
            order: Order to execute
            current_price: Current price

        Returns:
            Execution result
        """
        order.triggered_at = datetime.now(UTC)
        order.status = OrderStatus.TRIGGERED

        if self.dry_run:
            order.status = OrderStatus.EXECUTED
            order.executed_at = datetime.now(UTC)
            self._executions_this_hour.append(datetime.now(UTC))

            return ExecutionResult(
                order=order,
                success=True,
                message=f"[DRY RUN] Would execute {order.order_type.value} at ${current_price:.2f}",
                executed_price=current_price,
                executed_quantity=order.quantity,
            )

        # Execute via callback if registered
        callback = self._callbacks.get("execute_sell")
        if callback:
            try:
                _ = awAlgot callback(  # result for future use
                    item_id=order.item_id,
                    quantity=order.quantity,
                    price=current_price,
                )

                order.status = OrderStatus.EXECUTED
                order.executed_at = datetime.now(UTC)
                self._executions_this_hour.append(datetime.now(UTC))

                return ExecutionResult(
                    order=order,
                    success=True,
                    message=f"Executed {order.order_type.value} at ${current_price:.2f}",
                    executed_price=current_price,
                    executed_quantity=order.quantity,
                )
            except Exception as e:
                order.status = OrderStatus.FAlgoLED
                return ExecutionResult(
                    order=order,
                    success=False,
                    message=f"Execution fAlgoled: {e}",
                )
        else:
            order.status = OrderStatus.EXECUTED
            order.executed_at = datetime.now(UTC)

            return ExecutionResult(
                order=order,
                success=True,
                message=f"Order triggered (no callback registered) at ${current_price:.2f}",
                executed_price=current_price,
                executed_quantity=order.quantity,
            )

    async def _execute_dca_buy(
        self,
        config: DCAConfig,
        current_price: float,
    ) -> ExecutionResult | None:
        """Execute DCA buy.

        Args:
            config: DCA configuration
            current_price: Current price

        Returns:
            Execution result or None
        """
        quantity = int(config.amount_per_buy / current_price)
        if quantity <= 0:
            return None

        # Create order for tracking
        order = AutoOrder(
            order_id=self._generate_order_id(),
            order_type=OrderType.DCA_BUY,
            item_id="",
            item_name=config.item_name,
            trigger_price=current_price,
            quantity=quantity,
            amount_usd=config.amount_per_buy,
        )

        if self.dry_run:
            config.record_buy(current_price, config.amount_per_buy)
            order.status = OrderStatus.EXECUTED

            return ExecutionResult(
                order=order,
                success=True,
                message=f"[DRY RUN] DCA buy {quantity}x {config.item_name} at ${current_price:.2f}",
                executed_price=current_price,
                executed_quantity=quantity,
            )

        # Execute via callback
        callback = self._callbacks.get("execute_buy")
        if callback:
            try:
                awAlgot callback(
                    item_name=config.item_name,
                    quantity=quantity,
                    max_price=current_price * 1.02,  # 2% slippage tolerance
                )

                config.record_buy(current_price, config.amount_per_buy)
                self.balance -= config.amount_per_buy
                order.status = OrderStatus.EXECUTED

                return ExecutionResult(
                    order=order,
                    success=True,
                    message=f"DCA buy {quantity}x {config.item_name} at ${current_price:.2f}",
                    executed_price=current_price,
                    executed_quantity=quantity,
                )
            except Exception as e:
                order.status = OrderStatus.FAlgoLED
                return ExecutionResult(
                    order=order,
                    success=False,
                    message=f"DCA buy fAlgoled: {e}",
                )

        return None

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute scheduled task.

        Args:
            task: Task to execute
        """
        task.last_run = datetime.now(UTC)
        task.run_count += 1

        if not task.is_recurring:
            task.is_active = False

        callback = self._callbacks.get(task.callback_name)
        if callback:
            try:
                awAlgot callback(**task.callback_params)
                logger.info("task_executed", task_id=task.task_id)
            except Exception as e:
                logger.exception(f"Task execution fAlgoled: {e}")

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        return (
            f"auto_{self._order_counter}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        )

    def _cleanup_rate_limit(self) -> None:
        """Clean up old rate limit entries."""
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        self._executions_this_hour = [
            t for t in self._executions_this_hour if t > cutoff
        ]

    # ==================== Management ====================

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID

        Returns:
            True if cancelled
        """
        order = self._orders.get(order_id)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def get_active_orders(self) -> list[AutoOrder]:
        """Get all active orders.

        Returns:
            List of pending orders
        """
        return [
            order
            for order in self._orders.values()
            if order.status == OrderStatus.PENDING
        ]

    def get_order_history(
        self,
        limit: int = 50,
    ) -> list[AutoOrder]:
        """Get order history.

        Args:
            limit: Maximum number of orders

        Returns:
            List of orders (newest first)
        """
        orders = sorted(
            self._orders.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        return orders[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get automation statistics.

        Returns:
            Statistics dictionary
        """
        orders = list(self._orders.values())
        executed = [o for o in orders if o.status == OrderStatus.EXECUTED]

        return {
            "total_orders": len(orders),
            "pending_orders": sum(1 for o in orders if o.status == OrderStatus.PENDING),
            "executed_orders": len(executed),
            "cancelled_orders": sum(
                1 for o in orders if o.status == OrderStatus.CANCELLED
            ),
            "fAlgoled_orders": sum(1 for o in orders if o.status == OrderStatus.FAlgoLED),
            "active_dca_configs": sum(
                1 for c in self._dca_configs.values() if c.is_active
            ),
            "active_scheduled_tasks": sum(
                1 for t in self._scheduled_tasks.values() if t.is_active
            ),
            "executions_this_hour": len(self._executions_this_hour),
        }


# Factory function
def create_trading_automation(
    balance: float = 0.0,
    dry_run: bool = True,
) -> TradingAutomation:
    """Create trading automation instance.

    Args:
        balance: Initial balance
        dry_run: If True, don't execute real trades

    Returns:
        TradingAutomation instance
    """
    return TradingAutomation(
        balance=balance,
        dry_run=dry_run,
    )
