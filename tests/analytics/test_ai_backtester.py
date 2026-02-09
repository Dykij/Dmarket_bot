"""Tests for AI Backtester.

Tests Phase 3 implementation of AI-powered backtesting.
"""

from datetime import datetime, timedelta

import pytest

from src.analytics.ai_backtester import (
    AIBacktester,
    BacktestResult,
    Trade,
    create_ai_backtester,
)


class TestAIBacktester:
    """Tests for AIBacktester class."""

    def test_initialization(self):
        """Test backtester initialization."""
        backtester = AIBacktester(initial_balance=100.0, commission_percent=7.0)

        assert backtester.initial_balance == 100.0
        assert backtester.commission_percent == 7.0
        assert backtester.current_balance == 100.0

    def test_factory_function(self):
        """Test factory function creates valid backtester."""
        backtester = create_ai_backtester(initial_balance=200.0)

        assert isinstance(backtester, AIBacktester)
        assert backtester.initial_balance == 200.0

    @pytest.mark.asyncio
    async def test_backtest_with_empty_data(self):
        """Test backtesting with empty historical data."""
        backtester = AIBacktester(initial_balance=100.0)

        result = await backtester.backtest_arbitrage_strategy(
            historical_data=[],
            strategy="standard",
        )

        assert result.total_trades == 0
        assert result.total_profit == 0.0
        assert result.final_balance == 100.0

    @pytest.mark.asyncio
    async def test_backtest_profitable_trade(self):
        """Test backtesting with profitable arbitrage opportunity."""
        backtester = AIBacktester(initial_balance=100.0)

        # Historical data with good arbitrage opportunity
        now = datetime.now()
        historical_data = [
            {
                "timestamp": now,
                "itemId": "item_1",
                "title": "AK-47 | Redline",
                "price": {"USD": 1000},  # $10
                "suggestedPrice": {"USD": 1500},  # $15 (50% profit)
            },
            {
                "timestamp": now + timedelta(hours=1),
                "itemId": "item_1",
                "title": "AK-47 | Redline",
                "price": {"USD": 1500},  # Price increased
                "suggestedPrice": {"USD": 1500},
            },
        ]

        result = await backtester.backtest_arbitrage_strategy(
            historical_data=historical_data,
            strategy="standard",
            min_profit_percent=5.0,
        )

        # Should execute buy and sell
        assert result.total_trades == 2  # 1 buy + 1 sell
        assert result.profitable_trades >= 0
        assert result.final_balance > backtester.initial_balance  # Profit made

    @pytest.mark.asyncio
    async def test_backtest_unprofitable_filtered(self):
        """Test that unprofitable opportunities are filtered."""
        backtester = AIBacktester(initial_balance=100.0)

        now = datetime.now()
        historical_data = [
            {
                "timestamp": now,
                "itemId": "item_bad",
                "title": "Bad Item",
                "price": {"USD": 1000},  # $10
                "suggestedPrice": {"USD": 1020},  # Only $0.20 profit (2%)
            }
        ]

        result = await backtester.backtest_arbitrage_strategy(
            historical_data=historical_data,
            strategy="standard",
            min_profit_percent=5.0,  # Requires 5%
        )

        # Should not trade due to low profit
        assert result.total_trades == 0

    @pytest.mark.asyncio
    async def test_backtest_different_strategies(self):
        """Test different strategy types."""
        backtester = AIBacktester(initial_balance=200.0)

        now = datetime.now()
        historical_data = [
            {
                "timestamp": now,
                "itemId": "item_1",
                "title": "Test Item",
                "price": {"USD": 1000},
                "suggestedPrice": {"USD": 1400},  # 40% margin
            }
        ]

        # Test conservative strategy
        result_conservative = await backtester.backtest_arbitrage_strategy(
            historical_data=historical_data,
            strategy="conservative",
            min_profit_percent=5.0,
        )

        # Reset
        backtester.current_balance = backtester.initial_balance

        # Test aggressive strategy
        result_aggressive = await backtester.backtest_arbitrage_strategy(
            historical_data=historical_data,
            strategy="aggressive",
            min_profit_percent=3.0,
        )

        # Both should trade this good opportunity
        assert result_conservative.total_trades > 0
        assert result_aggressive.total_trades > 0

    @pytest.mark.asyncio
    async def test_backtest_insufficient_balance(self):
        """Test that trades are skipped when balance insufficient."""
        backtester = AIBacktester(initial_balance=5.0)  # Very low balance

        now = datetime.now()
        historical_data = [
            {
                "timestamp": now,
                "itemId": "expensive_item",
                "title": "Expensive Item",
                "price": {"USD": 10000},  # $100 (too expensive)
                "suggestedPrice": {"USD": 15000},
            }
        ]

        result = await backtester.backtest_arbitrage_strategy(
            historical_data=historical_data,
            strategy="standard",
        )

        # Should not trade due to insufficient balance
        assert result.total_trades == 0
        assert result.final_balance == 5.0  # Balance unchanged

    @pytest.mark.asyncio
    async def test_execute_buy_reduces_balance(self):
        """Test that buy execution reduces balance correctly."""
        backtester = AIBacktester(initial_balance=100.0)

        initial = backtester.current_balance

        trade = await backtester._execute_buy(
            timestamp=datetime.now(),
            item_id="test_item",
            title="Test",
            price=10.0,
        )

        assert trade is not None
        assert trade.action == "buy"
        assert trade.price == 10.0
        assert abs(trade.commission - 0.7) < 0.01  # 7% of 10.0, allowing float precision
        assert backtester.current_balance < initial

    @pytest.mark.asyncio
    async def test_execute_sell_increases_balance(self):
        """Test that sell execution increases balance correctly."""
        backtester = AIBacktester(initial_balance=100.0)

        # First buy
        await backtester._execute_buy(
            timestamp=datetime.now(),
            item_id="test_item",
            title="Test",
            price=10.0,
        )

        balance_after_buy = backtester.current_balance

        # Then sell
        trade = await backtester._execute_sell(
            timestamp=datetime.now(),
            item_id="test_item",
            title="Test",
            price=15.0,
            buy_price=10.0,
        )

        assert trade is not None
        assert trade.action == "sell"
        assert trade.price == 15.0
        assert trade.profit > 0  # Should be profitable
        assert backtester.current_balance > balance_after_buy

    def test_calculate_profit_margin(self):
        """Test profit margin calculation."""
        backtester = AIBacktester()

        # 50% gross margin, ~40% after 7% commission
        margin = backtester._calculate_profit_margin(10.0, 15.0)

        assert margin > 30  # At least 30% profit
        assert margin < 50  # Less than 50% due to commission

    def test_calculate_profit_margin_with_zero_price(self):
        """Test profit margin with zero buy price."""
        backtester = AIBacktester()

        margin = backtester._calculate_profit_margin(0.0, 15.0)

        assert margin == 0.0

    def test_get_price_from_dict(self):
        """Test price extraction from API format."""
        backtester = AIBacktester()

        price = backtester._get_price({"USD": 1234})

        assert price == 12.34

    def test_get_price_handles_invalid_data(self):
        """Test price extraction with invalid data."""
        backtester = AIBacktester()

        price = backtester._get_price({})

        assert price == 0.0

    def test_get_strategy_params(self):
        """Test strategy parameter retrieval."""
        backtester = AIBacktester()

        conservative = backtester._get_strategy_params("conservative")
        standard = backtester._get_strategy_params("standard")
        aggressive = backtester._get_strategy_params("aggressive")

        # Conservative should have highest requirements
        assert conservative["min_margin"] > standard["min_margin"]
        assert standard["min_margin"] > aggressive["min_margin"]

    def test_calculate_max_drawdown_empty_trades(self):
        """Test max drawdown calculation with no trades."""
        backtester = AIBacktester()

        drawdown = backtester._calculate_max_drawdown([])

        assert drawdown == 0.0

    def test_calculate_metrics_with_trades(self):
        """Test metrics calculation with sample trades."""
        backtester = AIBacktester(initial_balance=100.0)
        backtester.current_balance = 110.0  # Simulated profit

        trades = [
            Trade(
                timestamp=datetime.now(),
                item_title="Item 1",
                action="buy",
                price=10.0,
                commission=0.7,
            ),
            Trade(
                timestamp=datetime.now(),
                item_title="Item 1",
                action="sell",
                price=15.0,
                commission=1.05,
                profit=3.25,
            ),
        ]

        result = backtester._calculate_metrics(trades)

        assert result.total_trades == 2
        assert result.profitable_trades == 1
        assert result.total_profit > 0
        assert result.win_rate == 100.0
        assert result.final_balance == 110.0


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_result_creation(self):
        """Test creating backtest result."""
        result = BacktestResult(
            total_trades=10,
            profitable_trades=7,
            total_profit=50.0,
            roi_percent=25.0,
            win_rate=70.0,
        )

        assert result.total_trades == 10
        assert result.profitable_trades == 7
        assert result.win_rate == 70.0

    def test_result_default_values(self):
        """Test default values of backtest result."""
        result = BacktestResult()

        assert result.total_trades == 0
        assert result.total_profit == 0.0
        assert result.trades == []


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self):
        """Test creating trade."""
        now = datetime.now()
        trade = Trade(
            timestamp=now,
            item_title="Test Item",
            action="buy",
            price=10.0,
            commission=0.7,
        )

        assert trade.timestamp == now
        assert trade.action == "buy"
        assert trade.price == 10.0
