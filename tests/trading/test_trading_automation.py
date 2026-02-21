"""Tests for Trading Automation Module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.trading.trading_automation import (
    AutoOrder,
    DCAConfig,
    OrderStatus,
    OrderType,
    TradingAutomation,
    create_trading_automation,
)


class TestTradingAutomation:
    """Tests for TradingAutomation class."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        auto = TradingAutomation()
        
        assert auto.balance == 0.0
        assert auto.dry_run is True
        assert auto.max_orders_per_hour == 10
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        auto = TradingAutomation(
            balance=100.0,
            dry_run=False,
            max_orders_per_hour=20,
        )
        
        assert auto.balance == 100.0
        assert auto.dry_run is False
        assert auto.max_orders_per_hour == 20
    
    def test_set_balance(self):
        """Test balance update."""
        auto = TradingAutomation()
        auto.set_balance(500.0)
        
        assert auto.balance == 500.0
    
    def test_set_balance_negative(self):
        """Test negative balance is clamped to 0."""
        auto = TradingAutomation()
        auto.set_balance(-100.0)
        
        assert auto.balance == 0.0


class TestStopLossTakeProfit:
    """Tests for stop-loss and take-profit orders."""
    
    def test_set_stop_loss(self):
        """Test setting stop-loss order."""
        auto = TradingAutomation()
        
        order = auto.set_stop_loss(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            stop_percent=10.0,
        )
        
        assert order.order_type == OrderType.STOP_LOSS
        assert order.trigger_price == 90.0  # 10% below entry
        assert order.status == OrderStatus.PENDING
    
    def test_set_take_profit(self):
        """Test setting take-profit order."""
        auto = TradingAutomation()
        
        order = auto.set_take_profit(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            profit_percent=20.0,
        )
        
        assert order.order_type == OrderType.TAKE_PROFIT
        assert order.trigger_price == 120.0  # 20% above entry
        assert order.status == OrderStatus.PENDING
    
    def test_set_stop_loss_with_expiry(self):
        """Test stop-loss with expiration."""
        auto = TradingAutomation()
        
        order = auto.set_stop_loss(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            stop_percent=10.0,
            expires_hours=24,
        )
        
        assert order.expires_at is not None
        assert order.expires_at > datetime.now(UTC)
    
    def test_set_trAlgoling_stop(self):
        """Test trAlgoling stop order."""
        auto = TradingAutomation()
        
        order = auto.set_trAlgoling_stop(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            trAlgol_percent=5.0,
        )
        
        assert order.order_type == OrderType.STOP_LOSS
        assert order.trigger_price == 95.0  # 5% below entry
    
    def test_update_trAlgoling_stop(self):
        """Test trAlgoling stop update."""
        auto = TradingAutomation()
        
        order = auto.set_trAlgoling_stop(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            trAlgol_percent=5.0,
        )
        
        # Price increased to 110
        updated = auto.update_trAlgoling_stop(order.order_id, 110.0)
        
        assert updated is True
        assert order.trigger_price == 104.5  # 5% below 110
    
    def test_update_trAlgoling_stop_no_update_on_drop(self):
        """Test trAlgoling stop doesn't update on price drop."""
        auto = TradingAutomation()
        
        order = auto.set_trAlgoling_stop(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            trAlgol_percent=5.0,
        )
        
        original_stop = order.trigger_price
        
        # Price dropped to 90 - shouldn't update
        updated = auto.update_trAlgoling_stop(order.order_id, 90.0)
        
        assert updated is False
        assert order.trigger_price == original_stop


