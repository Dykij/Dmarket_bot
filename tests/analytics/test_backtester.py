"""Tests for backtester.py - Backtesting engine for trading strategies.

This module tests Trade, Position, BacktestResult dataclasses,
TradingStrategy abstract class, SimpleArbitrageStrategy implementation,
and the mAlgon Backtester class.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.analytics.backtester import (
    Backtester,
    BacktestResult,
    Position,
    SimpleArbitrageStrategy,
    Trade,
    TradeType,
)
from src.analytics.historical_data import PriceHistory, PricePoint

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture()
def sample_trade_buy():
    """Create a sample buy trade."""
    return Trade(
        trade_type=TradeType.BUY,
        item_title="AK-47 | Redline (FT)",
        price=Decimal("10.00"),
        quantity=5,
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
        fees=Decimal(0),
    )


@pytest.fixture()
def sample_trade_sell():
    """Create a sample sell trade."""
    return Trade(
        trade_type=TradeType.SELL,
        item_title="AK-47 | Redline (FT)",
        price=Decimal("12.00"),
        quantity=5,
        timestamp=datetime(2025, 1, 2, 12, 0, 0),
        fees=Decimal("4.20"),  # 7% fee
    )


@pytest.fixture()
def sample_position():
    """Create a sample position."""
    return Position(
        item_title="AK-47 | Redline (FT)",
        quantity=5,
        average_cost=Decimal("10.00"),
        created_at=datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture()
def sample_price_history():
    """Create sample price history."""
    base_date = datetime(2025, 1, 1)
    points = [
        PricePoint(
            game="csgo",
            title="AK-47 | Redline (FT)",
            timestamp=base_date + timedelta(days=i),
            price=Decimal(str(10 + i * 0.5)),  # Gradually increasing
        )
        for i in range(10)
    ]
    return PriceHistory(
        title="AK-47 | Redline (FT)",
        game="csgo",
        points=points,
    )


@pytest.fixture()
def sample_backtest_result():
    """Create a sample backtest result."""
    return BacktestResult(
        strategy_name="TestStrategy",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        initial_balance=Decimal(1000),
        final_balance=Decimal(1100),
        total_trades=10,
        profitable_trades=7,
        total_profit=Decimal(100),
        max_drawdown=Decimal(5),
        sharpe_ratio=1.5,
        win_rate=70.0,
        trades=[],
        positions_closed=5,
    )


# ============================================================================
# Test TradeType Enum
# ============================================================================


class TestTradeType:
    """Tests for TradeType enum."""

    def test_buy_value(self):
        """Test BUY enum value."""
        assert TradeType.BUY.value == "buy"

    def test_sell_value(self):
        """Test SELL enum value."""
        assert TradeType.SELL.value == "sell"

    def test_enum_string_comparison(self):
        """Test enum string comparison."""
        assert TradeType.BUY == "buy"
        assert TradeType.SELL == "sell"


# ============================================================================
# Test Trade Dataclass
# ============================================================================


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self, sample_trade_buy):
        """Test trade creation."""
        assert sample_trade_buy.trade_type == TradeType.BUY
        assert sample_trade_buy.item_title == "AK-47 | Redline (FT)"
        assert sample_trade_buy.price == Decimal("10.00")
        assert sample_trade_buy.quantity == 5

    def test_total_cost_buy_no_fees(self, sample_trade_buy):
        """Test total cost for buy with no fees."""
        assert sample_trade_buy.total_cost == Decimal("50.00")

    def test_total_cost_sell_with_fees(self, sample_trade_sell):
        """Test total cost for sell with fees."""
        # Price * quantity + fees
        expected = Decimal("12.00") * 5 + Decimal("4.20")
        assert sample_trade_sell.total_cost == expected

    def test_net_amount_buy(self, sample_trade_buy):
        """Test net amount for buy trade (negative)."""
        # Buy trades should be negative (money out)
        assert sample_trade_buy.net_amount == -Decimal("50.00")

    def test_net_amount_sell(self, sample_trade_sell):
        """Test net amount for sell trade (positive after fees)."""
        # Sell: price * quantity - fees
        expected = Decimal("12.00") * 5 - Decimal("4.20")
        assert sample_trade_sell.net_amount == expected

    def test_trade_default_fees(self):
        """Test trade default fees is zero."""
        trade = Trade(
            trade_type=TradeType.BUY,
            item_title="Test",
            price=Decimal("5.00"),
            quantity=1,
            timestamp=datetime.now(),
        )
        assert trade.fees == Decimal(0)


# ============================================================================
# Test Position Dataclass
# ============================================================================


class TestPosition:
    """Tests for Position dataclass."""

    def test_position_creation(self, sample_position):
        """Test position creation."""
        assert sample_position.item_title == "AK-47 | Redline (FT)"
        assert sample_position.quantity == 5
        assert sample_position.average_cost == Decimal("10.00")

    def test_total_value(self, sample_position):
        """Test total value calculation."""
        assert sample_position.total_value == Decimal("50.00")

    def test_update_position(self, sample_position):
        """Test updating position with new purchase."""
        # Add 5 more at $12
        sample_position.update(5, Decimal("12.00"))

        assert sample_position.quantity == 10
        # Average: (50 + 60) / 10 = 11
        assert sample_position.average_cost == Decimal("11.00")

    def test_update_position_different_price(self):
        """Test updating position with different price."""
        position = Position(
            item_title="Test",
            quantity=10,
            average_cost=Decimal("5.00"),
            created_at=datetime.now(),
        )

        # Add 10 more at $10
        position.update(10, Decimal("10.00"))

        assert position.quantity == 20
        # Average: (50 + 100) / 20 = 7.5
        assert position.average_cost == Decimal("7.50")


# ============================================================================
# Test BacktestResult Dataclass
# ============================================================================


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_result_creation(self, sample_backtest_result):
        """Test backtest result creation."""
        assert sample_backtest_result.strategy_name == "TestStrategy"
        assert sample_backtest_result.total_trades == 10
        assert sample_backtest_result.profitable_trades == 7

    def test_total_return_positive(self, sample_backtest_result):
        """Test total return calculation (positive)."""
        # (1100 - 1000) / 1000 * 100 = 10%
        assert sample_backtest_result.total_return == 10.0

    def test_total_return_zero_initial_balance(self):
        """Test total return with zero initial balance."""
        result = BacktestResult(
            strategy_name="Test",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            initial_balance=Decimal(0),
            final_balance=Decimal(100),
            total_trades=1,
            profitable_trades=1,
            total_profit=Decimal(100),
            max_drawdown=Decimal(0),
            sharpe_ratio=0,
            win_rate=100.0,
        )
        assert result.total_return == 0.0

    def test_avg_profit_per_trade(self, sample_backtest_result):
        """Test average profit per trade."""
        # 100 / 10 = 10
        assert sample_backtest_result.avg_profit_per_trade == Decimal(10)

    def test_avg_profit_no_trades(self):
        """Test average profit with no trades."""
        result = BacktestResult(
            strategy_name="Test",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            initial_balance=Decimal(1000),
            final_balance=Decimal(1000),
            total_trades=0,
            profitable_trades=0,
            total_profit=Decimal(0),
            max_drawdown=Decimal(0),
            sharpe_ratio=0,
            win_rate=0.0,
        )
        assert result.avg_profit_per_trade == Decimal(0)

    def test_to_dict(self, sample_backtest_result):
        """Test conversion to dictionary."""
        d = sample_backtest_result.to_dict()

        assert d["strategy_name"] == "TestStrategy"
        assert d["total_trades"] == 10
        assert d["profitable_trades"] == 7
        assert d["total_profit"] == 100.0
        assert d["win_rate"] == 70.0
        assert d["sharpe_ratio"] == 1.5
        assert "start_date" in d
        assert "end_date" in d


# ============================================================================
# Test SimpleArbitrageStrategy
# ============================================================================


class TestSimpleArbitrageStrategy:
    """Tests for SimpleArbitrageStrategy."""

    def test_strategy_creation(self):
        """Test strategy creation with default params."""
        strategy = SimpleArbitrageStrategy()

        assert strategy.name == "SimpleArbitrage"
        assert strategy.buy_threshold == 0.05
        assert strategy.sell_margin == 0.08
        assert strategy.max_position_pct == 0.1
        assert strategy.dmarket_fee == 0.07

    def test_strategy_custom_params(self):
        """Test strategy with custom parameters."""
        strategy = SimpleArbitrageStrategy(
            buy_threshold=0.10,
            sell_margin=0.15,
            max_position_pct=0.2,
            dmarket_fee=0.05,
        )

        assert strategy.buy_threshold == 0.10
        assert strategy.sell_margin == 0.15
        assert strategy.max_position_pct == 0.2
        assert strategy.dmarket_fee == 0.05

    def test_should_buy_below_average(self, sample_price_history):
        """Test should_buy when price is below average."""
        strategy = SimpleArbitrageStrategy(buy_threshold=0.10)

        # Price well below average
        current_price = Decimal("5.00")  # Below avg ~12.25
        balance = Decimal(1000)
        positions = {}

        should_buy, price, qty = strategy.should_buy(
            sample_price_history, current_price, balance, positions
        )

        assert should_buy is True
        assert price == current_price
        assert qty > 0

    def test_should_buy_above_average(self, sample_price_history):
        """Test should_buy when price is above average."""
        strategy = SimpleArbitrageStrategy(buy_threshold=0.05)

        # Price above average
        current_price = Decimal("15.00")
        balance = Decimal(1000)
        positions = {}

        should_buy, _price, qty = strategy.should_buy(
            sample_price_history, current_price, balance, positions
        )

        assert should_buy is False
        assert qty == 0

    def test_should_buy_already_has_position(self, sample_price_history):
        """Test should_buy returns False when already has position."""
        strategy = SimpleArbitrageStrategy()

        current_price = Decimal("5.00")
        balance = Decimal(1000)
        positions = {
            "AK-47 | Redline (FT)": Position(
                item_title="AK-47 | Redline (FT)",
                quantity=5,
                average_cost=Decimal("10.00"),
                created_at=datetime.now(),
            )
        }

        should_buy, _price, _qty = strategy.should_buy(
            sample_price_history, current_price, balance, positions
        )

        assert should_buy is False

    def test_should_buy_insufficient_balance(self, sample_price_history):
        """Test should_buy with insufficient balance."""
        strategy = SimpleArbitrageStrategy(max_position_pct=0.1)

        current_price = Decimal("100.00")
        balance = Decimal(50)  # Too low
        positions = {}

        should_buy, _price, _qty = strategy.should_buy(
            sample_price_history, current_price, balance, positions
        )

        assert should_buy is False

    def test_should_sell_target_reached(self, sample_position):
        """Test should_sell when target price reached."""
        strategy = SimpleArbitrageStrategy(sell_margin=0.08, dmarket_fee=0.07)

        # Create price history
        price_history = PriceHistory(
            title="AK-47 | Redline (FT)",
            game="csgo",
            points=[],
        )

        # Price above target (cost * 1.15)
        current_price = Decimal("12.00")  # > 10 * 1.15

        should_sell, _price, qty = strategy.should_sell(
            price_history, current_price, sample_position
        )

        assert should_sell is True
        assert qty == sample_position.quantity

    def test_should_sell_below_target(self, sample_position):
        """Test should_sell when price below target."""
        strategy = SimpleArbitrageStrategy(sell_margin=0.08, dmarket_fee=0.07)

        price_history = PriceHistory(
            title="AK-47 | Redline (FT)",
            game="csgo",
            points=[],
        )

        # Price below target
        current_price = Decimal("10.50")

        should_sell, _price, _qty = strategy.should_sell(
            price_history, current_price, sample_position
        )

        assert should_sell is False

    def test_should_sell_stop_loss(self, sample_position):
        """Test should_sell triggers stop loss."""
        strategy = SimpleArbitrageStrategy()

        price_history = PriceHistory(
            title="AK-47 | Redline (FT)",
            game="csgo",
            points=[],
        )

        # Price below 90% of average cost (stop loss)
        current_price = Decimal("8.00")  # < 10 * 0.90

        should_sell, _price, _qty = strategy.should_sell(
            price_history, current_price, sample_position
        )

        assert should_sell is True


# ============================================================================
# Test Backtester Class
# ============================================================================


class TestBacktester:
    """Tests for Backtester class."""

    def test_backtester_creation(self):
        """Test backtester creation."""
        backtester = Backtester()
        assert backtester.fee_rate == 0.07

    def test_backtester_custom_fee(self):
        """Test backtester with custom fee rate."""
        backtester = Backtester(fee_rate=0.05)
        assert backtester.fee_rate == 0.05

    @pytest.mark.asyncio()
    async def test_run_basic_backtest(self, sample_price_history):
        """Test running a basic backtest."""
        backtester = Backtester()
        strategy = SimpleArbitrageStrategy()

        price_histories = {"AK-47 | Redline (FT)": sample_price_history}

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=price_histories,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 10),
            initial_balance=Decimal(1000),
        )

        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "SimpleArbitrage"
        assert result.initial_balance == Decimal(1000)

    @pytest.mark.asyncio()
    async def test_run_empty_price_history(self):
        """Test running backtest with empty price history."""
        backtester = Backtester()
        strategy = SimpleArbitrageStrategy()

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories={},
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 10),
            initial_balance=Decimal(1000),
        )

        assert result.total_trades == 0
        assert result.final_balance == Decimal(1000)

    def test_get_price_at_date_exact(self, sample_price_history):
        """Test getting price at exact date."""
        backtester = Backtester()

        target_date = datetime(2025, 1, 1)
        point = backtester._get_price_at_date(sample_price_history, target_date)

        assert point is not None
        assert point.price == Decimal(10)

    def test_get_price_at_date_no_match(self, sample_price_history):
        """Test getting price at date with no matching point."""
        backtester = Backtester()

        # Date far from any points
        target_date = datetime(2024, 1, 1)
        point = backtester._get_price_at_date(sample_price_history, target_date)

        assert point is None

    def test_get_price_at_date_empty_history(self):
        """Test getting price from empty history."""
        backtester = Backtester()

        empty_history = PriceHistory(
            title="Test",
            game="csgo",
            points=[],
        )

        point = backtester._get_price_at_date(empty_history, datetime.now())

        assert point is None

    def test_execute_buy(self):
        """Test execute buy trade."""
        backtester = Backtester()

        trade = backtester._execute_buy(
            title="Test Item",
            price=Decimal("10.00"),
            quantity=5,
            timestamp=datetime(2025, 1, 1),
        )

        assert trade.trade_type == TradeType.BUY
        assert trade.price == Decimal("10.00")
        assert trade.quantity == 5
        assert trade.fees == Decimal(0)  # No fees on buy

    def test_execute_sell(self, sample_position):
        """Test execute sell trade."""
        backtester = Backtester(fee_rate=0.07)

        trade = backtester._execute_sell(
            title="Test Item",
            price=Decimal("12.00"),
            quantity=5,
            timestamp=datetime(2025, 1, 1),
            position=sample_position,
        )

        assert trade.trade_type == TradeType.SELL
        assert trade.price == Decimal("12.00")
        assert trade.quantity == 5
        # Fee: 12 * 5 * 0.07 = 4.20
        assert trade.fees == Decimal("4.20")

    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation."""
        backtester = Backtester()

        # Balance history with 10% drawdown
        balance_history = [
            Decimal(1000),
            Decimal(1100),  # Peak
            Decimal(990),  # Drawdown: (1100-990)/1100 = 10%
            Decimal(1050),
        ]

        max_dd = backtester._calculate_max_drawdown(balance_history)

        assert max_dd == Decimal(10)  # 10%

    def test_calculate_max_drawdown_no_drawdown(self):
        """Test max drawdown with no drawdown."""
        backtester = Backtester()

        # Always increasing
        balance_history = [
            Decimal(1000),
            Decimal(1100),
            Decimal(1200),
        ]

        max_dd = backtester._calculate_max_drawdown(balance_history)

        assert max_dd == Decimal(0)

    def test_calculate_max_drawdown_short_history(self):
        """Test max drawdown with short history."""
        backtester = Backtester()

        balance_history = [Decimal(1000)]

        max_dd = backtester._calculate_max_drawdown(balance_history)

        assert max_dd == Decimal(0)

    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        backtester = Backtester()

        # Steady returns
        balance_history = [
            Decimal(1000),
            Decimal(1010),  # 1% return
            Decimal("1020.10"),  # ~1% return
            Decimal("1030.30"),  # ~1% return
        ]

        sharpe = backtester._calculate_sharpe_ratio(balance_history)

        assert isinstance(sharpe, float)

    def test_calculate_sharpe_ratio_short_history(self):
        """Test Sharpe ratio with short history."""
        backtester = Backtester()

        balance_history = [Decimal(1000)]

        sharpe = backtester._calculate_sharpe_ratio(balance_history)

        assert sharpe == 0.0

    def test_calculate_sharpe_ratio_no_variance(self):
        """Test Sharpe ratio with no variance."""
        backtester = Backtester()

        # Same balance every day
        balance_history = [Decimal(1000)] * 10

        sharpe = backtester._calculate_sharpe_ratio(balance_history)

        assert sharpe == 0.0


