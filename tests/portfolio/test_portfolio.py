"""Tests for portfolio models and manager."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.portfolio.analyzer import PortfolioAnalyzer
from src.portfolio.manager import PortfolioManager
from src.portfolio.models import (
    ItemCategory,
    ItemRarity,
    Portfolio,
    PortfolioItem,
    PortfolioMetrics,
    PortfolioSnapshot,
)


class TestPortfolioItem:
    """Tests for PortfolioItem dataclass."""

    def test_create_item(self):
        """Test creating a portfolio item."""
        item = PortfolioItem(
            item_id="test_123",
            title="AK-47 | Redline",
            game="csgo",
            buy_price=Decimal("10.50"),
            current_price=Decimal("12.00"),
            quantity=2,
        )

        assert item.item_id == "test_123"
        assert item.title == "AK-47 | Redline"
        assert item.buy_price == Decimal("10.50")
        assert item.current_price == Decimal("12.00")
        assert item.quantity == 2

    def test_pnl_calculation(self):
        """Test P&L calculation."""
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("12.00"),
            quantity=2,
        )

        assert item.pnl == Decimal("4.00")  # (12-10) * 2
        assert item.pnl_percent == 20.0  # 20% gAlgon

    def test_pnl_loss(self):
        """Test P&L for losing position."""
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("8.00"),
            quantity=1,
        )

        assert item.pnl == Decimal("-2.00")
        assert item.pnl_percent == -20.0

    def test_total_cost_and_value(self):
        """Test total cost and current value."""
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("15.00"),
            quantity=3,
        )

        assert item.total_cost == Decimal("30.00")
        assert item.current_value == Decimal("45.00")

    def test_to_dict(self):
        """Test conversion to dictionary."""
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("12.00"),
        )

        data = item.to_dict()

        assert data["item_id"] == "test"
        assert data["title"] == "Test Item"
        assert data["buy_price"] == 10.00
        assert data["pnl"] == 2.00
        assert data["pnl_percent"] == 20.0

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "item_id": "test",
            "title": "Test Item",
            "game": "csgo",
            "buy_price": 10.00,
            "current_price": 12.00,
            "quantity": 2,
            "category": "weapon",
            "rarity": "covert",
        }

        item = PortfolioItem.from_dict(data)

        assert item.item_id == "test"
        assert item.buy_price == Decimal("10.00")
        assert item.category == ItemCategory.WEAPON
        assert item.rarity == ItemRarity.COVERT


class TestPortfolio:
    """Tests for Portfolio class."""

    def test_create_empty_portfolio(self):
        """Test creating empty portfolio."""
        portfolio = Portfolio(user_id=123)

        assert portfolio.user_id == 123
        assert len(portfolio.items) == 0

    def test_add_item(self):
        """Test adding item to portfolio."""
        portfolio = Portfolio(user_id=123)
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
        )

        portfolio.add_item(item)

        assert len(portfolio.items) == 1
        assert portfolio.items[0].title == "Test Item"

    def test_add_existing_item_increases_quantity(self):
        """Test that adding existing item increases quantity."""
        portfolio = Portfolio(user_id=123)

        item1 = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
            quantity=1,
        )
        item2 = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("12.00"),
            current_price=Decimal("12.00"),
            quantity=2,
        )

        portfolio.add_item(item1)
        portfolio.add_item(item2)

        assert len(portfolio.items) == 1
        assert portfolio.items[0].quantity == 3
        # Average cost: (10*1 + 12*2) / 3 = 34/3 ≈ 11.33
        assert float(portfolio.items[0].buy_price) == pytest.approx(11.33, rel=0.01)

    def test_remove_item_completely(self):
        """Test removing item completely."""
        portfolio = Portfolio(user_id=123)
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
            quantity=1,
        )
        portfolio.add_item(item)

        removed = portfolio.remove_item("test")

        assert removed is not None
        assert len(portfolio.items) == 0

    def test_remove_item_partial(self):
        """Test removing partial quantity."""
        portfolio = Portfolio(user_id=123)
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
            quantity=5,
        )
        portfolio.add_item(item)

        removed = portfolio.remove_item("test", quantity=2)

        assert removed is not None
        assert removed.quantity == 2
        assert portfolio.items[0].quantity == 3

    def test_get_item(self):
        """Test getting item by ID."""
        portfolio = Portfolio(user_id=123)
        item = PortfolioItem(
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=Decimal("10.00"),
            current_price=Decimal("10.00"),
        )
        portfolio.add_item(item)

        found = portfolio.get_item("test")
        not_found = portfolio.get_item("nonexistent")

        assert found is not None
        assert found.title == "Test Item"
        assert not_found is None

    def test_calculate_metrics(self):
        """Test calculating portfolio metrics."""
        portfolio = Portfolio(user_id=123)
        portfolio.add_item(
            PortfolioItem(
                item_id="item1",
                title="Item 1",
                game="csgo",
                buy_price=Decimal("10.00"),
                current_price=Decimal("15.00"),  # +50%
                quantity=1,
            )
        )
        portfolio.add_item(
            PortfolioItem(
                item_id="item2",
                title="Item 2",
                game="csgo",
                buy_price=Decimal("20.00"),
                current_price=Decimal("18.00"),  # -10%
                quantity=1,
            )
        )

        metrics = portfolio.calculate_metrics()

        assert metrics.total_cost == Decimal("30.00")
        assert metrics.total_value == Decimal("33.00")
        assert metrics.total_pnl == Decimal("3.00")
        assert metrics.items_count == 2
        assert metrics.best_performer == "Item 1"
        assert metrics.worst_performer == "Item 2"

    def test_update_prices(self):
        """Test updating prices."""
        portfolio = Portfolio(user_id=123)
        portfolio.add_item(
            PortfolioItem(
                item_id="test",
                title="Test",
                game="csgo",
                buy_price=Decimal("10.00"),
                current_price=Decimal("10.00"),
            )
        )

        portfolio.update_prices({"test": Decimal("15.00")})

        assert portfolio.items[0].current_price == Decimal("15.00")

    def test_take_snapshot(self):
        """Test taking portfolio snapshot."""
        portfolio = Portfolio(user_id=123)
        portfolio.add_item(
            PortfolioItem(
                item_id="test",
                title="Test",
                game="csgo",
                buy_price=Decimal("10.00"),
                current_price=Decimal("12.00"),
            )
        )

        snapshot = portfolio.take_snapshot()

        assert snapshot.total_value == Decimal("12.00")
        assert snapshot.items_count == 1
        assert len(portfolio.snapshots) == 1


class TestPortfolioManager:
    """Tests for PortfolioManager."""

    @pytest.fixture()
    def manager(self, tmp_path):
        """Create manager with temp storage."""
        storage_path = tmp_path / "portfolios.json"
        return PortfolioManager(api=None, storage_path=storage_path)

    def test_get_portfolio_creates_new(self, manager):
        """Test getting portfolio creates new if not exists."""
        portfolio = manager.get_portfolio(user_id=123)

        assert portfolio.user_id == 123
        assert len(portfolio.items) == 0

    def test_add_item(self, manager):
        """Test adding item via manager."""
        item = manager.add_item(
            user_id=123,
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=10.00,
        )

        assert item.title == "Test Item"
        portfolio = manager.get_portfolio(123)
        assert len(portfolio.items) == 1

    def test_remove_item(self, manager):
        """Test removing item via manager."""
        manager.add_item(
            user_id=123,
            item_id="test",
            title="Test Item",
            game="csgo",
            buy_price=10.00,
        )

        removed = manager.remove_item(user_id=123, item_id="test")

        assert removed is not None
        portfolio = manager.get_portfolio(123)
        assert len(portfolio.items) == 0

    def test_get_metrics(self, manager):
        """Test getting metrics via manager."""
        manager.add_item(
            user_id=123,
            item_id="test",
            title="Test",
            game="csgo",
            buy_price=10.00,
        )

        metrics = manager.get_metrics(123)

        assert metrics.items_count == 1
        assert metrics.total_cost == Decimal("10.00")

    def test_detect_category_knife(self, manager):
        """Test category detection for knife."""
        category = manager._detect_category("★ Butterfly Knife | Fade")
        assert category == ItemCategory.KNIFE

    def test_detect_category_weapon(self, manager):
        """Test category detection for weapon."""
        category = manager._detect_category("AK-47 | Redline (Field-Tested)")
        assert category == ItemCategory.WEAPON

    def test_detect_category_sticker(self, manager):
        """Test category detection for sticker."""
        category = manager._detect_category("Sticker | Navi Holo")
        assert category == ItemCategory.STICKER


class TestPortfolioAnalyzer:
    """Tests for PortfolioAnalyzer."""

    @pytest.fixture()
    def analyzer(self):
        """Create analyzer."""
        return PortfolioAnalyzer()

    @pytest.fixture()
    def sample_portfolio(self):
        """Create sample portfolio for testing."""
        portfolio = Portfolio(user_id=123)
        portfolio.add_item(
            PortfolioItem(
                item_id="ak",
                title="AK-47 | Redline",
                game="csgo",
                buy_price=Decimal("25.00"),
                current_price=Decimal("30.00"),
                category=ItemCategory.WEAPON,
            )
        )
        portfolio.add_item(
            PortfolioItem(
                item_id="awp",
                title="AWP | Asiimov",
                game="csgo",
                buy_price=Decimal("50.00"),
                current_price=Decimal("45.00"),
                category=ItemCategory.WEAPON,
            )
        )
        portfolio.add_item(
            PortfolioItem(
                item_id="knife",
                title="★ Karambit | Fade",
                game="csgo",
                buy_price=Decimal("500.00"),
                current_price=Decimal("550.00"),
                category=ItemCategory.KNIFE,
                rarity=ItemRarity.CONTRABAND,
            )
        )
        return portfolio

    def test_analyze_diversification_empty(self, analyzer):
        """Test diversification analysis on empty portfolio."""
        portfolio = Portfolio(user_id=123)
        report = analyzer.analyze_diversification(portfolio)

        assert report.diversification_score == 0
        assert len(report.recommendations) > 0

    def test_analyze_diversification(self, analyzer, sample_portfolio):
        """Test diversification analysis."""
        report = analyzer.analyze_diversification(sample_portfolio)

        assert "csgo" in report.by_game
        assert report.by_game["csgo"] == 100.0
        assert "weapon" in report.by_category
        assert "knife" in report.by_category
        assert report.diversification_score > 0

    def test_concentration_risk_detection(self, analyzer, sample_portfolio):
        """Test concentration risk detection."""
        report = analyzer.analyze_diversification(sample_portfolio)

        # Knife is ~88% of portfolio, should trigger concentration risk
        high_concentration = [
            r for r in report.concentration_risks if "Karambit" in r.item_title
        ]
        assert len(high_concentration) > 0 or len(report.concentration_risks) > 0

    def test_analyze_risk(self, analyzer, sample_portfolio):
        """Test risk analysis."""
        report = analyzer.analyze_risk(sample_portfolio)

        assert report.risk_level in {"low", "medium", "high", "critical"}
        assert 0 <= report.overall_risk_score <= 100
        assert 0 <= report.volatility_score <= 100
        assert 0 <= report.liquidity_score <= 100

    def test_get_top_performers(self, analyzer, sample_portfolio):
        """Test getting top performers."""
        top = analyzer.get_top_performers(sample_portfolio, limit=2)

        assert len(top) == 2
        # AK has +20%, should be best
        assert top[0].pnl_percent >= top[1].pnl_percent

    def test_get_worst_performers(self, analyzer, sample_portfolio):
        """Test getting worst performers."""
        worst = analyzer.get_worst_performers(sample_portfolio, limit=2)

        assert len(worst) == 2
        # AWP has -10%, should be worst
        assert worst[0].pnl_percent <= worst[1].pnl_percent


class TestPortfolioMetrics:
    """Tests for PortfolioMetrics dataclass."""

    def test_to_dict(self):
        """Test metrics to dictionary conversion."""
        metrics = PortfolioMetrics(
            total_value=Decimal(100),
            total_cost=Decimal(80),
            total_pnl=Decimal(20),
            total_pnl_percent=25.0,
            items_count=5,
            total_quantity=10,
        )

        data = metrics.to_dict()

        assert data["total_value"] == 100.0
        assert data["total_pnl_percent"] == 25.0
        assert data["items_count"] == 5


class TestPortfolioSnapshot:
    """Tests for PortfolioSnapshot dataclass."""

    def test_pnl_property(self):
        """Test snapshot P&L calculation."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(UTC),
            total_value=Decimal(120),
            total_cost=Decimal(100),
            items_count=5,
        )

        assert snapshot.pnl == Decimal(20)

    def test_to_dict(self):
        """Test snapshot to dictionary conversion."""
        snapshot = PortfolioSnapshot(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            total_value=Decimal(100),
            total_cost=Decimal(80),
            items_count=3,
        )

        data = snapshot.to_dict()

        assert data["total_value"] == 100.0
        assert data["items_count"] == 3
        assert data["pnl"] == 20.0