class TestDCA:
    """Tests for Dollar Cost Averaging."""
    
    def test_enable_dca(self):
        """Test enabling DCA."""
        auto = TradingAutomation()
        
        config = auto.enable_dca(
            item_name="AK-47 | Redline",
            target_price=50.0,
            amount_per_buy=10.0,
            interval_hours=24,
        )
        
        assert config.item_name == "AK-47 | Redline"
        assert config.target_price == 50.0
        assert config.is_active is True
    
    def test_disable_dca(self):
        """Test disabling DCA."""
        auto = TradingAutomation()
        
        auto.enable_dca("AK-47", 50.0, 10.0)
        result = auto.disable_dca("AK-47")
        
        assert result is True
        assert auto._dca_configs["AK-47"].is_active is False
    
    def test_get_dca_status(self):
        """Test getting DCA status."""
        auto = TradingAutomation()
        
        auto.enable_dca("AK-47", 50.0, 10.0)
        status = auto.get_dca_status("AK-47")
        
        assert status is not None
        assert status["item_name"] == "AK-47"
        assert status["target_price"] == 50.0
        assert status["total_invested"] == 0.0
    
    def test_dca_config_can_buy(self):
        """Test DCA can_buy logic."""
        config = DCAConfig(
            item_name="AK-47",
            target_price=50.0,
            amount_per_buy=10.0,
        )
        
        # Can buy when price below target
        assert config.can_buy(current_price=45.0, user_balance=100.0) is True
        
        # Cannot buy when price too high
        assert config.can_buy(current_price=60.0, user_balance=100.0) is False
        
        # Cannot buy when insufficient balance
        assert config.can_buy(current_price=45.0, user_balance=5.0) is False
    
    def test_dca_config_record_buy(self):
        """Test DCA buy recording."""
        config = DCAConfig(
            item_name="AK-47",
            target_price=50.0,
            amount_per_buy=10.0,
        )
        
        config.record_buy(price=45.0, amount=10.0)
        
        assert config.buy_count == 1
        assert config.total_invested == 10.0
        assert config.avg_price == 45.0
        assert config.last_buy_time is not None


class TestRebalancing:
    """Tests for portfolio rebalancing."""
    
    def test_set_rebalance_config_valid(self):
        """Test setting valid rebalance config."""
        auto = TradingAutomation()
        
        config = auto.set_rebalance_config(
            target_allocations={"AK-47": 0.5, "AWP": 0.5},
            rebalance_threshold=0.1,
        )
        
        assert config is not None
        assert config.target_allocations["AK-47"] == 0.5
    
    def test_set_rebalance_config_invalid(self):
        """Test setting invalid rebalance config (doesn't sum to 1)."""
        auto = TradingAutomation()
        
        config = auto.set_rebalance_config(
            target_allocations={"AK-47": 0.5, "AWP": 0.3},  # Sum = 0.8
        )
        
        assert config is None
    
    def test_calculate_rebalance_trades(self):
        """Test rebalance trade calculation."""
        auto = TradingAutomation()
        
        auto.set_rebalance_config(
            target_allocations={"AK-47": 0.5, "AWP": 0.5},
            rebalance_threshold=0.05,
        )
        
        current_holdings = {
            "AK-47": 70.0,  # 70%
            "AWP": 30.0,  # 30%
        }
        
        trades = auto.calculate_rebalance_trades(
            current_holdings=current_holdings,
            total_portfolio_value=100.0,
        )
        
        assert len(trades) == 2
        
        ak_trade = next(t for t in trades if t["item"] == "AK-47")
        assert ak_trade["action"] == "sell"  # Need to sell to reduce from 70% to 50%
        
        awp_trade = next(t for t in trades if t["item"] == "AWP")
        assert awp_trade["action"] == "buy"  # Need to buy to increase from 30% to 50%


class TestScheduledTasks:
    """Tests for scheduled tasks."""
    
    def test_schedule_one_time_task(self):
        """Test scheduling one-time task."""
        auto = TradingAutomation()
        
        schedule_time = datetime.now(UTC) + timedelta(hours=1)
        
        task = auto.schedule_task(
            task_type="market_scan",
            schedule_time=schedule_time,
        )
        
        assert task.task_type == "market_scan"
        assert task.is_recurring is False
    
    def test_schedule_recurring_task(self):
        """Test scheduling recurring task."""
        auto = TradingAutomation()
        
        task = auto.schedule_task(
            task_type="market_scan",
            interval_hours=4,
        )
        
        assert task.is_recurring is True
        assert task.interval_hours == 4
    
    def test_cancel_task(self):
        """Test cancelling task."""
        auto = TradingAutomation()
        
        task = auto.schedule_task("test", interval_hours=1)
        result = auto.cancel_task(task.task_id)
        
        assert result is True
        assert auto._scheduled_tasks[task.task_id].is_active is False