# ============================================================================
# Test Integration Scenarios
# ============================================================================


class TestBacktestIntegration:
    """Integration tests for backtesting scenarios."""

    @pytest.mark.asyncio()
    async def test_complete_trading_cycle(self):
        """Test a complete trading cycle (buy -> sell)."""
        backtester = Backtester(fee_rate=0.07)
        strategy = SimpleArbitrageStrategy(
            buy_threshold=0.20,  # Buy when 20% below average
            sell_margin=0.10,
            max_position_pct=0.5,
        )

        # Create price history that triggers buy then sell
        base_date = datetime(2025, 1, 1)
        points = [
            PricePoint(
                game="csgo", title="Test Item", timestamp=base_date, price=Decimal(10)
            ),
            PricePoint(
                game="csgo",
                title="Test Item",
                timestamp=base_date + timedelta(days=1),
                price=Decimal(7),
            ),  # Dip
            PricePoint(
                game="csgo",
                title="Test Item",
                timestamp=base_date + timedelta(days=2),
                price=Decimal(8),
            ),
            PricePoint(
                game="csgo",
                title="Test Item",
                timestamp=base_date + timedelta(days=3),
                price=Decimal(9),
            ),
            PricePoint(
                game="csgo",
                title="Test Item",
                timestamp=base_date + timedelta(days=4),
                price=Decimal(12),
            ),  # Rise
        ]

        price_histories = {
            "Test Item": PriceHistory(title="Test Item", game="csgo", points=points)
        }

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=price_histories,
            start_date=base_date,
            end_date=base_date + timedelta(days=4),
            initial_balance=Decimal(1000),
        )

        assert isinstance(result, BacktestResult)

    @pytest.mark.asyncio()
    async def test_multiple_items(self):
        """Test backtesting with multiple items."""
        backtester = Backtester()
        strategy = SimpleArbitrageStrategy()

        base_date = datetime(2025, 1, 1)

        # Create price histories for multiple items
        price_histories = {}
        for i, name in enumerate(["Item A", "Item B", "Item C"]):
            points = [
                PricePoint(
                    game="csgo",
                    title=name,
                    timestamp=base_date + timedelta(days=d),
                    price=Decimal(str(10 + i + d * 0.1)),
                )
                for d in range(5)
            ]
            price_histories[name] = PriceHistory(title=name, game="csgo", points=points)

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=price_histories,
            start_date=base_date,
            end_date=base_date + timedelta(days=4),
            initial_balance=Decimal(1000),
        )

        assert isinstance(result, BacktestResult)

    @pytest.mark.asyncio()
    async def test_result_metrics_consistency(self):
        """Test that result metrics are consistent."""
        backtester = Backtester()
        strategy = SimpleArbitrageStrategy()

        base_date = datetime(2025, 1, 1)
        points = [
            PricePoint(
                game="csgo",
                title="Test",
                timestamp=base_date + timedelta(days=d),
                price=Decimal(10),
            )
            for d in range(10)
        ]

        price_histories = {
            "Test": PriceHistory(title="Test", game="csgo", points=points)
        }

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=price_histories,
            start_date=base_date,
            end_date=base_date + timedelta(days=9),
            initial_balance=Decimal(1000),
        )

        # Profitable trades <= total trades
        assert result.profitable_trades <= result.total_trades

        # Win rate is consistent with profitable/total
        if result.total_trades > 0:
            expected_win_rate = (result.profitable_trades / result.total_trades) * 100
            assert abs(result.win_rate - expected_win_rate) < 0.01
