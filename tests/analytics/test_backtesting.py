"""Tests for historical data collector and backtester."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analytics.backtester import (
    Backtester,
    BacktestResult,
    Position,
    SimpleArbitrageStrategy,
    Trade,
    TradeType,
)
from src.analytics.historical_data import (
    HistoricalDataCollector,
    PriceHistory,
    PricePoint,
)


class TestPricePoint:
    """Tests for PricePoint dataclass."""

    def test_create_price_point(self):
        """Test creating a price point."""
        point = PricePoint(
            game="csgo",
            title="Test Item",
            price=Decimal("10.50"),
            timestamp=datetime.now(UTC),
            volume=5,
            source="market",
        )

        assert point.game == "csgo"
        assert point.title == "Test Item"
        assert point.price == Decimal("10.50")
        assert point.volume == 5
        assert point.source == "market"

    def test_to_dict(self):
        """Test converting to dictionary."""
        point = PricePoint(
            game="csgo",
            title="Test Item",
            price=Decimal("10.50"),
            timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = point.to_dict()

        assert data["game"] == "csgo"
        assert data["title"] == "Test Item"
        assert data["price"] == 10.50
        assert "timestamp" in data

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "game": "csgo",
            "title": "Test Item",
            "price": 10.50,
            "volume": 3,
            "timestamp": "2025-01-01T12:00:00+00:00",
            "source": "sales_history",
        }

        point = PricePoint.from_dict(data)

        assert point.game == "csgo"
        assert point.price == Decimal("10.50")
        assert point.volume == 3
        assert point.source == "sales_history"


class TestPriceHistory:
    """Tests for PriceHistory dataclass."""

    def test_empty_history(self):
        """Test empty price history."""
        history = PriceHistory(game="csgo", title="Test Item")

        assert history.average_price == Decimal(0)
        assert history.min_price == Decimal(0)
        assert history.max_price == Decimal(0)
        assert history.total_volume == 0
        assert history.price_volatility == 0.0

    def test_history_with_points(self):
        """Test history with price points."""
        now = datetime.now(UTC)
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                PricePoint("csgo", "Test Item", Decimal(10), now, 5),
                PricePoint("csgo", "Test Item", Decimal(12), now, 3),
                PricePoint("csgo", "Test Item", Decimal(11), now, 2),
            ],
        )

        assert history.average_price == Decimal(11)
        assert history.min_price == Decimal(10)
        assert history.max_price == Decimal(12)
        assert history.total_volume == 10

    def test_price_volatility(self):
        """Test price volatility calculation."""
        now = datetime.now(UTC)
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                PricePoint("csgo", "Test Item", Decimal(100), now),
                PricePoint("csgo", "Test Item", Decimal(110), now),
                PricePoint("csgo", "Test Item", Decimal(90), now),
                PricePoint("csgo", "Test Item", Decimal(100), now),
            ],
        )

        volatility = history.price_volatility
        assert volatility > 0
        assert volatility < 1  # Should be a small percentage


class TestHistoricalDataCollector:
    """Tests for HistoricalDataCollector."""

    @pytest.fixture()
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_sales_history = AsyncMock(return_value={"sales": []})
        api.get_aggregated_prices_bulk = AsyncMock(
            return_value={"aggregatedPrices": []}
        )
        return api

    @pytest.fixture()
    def collector(self, mock_api):
        """Create collector with mock API."""
        return HistoricalDataCollector(mock_api)

    @pytest.mark.asyncio()
    async def test_collect_price_history_empty(self, collector):
        """Test collecting empty price history."""
        history = await collector.collect_price_history("csgo", "Test Item", days=30)

        assert history.game == "csgo"
        assert history.title == "Test Item"
        assert len(history.points) == 0

    @pytest.mark.asyncio()
    async def test_collect_with_sales_data(self, mock_api, collector):
        """Test collecting with sales history data."""
        mock_api.get_sales_history.return_value = {
            "sales": [
                {
                    "price": {"USD": 1050},
                    "date": "2025-01-01T12:00:00Z",
                },
                {
                    "price": {"USD": 1100},
                    "date": "2025-01-02T12:00:00Z",
                },
            ]
        }

        history = await collector.collect_price_history("csgo", "Test Item", days=30)

        assert len(history.points) == 2
        assert history.points[0].price == Decimal("10.50")
        assert history.points[1].price == Decimal("11.00")

    @pytest.mark.asyncio()
    async def test_cache_works(self, collector, mock_api):
        """Test that caching works."""
        # First call
        await collector.collect_price_history("csgo", "Test Item", days=30)

        # Second call should use cache
        await collector.collect_price_history("csgo", "Test Item", days=30)

        # API should only be called once
        assert mock_api.get_sales_history.call_count == 1

    def test_clear_cache(self, collector):
        """Test cache clearing."""
        collector._cache["test"] = (datetime.now(UTC), PriceHistory("csgo", "Test"))

        collector.clear_cache()

        assert len(collector._cache) == 0

    def test_get_cache_stats(self, collector):
        """Test getting cache statistics."""
        stats = collector.get_cache_stats()

        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "ttl_minutes" in stats


class TestTrade:
    """Tests for Trade dataclass."""

    def test_buy_trade_total_cost(self):
        """Test total cost for buy trade."""
        trade = Trade(
            trade_type=TradeType.BUY,
            item_title="Test Item",
            price=Decimal(10),
            quantity=2,
            timestamp=datetime.now(UTC),
            fees=Decimal(0),
        )

        assert trade.total_cost == Decimal(20)
        assert trade.net_amount == Decimal(-20)

    def test_sell_trade_net_amount(self):
        """Test net amount for sell trade."""
        trade = Trade(
            trade_type=TradeType.SELL,
            item_title="Test Item",
            price=Decimal(10),
            quantity=2,
            timestamp=datetime.now(UTC),
            fees=Decimal("1.40"),  # 7% fee
        )

        assert trade.net_amount == Decimal("18.60")


class TestPosition:
    """Tests for Position dataclass."""

    def test_position_update(self):
        """Test updating position with additional purchase."""
        position = Position(
            item_title="Test Item",
            quantity=2,
            average_cost=Decimal(10),
            created_at=datetime.now(UTC),
        )

        position.update(3, Decimal(12))

        assert position.quantity == 5
        # Average: (2*10 + 3*12) / 5 = (20 + 36) / 5 = 56/5 = 11.2
        assert position.average_cost == Decimal("11.2")

    def test_position_total_value(self):
        """Test position total value."""
        position = Position(
            item_title="Test Item",
            quantity=5,
            average_cost=Decimal(10),
            created_at=datetime.now(UTC),
        )

        assert position.total_value == Decimal(50)


class TestSimpleArbitrageStrategy:
    """Tests for SimpleArbitrageStrategy."""

    @pytest.fixture()
    def strategy(self):
        """Create strategy with default settings."""
        return SimpleArbitrageStrategy(
            buy_threshold=0.05,
            sell_margin=0.08,
            max_position_pct=0.1,
        )

    def test_should_not_buy_if_already_have_position(self, strategy):
        """Test that strategy doesn't buy if position exists."""
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                PricePoint("csgo", "Test Item", Decimal(10), datetime.now(UTC)),
            ],
        )
        positions = {
            "Test Item": Position("Test Item", 1, Decimal(9), datetime.now(UTC))
        }

        should_buy, _, _ = strategy.should_buy(
            history,
            Decimal("9.50"),
            Decimal(100),
            positions,
        )

        assert should_buy is False

    def test_should_buy_when_below_threshold(self, strategy):
        """Test buying when price is below threshold."""
        now = datetime.now(UTC)
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                PricePoint("csgo", "Test Item", Decimal(10), now),
                PricePoint("csgo", "Test Item", Decimal(10), now),
            ],
        )

        # Price at 9.40 is 6% below average of 10 (below 5% threshold)
        should_buy, price, quantity = strategy.should_buy(
            history,
            Decimal("9.40"),
            Decimal(100),
            {},
        )

        assert should_buy is True
        assert price == Decimal("9.40")
        assert quantity >= 1

    def test_should_not_buy_when_price_too_high(self, strategy):
        """Test not buying when price is above threshold."""
        now = datetime.now(UTC)
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                PricePoint("csgo", "Test Item", Decimal(10), now),
            ],
        )

        # Price at 9.60 is only 4% below average (above 5% threshold)
        should_buy, _, _ = strategy.should_buy(
            history,
            Decimal("9.60"),
            Decimal(100),
            {},
        )

        assert should_buy is False

    def test_should_sell_at_target_margin(self, strategy):
        """Test selling at target margin."""
        history = PriceHistory(game="csgo", title="Test Item")
        position = Position("Test Item", 1, Decimal(10), datetime.now(UTC))

        # Target price: 10 * (1 + 0.08 + 0.07) = 11.50
        # We need to be AT or ABOVE this price
        should_sell, price, _quantity = strategy.should_sell(
            history,
            Decimal("11.60"),  # Slightly above target
            position,
        )

        assert should_sell is True
        assert price == Decimal("11.60")

    def test_should_sell_on_stop_loss(self, strategy):
        """Test selling on stop loss."""
        history = PriceHistory(game="csgo", title="Test Item")
        position = Position("Test Item", 1, Decimal(10), datetime.now(UTC))

        # Stop loss at -10%: 10 * 0.90 = 9.0
        should_sell, _price, _quantity = strategy.should_sell(
            history,
            Decimal("8.90"),
            position,
        )

        assert should_sell is True


