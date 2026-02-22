"""Tests for Portfolio Tracker Module."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.portfolio.portfolio_tracker import (
    InventoryItem,
    Marketplace,
    PerformanceMetrics,
    PortfolioSummary,
    PortfolioTracker,
    Trade,
    TradeType,
    create_portfolio_tracker,
)


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            trade_id="T000001",
            item_name="AK-47 | Redline",
            trade_type=TradeType.BUY,
            marketplace=Marketplace.DMARKET,
            price=Decimal("50.0"),
            commission=Decimal("0"),
            net_amount=Decimal("50.0"),
            timestamp=datetime.now(UTC),
        )

        assert trade.trade_id == "T000001"
        assert trade.trade_type == TradeType.BUY

    def test_trade_to_dict(self):
        """Test trade to dict conversion."""
        trade = Trade(
            trade_id="T000001",
            item_name="Test",
            trade_type=TradeType.SELL,
            marketplace=Marketplace.WAXPEER,
            price=Decimal("60.0"),
            commission=Decimal("3.6"),
            net_amount=Decimal("56.4"),
            timestamp=datetime.now(UTC),
        )

        data = trade.to_dict()
        assert "trade_id" in data
        assert "type" in data
        assert data["type"] == "sell"


class TestInventoryItem:
    """Tests for InventoryItem dataclass."""

    def test_unrealized_pnl_profit(self):
        """Test unrealized P/L calculation with profit."""
        item = InventoryItem(
            item_id="item1",
            item_name="Test Item",
            marketplace=Marketplace.DMARKET,
            purchase_price=Decimal("50.0"),
            current_price=Decimal("60.0"),
        )

        assert item.unrealized_pnl == Decimal("10.0")
        assert item.unrealized_pnl_percent == Decimal("20.0")

    def test_unrealized_pnl_loss(self):
        """Test unrealized P/L calculation with loss."""
        item = InventoryItem(
            item_id="item1",
            item_name="Test Item",
            marketplace=Marketplace.DMARKET,
            purchase_price=Decimal("60.0"),
            current_price=Decimal("50.0"),
        )

        assert item.unrealized_pnl == Decimal("-10.0")
        assert float(item.unrealized_pnl_percent) == pytest.approx(-16.67, rel=0.01)

    def test_to_dict(self):
        """Test to dict conversion."""
        item = InventoryItem(
            item_id="item1",
            item_name="Test",
            marketplace=Marketplace.DMARKET,
            purchase_price=Decimal("50.0"),
            current_price=Decimal("55.0"),
        )

        data = item.to_dict()
        assert "unrealized_pnl" in data
        assert "marketplace" in data


class TestPortfolioTracker:
    """Tests for PortfolioTracker."""

    @pytest.fixture
    def tracker(self):
        """Create test tracker."""
        return PortfolioTracker(user_id=123)

    def test_record_buy(self, tracker):
        """Test recording buy trade."""
        trade = tracker.record_buy(
            item_name="AK-47 | Redline",
            price=Decimal("50.0"),
            marketplace=Marketplace.DMARKET,
            item_id="item1",
        )

        assert trade.trade_type == TradeType.BUY
        assert trade.commission == Decimal("0")
        assert "item1" in tracker._inventory

    def test_record_sell(self, tracker):
        """Test recording sell trade."""
        # First buy
        tracker.record_buy(
            item_name="Test",
            price=Decimal("50.0"),
            item_id="item1",
        )

        # Then sell
        trade = tracker.record_sell(
            item_name="Test",
            price=Decimal("60.0"),
            marketplace=Marketplace.WAXPEER,
            item_id="item1",
        )

        assert trade.trade_type == TradeType.SELL
        # Waxpeer 6% commission
        assert trade.commission == Decimal("3.6")
        assert trade.net_amount == Decimal("56.4")
        # Item should be removed from inventory
        assert "item1" not in tracker._inventory

    def test_calculate_realized_pnl(self, tracker):
        """Test realized P/L calculation."""
        # Buy for $50
        tracker.record_buy(
            item_name="Test",
            price=Decimal("50.0"),
        )

        # Sell for $60 (net $56.4 after 6% commission)
        tracker.record_sell(
            item_name="Test",
            price=Decimal("60.0"),
            marketplace=Marketplace.WAXPEER,
        )

        pnl = tracker.calculate_realized_pnl()
        # $56.4 - $50 = $6.4
        assert pnl == Decimal("6.4")

    def test_calculate_unrealized_pnl(self, tracker):
        """Test unrealized P/L calculation."""
        # Add items manually
        tracker._inventory["item1"] = InventoryItem(
            item_id="item1",
            item_name="Test",
            marketplace=Marketplace.DMARKET,
            purchase_price=Decimal("50.0"),
            current_price=Decimal("60.0"),
        )

        pnl = tracker.calculate_unrealized_pnl()
        assert pnl == Decimal("10.0")

    def test_get_trades_filtered(self, tracker):
        """Test filtered trade retrieval."""
        tracker.record_buy("Item1", Decimal("50.0"))
        tracker.record_buy("Item2", Decimal("60.0"))
        tracker.record_sell("Item1", Decimal("55.0"), marketplace=Marketplace.WAXPEER)

        sells = tracker.get_trades(trade_type=TradeType.SELL)
        assert len(sells) == 1

        buys = tracker.get_trades(trade_type=TradeType.BUY)
        assert len(buys) == 2

    def test_clear_history(self, tracker):
        """Test clearing history."""
        tracker.record_buy("Test", Decimal("50.0"), item_id="item1")

        tracker.clear_history()

        assert len(tracker._trades) == 0
        assert len(tracker._inventory) == 0


class TestPortfolioSummary:
    """Tests for PortfolioSummary."""

    @pytest.fixture
    def mock_dmarket_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_user_inventory = AsyncMock(return_value={"items": []})
        return api

    @pytest.mark.asyncio
    async def test_get_summary(self, mock_dmarket_api):
        """Test getting portfolio summary."""
        tracker = PortfolioTracker(dmarket_api=mock_dmarket_api)

        # Add some trades
        tracker.record_buy("Item1", Decimal("50.0"), item_id="item1")
        tracker.record_buy("Item2", Decimal("100.0"), item_id="item2")

        summary = await tracker.get_portfolio_summary()

        assert isinstance(summary, PortfolioSummary)
        assert summary.total_trades == 2

    def test_summary_to_dict(self):
        """Test summary to dict conversion."""
        summary = PortfolioSummary(
            total_value=Decimal("1000.0"),
            total_cost=Decimal("900.0"),
            total_pnl=Decimal("100.0"),
            total_pnl_percent=Decimal("11.11"),
            realized_pnl=Decimal("50.0"),
            unrealized_pnl=Decimal("50.0"),
            total_items=5,
            total_trades=10,
            win_rate=Decimal("60.0"),
            avg_trade_pnl=Decimal("10.0"),
            best_trade=None,
            worst_trade=None,
        )

        data = summary.to_dict()
        assert "total_value" in data
        assert "win_rate" in data


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""

    @pytest.fixture
    def tracker(self):
        """Create test tracker."""
        return PortfolioTracker()

    def test_performance_with_no_trades(self, tracker):
        """Test performance with no trades."""
        metrics = tracker.get_performance_metrics(days=30)

        assert metrics.total_trades == 0
        assert metrics.total_pnl == Decimal("0")

    def test_performance_with_trades(self, tracker):
        """Test performance with trades."""
        # Buy and sell
        tracker.record_buy("Item1", Decimal("50.0"))
        tracker.record_sell("Item1", Decimal("60.0"), marketplace=Marketplace.WAXPEER)

        metrics = tracker.get_performance_metrics(days=30)

        assert metrics.total_trades == 2
        assert metrics.total_volume > 0

    def test_metrics_to_dict(self):
        """Test metrics to dict conversion."""
        metrics = PerformanceMetrics(
            period_start=datetime.now(UTC) - timedelta(days=30),
            period_end=datetime.now(UTC),
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            total_volume=Decimal("1000.0"),
            total_pnl=Decimal("100.0"),
            best_day_pnl=Decimal("50.0"),
            worst_day_pnl=Decimal("-20.0"),
            avg_hold_time=timedelta(hours=24),
            profit_factor=Decimal("2.0"),
        )

        data = metrics.to_dict()
        assert "win_rate" in data
        assert data["win_rate"] == 60.0


class TestCommissions:
    """Tests for commission calculations."""

    def test_dmarket_commission(self):
        """Test DMarket commission."""
        tracker = PortfolioTracker()
        trade = tracker.record_sell(
            "Test",
            Decimal("100.0"),
            marketplace=Marketplace.DMARKET,
        )

        # DMarket 7% commission
        assert trade.commission == Decimal("7.0")
        assert trade.net_amount == Decimal("93.0")

    def test_waxpeer_commission(self):
        """Test Waxpeer commission."""
        tracker = PortfolioTracker()
        trade = tracker.record_sell(
            "Test",
            Decimal("100.0"),
            marketplace=Marketplace.WAXPEER,
        )

        # Waxpeer 6% commission
        assert trade.commission == Decimal("6.0")
        assert trade.net_amount == Decimal("94.0")

    def test_steam_commission(self):
        """Test Steam commission."""
        tracker = PortfolioTracker()
        trade = tracker.record_sell(
            "Test",
            Decimal("100.0"),
            marketplace=Marketplace.STEAM,
        )

        # Steam 15% commission
        assert trade.commission == Decimal("15.0")
        assert trade.net_amount == Decimal("85.0")


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_portfolio_tracker(self):
        """Test factory function."""
        tracker = create_portfolio_tracker()

        assert isinstance(tracker, PortfolioTracker)
        assert tracker.dmarket is None
        assert tracker.waxpeer is None


class TestInventorySync:
    """Tests for inventory synchronization."""

    @pytest.fixture
    def mock_dmarket_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_user_inventory = AsyncMock(return_value={
            "items": [
                {
                    "itemId": "item1",
                    "title": "Test Item",
                    "price": {"USD": "5000"},
                }
            ]
        })
        return api

    @pytest.mark.asyncio
    async def test_sync_inventory(self, mock_dmarket_api):
        """Test inventory sync."""
        tracker = PortfolioTracker(dmarket_api=mock_dmarket_api)

        synced = await tracker.sync_inventory()

        assert synced == 1
        assert "item1" in tracker._inventory