class TestOrderExecution:
    """Tests for order execution."""
    
    @pytest.mark.asyncio
    async def test_check_and_execute_stop_loss(self):
        """Test stop-loss execution."""
        auto = TradingAutomation(dry_run=True)
        
        order = auto.set_stop_loss(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            stop_percent=10.0,
        )
        
        # Price dropped below stop
        results = awAlgot auto.check_and_execute({"item_1": 85.0})
        
        assert len(results) == 1
        assert results[0].success is True
        assert order.status == OrderStatus.EXECUTED
    
    @pytest.mark.asyncio
    async def test_check_and_execute_take_profit(self):
        """Test take-profit execution."""
        auto = TradingAutomation(dry_run=True)
        
        order = auto.set_take_profit(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            profit_percent=20.0,
        )
        
        # Price rose above target
        results = awAlgot auto.check_and_execute({"item_1": 125.0})
        
        assert len(results) == 1
        assert results[0].success is True
        assert order.status == OrderStatus.EXECUTED
    
    @pytest.mark.asyncio
    async def test_check_and_execute_no_trigger(self):
        """Test no execution when conditions not met."""
        auto = TradingAutomation(dry_run=True)
        
        auto.set_stop_loss(
            item_id="item_1",
            item_name="AK-47",
            entry_price=100.0,
            stop_percent=10.0,
        )
        
        # Price didn't drop below stop
        results = awAlgot auto.check_and_execute({"item_1": 95.0})
        
        assert len(results) == 0


class TestOrderManagement:
    """Tests for order management."""
    
    def test_cancel_order(self):
        """Test order cancellation."""
        auto = TradingAutomation()
        
        order = auto.set_stop_loss("item_1", "AK-47", 100.0, 10.0)
        result = auto.cancel_order(order.order_id)
        
        assert result is True
        assert order.status == OrderStatus.CANCELLED
    
    def test_get_active_orders(self):
        """Test getting active orders."""
        auto = TradingAutomation()
        
        auto.set_stop_loss("item_1", "AK-47", 100.0, 10.0)
        auto.set_take_profit("item_2", "AWP", 200.0, 20.0)
        
        active = auto.get_active_orders()
        
        assert len(active) == 2
        assert all(o.status == OrderStatus.PENDING for o in active)
    
    def test_get_order_history(self):
        """Test getting order history."""
        auto = TradingAutomation()
        
        auto.set_stop_loss("item_1", "AK-47", 100.0, 10.0)
        auto.set_stop_loss("item_2", "AWP", 200.0, 10.0)
        
        history = auto.get_order_history(limit=1)
        
        assert len(history) == 1
    
    def test_get_statistics(self):
        """Test getting automation statistics."""
        auto = TradingAutomation()
        
        auto.set_stop_loss("item_1", "AK-47", 100.0, 10.0)
        auto.enable_dca("AWP", 50.0, 10.0)
        auto.schedule_task("test", interval_hours=1)
        
        stats = auto.get_statistics()
        
        assert stats["total_orders"] == 1
        assert stats["pending_orders"] == 1
        assert stats["active_dca_configs"] == 1
        assert stats["active_scheduled_tasks"] == 1


class TestAutoOrder:
    """Tests for AutoOrder dataclass."""
    
    def test_is_expired_no_expiry(self):
        """Test order without expiry."""
        order = AutoOrder(
            order_id="test",
            order_type=OrderType.STOP_LOSS,
            item_id="item_1",
            item_name="Test",
        )
        
        assert order.is_expired() is False
    
    def test_is_expired_future(self):
        """Test order with future expiry."""
        order = AutoOrder(
            order_id="test",
            order_type=OrderType.STOP_LOSS,
            item_id="item_1",
            item_name="Test",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        
        assert order.is_expired() is False
    
    def test_is_expired_past(self):
        """Test expired order."""
        order = AutoOrder(
            order_id="test",
            order_type=OrderType.STOP_LOSS,
            item_id="item_1",
            item_name="Test",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        
        assert order.is_expired() is True
    
    def test_to_dict(self):
        """Test serialization."""
        order = AutoOrder(
            order_id="test_1",
            order_type=OrderType.STOP_LOSS,
            item_id="item_1",
            item_name="AK-47",
            trigger_price=90.0,
            quantity=1,
        )
        
        data = order.to_dict()
        
        assert data["order_id"] == "test_1"
        assert data["order_type"] == "stop_loss"


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_trading_automation(self):
        """Test factory function."""
        auto = create_trading_automation(
            balance=500.0,
            dry_run=False,
        )
        
        assert auto.balance == 500.0
        assert auto.dry_run is False