class TestBacktester:
    """Tests for Backtester."""

    @pytest.fixture()
    def backtester(self):
        """Create backtester."""
        return Backtester(fee_rate=0.07)

    @pytest.mark.asyncio()
    async def test_run_backtest_empty_data(self, backtester):
        """Test running backtest with empty data."""
        strategy = SimpleArbitrageStrategy()
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)

        result = await backtester.run(
            strategy=strategy,
            price_histories={},
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal(100),
        )

        assert result.total_trades == 0
        assert result.final_balance == Decimal(100)
        assert result.total_profit == Decimal(0)

    @pytest.mark.asyncio()
    async def test_run_backtest_with_data(self, backtester):
        """Test running backtest with price data."""
        strategy = SimpleArbitrageStrategy(
            buy_threshold=0.05,
            sell_margin=0.08,
        )

        # Create price history with opportunity
        now = datetime.now(UTC)
        history = PriceHistory(
            game="csgo",
            title="Test Item",
            points=[
                # Day 1: Price at 10 (baseline)
                PricePoint("csgo", "Test Item", Decimal(10), now - timedelta(days=3)),
                # Day 2: Price drops to 9 (10% below - good buy)
                PricePoint("csgo", "Test Item", Decimal(9), now - timedelta(days=2)),
                # Day 3: Price rises to 11.50 (above sell target)
                PricePoint(
                    "csgo", "Test Item", Decimal("11.50"), now - timedelta(days=1)
                ),
            ],
        )

        result = await backtester.run(
            strategy=strategy,
            price_histories={"Test Item": history},
            start_date=now - timedelta(days=3),
            end_date=now,
            initial_balance=Decimal(100),
        )

        assert result.strategy_name == "SimpleArbitrage"
        assert isinstance(result.total_trades, int)

    def test_calculate_max_drawdown(self, backtester):
        """Test max drawdown calculation."""
        balance_history = [
            Decimal(100),
            Decimal(110),  # +10%
            Decimal(88),  # -20% from peak (drawdown)
            Decimal(99),  # Recovery
        ]

        drawdown = backtester._calculate_max_drawdown(balance_history)

        assert drawdown == Decimal(20)  # 20% drawdown

    def test_calculate_sharpe_ratio(self, backtester):
        """Test Sharpe ratio calculation."""
        # Steady positive returns
        balance_history = [
            Decimal(100),
            Decimal(101),
            Decimal(102),
            Decimal(103),
        ]

        sharpe = backtester._calculate_sharpe_ratio(balance_history)

        # Should be positive for positive returns
        assert sharpe > 0


