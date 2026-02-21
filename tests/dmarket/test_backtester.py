"""Tests for backtester module.

Tests the backtesting system for trading strategies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from src.dmarket.backtester import (
    Backtester,
    BacktestResults,
    HistoricalDataSet,
    MeanReversionStrategy,
    MomentumStrategy,
    PricePoint,
    SimpleArbitrageStrategy,
    SimulatedTrade,
    TradeAction,
    TradeStatus,
    TradingStrategy,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.fixture()
def backtester():
    """Create backtester instance."""
    return Backtester(initial_balance=1000.0, fee_percent=7.0)


@pytest.fixture()
def sample_price_points():
    """Create sample price points for testing."""
    base_time = datetime.now(UTC) - timedelta(days=30)
    points = []
    price = 10.0

    for i in range(100):
        # Simulate price movement
        if i % 10 < 5:
            price *= 1.02  # Up trend
        else:
            price *= 0.98  # Down trend

        points.append(
            PricePoint(
                timestamp=base_time + timedelta(hours=i),
                item_id="item_001",
                item_name="AK-47 | Redline",
                price=round(price, 2),
                volume=5,
            )
        )

    return points


class TestPricePoint:
    """Tests for PricePoint dataclass."""

    def test_create_price_point(self):
        """Test creating a price point."""
        timestamp = datetime.now(UTC)
        point = PricePoint(
            timestamp=timestamp,
            item_id="item_001",
            item_name="AK-47 | Redline",
            price=10.50,
            volume=5,
        )

        assert point.timestamp == timestamp
        assert point.item_id == "item_001"
        assert point.price == 10.50
        assert point.volume == 5

    def test_price_point_optional_fields(self):
        """Test price point with optional fields."""
        point = PricePoint(
            timestamp=datetime.now(UTC),
            item_id="item_001",
            item_name="Test",
            price=10.0,
            min_price=9.0,
            max_price=11.0,
            avg_price=10.0,
        )

        assert point.min_price == 9.0
        assert point.max_price == 11.0
        assert point.avg_price == 10.0


class TestSimulatedTrade:
    """Tests for SimulatedTrade dataclass."""

    def test_create_trade(self):
        """Test creating a simulated trade."""
        trade = SimulatedTrade(
            trade_id="BT-000001",
            item_id="item_001",
            item_name="AK-47 | Redline",
            action=TradeAction.BUY,
            price=10.0,
            quantity=1,
            timestamp=datetime.now(UTC),
        )

        assert trade.trade_id == "BT-000001"
        assert trade.action == TradeAction.BUY
        assert trade.status == TradeStatus.OPEN

    def test_total_cost(self):
        """Test total cost calculation."""
        trade = SimulatedTrade(
            trade_id="BT-000001",
            item_id="item_001",
            item_name="Test",
            action=TradeAction.BUY,
            price=10.0,
            quantity=2,
            timestamp=datetime.now(UTC),
            fees=0.70,
        )

        assert trade.total_cost == 20.70

    def test_close_trade_with_profit(self):
        """Test closing a trade with profit."""
        trade = SimulatedTrade(
            trade_id="BT-000001",
            item_id="item_001",
            item_name="Test",
            action=TradeAction.BUY,
            price=10.0,
            quantity=1,
            timestamp=datetime.now(UTC),
            fees=0.70,
        )

        close_time = datetime.now(UTC)
        trade.close(12.0, close_time)

        assert trade.status == TradeStatus.CLOSED
        assert trade.close_price == 12.0
        assert trade.close_timestamp == close_time
        # Profit = 12 - 10.70 - (12 * 0.07) = 12 - 10.70 - 0.84 = 0.46
        assert trade.profit is not None
        assert abs(trade.profit - 0.46) < 0.01

    def test_close_trade_with_loss(self):
        """Test closing a trade with loss."""
        trade = SimulatedTrade(
            trade_id="BT-000001",
            item_id="item_001",
            item_name="Test",
            action=TradeAction.BUY,
            price=10.0,
            quantity=1,
            timestamp=datetime.now(UTC),
            fees=0.70,
        )

        trade.close(8.0, datetime.now(UTC))

        assert trade.status == TradeStatus.CLOSED
        assert trade.profit is not None
        assert trade.profit < 0


class TestHistoricalDataSet:
    """Tests for HistoricalDataSet."""

    def test_create_dataset(self):
        """Test creating a dataset."""
        dataset = HistoricalDataSet(
            item_id="item_001",
            item_name="Test Item",
            game="csgo",
        )

        assert dataset.item_id == "item_001"
        assert len(dataset.prices) == 0

    def test_add_price(self):
        """Test adding prices to dataset."""
        dataset = HistoricalDataSet(
            item_id="item_001",
            item_name="Test",
            game="csgo",
        )

        time1 = datetime.now(UTC) - timedelta(hours=2)
        time2 = datetime.now(UTC) - timedelta(hours=1)

        dataset.add_price(
            PricePoint(
                timestamp=time1, item_id="item_001", item_name="Test", price=10.0
            )
        )
        dataset.add_price(
            PricePoint(
                timestamp=time2, item_id="item_001", item_name="Test", price=11.0
            )
        )

        assert len(dataset.prices) == 2
        assert dataset.start_date == time1
        assert dataset.end_date == time2


class TestSimpleArbitrageStrategy:
    """Tests for SimpleArbitrageStrategy."""

    def test_create_strategy(self):
        """Test creating strategy with defaults."""
        strategy = SimpleArbitrageStrategy()

        assert strategy.min_profit_percent == 10.0
        assert strategy.max_loss_percent == 5.0
        assert "SimpleArbitrage" in strategy.name

    def test_create_strategy_custom(self):
        """Test creating strategy with custom parameters."""
        strategy = SimpleArbitrageStrategy(
            min_profit_percent=15.0,
            max_loss_percent=8.0,
            lookback_periods=20,
        )

        assert strategy.min_profit_percent == 15.0
        assert strategy.max_loss_percent == 8.0
        assert strategy.lookback_periods == 20

    def test_evaluate_insufficient_history(self):
        """Test evaluation with insufficient history."""
        strategy = SimpleArbitrageStrategy(lookback_periods=10)

        current_price = PricePoint(
            timestamp=datetime.now(UTC),
            item_id="item_001",
            item_name="Test",
            price=10.0,
        )

        action, _price, reason = strategy.evaluate(
            current_price=current_price,
            historical_prices=[current_price] * 5,  # Only 5 points
            open_positions=[],
            balance=1000.0,
        )

        assert action == TradeAction.HOLD
        assert "Insufficient" in str(reason)

    def test_evaluate_buy_signal(self):
        """Test buy signal when price is below average."""
        strategy = SimpleArbitrageStrategy(
            buy_threshold_percent=5.0,
            lookback_periods=5,
        )

        # Create history with higher prices
        base_time = datetime.now(UTC)
        history = [
            PricePoint(
                timestamp=base_time - timedelta(hours=i),
                item_id="item_001",
                item_name="Test",
                price=12.0,  # Average price
            )
            for i in range(10)
        ]

        # Current price significantly below average
        current_price = PricePoint(
            timestamp=base_time,
            item_id="item_001",
            item_name="Test",
            price=10.0,  # ~17% below average
        )

        action, price, reason = strategy.evaluate(
            current_price=current_price,
            historical_prices=history,
            open_positions=[],
            balance=1000.0,
        )

        assert action == TradeAction.BUY
        assert price == 10.0
        assert "below average" in str(reason).lower()

    def test_evaluate_hold_insufficient_balance(self):
        """Test hold when balance is insufficient."""
        strategy = SimpleArbitrageStrategy(
            buy_threshold_percent=5.0, lookback_periods=5
        )

        history = [
            PricePoint(
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                item_id="item_001",
                item_name="Test",
                price=12.0,
            )
            for i in range(10)
        ]

        current_price = PricePoint(
            timestamp=datetime.now(UTC),
            item_id="item_001",
            item_name="Test",
            price=10.0,
        )

        action, _price, reason = strategy.evaluate(
            current_price=current_price,
            historical_prices=history,
            open_positions=[],
            balance=5.0,  # Too low
        )

        assert action == TradeAction.HOLD
        assert "balance" in str(reason).lower()

    def test_should_close_at_profit_target(self):
        """Test closing position at profit target."""
        strategy = SimpleArbitrageStrategy(min_profit_percent=10.0)

        position = SimulatedTrade(
            trade_id="BT-001",
            item_id="item_001",
            item_name="Test",
            action=TradeAction.BUY,
            price=10.0,
            quantity=1,
            timestamp=datetime.now(UTC),
        )

        current_price = PricePoint(
            timestamp=datetime.now(UTC),
            item_id="item_001",
            item_name="Test",
            price=11.5,  # 15% profit
        )

        should_close, reason = strategy.should_close_position(position, current_price)

        assert should_close is True
        assert "Profit target" in reason

    def test_should_close_at_stop_loss(self):
        """Test closing position at stop loss."""
        strategy = SimpleArbitrageStrategy(max_loss_percent=5.0)

        position = SimulatedTrade(
            trade_id="BT-001",
            item_id="item_001",
            item_name="Test",
            action=TradeAction.BUY,
            price=10.0,
            quantity=1,
            timestamp=datetime.now(UTC),
        )

        current_price = PricePoint(
            timestamp=datetime.now(UTC),
            item_id="item_001",
            item_name="Test",
            price=9.0,  # 10% loss
        )

        should_close, reason = strategy.should_close_position(position, current_price)

        assert should_close is True
        assert "Stop-loss" in reason


class TestMomentumStrategy:
    """Tests for MomentumStrategy."""

    def test_create_strategy(self):
        """Test creating momentum strategy."""
        strategy = MomentumStrategy()

        assert strategy.momentum_periods == 5
        assert strategy.momentum_threshold == 3.0
        assert "Momentum" in strategy.name

    def test_evaluate_positive_momentum(self):
        """Test buy signal on positive momentum."""
        strategy = MomentumStrategy(
            momentum_periods=5,
            momentum_threshold=3.0,
        )

        # Create upward trend
        base_time = datetime.now(UTC)
        history = [
            PricePoint(
                timestamp=base_time - timedelta(hours=10 - i),
                item_id="item_001",
                item_name="Test",
                price=10.0 + i * 0.5,  # Rising prices
            )
            for i in range(10)
        ]

        current_price = PricePoint(
            timestamp=base_time,
            item_id="item_001",
            item_name="Test",
            price=15.0,  # Much higher
        )

        action, _price, reason = strategy.evaluate(
            current_price=current_price,
            historical_prices=history,
            open_positions=[],
            balance=1000.0,
        )

        # Should buy due to positive momentum
        assert action == TradeAction.BUY
        assert "momentum" in str(reason).lower()


class TestMeanReversionStrategy:
    """Tests for MeanReversionStrategy."""

    def test_create_strategy(self):
        """Test creating mean reversion strategy."""
        strategy = MeanReversionStrategy()

        assert strategy.lookback_periods == 20
        assert strategy.std_threshold == 2.0
        assert "MeanReversion" in strategy.name

    def test_evaluate_below_mean(self):
        """Test buy signal when price is below mean."""
        strategy = MeanReversionStrategy(
            lookback_periods=10,
            std_threshold=1.5,
        )

        # Create history around price of 10
        base_time = datetime.now(UTC)
        history = [
            PricePoint(
                timestamp=base_time - timedelta(hours=20 - i),
                item_id="item_001",
                item_name="Test",
                price=10.0 + (i % 2) * 0.2,  # Small variance around 10
            )
            for i in range(20)
        ]

        # Current price significantly below mean
        current_price = PricePoint(
            timestamp=base_time,
            item_id="item_001",
            item_name="Test",
            price=8.0,  # Well below mean of ~10
        )

        action, _price, reason = strategy.evaluate(
            current_price=current_price,
            historical_prices=history,
            open_positions=[],
            balance=1000.0,
        )

        # Should buy when price is far below mean
        assert action == TradeAction.BUY
        assert "below mean" in str(reason).lower()


class TestBacktester:
    """Tests for Backtester class."""

    def test_create_backtester(self):
        """Test creating backtester."""
        bt = Backtester(initial_balance=1000.0, fee_percent=7.0)

        assert bt.initial_balance == 1000.0
        assert bt.current_balance == 1000.0
        assert bt.fee_percent == 7.0
        assert len(bt.data) == 0
        assert len(bt.trades) == 0

    def test_load_data_from_list(self, backtester):
        """Test loading data from list."""
        prices = [
            {
                "timestamp": datetime.now(UTC) - timedelta(hours=i),
                "price": 10.0 + i * 0.1,
                "volume": 5,
            }
            for i in range(10)
        ]

        backtester.load_data_from_list(
            item_id="item_001",
            item_name="Test Item",
            game="csgo",
            prices=prices,
        )

        assert "item_001" in backtester.data
        assert len(backtester.data["item_001"].prices) == 10

    def test_generate_sample_data(self, backtester):
        """Test generating sample data."""
        backtester.generate_sample_data(
            item_id="item_001",
            item_name="Test Item",
            game="csgo",
            base_price=10.0,
            volatility=0.05,
            num_days=7,
            points_per_day=24,
        )

        assert "item_001" in backtester.data
        assert len(backtester.data["item_001"].prices) == 7 * 24

    @pytest.mark.asyncio()
    async def test_run_backtest_no_data(self, backtester):
        """Test running backtest with no data."""
        strategy = SimpleArbitrageStrategy()

        with pytest.rAlgoses(ValueError, match="No historical data"):
            awAlgot backtester.run(strategy)

    @pytest.mark.asyncio()
    async def test_run_backtest_with_sample_data(self, backtester):
        """Test running backtest with sample data."""
        backtester.generate_sample_data(
            item_id="item_001",
            item_name="Test Item",
            base_price=10.0,
            volatility=0.1,
            num_days=30,
            points_per_day=24,
        )

        strategy = SimpleArbitrageStrategy(
            min_profit_percent=5.0,
            buy_threshold_percent=3.0,
        )

        results = awAlgot backtester.run(strategy, item_id="item_001")

        assert isinstance(results, BacktestResults)
        assert results.strategy_name == strategy.name
        assert results.initial_balance == 1000.0
        assert results.final_balance >= 0
        assert len(results.equity_curve) > 0

    @pytest.mark.asyncio()
    async def test_run_backtest_multiple_positions(self, backtester):
        """Test backtest with multiple positions."""
        backtester.generate_sample_data(
            item_id="item_001",
            item_name="Item 1",
            base_price=10.0,
            num_days=10,
        )
        backtester.generate_sample_data(
            item_id="item_002",
            item_name="Item 2",
            base_price=20.0,
            num_days=10,
        )

        strategy = SimpleArbitrageStrategy(
            min_profit_percent=5.0,
            buy_threshold_percent=2.0,
        )

        results = awAlgot backtester.run(strategy, max_positions=3)

        assert results.strategy_name == strategy.name
        # Should have processed both items
        {t.item_id for t in results.trades}
        # At least some trades should have occurred
        assert len(results.equity_curve) > 0


class TestBacktestResults:
    """Tests for BacktestResults."""

    def test_create_results(self):
        """Test creating backtest results."""
        results = BacktestResults(
            strategy_name="TestStrategy",
            start_date=datetime.now(UTC) - timedelta(days=30),
            end_date=datetime.now(UTC),
            initial_balance=1000.0,
            final_balance=1100.0,
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            total_roi=10.0,
        )

        assert results.strategy_name == "TestStrategy"
        assert results.total_trades == 10
        assert results.total_roi == 10.0

    def test_to_dict(self):
        """Test converting results to dict."""
        results = BacktestResults(
            strategy_name="TestStrategy",
            start_date=datetime.now(UTC) - timedelta(days=30),
            end_date=datetime.now(UTC),
            initial_balance=1000.0,
            final_balance=1100.0,
            total_roi=10.0,
            sharpe_ratio=1.5,
            max_drawdown=5.0,
            win_rate=70.0,
        )

        result_dict = results.to_dict()

        assert result_dict["strategy_name"] == "TestStrategy"
        assert result_dict["total_roi"] == 10.0
        assert result_dict["sharpe_ratio"] == 1.5
        assert "start_date" in result_dict
        assert "end_date" in result_dict


class TestBacktesterMetrics:
    """Tests for backtest metrics calculation."""

    def test_max_drawdown_calculation(self, backtester):
        """Test max drawdown calculation."""
        equity_curve = [
            (datetime.now(UTC) - timedelta(hours=5), 1000.0),
            (datetime.now(UTC) - timedelta(hours=4), 1100.0),  # Peak
            (datetime.now(UTC) - timedelta(hours=3), 990.0),  # Drawdown
            (datetime.now(UTC) - timedelta(hours=2), 1050.0),
            (datetime.now(UTC) - timedelta(hours=1), 1000.0),
        ]

        max_dd = backtester._calculate_max_drawdown(equity_curve)

        # Max drawdown from 1100 to 990 = 10%
        assert max_dd == 10.0

    def test_max_drawdown_no_drawdown(self, backtester):
        """Test max drawdown when equity only rises."""
        equity_curve = [
            (datetime.now(UTC) - timedelta(hours=i), 1000.0 + i * 10) for i in range(5)
        ]

        max_dd = backtester._calculate_max_drawdown(equity_curve)

        assert max_dd == 0.0

    def test_sharpe_ratio_calculation(self, backtester):
        """Test Sharpe ratio calculation."""
        # Create equity curve with some returns
        base_time = datetime.now(UTC)
        equity_curve = [
            (base_time - timedelta(hours=10 - i), 1000.0 + i * 5) for i in range(10)
        ]

        sharpe = backtester._calculate_sharpe_ratio(equity_curve)

        # Should return a positive number for consistently rising equity
        assert sharpe > 0

    def test_sharpe_ratio_insufficient_data(self, backtester):
        """Test Sharpe ratio with insufficient data."""
        equity_curve = [(datetime.now(UTC), 1000.0)]

        sharpe = backtester._calculate_sharpe_ratio(equity_curve)

        assert sharpe == 0.0


class TestStrategyComparison:
    """Tests for comparing multiple strategies."""

    @pytest.mark.asyncio()
    async def test_compare_strategies(self, backtester):
        """Test comparing multiple strategies."""
        backtester.generate_sample_data(
            item_id="item_001",
            item_name="Test Item",
            base_price=10.0,
            num_days=30,
        )

        strategies = [
            SimpleArbitrageStrategy(min_profit_percent=5.0),
            SimpleArbitrageStrategy(min_profit_percent=10.0),
            MomentumStrategy(momentum_threshold=5.0),
        ]

        results = []
        for strategy in strategies:
            result = awAlgot backtester.run(strategy, item_id="item_001")
            results.append(result)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, BacktestResults)

    def test_summary_table(self, backtester):
        """Test generating summary table."""
        results = [
            BacktestResults(
                strategy_name="Strategy A",
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC),
                initial_balance=1000.0,
                final_balance=1100.0,
                total_roi=10.0,
                win_rate=60.0,
                sharpe_ratio=1.5,
                max_drawdown=5.0,
                total_trades=20,
            ),
            BacktestResults(
                strategy_name="Strategy B",
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC),
                initial_balance=1000.0,
                final_balance=1050.0,
                total_roi=5.0,
                win_rate=55.0,
                sharpe_ratio=1.0,
                max_drawdown=8.0,
                total_trades=15,
            ),
        ]

        table = backtester.get_summary_table(results)

        assert "Strategy A" in table
        assert "Strategy B" in table
        assert "ROI" in table
        assert "Win Rate" in table
        assert "Sharpe" in table


class TestCustomStrategy:
    """Tests for creating custom strategies."""

    def test_custom_strategy(self):
        """Test implementing a custom strategy."""

        class CustomStrategy(TradingStrategy):
            @property
            def name(self) -> str:
                return "CustomStrategy"

            def evaluate(
                self,
                current_price: PricePoint,
                historical_prices: Sequence[PricePoint],
                open_positions: list[SimulatedTrade],
                balance: float,
            ) -> tuple[TradeAction, float | None, str | None]:
                # Always hold
                return TradeAction.HOLD, None, "Custom logic"

        strategy = CustomStrategy()

        assert strategy.name == "CustomStrategy"

        result = strategy.evaluate(
            current_price=PricePoint(
                timestamp=datetime.now(UTC),
                item_id="test",
                item_name="Test",
                price=10.0,
            ),
            historical_prices=[],
            open_positions=[],
            balance=1000.0,
        )

        assert result[0] == TradeAction.HOLD