class TestBacktestResult:
    """Tests for BacktestResult."""

    def test_total_return(self):
        """Test total return calculation."""
        result = BacktestResult(
            strategy_name="Test",
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC),
            initial_balance=Decimal(100),
            final_balance=Decimal(120),
            total_trades=10,
            profitable_trades=7,
            total_profit=Decimal(20),
            max_drawdown=Decimal(5),
            sharpe_ratio=1.5,
            win_rate=70.0,
        )

        assert result.total_return == 20.0

    def test_avg_profit_per_trade(self):
        """Test average profit per trade."""
        result = BacktestResult(
            strategy_name="Test",
            start_date=datetime.now(UTC),
            end_date=datetime.now(UTC),
            initial_balance=Decimal(100),
            final_balance=Decimal(120),
            total_trades=10,
            profitable_trades=7,
            total_profit=Decimal(20),
            max_drawdown=Decimal(5),
            sharpe_ratio=1.5,
            win_rate=70.0,
        )

        assert result.avg_profit_per_trade == Decimal(2)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = BacktestResult(
            strategy_name="Test",
            start_date=datetime(2025, 1, 1, tzinfo=UTC),
            end_date=datetime(2025, 1, 31, tzinfo=UTC),
            initial_balance=Decimal(100),
            final_balance=Decimal(120),
            total_trades=10,
            profitable_trades=7,
            total_profit=Decimal(20),
            max_drawdown=Decimal(5),
            sharpe_ratio=1.5,
            win_rate=70.0,
        )

        data = result.to_dict()

        assert data["strategy_name"] == "Test"
        assert data["total_trades"] == 10
        assert data["total_profit"] == 20.0
        assert data["win_rate"] == 70.0
